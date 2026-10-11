"""Device-list callbacks use mocks and one explicit loopback discovery, never hardware."""

import os
import threading
import time
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import weakref

from m31tool.app import M31App, tk
from m31tool.discovery import DeviceTarget, DiscoveryError, DiscoveryResult
from tests.modbus_simulator import running_simulator


class Variable:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DeviceListCallbacks(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(
            connected=False, busy=False, closing=False, root=None, scan_cancel=None,
            device_targets={}, device_tree=Mock(), destination="old destination",
            transport=Variable("TCP"), unit_id=Variable("1"),
            host=Variable(""), tcp_port=Variable("502"),
            serial_port=Variable("/dev/ttyUSB1"), baudrate=Variable("19200"),
            parity=Variable("E"), stopbits=Variable("2"),
            timeout=Variable("2"), scan_hosts=Variable(""),
            scan_units=Variable("1-247"), scan_timeout=Variable("0.3"),
            scan_status=Variable(), status=Variable(), _run=Mock(), _error=Mock(),
            _show_transport=Mock(), _refresh_controls=Mock(),
            _discovery_complete=Mock(), session=Mock(),
        )
        self.app.device_tree.insert.side_effect = ["first", "second", "third"]
        self.app._remember_device_target = MethodType(M31App._remember_device_target, self.app)
        self.dialogs = patch("m31tool.app.messagebox", Mock()).start()
        self.addCleanup(patch.stopall)

    def test_select_distinct_units_same_tcp_endpoint_only_prepares_fields(self):
        for unit in (3, 17):
            target = DeviceTarget("tcp", unit, host="192.0.2.9", port=1502)
            self.app._remember_device_target(target, verified=True)
        for item, unit in (("first", 3), ("second", 17)):
            self.app.device_tree.selection.return_value = (item,)
            M31App._select_device_target(self.app)
            self.assertEqual(self.app.unit_id.get(), str(unit))
            self.assertEqual(self.app.host.get(), "192.0.2.9")
            self.assertEqual(self.app.tcp_port.get(), "1502")
            self.assertEqual(self.app.destination, "")
        self.app._run.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])

    def test_select_rtu_restores_all_serial_destination_fields(self):
        target = DeviceTarget(
            "rtu", 23, serial_port="/dev/ttyUSB7", baudrate=38400, parity="O", stopbits=2,
        )
        self.app._remember_device_target(target, verified=True)
        self.app.device_tree.selection.return_value = ("first",)
        M31App._select_device_target(self.app)
        self.assertEqual(
            tuple(getattr(self.app, name).get() for name in (
                "transport", "serial_port", "baudrate", "parity", "stopbits", "unit_id",
            )), ("RTU", "/dev/ttyUSB7", "38400", "O", "2", "23"),
        )

    def test_connected_busy_closing_guard_search_add_and_selection(self):
        target = DeviceTarget("tcp", 17, host="192.0.2.9", port=502)
        self.app.device_targets["first"] = target
        self.app.device_tree.selection.return_value = ("first",)
        for attribute in ("connected", "busy", "closing"):
            setattr(self.app, attribute, True)
            M31App._search_devices(self.app)
            M31App._add_current_target(self.app)
            M31App._select_device_target(self.app)
            setattr(self.app, attribute, False)
        self.assertEqual(self.app.unit_id.get(), "1")
        self.assertEqual(self.app.destination, "old destination")
        self.app._run.assert_not_called()
        self.app.device_tree.insert.assert_not_called()

    def test_search_requires_explicit_hosts_and_never_uses_current_host_implicitly(self):
        self.app.host.set("192.0.2.9")
        M31App._search_devices(self.app)
        self.app._error.assert_called_once()
        self.app._run.assert_not_called()
        self.assertIsNone(self.app.scan_cancel)

    def test_search_rejects_oversized_product_broadcast_and_bad_timeout(self):
        for hosts, units, timeout in (
            ("192.0.2.0/24", "1-247", "0.3"),
            ("192.0.2.1", "0", "0.3"),
            ("192.0.2.1", "1", "nan"),
            ("192.0.2.1", "1", "3"),
        ):
            self.app.scan_hosts.set(hosts)
            self.app.scan_units.set(units)
            self.app.scan_timeout.set(timeout)
            M31App._search_devices(self.app)
        self.assertEqual(self.app._error.call_count, 4)
        self.app._run.assert_not_called()

    @patch("m31tool.app.discover_tcp")
    def test_search_snapshots_inputs_in_worker_and_cancel_uses_event(self, discover):
        self.app.scan_hosts.set("192.0.2.9,192.0.2.10")
        self.app.scan_units.set("3,17")
        self.app.tcp_port.set("1502")
        M31App._search_devices(self.app)
        discover.assert_not_called()
        self.assertFalse(self.app.scan_cancel.is_set())
        self.app.scan_units.set("99")
        self.app.scan_hosts.set("changed")
        M31App._cancel_search(self.app)
        self.assertTrue(self.app.scan_cancel.is_set())
        self.app._run.call_args.args[1]()
        discover.assert_called_once_with(
            ["192.0.2.9", "192.0.2.10"], [3, 17], port=1502, timeout=0.3,
            cancel_event=self.app.scan_cancel,
        )

    @patch("m31tool.app.discover_rtu")
    def test_rtu_search_uses_client_serial_settings_not_tcp_fields(self, discover):
        self.app.transport.set("RTU")
        self.app.scan_units.set("7-9")
        M31App._search_devices(self.app)
        self.app._run.call_args.args[1]()
        discover.assert_called_once_with(
            "/dev/ttyUSB1", [7, 8, 9], baudrate=19200, parity="E", stopbits=2,
            timeout=0.3, cancel_event=self.app.scan_cancel,
        )

    def test_manual_target_unverified_and_success_upgrades_without_duplicate(self):
        self.app.host.set("192.0.2.9")
        self.app.unit_id.set("17")
        M31App._add_current_target(self.app)
        self.assertEqual(
            self.app.device_tree.insert.call_args.kwargs["values"][-1],
            "Unverified (manual)",
        )
        target = next(iter(self.app.device_targets.values()))
        self.assertEqual(target.transport, "tcp")
        self.app._remember_device_target(target, verified=True)
        self.app.device_tree.insert.assert_called_once()
        self.app.device_tree.set.assert_called_once_with(
            "first", "verification", "Found (read response)",
        )
        self.app._run.assert_not_called()

    def test_manual_rtu_target_matches_canonical_discovery_schema(self):
        self.app.transport.set("RTU")
        self.app.unit_id.set("23")
        M31App._add_current_target(self.app)
        target = DeviceTarget(
            "rtu", 23, serial_port="/dev/ttyUSB1", baudrate=19200, parity="E", stopbits=2,
        )
        self.assertEqual(self.app.device_targets["first"], target)
        self.app._remember_device_target(target, verified=True)
        self.app.device_tree.insert.assert_called_once()
        self.app.device_tree.set.assert_called_once_with(
            "first", "verification", "Found (read response)",
        )

    def test_cancelled_result_keeps_prior_and_partial_devices_and_reports_errors(self):
        old = DeviceTarget("tcp", 3, host="192.0.2.9", port=502)
        new = DeviceTarget("tcp", 17, host="192.0.2.9", port=502)
        self.app._remember_device_target(old)
        result = DiscoveryResult(
            devices=[new], errors=[DiscoveryError(new, "read", "timeout")],
            attempted=2, total=247, cancelled=True,
        )
        M31App._discovery_complete(self.app, result)
        self.assertEqual(list(self.app.device_targets.values()), [old, new])
        self.assertIn("Cancelled (partial results kept)", self.app.scan_status.get())
        self.assertIn("1 errors", self.app.scan_status.get())
        self.assertIn("unit 17", self.dialogs.showwarning.call_args.args[1])
        self.assertIsNone(self.app.scan_cancel)

    def test_worker_failure_keeps_existing_list_and_clears_cancel_state(self):
        self.app.device_targets["first"] = DeviceTarget("tcp", 3, host="192.0.2.9", port=502)
        self.app.scan_cancel = Mock()
        M31App._error(self.app, "Search devices", RuntimeError("backend failed"))
        self.assertEqual(len(self.app.device_targets), 1)
        self.assertIsNone(self.app.scan_cancel)
        self.assertIn("existing targets kept", self.app.scan_status.get())
        self.dialogs.showerror.assert_called_once()


