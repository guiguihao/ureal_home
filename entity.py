"""ureal_home 集成的基础实体基类。"""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UrealHomeCoordinator


class UrealHomeEntity(CoordinatorEntity[UrealHomeCoordinator]):
    """所有 ureal_home 平台实体的基类。

    继承自 CoordinatorEntity，这样当协调器（Coordinator）刷新并获取到新数据时，
    绑定的实体会自动接收到通知并触发界面更新（不需要在每个实体中手动写轮询）。
    """

    # 启用该属性后，实体的友好名称（friendly name）会自动继承自设备名称，且以实体本身的属性（如“温度”）命名。
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UrealHomeCoordinator,
        device: dict[str, Any],
    ) -> None:
        """初始化基础实体。"""
        super().__init__(coordinator)
        self._device = device
        self._device_id: str = str(device["did"])


    @property
    def device_info(self) -> DeviceInfo:
        """返回设备信息，将属于同一个物理设备的所有实体组合在 Home Assistant 的同一个“设备卡片”下。"""
        return DeviceInfo(
            # 设备的唯一识别组合
            identifiers={(DOMAIN, self._device_id)},
            # 设备在 UI 上显示的名称
            name=self._device.get("alias") or self._device.get("name") or self._device_id,
            # 制造厂商
            manufacturer="Ureal",
            # 设备型号（使用云端返回的 type）
            model=self._device.get("type", "unknown"),
        )

    # ------------------------------------------------------------------
    # 辅助工具方法
    # ------------------------------------------------------------------

    @property
    def _device_status(self) -> dict[str, Any]:
        """从协调器缓存数据中快速获取当前设备的属性状态字典。"""
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.get("status", {}).get(self._device_id, {})

    @property
    def available(self) -> bool:
        """判断当前实体是否可用（在线）。

        如果协调器无法连接或者云端设备上报为离线（online=False），实体在 HA 界面上会显示为“不可用”灰色状态。
        """
        if not super().available:
            return False
        
        # 在协调器拉取的设备列表中查找当前设备，并利用 QueryLinkStat 状态判断在线状态
        devices = (self.coordinator.data or {}).get("devices", [])
        for dev in devices:
            if str(dev["did"]) == self._device_id:
                link_stat = self._device_status.get("QueryLinkStat:0")
                return link_stat != "offline"
        return False

