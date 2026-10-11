"""Independent native Tk layout/keyboard checks; device traffic is loopback only."""

import os
import threading
import time
import unittest
from unittest.mock import patch

from m31tool.app import INTERPRETATIONS, M31App
from m31tool.core import M31_REGISTERS
from tests.modbus_simulator import running_simulator

try:
    import tkinter as tk
    from tkinter import ttk
except ModuleNotFoundError:
    tk = ttk = None


@unittest.skipUnless(tk is not None and os.environ.get("DISPLAY"),
                     "A graphical X display is required for native Tk layout tests.")
class NativeLayoutTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display is unavailable: {exc}")
        self.addCleanup(self._close)
        self.simulator_context = running_simulator()
        self.simulator = self.simulator_context.__enter__()
        self.dialog_patch = patch("m31tool.app.messagebox")
        self.messagebox = self.dialog_patch.start()
        self.messagebox.askyesno.return_value = False
        self.addCleanup(self.dialog_patch.stop)
        self.app = M31App(self.root)
        self.root.geometry("1280x800")
        self.root.update()

    def _close(self):
        try:
            if hasattr(self, "app"):
                self.app._request_close()
                self.wait_for(lambda: not self.root_exists())
            else:
                self.root.destroy()
        except tk.TclError:
            pass
        finally:
            if hasattr(self, "simulator_context"):
                self.simulator_context.__exit__(None, None, None)

    def wait_for(self, predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                self.root.update()
                if predicate():
                    return
            except tk.TclError:
                if predicate():
                    return
                raise
            time.sleep(0.01)
        self.fail(f"GUI did not settle; status={self.app.status.get()!r}")

    def root_exists(self):
        try:
            return bool(self.root.winfo_exists())
        except tk.TclError:
            return False

    def connect(self):
        host, port = self.simulator.address
        self.app.host.set(host)
        self.app.tcp_port.set(str(port))
        self.app.connect_button.invoke()
        self.wait_for(lambda: not self.app.busy)
        self.assertTrue(self.app.connected, self.app.status.get())

    def widgets(self, parent=None):
        for child in (parent or self.app).winfo_children():
            yield child
            yield from self.widgets(child)

    def entry(self, variable):
        return next(widget for widget in self.widgets()
                    if isinstance(widget, ttk.Entry)
                    and str(widget.cget("textvariable")) == str(variable))

    def key(self, widget, sequence):
        widget.focus_force()
        self.root.update()
        widget.event_generate(sequence)
        self.root.update()

    def show_tab(self, widget):
        while widget.master != self.app.notebook:
            widget = widget.master
        self.app.notebook.select(widget)
        self.root.update()

    def notebook_tab(self, widget):
        while widget.master is not None:
            if widget.master == self.app.notebook:
                return str(widget)
            widget = widget.master
        return None

    def assert_visible_bounds(self, widget):
        self.assertTrue(widget.winfo_ismapped(), str(widget))
        self.assertGreater(widget.winfo_width(), 8, str(widget))
        self.assertGreater(widget.winfo_height(), 8, str(widget))
        left, top = widget.winfo_rootx(), widget.winfo_rooty()
        right = left + widget.winfo_width()
        bottom = top + widget.winfo_height()
        parent = widget.master
        while parent is not None:
            with self.subTest(widget=str(widget), viewport=str(parent)):
                self.assertGreaterEqual(left, parent.winfo_rootx() - 1)
                self.assertGreaterEqual(top, parent.winfo_rooty() - 1)
                self.assertLessEqual(right, parent.winfo_rootx() + parent.winfo_width() + 1)
                self.assertLessEqual(bottom, parent.winfo_rooty() + parent.winfo_height() + 1)
            parent = parent.master

    def test_primary_controls_fit_all_tabs_at_supported_sizes(self):
        for size in ("850x680", "1280x800"):
            self.root.geometry(size)
            for transport in ("TCP", "RTU"):
                self.app.transport.set(transport)
                self.app._show_transport()
                for tab in self.app.notebook.tabs():
                    self.app.notebook.select(tab)
                    self.root.update()
                    with self.subTest(size=size, transport=transport, tab=tab):
                        for widget in self.widgets():
                            if isinstance(widget, ttk.Button) and self.notebook_tab(widget) in (
                                None, tab,
                            ):
                                self.assertTrue(widget.winfo_ismapped(),
                                                f"Action hidden: {widget.cget('text')}")
                            if widget.winfo_ismapped() and isinstance(
                                widget, (ttk.Button, ttk.Entry, ttk.Combobox)
                            ):
                                self.assert_visible_bounds(widget)
                                if isinstance(widget, ttk.Button):
                                    self.assertGreaterEqual(
                                        widget.winfo_width(), widget.winfo_reqwidth() - 2,
                                        f"Truncated button: {widget.cget('text')}",
                                    )
                            elif widget.winfo_ismapped() and isinstance(
                                widget, (ttk.Treeview, tk.Text)
                            ):
                                self.assert_visible_bounds(widget)
                                self.assertGreaterEqual(widget.winfo_height(), 48,
                                                        "Data viewport collapsed")
                        self.assert_visible_bounds(self.app.status_label)
        self.assertEqual(self.simulator.requests, [])

    def test_summary_identity_survives_errors_but_not_disconnect(self):
        self.assertIn("disconnected", self.app.connection_summary.get().lower())
        self.assertEqual(self.simulator.requests, [])
        self.connect()
        destination = self.app.destination
        self.assertIn(destination, self.app.connection_summary.get())
        self.app.address.set("65535")
        self.app.count.set("2")
        self.app.read_button.invoke()
        self.root.update()
        self.assertIn("failed", self.app.status.get().lower())
        self.assertTrue(self.app.connected)
        self.assertIn(destination, self.app.connection_summary.get())
        self.assertEqual(self.simulator.requests, [])
        self.app.disconnect_button.invoke()
        self.wait_for(lambda: not self.app.busy)
        self.assertFalse(self.app.connected)
        self.assertIn("disconnected", self.app.connection_summary.get().lower())
        self.assertTrue(self.app.connection_summary.get().lower().startswith("disconnected"))

    def test_long_status_wraps_without_hiding_primary_actions(self):
        self.root.geometry("850x680")
        self.app._error(
            "Read",
            ConnectionError("The peer closed the connection before a complete response "
                            "was received. Verify the host, port and network; displayed "
                            "values are unchanged and have not been refreshed."),
        )
        self.root.update()
        self.assertGreater(int(self.app.status_label.cget("wraplength")), 0)
        self.assertLessEqual(self.app.status_label.winfo_reqheight(),
                             self.app.status_label.winfo_height() + 2)
        for widget in (self.app.status_label, self.app.connect_button, self.app.read_button):
            self.assert_visible_bounds(widget)
        self.show_tab(self.app.write_button)
        self.assert_visible_bounds(self.app.write_button)

    def test_return_connect_and_read_use_existing_callback_guards(self):
        host_entry = self.entry(self.app.host)
        address_entry = self.entry(self.app.address)
        with patch.object(self.app, "_run") as run:
            self.key(address_entry, "<Return>")
            run.assert_not_called()
            host, port = self.simulator.address
            self.app.host.set(host)
            self.app.tcp_port.set(str(port))
            self.key(host_entry, "<Return>")
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0], "Connect")
            run.reset_mock()
            self.app.connected = True
            self.app._refresh_controls()
            self.key(address_entry, "<Return>")
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0], "Read")
            run.reset_mock()
            for attribute in ("busy", "closing"):
                setattr(self.app, attribute, True)
                self.key(address_entry, "<Return>")
                self.key(host_entry, "<Return>")
                run.assert_not_called()
                setattr(self.app, attribute, False)
            self.app.connected = False
            self.app._refresh_controls()
        self.assertEqual(self.simulator.requests, [])

    def test_catalog_return_prepares_two_word_float_without_io(self):
        spec = next(entry for entry in M31_REGISTERS if entry.key == "ai_float")
        item = next(item for item in self.app.catalog_tree.get_children()
                    if self.app.catalog_tree.item(item, "values")[0] == spec.label)
        self.show_tab(self.app.catalog_tree)
        self.app.catalog_tree.selection_set(item)
        self.app.catalog_tree.focus(item)
        self.app.catalog_tree.see(item)
        self.key(self.app.catalog_tree, "<Return>")
        self.assertEqual(self.app.object_type.get(), "Input registers")
        self.assertEqual(self.app.address.get(), str(spec.address))
        self.assertEqual(self.app.count.get(), "2")
        self.assertEqual(self.app.notebook.select(), str(self.app.explorer))
        self.assertTrue(self.app.catalog_detail.get())
        self.assertEqual(self.simulator.requests, [])
        for attribute in ("busy", "closing"):
            setattr(self.app, attribute, True)
            self.app.address.set("7")
            self.app._prepare_catalog_item(item)
            self.assertEqual(self.app.address.get(), "7")
            setattr(self.app, attribute, False)

    def test_ctrl_tab_and_reverse_traverse_notebook(self):
        tabs = self.app.notebook.tabs()
        self.app.notebook.select(tabs[0])
        self.key(self.entry(self.app.address), "<Control-Tab>")
        self.assertEqual(self.app.notebook.select(), tabs[1])
        self.key(self.app.notebook, "<Control-Shift-Tab>")
        self.assertEqual(self.app.notebook.select(), tabs[0])
        self.assertEqual(self.simulator.requests, [])

    def test_busy_progress_and_cursor_clear_after_success_and_error(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                release = threading.Event()

                def operation():
                    if not release.wait(5):
                        raise TimeoutError("Test worker was not released")
                    if fail:
                        raise ConnectionError("Simulated read failure")
                    return []

                try:
                    self.app._run("Read", operation, lambda _: None)
                    self.root.update()
                    self.assertTrue(self.app.busy)
                    self.assertEqual(str(self.app.progress.cget("mode")), "indeterminate")
                    self.assertTrue(self.root.cget("cursor"))
                    self.assertEqual(str(self.app.connect_button.cget("state")), "disabled")
                finally:
                    release.set()
                    self.wait_for(lambda: not self.app.busy)
                self.assertEqual(self.root.cget("cursor"), "")
                self.assertEqual(float(self.app.progress.cget("value")), 0)
                self.assertEqual(str(self.app.connect_button.cget("state")), "normal")
        self.assertEqual(self.simulator.requests, [])

    def test_shutdown_cancels_native_progress_timer_before_destroy(self):
        pending_at_destroy = []
        destroy = self.root.destroy

        def checked_destroy():
            pending_at_destroy.extend(
                str(self.root.tk.call("after", "info", timer))
                for timer in self.root.tk.call("after", "info")
            )
            destroy()

        with patch.object(self.root, "destroy", side_effect=checked_destroy):
            self.app._request_close()
            self.wait_for(lambda: not self.root_exists())
        self.assertFalse(
            any("ttk::progressbar::Autoincrement" in timer for timer in pending_at_destroy),
            f"Native progress callback survives root destruction: {pending_at_destroy}",
        )
        self.assertEqual(self.simulator.requests, [])

    def test_local_source_visible_in_interpretation_and_write_remains_default_no(self):
        rows = [("Holding registers", 0, 16256), ("Holding registers", 1, 0)]
        with patch("m31tool.app.filedialog.askopenfilename", return_value="mock.csv"), \
                patch("m31tool.app.load_csv", return_value=rows):
            self.app.import_button.invoke()
        self.show_tab(self.app.decoded_view)
        self.app.interpretation.set(INTERPRETATIONS[1])
        self.app._update_interpretation()
        self.root.update()
        source_labels = [widget for widget in self.widgets()
                         if isinstance(widget, ttk.Label) and widget.winfo_ismapped()
                         and str(widget.cget("textvariable")) == str(self.app.source)]
        self.assertTrue(source_labels, "Interpretation must show the raw data's source")
        self.assertIn("LOCAL CSV", self.app.source.get())
        self.assertIn("1.0", self.app.decoded_view.get("1.0", "end"))
        self.assertEqual(self.app.rows, rows)
        self.assertEqual(self.simulator.requests, [])
        self.connect()
        self.show_tab(self.app.write_button)
        self.key(self.entry(self.app.write_value), "<Return>")
        self.messagebox.askyesno.assert_not_called()
        self.app.write_button.invoke()
        self.messagebox.askyesno.assert_called_once()
        self.assertEqual(self.messagebox.askyesno.call_args.kwargs["default"], "no")
        self.assertEqual(self.simulator.requests, [])


if __name__ == "__main__":
    unittest.main()
