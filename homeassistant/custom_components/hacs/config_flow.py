"""Adds config flow for HACS."""

from __future__ import annotations

import aiohttp
import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING

from aiogithubapi import (
    GitHubDeviceAPI,
    GitHubException,
    GitHubLoginDeviceModel,
    GitHubLoginOauthModel,
)
from aiogithubapi.common.const import OAUTH_USER_LOGIN
from awesomeversion import AwesomeVersion
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import __version__ as HAVERSION
from homeassistant.core import callback
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.helpers import aiohttp_client
from homeassistant.loader import async_get_integration
import voluptuous as vol

from .base import HacsBase
from .const import CLIENT_ID, DOMAIN, LOCALE, MINIMUM_HA_VERSION, BASE_API_URL
from .utils.configuration_schema import (
    APPDAEMON,
    COUNTRY,
    SIDEPANEL_ICON,
    SIDEPANEL_TITLE,
    GITHUB_APIS,
)
from .utils.logger import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class HacsFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for HACS."""

    VERSION = 1

    hass: HomeAssistant
    activation_task: asyncio.Task | None = None
    device: GitHubDeviceAPI | None = None

    _registration: GitHubLoginDeviceModel | None = None
    _activation: GitHubLoginOauthModel | None = None
    _reauth: bool = False

    def __init__(self) -> None:
        """Initialize."""
        self._errors = {}
        self._user_input = {}

    async def async_step_user(self, user_input):
        """Handle a flow initialized by the user."""
        self._errors = {}
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if self.hass.data.get(DOMAIN):
            return self.async_abort(reason="single_instance_allowed")

        if user_input:
            if [x for x in user_input if x.startswith("acc_") and not user_input[x]]:
                self._errors["base"] = "acc"
                return await self._show_config_form(user_input)

            if not user_input.get('use_shared'):
                self._user_input = user_input
                return await self.async_step_device(user_input)
            elif not await self.async_get_shard_token():
                self._errors['base'] = 'get_shared'
            else:
                return await self.async_step_device_done(user_input)

        # Initial form
        return await self._show_config_form(user_input)

    async def async_step_device(self, _user_input):
        """Handle device steps."""

        async def _wait_for_activation() -> None:
            try:
                response = await self.device.activation(device_code=self._registration.device_code)
                self._activation = response.data
            finally:

                async def _progress():
                    with suppress(UnknownFlow):
                        await self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)

        if not self.device:
            integration = await async_get_integration(self.hass, DOMAIN)
            self.device = GitHubDeviceAPI(
                client_id=CLIENT_ID,
                session=aiohttp_client.async_get_clientsession(self.hass),
                **{"client_name": f"HACS/{integration.version}"},
            )
            try:
                response = await self.device.register()
                self._registration = response.data
            except GitHubException as exception:
                LOGGER.exception(exception)
                return self.async_abort(reason="could_not_register")

        if self.activation_task is None:
            self.activation_task = self.hass.async_create_task(_wait_for_activation())

        if self.activation_task.done():
            if (exception := self.activation_task.exception()) is not None:
                LOGGER.exception(exception)
                return self.async_show_progress_done(next_step_id="could_not_register")
            return self.async_show_progress_done(next_step_id="device_done")

        show_progress_kwargs = {
            "step_id": "device",
            "progress_action": "wait_for_device",
            "description_placeholders": {
                "url": OAUTH_USER_LOGIN,
                "code": self._registration.user_code,
            },
            "progress_task": self.activation_task,
        }
        return self.async_show_progress(**show_progress_kwargs)

    async def _show_config_form(self, user_input):
        """Show the configuration form to edit location data."""

        if not user_input:
            user_input = {}

        if AwesomeVersion(HAVERSION) < MINIMUM_HA_VERSION:
            return self.async_abort(
                reason="min_ha_version",
                description_placeholders={"version": MINIMUM_HA_VERSION},
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("use_shared", default=user_input.get("use_shared", True)): bool,
                    vol.Required("acc_logs", default=user_input.get("acc_logs", False)): bool,
                    vol.Required("acc_addons", default=user_input.get("acc_addons", False)): bool,
                    vol.Required(
                        "acc_untested", default=user_input.get("acc_untested", False)
                    ): bool,
                    vol.Required("acc_disable", default=user_input.get("acc_disable", False)): bool,
                }
            ),
            errors=self._errors,
        )

    async def async_step_device_done(self, user_input: dict[str, bool] | None = None):
        """Handle device steps"""
        if self._reauth:
            existing_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            self.hass.config_entries.async_update_entry(
                existing_entry, data={**existing_entry.data, "token": self._activation.access_token}
            )
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title="",
            data={
                "token": self._activation.access_token,
            },
            options={
                "experimental": True,
                "use_shared": user_input.get('use_shared', False),
            },
        )

    async def async_step_could_not_register(self, _user_input=None):
        """Handle issues that need transition await from progress step."""
        return self.async_abort(reason="could_not_register")

    async def async_step_reauth(self, _user_input=None):
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        self._reauth = True
        return await self.async_step_device(None)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HacsOptionsFlowHandler(config_entry)

    async def async_get_shard_token(self):
        api = 'https://tokenhub.hacs.vip/api/token/get'
        try:
            integration = await async_get_integration(self.hass, DOMAIN)
            http = aiohttp_client.async_get_clientsession(self.hass)
            res = await http.get(
                api,
                timeout=aiohttp.ClientTimeout(total=10),
                headers={
                    'User-Agent': f'HACS China/{integration.version}',
                },
            )
            dat = await res.json()
            token = dat.get('data', {}).get('token')
        except Exception:
            return None
        self._activation = GitHubLoginOauthModel({
            'access_token': token,
        })
        return token


class HacsOptionsFlowHandler(OptionsFlow):
    """HACS config flow options handler."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        if AwesomeVersion(HAVERSION) < "2024.11.99":
            self.config_entry = config_entry

    async def async_step_init(self, _user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        hacs: HacsBase = self.hass.data.get(DOMAIN)
        if user_input is not None:
            if api := user_input.get('github_api_custom'):
                user_input['github_api_base'] = api
            if user_input.get('share_token'):
                resp = await self.async_share_token(self.config_entry.data.get('token')) or {}
                if resp.get('data', {}).get('use_count'):
                    return self.async_abort(reason="token_exists")
            return self.async_create_entry(title="", data={
                "use_shared": self.config_entry.options.get('use_shared', False),
                **user_input,
                "experimental": True,
            })

        if hacs is None or hacs.configuration is None:
            return self.async_abort(reason="not_setup")

        if hacs.queue.has_pending_tasks:
            return self.async_abort(reason="pending_tasks")

        api_base = hacs.configuration.github_api_base or BASE_API_URL
        GITHUB_APIS.setdefault(api_base, f'{api_base} (自定义)')
        schema = {
            vol.Optional(SIDEPANEL_TITLE, default=hacs.configuration.sidepanel_title): str,
            vol.Optional(SIDEPANEL_ICON, default=hacs.configuration.sidepanel_icon): str,
            vol.Optional(COUNTRY, default=hacs.configuration.country): vol.In(LOCALE),
            vol.Optional("github_api_base", default=api_base): vol.In(GITHUB_APIS),
            vol.Optional("github_api_custom", default=''): str,
            vol.Optional(APPDAEMON, default=hacs.configuration.appdaemon): bool,
        }

        if not self.config_entry.options.get('use_shared'):
            schema.update({
                vol.Optional('share_token', default=self.config_entry.options.get('share_token', False)): bool,
            })

        return self.async_show_form(step_id="user", data_schema=vol.Schema(schema))

    async def async_share_token(self, token):
        api = 'https://tokenhub.hacs.vip/api/token/share'
        try:
            integration = await async_get_integration(self.hass, DOMAIN)
            http = aiohttp_client.async_get_clientsession(self.hass)
            res = await http.get(
                api,
                timeout=aiohttp.ClientTimeout(total=10),
                headers={
                    'User-Agent': f'HACS China/{integration.version}',
                },
                json={
                    'type': 'github',
                    'token': token,
                },
            )
            resp = await res.json() or {}
            LOGGER.warning('Thanks for sharing your token: %s', resp)
        except Exception:
            resp = None
        return resp
