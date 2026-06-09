"""ureal_home 集成入口文件。"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, UrealHomeAPI
from .const import CONF_API_URL, CONF_TOKEN, CONF_APP_KEY, CONF_SN, DATA_API, DATA_COORDINATOR, DOMAIN, PLATFORMS
from .coordinator import UrealHomeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """从配置条目（ConfigEntry）初始化并启动集成。"""
    
    # 1. 实例化 aiohttp 客户端 session 与 API 客户端
    session = async_get_clientsession(hass)
    
    token = entry.data[CONF_TOKEN]
    app_key = entry.data[CONF_APP_KEY]
    sn = entry.data[CONF_SN]
    
    api = UrealHomeAPI(
        session=session,
        api_url=entry.data[CONF_API_URL],
        token=token,
        app_key=app_key,
        sn=sn,
    )

    # 2. 创建数据更新协调器（Coordinator）负责后续的定时数据轮询
    coordinator = UrealHomeCoordinator(hass, api)

    # 3. 立即进行首次数据刷新（拉取设备列表和属性），如果失败会引发 ConfigEntryNotReady 异常延迟重试
    await coordinator.async_config_entry_first_refresh()

    # 4. 将 api 和 coordinator 实例存入 hass.data 共享中，以便各个平台实体访问
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_API: api,
        DATA_COORDINATOR: coordinator,
    }

    # 6. 将配置异步转发到各个实体平台（如 sensor、switch 等）进行子设备初始化
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载配置条目（例如用户在 UI 上删除或禁用集成时触发）。"""
    # 1. 卸载该配置条目下属的各个平台实体
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # 2. 从内存缓存 hass.data 中移除对应的数据
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
        
    return unloaded