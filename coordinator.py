"""ureal_home 集成的数据更新协调器（Coordinator）。"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from homeassistant.config_entries import ConfigEntry

from .api import CannotConnect, InvalidAuth, UrealHomeAPI
from .const import (
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class UrealHomeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """协调器：定时轮询云端 API，并将最新状态分发给集成下的所有实体。

    _async_update_data 方法返回的数据结构如下:
    {
        "devices": [
            { "id": "...", "name": "...", "type": "...", "online": True, ... }
        ],
        "status": {
            "device-001": { "temperature": 26.5, "humidity": 60 },
            "device-002": { "state": True },
        }
    }
    """

    def __init__(
        self, hass: HomeAssistant, api: UrealHomeAPI, entry: ConfigEntry
    ) -> None:
        """初始化数据更新协调器。"""
        self.api = api
        self.config_entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # 设置定时轮询间隔时间（在 const.py 中定义，默认 30 秒）
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _fetch_data(self) -> dict[str, Any]:
        """实际拉取数据的逻辑。"""
        # 1. 从云端拉取当前账号绑定的设备列表
        devices = await self.api.async_get_devices()
        _LOGGER.info("获取到设备列表，共 %d 个设备", len(devices))
        for dev in devices:
            _LOGGER.debug(
                "  设备: did=%s alias=%s type=%s",
                dev.get("did"), dev.get("alias"), dev.get("type"),
            )

        if not devices:
            _LOGGER.warning("设备列表为空，可能 SN 配置有误或账号无绑定设备")
            return {"devices": [], "status": {}}

        # 2. 并行获取列表中每个设备的最新属性状态
        import asyncio  # noqa: PLC0415

        # 构造每个设备的异步获取状态任务
        status_tasks = {
            str(device["did"]): self.api.async_get_device_status(str(device["did"]), device.get("sn"))
            for device in devices
        }
        # 并发执行所有状态查询任务
        status_results = await asyncio.gather(
            *status_tasks.values(), return_exceptions=True
        )

        status: dict[str, Any] = {}
        for device_id, result in zip(status_tasks.keys(), status_results):
            if isinstance(result, Exception):
                # 若单个设备状态获取失败，记录警告日志但继续运行，避免影响其他正常设备
                _LOGGER.warning(
                    "获取设备 %s 状态失败: %s",
                    device_id,
                    result,
                )
                status[device_id] = {}
            else:
                status[device_id] = result

        # 返回包含设备列表和各设备状态的字典，实体会自动通过 coordinator.data 拿到这些数据
        _LOGGER.info("数据刷新完成: %d 个设备", len(devices))
        return {"devices": devices, "status": status}


    async def _async_update_data(self) -> dict[str, Any]:
        """从云端 API 获取最新数据。

        协调器会按照指定的 update_interval 自动周期性调用此方法。
        """
        try:
            return await self._fetch_data()
        except InvalidAuth as err:
            # 尝试使用保存的账户密码进行自动登录
            username = self.config_entry.data.get(CONF_USERNAME)
            password = self.config_entry.data.get(CONF_PASSWORD)
            if username and password:
                _LOGGER.info("登录 Token 失效，正在尝试自动重新登录...")
                try:
                    new_token = await self.api.async_login(username, password)
                    # 重新登录成功后更新 config entry 以便持久化新 token
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={**self.config_entry.data, CONF_TOKEN: new_token},
                    )
                    _LOGGER.info("自动重新登录成功，Token 已刷新。")
                    # 使用新 token 再次尝试拉取数据
                    return await self._fetch_data()
                except Exception as login_err:
                    _LOGGER.error("自动重新登录失败: %s", login_err)
            
            # 如果没有配置密码或自动登录失败，才抛出 ConfigEntryAuthFailed
            raise ConfigEntryAuthFailed from err
        except CannotConnect as err:
            # 暂时性的网络连接错误，抛出 UpdateFailed
            # HA 会自动将相关实体标记为“不可用”，并在后台继续尝试重新轮询
            raise UpdateFailed(f"无法连接到 ureal_home API: {err}") from err

