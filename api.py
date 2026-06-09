"""ureal_home 集成的云端 API 客户端类。"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class CannotConnect(Exception):
    """无法连接到服务器的异常。"""


class InvalidAuth(Exception):
    """身份验证失败的异常。"""


class UrealHomeAPI:
    """与 ureal_home 云端 API 通信的客户端类。"""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_url: str,
        token: str | None = None,
        app_key: str | None = None,
        sn: str | None = None,
    ) -> None:
        """初始化 API 客户端。"""
        self._session = session
        self._api_url = api_url.rstrip("/")
        self._token = token
        self._app_key = app_key
        self._sn = sn

    def _generate_sign(self, timestamp: int) -> str:
        """生成 API 签名: md5(timestamp + '_hzureal.com_2019')"""
        sign_str = f"{timestamp}_hzureal.com_2019"
        return hashlib.md5(sign_str.encode()).hexdigest()

    async def _post(
        self, endpoint: str, data: dict[str, Any] = None, retries: int = 2
    ) -> Any:
        """封装 POST 请求逻辑，包含签名、认证 Header 和重试机制。"""
        url = f"{self._api_url}{endpoint}"
        
        timestamp = int(time.time() * 1000)
        sign = self._generate_sign(timestamp)
        
        headers = {
            "Content-Type": "application/json",
            "timestamp": str(timestamp),
            "sign": sign
        }
        
        payload = data or {}
        if self._token and "token" not in payload:
            payload["token"] = self._token
        if self._app_key and "appKey" not in payload:
            payload["appKey"] = self._app_key

        _LOGGER.debug("发送 API 请求: POST %s, Payload: %s", endpoint, payload)
        
        last_error = None
        for attempt in range(retries + 1):
            try:
                async with self._session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        raise CannotConnect(f"HTTP 错误代码: {resp.status}")
                    
                    result = await resp.json()
                    if result.get("code") != 0:
                        code = result.get("code")
                        msg = result.get("msg", "未知错误")
                        _LOGGER.error("API 错误 (%s): %s (URL: %s)", code, msg, endpoint)
                        # 110106/110107 indicates invalid/expired login token
                        if code in (110106, 110107):
                            raise InvalidAuth(msg)
                        return None
                    return result.get("data")
            except aiohttp.ClientError as err:
                last_error = err
                _LOGGER.warning("HTTP 请求失败 (尝试 %d/%d): %s", attempt + 1, retries + 1, err)
                if attempt < retries:
                    await asyncio.sleep(1.0 * (attempt + 1))
            except Exception as err:
                if isinstance(err, (CannotConnect, InvalidAuth)):
                    raise
                last_error = err
                _LOGGER.warning("请求发生非预期错误: %s", err)
                if attempt < retries:
                    await asyncio.sleep(1.0 * (attempt + 1))
        
        raise CannotConnect(f"HTTP 请求在 {retries + 1} 次尝试后失败: {last_error}")

    async def async_get_homes(self) -> list[dict[str, Any]]:
        """获取用户家庭/网关列表。"""
        res = await self._post("/host/list2")
        if isinstance(res, list):
            return res
        return []

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """获取当前 SN 绑定的所有设备列表。"""
        if not self._sn:
            _LOGGER.error("未配置 SN 序列号，无法获取设备列表。")
            return []
        
        res = await self._post("/host/project/get", {"sn": self._sn})
        if res and isinstance(res, dict) and "device" in res:
            return res["device"]
        return []

    async def async_get_device_status(self, device_id: str) -> dict[str, Any]:
        """获取指定设备的最新属性状态字典。"""
        if not self._sn:
            _LOGGER.error("未配置 SN 序列号，无法获取设备状态。")
            return {}
            
        try:
            did = int(device_id)
        except ValueError:
            did = device_id
            
        res = await self._post("/device/stat/get", {"sn": self._sn, "did": did})
        states: dict[str, Any] = {}
        if isinstance(res, list):
            for item in res:
                node = item.get("node")
                idx = item.get("idx", 0)
                value = item.get("value")
                if node is not None:
                    states[f"{node}:{idx}"] = value
        return states

    async def async_set_device_property(
        self, device_id: str, idx: int, node: str, value: Any
    ) -> bool:
        """向指定设备发送控制指令。"""
        if not self._sn:
            _LOGGER.error("未配置 SN 序列号，无法控制设备。")
            return False
            
        try:
            did = int(device_id)
        except ValueError:
            did = device_id
            
        payload = {
            "sn": self._sn,
            "did": did,
            "idx": idx,
            "node": node,
            "value": str(value),
            "cliernttype": "Android",
            "clienttype": "Android"
        }
        await self._post("/device/ai/ctrl", payload)
        return True

    def set_credentials(self, token: str, app_key: str, sn: str | None = None) -> None:
        """保存已持久化的 Token, App Key 和 SN 到客户端实例。"""
        self._token = token
        self._app_key = app_key
        if sn:
            self._sn = sn


