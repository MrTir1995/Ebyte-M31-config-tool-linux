from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from m31tool.app import M31App


def variable(value):
    return Mock(get=Mock(return_value=value))


class GUISafetyTests(unittest.TestCase):
    """Exercise GUI callbacks without a Tk root, display, or worker thread."""

    def setUp(self):
        self.app = SimpleNamespace(
            connected=True, busy=False, closing=False, root=None,
            destination="TCP 127.0.0.1:502, unit 1",
            write_type=variable("Holding registers"), write_address=variable("0"),
            write_value=variable("42"), session=Mock(), _run=Mock(),
            write_encoding=variable("Raw unsigned values"), write_word_order=variable(""),
            _error=Mock(), _display=Mock(), status=Mock(),
            object_type=variable("Holding registers"), address=variable("0"),
            count=variable("1"),
        )
        self.dialog_patch = patch("m31tool.app.messagebox", Mock())
        self.dialog = self.dialog_patch.start()
        self.addCleanup(self.dialog_patch.stop)
        self.dialog.askyesno.return_value = True

    def operation(self):
        return self.app._run.call_args.args[1]

    def test_cancelled_confirmation_does_not_write(self):
        self.dialog.askyesno.return_value = False
        M31App._write(self.app)
        self.app._run.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])
        self.assertEqual(self.dialog.askyesno.call_args.kwargs["default"], "no")

    def test_confirmed_register_write_has_ordered_readback(self):
        self.app.session.read_holding_registers.return_value = [42]
        M31App._write(self.app)
        self.assertEqual(self.operation()(), [("Holding registers", 0, 42)])
        self.assertEqual(
            self.app.session.mock_calls,
            [call.write_register(0, 42), call.read_holding_registers(0, 1)],
        )
        self.assertIn(
            self.app.destination, self.dialog.askyesno.call_args.args[1]
        )

    def test_confirmed_coil_write_has_ordered_readback(self):
        self.app.write_type = variable("Coils")
        self.app.write_value = variable("1")
        self.app.session.read_coils.return_value = [True]
        M31App._write(self.app)
        self.assertEqual(self.operation()(), [("Coils", 0, 1)])
        self.assertEqual(
            self.app.session.mock_calls,
            [call.write_coil(0, True), call.read_coils(0, 1)],
        )

    def test_readback_mismatch_or_error_never_looks_successful(self):
        for response in ([17], []):
            with self.subTest(response=response):
                self.app.session.read_holding_registers.return_value = response
                M31App._write(self.app)
                with self.assertRaisesRegex(RuntimeError, "could have taken effect"):
                    self.operation()()
        self.app.session.read_holding_registers.side_effect = ConnectionError("lost")
        M31App._write(self.app)
        with self.assertRaisesRegex(RuntimeError, "No rollback"):
            self.operation()()
        self.app._display.assert_not_called()

    def test_inactive_busy_or_closing_gui_never_starts_write(self):
        for attribute, value in (
            ("connected", False), ("busy", True), ("closing", True)
        ):
            with self.subTest(attribute=attribute):
                previous = getattr(self.app, attribute)
                setattr(self.app, attribute, value)
                M31App._write(self.app)
                setattr(self.app, attribute, previous)
        self.app._run.assert_not_called()
        self.dialog.askyesno.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])

    def test_readonly_tables_cannot_be_written(self):
        for kind in ("Discrete inputs", "Input registers"):
            with self.subTest(kind=kind):
                self.app.write_type = variable(kind)
                M31App._write(self.app)
        self.app._run.assert_not_called()
        self.dialog.askyesno.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])

    def test_invalid_read_span_is_rejected_before_worker(self):
        for address, count in (("65535", "2"), ("0", "126"), ("-1", "1")):
            with self.subTest(address=address, count=count):
                self.app.address, self.app.count = variable(address), variable(count)
                M31App._read(self.app)
        self.assertEqual(self.app._error.call_count, 3)
        self.app._run.assert_not_called()

    def refresh_fixture(self):
        self.app.auto_refresh = variable(True)
        self.app.refresh_interval = variable("0.5")
        self.app.auto_refresh_after = None
        self.app.root = Mock()
        self.app.root.after.return_value = "refresh-timer"
        for name in ("_cancel_auto_refresh", "_schedule_auto_refresh", "_auto_refresh"):
            setattr(self.app, name, getattr(M31App, name).__get__(self.app))

    def test_auto_refresh_schedules_read_only_callback_and_cancels(self):
        self.refresh_fixture()
        M31App._toggle_auto_refresh(self.app)
        self.app.root.after.assert_called_once_with(500, self.app._auto_refresh)
        self.app.auto_refresh.get.return_value = False
        M31App._toggle_auto_refresh(self.app)
        self.app.root.after_cancel.assert_called_once_with("refresh-timer")
        self.assertIsNone(self.app.auto_refresh_after)
        self.assertEqual(self.app.session.mock_calls, [])

    def test_auto_refresh_never_reads_disconnected_busy_or_closing(self):
        self.refresh_fixture()
        self.app._read = Mock()
        for attribute, value in (("connected", False), ("busy", True), ("closing", True)):
            previous = getattr(self.app, attribute)
            setattr(self.app, attribute, value)
            self.app._auto_refresh()
            setattr(self.app, attribute, previous)
        self.app._read.assert_not_called()
        self.app.root.after.assert_not_called()

    def test_auto_refresh_invalid_address_or_count_stops_and_cancels(self):
        self.refresh_fixture()
        for address, count in (("bad", "1"), ("65535", "2"), ("0", "126"), ("0", "0")):
            with self.subTest(address=address, count=count):
                self.app.auto_refresh_after = "timer"
                self.app.auto_refresh.reset_mock()
                self.app.address, self.app.count = variable(address), variable(count)
                M31App._read(self.app, automatic=True)
                self.app.auto_refresh.set.assert_called_once_with(False)
                self.assertIsNone(self.app.auto_refresh_after)
        self.assertEqual(self.app._error.call_count, 4)
        self.app._run.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])

    def test_auto_refresh_invalid_interval_stops_without_io(self):
        self.refresh_fixture()
        for value in ("bad", "nan", "inf", "0.09", "5.1"):
            with self.subTest(interval=value):
                self.app.auto_refresh.reset_mock()
                self.app.refresh_interval = variable(value)
                self.app._schedule_auto_refresh()
                self.app.auto_refresh.set.assert_called_once_with(False)
                self.assertIsNone(self.app.auto_refresh_after)
        self.assertEqual(self.app._error.call_count, 5)
        self.app.root.after.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])

    def test_auto_refresh_interval_change_replaces_timer_without_io(self):
        self.refresh_fixture()
        self.app.auto_refresh_after = "old-timer"
        self.app.refresh_interval = variable("0.1")
        self.app._schedule_auto_refresh()
        self.app.root.after_cancel.assert_called_once_with("old-timer")
        self.app.root.after.assert_called_once_with(100, self.app._auto_refresh)
        self.assertEqual(self.app.auto_refresh_after, "refresh-timer")
        self.app._run.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])

    def test_auto_refresh_invalid_toggle_does_not_report_enabled(self):
        self.refresh_fixture()
        self.app.refresh_interval = variable("nan")
        self.app.auto_refresh.set.side_effect = (
            lambda value: setattr(self.app.auto_refresh.get, "return_value", value)
        )
        M31App._toggle_auto_refresh(self.app)
        self.app.auto_refresh.set.assert_called_once_with(False)
        self.app.status.set.assert_not_called()
        self.app.root.after.assert_not_called()
        self.app._run.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])

    def test_disconnect_cancels_refresh_before_worker_and_updates_controls(self):
        self.refresh_fixture()
        self.app.auto_refresh_after = "refresh-timer"
        self.app._refresh_controls = Mock()
        actions = Mock()
        actions.attach_mock(self.app.auto_refresh.set, "disable")
        actions.attach_mock(self.app.root.after_cancel, "cancel")
        actions.attach_mock(self.app._refresh_controls, "controls")
        actions.attach_mock(self.app._run, "run")
        M31App._disconnect(self.app)
        self.assertEqual(
            actions.mock_calls[:3],
            [call.disable(False), call.cancel("refresh-timer"), call.controls()],
        )
        self.assertEqual(actions.mock_calls[3][0], "run")
        self.assertEqual(self.app._run.call_args.args[:2], ("Disconnect", self.app.session.close))
        self.assertIsNone(self.app.auto_refresh_after)
        self.assertEqual(self.app.session.mock_calls, [])

    @patch("m31tool.app.load_csv")
    @patch("m31tool.app.filedialog", new_callable=Mock)
    def test_csv_import_is_local_only(self, dialog, load):
        dialog.askopenfilename.return_value = "unused-test.csv"
        load.return_value = [("Holding registers", 0, 42)]
        M31App._import_csv(self.app)
        self.app._display.assert_called_once()
        self.assertIn("LOCAL CSV", self.app._display.call_args.args[1])
        self.app._run.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])


if __name__ == "__main__":
    unittest.main()
