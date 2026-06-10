"""ureal_home 集成的选项选择（Select） platform。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.select import SelectEntity
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
    """初始化并添加选项选择实体。"""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: UrealHomeCoordinator = entry_data[DATA_COORDINATOR]
    api: UrealHomeAPI = entry_data[DATA_API]

    entities: list[UrealHomeSelect] = []
    devices = (coordinator.data or {}).get("devices", [])

    _LOGGER.info("选项平台初始化: 找到 %d 个设备", len(devices))

    for device in devices:
        did = str(device["did"])
        dev_type = device.get("type", "")

        # 优先使用静态能力映射来创建选择实体
        if dev_type in DEVICE_CAPABILITIES:
            selects = DEVICE_CAPABILITIES[dev_type].get("selects", [])
            _LOGGER.debug("设备 did=%s type=%s → 静态映射: %d 个选择实体", did, dev_type, len(selects))
            for control_node, feedback_node, idx, name, options_map, options in selects:
                entities.append(
                    UrealHomeSelect(
                        coordinator,
                        api,
                        device,
                        control_node=control_node,
                        feedback_node=feedback_node,
                        idx=idx,
                        name=name,
                        options_map=options_map,
                        options=options,
                    )
                )

    _LOGGER.info("选项平台注册 %d 个实体", len(entities))
    async_add_entities(entities)


class UrealHomeSelect(UrealHomeEntity, SelectEntity):
    """代表 ureal_home 设备上的单个下拉模式/风速控制选择。"""

    def __init__(
        self,
        coordinator: UrealHomeCoordinator,
        api: UrealHomeAPI,
        device: dict[str, Any],
        control_node: str,
        feedback_node: str,
        idx: int = 0,
        name: str | None = None,
        options_map: dict[str, Any] = None,
        options: list[str] = None,
    ) -> None:
        """初始化选择实体。"""
        super().__init__(coordinator, device)
        self._api = api
        self._control_node = control_node
        self._feedback_node = feedback_node
        self._idx = idx
        self._options_map = options_map or {}
        self._attr_options = options or []
        
        # 建立反向查找表，用于将 API 返回的值映射到 HA 的 UI 选项名称
        self._value_to_option = {str(v): k for k, v in self._options_map.items()}

        device_alias = device.get("alias") or device.get("name") or self._device_id
        if name:
            self._attr_name = name
        else:
            name_suffix = f" {idx}" if idx > 0 else ""
            self._attr_name = f"{device_alias} {control_node}{name_suffix}"

        # 唯一标识符中需带上属性 Key 与通道索引
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{control_node}_{idx}"

    @property
    def current_option(self) -> str | None:
        """返回当前选中的选项名称。"""
        val = self._device_status.get(f"{self._feedback_node}:{self._idx}")
        if val is None:
            val = self._device_status.get(f"{self._control_node}:{self._idx}")
        if val is not None:
            return self._value_to_option.get(str(val))
        return None

    async def async_select_option(self, option: str) -> None:
        """执行选项选中操作。"""
        api_val = self._options_map.get(option)
        if api_val is None:
            _LOGGER.error("无效的选项选择: %s", option)
            return

        await self._api.async_set_device_property(
            self._device_id,
            self._idx,
            self._control_node,
            api_val,
            self._device.get("sn"),
        )

        # 乐观更新本地缓存，防止 UI 状态回跳
        if self.coordinator.data and "status" in self.coordinator.data:
            status = self.coordinator.data["status"].setdefault(self._device_id, {})
            status[f"{self._feedback_node}:{self._idx}"] = str(api_val)
            status[f"{self._control_node}:{self._idx}"] = str(api_val)
        self.async_write_ha_state()

        # 延迟 2 秒后请求刷新，给云端状态同步留出缓冲时间
        await asyncio.sleep(2.0)
        await self.coordinator.async_request_refresh()
