import threading
import unittest
from unittest.mock import Mock, patch

from m31tool.core import ModbusConnectionError, ModbusResponseError, ModbusSession
from m31tool.discovery import (
    DeviceTarget,
    discover_rtu,
    discover_tcp,
    parse_hosts,
    parse_unit_ids,
)


class ParsingTests(unittest.TestCase):
    def test_explicit_hosts_and_exact_deduplication(self):
        self.assertEqual(
            parse_hosts(" 192.0.2.1,example.org\n192.0.2.1 "),
            ["192.0.2.1", "example.org"],
        )
        self.assertEqual(parse_hosts("EXAMPLE.org,example.org"),
                         ["EXAMPLE.org", "example.org"])

    def test_ipv4_cidr(self):
        self.assertEqual(parse_hosts("192.0.2.1/30"),
                         ["192.0.2.1", "192.0.2.2"])
        self.assertEqual(parse_hosts("192.0.2.0/31"),
                         ["192.0.2.0", "192.0.2.1"])
        self.assertEqual(parse_hosts("192.0.2.9/32"), ["192.0.2.9"])
        self.assertEqual(len(parse_hosts("192.0.2.0/24")), 254)

    def test_invalid_hosts(self):
        for text in (
            "", " ", "http://example.org", "example.org:502", "a,,b",
            "a,\nb", "999.1.1.1", "-example.org", "a..b",
            "192.0.2.0/24,example.org", "192.0.2.0/23", "0.0.0.0/0",
            "::/64", "[::1]", "fe80::1%eth0", "host/path",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_hosts(text)

    def test_unit_ids(self):
        self.assertEqual(parse_unit_ids("1-3, 2,7\n247"), [1, 2, 3, 7, 247])
        self.assertEqual(parse_unit_ids(" 1 - 247 "), list(range(1, 248)))

    def test_invalid_units(self):
        for text in ("", "0", "248", "3-1", "-1", "1,,2", "1.5", "1-999999"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_unit_ids(text)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.sessions = []
        self.factory_patch = patch("m31tool.discovery.ModbusSession")
        self.factory = self.factory_patch.start()
        self.addCleanup(self.factory_patch.stop)
        self.factory.side_effect = self.make_session

    def make_session(self, **kwargs):
        session = Mock(spec=ModbusSession)
        session.read_coils.return_value = [False]
        session.read_discrete_inputs.return_value = [True]
        session.read_holding_registers.return_value = [17]
        self.sessions.append(session)
        return session

    def test_tcp_targets_preserve_real_addressing_and_read_only(self):
        progress = Mock()
        result = discover_tcp(["192.0.2.1", "192.0.2.1", "gateway"], [3, 3, 9],
                              port=1502, timeout=.2, progress=progress)
        self.assertEqual(result.devices, [
            DeviceTarget("tcp", 3, host="192.0.2.1", port=1502),
            DeviceTarget("tcp", 9, host="192.0.2.1", port=1502),
            DeviceTarget("tcp", 3, host="gateway", port=1502),
            DeviceTarget("tcp", 9, host="gateway", port=1502),
        ])
        self.assertEqual((result.attempted, result.total, result.probes_attempted),
                         (4, 4, 4))
        self.assertFalse(result.cancelled)
        self.assertEqual(result.errors, [])
        self.assertEqual([call.kwargs["unit_id"] for call in
                          self.factory.call_args_list], [3, 9, 3, 9])
        for session in self.sessions:
            self.assertEqual([call[0] for call in session.method_calls],
                             ["open_tcp", "read_coils", "close"])
            session.read_coils.assert_called_once_with(0, 1)
        progress.assert_called_with(4, 4, result.devices[-1])

    def test_rtu_configuration_and_sequential_close(self):
        result = discover_rtu(" /dev/ttyUSB0 ", [7, 7, 2], baudrate=19200,
                              parity="e", stopbits=2)
        self.assertEqual(result.devices, [
            DeviceTarget("rtu", unit, serial_port="/dev/ttyUSB0",
                         baudrate=19200, parity="E", stopbits=2)
            for unit in (7, 2)
        ])
        for session in self.sessions:
            session.open_rtu.assert_called_once_with(
                "/dev/ttyUSB0", baudrate=19200, parity="E", stopbits=2)
            session.close.assert_called_once()

    def test_exception_is_diagnostic_then_next_table_can_confirm(self):
        session = self.make_session()
        session.read_coils.side_effect = ModbusResponseError(
            "read_coils: device returned Modbus exception 1.")
        self.factory.side_effect = None
        self.factory.return_value = session
        result = discover_tcp(["gateway"], [1])
        self.assertEqual(len(result.devices), 1)
        self.assertEqual(result.probes_attempted, 2)
        self.assertEqual(result.errors[0].target, result.devices[0])
        self.assertEqual(result.errors[0].operation, "read_coils")
        self.assertIn("exception 1", result.errors[0].message)
        session.read_discrete_inputs.assert_called_once_with(0, 1)
        session.read_holding_registers.assert_not_called()

    def test_bounded_three_probes_no_connection_only_success(self):
        session = self.make_session()
        for method in ("read_coils", "read_discrete_inputs",
                       "read_holding_registers"):
            getattr(session, method).side_effect = ModbusResponseError(
                "device returned Modbus exception 2.")
        self.factory.side_effect = None
        self.factory.return_value = session
        result = discover_tcp(["gateway"], [1])
        self.assertEqual(result.devices, [])
        self.assertEqual(len(result.errors), 3)
        self.assertEqual(result.probes_attempted, 3)
        session.close.assert_called_once()

    def test_malformed_results_never_discover_a_target(self):
        session = self.make_session()
        session.read_coils.return_value = None
        session.read_discrete_inputs.return_value = []
        session.read_holding_registers.return_value = [True]
        self.factory.side_effect = None
        self.factory.return_value = session
        result = discover_tcp(["gateway"], [1])
        self.assertEqual(result.devices, [])
        self.assertEqual(len(result.errors), 3)

    def test_holding_register_fallback(self):
        session = self.make_session()
        session.read_coils.side_effect = ModbusResponseError("unsupported")
        session.read_discrete_inputs.side_effect = ModbusResponseError("unsupported")
        self.factory.side_effect = None
        self.factory.return_value = session
        result = discover_tcp(["gateway"], [1])
        self.assertEqual(len(result.devices), 1)
        self.assertEqual(result.probes_attempted, 3)
        session.read_holding_registers.assert_called_once_with(0, 1)

    def test_connection_failure_continues_and_closes(self):
        first = self.make_session()
        second = self.make_session()
        first.open_tcp.side_effect = ModbusConnectionError("unreachable")
        self.factory.side_effect = [first, second]
        result = discover_tcp(["gateway"], [1, 2])
        self.assertEqual([target.unit_id for target in result.devices], [2])
        self.assertEqual(result.attempted, 2)
        self.assertEqual(result.probes_attempted, 1)
        self.assertEqual(result.errors[0].operation, "connect")
        first.read_coils.assert_not_called()
        first.close.assert_called_once()
        second.close.assert_called_once()

    def test_close_error_is_retained(self):
        session = self.make_session()
        session.close.side_effect = ModbusConnectionError("close failed")
        self.factory.side_effect = None
        self.factory.return_value = session
        result = discover_tcp(["gateway"], [1])
        self.assertEqual(len(result.devices), 1)
        self.assertEqual(result.errors[0].operation, "close")

    def test_validation_before_any_session_or_io(self):
        calls = [
            lambda: discover_tcp(["gateway", "http://bad"], [1]),
            lambda: discover_tcp(["gateway"], [1, 0]),
            lambda: discover_tcp(["gateway"], [True]),
            lambda: discover_tcp([], [1]),
            lambda: discover_tcp(["gateway"], []),
            lambda: discover_tcp(["gateway"], [1], port=0),
            lambda: discover_tcp(["gateway"], [1], port=True),
            lambda: discover_tcp(["gateway"], [1], port=65536),
            lambda: discover_tcp([f"h{i}" for i in range(257)], [1]),
            lambda: discover_tcp([f"h{i}" for i in range(5)], list(range(1, 248))),
            lambda: discover_rtu("", [1]),
            lambda: discover_rtu("COM1", [0]),
            lambda: discover_rtu("COM1", [1], baudrate=0),
            lambda: discover_rtu("COM1", [1], baudrate=True),
            lambda: discover_rtu("COM1", [1], parity="X"),
            lambda: discover_rtu("COM1", [1], stopbits=3),
        ]
        for timeout in (0, -1, float("nan"), float("inf"), True, 61, "0.3"):
            calls.append(lambda timeout=timeout:
                         discover_tcp(["gateway"], [1], timeout=timeout))
            calls.append(lambda timeout=timeout:
                         discover_rtu("COM1", [1], timeout=timeout))
        for call in calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()
        self.factory.assert_not_called()

    def test_candidate_limit_exact_boundary(self):
        result = discover_tcp([f"h{i}" for i in range(8)], list(range(1, 129)))
        self.assertEqual(result.total, 1024)
        self.assertEqual(len(result.devices), 1024)

    def test_precancelled_scan_has_no_io(self):
        cancel = threading.Event()
        cancel.set()
        for scan in (
            lambda: discover_tcp(["gateway"], [1], cancel_event=cancel),
            lambda: discover_rtu("COM1", [1], cancel_event=cancel),
        ):
            result = scan()
            self.assertTrue(result.cancelled)
            self.assertEqual((result.attempted, result.total), (0, 1))
            self.assertEqual(result.devices, [])
        self.factory.assert_not_called()

    def test_cancel_between_probes(self):
        cancel = threading.Event()
        session = self.make_session()

        def cancel_read(*args):
            cancel.set()
            raise ModbusResponseError("unsupported")

        session.read_coils.side_effect = cancel_read
        self.factory.side_effect = None
        self.factory.return_value = session
        result = discover_tcp(["gateway"], [1, 2], cancel_event=cancel)
        self.assertTrue(result.cancelled)
        self.assertEqual((result.attempted, result.probes_attempted), (1, 1))
        session.read_discrete_inputs.assert_not_called()
        session.close.assert_called_once()

    def test_cancel_between_candidates_preserves_partial_result(self):
        cancel = threading.Event()
        result = discover_tcp(
            ["gateway"], [1, 2], cancel_event=cancel,
            progress=lambda attempted, total, target: cancel.set(),
        )
        self.assertTrue(result.cancelled)
        self.assertEqual([target.unit_id for target in result.devices], [1])
        self.assertEqual(result.attempted, 1)
        self.assertEqual(result.total, 2)

    def test_progress_exception_does_not_leak_connection(self):
        def progress(*args):
            raise RuntimeError("callback failed")

        with self.assertRaisesRegex(RuntimeError, "callback failed"):
            discover_tcp(["gateway"], [1], progress=progress)
        self.sessions[0].close.assert_called_once()

    def test_concurrent_rtu_scans_are_serialized(self):
        opened = threading.Event()
        release = threading.Event()
        second_started = threading.Event()
        second_opened = threading.Event()
        results = []
        first = self.make_session()
        second = self.make_session()

        def first_open(*args, **kwargs):
            opened.set()
            if not release.wait(2):
                raise AssertionError("test release timed out")

        first.open_rtu.side_effect = first_open
        second.open_rtu.side_effect = lambda *args, **kwargs: second_opened.set()
        self.factory.side_effect = [first, second]

        def run_second():
            second_started.set()
            results.append(discover_rtu("COM1", [2]))

        a = threading.Thread(target=lambda: results.append(discover_rtu("COM1", [1])))
        b = threading.Thread(target=run_second)
        a.start()
        try:
            self.assertTrue(opened.wait(2))
            b.start()
            self.assertTrue(second_started.wait(2))
            self.assertFalse(second_opened.wait(.05))
        finally:
            release.set()
            a.join(2)
            if b.ident is not None:
                b.join(2)
        self.assertFalse(a.is_alive())
        self.assertFalse(b.is_alive())
        self.assertEqual(len(results), 2)
        self.assertTrue(second_opened.is_set())
        first.close.assert_called_once()
        second.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
