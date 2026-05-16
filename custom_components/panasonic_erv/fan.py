from __future__ import annotations

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_coordinator, get_hub

SPEED_TO_PERCENT = {
    1: 33,
    2: 66,
    3: 100,
}

SPEED_TO_NAME = {
    1: "低",
    2: "中",
    3: "高",
}

MODE_TO_PRESET = {
    0: "热交换",
    1: "普通模式",
}

PRESET_TO_MODE = {
    "热交换": 0,
    "普通模式": 1,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = get_coordinator(hass, entry)
    hub = get_hub(hass, entry)
    async_add_entities([PanasonicErvFan(coordinator, hub)])


class PanasonicErvFan(CoordinatorEntity, FanEntity):
    _attr_name = "松下新风"
    _attr_icon = "mdi:air-filter"
    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE

    def __init__(self, coordinator, hub):
        super().__init__(coordinator)
        self._hub = hub
        self._attr_unique_id = f"{coordinator.name}_fan"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("power") == 1

    @property
    def percentage(self) -> int | None:
        speed = self.coordinator.data.get("fan_speed")
        if speed is None:
            return None
        return SPEED_TO_PERCENT.get(speed)

    @property
    def percentage_step(self) -> int:
        return 33

    @property
    def preset_modes(self) -> list[str]:
        return ["热交换", "普通模式"]

    @property
    def current_preset_mode(self) -> str | None:
        mode = self.coordinator.data.get("mode")
        return MODE_TO_PRESET.get(mode)

    @property
    def extra_state_attributes(self):
        speed = self.coordinator.data.get("fan_speed")
        mode = self.coordinator.data.get("mode")
        actual_speed = self.coordinator.data.get("actual_fan_speed")
        actual_mode = self.coordinator.data.get("actual_mode")
        temp_raw = self.coordinator.data.get("temp_raw")

        return {
            "当前风量档位": SPEED_TO_NAME.get(speed, "未知"),
            "当前模式": MODE_TO_PRESET.get(mode, "未知"),
            "实际风量档位": SPEED_TO_NAME.get(actual_speed, "未知"),
            "实际模式": MODE_TO_PRESET.get(actual_mode, "未知"),
            "室内湿度": self.coordinator.data.get("ra_humidity"),
            "温度": (temp_raw - 30) if isinstance(temp_raw, int) and temp_raw > 0 else None,
            "滤网清扫剩余时间(小时)": self.coordinator.data.get("filter_clean_hours"),
            "滤网更换剩余时间(小时)": self.coordinator.data.get("filter_replace_hours"),
            "故障代码": self.coordinator.data.get("fault_code"),
        }

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs) -> None:
        await self.hass.async_add_executor_job(self._hub.write_register, 1, 1)

        if preset_mode is not None:
            mode_value = PRESET_TO_MODE.get(preset_mode)
            if mode_value is not None:
                await self.hass.async_add_executor_job(self._hub.write_register, 2, mode_value)

        if percentage is not None:
            speed = self._percentage_to_speed(percentage)
            await self.hass.async_add_executor_job(self._hub.write_register, 3, speed)

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(self._hub.write_register, 1, 0)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        if not self.is_on:
            await self.hass.async_add_executor_job(self._hub.write_register, 1, 1)

        speed = self._percentage_to_speed(percentage)
        await self.hass.async_add_executor_job(self._hub.write_register, 3, speed)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        mode_value = PRESET_TO_MODE.get(preset_mode)
        if mode_value is None:
            return

        if not self.is_on:
            await self.hass.async_add_executor_job(self._hub.write_register, 1, 1)

        await self.hass.async_add_executor_job(self._hub.write_register, 2, mode_value)
        await self.coordinator.async_request_refresh()

    def _percentage_to_speed(self, percentage: int) -> int:
        if percentage <= 33:
            return 1
        if percentage <= 66:
            return 2
        return 3
