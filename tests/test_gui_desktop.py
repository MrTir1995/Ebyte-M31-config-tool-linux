"""Real Tk widget and async application tests against a loopback Modbus peer."""

from pathlib import Path
import shutil
import unittest
import uuid
from unittest.mock import patch

from m31tool.app import M31App
from tests.modbus_simulator import running_simulator
from tests.tk_lifecycle import release_tk_fixture

try:
    import tkinter as tk
except ModuleNotFoundError:
    tk = None


HAS_DISPLAY = tk is not None


@unittest.skipUnless(HAS_DISPLAY, "A graphical display is required for Tk tests.")
class DesktopGUITests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display is unavailable: {exc}")
        self.addCleanup(release_tk_fixture, self)
        self.simulator_context = running_simulator()
        self.simulator = self.simulator_context.__enter__()
        self.app = M31App(self.root)
        self.dialogs = patch("m31tool.app.messagebox")
        self.messagebox = self.dialogs.start()
        self.addCleanup(self.dialogs.stop)
        self.root.update()

    def tearDown(self):
        try:
            if hasattr(self, "root") and hasattr(self, "app"):
                self.app._request_close()
                self.wait_for(lambda: not self.root.winfo_exists())
        except (tk.TclError, AssertionError):
            if hasattr(self, "root"):
                try:
                    self.root.destroy()
                except tk.TclError:
                    pass
            if hasattr(self, "app"):
                self.app.session.close()
        finally:
            if hasattr(self, "simulator_context"):
                self.simulator_context.__exit__(None, None, None)

    def wait_for(self, predicate, timeout=5):
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                self.root.update()
            except tk.TclError:
                break
            if predicate():
                return
            time.sleep(0.01)
        self.fail(f"Timed out waiting for GUI state; status={self.app.status.get()!r}")

    def connect(self):
        host, port = self.simulator.address
        self.app.host.set(host)
        self.app.tcp_port.set(str(port))
        self.app.connect_button.invoke()
        self.wait_for(lambda: not self.app.busy)
        self.assertTrue(self.app.connected, self.app.status.get())

    def test_worker_error_chain_does_not_retain_tk_frames(self):
        def fail():
            try:
                raise OSError("closed connection")
            except OSError as exc:
                raise ValueError("bad response") from exc

        self.app._run("Read", fail, lambda _: self.fail("Failure ran success callback"))
        self.app.worker_thread.join()
        event = self.app.events.get_nowait()
        error = event[2]
        self.assertIsInstance(error, ValueError)
        self.assertEqual(str(error), "bad response")
        self.assertIsInstance(error.__cause__, OSError)
        self.assertIsNone(error.__traceback__)
        self.assertIsNone(error.__cause__.__traceback__)
        self.assertIsNone(error.__context__.__traceback__)
        self.app.events.put(event)
        self.wait_for(lambda: not self.app.busy)
        self.assertIn("ValueError: bad response", self.app.status.get())
        self.messagebox.showerror.assert_called_once()
        self.assertEqual(self.simulator.requests, [])

    def test_destroy_removes_owned_timer_and_focus_binding(self):
        import time

        self.app._run(
            "Read", lambda: time.sleep(0.03),
            lambda _: self.fail("Destroyed frame ran a queued callback"),
        )
        worker = self.app.worker_thread
        callback = self.app._poll_after
        focus_binding = self.app._focus_binding
        self.app.auto_refresh_after = self.root.after(
            1000, lambda: self.fail("Destroyed frame ran auto-refresh"),
        )
        refresh_callback = self.app.auto_refresh_after
        self.assertIn(callback, self.root.tk.call("after", "info"))
        self.assertIn(focus_binding, self.root.bind("<FocusIn>"))
        self.app.destroy()
        self.assertFalse(worker.is_alive())
        self.assertIsNone(self.app.worker_thread)
        self.assertTrue(self.app.events.empty())
        self.assertNotIn(callback, self.root.tk.call("after", "info"))
        self.assertNotIn(refresh_callback, self.root.tk.call("after", "info"))
        self.assertIsNone(self.app.auto_refresh_after)
        self.assertNotIn(focus_binding, self.root.bind("<FocusIn>"))
        self.assertIsNone(self.app._poll_after)
        self.assertIsNone(self.app._focus_binding)
        self.app.destroy()
        # The frame is disposed, but the embedding root is still usable.
        self.root.update()
        self.root.destroy()
        self.app.closing = True

    def test_auto_refresh_polls_selected_range_read_only_and_stops_when_disabled(self):
        import time

        self.assertFalse(self.app.auto_refresh.get())
        self.connect()
        self.app.refresh_interval.set("0.1")
        self.app.auto_refresh_button.invoke()
        self.wait_for(lambda: len(self.simulator.requests) >= 2 and not self.app.busy)
        self.assertTrue(self.app.auto_refresh.get())
        self.assertTrue(all(request[1] == bytes.fromhex("0300000001")
                            for request in self.simulator.requests))
        self.assertIn("Auto-refresh read", self.app.source.get())
        self.app.auto_refresh_button.invoke()
        count = len(self.simulator.requests)
        deadline = time.monotonic() + 0.2
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(self.app.auto_refresh.get())
        self.assertEqual(len(self.simulator.requests), count)

    def test_auto_refresh_failure_disables_without_retry(self):
        import time

        self.connect()
        self.simulator.forced_exception = 2
        self.app.refresh_interval.set("0.1")
        self.app.auto_refresh_button.invoke()
        self.wait_for(lambda: not self.app.busy and not self.app.auto_refresh.get())
        self.assertIn("Auto refresh failed", self.app.status.get())
        self.messagebox.showerror.assert_called_once()
        deadline = time.monotonic() + 0.2
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertEqual(len(self.simulator.requests), 1)
        self.assertIsNone(self.app.auto_refresh_after)

    def test_auto_refresh_invalid_settings_unchecks_and_disconnect_cancels(self):
        self.connect()
        self.app.auto_refresh.set(True)
        self.app._schedule_auto_refresh()
        self.app.address.set("bad")
        self.app._read(automatic=True)
        self.assertFalse(self.app.auto_refresh.get())
        self.assertIsNone(self.app.auto_refresh_after)
        self.assertEqual(self.simulator.requests, [])
        self.app.address.set("0")
        self.app.auto_refresh.set(True)
        self.app._schedule_auto_refresh()
        self.app._disconnect()
        self.wait_for(lambda: not self.app.busy)
        self.assertFalse(self.app.auto_refresh.get())
        self.assertIsNone(self.app.auto_refresh_after)

    def test_initial_window_has_no_io_and_transport_switch_is_real(self):
        self.assertTrue(self.root.winfo_exists())
        self.assertEqual(self.app.results.get_children(), ())
        self.assertEqual(self.simulator.requests, [])
        self.assertEqual(str(self.app.read_button["state"]), "disabled")
        self.assertEqual(str(self.app.connect_button["state"]), "normal")

        self.app.transport.set("RTU")
        self.app.controls[0][0].event_generate("<<ComboboxSelected>>")
        self.root.update()
        self.assertEqual(self.app.rtu_frame.winfo_manager(), "grid")
        self.assertEqual(self.app.tcp_frame.winfo_manager(), "")
        self.app.transport.set("TCP")
        self.app.controls[0][0].event_generate("<<ComboboxSelected>>")
        self.root.update()
        self.assertEqual(self.app.tcp_frame.winfo_manager(), "grid")
        self.assertEqual(self.app.rtu_frame.winfo_manager(), "")
        self.assertEqual(self.simulator.requests, [])

    def test_connect_read_disconnect_and_device_error(self):
        self.connect()
        self.assertEqual(str(self.app.read_button["state"]), "normal")

        self.app.object_type.set("Holding registers")
        self.app.address.set("0")
        self.app.count.set("2")
        self.app.read_button.invoke()
        self.wait_for(lambda: not self.app.busy)
        self.assertEqual(
            self.app.results.item(self.app.results.get_children()[0], "values"),
            ("Holding registers", "0", "17"),
        )
        self.assertEqual(
            self.app.results.item(self.app.results.get_children()[1], "values"),
            ("Holding registers", "1", "65535"),
        )
        self.assertIn("Live device read", self.app.source.get())

        self.simulator.forced_exception = 2
        self.app.read_button.invoke()
        self.wait_for(lambda: not self.app.busy)
        self.assertIn("Read failed", self.app.status.get())
        self.messagebox.showerror.assert_called()
        self.simulator.forced_exception = None

        self.app.disconnect_button.invoke()
        self.wait_for(lambda: not self.app.busy)
        self.assertFalse(self.app.connected)
        self.assertEqual(str(self.app.read_button["state"]), "disabled")
        request_count = len(self.simulator.requests)
        self.app.read_button.invoke()
        self.root.update()
        self.assertEqual(len(self.simulator.requests), request_count)

    def test_local_csv_import_export_never_touches_device(self):
        directory = Path(__file__).parent / (".desktop-test-" + uuid.uuid4().hex)
        directory.mkdir()
        self.addCleanup(shutil.rmtree, directory)
        imported = directory / "import.csv"
        exported = directory / "export.csv"
        imported.write_text(
            "object_type,address,value\nHolding registers,0,42\n",
            encoding="utf-8",
        )
        with patch("m31tool.app.filedialog.askopenfilename", return_value=str(imported)):
            self.app.import_button.invoke()
        self.root.update()
        self.assertIn("LOCAL CSV", self.app.source.get())
        self.assertEqual(len(self.app.results.get_children()), 1)
        self.assertEqual(self.simulator.requests, [])

        with patch("m31tool.app.filedialog.asksaveasfilename", return_value=str(exported)):
            self.app.export_button.invoke()
        self.root.update()
        self.assertEqual(
            exported.read_text(encoding="utf-8").splitlines(),
            ["object_type,address,value", "Holding registers,0,42"],
        )
        self.assertEqual(self.simulator.requests, [])

    def test_confirmed_write_is_read_back_and_cancelled_write_sends_nothing(self):
        self.connect()
        self.app.write_type.set("Holding registers")
        self.app.write_address.set("0")
        self.app.write_value.set("4242")

        self.messagebox.askyesno.return_value = True
        self.app.write_button.invoke()
        self.wait_for(lambda: not self.app.busy)
        self.assertEqual(self.simulator.holding_registers[0], 4242)
        self.assertEqual(
            self.simulator.requests[-2:],
            [(1, b"\x06\x00\x00\x10\x92"), (1, b"\x03\x00\x00\x00\x01")],
        )
        self.assertIn("Write verified", self.app.status.get())
        self.assertIn("read-back", self.app.source.get())

        request_count = len(self.simulator.requests)
        self.messagebox.askyesno.return_value = False
        self.app.write_value.set("1234")
        self.app.write_button.invoke()
        self.root.update()
        self.messagebox.askyesno.assert_called()
        self.assertEqual(len(self.simulator.requests), request_count)
        self.assertEqual(self.simulator.holding_registers[0], 4242)


if __name__ == "__main__":
    unittest.main()
