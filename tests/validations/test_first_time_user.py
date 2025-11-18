"""Tests the firstuser"""

from typing import Dict
import logging

import aiohttp
import pytest

from ..conftest import DEFAULT_TIMEOUT, API, VER

LOGGER = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
class ValueStorage:
    """Storage for values generated and used in this testsuite"""

    code = ""
    jwt = ""
    jwt_exchange_code = ""
    call_sign = ""


@pytest.mark.asyncio
async def test_token_code_generate(
    session_with_tpjwt: aiohttp.ClientSession,
) -> None:
    """Tests that we can create a token"""
    client = session_with_tpjwt
    url = f"{API}/{VER}/token/code/generate"
    data = {"claims": {"anon_admin_session": True}}
    LOGGER.debug("Fetching {}".format(url))
    response = await client.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["code"] != ""
    ValueStorage.code = payload["code"]


@pytest.mark.asyncio
async def test_check_valid_token_code(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Tests that we can check valid temp_admin_code"""
    client = session_with_testcas
    url = f"{API}/{VER}/firstuser/check-code?temp_admin_code={ValueStorage.code}"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert response.status == 200
    assert payload["code_ok"] is True


@pytest.mark.asyncio
async def test_token_code_exchange_to_jwt(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Tests that we can exchange token for jwt"""
    client = session_with_testcas
    url = f"{API}/{VER}/token/code/exchange"
    data = {"code": f"{ValueStorage.code}"}
    LOGGER.debug("Fetching {}".format(url))
    response = await client.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["jwt"] != ""
    ValueStorage.jwt = payload["jwt"]


@pytest.mark.asyncio
async def test_firstuser_add_admin(
    session_with_testcas: aiohttp.ClientSession,
    call_sign_generator: str,
) -> None:
    """Tests that we can add firstuser admin"""
    client = session_with_testcas
    client.headers.update({"Authorization": f"Bearer {ValueStorage.jwt}"})
    url = f"{API}/{VER}/firstuser/add-admin"
    data = {
        "callsign": f"{call_sign_generator}",
    }
    LOGGER.debug("Fetching {}".format(url))
    LOGGER.debug("Authorization Bearer {}".format({ValueStorage.jwt}))
    response = await client.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["admin_added"] is True
    assert payload["jwt_exchange_code"] != ""
    ValueStorage.jwt_exchange_code = payload["jwt_exchange_code"]
    ValueStorage.call_sign = call_sign_generator


@pytest.mark.asyncio
async def test_duplicate_firstuser_admin(
    session_with_testcas: aiohttp.ClientSession,
    error_messages: Dict[str, str],
) -> None:
    """Tests failure if firstuser admin already exists"""
    client = session_with_testcas
    client.headers.update({"Authorization": f"Bearer {ValueStorage.jwt}"})
    url = f"{API}/{VER}/firstuser/add-admin"
    data = {
        "callsign": f"{ValueStorage.call_sign}",
    }
    LOGGER.debug("Fetching {}".format(url))
    response = await client.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert response.status == 403
    assert payload["detail"] == error_messages["FORBIDDEN"]


@pytest.mark.asyncio
async def test_check_invalid_token_code(
    session_with_testcas: aiohttp.ClientSession,
    error_messages: Dict[str, str],
) -> None:
    """Tests that we can check valid temp_admin_code"""
    client = session_with_testcas
    url = f"{API}/{VER}/firstuser/check-code?temp_admin_code={ValueStorage.code}"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert response.status == 403
    assert payload["detail"] == error_messages["CODE_ALREADY_USED"]
