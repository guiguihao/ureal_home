"""ureal_home 集成的开关（Switch）平台。"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """初始化并添加开关实体。"""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: UrealHomeCoordinator = entry_data[DATA_COORDINATOR]
    api: UrealHomeAPI = entry_data[DATA_API]

    entities: list[UrealHomeSwitch] = []
    devices = (coordinator.data or {}).get("devices", [])

    for device in devices:
        did = str(device["did"])
        dev_type = device.get("type", "")

        # 1. 优先使用静态能力映射来创建开关实体，防止离线无法加载实体
        if dev_type in DEVICE_CAPABILITIES:
            switches = DEVICE_CAPABILITIES[dev_type].get("switches", [])
            for control_node, feedback_node, idx, alias in switches:
                entities.append(
                    UrealHomeSwitch(
                        coordinator,
                        api,
                        device,
                        control_node=control_node,
                        feedback_node=feedback_node,
                        idx=idx,
                        name=alias,
                    )
                )
        else:
            # 2. 如果型号未知，降级使用动态状态轮询或 names 元数据发现
            names = device.get("names")
            if names and isinstance(names, list):
                for item in names:
                    idx = item.get("idx")
                    alias = item.get("alias")
                    if idx is not None:
                        entities.append(UrealHomeSwitch(coordinator, api, device, idx=idx, name=alias))
            else:
                status = (coordinator.data or {}).get("status", {}).get(did, {})
                if (
                    dev_type.startswith(("RL-LT-", "RL-DIMC-", "RL-FHD-"))
                    or "QuerySwitch:0" in status
                    or "Switch:0" in status
                ):
                    name = device.get("alias") or device.get("name") or did
                    entities.append(UrealHomeSwitch(coordinator, api, device, idx=0, name=name))

    async_add_entities(entities)


class UrealHomeSwitch(UrealHomeEntity, SwitchEntity):
    """代表 ureal_home 的开关实体（支持单通道和多通道独立控制与反馈）。"""

    def __init__(
        self,
        coordinator: UrealHomeCoordinator,
        api: UrealHomeAPI,
        device: dict[str, Any],
        control_node: str = "Switch",
        feedback_node: str = "QuerySwitch",
        idx: int = 0,
        name: str | None = None,
    ) -> None:
        """初始化开关实体。"""
        super().__init__(coordinator, device)
        self._api = api
        self._control_node = control_node
        self._feedback_node = feedback_node
        self._idx = idx
        
        device_alias = device.get("alias") or device.get("name") or self._device_id
        if name:
            self._attr_name = name
        else:
            name_suffix = f" {idx}" if idx > 0 else ""
            self._attr_name = f"{device_alias}{name_suffix}"
            
        # 唯一标识符中需带上属性 Key 与通道索引
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{control_node}_{idx}"

    @property
    def is_on(self) -> bool | None:
        """返回开关当前的状态（True 为开启，False 为关闭）。"""
        val = self._device_status.get(f"{self._feedback_node}:{self._idx}")
        if val is None:
            val = self._device_status.get(f"{self._control_node}:{self._idx}")
        return val == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """执行开启操作。"""
        await self._api.async_set_device_property(self._device_id, self._idx, self._control_node, "on")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """执行关闭操作。"""
        await self._api.async_set_device_property(self._device_id, self._idx, self._control_node, "off")
        await self.coordinator.async_request_refresh()