@unittest.skipUnless(tk is not None and os.environ.get("DISPLAY"), "Native Tk display required.")
class NativeDeviceListTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.sessions = patch("m31tool.app.ModbusSession").start()
        def session_factory(**kwargs):
            session = Mock(connected=False, unit_id=kwargs["unit_id"])
            session.open_tcp.side_effect = lambda *args, **kw: setattr(session, "connected", True)
            session.close.side_effect = lambda: setattr(session, "connected", False)
            return session
        self.sessions.side_effect = session_factory
        self.dialogs = patch("m31tool.app.messagebox", Mock()).start()
        self.addCleanup(patch.stopall)
        self.app = M31App(self.root)
        self.root.update()
        self.addCleanup(self.close)

    def close(self):
        self.app._request_close()
        self.wait_for(lambda: not self.exists())

    def exists(self):
        try:
            return bool(self.root.winfo_exists())
        except tk.TclError:
            return False

    def wait_for(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if predicate():
                return
            try:
                self.root.update()
            except tk.TclError:
                if predicate():
                    return
                raise
            time.sleep(0.01)
        self.fail(self.app.status.get())

    def test_initialization_has_seventh_tab_and_no_search_or_device_io(self):
        self.assertEqual(len(self.app.notebook.tabs()), 7)
        self.assertEqual(self.app.scan_hosts.get(), "")
        self.assertEqual(self.app.scan_units.get(), "1-247")
        self.assertEqual(self.app.device_targets, {})
        self.assertIsNone(self.app.scan_cancel)
        self.assertTrue(self.app.events.empty())
        self.assertFalse(self.app.busy)
        self.assertEqual(str(self.app.cancel_search_button["state"]), "disabled")
        self.assertEqual(self.app.session.mock_calls, [])

    def test_selected_unit_connects_and_confirms_exact_destination_for_each_write(self):
        for unit in (3, 17):
            target = DeviceTarget("tcp", unit, host="192.0.2.9", port=1502)
            self.app._remember_device_target(target, verified=True)
        for item, unit in self.app.device_targets.items():
            self.app.device_tree.selection_set(item)
            self.root.update()
            self.app._connect()
            self.wait_for(lambda: not self.app.busy)
            session = self.app.session
            self.assertTrue(self.app.connected)
            self.assertEqual(session.unit_id, unit.unit_id)
            session.open_tcp.assert_called_once_with("192.0.2.9", port=1502)
            self.app._refresh_controls()
            self.assertEqual(str(self.app.search_button["state"]), "disabled")
            self.app.write_value.set("42")
            session.read_holding_registers.return_value = [42]
            self.dialogs.askyesno.return_value = True
            self.app._write()
            self.wait_for(lambda: not self.app.busy)
            self.assertIn(
                f"TCP 192.0.2.9:1502, unit {unit.unit_id}",
                self.dialogs.askyesno.call_args.args[1],
            )
            session.write_register.assert_called_once_with(0, 42)
            session.read_holding_registers.assert_called_once_with(0, 1)
            self.app._disconnect()
            self.wait_for(lambda: not self.app.busy)
            self.assertFalse(self.app.connected)

    def test_poll_reports_discovery_exception_without_losing_devices(self):
        self.app._remember_device_target(DeviceTarget("tcp", 3, host="192.0.2.9", port=502))
        with patch("m31tool.app.discover_tcp", side_effect=RuntimeError("test failure")):
            self.app.scan_hosts.set("192.0.2.9")
            self.app.scan_units.set("3")
            self.app._search_devices()
            self.wait_for(lambda: not self.app.busy)
        self.assertEqual(len(self.app.device_targets), 1)
        self.assertIsNone(self.app.scan_cancel)
        self.assertIn("FAILED", self.app.scan_status.get())
        self.assertEqual(str(self.app.cancel_search_button["state"]), "disabled")
        self.dialogs.showerror.assert_called_once()

    def test_active_session_cannot_change_selected_target_even_programmatically(self):
        for unit in (3, 17):
            self.app._remember_device_target(
                DeviceTarget("tcp", unit, host="192.0.2.9", port=502),
            )
        first, second = self.app.device_targets
        self.app.device_tree.selection_set(first)
        self.root.update()
        self.app._connect()
        self.wait_for(lambda: not self.app.busy)
        self.assertTrue(self.app.connected)
        self.app.device_tree.selection_set(second)
        self.root.update()
        self.assertEqual(self.app.device_tree.selection(), (first,))
        self.assertEqual(self.app.unit_id.get(), "3")
        self.assertIn("unit 3", self.app.destination)
        self.assertEqual(self.app.session.unit_id, 3)

    def test_close_releases_owned_tk_variables_on_main_thread_before_later_workers(self):
        references = [
            weakref.ref(value) for value in vars(self.app).values()
            if isinstance(value, tk.Variable)
        ]
        finalized_threads = []
        original_finalize = tk.Variable.__del__

        def finalize(variable):
            finalized_threads.append(threading.get_ident())
            original_finalize(variable)

        with patch.object(tk.Variable, "__del__", finalize):
            self.close()
        self.assertTrue(references)
        self.assertTrue(all(reference() is None for reference in references))
        self.assertEqual(len(finalized_threads), len(references))
        self.assertEqual(set(finalized_threads), {threading.get_ident()})
        self.assertIsNone(self.app.worker_thread)
        self.assertEqual(self.app.controls, [])

    def test_real_loopback_discovery_deduplicates_manual_target_and_prepares_tcp(self):
        with running_simulator() as simulator:
            host, port = simulator.address
            self.app.host.set(host)
            self.app.tcp_port.set(str(port))
            self.app.unit_id.set("1")
            self.app._add_current_target()
            item = next(iter(self.app.device_targets))
            self.assertEqual(self.app.device_targets[item].transport, "tcp")
            self.assertEqual(
                self.app.device_tree.set(item, "verification"), "Unverified (manual)",
            )
            self.app.scan_hosts.set(host)
            self.app.scan_units.set("1")
            self.app._search_devices()
            self.wait_for(lambda: not self.app.busy)
            self.assertEqual(len(self.app.device_targets), 1)
            self.assertEqual(
                self.app.device_tree.set(item, "verification"), "Found (read response)",
            )
            self.assertEqual(
                self.app.device_tree.set(item, "endpoint"), f"TCP {host}:{port}",
            )
            self.app.transport.set("RTU")
            self.app.host.set("other")
            self.app.tcp_port.set("502")
            self.app.unit_id.set("17")
            self.app.device_tree.selection_set(item)
            self.root.update()
            self.assertEqual(self.app.transport.get(), "TCP")
            self.assertEqual(self.app.host.get(), host)
            self.assertEqual(self.app.tcp_port.get(), str(port))
            self.assertEqual(self.app.unit_id.get(), "1")
            self.assertEqual(self.app.serial_port.get(), "/dev/ttyUSB0")
            self.assertEqual(self.app.parity.get(), "N")
            self.assertFalse(self.app.connected)
            self.assertEqual(self.app.session.mock_calls, [])
            self.assertTrue(simulator.requests)
            self.assertTrue(all(unit == 1 and pdu[0] in (1, 3, 4)
                                for unit, pdu in simulator.requests))
