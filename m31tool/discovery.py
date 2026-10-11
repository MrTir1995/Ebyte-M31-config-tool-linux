"""Explicit, bounded, read-only discovery of logical Modbus targets.

Nothing enumerates local networks or serial ports. A successful read identifies
an endpoint/unit pair, not a physical device: TCP gateways may proxy many units.
Protocol exceptions remain diagnostic observations, not discoveries, because
core.ModbusResponseError does not distinguish valid exception frames from
missing or malformed replies. Devices without a readable address zero can
therefore remain undiscovered.

Scans are synchronous; run them in a worker, not a GUI event loop. Progress is
called as ``progress(attempted, total, target)`` after each started candidate.
It runs on the caller's thread and must marshal GUI updates itself. Cancellation
is checked between candidates and probes; an in-flight exchange still waits for
its configured timeout. Each candidate uses at most three one-value reads, with
no retries or writes. Limits apply to unique endpoint/unit combinations (1024),
explicit hosts (256), and timeout (0 < timeout <= 60 seconds).
"""

from dataclasses import dataclass, field
import ipaddress
import math
import re
from threading import Event, Lock
from typing import Callable

from .core import ModbusError, ModbusResponseError, ModbusSession


MAX_HOSTS = 256
MAX_CANDIDATES = 1024
_RTU_SCAN_LOCK = Lock()


@dataclass(frozen=True)
class DeviceTarget:
    """Connection parameters; unit_id always remains the Modbus address.

    TCP uses host/port; RTU uses serial_port/baudrate/parity/stopbits. The
    unused endpoint fields are None. Equality identifies a logical target.
    """

    transport: str
    unit_id: int
    host: str | None = None
    port: int | None = None
    serial_port: str | None = None
    baudrate: int | None = None
    parity: str | None = None
    stopbits: int | None = None


@dataclass(frozen=True)
class DiscoveryError:
    """A failed connection, probe, or close (also retained before success)."""

    target: DeviceTarget
    operation: str
    message: str


@dataclass
class DiscoveryResult:
    """Devices are confirmed by reads only; errors never imply success.

    attempted counts started candidates, total counts validated unique
    candidates, probes_attempted counts read calls, and cancelled records an
    observed cancellation. A cancelled result can contain earlier discoveries.
    """

    devices: list[DeviceTarget] = field(default_factory=list)
    errors: list[DiscoveryError] = field(default_factory=list)
    attempted: int = 0
    total: int = 0
    probes_attempted: int = 0
    cancelled: bool = False


ProgressCallback = Callable[[int, int, DeviceTarget], None]


def _integer(name: str, value: int, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}.")
    return value


def _host(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Host must be a nonempty IP address or DNS name.")
    host = value.strip()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if (len(host) > 253 or re.fullmatch(r"[0-9.]+", host)
                or not all(re.fullmatch(
                    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label
                ) for label in host.rstrip(".").split("."))):
            raise ValueError(f"Invalid plain host: {host!r}.") from None
    else:
        if "%" in host:
            raise ValueError("Scoped IP addresses are not supported.")
    return host


def _units(unit_ids: list[int]) -> list[int]:
    if not isinstance(unit_ids, list) or not unit_ids:
        raise ValueError("Supply a nonempty list of explicit unit IDs.")
    return list(dict.fromkeys(
        _integer("unit_id", unit, 1, 247) for unit in unit_ids
    ))


def parse_unit_ids(text: str) -> list[int]:
    """Parse comma/newline-separated IDs and inclusive ranges, e.g. 1-4,7."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Supply explicit unit IDs.")
    units = []
    for token in re.split(r"[,\n]", text):
        match = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", token)
        if match is None:
            raise ValueError(f"Invalid unit ID/range: {token!r}.")
        start = _integer("unit_id", int(match[1]), 1, 247)
        end = start if match[2] is None else _integer(
            "unit_id", int(match[2]), 1, 247
        )
        if end < start:
            raise ValueError("Unit ID ranges must be ascending.")
        units.extend(range(start, end + 1))
    return _units(units)


def parse_hosts(text: str) -> list[str]:
    """Parse explicit comma/newline hosts OR one IPv4 CIDR (<=256 hosts).

    CIDRs use ipaddress.hosts(): network/broadcast are excluded except /31 and
    /32. Host bits in a CIDR are accepted and mapped to its containing network.
    URLs, host:port syntax, mixed CIDR/host lists and empty entries are rejected.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Supply explicit hosts or one IPv4 CIDR.")
    tokens = re.split(r"[,\n]", text.strip())
    if "/" in text:
        if len(tokens) != 1:
            raise ValueError("Supply a single IPv4 CIDR, not mixed targets.")
        try:
            network = ipaddress.IPv4Network(tokens[0].strip(), strict=False)
        except ValueError as exc:
            raise ValueError("Invalid IPv4 CIDR.") from exc
        count = network.num_addresses if network.prefixlen >= 31 else (
            network.num_addresses - 2
        )
        if count > MAX_HOSTS:
            raise ValueError(f"CIDR must contain at most {MAX_HOSTS} hosts.")
        return [str(host) for host in network.hosts()]
    return _hosts(tokens)


def _hosts(hosts: list[str]) -> list[str]:
    if not isinstance(hosts, list) or not hosts:
        raise ValueError("Supply a nonempty list of explicit hosts.")
    validated = list(dict.fromkeys(_host(host) for host in hosts))
    if len(validated) > MAX_HOSTS:
        raise ValueError(f"Supply at most {MAX_HOSTS} unique hosts.")
    return validated


def _validate_scan(count: int, timeout: float) -> None:
    if count > MAX_CANDIDATES:
        raise ValueError(f"Supply at most {MAX_CANDIDATES} unique candidates.")
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or not 0 < timeout <= 60):
        raise ValueError("timeout must be finite and in (0, 60] seconds.")


