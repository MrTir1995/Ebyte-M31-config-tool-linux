import unittest
from unittest.mock import Mock

from m31tool.core import ModbusResponseError, ModbusSession
from m31tool.pump import (
    AI1_PROCESS_REGISTER,
    DO_PUMP,
    PumpController,
    pressure_from_process_value,
)
from tests.modbus_simulator import running_simulator


def process_value_for_pressure(pressure_bar):
    current_ma = 4 + pressure_bar * 16 / 10
    return round(current_ma * 27648 / 20)


class PressureConversionTests(unittest.TestCase):
    def test_converts_sensor_endpoints_and_control_pressures(self):
        self.assertAlmostEqual(pressure_from_process_value(5530), 0.0, places=3)
        self.assertAlmostEqual(
            pressure_from_process_value(process_value_for_pressure(1.6)), 1.6, places=3
        )
        self.assertAlmostEqual(pressure_from_process_value(27648), 10.0)

    def test_rejects_out_of_range_or_invalid_values(self):
        for value in (0, 5529, 27649, 32768, -1, 65536, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                pressure_from_process_value(value)


class PumpControllerTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.controller = PumpController(self.session)
        self.session.read_discrete_inputs.return_value = [True, False]
        self.session.read_input_registers.return_value = [process_value_for_pressure(2.0)]
        self.session.read_coils.return_value = [False]

    def test_uses_expected_m31_addresses_and_holds_between_thresholds(self):
        status = self.controller.scan()
        self.session.read_discrete_inputs.assert_called_once_with(0, 2)
        self.session.read_input_registers.assert_called_once_with(AI1_PROCESS_REGISTER, 1)
        self.session.read_coils.assert_called_once_with(DO_PUMP, 1)
        self.session.write_coil.assert_not_called()
        self.assertFalse(status.output_on)

    def test_starts_below_1_6_bar_and_verifies_output(self):
        self.session.read_input_registers.return_value = [process_value_for_pressure(1.5)]
        self.session.read_coils.side_effect = [[False], [True]]
        status = self.controller.scan()
        self.session.write_coil.assert_called_once_with(DO_PUMP, True)
        self.assertTrue(status.output_on)

    def test_stops_at_3_bar(self):
        self.session.read_input_registers.return_value = [process_value_for_pressure(3.0)]
        self.session.read_coils.side_effect = [[True], [False]]
        status = self.controller.scan()
        self.session.write_coil.assert_called_once_with(DO_PUMP, False)
        self.assertFalse(status.output_on)

    def test_uses_configured_thresholds_and_disables_automation(self):
        self.session.read_input_registers.return_value = [process_value_for_pressure(2.1)]
        self.session.read_coils.side_effect = [[False], [True]]
        status = self.controller.scan(start_pressure_bar=2.2, stop_pressure_bar=4.0)
        self.session.write_coil.assert_called_once_with(DO_PUMP, True)
        self.assertTrue(status.output_on)

        self.session.reset_mock()
        self.session.read_discrete_inputs.return_value = [True, False]
        self.session.read_input_registers.return_value = [process_value_for_pressure(1.5)]
        self.session.read_coils.side_effect = [[True], [False]]
        status = self.controller.scan(enabled=False)
        self.session.write_coil.assert_called_once_with(DO_PUMP, False)
        self.assertFalse(status.output_on)

    def test_rejects_invalid_pressure_thresholds(self):
        with self.assertRaises(ValueError):
            self.controller.scan(start_pressure_bar=3.0, stop_pressure_bar=3.0)

    def test_motor_fault_stops_pump_at_any_pressure(self):
        self.session.read_discrete_inputs.return_value = [False, True]
        self.session.read_coils.side_effect = [[True], [False]]
        status = self.controller.scan()
        self.session.write_coil.assert_called_once_with(DO_PUMP, False)
        self.assertTrue(status.motor_fault)
        self.assertTrue(status.running_feedback)

    def test_invalid_transmitter_value_stops_pump(self):
        self.session.read_input_registers.return_value = [0]
        self.session.read_coils.side_effect = [[True], [False]]
        status = self.controller.scan()
        self.session.write_coil.assert_called_once_with(DO_PUMP, False)
        self.assertFalse(status.sensor_valid)
        self.assertIsNone(status.pressure_bar)

    def test_failed_output_readback_is_reported(self):
        self.session.read_input_registers.return_value = [process_value_for_pressure(1.5)]
        self.session.read_coils.side_effect = [[False], [False]]
        with self.assertRaises(ModbusResponseError):
            self.controller.scan()


class PumpControllerSimulatorTests(unittest.TestCase):
    def test_controls_m31_registers_over_modbus_tcp(self):
        with running_simulator() as server:
            server.discrete_inputs[0] = True
            server.discrete_inputs[1] = False
            server.input_registers[AI1_PROCESS_REGISTER] = process_value_for_pressure(1.5)
            session = ModbusSession(timeout=0.5)
            try:
                session.open_tcp(*server.address)
                status = PumpController(session).scan()
                self.assertTrue(status.output_on)
                self.assertTrue(server.coils[DO_PUMP])
                self.assertEqual(
                    [request[1][0] for request in server.requests],
                    [2, 4, 1, 5, 1],
                )
            finally:
                session.close()


if __name__ == "__main__":
    unittest.main()
