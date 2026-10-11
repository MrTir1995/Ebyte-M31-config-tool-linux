"""M31 device parameters and explicit negotiation from manual section 4.8.

All addresses are zero-based holding-register PDU addresses. This module does
not automatically discover, negotiate, save, restart, or change configuration.
Byte order within multi-register addresses and target strings is not confirmed:
these fields deliberately retain only their raw words, not guessed text/IPs.
"""

from dataclasses import dataclass
import math
import time

from .core import ModbusError, ModbusResponseError, ModbusSession


DEVICE_MANUAL_SOURCE = "https://www.cdebyte.com/pdf-down.aspx?id=3402 §4.8"
NEGOTIATION_MANUAL_SOURCE = (
    "https://www.cdebyte.com/pdf-down.aspx?id=3402 §4.8 pp.51–53"
)


class NegotiationError(ModbusError):
    """Negotiation failed; a write may already have changed device state."""


class NegotiationTimeoutError(NegotiationError):
    """The client-selected negotiation deadline expired."""


@dataclass(frozen=True)
class DeviceRegisterSpec:
    """One documented parameter; enumerations map raw codes to display text."""

    key: str
    label: str
    address: int
    count: int = 1
    enumerations: tuple[tuple[int, str], ...] = ()
    decode_note: str = "Raw holding-register words; no interpretation assumed."


@dataclass(frozen=True)
class ReadSpec:
    """One contiguous FC03 range containing documented addresses only."""

    address: int
    count: int


_RAW_BYTES = "Raw words only: application byte/word ordering is not confirmed."
_ENUM = "Decoded manufacturer enumeration; unknown codes remain raw."

DEVICE_REGISTER_CATALOG = (
    DeviceRegisterSpec(
        "baudrate", "Serial baud rate", 0x7530,
        enumerations=tuple(enumerate(
            ("2400 baud", "4800 baud", "9600 baud", "19200 baud",
             "38400 baud", "57600 baud", "115200 baud", "230400 baud"), 1,
        )), decode_note=_ENUM,
    ),
    DeviceRegisterSpec(
        "parity", "Serial parity", 0x7531,
        enumerations=((0, "None"), (1, "Odd"), (2, "Even")),
        decode_note=_ENUM,
    ),
    DeviceRegisterSpec(
        "network_mode", "Network mode", 0x7532,
        enumerations=((0, "TCP server"), (1, "TCP client"),
                      (2, "UDP server"), (3, "UDP client")),
        decode_note=_ENUM,
    ),
    DeviceRegisterSpec("dhcp", "DHCP", 0x7533),
    DeviceRegisterSpec("mac", "MAC address", 0x7534, 3,
                       decode_note=_RAW_BYTES),
    DeviceRegisterSpec("ip", "IP address", 0x7537, 2,
                       decode_note=_RAW_BYTES),
    DeviceRegisterSpec("subnet", "Subnet mask", 0x7539, 2,
                       decode_note=_RAW_BYTES),
    DeviceRegisterSpec("gateway", "Gateway", 0x753B, 2,
                       decode_note=_RAW_BYTES),
    DeviceRegisterSpec("dns", "DNS server", 0x753D, 2,
                       decode_note=_RAW_BYTES),
    DeviceRegisterSpec("local_port", "Local port", 0x7541),
    DeviceRegisterSpec("target", "Target address/string", 0x7542, 64,
                       decode_note=_RAW_BYTES),
    DeviceRegisterSpec("target_port", "Target port", 0x7582),
    DeviceRegisterSpec(
        "protocol", "Network protocol", 0x7583,
        enumerations=((0, "RTU over network"), (1, "TCP")),
        decode_note=_ENUM,
    ),
    DeviceRegisterSpec("negotiation_lock", "Negotiation lock", 0x7584),
    DeviceRegisterSpec(
        "negotiation_status", "Negotiation status", 0x7586,
        enumerations=((0, "Incomplete"), (1, "Complete")),
        decode_note=_ENUM,
    ),
    DeviceRegisterSpec(
        "exception_status", "Exception status", 0x7587,
        enumerations=((0, "OK"), (1, "Slave did not reply"),
                      (2, "Wrong sequence")),
        decode_note=_ENUM,
    ),
    DeviceRegisterSpec("expansion_bitmap", "Expansion bitmap", 0x7588, 2),
)


def _read_specs() -> tuple[ReadSpec, ...]:
    spans: list[ReadSpec] = []
    for field in DEVICE_REGISTER_CATALOG:
        if (spans and spans[-1].address + spans[-1].count == field.address
                and spans[-1].count + field.count <= 125):
            previous = spans[-1]
            spans[-1] = ReadSpec(previous.address, previous.count + field.count)
        else:
            spans.append(ReadSpec(field.address, field.count))
    return tuple(spans)


