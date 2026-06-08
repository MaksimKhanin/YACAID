"""Thin REST client for Home Assistant.

Rather than reimplementing drivers for every smart-home device, the recorder
("brains" of the household assistant) talks to a Home Assistant instance over
its REST API and lets HA own the device ecosystem (Zigbee/Z-Wave/MQTT/...).
See https://developers.home-assistant.io/docs/api/rest/ — auth is a long-lived
access token sent as `Authorization: Bearer <token>`.
"""
import requests

from logger_setup import get_logger

logger = get_logger("home_assistant")


class HomeAssistantClient:
    def __init__(self, base_url: str, token: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def call_service(self, domain: str, service: str, entity_id: str = None, **data):
        """Call a HA service, e.g. call_service("light", "turn_on", entity_id="light.hallway", brightness_pct=80).

        Returns the list of entity states HA reports as changed by the call.
        """
        payload = dict(data)
        if entity_id is not None:
            payload["entity_id"] = entity_id

        response = requests.post(
            f"{self.base_url}/api/services/{domain}/{service}",
            headers=self._headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        logger.info(f"HA-сервис вызван: {domain}.{service} {payload}")
        return response.json()

    def get_state(self, entity_id: str) -> dict:
        """Fetch the current state of a single entity, e.g. 'binary_sensor.front_door'."""
        response = requests.get(
            f"{self.base_url}/api/states/{entity_id}",
            headers=self._headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_states(self) -> list:
        """Fetch the current state of every entity known to HA."""
        response = requests.get(
            f"{self.base_url}/api/states",
            headers=self._headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
