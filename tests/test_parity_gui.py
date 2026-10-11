"""Parity UI safety and real desktop tests; device traffic stays on loopback."""

from pathlib import Path
import shutil
import unittest
import uuid
from unittest.mock import Mock, call, patch

from m31tool.app import M31App, PROFILE_FIELDS
from m31tool.core import M31_REGISTERS
from m31tool.device import DEVICE_READ_SPECS, DEVICE_REGISTER_CATALOG
from m31tool.formats import load_profile, load_xlsx, save_xlsx
from tests import test_gui_desktop as desktop, test_gui_safety as safety

variable = safety.variable


class ParitySafetyTests(unittest.TestCase):
    setUp = safety.GUISafetyTests.setUp
    operation = safety.GUISafetyTests.operation

    @patch("m31tool.app.read_device_info")
    def test_device_read_runs_only_explicitly_in_worker(self, read):
        self.app.device_source = Mock()
        read.return_value = {"fields": [], "source": "manual", "read_only": True}
        M31App._read_device_info(self.app)
        read.assert_not_called()
        self.assertEqual(self.operation()(), read.return_value)
        read.assert_called_once_with(self.app.session)
        self.dialog.askyesno.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])

    @patch("m31tool.app.read_device_info")
    def test_device_read_inactive_busy_closing_never_starts(self, read):
        self.app.device_source = Mock()
        for attribute, value in (
            ("connected", False), ("busy", True), ("closing", True),
        ):
            previous = getattr(self.app, attribute)
            setattr(self.app, attribute, value)
            M31App._read_device_info(self.app)
            setattr(self.app, attribute, previous)
        self.app._run.assert_not_called()
        read.assert_not_called()
        self.app.device_source.set.assert_not_called()

    @patch("m31tool.app.negotiate_addresses")
    def test_negotiation_cancelled_or_blocked_sends_nothing(self, negotiate):
        self.dialog.askyesno.return_value = False
        M31App._negotiate(self.app)
        self.assertEqual(self.dialog.askyesno.call_args.kwargs["default"], "no")
        text = self.dialog.askyesno.call_args.args[1]
        for warning in ("topology", "addresses may change", "0x7584", "0x7585",
                        "30-second", "NOT a vendor", self.app.destination):
            self.assertIn(warning, text)
        self.dialog.askyesno.reset_mock()
        for attribute, value in (
            ("connected", False), ("busy", True), ("closing", True),
        ):
            previous = getattr(self.app, attribute)
            setattr(self.app, attribute, value)
            M31App._negotiate(self.app)
            setattr(self.app, attribute, previous)
        self.dialog.askyesno.assert_not_called()
        negotiate.assert_not_called()
        self.app._run.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])

    @patch("m31tool.app.negotiate_addresses")
    def test_confirmed_negotiation_runs_only_worker_with_client_deadline(self, negotiate):
        self.app.negotiation_result, self.app.device_source = Mock(), Mock()
        M31App._negotiate(self.app)
        negotiate.assert_not_called()
        self.operation()()
        negotiate.assert_called_once_with(self.app.session, timeout=30.0, poll_interval=0.25)
        self.assertEqual(self.app.session.mock_calls, [])

    def test_multiple_registers_confirm_entire_range_and_verify_every_value(self):
        self.app.write_address = variable("10")
        self.app.write_value = variable("42, 0xffff, 0")
        self.app.session.read_holding_registers.return_value = [42, 65535, 0]
        M31App._write(self.app)
        self.assertEqual(
            self.operation()(),
            [("Holding registers", 10, 42), ("Holding registers", 11, 65535),
             ("Holding registers", 12, 0)],
        )
        self.assertEqual(self.app.session.mock_calls, [
            call.write_registers(10, [42, 65535, 0]),
            call.read_holding_registers(10, 3),
        ])
        text = self.dialog.askyesno.call_args.args[1]
        self.assertIn("10–12", text)
        self.assertIn("42, 65535, 0", text)
        self.assertIn("10.", text)
        self.assertEqual(self.dialog.askyesno.call_args.kwargs["default"], "no")

    def test_multiple_coils_and_cancellation(self):
        self.app.write_type = variable("Coils")
        self.app.write_value = variable("1,0,1")
        self.dialog.askyesno.return_value = False
        M31App._write(self.app)
        self.app._run.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])
        self.dialog.askyesno.return_value = True
        self.app.session.read_coils.return_value = [True, False, True]
        M31App._write(self.app)
        self.operation()()
        self.assertEqual(self.app.session.mock_calls, [
            call.write_coils(0, [True, False, True]), call.read_coils(0, 3),
        ])
        self.assertIn("0F.", self.dialog.askyesno.call_args.args[1])

    def test_float_write_uses_explicit_order_and_complete_raw_readback(self):
        self.app.write_encoding = variable("IEEE754 float32")
        self.app.write_word_order = variable("little")
        self.app.write_address = variable("1000")
        self.app.write_value = variable("123.25, -2.5")
        words = [0x8000, 0x42F6, 0, 0xC020]
        self.app.session.read_holding_registers.return_value = words
        M31App._write(self.app)
        self.operation()()
        self.assertEqual(self.app.session.mock_calls, [
            call.write_registers(1000, words), call.read_holding_registers(1000, 4),
        ])
        text = self.dialog.askyesno.call_args.args[1]
        for detail in ("IEEE754", "little", "123.25", "-2.5", "1000–1003",
                       "32768, 17142, 0, 49184", "NOT inferred"):
            self.assertIn(detail, text)
        self.assertEqual(self.dialog.askyesno.call_args.kwargs["default"], "no")

    def test_float_invalid_order_type_value_and_span_never_start_io(self):
        self.app.write_encoding = variable("IEEE754 float32")
        for kind, address, text, order in (
            ("Holding registers", "1000", "1.0", ""),
            ("Holding registers", "1000", "1.0", "BIG"),
            ("Coils", "0", "1.0", "big"),
            ("Holding registers", "1000", "NaN", "big"),
            ("Holding registers", "1000", "1e40", "little"),
            ("Holding registers", "65535", "1.0", "big"),
        ):
            with self.subTest(kind=kind, address=address, text=text, order=order):
                self.app.write_type = variable(kind)
                self.app.write_address = variable(address)
                self.app.write_value = variable(text)
                self.app.write_word_order = variable(order)
                M31App._write(self.app)
        self.assertEqual(self.app._error.call_count, 6)
        self.dialog.askyesno.assert_not_called()
        self.app._run.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])

    def test_float_cancelled_write_and_failed_readback_are_not_success(self):
        self.app.write_encoding = variable("IEEE754 float32")
        self.app.write_word_order = variable("big")
        self.app.write_value = variable("1.0")
        self.dialog.askyesno.return_value = False
        M31App._write(self.app)
        self.app._run.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])
        self.dialog.askyesno.return_value = True
        self.app.session.read_holding_registers.return_value = [0x3F80, 1]
        M31App._write(self.app)
        with self.assertRaisesRegex(RuntimeError, "verification failed"):
            self.operation()()
        self.assertEqual(self.app.session.mock_calls, [
            call.write_registers(0, [0x3F80, 0]), call.read_holding_registers(0, 2),
        ])
        self.app._display.assert_not_called()

    def test_multivalue_invalid_input_rejected_before_confirmation(self):
        for kind, address, values in (
            ("Holding registers", "65535", "1,2"),
            ("Holding registers", "0", "1,"),
            ("Holding registers", "0", "1,,2"),
            ("Holding registers", "0", ",".join(["0"] * 124)),
            ("Coils", "0", "1,2"),
            ("Coils", "0", ",".join(["0"] * 1969)),
        ):
            with self.subTest(kind=kind, address=address, values=values[:20]):
                self.app.write_type = variable(kind)
                self.app.write_address = variable(address)
                self.app.write_value = variable(values)
                M31App._write(self.app)
        self.assertEqual(self.app._error.call_count, 6)
        self.dialog.askyesno.assert_not_called()
        self.app._run.assert_not_called()

    def test_multivalue_mismatch_short_read_and_write_error_are_not_success(self):
        self.app.write_value = variable("42,43")
        for actual in ([42, 17], [42], [42, 43, 44]):
            self.app.session.read_holding_registers.return_value = actual
            M31App._write(self.app)
            with self.assertRaisesRegex(RuntimeError, "No rollback"):
                self.operation()()
        self.app.session.write_registers.side_effect = ConnectionError("lost ack")
        M31App._write(self.app)
        with self.assertRaisesRegex(RuntimeError, "could have taken effect"):
            self.operation()()
        self.app._display.assert_not_called()

    @patch("m31tool.app.filedialog", new_callable=Mock)
    @patch("m31tool.app.load_xlsx", return_value=[("Coils", 1, 1)])
    def test_xlsx_import_is_local_only_and_failure_preserves_table(self, load, dialog):
        dialog.askopenfilename.return_value = "unused.xlsx"
        M31App._import_xlsx(self.app)
        self.assertIn("LOCAL XLSX", self.app._display.call_args.args[1])
        self.app._display.reset_mock()
        load.side_effect = ValueError("bad workbook")
        M31App._import_xlsx(self.app)
        self.app._display.assert_not_called()
        self.app._error.assert_called_once()
        self.app._run.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])

    @patch("m31tool.app.filedialog", new_callable=Mock)
    @patch("m31tool.app.load_profile")
    def test_profile_connected_busy_closing_and_cancelled_do_not_load(self, load, dialog):
        M31App._load_profile(self.app)
        self.app.connected = False
        self.app.busy = True
        M31App._load_profile(self.app)
        self.app.busy, self.app.closing = False, True
        M31App._load_profile(self.app)
        dialog.askopenfilename.assert_not_called()
        self.app.closing = False
        dialog.askopenfilename.return_value = ""
        M31App._load_profile(self.app)
        load.assert_not_called()
        self.app._run.assert_not_called()
        self.assertEqual(self.app.session.mock_calls, [])


