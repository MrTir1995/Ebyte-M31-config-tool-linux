"""Callback observations only; TCP tests use an independent loopback peer.

RTU tests mock construction and never claim physical serial capture.
"""

from dataclasses import FrozenInstanceError, fields
import struct
import threading
import unittest
from unittest.mock import ANY, Mock, patch

from m31tool.core import (
    ModbusConnectionError,
    ModbusResponseError,
    ModbusSession,
    TransportTraceRecord,
)
from tests.modbus_simulator import running_simulator


class TransportTraceTests(unittest.TestCase):
    def setUp(self):
        self.session = ModbusSession(unit_id=7, timeout=0.2)
        self.addCleanup(self.session.close)

    def open_mock(self, transport="TCP"):
        name = "ModbusTcpClient" if transport == "TCP" else "ModbusSerialClient"
        with patch(f"m31tool.core.{name}") as factory:
            client = factory.return_value
            client.connect.return_value = True
            client.connected = True
            if transport == "TCP":
                self.session.open_tcp(" localhost ", 1502)
                factory.assert_called_once_with(
                    "localhost", port=1502, timeout=0.2, retries=0,
                    trace_packet=ANY,
                )
            else:
                self.session.open_rtu(" test-port ", 19200, "e", 2)
                factory.assert_called_once_with(
                    "test-port", baudrate=19200, bytesize=8, parity="E",
                    stopbits=2, timeout=0.2, retries=0, trace_packet=ANY,
                )
            return client, factory.call_args.kwargs["trace_packet"]

    def test_contract_and_empty_local_construction(self):
        self.assertEqual(
            [field.name for field in fields(TransportTraceRecord)],
            ["sequence", "timestamp", "direction", "transport", "endpoint",
             "unit_id", "data"],
        )
        self.assertEqual(self.session.trace_snapshot(), ())
        self.assertEqual(self.session.trace_dropped, 0)
        self.session.clear_trace()
        with self.assertRaises(ModbusConnectionError):
            self.session.read_holding_registers(0, 1)
        self.assertEqual(self.session.trace_snapshot(), ())

    def test_both_constructor_hooks_preserve_identity_and_metadata_without_io(self):
        for transport, endpoint in (("TCP", "localhost:1502"), ("RTU", "test-port")):
            with self.subTest(transport=transport):
                self.session.clear_trace()
                client, hook = self.open_mock(transport)
                self.assertEqual(self.session.trace_snapshot(), ())
                before = list(client.mock_calls)
                tx = bytes.fromhex("010300000001840a")
                rx = bytes.fromhex("0103020011")
                with patch("m31tool.core.monotonic", side_effect=[10.0, 11.0]):
                    self.assertIs(hook(True, tx), tx)
                    self.assertIs(hook(False, rx), rx)
                records = self.session.trace_snapshot()
                self.assertIsInstance(records, tuple)
                self.assertEqual([r.direction for r in records], ["TX attempt", "RX buffer"])
                self.assertEqual([r.data for r in records], [tx, rx])
                self.assertEqual([r.timestamp for r in records], [10.0, 11.0])
                self.assertEqual(records[1].sequence, records[0].sequence + 1)
                for record in records:
                    self.assertEqual((record.transport, record.endpoint, record.unit_id),
                                     (transport, endpoint, 7))
                with self.assertRaises(FrozenInstanceError):
                    records[0].data = b"changed"
                self.assertEqual(client.mock_calls, before)

    def test_metadata_is_bound_before_constructor_and_not_relabelled_on_reopen(self):
        hooks = []

        def construct(*args, **kwargs):
            hook = kwargs["trace_packet"]
            hooks.append(hook)
            hook(True, b"constructor-observation")
            return Mock(connect=Mock(return_value=True), connected=True)

        with patch("m31tool.core.ModbusTcpClient", side_effect=construct):
            self.session.open_tcp("first", 1502)
            self.session.open_tcp("second", 1503)
        hooks[0](False, b"old-buffer")
        self.assertEqual(
            [r.endpoint for r in self.session.trace_snapshot()],
            ["first:1502", "second:1503", "first:1502"],
        )

    def test_mutable_callback_buffer_is_copied_but_returned_unchanged(self):
        _, hook = self.open_mock()
        data = bytearray(b"original")
        self.assertIs(hook(False, data), data)
        data[:] = b"modified"
        record = self.session.trace_snapshot()[0]
        self.assertIsInstance(record.data, bytes)
        self.assertEqual(record.data, b"original")

    def test_bounded_order_dropped_count_and_local_clear(self):
        client, hook = self.open_mock()
        for index in range(503):
            data = struct.pack(">H", index)
            self.assertIs(hook(bool(index % 2), data), data)
        snapshot = self.session.trace_snapshot()
        self.assertEqual(len(snapshot), 500)
        self.assertEqual([r.sequence for r in snapshot], list(range(4, 504)))
        self.assertEqual([r.data for r in snapshot],
                         [struct.pack(">H", i) for i in range(3, 503)])
        self.assertEqual(sorted(r.timestamp for r in snapshot),
                         [r.timestamp for r in snapshot])
        self.assertEqual(self.session.trace_dropped, 3)
        before = list(client.mock_calls)
        self.session.clear_trace()
        self.assertEqual(self.session.trace_snapshot(), ())
        self.assertEqual(self.session.trace_dropped, 0)
        self.assertEqual(client.mock_calls, before)
        hook(False, b"next")
        self.assertEqual(self.session.trace_snapshot()[0].sequence, 504)
        self.assertEqual(len(snapshot), 500)

    def test_callback_snapshot_and_clear_do_not_acquire_session_lock(self):
        _, hook = self.open_mock()
        done = threading.Event()

        def observe():
            hook(False, b"buffer")
            self.session.trace_snapshot()
            self.session.clear_trace()
            _ = self.session.trace_dropped
            done.set()

        with self.session._lock:
            thread = threading.Thread(target=observe, daemon=True)
            thread.start()
            completed_while_locked = done.wait(1)
        thread.join(1)
        self.assertTrue(completed_while_locked)
        self.assertFalse(thread.is_alive())

    def test_concurrent_callbacks_have_unique_ordered_sequences(self):
        _, hook = self.open_mock()
        threads = [
            threading.Thread(target=lambda: [hook(True, b"x") for _ in range(150)])
            for _ in range(4)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(2)
            self.assertFalse(thread.is_alive())
        self.assertEqual([r.sequence for r in self.session.trace_snapshot()],
                         list(range(101, 601)))
        self.assertEqual(self.session.trace_dropped, 100)

    def test_cumulative_and_malformed_buffers_are_not_rewritten_or_synthesized(self):
        client, hook = self.open_mock()
        buffers = [b"\x00", b"\x00\xff", b"\x00\xffbroken"]

        def request(**kwargs):
            for data in buffers:
                self.assertIs(hook(False, data), data)
            return Mock(function_code=3, registers=[-1], isError=Mock(return_value=False))

        client.read_holding_registers.side_effect = request
        with self.assertRaises(ModbusResponseError):
            self.session.read_holding_registers(0, 1)
        self.assertEqual([r.data for r in self.session.trace_snapshot()], buffers)
        self.assertTrue(all(r.direction == "RX buffer"
                            for r in self.session.trace_snapshot()))
        self.session.clear_trace()
        client.read_holding_registers.side_effect = OSError("send failed")
        with self.assertRaises(ModbusConnectionError):
            self.session.read_holding_registers(0, 1)
        self.assertEqual(self.session.trace_snapshot(), ())


class LoopbackTransportTraceTests(unittest.TestCase):
    def setUp(self):
        self.context = running_simulator()
        self.simulator = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        self.session = ModbusSession(timeout=0.1)
        self.addCleanup(self.session.close)
        self.session.open_tcp(*self.simulator.address)

    @staticmethod
    def adu(transaction, pdu):
        return struct.pack(">HHHB", transaction, 0, len(pdu) + 1, 1) + pdu

    def assert_exchange(self, transaction, request, response):
        records = self.session.trace_snapshot()
        self.assertEqual(records[0].direction, "TX attempt")
        self.assertEqual(records[0].data, self.adu(transaction, request))
        expected = self.adu(transaction, response)
        # Receive hooks may expose accumulating parser buffers.
        self.assertGreaterEqual(len(records), 2)
        for record in records[1:]:
            self.assertEqual(record.direction, "RX buffer")
            self.assertTrue(expected.startswith(record.data))
        self.assertEqual(records[-1].data, expected)
        for record in records:
            self.assertEqual(record.transport, "TCP")
            self.assertEqual(record.endpoint, "%s:%s" % self.simulator.address)
            self.assertEqual(record.unit_id, 1)

    def test_exact_fc03_fc06_fc16_and_explicit_readback_observations(self):
        self.assertEqual(self.session.trace_snapshot(), ())
        self.assertEqual(self.simulator.requests, [])
        exchanges = (
            (lambda: self.session.read_holding_registers(0, 2), [17, 65535],
             bytes.fromhex("0300000002"), bytes.fromhex("03040011ffff")),
            (lambda: self.session.write_register(0, 1234), None,
             bytes.fromhex("06000004d2"), bytes.fromhex("06000004d2")),
            (lambda: self.session.read_holding_registers(0, 1), [1234],
             bytes.fromhex("0300000001"), bytes.fromhex("030204d2")),
            (lambda: self.session.write_registers(0, [10, 65535]), None,
             bytes.fromhex("100000000204000affff"), bytes.fromhex("1000000002")),
            (lambda: self.session.read_holding_registers(0, 2), [10, 65535],
             bytes.fromhex("0300000002"), bytes.fromhex("0304000affff")),
        )
        for transaction, (operation, result, request, response) in enumerate(exchanges, 1):
            with self.subTest(transaction=transaction):
                self.session.clear_trace()
                self.assertEqual(operation(), result)
                self.assert_exchange(transaction, request, response)
                self.assertEqual(self.simulator.requests[-1], (1, request))

    def test_device_exception_and_truncated_response_remain_errors(self):
        self.simulator.forced_exception = 4
        with self.assertRaises(ModbusResponseError):
            self.session.read_holding_registers(0, 2)
        self.assert_exchange(1, bytes.fromhex("0300000002"), bytes.fromhex("8304"))
        self.session.clear_trace()
        self.simulator.forced_exception = None
        self.simulator.short_register_response = True
        with self.assertRaises(ModbusResponseError):
            self.session.read_holding_registers(0, 2)
        self.assert_exchange(2, bytes.fromhex("0300000002"), bytes.fromhex("03020011"))

    def test_timeout_records_only_one_tx_attempt_and_no_synthetic_rx(self):
        self.simulator.silent = True
        with self.assertRaises(ModbusConnectionError):
            self.session.write_register(0, 42)
        records = self.session.trace_snapshot()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].direction, "TX attempt")
        self.assertEqual(records[0].data, self.adu(1, bytes.fromhex("060000002a")))
        self.assertEqual(len(self.simulator.requests), 1)

    def test_tx_callback_does_not_prove_successful_send(self):
        with patch.object(self.session._client.transaction, "low_level_send",
                          side_effect=OSError("send failed")) as send:
            with self.assertRaises(ModbusConnectionError):
                self.session.write_register(0, 42)
        send.assert_called_once()
        records = self.session.trace_snapshot()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].direction, "TX attempt")
        self.assertEqual(records[0].data, self.adu(1, bytes.fromhex("060000002a")))
        self.assertEqual(self.simulator.requests, [])


if __name__ == "__main__":
    unittest.main()
