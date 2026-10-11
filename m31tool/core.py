"""Synchronous Modbus transport and the documented M31 register addresses.

Addresses are zero-based Modbus PDU addresses, not 3xxxx/4xxxx notation.
The catalog records starting addresses only; channel counts, float word order,
scaling, and model-specific ranges must be verified against the actual device.
"""

from dataclasses import dataclass
from enum import Enum
import math
from threading import RLock
from typing import Any

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException as PymodbusException
from serial import SerialException


class ModbusError(Exception):
    """Base class for communication and device-response failures."""


class ModbusConnectionError(ModbusError):
    """Connection establishment or a Modbus exchange failed."""


class ModbusResponseError(ModbusError):
    """The device returned a Modbus exception or an invalid acknowledgment."""


class RegisterKind(str, Enum):
    """The four standard Modbus data tables."""

    COILS = "coils"
    DISCRETE_INPUTS = "discrete_inputs"
    HOLDING_REGISTERS = "holding_registers"
    INPUT_REGISTERS = "input_registers"


@dataclass(frozen=True)
class RegisterSpec:
    """Descriptive address information, not a complete device layout."""

    key: str
    label: str
    table: str
    address: int
    description: str
    words_per_value: int | None = None
    min_value: int | None = None
    max_value: int | None = None
    default: int | None = None

    @property
    def kind(self) -> RegisterKind:
        return RegisterKind(self.table)


DI_START = 0x0000
DO_START = 0x0000
FILTER_DI_ADDRESS = 0x0DA3
FILTER_AI_ADDRESS = 0x0DA2
FILTER_MIN = 1
FILTER_MAX = 16
FILTER_DEFAULT = 6

M31_REGISTER_CATALOG = (
    RegisterSpec("di", "Digitale Eingänge", "discrete_inputs", DI_START,
                 "DI ab Adresse 0; Anzahl modellabhängig."),
    RegisterSpec("do", "Digitale Ausgänge", "coils", DO_START,
                 "DO ab Adresse 0; Anzahl und Lastgrenzen modellabhängig."),
    RegisterSpec("ai_integer", "AI Ganzzahl", "input_registers", 0x0000,
                 "Ganzzahl-Messwerte; Kanalanzahl und Skalierung nicht festgelegt."),
    RegisterSpec("ai_float", "AI IEEE754", "input_registers", 0x03E8,
                 "IEEE754 über zwei Register; Wortreihenfolge nicht festgelegt.",
                 words_per_value=2),
    RegisterSpec("ai_process", "AI Prozesswert", "input_registers", 0x0BB8,
                 "Prozesswerte; Layout, Skalierung und Einheiten nicht festgelegt."),
    RegisterSpec("ao_integer", "AO Ganzzahl", "holding_registers", 0x0000,
                 "AO-Basisadresse; Kanalanzahl, Skalierung und Bereich nicht festgelegt."),
    RegisterSpec("ao_float", "AO 0x03E8", "holding_registers", 0x03E8,
                 "Dokumentierte AO-Adresse; Layout und Wortreihenfolge nicht festgelegt."),
    RegisterSpec("ao_alternative", "AO 0x01F4", "holding_registers", 0x01F4,
                 "Dokumentierte AO-Adresse; Layout und Wertebereich nicht festgelegt."),
    RegisterSpec("di_filter", "DI Filter", "holding_registers", FILTER_DI_ADDRESS,
                 "DI-Filterwert 1–16, Standardwert 6; wird nicht automatisch gesetzt.",
                 words_per_value=1, min_value=FILTER_MIN, max_value=FILTER_MAX,
                 default=FILTER_DEFAULT),
    RegisterSpec("ai_filter", "AI Filter", "holding_registers", FILTER_AI_ADDRESS,
                 "AI-Filterwert 1–16, Standardwert 6; wird nicht automatisch gesetzt.",
                 words_per_value=1, min_value=FILTER_MIN, max_value=FILTER_MAX,
                 default=FILTER_DEFAULT),
)
REGISTER_CATALOG = M31_REGISTER_CATALOG
M31_REGISTERS = M31_REGISTER_CATALOG


