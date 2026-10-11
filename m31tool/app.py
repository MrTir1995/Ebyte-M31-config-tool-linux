"""Tkinter desktop interface for safe, explicit Modbus operations."""

from __future__ import annotations

import csv
import queue
import threading

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ModuleNotFoundError as exc:
    if exc.name not in ("tkinter", "_tkinter"):
        raise
    tk = None
    filedialog = messagebox = ttk = None

from m31tool.core import M31_REGISTERS, ModbusSession, RegisterKind, RegisterSpec
from m31tool.device import (
    DEVICE_MANUAL_SOURCE, DEVICE_REGISTER_CATALOG, negotiate_addresses, read_device_info,
)
from m31tool.discovery import (
    DeviceTarget, discover_rtu, discover_tcp, parse_hosts, parse_unit_ids,
)
from m31tool.formats import (
    PROFILE_FIELDS, decode_float32, load_profile, load_xlsx, save_profile, save_xlsx,
    parse_float32_write,
)


OBJECT_TYPES = (
    "Coils",
    "Discrete inputs",
    "Holding registers",
    "Input registers",
)
READ_METHODS = (
    "read_coils",
    "read_discrete_inputs",
    "read_holding_registers",
    "read_input_registers",
)
CSV_FIELDS = ("object_type", "address", "value")
INTERPRETATIONS = ("Raw unsigned 16-bit", "IEEE754 float32")
WRITE_ENCODINGS = ("Raw unsigned values", "IEEE754 float32")
TK_REQUIREMENT = (
    "Tkinter is unavailable. Install your Linux distribution's Tkinter package "
    "(Debian/Ubuntu: sudo apt install python3-tk; Fedora: sudo dnf install "
    "python3-tkinter), then use a Python interpreter with Tk support."
)
CATALOG_TYPES = {
    RegisterKind.COILS: "Coils",
    RegisterKind.DISCRETE_INPUTS: "Discrete inputs",
    RegisterKind.HOLDING_REGISTERS: "Holding registers",
    RegisterKind.INPUT_REGISTERS: "Input registers",
}


def _integer(text: str, name: str, minimum: int, maximum: int) -> int:
    try:
        value = int(text.strip(), 16 if text.strip().lower().startswith("0x") else 10)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer (decimal or 0x hexadecimal).") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def load_csv(path) -> list[tuple[str, int, int]]:
    """Validate and load local display data without touching a device."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(CSV_FIELDS):
            raise ValueError("CSV header must be exactly: object_type,address,value")
        for line, row in enumerate(reader, 2):
            if len(rows) >= 100_000:
                raise ValueError("CSV exceeds the 100,000-row local import limit.")
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV line {line} has missing or extra columns.")
            kind = row["object_type"].strip()
            if kind not in OBJECT_TYPES:
                raise ValueError(f"CSV line {line}: unknown object type {kind!r}.")
            address = _integer(row["address"], f"Line {line} address", 0, 65535)
            value = _integer(
                row["value"], f"Line {line} value", 0,
                1 if kind in OBJECT_TYPES[:2] else 65535,
            )
            rows.append((kind, address, value))
    return rows


def save_csv(path, rows) -> None:
    """Export displayed rows using the same schema as local imports."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_FIELDS)
        writer.writerows(rows)


def _confirm_write(root, text: str, count: int) -> bool:
    if count <= 32:
        return messagebox.askyesno(
            "Confirm device write", text, icon="warning", default="no", parent=root
        )
    dialog = tk.Toplevel(root)
    dialog.title("Confirm device write — review every value")
    dialog.transient(root)
    dialog.geometry("750x500")
    result = False

    def finish(confirmed=False):
        nonlocal result
        result = confirmed
        dialog.destroy()

    frame = ttk.Frame(dialog, padding=12)
    frame.pack(fill="both", expand=True)
    details = tk.Text(frame, wrap="word", width=80, height=20)
    scrollbar = ttk.Scrollbar(frame, command=details.yview)
    details.configure(yscrollcommand=scrollbar.set)
    details.insert("1.0", text)
    details.configure(state="disabled")
    details.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    buttons = ttk.Frame(dialog, padding=12)
    buttons.pack(fill="x")
    no = ttk.Button(buttons, text="No — cancel", command=finish)
    no.pack(side="right", padx=8)
    ttk.Button(
        buttons, text="Yes — write all values", command=lambda: finish(True)
    ).pack(side="right")
    dialog.protocol("WM_DELETE_WINDOW", finish)
    dialog.bind("<Escape>", lambda event: finish())
    dialog.bind("<Return>", lambda event: finish())
    dialog.grab_set()
    no.focus_set()
    root.wait_window(dialog)
    return result


