"""Tests in sequence to simulate an end-to-end scenario"""
from typing import Tuple, Dict
import logging

import aiohttp
import pytest

from ..conftest import DEFAULT_TIMEOUT

LOGGER = logging.getLogger(__name__)

# pylint: disable=too-few-public-methods
class ValueStorage:
    """Storage for values generated and used in this testsuite"""

    work_id = ""
    jwt = ""
    work_id_hash = ""
    invite_code = ""


@pytest.mark.asyncio
async def test_1_firstuser_add_admin(
    session_with_tpjwt: aiohttp.ClientSession,
    localmaeher_api: Tuple[str, str],
    work_id_generator: str,
) -> None:
    """Tests that we can create new work_id"""
    client = session_with_tpjwt
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/firstuser/add-admin"
    data = {
        "work_id": f"{work_id_generator}",
    }
    LOGGER.debug("Fetching {}".format(url))
    LOGGER.debug("Data: {}".format(data))
    response = await client.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["admin_added"] is True
    assert payload["jwt_exchange_code"] != ""
    ValueStorage.jwt = payload["jwt_exchange_code"]
    ValueStorage.work_id = work_id_generator


@pytest.mark.asyncio
async def test_2_enrollment_list_for_available_work_id(
    session_with_tpjwt: aiohttp.ClientSession,
    localmaeher_api: Tuple[str, str],
    work_id_generator: str,
) -> None:
    """Tests that we have work_id available for enrollment"""
    client = session_with_tpjwt
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/list"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    work_id_to_enroll = False
    for item in payload["work_id_list"]:
        assert item["work_id"] != ""
        assert item["work_id_hash"] != ""
        assert item["state"] != ""
        if item["work_id"] == ValueStorage.work_id and item["accepted"] == "yes":
            ValueStorage.work_id_hash = item["work_id_hash"]
            work_id_to_enroll = True
    assert work_id_to_enroll is True


@pytest.mark.asyncio
async def test_3_invite_code_create(
    session_with_tpjwt: aiohttp.ClientSession,
    localmaeher_api: Tuple[str, str],
) -> None:
    """Tests that we can create a new invite code"""
    client = session_with_tpjwt
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/invitecode/create"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.post(url, json=None, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["invite_code"] != ""
    ValueStorage.invite_code = payload["invite_code"]


@pytest.mark.asyncio
async def test_4_invite_code_is_ok(
    session_with_testcas: aiohttp.ClientSession,
    localmaeher_api: Tuple[str, str],
) -> None:
    """Tests that we can verify that the given invite code is ok"""
    client = session_with_testcas
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/invitecode?invitecode={ValueStorage.invite_code}"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["invitecode_is_active"] is True


@pytest.mark.asyncio
@pytest.mark.skip(reason="Fails due to not checking correct things")
async def test_5_invite_code_enroll(
    session_with_tpjwt: aiohttp.ClientSession,
    localmaeher_api: Tuple[str, str],
) -> None:
    """
    Tests that we can enroll an empty (accepted == '') work_id
    and active (see above test) invite_code
    """
    client = session_with_tpjwt
    url = f"{localmaeher_api[0]}/{localmaeher_api[1]}/enrollment/invitecode/enroll"
    data = {
        "invite_code": f"{ValueStorage.invite_code}",
        "work_id": f"{ValueStorage.work_id}",
    }
    LOGGER.debug("Fetching {}".format(url))
    LOGGER.debug("Data: {}".format(data))
    response = await client.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    #response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert response.status == 202