def _integer(name: str, value: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be in {minimum}..{maximum}.")
    return value


def _text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string.")
    return value.strip()


class ModbusSession:
    """One explicit TCP/RTU connection, with serialized synchronous requests.

    Construction is local only. Unit IDs 1–247 exclude unsafe RTU broadcasts.
    Each write sends one request (no automatic retries), validates its echoed
    acknowledgment, and returns None. An acknowledgment is not readback:
    callers must explicitly read and compare after a confirmed write. A timeout
    may mean a write was applied but its response was lost; do not blindly retry.
    """

    def __init__(self, unit_id: int = 1, timeout: float = 2.0):
        self._unit_id = _integer("unit_id", unit_id, 1, 247)
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("timeout must be a finite positive number.")
        self._timeout = float(timeout)
        self._client: ModbusTcpClient | ModbusSerialClient | None = None
        self._lock = RLock()

    @property
    def unit_id(self) -> int:
        return self._unit_id

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def connected(self) -> bool:
        """Local transport state; this does not probe the remote device."""
        with self._lock:
            return self._client is not None and bool(self._client.connected)

    def open_tcp(self, host: str, port: int = 502) -> None:
        host = _text("host", host)
        port = _integer("TCP port", port, 1, 65535)
        with self._lock:
            self.close()
            client = ModbusTcpClient(
                host, port=port, timeout=self.timeout, retries=0,
            )
            self._connect(client, f"TCP {host}:{port}")

    def open_rtu(
        self, port: str, baudrate: int = 9600, parity: str = "N",
        stopbits: int = 1,
    ) -> None:
        port = _text("serial port", port)
        baudrate = _integer("baudrate", baudrate, 1, 4_000_000)
        if not isinstance(parity, str) or parity.upper() not in ("N", "E", "O"):
            raise ValueError("parity must be N, E, or O.")
        stopbits = _integer("stopbits", stopbits, 1, 2)
        with self._lock:
            self.close()
            client = ModbusSerialClient(
                port, baudrate=baudrate, bytesize=8, parity=parity.upper(),
                stopbits=stopbits, timeout=self.timeout, retries=0,
            )
            self._connect(client, f"RTU {port}")

    def _connect(self, client: Any, endpoint: str) -> None:
        try:
            if not client.connect():
                raise ModbusConnectionError(f"Could not connect to {endpoint}.")
        except (OSError, SerialException, PymodbusException) as exc:
            client.close()
            raise ModbusConnectionError(f"Could not connect to {endpoint}: {exc}") from exc
        except ModbusConnectionError:
            client.close()
            raise
        self._client = client

    def close(self) -> None:
        """Close the transport; safe to call repeatedly."""
        with self._lock:
            client, self._client = self._client, None
            if client is not None:
                try:
                    client.close()
                except (OSError, SerialException, PymodbusException) as exc:
                    raise ModbusConnectionError(f"Could not close transport: {exc}") from exc

    @staticmethod
    def _span(address: int, count: int, maximum: int) -> None:
        _integer("address", address, 0, 65535)
        _integer("count", count, 1, maximum)
        if address + count > 65536:
            raise ValueError("Requested range exceeds Modbus address 65535.")

    def _request(self, method: str, function_code: int, **kwargs: Any) -> Any:
        if not self.connected:
            raise ModbusConnectionError("No open Modbus connection.")
        try:
            response = getattr(self._client, method)(
                **kwargs, device_id=self.unit_id,
            )
        except (OSError, SerialException, PymodbusException) as exc:
            raise ModbusConnectionError(
                f"{method} failed: {exc}. For writes, the device state may be unknown."
            ) from exc
        if response is None:
            raise ModbusResponseError(f"{method} returned no response.")
        if not callable(getattr(response, "isError", None)):
            raise ModbusResponseError(f"{method}: invalid response object.")
        if response.isError():
            code = getattr(response, "exception_code", None)
            raise ModbusResponseError(
                f"{method}: device returned Modbus exception {code}."
            )
        if getattr(response, "function_code", None) != function_code:
            raise ModbusResponseError(f"{method}: unexpected response function code.")
        return response

    def _read(self, method: str, function_code: int, address: int,
              count: int, bits: bool) -> list[int] | list[bool]:
        self._span(address, count, 2000 if bits else 125)
        with self._lock:
            response = self._request(
                method, function_code, address=address, count=count,
            )
            values = getattr(response, "bits" if bits else "registers", None)
            if not isinstance(values, (list, tuple)) or len(values) < count:
                raise ModbusResponseError(f"{method}: truncated or invalid response.")
            if bits:
                if any(type(value) not in (int, bool) or value not in (0, 1)
                       for value in values[:count]):
                    raise ModbusResponseError(f"{method}: invalid bit values.")
                return [bool(value) for value in values[:count]]
            if len(values) != count or any(
                isinstance(value, bool) or not isinstance(value, int)
                or not 0 <= value <= 65535 for value in values
            ):
                raise ModbusResponseError(f"{method}: invalid register values.")
            return list(values)

    def read_coils(self, address: int, count: int) -> list[bool]:
        return self._read("read_coils", 1, address, count, True)

    def read_discrete_inputs(self, address: int, count: int) -> list[bool]:
        return self._read("read_discrete_inputs", 2, address, count, True)

    def read_holding_registers(self, address: int, count: int) -> list[int]:
        return self._read("read_holding_registers", 3, address, count, False)

    def read_input_registers(self, address: int, count: int) -> list[int]:
        return self._read("read_input_registers", 4, address, count, False)

    def write_coil(self, address: int, value: bool | int) -> None:
        _integer("address", address, 0, 65535)
        if type(value) not in (bool, int) or value not in (False, True):
            raise ValueError("coil value must be bool or integer 0/1.")
        value = bool(value)
        with self._lock:
            response = self._request("write_coil", 5, address=address, value=value)
            if (getattr(response, "address", None) != address
                    or getattr(response, "bits", None) != [value]):
                raise ModbusResponseError("write_coil: acknowledgment does not match request.")

    def write_coils(self, address: int, values: list[bool]) -> None:
        if not isinstance(values, list):
            raise ValueError("coil values must be a list of booleans.")
        self._span(address, len(values), 1968)
        if any(type(value) is not bool for value in values):
            raise ValueError("coil values must be a list of booleans.")
        with self._lock:
            response = self._request(
                "write_coils", 15, address=address, values=values,
            )
            if (getattr(response, "address", None) != address
                    or getattr(response, "count", None) != len(values)):
                raise ModbusResponseError(
                    "write_coils: acknowledgment does not match request."
                )

    def write_register(self, address: int, value: int) -> None:
        _integer("address", address, 0, 65535)
        _integer("register value", value, 0, 65535)
        if address in (FILTER_DI_ADDRESS, FILTER_AI_ADDRESS):
            _integer("filter value", value, FILTER_MIN, FILTER_MAX)
        with self._lock:
            response = self._request("write_register", 6, address=address, value=value)
            if (getattr(response, "address", None) != address
                    or getattr(response, "registers", None) != [value]):
                raise ModbusResponseError(
                    "write_register: acknowledgment does not match request."
                )

    def write_registers(self, address: int, values: list[int]) -> None:
        if not isinstance(values, list):
            raise ValueError("register values must be a list of integers.")
        self._span(address, len(values), 123)
        for offset, value in enumerate(values):
            _integer("register value", value, 0, 65535)
            if address + offset in (FILTER_DI_ADDRESS, FILTER_AI_ADDRESS):
                _integer("filter value", value, FILTER_MIN, FILTER_MAX)
        with self._lock:
            response = self._request(
                "write_registers", 16, address=address, values=values,
            )
            if (getattr(response, "address", None) != address
                    or getattr(response, "count", None) != len(values)):
                raise ModbusResponseError(
                    "write_registers: acknowledgment does not match request."
                )


__all__ = [
    "ModbusSession", "ModbusError", "ModbusConnectionError", "ModbusResponseError",
    "RegisterKind", "RegisterSpec", "M31_REGISTERS", "M31_REGISTER_CATALOG",
    "REGISTER_CATALOG", "DI_START", "DO_START",
    "FILTER_DI_ADDRESS", "FILTER_AI_ADDRESS", "FILTER_MIN", "FILTER_MAX",
    "FILTER_DEFAULT",
]