class M31App(ttk.Frame if ttk is not None else object):
    """All device I/O runs in one worker at a time; Tk stays on the main thread."""

    def __init__(self, master: tk.Tk) -> None:
        if tk is None:
            raise RuntimeError(TK_REQUIREMENT)
        super().__init__(master, padding=12)
        self.root = master
        self.session = ModbusSession(unit_id=1, timeout=2.0)
        self.connected = False
        self.destination = ""
        self.busy = False
        self.closing = False
        self.close_started = False
        self.events: queue.Queue = queue.Queue()
        self.worker_thread = None
        self._poll_after = None
        self._focus_binding = None
        self._destroyed = False
        self.rows: list[tuple[str, int, int]] = []
        self.controls: list[tuple[ttk.Widget, str]] = []
        self.transport = tk.StringVar(value="TCP")
        self.host = tk.StringVar(value="")
        self.tcp_port = tk.StringVar(value="502")
        self.serial_port = tk.StringVar(value="/dev/ttyUSB0")
        self.baudrate = tk.StringVar(value="9600")
        self.parity = tk.StringVar(value="N")
        self.stopbits = tk.StringVar(value="1")
        self.unit_id = tk.StringVar(value="1")
        self.timeout = tk.StringVar(value="2.0")
        self.object_type = tk.StringVar(value=OBJECT_TYPES[2])
        self.address = tk.StringVar(value="0")
        self.count = tk.StringVar(value="1")
        self.auto_refresh = tk.BooleanVar(value=False)
        self.refresh_interval = tk.StringVar(value="1.0")
        self.auto_refresh_after = None
        self.write_type = tk.StringVar(value="Holding registers")
        self.write_address = tk.StringVar(value="0")
        self.write_value = tk.StringVar(value="0")
        self.write_encoding = tk.StringVar(value=WRITE_ENCODINGS[0])
        self.write_word_order = tk.StringVar(value="")
        self.interpretation = tk.StringVar(value=INTERPRETATIONS[0])
        self.word_order = tk.StringVar(value="big")
        self.decoded = tk.StringVar(value="Raw table/export is never converted.")
        self.status = tk.StringVar(value="Disconnected — no device operations performed.")
        self.connection_summary = tk.StringVar(value="Disconnected — choose a destination below.")
        self.catalog_detail = tk.StringVar(value="Select an entry to see its full description.")
        self.source = tk.StringVar(value="No reads displayed.")
        self.device_source = tk.StringVar(value="No device parameters/status read performed.")
        self.negotiation_result = tk.StringVar(value="No address negotiation requested.")
        self.device_targets = {}
        self.prepared_target_item = ""
        self.scan_cancel = None
        self.scan_hosts = tk.StringVar(value="")
        self.scan_units = tk.StringVar(value="1-247")
        self.scan_timeout = tk.StringVar(value="0.3")
        self.scan_status = tk.StringVar(value="No search performed. Device list is local to this window.")
        self.trace_source = tk.StringVar(value="No transport observations displayed. Refresh explicitly.")
        self.trace_rows = []
        self.pack(fill="both", expand=True)
        self._build()
        self._refresh_controls()
        self.root.protocol("WM_DELETE_WINDOW", self._request_close)
        self._poll_after = self.root.after(75, self._poll)

    def destroy(self) -> None:
        """Release owned Tk objects on Tk's thread, not later worker-thread GC."""
        if self._destroyed:
            return
        self._destroyed = True
        self._cancel_auto_refresh()
        if self._poll_after is not None:
            self.root.after_cancel(self._poll_after)
            self._poll_after = None
        if self._focus_binding is not None:
            self.root.unbind("<FocusIn>", self._focus_binding)
            self._focus_binding = None
        # Direct root/frame destruction must not orphan queued Tk callbacks.
        # Normal close already waits for I/O in _poll; this covers owner teardown.
        if self.worker_thread is not None:
            self.worker_thread.join()
            self.worker_thread = None
        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                break
        super().destroy()
        self.controls.clear()
        self.connection_controls.clear()
        self.discovery_controls.clear()
        for name, value in tuple(vars(self).items()):
            if isinstance(value, tk.Variable) or (
                isinstance(value, tk.Misc) and name not in ("master", "root")
            ):
                delattr(self, name)

    def _entry(self, parent, variable, width=14):
        widget = ttk.Entry(parent, textvariable=variable, width=width)
        self.controls.append((widget, "normal"))
        return widget

    def _combo(self, parent, variable, values, width=20):
        widget = ttk.Combobox(
            parent, textvariable=variable, values=values, state="readonly", width=width
        )
        self.controls.append((widget, "readonly"))
        return widget

    def _wrapped_label(self, parent, **options):
        label = ttk.Label(parent, anchor="w", justify="left", width=1, wraplength=760, **options)
        label.pack(fill="x", pady=(0, 8))
        label.bind(
            "<Configure>",
            lambda event: label.configure(wraplength=max(1, event.width)),
        )
        return label

    def _bind_action(self, widget, action):
        def invoke(event):
            action()
            return "break"
        widget.bind("<Return>", invoke)
        widget.bind("<KP_Enter>", invoke)

    def _build_viewport(self):
        viewport = ttk.Frame(self)
        viewport.pack(fill="both", expand=True)
        canvas = tk.Canvas(viewport, highlightthickness=0, background="#f4f5f7")
        vertical = ttk.Scrollbar(viewport, command=canvas.yview)
        horizontal = ttk.Scrollbar(viewport, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        viewport.rowconfigure(0, weight=1)
        viewport.columnconfigure(0, weight=1)
        body = ttk.Frame(canvas)
        window = canvas.create_window(0, 0, window=body, anchor="nw")

        def resize(event=None):
            # Native fonts/DPI can require more space than the minimum window.
            width = max(canvas.winfo_width(), body.winfo_reqwidth())
            height = max(canvas.winfo_height(), body.winfo_reqheight())
            canvas.itemconfigure(window, width=width, height=height)
            canvas.configure(scrollregion=(0, 0, width, height))
            if width > canvas.winfo_width():
                horizontal.grid(row=1, column=0, sticky="ew")
            else:
                horizontal.grid_remove()
                canvas.xview_moveto(0)
            if height > canvas.winfo_height():
                vertical.grid(row=0, column=1, sticky="ns")
            else:
                vertical.grid_remove()
                canvas.yview_moveto(0)

        body.bind("<Configure>", resize)
        canvas.bind("<Configure>", resize)
        self.content_canvas = canvas
        self.content_body = body
        self._focus_binding = self.root.bind("<FocusIn>", self._reveal_control, add="+")
        return viewport, body

    def _reveal_control(self, event):
        widget = event.widget
        parent = widget
        while parent is not self.content_body:
            parent = getattr(parent, "master", None)
            if parent is None:
                return
        if not widget.winfo_ismapped():
            return
        canvas = self.content_canvas
        for position, origin, size, viewport_size, content_size, view, move in (
            (widget.winfo_rootx(), canvas.winfo_rootx(), widget.winfo_width(), canvas.winfo_width(),
             self.content_body.winfo_width(), canvas.xview, canvas.xview_moveto),
            (widget.winfo_rooty(), canvas.winfo_rooty(), widget.winfo_height(), canvas.winfo_height(),
             self.content_body.winfo_height(), canvas.yview, canvas.yview_moveto),
        ):
            offset = position - origin
            if size <= viewport_size and (offset < 0 or offset + size > viewport_size):
                target = offset if offset < 0 else offset + size - viewport_size
                move(view()[0] + target / content_size)

    def _build(self) -> None:
        self.root.title("M31 Modbus Tool — Unofficial — Disconnected")
        self.root.minsize(850, 680)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font="TkDefaultFont", background="#f4f5f7", foreground="#202735")
        style.configure("TFrame", background="#f4f5f7")
        style.configure("TLabel", background="#f4f5f7", foreground="#202735")
        style.configure("Heading.TLabel", font="TkHeadingFont")
        style.configure("Warning.TLabel", foreground="#8b261d")
        style.configure("TButton", padding=(12, 7), focuscolor="#1659a5")
        style.map("TButton", foreground=[("disabled", "#596373")])
        style.configure("Primary.TButton", background="#1659a5", foreground="#ffffff",
                        focuscolor="#ffffff")
        style.map("Primary.TButton", background=[("disabled", "#e0e4ea"), ("active", "#10467f")],
                  foreground=[("disabled", "#596373"), ("!disabled", "#ffffff")])
        style.configure("Danger.TButton", background="#8b261d", foreground="#ffffff",
                        focuscolor="#ffffff")
        style.map("Danger.TButton", background=[("disabled", "#e0e4ea"), ("active", "#702017")],
                  foreground=[("disabled", "#596373"), ("!disabled", "#ffffff")])
        style.configure("TEntry", fieldbackground="#ffffff", foreground="#202735", padding=5)
        style.configure("TCombobox", fieldbackground="#ffffff", foreground="#202735", padding=5)
        style.map("TEntry", bordercolor=[("focus", "#1659a5")])
        style.map("TCombobox", fieldbackground=[("readonly", "#ffffff")],
                  foreground=[("disabled", "#596373"), ("readonly", "#202735")],
                  bordercolor=[("focus", "#1659a5")])
        style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff",
                        foreground="#202735", rowheight=28, font="TkDefaultFont")
        style.map("Treeview", background=[("selected", "#1659a5")],
                  foreground=[("selected", "#ffffff")], bordercolor=[("focus", "#1659a5")])
        style.configure("Treeview.Heading", font="TkHeadingFont", padding=(8, 6))
        style.configure("TNotebook.Tab", padding=(10, 7))
        style.map("TNotebook.Tab", foreground=[("selected", "#10467f")])
        viewport, body = self._build_viewport()
        ttk.Label(
            body, text="M31 Modbus Tool · Unofficial community client", style="Heading.TLabel"
        ).pack(anchor="w", pady=(0, 8))
        self._wrapped_label(
            body, text="Safety: writes can energize loads. Verify wiring, module addresses "
            "and analog ranges first.", style="Warning.TLabel",
        )
        self._wrapped_label(body, textvariable=self.connection_summary, style="Heading.TLabel")

        connection = ttk.LabelFrame(body, text="Connection", padding=12)
        connection.pack(fill="x")
        ttk.Label(connection, text="Transport").grid(row=0, column=0, sticky="w")
        selector = self._combo(connection, self.transport, ("TCP", "RTU"), 7)
        selector.grid(row=0, column=1, padx=5, sticky="w")
        selector.bind("<<ComboboxSelected>>", lambda event: self._show_transport())
        ttk.Label(connection, text="Unit ID").grid(row=0, column=2)
        unit_entry = self._entry(connection, self.unit_id, 6)
        unit_entry.grid(row=0, column=3, padx=5)
        ttk.Label(connection, text="Timeout (s)").grid(row=0, column=4)
        timeout_entry = self._entry(connection, self.timeout, 6)
        timeout_entry.grid(row=0, column=5, padx=5)
        connection.columnconfigure(6, weight=1)
        for entry in (unit_entry, timeout_entry):
            self._bind_action(entry, self._connect)
        self.connect_button = ttk.Button(
            connection, text="Connect", command=self._connect, style="Primary.TButton"
        )
        self.connect_button.grid(row=0, column=7, padx=5)
        self.disconnect_button = ttk.Button(
            connection, text="Disconnect", command=self._disconnect
        )
        self.disconnect_button.grid(row=0, column=8, padx=5)

        self.tcp_frame = ttk.Frame(connection)
        self.tcp_frame.grid(row=1, column=0, columnspan=9, sticky="w", pady=(8, 0))
        ttk.Label(self.tcp_frame, text="Host").pack(side="left")
        host_entry = self._entry(self.tcp_frame, self.host, 28)
        host_entry.pack(side="left", padx=5)
        ttk.Label(self.tcp_frame, text="Port").pack(side="left")
        port_entry = self._entry(self.tcp_frame, self.tcp_port, 7)
        port_entry.pack(side="left", padx=5)
        for entry in (host_entry, port_entry):
            self._bind_action(entry, self._connect)
        self.rtu_frame = ttk.Frame(connection)
        self.rtu_frame.grid(row=1, column=0, columnspan=9, sticky="w", pady=(8, 0))
        for label, variable, width in (
            ("Serial device", self.serial_port, 22),
            ("Baud", self.baudrate, 8),
        ):
            ttk.Label(self.rtu_frame, text=label).pack(side="left")
            entry = self._entry(self.rtu_frame, variable, width)
            entry.pack(side="left", padx=5)
            self._bind_action(entry, self._connect)
        ttk.Label(self.rtu_frame, text="Parity (8 data bits)").pack(side="left")
        self._combo(self.rtu_frame, self.parity, ("N", "E", "O"), 3).pack(
            side="left", padx=5
        )
        ttk.Label(self.rtu_frame, text="Stop bits").pack(side="left")
        self._combo(self.rtu_frame, self.stopbits, ("1", "2"), 3).pack(
            side="left", padx=5
        )
        self._show_transport()
        self.connection_controls = {widget for widget, _ in self.controls}
        notebook = ttk.Notebook(body)
        notebook.pack(fill="both", expand=True, pady=8)
        explorer = ttk.Frame(notebook, padding=8)
        catalog = ttk.Frame(notebook, padding=8)
        interpretation_tab = ttk.Frame(notebook, padding=8)
        device_tab = ttk.Frame(notebook, padding=8)
        write_tab = ttk.Frame(notebook, padding=12)
        files_tab = ttk.Frame(notebook, padding=12)
        notebook.add(explorer, text="Register explorer")
        notebook.add(catalog, text="M31 catalog")
        notebook.add(interpretation_tab, text="Interpretation")
        notebook.add(device_tab, text="Device status")
        notebook.add(write_tab, text="Device writes")
        notebook.add(files_tab, text="Local files")
        notebook.enable_traversal()
        self.notebook = notebook
        self.explorer = explorer
        devices_tab = ttk.Frame(notebook, padding=8)
        notebook.add(devices_tab, text="Device list")
        self._build_device_list(devices_tab)
        trace_tab = ttk.Frame(notebook, padding=8)
        notebook.add(trace_tab, text="Modbus trace")
        self._build_trace(trace_tab)

        read_bar = ttk.Frame(explorer)
        read_bar.pack(fill="x")
        self._combo(read_bar, self.object_type, OBJECT_TYPES).pack(side="left")
        ttk.Label(read_bar, text="Address").pack(side="left", padx=(8, 3))
        address_entry = self._entry(read_bar, self.address, 9)
        address_entry.pack(side="left")
        ttk.Label(read_bar, text="Count").pack(side="left", padx=(8, 3))
        count_entry = self._entry(read_bar, self.count, 6)
        count_entry.pack(side="left")
        for entry in (address_entry, count_entry):
            self._bind_action(entry, self._read)
        self.read_button = ttk.Button(
            read_bar, text="Read", command=self._read, style="Primary.TButton"
        )
        self.read_button.pack(side="left", padx=8)
        refresh_bar = ttk.Frame(explorer)
        refresh_bar.pack(fill="x", pady=(0, 8))
        self.auto_refresh_button = ttk.Checkbutton(
            refresh_bar, text="Auto-refresh read only", variable=self.auto_refresh,
            command=self._toggle_auto_refresh,
        )
        self.auto_refresh_button.pack(side="left", padx=(4, 0))
        self.controls.append((self.auto_refresh_button, "normal"))
        ttk.Label(refresh_bar, text="Every").pack(side="left", padx=(8, 3))
        self.refresh_interval_combo = self._combo(
            refresh_bar, self.refresh_interval,
            tuple(f"{tenths / 10:.1f}" for tenths in range(1, 51)), 5,
        )
        self.refresh_interval_combo.pack(side="left")
        self.refresh_interval_combo.bind(
            "<<ComboboxSelected>>", lambda event: self._schedule_auto_refresh()
        )
        ttk.Label(refresh_bar, text="s").pack(side="left", padx=(3, 0))
        self._wrapped_label(explorer, text="Zero-based protocol addresses · "
                            "Read only · Enter in Address or Count to read. Auto-refresh "
                            "polls this range and stops on errors.")
        self._wrapped_label(explorer, textvariable=self.source)

        self.results = self._tree(
            explorer, CSV_FIELDS, ("Object type", "Address", "Value"), horizontal=True
        )
        for column, width in zip(CSV_FIELDS, (280, 140, 180)):
            self.results.column(column, width=width, stretch=True)
        self.results.configure(height=6)
        self._wrapped_label(files_tab, text="Local files only. Imports replace the raw table; "
                            "they never write to a device. Exports keep raw values unchanged.")
        csv_bar = ttk.LabelFrame(files_tab, text="Raw table", padding=12)
        csv_bar.pack(fill="x", pady=(0, 12))
        self.export_button = ttk.Button(csv_bar, text="Export CSV", command=self._export_csv)
        self.export_button.pack(side="left")
        self.import_button = ttk.Button(
            csv_bar, text="Import CSV (local only)", command=self._import_csv
        )
        self.import_button.pack(side="left", padx=6)
        self.export_xlsx_button = ttk.Button(
            csv_bar, text="Export XLSX", command=self._export_xlsx
        )
        self.export_xlsx_button.pack(side="left", padx=6)
        self.import_xlsx_button = ttk.Button(
            csv_bar, text="Import XLSX (local only)", command=self._import_xlsx
        )
        self.import_xlsx_button.pack(side="left", padx=6)
        profile_bar = ttk.LabelFrame(files_tab, text="Client connection profile", padding=12)
        profile_bar.pack(fill="x", pady=(0, 12))
        self.save_profile_button = ttk.Button(
            profile_bar, text="Save client profile", command=self._save_profile
        )
        self.save_profile_button.pack(side="left")
        self.load_profile_button = ttk.Button(
            profile_bar, text="Load client profile", command=self._load_profile
        )
        self.load_profile_button.pack(side="left", padx=8)
        self._wrapped_label(files_tab, text="Profiles contain local connection settings, "
                            "not device configuration. Disconnect before loading a profile.")
        self._wrapped_label(files_tab, text="Firmware updates and proprietary UDP discovery "
                            "are not supported.")

        self._wrapped_label(write_tab, text="Danger: device writes can change outputs and "
                            "energize loads. Every write requires confirmation.",
                            style="Warning.TLabel")
        write_box = ttk.LabelFrame(write_tab, text="Explicit write + full read-back", padding=12)
        write_box.pack(fill="x", pady=(0, 12))
        write_box.columnconfigure(3, weight=1)
        self._combo(
            write_box, self.write_type, ("Coils", "Holding registers")
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(write_box, text="Address").grid(row=0, column=1, padx=(0, 6))
        self._entry(write_box, self.write_address, 9).grid(row=0, column=2)
        ttk.Label(write_box, text="Value encoding").grid(row=1, column=0, sticky="w", pady=(12, 0))
        self._combo(write_box, self.write_encoding, WRITE_ENCODINGS, 22).grid(
            row=1, column=1, columnspan=3, sticky="w", pady=(12, 0)
        )
        ttk.Label(write_box, text="Float word order").grid(row=2, column=0, sticky="w", pady=(12, 0))
        self._combo(write_box, self.write_word_order, ("big", "little"), 12).grid(
            row=2, column=1, columnspan=3, sticky="w", pady=(12, 0)
        )
        ttk.Label(write_box, text="Value(s)").grid(row=3, column=0, sticky="w", pady=(12, 0))
        self._entry(write_box, self.write_value, 22).grid(
            row=3, column=1, columnspan=3, sticky="w", pady=(12, 0)
        )
        self.write_button = ttk.Button(
            write_box, text="Confirm device write…", command=self._write, style="Danger.TButton"
        )
        self.write_button.grid(row=4, column=0, columnspan=4, sticky="e", pady=(12, 0))
        self._wrapped_label(
            write_tab,
            text="Comma-separated raw values: coils 0=OFF / 1=ON; registers 0–65535. "
            "Single: 05/06; multiple: 0F/10. Read-back verifies every stored value, "
            "not the physical load. Float input: holding registers only, two words per value; "
            "explicitly select the documented word order. Addresses, units and analog "
            "ranges are never inferred.",
        )

        self._wrapped_label(
            catalog,
            text="Select an entry, then press Enter or double-click to prepare a read (no I/O). "
            "Consult the exact module/firmware manual before writing.",
        )
        self._wrapped_label(catalog, textvariable=self.catalog_detail)
        self.catalog_tree = self._tree(
            catalog, ("name", "kind", "address", "description"),
            ("Name", "Object type", "Address", "Description"),
            horizontal=True,
        )
        self.catalog_tree.column("name", width=220)
        self.catalog_tree.column("description", width=480)
        self.catalog_tree.bind("<Double-1>", self._select_catalog)
        self._bind_action(self.catalog_tree, self._prepare_selected_catalog)
        self.catalog_tree.bind("<<TreeviewSelect>>", self._show_catalog_detail)
        self._populate_catalog()
        self._wrapped_label(
            device_tab,
            text="READ ONLY: documented M31 parameters/status, with raw register words. "
            "Reading does not change device configuration, negotiate transport, or "
            "apply settings to this client. Address negotiation below is a SEPARATE "
            "explicit device-changing action. Verify the exact model/firmware manual.",
        )
        self.device_read_button = ttk.Button(
            device_tab, text="Read device parameters/status", command=self._read_device_info,
            style="Primary.TButton",
        )
        self.device_read_button.pack(anchor="w")
        self.negotiate_button = ttk.Button(
            device_tab, text="Confirm address negotiation…", command=self._negotiate,
            style="Danger.TButton",
        )
        self.negotiate_button.pack(anchor="w", pady=(6, 0))
        self._wrapped_label(
            device_tab,
            text="Negotiation client timeout: 30 seconds (not a vendor completion promise); "
            "poll interval: 0.25 seconds. An in-flight request may additionally take the "
            "connection timeout. No automatic negotiation or configuration writes.",
        )
        self._wrapped_label(device_tab, textvariable=self.negotiation_result)
        self._wrapped_label(device_tab, textvariable=self.device_source)
        self.device_results = self._tree(
            device_tab, ("parameter", "address", "raw_words", "documented_value"),
            ("Parameter", "Address(es)", "Raw words (decimal / hex)", "Documented value"),
            horizontal=True,
        )
        self.device_results.column("parameter", width=190)
        self.device_results.configure(height=4)
        self.device_results.column("address", width=110)
        self.device_results.column("raw_words", width=330)
        self.device_results.column("documented_value", width=650)
        self._wrapped_label(interpretation_tab, textvariable=self.source)
        self._wrapped_label(
            interpretation_tab,
            text="Interpretation is local and optional. Each float uses two consecutive "
            "registers of the same object type. Choose the word order using the exact "
            "device manual; no M31 word order is assumed. Raw table and exports stay unchanged.",
        )
        display_bar = ttk.Frame(interpretation_tab)
        display_bar.pack(fill="x")
        for label, variable, values in (
            ("Interpretation", self.interpretation, INTERPRETATIONS),
            ("Word order", self.word_order, ("big", "little")),
        ):
            ttk.Label(display_bar, text=label).pack(side="left", padx=(0, 4))
            selector = self._combo(display_bar, variable, values, 22)
            selector.pack(side="left", padx=(0, 12))
            selector.bind("<<ComboboxSelected>>", lambda event: self._update_interpretation())
        self._wrapped_label(
            interpretation_tab,
            text="big = high word first; little = low word first (bytes within words unchanged).",
        )
        decoded_frame = ttk.Frame(interpretation_tab)
        decoded_frame.pack(fill="both", expand=True)
        decoded_frame.configure(width=1, height=64)
        decoded_frame.pack_propagate(False)
        self.decoded_view = tk.Text(
            decoded_frame, height=8, wrap="word", state="disabled", font="TkTextFont",
            background="#ffffff", foreground="#202735", highlightcolor="#1659a5",
            highlightthickness=2, relief="flat", padx=8, pady=8,
        )
        decoded_scroll = ttk.Scrollbar(decoded_frame, command=self.decoded_view.yview)
        self.decoded_view.configure(yscrollcommand=decoded_scroll.set)
        self.decoded_view.pack(side="left", fill="both", expand=True)
        decoded_scroll.pack(side="right", fill="y")
        self._update_interpretation()
        separator = ttk.Separator(self)
        separator.pack(fill="x", pady=4)
        self.progress = ttk.Progressbar(self, mode="indeterminate", takefocus=False)
        self.progress.pack(fill="x", pady=(0, 6))
        self.status_label = self._wrapped_label(self, textvariable=self.status)
        viewport.pack_forget()
        separator.pack_forget()
        self.progress.pack_forget()
        self.status_label.pack_configure(side="bottom")
        self.progress.pack(side="bottom", fill="x", pady=(0, 6))
        separator.pack(side="bottom", fill="x", pady=4)
        viewport.pack(fill="both", expand=True)

    def _tree(self, parent, columns, headings, horizontal=False):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        # Let data panes shrink; their column widths must not force the whole
        # notebook wider than the controls (the trees have their own scrollbars).
        frame.configure(width=1, height=88)
        frame.pack_propagate(False)
        frame.grid_propagate(False)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=10)
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
            tree.column(
                column, width=170 if column != "address" else 85,
                minwidth=60, stretch=not horizontal,
            )
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        if horizontal:
            horizontal_scrollbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
            tree.configure(xscrollcommand=horizontal_scrollbar.set)
            tree.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
        else:
            tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
        return tree

    def _build_trace(self, parent):
        self._wrapped_label(
            parent,
            text="Local pymodbus transport-hook observations, NOT a packet capture. "
            "TX attempt is observed before sending, not proof of delivery. "
            "RX buffer can contain partial or cumulative data, not one frame per row. "
            "No replay or arbitrary command sending.",
        )
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 8))
        self.trace_refresh_button = ttk.Button(
            toolbar, text="Refresh trace", command=self._refresh_trace
        )
        self.trace_refresh_button.pack(side="left")
        self.trace_copy_button = ttk.Button(
            toolbar, text="Copy displayed trace", command=self._copy_trace
        )
        self.trace_copy_button.pack(side="left", padx=8)
        self.trace_clear_button = ttk.Button(
            toolbar, text="Clear local trace", command=self._clear_trace
        )
        self.trace_clear_button.pack(side="left")
        self._wrapped_label(parent, textvariable=self.trace_source)
        self.trace_tree = self._tree(
            parent, ("sequence", "time", "transport", "target", "direction", "hex"),
            ("Sequence", "Monotonic seconds", "Transport", "Endpoint / unit", "Observation", "Hex bytes"),
            horizontal=True,
        )
        for column, width in (("sequence", 80), ("time", 150), ("transport", 90),
                              ("target", 260), ("direction", 120), ("hex", 600)):
            self.trace_tree.column(column, width=width)

    def _refresh_trace(self):
        if self.busy or self.closing:
            return
        records = self.session.trace_snapshot()
        self.trace_rows = [
            (str(record.sequence), f"{record.timestamp:.6f}", record.transport,
             f"{record.endpoint}, unit {record.unit_id}", record.direction,
             record.data.hex(" "))
            for record in records
        ]
        for item in self.trace_tree.get_children():
            self.trace_tree.delete(item)
        for row in self.trace_rows:
            self.trace_tree.insert("", "end", values=row)
        self.trace_source.set(
            f"Local snapshot: {len(records)} transport-hook observations; "
            f"{self.session.trace_dropped} older observations discarded by the bounded log. "
            "Refresh explicitly after operations. No physical capture/delivery proof."
        )
        self._refresh_controls()

    def _copy_trace(self):
        if self.busy or self.closing or not self.trace_rows:
            return
        text = (
            "M31Tool local pymodbus transport-hook observations (NOT packet capture).\n"
            "TX attempt: before sending; RX buffer: possibly partial/cumulative.\n"
            "Sequence\tMonotonic seconds\tTransport\tEndpoint / unit\tObservation\tHex bytes\n"
            + "\n".join("\t".join(row) for row in self.trace_rows)
        )
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except tk.TclError as exc:
            self._error("Copy transport trace", exc)
            return
        self.status.set(f"Copied {len(self.trace_rows)} displayed transport observations locally.")

    def _clear_trace(self):
        if self.busy or self.closing:
            return
        self.session.clear_trace()
        self._refresh_trace()
        self.status.set("Local transport trace cleared — no device operations.")

    def _populate_catalog(self) -> None:
        # Only existing non-U read definitions enter the operational catalog.
        # Research candidates and the separately implemented trigger stay inert.
        self.catalog_entries = tuple(M31_REGISTERS) + tuple(
            RegisterSpec(
                f"device_{entry.key}", entry.label, "holding_registers", entry.address,
                f"{DEVICE_MANUAL_SOURCE}; {entry.count} word(s). "
                f"{entry.decode_note} "
                + ("; ".join(f"{value}: {label}" for value, label in entry.enumerations)
                   if entry.enumerations else "No value/byte-order interpretation inferred.")
                + " Catalog selection prepares a read only; no configuration is applied.",
                words_per_value=entry.count,
            )
            for entry in DEVICE_REGISTER_CATALOG
        )
        for entry in self.catalog_entries:
            self.catalog_tree.insert(
                "", "end",
                values=(entry.label, CATALOG_TYPES[entry.kind], entry.address, entry.description),
            )

    def _select_catalog(self, event) -> None:
        item = self.catalog_tree.identify_row(event.y)
        self._prepare_catalog_item(item)

    def _prepare_selected_catalog(self) -> None:
        selected = self.catalog_tree.selection()
        if selected:
            self._prepare_catalog_item(selected[0])

    def _show_catalog_detail(self, event=None) -> None:
        selected = self.catalog_tree.selection()
        if selected:
            name, kind, address, description = self.catalog_tree.item(selected[0], "values")
            self.catalog_detail.set(f"{name} · {kind} · Address {address}\n{description}")

    def _prepare_catalog_item(self, item) -> None:
        if not item or self.busy or self.closing:
            return
        _, kind, address, _ = self.catalog_tree.item(item, "values")
        if kind not in OBJECT_TYPES:
            self._error("Catalog", ValueError(f"Unsupported catalog object type: {kind}"))
            return
        try:
            value = _integer(address, "Catalog address", 0, 65535)
        except ValueError as exc:
            self._error("Catalog", exc)
            return
        self.object_type.set(kind)
        self.address.set(str(value))
        entry = next(
            (entry for entry in self.catalog_entries
             if entry.address == value and CATALOG_TYPES[entry.kind] == kind
             and entry.label == self.catalog_tree.item(item, "values")[0]),
            None,
        )
        self.count.set(str(entry.words_per_value or 1) if entry else "1")
        self.notebook.select(self.explorer)

    def _show_transport(self) -> None:
        self.tcp_frame.grid_remove()
        self.rtu_frame.grid_remove()
        (self.tcp_frame if self.transport.get() == "TCP" else self.rtu_frame).grid()

    def _build_device_list(self, parent) -> None:
        self._wrapped_label(
            parent, text="READ ONLY search — explicit targets only; never automatic. "
            "The Unit ID addresses EVERY Modbus command, not just discovery. "
            "TCP unit aliases may refer to the same hardware; RTU devices need distinct IDs.",
        )
        self._wrapped_label(
            parent, text="TCP: enter hosts (comma-separated) or CIDR, using the connection port. "
            "RTU: uses the current serial settings. Maximum 256 hosts / 1,024 host×ID attempts. "
            "Narrow the unit range for larger networks. Disconnect before searching or selecting. "
            "No readable response does not prove a device is absent.",
        )
        first = len(self.controls)
        fields = ttk.Frame(parent)
        fields.pack(fill="x", pady=(0, 6))
        ttk.Label(fields, text="TCP hosts / CIDR").grid(row=0, column=0, sticky="w")
        self._entry(fields, self.scan_hosts, 32).grid(row=0, column=1, sticky="ew", padx=5)
        fields.columnconfigure(1, weight=1)
        ttk.Label(fields, text="Unit IDs").grid(row=1, column=0, sticky="w")
        self._entry(fields, self.scan_units, 20).grid(row=1, column=1, sticky="w", padx=5)
        ttk.Label(fields, text="Probe timeout (s)").grid(row=1, column=2, padx=5)
        self._entry(fields, self.scan_timeout, 6).grid(row=1, column=3)
        self.discovery_controls = {widget for widget, _ in self.controls[first:]}
        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(0, 6))
        self.search_button = ttk.Button(
            buttons, text="Search devices", command=self._search_devices, style="Primary.TButton",
        )
        self.search_button.pack(side="left")
        self.cancel_search_button = ttk.Button(
            buttons, text="Cancel search", command=self._cancel_search,
        )
        self.cancel_search_button.pack(side="left", padx=5)
        self.add_target_button = ttk.Button(
            buttons, text="Add current target (unverified)", command=self._add_current_target,
        )
        self.add_target_button.pack(side="left")
        self._wrapped_label(parent, textvariable=self.scan_status)
        self.device_tree = self._tree(
            parent, ("endpoint", "unit", "verification"),
            ("Endpoint / serial settings", "Unit ID", "Detection"), horizontal=True,
        )
        self.device_tree.configure(height=4, selectmode="browse")
        for column, width in (("endpoint", 400), ("unit", 80), ("verification", 150)):
            self.device_tree.column(column, width=width)
        self.device_tree.bind("<<TreeviewSelect>>", self._select_device_target)
        self.device_tree.bind(
            "<Button-1>",
            lambda event: "break" if self.connected or self.busy or self.closing else None,
        )
        self._bind_action(self.device_tree, self._select_device_target)

    def _remember_device_target(self, target, verified=False) -> None:
        for item, previous in self.device_targets.items():
            if previous == target:
                if verified:
                    self.device_tree.set(item, "verification", "Found (read response)")
                return
        if target.transport.lower() == "tcp":
            endpoint = f"TCP {target.host}:{target.port}"
        else:
            endpoint = (
                f"RTU {target.serial_port}, {target.baudrate} "
                f"8{target.parity}{target.stopbits}"
            )
        item = self.device_tree.insert(
            "", "end", values=(
                endpoint, target.unit_id,
                "Found (read response)" if verified else "Unverified (manual)",
            ),
        )
        self.device_targets[item] = target

    def _select_device_target(self, event=None) -> None:
        if self.connected or self.busy or self.closing:
            selected = self.device_tree.selection()
            prepared = getattr(self, "prepared_target_item", "")
            expected = (prepared,) if prepared else ()
            if selected != expected:
                if prepared:
                    self.device_tree.selection_set(prepared)
                elif selected:
                    self.device_tree.selection_remove(*selected)
            return
        selected = self.device_tree.selection()
        if not selected:
            return
        target = self.device_targets[selected[0]]
        self.prepared_target_item = selected[0]
        self.transport.set(target.transport.upper())
        self.unit_id.set(str(target.unit_id))
        if target.transport.lower() == "tcp":
            self.host.set(target.host)
            self.tcp_port.set(str(target.port))
        else:
            self.serial_port.set(target.serial_port)
            self.baudrate.set(str(target.baudrate))
            self.parity.set(target.parity)
            self.stopbits.set(str(target.stopbits))
        self.destination = ""
        self._show_transport()
        self._refresh_controls()
        self.status.set("Target prepared locally — press Connect. No device I/O performed.")

    def _add_current_target(self) -> None:
        if self.connected or self.busy or self.closing:
            return
        try:
            unit = _integer(self.unit_id.get(), "Unit ID", 1, 247)
            if self.transport.get() == "TCP":
                host = self.host.get().strip()
                if not host:
                    raise ValueError("TCP host is required.")
                target = DeviceTarget(
                    transport="tcp", host=host,
                    port=_integer(self.tcp_port.get(), "TCP port", 1, 65535), unit_id=unit,
                )
            else:
                port = self.serial_port.get().strip()
                if not port:
                    raise ValueError("Serial device is required.")
                target = DeviceTarget(
                    transport="rtu", serial_port=port, unit_id=unit,
                    baudrate=_integer(self.baudrate.get(), "Baud rate", 1, 4_000_000),
                    parity=self.parity.get(), stopbits=int(self.stopbits.get()),
                )
            self._remember_device_target(target)
        except (ValueError, OverflowError) as exc:
            self._error("Add target", exc)
            return
        self.scan_status.set("Added unverified target locally. No device I/O performed.")

    def _search_devices(self) -> None:
        if self.connected or self.busy or self.closing:
            return
        try:
            units = parse_unit_ids(self.scan_units.get())
            timeout = float(self.scan_timeout.get())
            if not 0 < timeout <= 2:
                raise ValueError("Probe timeout must be greater than zero and at most 2 seconds.")
            if self.transport.get() == "TCP":
                hosts = parse_hosts(self.scan_hosts.get())
                if len(hosts) * len(units) > 1024:
                    raise ValueError("Search exceeds 1,024 attempts. Narrow the hosts or unit range.")
                port = _integer(self.tcp_port.get(), "TCP port", 1, 65535)
                kwargs = dict(port=port, timeout=timeout)
                discover, args = discover_tcp, (hosts, units)
            else:
                port = self.serial_port.get().strip()
                if not port:
                    raise ValueError("Serial device is required.")
                kwargs = dict(
                    baudrate=_integer(self.baudrate.get(), "Baud rate", 1, 4_000_000),
                    parity=self.parity.get(), stopbits=int(self.stopbits.get()), timeout=timeout,
                )
                discover, args = discover_rtu, (port, units)
        except (ValueError, OverflowError) as exc:
            self._error("Search devices", exc)
            return
        self.scan_cancel = threading.Event()
        kwargs["cancel_event"] = self.scan_cancel
        self.scan_status.set("Searching read-only… Cancel keeps partial results. No writes performed.")
        self._run("Search devices", lambda: discover(*args, **kwargs), self._discovery_complete)

    def _cancel_search(self) -> None:
        if self.scan_cancel is not None:
            self.scan_cancel.set()
            self.scan_status.set("Cancelling after the current probe — partial results will be kept.")

    def _discovery_complete(self, result) -> None:
        self.scan_cancel = None
        for target in result.devices:
            self._remember_device_target(target, verified=True)
        state = "Cancelled (partial results kept)" if result.cancelled else "Completed"
        summary = (
            f"{state}: {len(result.devices)} responding targets, "
            f"{result.attempted} attempts, {len(result.errors)} errors. No writes performed."
        )
        self.scan_status.set(summary)
        self.status.set(summary)
        if result.errors:
            details = "\n".join(
                f"{error.target.transport} "
                f"{error.target.host or error.target.serial_port}, "
                f"unit {error.target.unit_id}: {error.operation}: {error.message}"
                for error in result.errors[:10]
            )
            if len(result.errors) > 10:
                details += f"\n… {len(result.errors) - 10} further probe errors."
            messagebox.showwarning("Search devices — probe errors", details, parent=self.root)

    def _refresh_controls(self) -> None:
        blocked = self.busy or self.closing
        if self.connected:
            summary = f"Connected — {self.destination or 'device'}"
        elif self.destination:
            summary = f"Disconnected — last destination: {self.destination}"
        else:
            summary = "Disconnected — choose a destination below."
        self.connection_summary.set(summary)
        self.root.title(f"M31 Modbus Tool — Unofficial — {summary}")
        self.root.configure(cursor="watch" if blocked else "")
        if self.busy:
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(value=0)
        for widget, state in self.controls:
            disabled = blocked or (
                self.connected and widget in self.connection_controls | self.discovery_controls
            )
            widget.configure(state="disabled" if disabled else state)
        self.connect_button.configure(state="disabled" if blocked or self.connected else "normal")
        self.disconnect_button.configure(state="disabled" if blocked or not self.connected else "normal")
        for button in (
            self.read_button, self.write_button, self.device_read_button, self.negotiate_button,
        ):
            button.configure(state="normal" if self.connected and not blocked else "disabled")
        self.auto_refresh_button.configure(
            state="normal" if self.connected and not blocked else "disabled"
        )
        self.refresh_interval_combo.configure(
            state="readonly" if self.connected and not blocked else "disabled"
        )
        self.import_button.configure(state="disabled" if blocked else "normal")
        self.export_button.configure(state="normal" if self.rows and not blocked else "disabled")
        self.import_xlsx_button.configure(state="disabled" if blocked else "normal")
        self.export_xlsx_button.configure(state="normal" if self.rows and not blocked else "disabled")
        self.save_profile_button.configure(state="disabled" if blocked else "normal")
        self.load_profile_button.configure(
            state="disabled" if blocked or self.connected else "normal"
        )
        for button in (self.search_button, self.add_target_button):
            button.configure(state="disabled" if blocked or self.connected else "normal")
        self.cancel_search_button.configure(
            state="normal" if self.scan_cancel is not None and self.busy else "disabled"
        )
        self.device_tree.state(["disabled"] if blocked or self.connected else ["!disabled"])
        self.trace_refresh_button.configure(state="disabled" if blocked else "normal")
        self.trace_clear_button.configure(state="disabled" if blocked else "normal")
        self.trace_copy_button.configure(
            state="normal" if self.trace_rows and not blocked else "disabled"
        )

    def _error(self, title: str, error: Exception) -> None:
        detail = f"{type(error).__name__}: {error}"
        if title == "Search devices":
            self.scan_cancel = None
            self.scan_status.set(f"Search FAILED — existing targets kept. {detail}")
        if title == "Read device parameters/status":
            self.device_source.set(
                "Device read FAILED — any displayed snapshot is unchanged, not refreshed."
            )
        if title == "Address negotiation":
            self.negotiation_result.set(
                f"Negotiation FAILED; device addresses/state may have changed. {detail}\n"
                "No rollback or retry performed. Check topology and explicitly read "
                "device parameters/status to refresh."
            )
        self.status.set(f"{title} failed — {detail}")
        messagebox.showerror(title, detail, parent=self.root)

    def _run(self, label, operation, success) -> None:
        if self.busy:
            return
        self._cancel_auto_refresh()
        self.busy = True
        self.status.set(f"{label}…")
        self._refresh_controls()

        def worker():
            result, error = None, None
            try:
                result = operation()
            except Exception as exc:
                error = exc
                # Tracebacks retain this worker frame and its Tk-owning closures.
                # Keep the exception/chain for reporting, but not those frames:
                # a later worker's cyclic GC must never finalize an old Tk root.
                pending = [error]
                seen = set()
                while pending:
                    failure = pending.pop()
                    if id(failure) in seen:
                        continue
                    seen.add(id(failure))
                    failure.__traceback__ = None
                    pending.extend(
                        linked for linked in (failure.__cause__, failure.__context__)
                        if linked is not None
                    )
            self.events.put((label, result, error, bool(self.session.connected), success))

        self.worker_thread = threading.Thread(
            target=worker, name="m31-device-io", daemon=True,
        )
        self.worker_thread.start()

    def _poll(self) -> None:
        self._poll_after = None
        if self._destroyed:
            return
        try:
            label, result, error, connected, success = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            # The event is the worker's final statement; join its short cleanup
            # tail before a callback can destroy Tk or release the last owner.
            if self.worker_thread is not None:
                self.worker_thread.join()
                self.worker_thread = None
            self.busy = False
            self.connected = connected
            self._refresh_controls()
            if self.close_started:
                if error is not None:
                    self._error(label, error)
                self.root.destroy()
                return
            if error is not None:
                if label == "Auto refresh":
                    self.auto_refresh.set(False)
                    self._cancel_auto_refresh()
                self._error(label, error)
            else:
                try:
                    success(result)
                except Exception as exc:
                    if label == "Auto refresh":
                        self.auto_refresh.set(False)
                        self._cancel_auto_refresh()
                    self._error(label, exc)
            self._refresh_controls()
            self._schedule_auto_refresh()
            if self.closing:
                self._finish_close()
        if not self._destroyed:
            self._poll_after = self.root.after(75, self._poll)

    def _connect(self) -> None:
        if self.busy or self.connected or self.closing:
            return
        try:
            unit = _integer(self.unit_id.get(), "Unit ID", 1, 247)
            timeout = float(self.timeout.get())
            if not 0 < timeout <= 60:
                raise ValueError("Timeout must be greater than zero and at most 60 seconds.")
            transport = self.transport.get()
            if transport == "TCP":
                host = self.host.get().strip()
                if not host:
                    raise ValueError("TCP host is required.")
                port = _integer(self.tcp_port.get(), "TCP port", 1, 65535)
                destination = f"TCP {host}:{port}, unit {unit}"
            else:
                port = self.serial_port.get().strip()
                if not port:
                    raise ValueError("Serial device is required.")
                baud = _integer(self.baudrate.get(), "Baud rate", 1, 4_000_000)
                parity, stopbits = self.parity.get(), int(self.stopbits.get())
                destination = f"RTU {port}, {baud} 8{parity}{stopbits}, unit {unit}"
        except (ValueError, OverflowError) as exc:
            self._error("Connection settings", exc)
            return

        def operation():
            self.session.close()
            self.session = ModbusSession(unit_id=unit, timeout=timeout)
            if transport == "TCP":
                self.session.open_tcp(host, port=port)
            else:
                self.session.open_rtu(port, baudrate=baud, parity=parity, stopbits=stopbits)
            if not self.session.connected:
                raise ConnectionError("Backend did not establish a connection.")

        def success(_):
            self.destination = destination
            self.status.set(f"Connected — {destination}")

        self.destination = destination
        self._run("Connect", operation, success)

    def _disconnect(self) -> None:
        if not self.busy and not self.closing:
            self.auto_refresh.set(False)
            self._cancel_auto_refresh()
            self._run("Disconnect", self.session.close, lambda _: self.status.set("Disconnected."))

    def _display(self, rows, source) -> None:
        self.rows = list(rows)
        for item in self.results.get_children():
            self.results.delete(item)
        for row in self.rows:
            self.results.insert("", "end", values=row)
        self.source.set(source)
        self._update_interpretation()
        self._refresh_controls()

    def _update_interpretation(self) -> None:
        lines = ["Raw table/export is never converted."]
        if self.interpretation.get() == INTERPRETATIONS[1]:
            order = self.word_order.get()
            lines = [f"IEEE754 float32 — explicitly selected {order} word order:"]
            index = 0
            while index < len(self.rows):
                kind, address, value = self.rows[index]
                if kind not in OBJECT_TYPES[2:]:
                    lines.append(f"{kind} {address}: not a register; no float interpretation.")
                    index += 1
                    continue
                if (index + 1 < len(self.rows)
                        and self.rows[index + 1][:2] == (kind, address + 1)):
                    next_value = self.rows[index + 1][2]
                    result = decode_float32([value, next_value], word_order=order)
                    lines.append(
                        f"{kind} {address}–{address + 1}: {result!r} "
                        f"(raw {value}, {next_value})"
                    )
                    index += 2
                else:
                    lines.append(f"{kind} {address}: missing consecutive word; not decoded.")
                    index += 1
            if not self.rows:
                lines.append("No raw values displayed.")
        self.decoded.set("\n".join(lines))
        self.decoded_view.configure(state="normal")
        self.decoded_view.delete("1.0", "end")
        self.decoded_view.insert("1.0", self.decoded.get())
        self.decoded_view.configure(state="disabled")

    def _cancel_auto_refresh(self) -> None:
        if self.auto_refresh_after is not None:
            self.root.after_cancel(self.auto_refresh_after)
            self.auto_refresh_after = None

    def _schedule_auto_refresh(self) -> None:
        self._cancel_auto_refresh()
        if not self.auto_refresh.get() or not self.connected or self.busy or self.closing:
            return
        try:
            interval = float(self.refresh_interval.get())
            if not 0.1 <= interval <= 5.0:
                raise ValueError("Auto-refresh interval must be between 0.1 and 5 seconds.")
        except ValueError as exc:
            self.auto_refresh.set(False)
            self._error("Auto-refresh settings", exc)
            return
        self.auto_refresh_after = self.root.after(int(interval * 1000), self._auto_refresh)

    def _auto_refresh(self) -> None:
        self.auto_refresh_after = None
        if not self.auto_refresh.get() or not self.connected or self.busy or self.closing:
            return
        self._read(automatic=True)

    def _toggle_auto_refresh(self) -> None:
        if self.auto_refresh.get():
            if not self.connected or self.busy or self.closing:
                self.auto_refresh.set(False)
                return
            self._schedule_auto_refresh()
            if self.auto_refresh.get():
                self.status.set("Auto-refresh enabled — selected range only; read-only.")
        else:
            self._cancel_auto_refresh()
            self.status.set("Auto-refresh disabled.")

    def _read(self, *, automatic: bool = False) -> None:
        if not self.connected or self.busy or self.closing:
            return
        try:
            kind = self.object_type.get()
            index = OBJECT_TYPES.index(kind)
            address = _integer(self.address.get(), "Address", 0, 65535)
            count = _integer(self.count.get(), "Count", 1, 2000 if index < 2 else 125)
            if address + count > 65536:
                raise ValueError("Read range exceeds address 65535.")
        except ValueError as exc:
            if automatic:
                self.auto_refresh.set(False)
                self._cancel_auto_refresh()
            self._error("Read settings", exc)
            return

        def operation():
            values = list(getattr(self.session, READ_METHODS[index])(address, count))
            if len(values) != count:
                raise ValueError(f"Expected {count} values, received {len(values)}.")
            return [(kind, address + offset, int(value)) for offset, value in enumerate(values)]

        def success(rows):
            self._display(rows, "Live device read (raw values).")
            if automatic:
                self.source.set("Auto-refresh read (raw values; no device writes).")
                self.status.set(f"Auto-refresh complete — {count} {kind.lower()} at {address}.")
            else:
                self.status.set(f"Read complete — {count} {kind.lower()} at {address}.")

        self._run("Auto refresh" if automatic else "Read", operation, success)

    def _read_device_info(self) -> None:
        if not self.connected or self.busy or self.closing:
            return
        destination = self.destination
        self.device_source.set(
            f"Reading parameters/status from {destination} — prior snapshot not yet refreshed."
        )

        def operation():
            return read_device_info(self.session)

        def success(info):
            rows = []
            for field in info["fields"]:
                end = field["address"] + field["count"] - 1
                address = f"0x{field['address']:04X}"
                if field["count"] > 1:
                    address += f"–0x{end:04X}"
                raw = ", ".join(map(str, field["raw_words"])) + f" / {field['raw_hex']}"
                decoded = field["decoded"]
                note = field["decode_note"]
                value = f"{decoded} — {note}" if decoded is not None else f"Raw only — {note}"
                rows.append((field["label"], address, raw, value))
            for item in self.device_results.get_children():
                self.device_results.delete(item)
            for row in rows:
                self.device_results.insert("", "end", values=row)
            self.device_source.set(
                f"READ-ONLY snapshot: {destination}\nDocumentation: {info['source']}"
            )
            self.status.set(
                f"Device parameters/status read complete — {len(rows)} named fields; no writes."
            )

        self._run("Read device parameters/status", operation, success)

    def _negotiate(self) -> None:
        if not self.connected or self.busy or self.closing:
            return
        if not messagebox.askyesno(
            "Confirm address negotiation — device-changing action",
            f"Device: {self.destination}\n\n"
            "This explicitly unlocks negotiation (holding register 0x7584 = 1) and "
            "triggers it (0x7585 = 1). Expansion-module addresses may change and "
            "communication may be interrupted. Verify the manufacturer's supported "
            "hardware topology, module order, wiring and firmware first.\n\n"
            "The client polls status with a 30-second deadline and 0.25-second interval; "
            "this is a client limit, NOT a vendor completion promise. A timeout or error "
            "does NOT undo either write. An in-flight request may additionally take "
            "the configured connection timeout. Device state may already have changed.\n\n"
            "No automatic retry, rollback or client-setting change follows. Use the "
            "explicit Read device parameters/status button to refresh afterwards.\n\n"
            "Start address negotiation?",
            icon="warning", default="no", parent=self.root,
        ):
            return
        self.negotiation_result.set(
            "Address negotiation requested — device state may change; waiting for status."
        )
        self.device_source.set(
            "Device-changing negotiation requested — any parameters/status snapshot is stale. "
            "Explicitly read to refresh afterwards."
        )

        def operation():
            return negotiate_addresses(self.session, timeout=30.0, poll_interval=0.25)

        def success(result):
            outcome = "completed without reported exception" if result["success"] else (
                "completed with a reported exception — check the device"
            )
            exception_label = result["exception_label"] or "Unknown exception code"
            self.negotiation_result.set(
                f"Negotiation {outcome}.\n"
                f"Status: {result['status']} (0x{result['status']:04X}) — "
                f"{result['status_label']}; exception: {result['exception']} "
                f"(0x{result['exception']:04X}) — {exception_label}.\n"
                f"Expansion bitmap, raw only: {result['bitmap_raw_words']} / "
                f"{result['bitmap_raw_hex']}.\n"
                "Device addresses/state may have changed. Explicitly Read device "
                "parameters/status to refresh; no automatic retry or rollback."
            )
            self.status.set(
                f"Address negotiation {outcome}; raw result displayed. Explicit refresh required."
            )

        self._run("Address negotiation", operation, success)

    def _write(self) -> None:
        if not self.connected or self.busy or self.closing:
            return
        try:
            kind = self.write_type.get()
            if kind not in ("Coils", "Holding registers"):
                raise ValueError("Only coils and holding registers can be written.")
            address = _integer(self.write_address.get(), "Write address", 0, 65535)
            encoding = self.write_encoding.get()
            encoding_note = ""
            if encoding == WRITE_ENCODINGS[1]:
                if kind != "Holding registers":
                    raise ValueError("Float values can only be written to holding registers.")
                order = self.write_word_order.get()
                values = parse_float32_write(self.write_value.get(), order)
                encoding_note = (
                    f"IEEE754 float32 input(s): {self.write_value.get()}\n"
                    f"Explicit word order: {order}; two registers per float.\n"
                    "Channel addresses, engineering units and ranges are NOT inferred.\n"
                )
            elif encoding == WRITE_ENCODINGS[0]:
                texts = self.write_value.get().split(",")
                limit = 1968 if kind == "Coils" else 123
                if len(texts) > limit:
                    raise ValueError(f"At most {limit} values may be written at once.")
                values = [
                    _integer(text, f"Write value {offset + 1}", 0,
                             1 if kind == "Coils" else 65535)
                    for offset, text in enumerate(texts)
                ]
            else:
                raise ValueError("Select a supported write encoding.")
            count = len(values)
            end_address = address + count - 1
            if end_address > 65535:
                raise ValueError("Write range exceeds address 65535.")
        except ValueError as exc:
            self._error("Write settings", exc)
            return
        function_code = (
            ("05" if kind == "Coils" else "06") if count == 1
            else ("0F" if kind == "Coils" else "10")
        )
        if not _confirm_write(
            self.root,
            f"Device: {self.destination}\n"
            f"Write {kind}, zero-based addresses {address}–{end_address}, "
            f"{count} raw value(s)?\n"
            f"Function code: {function_code}.\n\n"
            f"{encoding_note}"
            "This can change outputs and energize relay loads. Verify wiring, module "
            "address mapping, and analog ranges first.\n\n"
            "A mandatory read-back follows. A failure does NOT undo a write.\n\n"
            f"Complete raw values, in ascending address order:\n{', '.join(map(str, values))}",
            count,
        ):
            return

        def operation():
            try:
                if kind == "Coils":
                    if count == 1:
                        self.session.write_coil(address, bool(values[0]))
                    else:
                        self.session.write_coils(address, [bool(value) for value in values])
                    actual = list(self.session.read_coils(address, count))
                else:
                    if count == 1:
                        self.session.write_register(address, values[0])
                    else:
                        self.session.write_registers(address, values)
                    actual = list(self.session.read_holding_registers(address, count))
                if len(actual) != count or [int(value) for value in actual] != values:
                    raise ValueError(f"Read-back mismatch: requested {values}, received {actual!r}.")
            except Exception as exc:
                raise RuntimeError(
                    f"Write could have taken effect; verification failed. No rollback was "
                    f"attempted. Check the device before retrying. {type(exc).__name__}: {exc}"
                ) from exc
            return [(kind, address + offset, int(value)) for offset, value in enumerate(actual)]

        def success(rows):
            self._display(rows, "Live device read-back after confirmed write.")
            self.status.set(f"Write verified — {count} {kind.lower()} at {address}–{end_address}.")

        self._run("Write and read-back", operation, success)

    def _export_csv(self) -> None:
        if not self.rows or self.busy or self.closing:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Export displayed values", defaultextension=".csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*")),
        )
        if not path:
            return
        try:
            save_csv(path, self.rows)
        except (OSError, csv.Error) as exc:
            self._error("CSV export", exc)
            return
        self.status.set(f"Exported {len(self.rows)} displayed values to {path}.")

    def _import_csv(self) -> None:
        if self.busy or self.closing:
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Import CSV locally — no device writes",
            filetypes=(("CSV files", "*.csv"), ("All files", "*")),
        )
        if not path:
            return
        try:
            rows = load_csv(path)
        except (OSError, UnicodeError, csv.Error, ValueError) as exc:
            self._error("CSV import", exc)
            return
        self._display(rows, f"LOCAL CSV data — NOT a device read: {path}")
        self.status.set(f"Imported {len(rows)} rows locally. No device I/O performed.")

    def _export_xlsx(self) -> None:
        if not self.rows or self.busy or self.closing:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Export raw displayed values",
            defaultextension=".xlsx", filetypes=(("Excel workbooks", "*.xlsx"),),
        )
        if not path:
            return
        try:
            save_xlsx(path, self.rows)
        except Exception as exc:
            self._error("XLSX export", exc)
            return
        self.status.set(f"Exported {len(self.rows)} raw displayed values to {path}.")

    def _import_xlsx(self) -> None:
        if self.busy or self.closing:
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Import XLSX locally — no device writes",
            filetypes=(("Excel workbooks", "*.xlsx"),),
        )
        if not path:
            return
        try:
            rows = load_xlsx(path)
        except Exception as exc:
            self._error("XLSX import", exc)
            return
        self._display(rows, f"LOCAL XLSX data — NOT a device read: {path}")
        self.status.set(f"Imported {len(rows)} rows locally. No device I/O performed.")

    def _save_profile(self) -> None:
        if self.busy or self.closing:
            return
        try:
            settings = {name: getattr(self, name).get() for name in PROFILE_FIELDS}
            for name, minimum, maximum in (
                ("tcp_port", 1, 65535), ("baudrate", 1, 4_000_000),
                ("stopbits", 1, 2), ("unit_id", 1, 247),
                ("address", 0, 65535), ("count", 1, 2000),
            ):
                settings[name] = _integer(settings[name], name, minimum, maximum)
            settings["timeout"] = float(settings["timeout"])
        except (ValueError, OverflowError) as exc:
            self._error("Client profile", exc)
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Save local client profile — not device configuration",
            defaultextension=".json", filetypes=(("M31Tool client profiles", "*.json"),),
        )
        if not path:
            return
        try:
            save_profile(path, settings)
        except Exception as exc:
            self._error("Client profile save", exc)
            return
        self.status.set(f"Saved local client profile to {path}. No device I/O performed.")

    def _load_profile(self) -> None:
        if self.busy or self.connected or self.closing:
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Load local client profile — disconnected only",
            filetypes=(("M31Tool client profiles", "*.json"),),
        )
        if not path:
            return
        try:
            settings = load_profile(path)
        except Exception as exc:
            self._error("Client profile load", exc)
            return
        for name in PROFILE_FIELDS:
            getattr(self, name).set(str(settings[name]))
        self.destination = ""
        self._show_transport()
        self._update_interpretation()
        self._refresh_controls()
        self.status.set(f"Loaded local client profile from {path}. Still disconnected; no device I/O.")

    def _request_close(self) -> None:
        if self.closing:
            return
        self.closing = True
        self.auto_refresh.set(False)
        self._cancel_auto_refresh()
        if self.scan_cancel is not None:
            self.scan_cancel.set()
        self._refresh_controls()
        if self.busy:
            self.status.set("Closing — waiting for the current operation to finish safely…")
        else:
            self._finish_close()

    def _finish_close(self) -> None:
        self.close_started = True
        self._run("Close connection", self.session.close, lambda _: None)


def main() -> int:
    """Launch the desktop application; importing this module performs no writes."""
    if tk is None:
        raise SystemExit(TK_REQUIREMENT)
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise SystemExit(f"Cannot open the Tk desktop window: {exc}. "
                         "Run from a graphical Linux desktop with a working display.") from exc
    M31App(root)
    root.mainloop()
    return 0