@unittest.skipUnless(desktop.tk is not None, "Tk is required for desktop tests.")
class ParityDesktopTests(unittest.TestCase):
    setUp = desktop.DesktopGUITests.setUp
    tearDown = desktop.DesktopGUITests.tearDown

    def test_float_input_real_tk_loopback_has_two_word_write_and_readback(self):
        self.connect()
        self.assertEqual(self.app.write_encoding.get(), "Raw unsigned values")
        self.assertEqual(self.app.write_word_order.get(), "")
        self.app.write_encoding.set("IEEE754 float32")
        self.app.write_word_order.set("little")
        self.app.write_address.set("1000")
        self.app.write_value.set("123.25")
        self.simulator.holding_registers.update({1000: 0, 1001: 0})
        self.messagebox.askyesno.return_value = False
        self.app._write()
        self.assertEqual(self.simulator.requests, [])
        self.messagebox.askyesno.return_value = True
        self.app._write()
        self.wait_for(lambda: not self.app.busy)
        self.assertIn("Write verified", self.app.status.get())
        self.assertEqual(self.app.rows, [
            ("Holding registers", 1000, 0x8000), ("Holding registers", 1001, 0x42F6),
        ])
        self.assertEqual(self.simulator.requests, [
            (1, bytes.fromhex("1003e8000204800042f6")),
            (1, bytes.fromhex("0303e80002")),
        ])
        self.assertEqual(self.simulator.holding_registers[1000], 0x8000)
        self.assertEqual(self.simulator.holding_registers[1001], 0x42F6)

    def test_trace_refresh_copy_clear_are_local_and_show_actual_callback_bytes(self):
        self.app._refresh_trace()
        self.assertEqual(self.app.trace_rows, [])
        self.assertEqual(self.simulator.requests, [])
        self.connect()
        self.app.address.set("0")
        self.app.count.set("1")
        self.app._read()
        self.wait_for(lambda: not self.app.busy)
        requests = list(self.simulator.requests)
        records = self.app.session.trace_snapshot()
        self.assertTrue(records)
        self.app._refresh_trace()
        self.assertEqual(len(self.app.trace_rows), len(records))
        self.assertEqual(
            [row[-1] for row in self.app.trace_rows],
            [record.data.hex(" ") for record in records],
        )
        self.app._copy_trace()
        copied = self.root.clipboard_get()
        for detail in ("NOT packet capture", "TX attempt", "RX buffer", "unit 1"):
            self.assertIn(detail, copied)
        for record in records:
            self.assertIn(record.data.hex(" "), copied)
        self.app._clear_trace()
        self.assertEqual(self.app.trace_rows, [])
        self.assertEqual(self.app.session.trace_snapshot(), ())
        self.assertEqual(self.simulator.requests, requests)
    wait_for = desktop.DesktopGUITests.wait_for
    connect = desktop.DesktopGUITests.connect

    def test_device_tab_initially_idle_and_disabled(self):
        self.assertEqual(str(self.app.device_read_button["state"]), "disabled")
        self.assertEqual(str(self.app.negotiate_button["state"]), "disabled")
        self.assertEqual(self.app.device_results.get_children(), ())
        self.app.device_read_button.invoke()
        self.root.update()
        self.assertEqual(self.simulator.requests, [])
        self.assertIn("No device", self.app.device_source.get())

    def test_negotiation_real_tk_fake_domain_result_errors_and_explicit_refresh(self):
        result = {
            "source": "manual", "read_only": False, "status": 1,
            "status_label": "Complete", "exception": 0, "exception_label": "None",
            "success": True, "bitmap_raw_words": [0, 2], "bitmap_raw_hex": "0x0000 0x0002",
        }
        self.connect()
        self.root.geometry("850x680")
        before = list(self.simulator.requests)
        self.messagebox.askyesno.return_value = False
        with patch("m31tool.app.negotiate_addresses", return_value=result) as negotiate:
            self.app.negotiate_button.invoke()
            self.assertFalse(self.app.busy)
            negotiate.assert_not_called()
            self.messagebox.askyesno.return_value = True
            self.app.negotiate_button.invoke()
            self.assertTrue(self.app.busy)
            self.assertEqual(str(self.app.negotiate_button["state"]), "disabled")
            self.wait_for(lambda: not self.app.busy)
            negotiate.assert_called_once_with(
                self.app.session, timeout=30.0, poll_interval=0.25
            )
        self.assertIn("0x0001", self.app.negotiation_result.get())
        self.assertIn("0x0000 0x0002", self.app.negotiation_result.get())
        self.assertIn("Explicitly Read", self.app.negotiation_result.get())
        self.assertIn("stale", self.app.device_source.get())
        self.assertEqual(self.app.device_results.get_children(), ())
        self.assertEqual(self.simulator.requests, before)

        result.update(exception=2, exception_label="Wrong sequence", success=False)
        with patch("m31tool.app.negotiate_addresses", return_value=result):
            self.app.negotiate_button.invoke()
            self.wait_for(lambda: not self.app.busy)
        self.assertIn("reported exception", self.app.status.get())
        self.assertIn("Wrong sequence", self.app.negotiation_result.get())
        for failure in (TimeoutError("client deadline"), ConnectionError("lost")):
            with patch("m31tool.app.negotiate_addresses", side_effect=failure):
                self.app.negotiate_button.invoke()
                self.wait_for(lambda: not self.app.busy)
            self.assertIn("FAILED", self.app.negotiation_result.get())
            self.assertIn("may have changed", self.app.negotiation_result.get())
            self.assertIn("No rollback or retry", self.app.negotiation_result.get())
        self.messagebox.showerror.assert_called()
        self.assertEqual(self.simulator.requests, before)
        self.root.update_idletasks()
        status = self.app.winfo_children()[-1]
        self.assertLessEqual(
            status.winfo_rooty() - self.root.winfo_rooty() + status.winfo_height(),
            self.root.winfo_height(),
        )

    def test_device_read_fake_session_real_tk_renders_and_preserves_raw_explorer(self):
        self.connect()
        rows = [("Holding registers", 0, 17)]
        self.app._display(rows, "Existing explorer read")
        before = list(self.simulator.requests)
        with patch.object(
            self.app.session, "read_holding_registers",
            side_effect=lambda address, count: [0] * count,
        ) as read:
            self.app.device_read_button.invoke()
            self.assertTrue(self.app.busy)
            self.assertEqual(str(self.app.device_read_button["state"]), "disabled")
            self.wait_for(lambda: not self.app.busy)
        self.assertEqual(
            read.call_args_list,
            [call(spec.address, spec.count) for spec in DEVICE_READ_SPECS],
        )
        items = self.app.device_results.get_children()
        self.assertEqual(len(items), len(DEVICE_REGISTER_CATALOG))
        first = self.app.device_results.item(items[0], "values")
        self.assertEqual(first[0], DEVICE_REGISTER_CATALOG[0].label)
        self.assertIn("0x", first[1])
        self.assertIn("0 / 0x0000", first[2])
        self.assertTrue(first[3])
        self.assertIn("READ-ONLY snapshot", self.app.device_source.get())
        self.assertIn(self.app.destination, self.app.device_source.get())
        self.assertIn("no writes", self.app.status.get())
        self.assertEqual(self.app.rows, rows)
        self.assertEqual(self.app.source.get(), "Existing explorer read")
        self.assertEqual(self.simulator.requests, before)

        snapshot = [self.app.device_results.item(item, "values") for item in items]
        with patch("m31tool.app.read_device_info", side_effect=ValueError("device rejected read")):
            self.app.device_read_button.invoke()
            self.wait_for(lambda: not self.app.busy)
        self.assertIn("FAILED", self.app.device_source.get())
        self.assertIn("device rejected read", self.app.status.get())
        self.messagebox.showerror.assert_called()
        self.assertEqual(snapshot, [
            self.app.device_results.item(item, "values")
            for item in self.app.device_results.get_children()
        ])
        self.assertEqual(self.simulator.requests, before)

    def local_directory(self):
        directory = Path(__file__).parent / (".parity-test-" + uuid.uuid4().hex)
        directory.mkdir()
        self.addCleanup(shutil.rmtree, directory)
        return directory

    def test_raw_float_display_word_order_pairs_and_exports_are_unchanged(self):
        rows = [
            ("Input registers", 1000, 0x3f80), ("Input registers", 1001, 0),
            ("Input registers", 1002, 0), ("Input registers", 1003, 0x4000),
            ("Input registers", 1005, 42), ("Coils", 0, 1),
        ]
        self.app._display(rows, "LOCAL test values")
        self.app.interpretation.set("IEEE754 float32")
        self.app._update_interpretation()
        self.assertIn("1000–1001: 1.0", self.app.decoded.get())
        self.assertIn("1005: missing consecutive word", self.app.decoded.get())
        self.assertIn("not a register", self.app.decoded.get())
        self.app.word_order.set("little")
        self.app._update_interpretation()
        self.assertIn("1002–1003: 2.0", self.app.decoded.get())
        self.assertEqual(self.app.rows, rows)
        self.assertEqual(len(self.app.results.get_children()), len(rows))
        self.assertEqual(self.simulator.requests, [])

    def test_catalog_float_prepares_two_word_read_without_io(self):
        for key, kind in (("ai_float", "Input registers"), ("ao_float", "Holding registers")):
            index = next(i for i, entry in enumerate(M31_REGISTERS) if entry.key == key)
            item = self.app.catalog_tree.get_children()[index]
            self.app.catalog_tree.identify_row = Mock(return_value=item)
            self.app._select_catalog(Mock(y=0))
            self.assertEqual(self.app.address.get(), "1000")
            self.assertEqual(self.app.count.get(), "2")
            self.assertEqual(self.app.object_type.get(), kind)
            self.assertEqual(self.app.interpretation.get(), "Raw unsigned 16-bit")
        self.assertEqual(self.simulator.requests, [])

    def test_range_catalog_prepares_reads_only_and_keeps_ao_conflict_visible(self):
        for key, address in (("ai_range", 0x0DAC), ("ao_range", 0x1194)):
            index = next(i for i, entry in enumerate(M31_REGISTERS) if entry.key == key)
            entry = M31_REGISTERS[index]
            self.assertIn("lesen", entry.label)
            if key == "ao_range":
                self.assertIn("widersprüchlich", entry.description)
                self.assertIn("0x0DAC", entry.description)
            item = self.app.catalog_tree.get_children()[index]
            self.app.catalog_tree.identify_row = Mock(return_value=item)
            self.app._select_catalog(Mock(y=0))
            self.assertEqual(self.app.address.get(), str(address))
            self.assertEqual(self.app.count.get(), "1")
            self.assertEqual(self.app.object_type.get(), "Holding registers")
        self.assertEqual(self.simulator.requests, [])

    def test_complete_non_u_read_catalog_prepares_exact_device_field_widths(self):
        entries = self.app.catalog_entries
        self.assertEqual(len(entries), len(M31_REGISTERS) + len(DEVICE_REGISTER_CATALOG))
        self.assertEqual(len({entry.key for entry in entries}), len(entries))
        addresses = {entry.address for entry in entries}
        self.assertNotIn(0x7585, addresses)
        self.assertNotIn(0x753F, addresses)
        self.assertNotIn(0x7540, addresses)
        for candidate in (0x0C1D, 0x0C1E, 0x0C1F, 0x0C20, 0x0C2C, 0x0C80, 0x0D80):
            self.assertNotIn(candidate, addresses)
        self.app.write_address.set("17")
        self.app.write_value.set("42")
        for offset, spec in enumerate(DEVICE_REGISTER_CATALOG, len(M31_REGISTERS)):
            with self.subTest(field=spec.key):
                item = self.app.catalog_tree.get_children()[offset]
                self.app.catalog_tree.selection_set(item)
                self.app._show_catalog_detail()
                self.assertIn("read only", self.app.catalog_detail.get())
                self.assertIn("§4.8", self.app.catalog_detail.get())
                self.app._prepare_selected_catalog()
                self.assertEqual(self.app.address.get(), str(spec.address))
                self.assertEqual(self.app.count.get(), str(spec.count))
                self.assertEqual(self.app.object_type.get(), "Holding registers")
        self.assertEqual(self.app.write_address.get(), "17")
        self.assertEqual(self.app.write_value.get(), "42")
        self.assertEqual(self.simulator.requests, [])

    def test_minimum_window_keeps_write_and_status_visible(self):
        self.root.geometry("850x680")
        tab = self.app.write_button
        while tab.master != self.app.notebook:
            tab = tab.master
        self.app.notebook.select(tab)
        self.root.update()
        self.app.write_button.focus_force()
        self.root.update()
        self.assertEqual(self.app.notebook.tab(tab, "text"), "Device writes")
        self.assertEqual((self.root.winfo_width(), self.root.winfo_height()), (850, 680))
        for widget in (self.app.write_button, self.app.status_label, self.app.progress):
            self.assertTrue(widget.winfo_ismapped(), str(widget))
            self.assertGreater(widget.winfo_height(), 8)
            parent = widget.master
            while parent is not None:
                self.assertGreaterEqual(widget.winfo_rootx(), parent.winfo_rootx())
                self.assertGreaterEqual(widget.winfo_rooty(), parent.winfo_rooty())
                self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                     parent.winfo_rootx() + parent.winfo_width())
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                     parent.winfo_rooty() + parent.winfo_height())
                parent = parent.master
        self.assertEqual(self.simulator.requests, [])

    def test_local_xlsx_import_export_works_while_connected_without_io(self):
        directory = self.local_directory()
        imported, exported = directory / "in.xlsx", directory / "out.xlsx"
        rows = [("Holding registers", 10, 42), ("Holding registers", 11, 43)]
        save_xlsx(imported, rows)
        self.connect()
        before = list(self.simulator.requests)
        with patch("m31tool.app.filedialog.askopenfilename", return_value=str(imported)):
            self.app.import_xlsx_button.invoke()
        self.assertIn("LOCAL XLSX", self.app.source.get())
        self.app.write_value.set("7")
        with patch("m31tool.app.filedialog.asksaveasfilename", return_value=str(exported)):
            self.app.export_xlsx_button.invoke()
        self.assertEqual(load_xlsx(exported), rows)
        self.assertEqual(self.app.write_value.get(), "7")
        self.assertEqual(self.simulator.requests, before)

    def test_connect_and_local_import_profile_never_negotiate(self):
        directory = self.local_directory()
        workbook, profile = directory / "local.xlsx", directory / "profile.json"
        save_xlsx(workbook, [("Holding registers", 0, 1)])
        with patch("m31tool.app.negotiate_addresses") as negotiate:
            with patch("m31tool.app.filedialog.asksaveasfilename", return_value=str(profile)):
                self.app.save_profile_button.invoke()
            with patch("m31tool.app.filedialog.askopenfilename", return_value=str(profile)):
                self.app.load_profile_button.invoke()
            with patch("m31tool.app.filedialog.askopenfilename", return_value=str(workbook)):
                self.app.import_xlsx_button.invoke()
            self.connect()
            negotiate.assert_not_called()
        self.messagebox.askyesno.assert_not_called()
        self.assertEqual(self.simulator.requests, [])

    def test_client_profile_roundtrip_local_disconnected_and_invalid_atomic(self):
        directory = self.local_directory()
        path = directory / "profile.json"
        self.app.host.set("127.0.0.1")
        self.app.count.set("2")
        self.app.write_value.set("123")
        with patch("m31tool.app.filedialog.asksaveasfilename", return_value=str(path)):
            self.app.save_profile_button.invoke()
        settings = load_profile(path)
        self.assertEqual(set(settings), set(PROFILE_FIELDS))
        self.assertEqual(settings["count"], 2)
        self.assertNotIn("write_value", path.read_text())
        self.app.host.set("changed")
        with patch("m31tool.app.filedialog.askopenfilename", return_value=str(path)):
            self.app.load_profile_button.invoke()
        self.assertEqual(self.app.host.get(), "127.0.0.1")
        self.assertEqual(self.app.write_value.get(), "123")
        self.assertFalse(self.app.connected)
        self.assertEqual(self.simulator.requests, [])
        path.write_text('{"invalid":"schema"}')
        before = {name: getattr(self.app, name).get() for name in PROFILE_FIELDS}
        with patch("m31tool.app.filedialog.askopenfilename", return_value=str(path)):
            self.app.load_profile_button.invoke()
        self.assertEqual(before, {name: getattr(self.app, name).get() for name in PROFILE_FIELDS})
        self.messagebox.showerror.assert_called()
        self.assertEqual(self.simulator.requests, [])
        self.connect()
        self.assertEqual(str(self.app.load_profile_button["state"]), "disabled")
        with patch("m31tool.app.filedialog.askopenfilename") as dialog:
            self.app._load_profile()
        dialog.assert_not_called()

    def test_multiple_real_register_and_coil_writes_read_back_then_cancel(self):
        self.connect()
        self.messagebox.askyesno.return_value = True
        for kind, values, function in (
            ("Holding registers", "123,456", 0x10), ("Coils", "1,0,1", 0x0f),
        ):
            self.app.write_type.set(kind)
            self.app.write_value.set(values)
            self.app.write_button.invoke()
            self.wait_for(lambda: not self.app.busy)
            self.assertIn("Write verified", self.app.status.get())
            self.assertEqual(self.simulator.requests[-2][1][0], function)
            self.assertEqual(len(self.app.rows), len(values.split(",")))
        before = list(self.simulator.requests)
        self.messagebox.askyesno.return_value = False
        self.app.write_button.invoke()
        self.root.update()
        self.assertEqual(self.simulator.requests, before)

    def test_large_write_confirmation_is_scrollable_and_defaults_to_cancel(self):
        self.connect()
        values = ",".join(map(str, range(33)))
        self.app.write_value.set(values)
        before = list(self.simulator.requests)
        reviewed = []

        def cancel_dialog():
            dialog = next(
                widget for widget in self.root.winfo_children()
                if isinstance(widget, desktop.tk.Toplevel)
            )
            frames = dialog.winfo_children()
            details = next(
                widget for widget in frames[0].winfo_children()
                if isinstance(widget, desktop.tk.Text)
            )
            reviewed.append(details.get("1.0", "end"))
            self.assertIn("0–32", reviewed[0])
            self.assertIn(", ".join(map(str, range(33))), reviewed[0])
            self.assertEqual(str(details["state"]), "disabled")
            no = next(
                widget for widget in frames[1].winfo_children()
                if widget["text"] == "No — cancel"
            )
            no.invoke()

        self.root.after(100, cancel_dialog)
        self.app.write_button.invoke()
        self.assertEqual(len(reviewed), 1)
        self.assertEqual(self.simulator.requests, before)
        self.assertFalse(self.app.busy)


if __name__ == "__main__":
    unittest.main()
