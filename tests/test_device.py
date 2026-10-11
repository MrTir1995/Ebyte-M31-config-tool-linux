import struct
import unittest
from unittest.mock import patch

from m31tool.core import ModbusConnectionError, ModbusResponseError, ModbusSession
from m31tool.device import (
    DEVICE_MANUAL_SOURCE,
    DEVICE_READ_SPECS,
    DEVICE_REGISTER_CATALOG,
    NegotiationError,
    NegotiationTimeoutError,
    negotiate_addresses,
    read_device_info,
)
from tests.modbus_simulator import running_simulator


class FakeSession:
    """Only FC03 is available, making accidental mutations fail immediately."""

    def __init__(self, words=None):
        self.words = words or {}
        self.requests = []

    def read_holding_registers(self, address, count):
        self.requests.append((address, count))
        return [self.words.get(offset, offset)
                for offset in range(address, address + count)]


class DeviceTests(unittest.TestCase):
    def test_bounded_ranges_only_cover_documented_registers(self):
        self.assertEqual(
            [(spec.address, spec.count) for spec in DEVICE_READ_SPECS],
            [(0x7530, 15), (0x7541, 68), (0x7586, 4)],
        )
        documented = [address for spec in DEVICE_REGISTER_CATALOG
                      for address in range(spec.address, spec.address + spec.count)]
        requested = [address for spec in DEVICE_READ_SPECS
                     for address in range(spec.address, spec.address + spec.count)]
        self.assertEqual(requested, documented)
        self.assertEqual(len(documented), len(set(documented)))
        self.assertTrue(all(1 <= spec.count <= 125 for spec in DEVICE_READ_SPECS))

    def test_snapshot_preserves_exact_raw_words_and_schema(self):
        session = FakeSession()
        result = read_device_info(session)
        self.assertTrue(result["read_only"])
        self.assertEqual(result["source"], DEVICE_MANUAL_SOURCE)
        self.assertEqual(len(result["fields"]), 17)
        for spec, field in zip(DEVICE_REGISTER_CATALOG, result["fields"]):
            with self.subTest(key=spec.key):
                self.assertEqual(set(field), {
                    "key", "label", "address", "count", "raw_words",
                    "raw_hex", "decoded", "decode_note",
                })
                self.assertEqual(field["key"], spec.key)
                self.assertEqual(field["address"], spec.address)
                self.assertEqual(field["count"], spec.count)
                self.assertEqual(field["raw_words"],
                                 list(range(spec.address, spec.address + spec.count)))
        self.assertEqual(session.requests, [
            (spec.address, spec.count) for spec in DEVICE_READ_SPECS
        ])

    def test_every_documented_enum_and_unknown_code(self):
        for spec in DEVICE_REGISTER_CATALOG:
            for code, label in (*spec.enumerations, (65535, None)):
                with self.subTest(key=spec.key, code=code):
                    result = read_device_info(FakeSession({spec.address: code}))
                    field = next(f for f in result["fields"] if f["key"] == spec.key)
                    self.assertEqual(field["decoded"], label)
                    self.assertEqual(field["raw_words"][0], code)

    def test_multiregister_fields_never_guess_byte_order(self):
        result = read_device_info(FakeSession({0x7537: 0xC0A8, 0x7538: 0x0307}))
        fields = {field["key"]: field for field in result["fields"]}
        self.assertEqual(fields["ip"]["raw_hex"], "0xC0A8 0x0307")
        for key in ("mac", "ip", "subnet", "gateway", "dns", "target",
                    "expansion_bitmap"):
            self.assertIsNone(fields[key]["decoded"])

    def test_transport_and_modbus_errors_propagate_without_retries(self):
        for error in (ModbusResponseError("Modbus exception 2"),
                      ModbusConnectionError("Connection lost")):
            session = FakeSession()

            def fail(address, count):
                session.requests.append((address, count))
                raise error

            session.read_holding_registers = fail
            with self.assertRaises(type(error)) as raised:
                read_device_info(session)
            self.assertIs(raised.exception, error)
            self.assertEqual(session.requests, [(0x7530, 15)])

    def test_invalid_response_is_explicit_error(self):
        for values in (None, [], [0] * 14, [0] * 16, [True] * 15,
                       [-1] * 15, [65536] * 15, ["0"] * 15):
            with self.subTest(values=values):
                session = FakeSession()
                session.read_holding_registers = lambda address, count: values
                with self.assertRaises(ModbusResponseError):
                    read_device_info(session)

    def test_failure_after_first_range_does_not_return_partial_success(self):
        session = FakeSession()
        original = session.read_holding_registers

        def fail_second(address, count):
            if address == 0x7541:
                raise ModbusResponseError("Modbus exception 2")
            return original(address, count)

        session.read_holding_registers = fail_second
        with self.assertRaisesRegex(ModbusResponseError, "exception 2"):
            read_device_info(session)

    def test_loopback_uses_fc03_and_never_writes(self):
        with running_simulator() as simulator:
            for spec in DEVICE_REGISTER_CATALOG:
                simulator.holding_registers.update(
                    (address, address)
                    for address in range(spec.address, spec.address + spec.count)
                )
            session = ModbusSession(unit_id=1, timeout=0.2)
            try:
                session.open_tcp(*simulator.address)
                snapshot = read_device_info(session)
                self.assertEqual(len(snapshot["fields"]), 17)
                self.assertEqual(
                    simulator.requests,
                    [(1, bytes([3]) + struct.pack(">HH", spec.address, spec.count))
                     for spec in DEVICE_READ_SPECS],
                )
            finally:
                session.close()


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class NegotiationSession:
    def __init__(self, statuses=(1,), exception=0, bitmap=(0x1234, 0xABCD)):
        self.statuses = iter(statuses)
        self.last_status = 0
        self.result = [exception, *bitmap]
        self.calls = []
        self.fail_at = None

    def write_register(self, address, value):
        self.calls.append(("write", address, value))
        if len(self.calls) == self.fail_at:
            raise ModbusConnectionError("lost acknowledgment")

    def read_holding_registers(self, address, count):
        self.calls.append(("read", address, count))
        if len(self.calls) == self.fail_at:
            raise ModbusResponseError("Modbus exception 2")
        if address == 0x7586:
            self.last_status = next(self.statuses, self.last_status)
            return [self.last_status]
        return self.result


class NegotiationTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.time_patch = patch("m31tool.device.time.monotonic", self.clock.monotonic)
        self.sleep_patch = patch("m31tool.device.time.sleep", self.clock.sleep)
        self.time_patch.start()
        self.sleep_patch.start()
        self.addCleanup(self.time_patch.stop)
        self.addCleanup(self.sleep_patch.stop)

    def test_success_exact_sequential_writes_and_bounded_polling(self):
        session = NegotiationSession((0, 0, 1))
        self.assertEqual(session.calls, [])
        result = negotiate_addresses(session, timeout=1, poll_interval=0.25)
        self.assertEqual(session.calls, [
            ("write", 0x7584, 1), ("write", 0x7585, 1),
            ("read", 0x7586, 1), ("read", 0x7586, 1), ("read", 0x7586, 1),
            ("read", 0x7587, 3),
        ])
        self.assertEqual(self.clock.sleeps, [0.25, 0.25])
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], 1)
        self.assertEqual(result["exception_label"], "OK")
        self.assertEqual(result["bitmap_raw_words"], [0x1234, 0xABCD])
        self.assertEqual(result["bitmap_raw_hex"], "0x1234 0xABCD")
        self.assertFalse(result["read_only"])

    def test_validate_all_arguments_before_any_write(self):
        for key in ("timeout", "poll_interval"):
            for value in (0, -1, True, "1", None, float("inf"), float("nan")):
                with self.subTest(key=key, value=value):
                    session = NegotiationSession()
                    with self.assertRaises(ValueError):
                        negotiate_addresses(session, **{key: value})
                    self.assertEqual(session.calls, [])

    def test_incomplete_timeout_caps_sleep_and_does_not_retry_writes(self):
        session = NegotiationSession((0,))
        with self.assertRaisesRegex(NegotiationTimeoutError, "may have changed"):
            negotiate_addresses(session, timeout=0.6, poll_interval=0.25)
        self.assertAlmostEqual(self.clock.now, 0.6)
        self.assertEqual(len(self.clock.sleeps), 3)
        self.assertAlmostEqual(self.clock.sleeps[-1], 0.1)
        self.assertEqual(session.calls[:2], [
            ("write", 0x7584, 1), ("write", 0x7585, 1),
        ])
        self.assertEqual(len(session.calls), 5)

    def test_write_and_read_failures_explicit_state_warning_no_rollback(self):
        for fail_at in (1, 2, 3, 4):
            with self.subTest(fail_at=fail_at):
                session = NegotiationSession()
                session.fail_at = fail_at
                with self.assertRaisesRegex(NegotiationError, "may have changed") as exc:
                    negotiate_addresses(session)
                self.assertIsInstance(exc.exception.__cause__, (
                    ModbusConnectionError, ModbusResponseError,
                ))
                self.assertEqual(len(session.calls), fail_at)

    def test_unknown_status_is_raw_explicit_error(self):
        session = NegotiationSession((65535,))
        with self.assertRaisesRegex(NegotiationError, "65535.*0xFFFF"):
            negotiate_addresses(session)
        self.assertEqual(len(session.calls), 3)

    def test_known_and_unknown_exception_codes_are_not_false_success(self):
        for code, label in ((0, "OK"), (1, "Slave did not reply"),
                            (2, "Wrong sequence"), (65535, None)):
            with self.subTest(code=code):
                result = negotiate_addresses(NegotiationSession(exception=code))
                self.assertEqual(result["exception"], code)
                self.assertEqual(result["exception_label"], label)
                self.assertEqual(result["success"], code == 0)

    def test_invalid_bitmap_surfaces_with_state_warning(self):
        for bitmap in ((), (1,), (1, 2, 3), (-1, 0), (0, 65536), (True, 0)):
            with self.subTest(bitmap=bitmap):
                with self.assertRaisesRegex(NegotiationError, "may have changed"):
                    negotiate_addresses(NegotiationSession(bitmap=bitmap))

    def test_slow_exchange_cannot_return_success_after_deadline(self):
        session = NegotiationSession()
        original = session.read_holding_registers

        def delayed_read(address, count):
            result = original(address, count)
            self.clock.now += 2
            return result

        session.read_holding_registers = delayed_read
        with self.assertRaises(NegotiationTimeoutError):
            negotiate_addresses(session, timeout=1)
        self.assertEqual(len(session.calls), 3)

    def test_slow_unlock_prevents_trigger_after_deadline(self):
        session = NegotiationSession()
        original = session.write_register

        def delayed_write(address, value):
            original(address, value)
            self.clock.now += 2

        session.write_register = delayed_write
        with self.assertRaises(NegotiationTimeoutError):
            negotiate_addresses(session, timeout=1)
        self.assertEqual(session.calls, [("write", 0x7584, 1)])


if __name__ == "__main__":
    unittest.main()
