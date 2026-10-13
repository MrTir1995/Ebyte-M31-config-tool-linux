import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from m31tool.homeassistant import HomeAssistantMqtt
from m31tool.pump import PumpSettings


class PumpSettingsTests(unittest.TestCase):
    def test_changes_are_validated_persisted_and_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            settings = PumpSettings(path=path)
            settings.set_pressure("start_pressure_bar", 2.1)
            settings.set_pressure("stop_pressure_bar", 4.2)
            settings.set_enabled(False)

            restored = PumpSettings(path=path)
            self.assertEqual(
                restored.snapshot(),
                settings.snapshot(),
            )
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {
                    "enabled": False,
                    "start_pressure_bar": 2.1,
                    "stop_pressure_bar": 4.2,
                },
            )

    def test_invalid_setting_does_not_change_current_values(self):
        settings = PumpSettings()
        for name, value in (
            ("start_pressure_bar", 3.0),
            ("stop_pressure_bar", 1.5),
            ("stop_pressure_bar", 10.1),
            ("start_pressure_bar", float("nan")),
            ("start_pressure_bar", 1.65),
        ):
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                settings.set_pressure(name, value)
        self.assertEqual(settings.snapshot().start_pressure_bar, 1.6)
        self.assertEqual(settings.snapshot().stop_pressure_bar, 3.0)


class HomeAssistantMqttTests(unittest.TestCase):
    def setUp(self):
        self.settings = PumpSettings()
        self.bridge = HomeAssistantMqtt(
            self.settings, host="127.0.0.1", port=1883, device_id="pump_test"
        )
        self.client = Mock()

    def command(self, suffix, payload):
        message = Mock(
            topic=f"m31_pump/pump_test/{suffix}/set",
            payload=payload,
        )
        self.bridge._on_message(self.client, None, message)

    def test_discovery_exposes_switch_and_both_pressure_numbers(self):
        configs = self.bridge._discovery_configs()
        self.assertEqual(
            set(configs),
            {
                "homeassistant/switch/pump_test/automation/config",
                "homeassistant/number/pump_test/pressure_start/config",
                "homeassistant/number/pump_test/pressure_stop/config",
            },
        )
        start = configs["homeassistant/number/pump_test/pressure_start/config"]
        stop = configs["homeassistant/number/pump_test/pressure_stop/config"]
        self.assertEqual((start["min"], start["max"], start["step"]), (0, 9.9, 0.1))
        self.assertEqual((stop["min"], stop["max"], stop["step"]), (0.1, 10, 0.1))
        self.assertEqual(start["unit_of_measurement"], "bar")
        self.assertEqual(start["availability_topic"], "m31_pump/pump_test/availability")

    def test_commands_change_and_republish_persisted_settings(self):
        self.command("automation", b"OFF")
        self.command("pressure_start", b"2.0")
        self.command("pressure_stop", b"4.0")
        current = self.settings.snapshot()
        self.assertFalse(current.enabled)
        self.assertEqual(current.start_pressure_bar, 2.0)
        self.assertEqual(current.stop_pressure_bar, 4.0)
        self.assertEqual(self.client.publish.call_count, 9)

    def test_invalid_commands_leave_settings_unchanged(self):
        self.command("pressure_start", b"3.0")
        self.command("automation", b"maybe")
        self.assertTrue(self.settings.snapshot().enabled)
        self.assertEqual(self.settings.snapshot().start_pressure_bar, 1.6)
        self.assertEqual(self.client.publish.call_count, 6)

    def test_connect_publishes_retained_discovery_and_subscribes_commands(self):
        self.bridge._on_connect(self.client, None, None, Mock(is_failure=False), None)
        self.assertEqual(self.client.publish.call_count, 7)
        self.assertTrue(all(call.kwargs["retain"] for call in self.client.publish.call_args_list))
        self.client.subscribe.assert_called_once_with(
            [
                ("m31_pump/pump_test/automation/set", 1),
                ("m31_pump/pump_test/pressure_start/set", 1),
                ("m31_pump/pump_test/pressure_stop/set", 1),
            ]
        )


if __name__ == "__main__":
    unittest.main()
