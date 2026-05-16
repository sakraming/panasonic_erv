from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pymodbus.client import ModbusTcpClient

from .const import DEFAULT_NAME, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.SELECT]


@dataclass
class PanasonicErvHub:
    host: str
    port: int

    def _client(self) -> ModbusTcpClient:
        return ModbusTcpClient(self.host, port=self.port, timeout=3, framer="rtu")

    def read_data(self) -> dict:
        client = self._client()
        if not client.connect():
            raise ConnectionError(f"无法连接到 {self.host}:{self.port}")
        try:
            result = client.read_holding_registers(address=1, count=16)
            if result.isError():
                raise ConnectionError(f"读取寄存器失败: {result}")
            reg = result.registers
            return {
                "power": reg[0],
                "mode": reg[1],
                "fan_speed": reg[2],
                "actual_mode": reg[3],
                "actual_fan_speed": reg[4],
                "ra_humidity": reg[6],
                "temp_raw": reg[7],
                "filter_clean_hours": reg[9],
                "filter_replace_hours": reg[11],
                "fault_code": reg[14],
            }
        finally:
            client.close()

    def write_register(self, address: int, value: int) -> None:
        client = self._client()
        if not client.connect():
            raise ConnectionError(f"无法连接到 {self.host}:{self.port}")
        try:
            result = client.write_registers(address=address, values=[value])
            if result.isError():
                raise ConnectionError(f"写入寄存器失败: {result}")
        finally:
            client.close()


def get_hub(hass: HomeAssistant, entry: ConfigEntry) -> PanasonicErvHub:
    return hass.data[DOMAIN][entry.entry_id]["hub"]


def get_coordinator(hass: HomeAssistant, entry: ConfigEntry) -> DataUpdateCoordinator:
    return hass.data[DOMAIN][entry.entry_id]["coordinator"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data.get(CONF_HOST)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    hub = PanasonicErvHub(host, port)

    async def async_update_data() -> dict:
        try:
            return await hass.async_add_executor_job(hub.read_data)
        except Exception as err:
            raise UpdateFailed(str(err)) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "hub": hub,
        "coordinator": coordinator,
        "name": name,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
