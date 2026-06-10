"""Config flow for ureal_home integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, InvalidAuth, UrealHomeAPI
from .const import (
    CONF_API_URL,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_APP_KEY,
    CONF_SN,
    DEFAULT_API_URL,
    DEFAULT_APP_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# 定义 UI 界面表单的 Schema 结构
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_URL, default=DEFAULT_API_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_APP_KEY, default=DEFAULT_APP_KEY): str,
    }
)


class UrealHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """处理 ureal_home 的配置流程。"""

    VERSION = 1

    def __init__(self) -> None:
        """初始化配置流。"""
        self._temporary_data: dict[str, Any] = {}
        self._homes: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理初始配置步骤。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = UrealHomeAPI(
                session=session,
                api_url=user_input[CONF_API_URL],
                app_key=user_input[CONF_APP_KEY],
            )

            try:
                # 1. 登录并获取 Token
                token = await api.async_login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                # 2. 登录成功后，调用 async_get_homes 获取绑定的网关列表
                homes = await api.async_get_homes()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during verification")
                errors["base"] = "unknown"
            else:
                if not homes:
                    errors["base"] = "no_gateways"
                else:
                    self._temporary_data = {
                        CONF_API_URL: user_input[CONF_API_URL],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_TOKEN: token,
                        CONF_APP_KEY: user_input[CONF_APP_KEY],
                    }
                    self._homes = homes

                    if len(homes) == 1:
                        home = homes[0]
                        sn = home["sn"]
                        name = home.get("name") or sn
                        
                        await self.async_set_unique_id(sn)
                        self._abort_if_unique_id_configured()

                        # 验证是否可以成功获取该 SN 对应的设备列表
                        api._sn = sn
                        try:
                            await api.async_get_devices()
                        except InvalidAuth:
                            errors["base"] = "invalid_auth"
                        except CannotConnect:
                            errors["base"] = "cannot_connect"
                        except Exception:  # noqa: BLE001
                            _LOGGER.exception("Unexpected error during device list verification")
                            errors["base"] = "unknown"
                        else:
                            return self.async_create_entry(
                                title=name,
                                data={
                                    **self._temporary_data,
                                    CONF_SN: sn,
                                },
                            )
                    else:
                        return await self.async_step_select_gateway()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_select_gateway(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """多网关时让用户选择一个进行配置。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            sn = user_input[CONF_SN]
            name = sn
            for home in self._homes:
                if home["sn"] == sn:
                    name = home.get("name") or sn
                    break

            await self.async_set_unique_id(sn)
            self._abort_if_unique_id_configured()

            # 验证是否可以成功获取该 SN 对应的设备列表
            session = async_get_clientsession(self.hass)
            api = UrealHomeAPI(
                session=session,
                api_url=self._temporary_data[CONF_API_URL],
                token=self._temporary_data[CONF_TOKEN],
                app_key=self._temporary_data[CONF_APP_KEY],
                sn=sn,
            )
            try:
                await api.async_get_devices()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during device list verification")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        **self._temporary_data,
                        CONF_SN: sn,
                    },
                )

        home_choices = {
            home["sn"]: f"{home.get('name') or home['sn']} ({home['sn']})"
            for home in self._homes
        }

        return self.async_show_form(
            step_id="select_gateway",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SN): vol.In(home_choices),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """处理重新认证流程。"""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """确认重新认证并更新已存的配置凭据。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            existing_entry = self.hass.config_entries.async_get_entry(
                self.context["entry_id"]
            )
            if existing_entry is None:
                return self.async_abort(reason="entry_not_found")

            session = async_get_clientsession(self.hass)
            api = UrealHomeAPI(
                session=session,
                api_url=existing_entry.data[CONF_API_URL],
                app_key=user_input[CONF_APP_KEY],
            )

            try:
                # 重新登录以刷新 Token
                token = await api.async_login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                # 使用已有 SN 验证设备获取
                api._sn = existing_entry.data.get(CONF_SN)
                await api.async_get_devices()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during re-auth")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={
                        **existing_entry.data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_TOKEN: token,
                        CONF_APP_KEY: user_input[CONF_APP_KEY],
                    },
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_APP_KEY, default=DEFAULT_APP_KEY): vol.All(str),
                }
            ),
            errors=errors,
        )