DEVICE_READ_SPECS = _read_specs()


def read_device_info(session: ModbusSession) -> dict:
    """Explicitly read a complete parameter snapshot using FC03 only.

    Returns ``source``, ``read_only``, and ``fields`` (in catalog order). Each
    field contains key, label, address, count, raw_words, raw_hex, decoded
    (display text or None), and decode_note. Raw words are never transformed.
    Communication/Modbus exceptions propagate; failed reads do not produce a
    misleading partial snapshot. Multiple requests are not an atomic snapshot.
    """
    words: dict[int, int] = {}
    for span in DEVICE_READ_SPECS:
        values = session.read_holding_registers(span.address, span.count)
        if (not isinstance(values, (list, tuple)) or len(values) != span.count
                or any(type(value) is not int or not 0 <= value <= 65535
                       for value in values)):
            raise ModbusResponseError(
                f"Device parameters at 0x{span.address:04X}: "
                "invalid or truncated register response."
            )
        words.update((span.address + index, value)
                     for index, value in enumerate(values))

    fields = []
    for spec in DEVICE_REGISTER_CATALOG:
        raw = [words[address]
               for address in range(spec.address, spec.address + spec.count)]
        fields.append({
            "key": spec.key,
            "label": spec.label,
            "address": spec.address,
            "count": spec.count,
            "raw_words": raw,
            "raw_hex": " ".join(f"0x{value:04X}" for value in raw),
            "decoded": dict(spec.enumerations).get(raw[0]),
            "decode_note": spec.decode_note,
        })
    return {
        "source": DEVICE_MANUAL_SOURCE,
        "read_only": True,
        "fields": fields,
    }


def negotiate_addresses(
    session: ModbusSession, *, timeout: float = 30.0,
    poll_interval: float = 0.25,
) -> dict:
    """Explicitly unlock and trigger address negotiation (manual pp.51–53).

    Call only after operator authorization: negotiation can change expansion
    addresses/topology. Writes are sequential, issued once, and never rolled
    back. Any failure after a write attempt reports possible state changes.
    Timeout and poll interval are finite positive client-selected seconds,
    not manufacturer timing guarantees. The monotonic deadline bounds polling;
    an in-flight synchronous exchange remains subject to the session timeout.

    A completed result preserves status, exception, and bitmap_raw_words/hex.
    ``success`` is true only for exception 0. Unknown status is an error;
    unknown exception returns its raw code and a None exception_label. Bitmap
    word order and bit/channel assignment are deliberately not interpreted.
    """
    for name, value in (("timeout", timeout), ("poll_interval", poll_interval)):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ValueError(f"{name} must be a finite positive number.")

    deadline = time.monotonic() + timeout
    state_warning = (
        "Device state/addresses may have changed; no automatic retry or rollback."
    )

    def check_deadline() -> None:
        if time.monotonic() >= deadline:
            raise NegotiationTimeoutError(
                f"Negotiation exceeded client timeout {timeout:g}s. {state_warning}"
            )

    def read_words(address: int, count: int) -> list[int]:
        check_deadline()
        values = session.read_holding_registers(address, count)
        if (not isinstance(values, (list, tuple)) or len(values) != count
                or any(type(value) is not int or not 0 <= value <= 65535
                       for value in values)):
            raise ModbusResponseError(
                f"Negotiation at 0x{address:04X}: invalid/truncated words {values!r}."
            )
        check_deadline()
        return list(values)

    try:
        session.write_register(0x7584, 1)
        check_deadline()
        session.write_register(0x7585, 1)
        while True:
            status = read_words(0x7586, 1)[0]
            if status == 1:
                break
            if status != 0:
                raise ModbusResponseError(
                    f"Unknown negotiation status {status} (0x{status:04X})."
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                check_deadline()
            time.sleep(min(poll_interval, remaining))
        exception, *bitmap = read_words(0x7587, 3)
    except NegotiationError:
        raise
    except ModbusError as exc:
        raise NegotiationError(f"Negotiation failed: {exc} {state_warning}") from exc

    labels = dict(next(
        spec.enumerations for spec in DEVICE_REGISTER_CATALOG
        if spec.key == "exception_status"
    ))
    return {
        "source": NEGOTIATION_MANUAL_SOURCE,
        "read_only": False,
        "status": status,
        "status_label": "Complete",
        "exception": exception,
        "exception_label": labels.get(exception),
        "success": exception == 0,
        "bitmap_raw_words": bitmap,
        "bitmap_raw_hex": " ".join(f"0x{value:04X}" for value in bitmap),
    }
