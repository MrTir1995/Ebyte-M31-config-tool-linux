import struct
import unittest
from unittest.mock import Mock, patch

from m31tool.core import (
    M31_REGISTERS,
    ModbusConnectionError,
    ModbusResponseError,
    ModbusSession,
    RegisterKind,
)

from tests.modbus_simulator import running_simulator


class CoreTCPTests(unittest.TestCase):
    def setUp(self):
        self.simulator_context = running_simulator()
        self.simulator = self.simulator_context.__enter__()
        self.addCleanup(self.simulator_context.__exit__, None, None, None)
        self.session = ModbusSession(unit_id=1, timeout=0.2)
        self.addCleanup(self.session.close)
        self.session.open_tcp(*self.simulator.address)

    def test_connection_and_close(self):
        self.assertTrue(self.session.connected)
        self.session.close()
        self.assertFalse(self.session.connected)
        self.session.close()

    def test_connection_performs_no_device_operations(self):
        self.assertEqual(self.simulator.requests, [])

    def test_host_di_request_matches_standard_tcp_frame(self):
        packets = []

        def trace_packet(sending, data):
            packets.append((sending, data))
            return data

        self.session._client.transaction.trace_packet = trace_packet
        self.simulator.discrete_inputs.update({4: False, 5: True, 6: False, 7: True})
        self.assertEqual(
            self.session.read_discrete_inputs(0, 8),
            [True, False, True, True, False, True, False, True],
        )
        self.assertEqual(
            [data for sending, data in packets if sending],
            [bytes.fromhex("000100000006010200000008")],
        )

    def test_reads_coils_and_discrete_inputs_without_padding(self):
        self.assertEqual(self.session.read_coils(0, 4), [False, True, True, False])
        self.assertEqual(
            self.session.read_discrete_inputs(0, 4), [True, False, True, True]
        )

    def test_reads_holding_and_input_registers(self):
        self.assertEqual(self.session.read_holding_registers(0, 2), [17, 65535])
        self.assertEqual(self.session.read_input_registers(0, 2), [321, 654])

    def test_addresses_are_zero_based_and_not_rebased(self):
        for method, address, expected in (
            (self.session.read_input_registers, 1000, 2500),
            (self.session.read_input_registers, 3000, 7000),
            (self.session.read_holding_registers, 500, 1200),
            (self.session.read_holding_registers, 3490, 8),
        ):
            with self.subTest(address=address):
                self.assertEqual(method(address, 1), [expected])
                unit, pdu = self.simulator.requests[-1]
                self.assertEqual(unit, 1)
                self.assertEqual(struct.unpack(">HH", pdu[1:]), (address, 1))

    def test_read_only_operations_never_write(self):
        self.session.read_coils(0, 4)
        self.session.read_discrete_inputs(0, 4)
        self.session.read_holding_registers(0, 2)
        self.session.read_input_registers(0, 2)
        self.assertEqual([pdu[0] for _, pdu in self.simulator.requests], [1, 2, 3, 4])

    def test_coil_write_and_explicit_read_back(self):
        for value in (True, False):
            with self.subTest(value=value):
                self.session.write_coil(0, value)
                self.assertEqual(self.session.read_coils(0, 1), [value])
        writes = [pdu for _, pdu in self.simulator.requests if pdu[0] == 5]
        self.assertEqual(
            [struct.unpack(">HH", pdu[1:]) for pdu in writes], [(0, 0xFF00), (0, 0)]
        )

    def test_register_write_and_explicit_read_back(self):
        for value in (0, 1234, 65535):
            with self.subTest(value=value):
                self.session.write_register(0, value)
                self.assertEqual(self.session.read_holding_registers(0, 1), [value])
        self.assertEqual(self.simulator.holding_registers[1], 65535)

    def test_multiple_coil_write_and_explicit_read_back(self):
        values = [True, False, False, True]
        self.assertIsNone(self.session.write_coils(0, values))
        self.assertEqual(self.session.read_coils(0, len(values)), values)
        writes = [pdu for _, pdu in self.simulator.requests if pdu[0] == 15]
        self.assertEqual(len(writes), 1)
        self.assertEqual(struct.unpack(">HHB", writes[0][1:6]), (0, 4, 1))

    def test_multiple_register_write_and_explicit_read_back(self):
        values = [10, 0, 65535]
        self.assertIsNone(self.session.write_registers(0, values))
        self.assertEqual(self.session.read_holding_registers(0, len(values)), values)
        writes = [pdu for _, pdu in self.simulator.requests if pdu[0] == 16]
        self.assertEqual(len(writes), 1)
        self.assertEqual(struct.unpack(">HHB", writes[0][1:6]), (0, 3, 6))

    def test_multi_write_standard_limits_and_last_address(self):
        for method, read, table, values in (
            (self.session.write_coils, self.session.read_coils,
             self.simulator.coils, [index % 3 == 0 for index in range(1968)]),
            (self.session.write_registers, self.session.read_holding_registers,
             self.simulator.holding_registers, list(range(123))),
        ):
            with self.subTest(method=method.__name__):
                address = 65536 - len(values)
                table.update({address + index: 0 for index in range(len(values))})
                before = len(self.simulator.requests)
                self.assertIsNone(method(address, values))
                self.assertEqual(len(self.simulator.requests), before + 1)
                self.assertEqual(read(address, len(values)), values)
                self.assertIsNone(method(65535, [values[-1]]))
                self.assertEqual(read(65535, 1), [values[-1]])

    def test_multi_writes_validate_filter_registers_in_overlapping_ranges(self):
        self.session.write_registers(3489, [42, 8, 16])
        self.assertEqual(
            self.session.read_holding_registers(3489, 3), [42, 8, 16]
        )
        for address, values in ((3489, [42, 0]), (3490, [17, 42])):
            with self.subTest(address=address, values=values):
                before = len(self.simulator.requests)
                with self.assertRaises(ValueError):
                    self.session.write_registers(address, values)
                self.assertEqual(len(self.simulator.requests), before)

    def test_protocol_exception_is_not_reported_as_success(self):
        self.simulator.forced_exception = 4
        for operation in (
            lambda: self.session.read_coils(0, 1),
            lambda: self.session.read_discrete_inputs(0, 1),
            lambda: self.session.read_holding_registers(0, 1),
            lambda: self.session.read_input_registers(0, 1),
            lambda: self.session.write_coil(0, True),
            lambda: self.session.write_register(0, 42),
            lambda: self.session.write_coils(0, [True, False]),
            lambda: self.session.write_registers(0, [42, 43]),
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(ModbusResponseError):
                    operation()

    def test_unknown_address_is_not_reported_as_success(self):
        with self.assertRaises(ModbusResponseError):
            self.session.read_holding_registers(60000, 1)
        with self.assertRaises(ModbusResponseError):
            self.session.write_register(60000, 1)

    def test_disconnected_peer_is_not_reported_as_success(self):
        self.simulator.disconnect = True
        with self.assertRaises(ModbusConnectionError):
            self.session.read_input_registers(0, 1)

    def test_timeout_is_not_reported_as_success(self):
        self.simulator.silent = True
        with self.assertRaises(ModbusConnectionError):
            self.session.read_input_registers(0, 1)
        self.assertEqual(len(self.simulator.requests), 1)

    def test_short_register_response_is_rejected(self):
        self.simulator.short_register_response = True
        with self.assertRaises(ModbusResponseError):
            self.session.read_input_registers(0, 2)

    def test_closed_session_rejects_operations(self):
        self.session.close()
        with self.assertRaises(ModbusConnectionError):
            self.session.read_coils(0, 1)
        with self.assertRaises(ModbusConnectionError):
            self.session.write_register(0, 1)

    def test_reconnect(self):
        self.session.close()
        self.session.open_tcp(*self.simulator.address)
        self.assertEqual(self.session.read_input_registers(0, 1), [321])

    def test_invalid_read_arguments_are_rejected_before_io(self):
        for address, count in (
            (-1, 1), (65536, 1), (0, 0), (0, -1), (0, 126), (65535, 2)
        ):
            with self.subTest(address=address, count=count):
                before = len(self.simulator.requests)
                with self.assertRaises(ValueError):
                    self.session.read_holding_registers(address, count)
                self.assertEqual(len(self.simulator.requests), before)

    def test_invalid_register_values_are_rejected_before_io(self):
        for value in (-1, 65536):
            with self.subTest(value=value):
                before = len(self.simulator.requests)
                with self.assertRaises(ValueError):
                    self.session.write_register(0, value)
                self.assertEqual(len(self.simulator.requests), before)

    def test_invalid_multi_write_arguments_are_rejected_before_io(self):
        invalid_coil_writes = (
            (0, []), (0, [True, 1]), (0, (True, False)),
            (0, None), (0, [False, "True"]), (0, [False, 0.0]),
            (-1, [True]), (65536, [True]), (True, [True]),
            (0.0, [True]), (65535, [True, False]),
            (0, [False] * 1969),
        )
        invalid_register_writes = (
            (0, []), (0, [False]), (0, [1, True]), (0, [-1]),
            (0, [65536]), (0, [1, 0.0]), (0, [1, "2"]),
            (0, None), (0, (1, 2)), (-1, [1]), (65536, [1]),
            (True, [1]), (0.0, [1]),
            (65535, [1, 2]), (0, [1] * 124),
        )
        for method, writes in (
            (self.session.write_coils, invalid_coil_writes),
            (self.session.write_registers, invalid_register_writes),
        ):
            for address, values in writes:
                with self.subTest(method=method.__name__, values=values):
                    before = len(self.simulator.requests)
                    with self.assertRaises(ValueError):
                        method(address, values)
                    self.assertEqual(len(self.simulator.requests), before)

    def test_acknowledged_write_does_not_prove_applied_value(self):
        self.simulator.ignore_writes = True
        self.session.write_register(0, 42)
        self.assertEqual(self.session.read_holding_registers(0, 1), [17])
        self.session.write_coil(0, True)
        self.assertEqual(self.session.read_coils(0, 1), [False])

    def test_acknowledged_multi_write_requires_explicit_full_readback(self):
        self.simulator.ignore_writes = True
        for write, read, values, original in (
            (self.session.write_coils, self.session.read_coils,
             [True, False, False, True], [False, True, True, False]),
            (self.session.write_registers, self.session.read_holding_registers,
             [42, 43], [17, 65535]),
        ):
            with self.subTest(write=write.__name__):
                before = len(self.simulator.requests)
                self.assertIsNone(write(0, values))
                self.assertEqual(len(self.simulator.requests), before + 1)
                self.assertEqual(read(0, len(values)), original)

    def test_multi_writes_are_not_retried_after_disconnect_or_timeout(self):
        for failure in ("disconnect", "silent"):
            for method, values, function in (
                ("write_coils", [True, False], 15),
                ("write_registers", [42, 43], 16),
            ):
                with self.subTest(failure=failure, method=method):
                    with running_simulator() as simulator:
                        setattr(simulator, failure, True)
                        session = ModbusSession(timeout=0.1)
                        try:
                            session.open_tcp(*simulator.address)
                            with self.assertRaises(ModbusConnectionError):
                                getattr(session, method)(0, values)
                            self.assertEqual(
                                [pdu[0] for _, pdu in simulator.requests], [function]
                            )
                        finally:
                            session.close()

    def test_write_is_not_automatically_retried(self):
        self.simulator.disconnect = True
        with self.assertRaises(ModbusConnectionError):
            self.session.write_register(0, 42)
        writes = [pdu for _, pdu in self.simulator.requests if pdu[0] == 6]
        self.assertEqual(len(writes), 1)

    def test_wrong_write_acknowledgment_is_rejected(self):
        self.simulator.bad_write_echo = True
        for operation in (
            lambda: self.session.write_coil(0, True),
            lambda: self.session.write_register(0, 42),
            lambda: self.session.write_coils(0, [True, False]),
            lambda: self.session.write_registers(0, [42, 43]),
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(ModbusResponseError):
                    operation()

    def test_multi_write_wrong_acknowledged_count_is_rejected(self):
        self.simulator.bad_write_count = True
        for operation in (
            lambda: self.session.write_coils(0, [True, False]),
            lambda: self.session.write_registers(0, [42, 43]),
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(ModbusResponseError):
                    operation()

    def test_filter_range_validation_before_write(self):
        for address in (3490, 3491):
            for value in (0, 17):
                with self.subTest(address=address, value=value):
                    before = len(self.simulator.requests)
                    with self.assertRaises(ValueError):
                        self.session.write_register(address, value)
                    self.assertEqual(len(self.simulator.requests), before)
        for value in (1, 16):
            self.session.write_register(3490, value)
            self.assertEqual(self.session.read_holding_registers(3490, 1), [value])

    def test_invalid_coil_values_before_write(self):
        for value in (-1, 2, "1", None, 0.5):
            with self.subTest(value=value):
                before = len(self.simulator.requests)
                with self.assertRaises(ValueError):
                    self.session.write_coil(0, value)
                self.assertEqual(len(self.simulator.requests), before)

    def test_unit_id_is_transmitted(self):
        self.session.close()
        session = ModbusSession(unit_id=7, timeout=0.2)
        self.addCleanup(session.close)
        session.open_tcp(*self.simulator.address)
        with self.assertRaises(ModbusResponseError):
            session.read_input_registers(0, 1)
        self.assertEqual(self.simulator.requests[-1][0], 7)


class RegisterProfileTests(unittest.TestCase):
    def test_public_profile_exists(self):
        self.assertTrue(M31_REGISTERS)
        self.assertTrue(list(RegisterKind))

    def test_documented_register_addresses_and_kinds(self):
        observed = {spec.key: (spec.kind, spec.address) for spec in M31_REGISTERS}
        self.assertEqual(len(observed), len(M31_REGISTERS))
        expected = {
            "di": (RegisterKind.DISCRETE_INPUTS, 0),
            "do": (RegisterKind.COILS, 0),
            "ai_integer": (RegisterKind.INPUT_REGISTERS, 0),
            "ai_float": (RegisterKind.INPUT_REGISTERS, 1000),
            "ai_process": (RegisterKind.INPUT_REGISTERS, 3000),
            "ao_integer": (RegisterKind.HOLDING_REGISTERS, 0),
            "ao_float": (RegisterKind.HOLDING_REGISTERS, 1000),
            "ao_alternative": (RegisterKind.HOLDING_REGISTERS, 500),
            "di_filter": (RegisterKind.HOLDING_REGISTERS, 3491),
            "ai_filter": (RegisterKind.HOLDING_REGISTERS, 3490),
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(observed[key], value)
        for spec in M31_REGISTERS:
            if spec.key.endswith("_filter"):
                self.assertEqual((spec.min_value, spec.max_value), (1, 16))

    def test_invalid_session_parameters(self):
        for unit_id in (0, -1, 248):
            with self.subTest(unit_id=unit_id):
                with self.assertRaises(ValueError):
                    ModbusSession(unit_id=unit_id)
        for timeout in (0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    ModbusSession(timeout=timeout)


class RTUConfigurationTests(unittest.TestCase):
    """Validate serial transport configuration without opening /dev devices."""

    @patch("m31tool.core.ModbusSerialClient")
    def test_serial_configuration_and_explicit_read(self, factory):
        client = factory.return_value
        client.connect.return_value = True
        client.connected = True
        client.read_input_registers.return_value = Mock(
            function_code=4, registers=[123], isError=Mock(return_value=False)
        )
        session = ModbusSession(unit_id=3, timeout=0.2)
        self.addCleanup(session.close)
        session.open_rtu("unused-test-port", baudrate=19200, parity="E", stopbits=2)
        factory.assert_called_once_with(
            "unused-test-port", baudrate=19200, bytesize=8, parity="E",
            stopbits=2, timeout=0.2, retries=0,
        )
        client.write_coil.assert_not_called()
        client.write_register.assert_not_called()
        self.assertEqual(session.read_input_registers(0, 1), [123])
        client.read_input_registers.assert_called_once_with(
            address=0, count=1, device_id=3
        )

    @patch("m31tool.core.ModbusSerialClient")
    def test_serial_connect_failure_closes_client(self, factory):
        factory.return_value.connect.return_value = False
        session = ModbusSession()
        with self.assertRaises(ModbusConnectionError):
            session.open_rtu("unused-test-port")
        self.assertFalse(session.connected)
        factory.return_value.close.assert_called_once()

    @patch("m31tool.core.ModbusSerialClient")
    def test_invalid_serial_parameters_never_create_client(self, factory):
        session = ModbusSession()
        for kwargs in (
            {"port": ""},
            {"port": "unused-test-port", "baudrate": 0},
            {"port": "unused-test-port", "parity": "X"},
            {"port": "unused-test-port", "stopbits": 3},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    session.open_rtu(**kwargs)
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
