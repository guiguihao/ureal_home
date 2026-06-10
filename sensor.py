"""ureal_home 集成的传感器（Sensor）平台。"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN, DEVICE_CAPABILITIES, SENSOR_DESCRIPTIONS
from .coordinator import UrealHomeCoordinator
from .entity import UrealHomeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """初始化并添加传感器实体。"""
    
    coordinator: UrealHomeCoordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    entities: list[UrealHomeSensor] = []
    devices = (coordinator.data or {}).get("devices", [])

    for device in devices:
        did = str(device["did"])
        dev_type = device.get("type", "")
        
        # 1. 优先使用静态能力映射来创建实体，防止设备离线或无缓存时无法注册实体
        if dev_type in DEVICE_CAPABILITIES:
            sensors = DEVICE_CAPABILITIES[dev_type].get("sensors", [])
            for prop_key, idx in sensors:
                entities.append(UrealHomeSensor(coordinator, device, prop_key, idx))
        else:
            # 2. 如果型号未知，降级使用动态状态轮询发现
            status = (coordinator.data or {}).get("status", {}).get(did, {})
            for status_key in status:
                if ":" in status_key:
                    prop_key, idx_str = status_key.split(":", 1)
                    try:
                        idx = int(idx_str)
                    except ValueError:
                        idx = 0
                else:
                    prop_key = status_key
                    idx = 0

                if prop_key in SENSOR_DESCRIPTIONS:
                    entities.append(UrealHomeSensor(coordinator, device, prop_key, idx))

    async_add_entities(entities)


class UrealHomeSensor(UrealHomeEntity, SensorEntity):
    """代表 ureal_home 设备上的单个传感器数值实体。"""

    def __init__(
        self,
        coordinator: UrealHomeCoordinator,
        device: dict[str, Any],
        prop_key: str,
        idx: int = 0,
    ) -> None:
        """初始化传感器实体。"""
        super().__init__(coordinator, device)
        self._prop_key = prop_key
        self._idx = idx
        
        # 获取预设的元数据描述，未定义时默认直接使用 key 名字
        desc = SENSOR_DESCRIPTIONS.get(prop_key, (prop_key, None, None, None))

        name_suffix = f" {idx}" if idx > 0 else ""
        self._attr_name = f"{desc[0]}{name_suffix}"
        self._attr_native_unit_of_measurement = desc[1]
        self._attr_device_class = desc[2]
        self._attr_state_class = desc[3]
        
        # 唯一标识符中需带上属性 Key 与通道索引
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{prop_key}_{idx}"

    @property
    def native_value(self) -> Any:
        """返回传感器的当前数值（自动从协调器的缓存状态中读取并转换为数值类型）。"""
        val = self._device_status.get(f"{self._prop_key}:{self._idx}")
        if val is not None:
            try:
                if "." in str(val):
                    return float(val)
                return int(val)
            except ValueError:
                return val
        return None