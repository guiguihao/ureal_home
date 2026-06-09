"""ureal_home 集成的数据更新协调器（Coordinator）。"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, InvalidAuth, UrealHomeAPI
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

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

    def __init__(self, hass: HomeAssistant, api: UrealHomeAPI) -> None:
        """初始化数据更新协调器。"""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # 设置定时轮询间隔时间（在 const.py 中定义，默认 30 秒）
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """从云端 API 获取最新数据。

        协调器会按照指定的 update_interval 自动周期性调用此方法。
        """
        try:
            # 1. 从云端拉取当前账号绑定的设备列表
            devices = await self.api.async_get_devices()

            # 2. 并行获取列表中每个设备的最新属性状态
            import asyncio  # noqa: PLC0415

            # 构造每个设备的异步获取状态任务
            status_tasks = {
                str(device["did"]): self.api.async_get_device_status(str(device["did"]))
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
            return {"devices": devices, "status": status}

        except InvalidAuth as err:
            # 登录凭证失效（例如 Token 过期），抛出 ConfigEntryAuthFailed
            # 这会在 HA 前端界面该集成上显示“需要重新认证”的通知，引导用户重新输入密码
            raise ConfigEntryAuthFailed from err
        except CannotConnect as err:
            # 暂时性的网络连接错误，抛出 UpdateFailed
            # HA 会自动将相关实体标记为“不可用”，并在后台继续尝试重新轮询
            raise UpdateFailed(f"无法连接到 ureal_home API: {err}") from err

