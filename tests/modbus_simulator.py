"""Small independent Modbus TCP peer; never connects to physical equipment."""

from contextlib import contextmanager
import socketserver
import struct
import threading


class _Handler(socketserver.BaseRequestHandler):
    def _receive(self, length):
        data = bytearray()
        while len(data) < length:
            chunk = self.request.recv(length - len(data))
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)

    def handle(self):
        self.request.settimeout(2)
        try:
            while True:
                header = self._receive(7)
                if header is None:
                    return
                transaction, protocol, length, unit = struct.unpack(">HHHB", header)
                if protocol != 0 or not 2 <= length <= 254:
                    return
                pdu = self._receive(length - 1)
                if pdu is None:
                    return
                response = self.server.reply(unit, pdu)
                if self.server.silent:
                    self.server.stop_event.wait(2)
                    return
                if response is None:
                    return
                self.request.sendall(
                    struct.pack(">HHHB", transaction, 0, len(response) + 1, unit)
                    + response
                )
        except (TimeoutError, ConnectionError, OSError):
            return


class ModbusSimulator(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.coils = {0: False, 1: True, 2: True, 3: False}
        self.discrete_inputs = {0: True, 1: False, 2: True, 3: True}
        self.holding_registers = {
            0: 17, 1: 65535, 2: 23, 500: 1200, 3489: 0, 3490: 8, 3491: 8,
        }
        self.input_registers = {0: 321, 1: 654, 1000: 2500, 3000: 7000}
        self.requests = []
        self.ignore_writes = False
        self.disconnect = False
        self.forced_exception = None
        self.bad_write_echo = False
        self.bad_write_count = False
        self.short_register_response = False
        self.silent = False
        self.stop_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def address(self):
        return self.server_address

    def reply(self, unit, pdu):
        with self._lock:
            self.requests.append((unit, bytes(pdu)))
            if self.disconnect:
                return None
            function = pdu[0]
            if self.forced_exception is not None:
                return bytes((function | 0x80, self.forced_exception))
            if unit != 1:
                return bytes((function | 0x80, 11))
            if function in (1, 2, 3, 4):
                if len(pdu) != 5:
                    return bytes((function | 0x80, 3))
                address, value = struct.unpack(">HH", pdu[1:])
                table = {
                    1: self.coils,
                    2: self.discrete_inputs,
                    3: self.holding_registers,
                    4: self.input_registers,
                }[function]
                maximum = 2000 if function in (1, 2) else 125
                if not 1 <= value <= maximum:
                    return bytes((function | 0x80, 3))
                if any(index not in table for index in range(address, address + value)):
                    return bytes((function | 0x80, 2))
                values = [table[index] for index in range(address, address + value)]
                if function in (1, 2):
                    data = bytearray((value + 7) // 8)
                    for index, enabled in enumerate(values):
                        if enabled:
                            data[index // 8] |= 1 << (index % 8)
                    data = bytes(data)
                else:
                    if self.short_register_response:
                        values = values[:1]
                    data = struct.pack(">" + "H" * len(values), *values)
                return bytes((function, len(data))) + data
            if function in (5, 6):
                if len(pdu) != 5:
                    return bytes((function | 0x80, 3))
                address, value = struct.unpack(">HH", pdu[1:])
                table = self.coils if function == 5 else self.holding_registers
                if address not in table:
                    return bytes((function | 0x80, 2))
                if function == 5 and value not in (0, 0xFF00):
                    return bytes((function | 0x80, 3))
                if not self.ignore_writes:
                    table[address] = bool(value) if function == 5 else value
                if self.bad_write_echo:
                    return bytes((function,)) + struct.pack(">HH", address + 1, value)
                return pdu
            if function in (15, 16):
                if len(pdu) < 6:
                    return bytes((function | 0x80, 3))
                address, count, byte_count = struct.unpack(">HHB", pdu[1:6])
                expected_bytes = (count + 7) // 8 if function == 15 else count * 2
                maximum = 1968 if function == 15 else 123
                if (not 1 <= count <= maximum or byte_count != expected_bytes
                        or len(pdu) != 6 + byte_count):
                    return bytes((function | 0x80, 3))
                table = self.coils if function == 15 else self.holding_registers
                addresses = range(address, address + count)
                if any(index not in table for index in addresses):
                    return bytes((function | 0x80, 2))
                payload = pdu[6:]
                if function == 15:
                    values = [
                        bool(payload[index // 8] & (1 << (index % 8)))
                        for index in range(count)
                    ]
                else:
                    values = list(struct.unpack(">" + "H" * count, payload))
                if not self.ignore_writes:
                    for index, value in zip(range(address, address + count), values):
                        table[index] = value
                ack_address = address + 1 if self.bad_write_echo else address
                ack_count = count - 1 if self.bad_write_count else count
                return bytes((function,)) + struct.pack(">HH", ack_address, ack_count)
            return bytes((function | 0x80, 1))


@contextmanager
def running_simulator():
    server = ModbusSimulator()
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield server
    finally:
        server.stop_event.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if thread.is_alive():
            raise RuntimeError("Simulator thread did not shut down")
