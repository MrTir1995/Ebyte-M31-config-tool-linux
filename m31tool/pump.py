"""Pressure-based M31 pump control for a 4–20 mA, 0–10 bar transmitter."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import logging
import math
import os
from pathlib import Path
import signal
import tempfile
from threading import Event, Lock

from m31tool.core import (
    ModbusConnectionError,
    ModbusError,
    ModbusResponseError,
    ModbusSession,
)
from m31tool.homeassistant import HomeAssistantMqtt


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
MIN_PRESSURE_BAR = 0.0
MAX_PRESSURE_BAR = 10.0


@dataclass(frozen=True)
class PumpStatus:
    pressure_bar: float | None
    raw_process_value: int
    sensor_valid: bool
    motor_fault: bool
    running_feedback: bool
    output_on: bool


@dataclass(frozen=True)
class PumpSettingsSnapshot:
    enabled: bool
    start_pressure_bar: float
    stop_pressure_bar: float


def _validated_pressures(start_pressure_bar: float, stop_pressure_bar: float) -> tuple[float, float]:
    values = (start_pressure_bar, stop_pressure_bar)
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
           or not math.isfinite(value) for value in values):
        raise ValueError("Pressure limits must be finite numbers.")
    start_pressure_bar = float(start_pressure_bar)
    stop_pressure_bar = float(stop_pressure_bar)
    if not MIN_PRESSURE_BAR <= start_pressure_bar < stop_pressure_bar <= MAX_PRESSURE_BAR:
        raise ValueError("Pressure limits must satisfy 0 <= start < stop <= 10 bar.")
    if any(not math.isclose(value * 10, round(value * 10), abs_tol=1e-8)
           for value in (start_pressure_bar, stop_pressure_bar)):
        raise ValueError("Pressure limits must use 0.1 bar increments.")
    return start_pressure_bar, stop_pressure_bar


class PumpSettings:
    """Thread-safe pressure and enable settings, optionally persisted on disk."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        start_pressure_bar: float = PRESSURE_START_BAR,
        stop_pressure_bar: float = PRESSURE_STOP_BAR,
        path: str | Path | None = None,
    ):
        if not isinstance(enabled, bool):
            raise ValueError("Automation enabled state must be boolean.")
        start_pressure_bar, stop_pressure_bar = _validated_pressures(
            start_pressure_bar, stop_pressure_bar
        )
        self._lock = Lock()
        self._path = Path(path) if path is not None else None
        self._snapshot = PumpSettingsSnapshot(
            enabled, start_pressure_bar, stop_pressure_bar
        )
        if self._path is not None and self._path.exists():
            self._snapshot = self._read()

    def _read(self) -> PumpSettingsSnapshot:
        try:
            values = json.loads(self._path.read_text(encoding="utf-8"))
            enabled = values["enabled"]
            if not isinstance(enabled, bool):
                raise ValueError("Persisted automation enabled state must be boolean.")
            start, stop = _validated_pressures(
                values["start_pressure_bar"], values["stop_pressure_bar"]
            )
            return PumpSettingsSnapshot(enabled, start, stop)
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid pump settings file: {self._path}") from exc

    def snapshot(self) -> PumpSettingsSnapshot:
        with self._lock:
            return self._snapshot

    def set_enabled(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("Automation enabled state must be boolean.")
        with self._lock:
            self._replace(enabled=enabled)

    def set_pressure(self, setting: str, value: float) -> None:
        if setting not in ("start_pressure_bar", "stop_pressure_bar"):
            raise ValueError("Unknown pressure setting.")
        with self._lock:
            current = self._snapshot
            start = value if setting == "start_pressure_bar" else current.start_pressure_bar
            stop = value if setting == "stop_pressure_bar" else current.stop_pressure_bar
            start, stop = _validated_pressures(start, stop)
            self._replace(start_pressure_bar=start, stop_pressure_bar=stop)

    def _replace(
        self,
        *,
        enabled: bool | None = None,
        start_pressure_bar: float | None = None,
        stop_pressure_bar: float | None = None,
    ) -> None:
        current = self._snapshot
        candidate = PumpSettingsSnapshot(
            current.enabled if enabled is None else enabled,
            current.start_pressure_bar if start_pressure_bar is None else start_pressure_bar,
            current.stop_pressure_bar if stop_pressure_bar is None else stop_pressure_bar,
        )
        if self._path is not None:
            self._write(candidate)
        self._snapshot = candidate

    def _write(self, snapshot: PumpSettingsSnapshot) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self._path.parent,
                prefix=f".{self._path.name}.", delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                os.chmod(temporary_path, 0o600)
                json.dump(
                    {
                        "enabled": snapshot.enabled,
                        "start_pressure_bar": snapshot.start_pressure_bar,
                        "stop_pressure_bar": snapshot.stop_pressure_bar,
                    },
                    temporary,
                )
                temporary.write("\n")
            os.replace(temporary_path, self._path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()


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

    def scan(
        self,
        *,
        enabled: bool = True,
        start_pressure_bar: float = PRESSURE_START_BAR,
        stop_pressure_bar: float = PRESSURE_STOP_BAR,
    ) -> PumpStatus:
        start_pressure_bar, stop_pressure_bar = _validated_pressures(
            start_pressure_bar, stop_pressure_bar
        )
        start_raw = math.ceil(
            (4 + start_pressure_bar * 16 / 10) * PROCESS_VALUE_MAX / 20
        )
        stop_raw = math.floor(
            (4 + stop_pressure_bar * 16 / 10) * PROCESS_VALUE_MAX / 20
        )
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

        if not enabled or not di1_healthy or pressure_bar is None:
            target_output = False
        elif raw_value < start_raw:
            target_output = True
        elif raw_value >= stop_raw:
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
    home_assistant = None
    try:
        settings = PumpSettings(
            enabled=True,
            start_pressure_bar=args.start_pressure,
            stop_pressure_bar=args.stop_pressure,
            path=args.settings_file,
        )
        if args.mqtt_host:
            home_assistant = HomeAssistantMqtt(
                settings,
                host=args.mqtt_host,
                port=args.mqtt_port,
                discovery_prefix=args.mqtt_discovery_prefix,
                device_id=args.device_id,
                credentials=(args.mqtt_username, args.mqtt_password),
            )
            home_assistant.start()
        while not stop.is_set():
            try:
                if not session.connected:
                    session.open_tcp(args.host, args.port)
                current_settings = settings.snapshot()
                status = controller.scan(
                    enabled=current_settings.enabled,
                    start_pressure_bar=current_settings.start_pressure_bar,
                    stop_pressure_bar=current_settings.stop_pressure_bar,
                )
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
        if home_assistant is not None:
            home_assistant.stop()
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
    parser.add_argument("--start-pressure", type=float, default=PRESSURE_START_BAR)
    parser.add_argument("--stop-pressure", type=float, default=PRESSURE_STOP_BAR)
    parser.add_argument(
        "--settings-file", type=Path,
        default=Path.home() / ".config" / "m31-pump" / "settings.json",
        help="local settings file (default: ~/.config/m31-pump/settings.json)",
    )
    parser.add_argument("--mqtt-host", default=None, help="MQTT broker host; enables Home Assistant discovery")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--mqtt-discovery-prefix", default="homeassistant")
    parser.add_argument("--device-id", default="m31_pump")
    parser.add_argument(
        "--mqtt-username", default=os.environ.get("M31_MQTT_USERNAME"),
        help="MQTT username (password is read from M31_MQTT_PASSWORD)",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in 1..65535")
    if not 1 <= args.unit_id <= 247:
        parser.error("--unit-id must be in 1..247")
    if not 0 <= args.ai_address <= 65535:
        parser.error("--ai-address must be in 0..65535")
    if args.mqtt_host == "":
        args.mqtt_host = None
    args.mqtt_password = os.environ.get("M31_MQTT_PASSWORD")
    if args.mqtt_host is None and (args.mqtt_username or args.mqtt_password):
        parser.error("--mqtt-host is required when MQTT credentials are configured")
    if not 1 <= args.mqtt_port <= 65535:
        parser.error("--mqtt-port must be in 1..65535")
    if (not args.mqtt_discovery_prefix.strip("/")
            or any(char in args.mqtt_discovery_prefix for char in "+#")):
        parser.error("--mqtt-discovery-prefix must be a valid topic prefix")
    if args.mqtt_username and not args.mqtt_password:
        parser.error("M31_MQTT_PASSWORD is required when an MQTT username is set")
    if args.mqtt_password and not args.mqtt_username:
        parser.error("M31_MQTT_USERNAME is required when an MQTT password is set")
    try:
        _validated_pressures(args.start_pressure, args.stop_pressure)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.device_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_" for char in args.device_id):
        parser.error("--device-id may contain only lowercase letters, digits, and underscores")

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
