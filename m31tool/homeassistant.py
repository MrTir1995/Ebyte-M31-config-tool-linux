"""Home Assistant MQTT Discovery for the M31 pump controller."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

import paho.mqtt.client as mqtt

if TYPE_CHECKING:
    from m31tool.pump import PumpSettings


LOGGER = logging.getLogger("m31tool.pump.mqtt")
_DEVICE_ID = re.compile(r"[a-z0-9_]+\Z")


class HomeAssistantMqtt:
    """Publish discovery entities and apply commands from an MQTT broker."""

    def __init__(
        self,
        settings: PumpSettings,
        *,
        host: str,
        port: int,
        discovery_prefix: str = "homeassistant",
        device_id: str = "m31_pump",
        credentials: tuple[str | None, str | None] = (None, None),
    ):
        if not host.strip():
            raise ValueError("MQTT host must not be empty.")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("MQTT port must be in 1..65535.")
        if not discovery_prefix or any(char in discovery_prefix for char in "+#"):
            raise ValueError("MQTT discovery prefix must be a valid topic prefix.")
        if not _DEVICE_ID.fullmatch(device_id):
            raise ValueError("Device ID may contain only lowercase letters, digits, and underscores.")
        username, secret = credentials
        if bool(username) != bool(secret):
            raise ValueError("MQTT username and password must be provided together.")
        self.settings = settings
        self.host = host
        self.port = port
        self.discovery_prefix = discovery_prefix.strip("/")
        self.device_id = device_id
        self.base_topic = f"m31_pump/{device_id}"
        self.availability_topic = f"{self.base_topic}/availability"
        self.username = username
        self._secret = secret
        self.client: mqtt.Client | None = None
        self.command_topics = {
            f"{self.base_topic}/automation/set": "enabled",
            f"{self.base_topic}/pressure_start/set": "start_pressure_bar",
            f"{self.base_topic}/pressure_stop/set": "stop_pressure_bar",
        }

    def start(self) -> None:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"m31-pump-{self.device_id}",
        )
        if self.username:
            client.username_pw_set(self.username, self._secret)
        client.will_set(self.availability_topic, "offline", qos=1, retain=True)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        self.client = client
        client.connect_async(self.host, self.port, keepalive=60)
        client.loop_start()

    def stop(self) -> None:
        if self.client is None:
            return
        self.client.publish(self.availability_topic, "offline", qos=1, retain=True)
        self.client.disconnect()
        self.client.loop_stop()
        self.client = None

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties) -> None:
        if reason_code.is_failure:
            LOGGER.warning("Home Assistant MQTT connection failed: %s", reason_code)
            return
        for topic, entity in self._discovery_configs().items():
            client.publish(topic, json.dumps(entity), qos=1, retain=True)
        client.publish(self.availability_topic, "online", qos=1, retain=True)
        client.subscribe([(topic, 1) for topic in self.command_topics])
        self._publish_states(client)
        LOGGER.info("Home Assistant MQTT connected; discovery entities published.")

    def _on_message(self, client, _userdata, message) -> None:
        setting = self.command_topics.get(message.topic)
        if setting is None:
            return
        try:
            payload = message.payload.decode("utf-8").strip()
            if setting == "enabled":
                if payload not in ("ON", "OFF"):
                    raise ValueError("Automation command must be ON or OFF.")
                self.settings.set_enabled(payload == "ON")
            else:
                self.settings.set_pressure(setting, float(payload))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            LOGGER.warning("Rejected Home Assistant MQTT command for %s: %s", setting, exc)
        self._publish_states(client)

    def _publish_states(self, client) -> None:
        current = self.settings.snapshot()
        states = {
            "automation/state": "ON" if current.enabled else "OFF",
            "pressure_start/state": f"{current.start_pressure_bar:.1f}",
            "pressure_stop/state": f"{current.stop_pressure_bar:.1f}",
        }
        for topic, value in states.items():
            client.publish(f"{self.base_topic}/{topic}", value, qos=1, retain=True)

    def _discovery_configs(self) -> dict[str, dict]:
        device = {
            "identifiers": [self.device_id],
            "name": "M31 Pump",
            "manufacturer": "Ebyte",
            "model": "M31",
        }
        common = {
            "availability_topic": self.availability_topic,
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": device,
        }
        entities = (
            (
                "switch",
                "automation",
                {
                    "name": "Pump automation",
                    "state_topic": f"{self.base_topic}/automation/state",
                    "command_topic": f"{self.base_topic}/automation/set",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "state_on": "ON",
                    "state_off": "OFF",
                },
            ),
            (
                "number",
                "pressure_start",
                {
                    "name": "Pump start pressure",
                    "state_topic": f"{self.base_topic}/pressure_start/state",
                    "command_topic": f"{self.base_topic}/pressure_start/set",
                    "min": 0,
                    "max": 9.9,
                    "step": 0.1,
                    "mode": "box",
                    "unit_of_measurement": "bar",
                },
            ),
            (
                "number",
                "pressure_stop",
                {
                    "name": "Pump stop pressure",
                    "state_topic": f"{self.base_topic}/pressure_stop/state",
                    "command_topic": f"{self.base_topic}/pressure_stop/set",
                    "min": 0.1,
                    "max": 10,
                    "step": 0.1,
                    "mode": "box",
                    "unit_of_measurement": "bar",
                },
            ),
        )
        result = {}
        for component, object_id, values in entities:
            config_topic = (
                f"{self.discovery_prefix}/{component}/{self.device_id}/"
                f"{object_id}/config"
            )
            result[config_topic] = {
                **common,
                **values,
                "unique_id": f"{self.device_id}_{object_id}",
            }
        return result
