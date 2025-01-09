"""Module provides the API functionality for ecoNET-300 Home Assistant Integration."""
import asyncio
from http import HTTPStatus
import logging
from typing import Any
import aiohttp
from aiohttp import BasicAuth, ClientSession

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    # API_EDITABLE_PARAMS_LIMITS_DATA,
    # API_EDITABLE_PARAMS_LIMITS_URI,
    API_REG_PARAMS_PARAM_DATA,
    API_REG_PARAMS_URI,
    # API_REG_PARAMSDATA_URI,
    # API_REG_PARAMSDATA_PARAM_DATA,
    API_EDIT_PARAMS_URI,
    API_EDIT_PARAMS_DATA,
    API_SYS_PARAMS_PARAM_HW_VER,
    API_SYS_PARAMS_PARAM_SW_REV,
    API_SYS_PARAMS_PARAM_UID,
    API_SYS_PARAMS_URI,
    EDITABLE_PARAMS_MAPPING_TABLE,
)
from .mem_cache import MemCache

_LOGGER = logging.getLogger(__name__)


def map_param(param_name):
    """Check params mapping in const.py."""
    if param_name not in EDITABLE_PARAMS_MAPPING_TABLE:
        return None

    return EDITABLE_PARAMS_MAPPING_TABLE[param_name]


class Limits:
    """Construct all the necessary attributes for the Limits object."""
    def __init__(self, min_v: int | None, max_v: int | None):
        """Construct the necessary attributes for the Limits object."""
        self.minv = min_v
        self.maxv = max_v

    class AuthError(Exception):
        """Raised when authentication fails."""


class AuthError(Exception):
    """Raised when authentication fails."""


class ApiError(Exception):
    """Raised when an API error occurs."""


class DataError(Exception):
    """Raised when there is an error with the data."""


class EconetClient:
    """Client for interacting with the ecoNET-300 API."""

    def __init__(
        self, host: str, username: str, password: str, session: ClientSession
    ) -> None:
        """Initialize the EconetClient."""

        proto = ["http://", "https://"]

        not_contains = all(p not in host for p in proto)

        if not_contains:
            #_LOGGER.warning("Manually adding 'http' to host")
            host = "http://" + host

        self._host = host
        self._session = session
        self._auth = BasicAuth(username, password)
        self._model_id = "default-model-id"
        self._sw_revision = "default-sw-revision"

    def host(self):
        """Get the host."""
        return self._host


    async def set_param(self, key: str, value: str):
        """Set a parameter."""
        url = f"{self._host}/econet/newParam?newParamName={key}&newParamValue={value}"
        _LOGGER.debug("Set Param URL: %s", url)
        return await self._get(url)


    async def get_params(self, reg: str):
        """Get parameters for a given registry.

        Args:
            reg (str): The registry to retrieve parameters from.

        Returns:
            dict: The parameters retrieved from the registry.
        """
        url = f"{self._host}/econet/{reg}"

        return await self._get(url)

    async def _get(self, url):
        attempt = 1
        max_attempts = 5

        while attempt <= max_attempts:
            try:
                _LOGGER.debug("Fetching data from URL: %s (Attempt %d)", url, attempt)
                _LOGGER.debug(
                    "Using model_id: %s, sw_revision: %s",
                    self._model_id,
                    self._sw_revision,
                )
                async with await self._session.get(
                    url, auth=self._auth, timeout=10
                ) as resp:
                    _LOGGER.debug("Received response with status: %s", resp.status)
                    if resp.status == HTTPStatus.UNAUTHORIZED:
                        _LOGGER.error("Unauthorized access to URL: %s", url)
                        raise AuthError

                    if resp.status != HTTPStatus.OK:
                        try:
                            error_message = await resp.text()
                        except (aiohttp.ClientError, aiohttp.ClientResponseError) as e:
                            error_message = f"Could not retrieve error message: {e}"

                        _LOGGER.error(
                            "Failed to fetch data from URL: %s (Status: %s) - Response: %s",
                            url,
                            resp.status,
                            error_message,
                        )
                        return None

                    data = await resp.json()
                    _LOGGER.debug("Fetched data: %s", data)
                    return data

            except TimeoutError:
                _LOGGER.warning("Timeout error, retry(%i/%i)", attempt, max_attempts)
                await asyncio.sleep(1)
            attempt += 1
        _LOGGER.error(
            "Failed to fetch data from %s after %d attempts", url, max_attempts
        )
        return None

