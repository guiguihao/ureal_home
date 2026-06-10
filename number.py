"""ureal_home 集成的数值（Number） platform。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_API, DATA_COORDINATOR, DOMAIN, DEVICE_CAPABILITIES
from .coordinator import UrealHomeCoordinator
from .entity import UrealHomeEntity
from .api import UrealHomeAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """初始化并添加数值实体。"""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: UrealHomeCoordinator = entry_data[DATA_COORDINATOR]
    api: UrealHomeAPI = entry_data[DATA_API]

    entities: list[UrealHomeNumber] = []
    devices = (coordinator.data or {}).get("devices", [])

    _LOGGER.info("数值平台初始化: 找到 %d 个设备", len(devices))

    for device in devices:
        did = str(device["did"])
        dev_type = device.get("type", "")

        # 优先使用静态能力映射来创建数值实体
        if dev_type in DEVICE_CAPABILITIES:
            numbers = DEVICE_CAPABILITIES[dev_type].get("numbers", [])
            _LOGGER.debug("设备 did=%s type=%s → 静态映射: %d 个数值实体", did, dev_type, len(numbers))
            for control_node, feedback_node, idx, name, min_val, max_val, unit in numbers:
                entities.append(
                    UrealHomeNumber(
                        coordinator,
                        api,
                        device,
                        control_node=control_node,
                        feedback_node=feedback_node,
                        idx=idx,
                        name=name,
                        min_val=min_val,
                        max_val=max_val,
                        unit=unit,
                    )
                )

    _LOGGER.info("数值平台注册 %d 个实体", len(entities))
    async_add_entities(entities)


class UrealHomeNumber(UrealHomeEntity, NumberEntity):
    """代表 ureal_home 设备上的单个数值控制（例如设定温度、设定湿度等）。"""

    def __init__(
        self,
        coordinator: UrealHomeCoordinator,
        api: UrealHomeAPI,
        device: dict[str, Any],
        control_node: str,
        feedback_node: str,
        idx: int = 0,
        name: str | None = None,
        min_val: float = 0.0,
        max_val: float = 100.0,
        unit: str | None = None,
    ) -> None:
        """初始化数值实体。"""
        super().__init__(coordinator, device)
        self._api = api
        self._control_node = control_node
        self._feedback_node = feedback_node
        self._idx = idx
        self._min_val = min_val
        self._max_val = max_val
        self._unit = unit

        device_alias = device.get("alias") or device.get("name") or self._device_id
        if name:
            self._attr_name = name
        else:
            name_suffix = f" {idx}" if idx > 0 else ""
            self._attr_name = f"{device_alias} {control_node}{name_suffix}"

        # 唯一标识符中需带上属性 Key 与通道索引
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{control_node}_{idx}"

    @property
    def native_value(self) -> float | None:
        """返回当前实体的数值值。"""
        val = self._device_status.get(f"{self._feedback_node}:{self._idx}")
        if val is None:
            val = self._device_status.get(f"{self._control_node}:{self._idx}")
        if val is not None:
            try:
                return float(val)
            except ValueError:
                return None
        return None

    @property
    def native_min_value(self) -> float:
        """返回可设定的最小值。"""
        return self._min_val

    @property
    def native_max_value(self) -> float:
        """返回可设定的最大值。"""
        return self._max_val

    @property
    def native_step(self) -> float:
        """返回设定数值的步长。"""
        return 1.0

    @property
    def native_unit_of_measurement(self) -> str | None:
        """返回数值的测量单位。"""
        return self._unit

    async def async_set_native_value(self, value: float) -> None:
        """执行数值设定操作。"""
        # 转换值为整数（如果值是整数格式）以保持接口友好度
        val_to_send = int(value) if value.is_integer() else value

        await self._api.async_set_device_property(
            self._device_id,
            self._idx,
            self._control_node,
            val_to_send,
            self._device.get("sn"),
        )

        # 乐观更新本地缓存，防止 UI 状态回跳
        if self.coordinator.data and "status" in self.coordinator.data:
            status = self.coordinator.data["status"].setdefault(self._device_id, {})
            status[f"{self._feedback_node}:{self._idx}"] = str(val_to_send)
            status[f"{self._control_node}:{self._idx}"] = str(val_to_send)
        self.async_write_ha_state()

        # 延迟 2 秒后请求刷新，给云端状态同步留出缓冲时间
        await asyncio.sleep(2.0)
        await self.coordinator.async_request_refresh()
