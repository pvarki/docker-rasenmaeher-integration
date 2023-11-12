"""Tests enrollment invitecode validations"""
from typing import Dict
import logging

import aiohttp
import pytest

from ..conftest import DEFAULT_TIMEOUT, API, VER


LOGGER = logging.getLogger(__name__)
pytestmark = pytest.mark.skip(reason="somethings flaky")
# pylint: disable=R0801

# pylint: disable=too-few-public-methods
class ValueStorage:
    """Storage for invite_code generated in this testsuite"""

    invite_code = ""


@pytest.mark.asyncio
async def test_not_used_invite_code(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Tests that we can check invite_code is usable"""
    client = session_with_testcas
    url = f"{API}/{VER}/enrollment/invitecode?invitecode=asdölfjasfrei33424äxcxc"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["invitecode_is_active"] is False


@pytest.mark.asyncio
async def test_invalid_invite_code_enroll(
    admin_jwt_session: aiohttp.ClientSession,
    error_messages: Dict[str, str],
) -> None:
    """Tests that we cannot enroll non-existent work_id and invite_code"""
    client = admin_jwt_session
    url = f"{API}/{VER}/enrollment/invitecode/enroll"
    data = {
        "invite_code": "adf32423sfa432",
        "callsign": "asfsafasdfasdfa",
    }
    LOGGER.debug("Fetching {}".format(url))
    response = await client.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert response.status == 404
    assert payload["detail"] == error_messages["INVITECODE_NOT_VALID"]


@pytest.mark.asyncio
async def test_missing_invite_code_enroll(
    admin_jwt_session: aiohttp.ClientSession,
    error_messages: Dict[str, str],
) -> None:
    """Tests that we cannot enroll if invite_code is missing"""
    client = admin_jwt_session
    url = f"{API}/{VER}/enrollment/invitecode/enroll"
    data = {
        "invitecode": "adf32423sfa432",
        "callsign": "asfsafasdfasdfa",
    }
    LOGGER.debug("Fetching {}".format(url))
    response = await client.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert response.status == 422
    assert " ".join(payload["detail"][0]["loc"]) == error_messages["BODY_INVITE_CODE"]
    assert payload["detail"][0]["msg"] == error_messages["FIELD_REQUIRED"]
    assert payload["detail"][0]["type"] == error_messages["VALUE_MISSING"]
    assert payload["detail"][1]["msg"] == error_messages["EXTRA_FIELDS"]


@pytest.mark.asyncio
async def test_invalid_session_in_invite_code_create(
    session_with_invalid_tpjwt: aiohttp.ClientSession,
) -> None:
    """Tests that we cannot create new invite code invalid jwt"""
    client = session_with_invalid_tpjwt
    url = f"{API}/{VER}/enrollment/invitecode/create"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.post(url, json=None, timeout=DEFAULT_TIMEOUT)
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert response.status == 403


@pytest.mark.asyncio
async def test_valid_invite_code_create(
    admin_jwt_session: aiohttp.ClientSession,
) -> None:
    """Tests that we can create a new invite code using jwt"""
    client = admin_jwt_session
    url = f"{API}/{VER}/enrollment/invitecode/create"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.post(url, timeout=DEFAULT_TIMEOUT)
    LOGGER.debug("response={}".format(response))
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["invite_code"] != ""
    ValueStorage.invite_code = payload["invite_code"]


@pytest.mark.asyncio
async def test_validity_of_invalid_special_char_invite_code(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Tests that we can verify invalid invite code containing special characters"""
    client = session_with_testcas
    url = f"{API}/{VER}/enrollment/invitecode?invitecode=älåpåp234a'ät4grfdpgo"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["invitecode_is_active"] is False


@pytest.mark.asyncio
async def test_validity_of_invalid_invite_code(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Tests that we can verify invalid invite code"""
    client = session_with_testcas
    url = f"{API}/{VER}/enrollment/invitecode?invitecode=aerersd3434"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["invitecode_is_active"] is False


@pytest.mark.asyncio
async def test_validity_of_valid_invite_code(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Tests that we can verify valid invite code"""
    client = session_with_testcas
    url = f"{API}/{VER}/enrollment/invitecode?invitecode={ValueStorage.invite_code}"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["invitecode_is_active"] is True


@pytest.mark.asyncio
async def test_deactivate_valid_invite_code(
    admin_jwt_session: aiohttp.ClientSession,
) -> None:
    """Tests that we can deactivate valid invite code"""
    client = admin_jwt_session
    url = f"{API}/{VER}/enrollment/invitecode/deactivate"
    data = {
        "invite_code": f"{ValueStorage.invite_code}",
    }
    LOGGER.debug("Fetching {}".format(url))
    response = await client.put(url, json=data, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["success"] is True


@pytest.mark.asyncio
async def test_valid_invite_code_is_not_active(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Tests that we can verify valid invite code"""
    client = session_with_testcas
    url = f"{API}/{VER}/enrollment/invitecode?invitecode={ValueStorage.invite_code}"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["invitecode_is_active"] is False


@pytest.mark.asyncio
async def test_activate_valid_invite_code(
    admin_jwt_session: aiohttp.ClientSession,
) -> None:
    """Tests that we can activate valid invite code"""
    client = admin_jwt_session
    url = f"{API}/{VER}/enrollment/invitecode/activate"
    data = {
        "invite_code": f"{ValueStorage.invite_code}",
    }
    LOGGER.debug("Fetching {}".format(url))
    response = await client.put(url, json=data, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["success"] is True


@pytest.mark.asyncio
async def test_valid_invite_code_is_active(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Tests that we can verify valid invite code"""
    client = session_with_testcas
    url = f"{API}/{VER}/enrollment/invitecode?invitecode={ValueStorage.invite_code}"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["invitecode_is_active"] is True