class Econet300Api:
    """Client for interacting with the ecoNET-300 API."""

    def __init__(self, client: EconetClient, cache: MemCache) -> None:
        """Initialize the Econet300Api object with a client, cache, and default values for uid, sw_revision, and hw_version."""
        self._client = client
        self._cache = cache
        self._uid = "default-uid"
        self._sw_revision = "default-sw-revision"
        self._hw_version = "default-hw-version"

    @classmethod
    async def create(cls, client: EconetClient, cache: MemCache):
        """Create an instance of Econet300Api."""
        c = cls(client, cache)
        await c.init()

        return c

    def host(self):
        """Get the host."""
        return self._client.host()

    def uid(self) -> str:
        """Get the UID."""
        return self._uid

    def sw_rev(self) -> str:
        """Get the software revision."""
        # Set a parameter value via the Econet 300 API.

    def hw_ver(self) -> str:
        """Get the hardware version."""
        return self._hw_version

    async def init(self):
        """Initialize the Econet300Api."""
        sys_params = await self._client.get_params(API_SYS_PARAMS_URI)

        if API_SYS_PARAMS_PARAM_UID not in sys_params:
            _LOGGER.warning(
                "%s not in sys_params - cannot set proper UUID",
                API_SYS_PARAMS_PARAM_UID,
            )
        else:
            self._uid = sys_params[API_SYS_PARAMS_PARAM_UID]

        if API_SYS_PARAMS_PARAM_SW_REV not in sys_params:
            _LOGGER.warning(
                "%s not in sys_params - cannot set proper sw_revision",
                API_SYS_PARAMS_PARAM_SW_REV,
            )
        else:
            self._sw_revision = sys_params[API_SYS_PARAMS_PARAM_SW_REV]

        if API_SYS_PARAMS_PARAM_HW_VER not in sys_params:
            _LOGGER.warning(
                "%s not in sys_params - cannot set proper hw_version",
                API_SYS_PARAMS_PARAM_HW_VER,
            )
        else:
            self._hw_version = sys_params[API_SYS_PARAMS_PARAM_HW_VER]

    async def set_param(self, param, value) -> bool:
        """Set a parameter value via the Econet 300 API."""
        param_idx = map_param(param)

        valuecheck = str(value).replace(".0", "")
        value = valuecheck
        
        if param_idx is None:
            _LOGGER.warning(
                "Requested param set for: '{param}' but mapping for this param does not exist"
            )
            return False

        data = await self._client.set_param(param_idx, value)
            
        if data is None or "result" not in data:
            return False

        if data["result"] != "OK":
            return False

        self._cache.set(param, value)

        return True


    async def get_param_limits(self, param: str):
        """Fetch and return the limits for a particular parameter from the Econet 300 API, using a cache for efficient retrieval if available."""
        if not self._cache.exists(API_EDIT_PARAMS_DATA):
            limits = await self._fetch_reg_key(
                API_EDIT_PARAMS_URI, API_EDIT_PARAMS_DATA
            )
            self._cache.set(API_EDIT_PARAMS_DATA, limits)

        limits = self._cache.get(API_EDIT_PARAMS_DATA)
        param_idx = map_param(param)
        
        if param_idx is None:
            _LOGGER.warning(
                "Requested param limits for: '%s' but mapping for this param does not exist",
                param,
            )
            return None

        if param_idx not in limits:
            _LOGGER.warning(
                "Requested param limits for: '%s(%s)' not in limits",
                param,
                param_idx,
            )
            return None

        curr_limits = limits[param_idx]
        
        return Limits(curr_limits['minv'], curr_limits['maxv'])


    async def fetch_data(self) -> dict[str, Any]:
        """Fetch merged reg_params, sys_params and edit_params data."""
        reg_params = await self._fetch_reg_key(
            API_REG_PARAMS_URI, API_REG_PARAMS_PARAM_DATA
        )
        # reg_paramsdata = await self._fetch_reg_key(
        #     API_REG_PARAMSDATA_URI, API_REG_PARAMSDATA_PARAM_DATA
        # )
        sys_params = await self._fetch_reg_key(API_SYS_PARAMS_URI)
        
        edit_params = await self._fetch_reg_key(
            API_EDIT_PARAMS_URI, API_EDIT_PARAMS_DATA
        )
        """ Edit Params values"""
        for key, value in edit_params.items():
            edit_params[key] = value['value']
        
        # _LOGGER.warning("Edits Params data: %s", edit_params)
        return {**reg_params, **sys_params, **edit_params} # **reg_paramsdata, 


    async def _fetch_reg_key(self, reg, data_key: str | None = None):
        """Fetch a key from the json-encoded data returned by the API for a given registry If key is None, then return whole data."""
        data = await self._client.get_params(reg)

        if 'error' in data:
            #_LOGGER.warning("Error in DATA: %s", data)
            """Retrive data again"""
            data = await self._client.get_params(reg)

        if data is None:
            raise DataError(f"Data fetched by API for reg: {reg} is None")

        if data_key is None:
            return data

        if data_key not in data:
            _LOGGER.debug(data)
            raise DataError(f"Data for key: {data_key} does not exist")

        return data[data_key]

async def make_api(hass: HomeAssistant, cache: MemCache, data: dict):
    """Create an Econet 300 API instance."""
    return await Econet300Api.create(
        EconetClient(
            data["host"],
            data["username"],
            data["password"],
            async_get_clientsession(hass),
        ),
        cache,
    )
