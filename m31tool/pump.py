"""Pressure-based M31 pump control for a 4–20 mA, 0–10 bar transmitter."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import logging
import math
import signal
from threading import Event

from m31tool.core import (
    ModbusConnectionError,
    ModbusError,
    ModbusResponseError,
    ModbusSession,
)


LOGGER = logging.getLogger("m31tool.pump")
DI_START = 0
DO_PUMP = 0
AI1_PROCESS_REGISTER = 0x0BB8
PRESSURE_START_BAR = 1.6
PRESSURE_STOP_BAR = 3.0
PROCESS_VALUE_MAX = 27648
PROCESS_VALUE_AT_4_MA = 4 * PROCESS_VALUE_MAX / 20
PRESSURE_START_RAW = math.ceil(
    (4 + PRESSURE_START_BAR * 16 / 10) * PROCESS_VALUE_MAX / 20
)
PRESSURE_STOP_RAW = math.floor(
    (4 + PRESSURE_STOP_BAR * 16 / 10) * PROCESS_VALUE_MAX / 20
)


@dataclass(frozen=True)
class PumpStatus:
    pressure_bar: float | None
    raw_process_value: int
    sensor_valid: bool
    motor_fault: bool
    running_feedback: bool
    output_on: bool


def _signed_int16(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 65535:
        raise ValueError("AI process register must be an unsigned 16-bit integer.")
    return value - 65536 if value >= 32768 else value


def pressure_from_process_value(value: int) -> float:
    """Convert the M31's 0–20 mA process value to 0–10 bar at 4–20 mA."""
    value = _signed_int16(value)
    if not PROCESS_VALUE_AT_4_MA <= value <= PROCESS_VALUE_MAX:
        raise ValueError("AI value is outside the configured 4–20 mA sensor range.")
    current_ma = value * 20 / PROCESS_VALUE_MAX
    return (current_ma - 4) * (10 / 16)


class PumpController:
    """Apply the pressure hysteresis and motor-fault interlock for one scan."""

    def __init__(self, session: ModbusSession, ai_address: int = AI1_PROCESS_REGISTER):
        self.session = session
        if isinstance(ai_address, bool) or not isinstance(ai_address, int) or not 0 <= ai_address <= 65535:
            raise ValueError("AI address must be an integer in 0..65535.")
        self.ai_address = ai_address

    def scan(self) -> PumpStatus:
        digital_inputs = self.session.read_discrete_inputs(DI_START, 2)
        if len(digital_inputs) != 2:
            raise ModbusResponseError("DI read did not return DI1 and DI2.")
        analog_values = self.session.read_input_registers(self.ai_address, 1)
        if len(analog_values) != 1:
            raise ModbusResponseError("AI read did not return the AI1 process value.")
        raw_value = analog_values[0]
        output_values = self.session.read_coils(DO_PUMP, 1)
        if len(output_values) != 1:
            raise ModbusResponseError("DO read did not return DO1.")

        try:
            pressure_bar = pressure_from_process_value(raw_value)
        except ValueError:
            pressure_bar = None

        di1_healthy, running_feedback = digital_inputs
        current_output = output_values[0]

        if not di1_healthy or pressure_bar is None:
            target_output = False
        elif raw_value < PRESSURE_START_RAW:
            target_output = True
        elif raw_value >= PRESSURE_STOP_RAW:
            target_output = False
        else:
            target_output = current_output

        if target_output != current_output:
            self.session.write_coil(DO_PUMP, target_output)
            confirmed_output = self.session.read_coils(DO_PUMP, 1)
            if len(confirmed_output) != 1 or confirmed_output[0] != target_output:
                raise ModbusResponseError("DO1 readback does not match the requested state.")
            current_output = confirmed_output[0]

        return PumpStatus(
            pressure_bar=pressure_bar,
            raw_process_value=raw_value,
            sensor_valid=pressure_bar is not None,
            motor_fault=not di1_healthy,
            running_feedback=running_feedback,
            output_on=current_output,
        )


def _positive_seconds(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number greater than zero") from exc
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("must be a number greater than zero")
    return result


def _safe_stop(session: ModbusSession, host: str, port: int) -> None:
    try:
        if not session.connected:
            session.open_tcp(host, port)
        session.write_coil(DO_PUMP, False)
        readback = session.read_coils(DO_PUMP, 1)
        if len(readback) != 1 or readback[0]:
            raise ModbusResponseError("DO1 could not be confirmed off.")
        LOGGER.info("DO1 confirmed off.")
    except ModbusError as exc:
        LOGGER.error("Could not confirm pump shutdown: %s", exc)


def _run(args: argparse.Namespace, stop: Event) -> None:
    session = ModbusSession(unit_id=args.unit_id, timeout=args.timeout)
    controller = PumpController(session, ai_address=args.ai_address)
    try:
        while not stop.is_set():
            try:
                if not session.connected:
                    session.open_tcp(args.host, args.port)
                status = controller.scan()
                pressure = (
                    f"{status.pressure_bar:.3f} bar"
                    if status.pressure_bar is not None
                    else f"ungültig (Rohwert {status.raw_process_value})"
                )
                LOGGER.info(
                    "Druck %s; DI1-Störung=%s; DI2-Betrieb=%s; DO1-Pumpe=%s",
                    pressure,
                    "ja" if status.motor_fault else "nein",
                    "ein" if status.running_feedback else "aus",
                    "ein" if status.output_on else "aus",
                )
            except ModbusError as exc:
                LOGGER.error("Modbus-Fehler; Pumpe wird sicher abgeschaltet: %s", exc)
                _safe_stop(session, args.host, args.port)
                try:
                    session.close()
                except ModbusConnectionError as close_error:
                    LOGGER.error("Could not close Modbus session: %s", close_error)
            stop.wait(args.interval)
    finally:
        _safe_stop(session, args.host, args.port)
        try:
            session.close()
        except ModbusConnectionError as exc:
            LOGGER.error("Could not close Modbus session: %s", exc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Control M31 DO1 from AI1 pressure and DI1 motor-fault status."
    )
    parser.add_argument("--host", required=True, help="M31 host IPv4 address or hostname")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port (default: 502)")
    parser.add_argument("--unit-id", type=int, default=1, help="Modbus unit ID (default: 1)")
    parser.add_argument(
        "--ai-address", type=int, default=AI1_PROCESS_REGISTER,
        help="AI1 process-value register address (default: 3000)",
    )
    parser.add_argument("--timeout", type=_positive_seconds, default=2.0)
    parser.add_argument("--interval", type=_positive_seconds, default=1.0)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in 1..65535")
    if not 1 <= args.unit_id <= 247:
        parser.error("--unit-id must be in 1..247")
    if not 0 <= args.ai_address <= 65535:
        parser.error("--ai-address must be in 0..65535")

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    stop = Event()
    previous_handlers = {}

    def request_stop(_signum, _frame):
        stop.set()

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.signal(signum, request_stop)
        _run(args, stop)
    except KeyboardInterrupt:
        stop.set()
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