def _discover(
    targets: list[DeviceTarget], timeout: float, cancel_event: Event | None,
    progress: ProgressCallback | None,
) -> DiscoveryResult:
    result = DiscoveryResult(total=len(targets))

    def cancelled() -> bool:
        if cancel_event is not None and cancel_event.is_set():
            result.cancelled = True
        return result.cancelled

    for target in targets:
        if cancelled():
            break
        result.attempted += 1
        session = ModbusSession(unit_id=target.unit_id, timeout=timeout)
        try:
            try:
                if target.transport == "tcp":
                    session.open_tcp(target.host, target.port)
                else:
                    session.open_rtu(
                        target.serial_port, baudrate=target.baudrate,
                        parity=target.parity, stopbits=target.stopbits,
                    )
            except ModbusError as exc:
                result.errors.append(DiscoveryError(target, "connect", str(exc)))
            else:
                for method in (
                    "read_coils", "read_discrete_inputs", "read_holding_registers",
                ):
                    if cancelled():
                        break
                    result.probes_attempted += 1
                    try:
                        values = getattr(session, method)(0, 1)
                        if (not isinstance(values, list) or len(values) != 1
                                or (method != "read_holding_registers"
                                    and type(values[0]) is not bool)
                                or (method == "read_holding_registers"
                                    and (type(values[0]) is not int
                                         or not 0 <= values[0] <= 65535))):
                            raise ModbusResponseError("Invalid read result.")
                    except ModbusError as exc:
                        result.errors.append(DiscoveryError(target, method, str(exc)))
                    else:
                        result.devices.append(target)
                        break
        finally:
            try:
                session.close()
            except ModbusError as exc:
                result.errors.append(DiscoveryError(target, "close", str(exc)))
        cancelled()
        if progress is not None:
            progress(result.attempted, result.total, target)
    cancelled()
    return result


def discover_tcp(
    hosts: list[str], unit_ids: list[int], port: int = 502,
    timeout: float = .3, cancel_event: Event | None = None,
    progress: ProgressCallback | None = None,
) -> DiscoveryResult:
    """Scan only the supplied hosts/units, validating all input before I/O."""
    hosts = _hosts(hosts)
    units = _units(unit_ids)
    port = _integer("TCP port", port, 1, 65535)
    _validate_scan(len(hosts) * len(units), timeout)
    targets = [
        DeviceTarget("tcp", unit, host=host, port=port)
        for host in hosts for unit in units
    ]
    return _discover(targets, timeout, cancel_event, progress)


def discover_rtu(
    port: str, unit_ids: list[int], baudrate: int = 9600, parity: str = "N",
    stopbits: int = 1, timeout: float = .3, cancel_event: Event | None = None,
    progress: ProgressCallback | None = None,
) -> DiscoveryResult:
    """Sequential RTU scan; concurrent calls never open serial simultaneously."""
    if not isinstance(port, str) or not port.strip():
        raise ValueError("Supply an explicit serial port.")
    units = _units(unit_ids)
    baudrate = _integer("baudrate", baudrate, 1, 4_000_000)
    if not isinstance(parity, str) or parity.upper() not in ("N", "E", "O"):
        raise ValueError("parity must be N, E, or O.")
    stopbits = _integer("stopbits", stopbits, 1, 2)
    _validate_scan(len(units), timeout)
    targets = [
        DeviceTarget(
            "rtu", unit, serial_port=port.strip(), baudrate=baudrate,
            parity=parity.upper(), stopbits=stopbits,
        ) for unit in units
    ]
    with _RTU_SCAN_LOCK:
        return _discover(targets, timeout, cancel_event, progress)
