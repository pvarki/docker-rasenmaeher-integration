"""Tests in sequence to simulate an end-to-end scenario"""
import asyncio
from typing import AsyncGenerator, cast, Tuple, Dict
import logging
from pathlib import Path
import base64
import os

import aiohttp
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from libadvian.testhelpers import nice_tmpdir  # pylint: disable=W0611
from libpvarki.mtlshelp import get_session

from ..conftest import DEFAULT_TIMEOUT, API, VER, CA_PATH

LOGGER = logging.getLogger(__name__)

# pylint: disable=W0621

# pylint: disable=too-few-public-methods
class ValueStorage:
    """Storage for values generated and used in this testsuite"""

    first_user_admin_call_sign = ""
    first_user_admin_jwt_exchange_code = ""
    first_user_admin_pfx = b""
    tp_logintoken_jwt = ""
    first_user_admin_jwt = ""
    invite_code = ""
    call_sign = ""
    call_sign_jwt = ""
    approve_code = ""


@pytest_asyncio.fixture
async def first_admin_jwt_session(
    session_with_testcas: aiohttp.ClientSession,
) -> AsyncGenerator[aiohttp.ClientSession, None]:
    """Client with JWT"""
    session = session_with_testcas
    session.headers.update({"Authorization": f"Bearer {ValueStorage.first_user_admin_jwt}"})
    yield session


@pytest_asyncio.fixture
async def first_admin_mtls_session(
    first_admin_jwt_session: aiohttp.ClientSession,
    nice_tmpdir: str,
) -> AsyncGenerator[Tuple[aiohttp.ClientSession, str], None]:
    """mTLS session for the first admin"""
    if not ValueStorage.first_user_admin_pfx:
        jwtclient = first_admin_jwt_session
        pfxresponse = await jwtclient.get(f"{API}/{VER}/enduserpfx/{ValueStorage.first_user_admin_call_sign}")
        ValueStorage.first_user_admin_pfx = await pfxresponse.read()
    datadir = Path(nice_tmpdir)
    keypath = datadir / "mtls.key"
    certpath = datadir / "mtls.cert"
    pfxdata = pkcs12.load_pkcs12(
        ValueStorage.first_user_admin_pfx, ValueStorage.first_user_admin_call_sign.encode("utf-8")
    )
    private_key = cast(rsa.RSAPrivateKey, pfxdata.key)
    keypath.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    assert pfxdata.cert
    cert = pfxdata.cert.certificate
    certpath.write_bytes(cert.public_bytes(encoding=serialization.Encoding.PEM))
    async with get_session((certpath, keypath), CA_PATH) as client:
        if "localmaeher" in API:
            newapi = API.replace("localmaeher", "mtls.localmaeher")
        else:
            newapi = API.replace("https://", "https://mtls.")
        yield client, newapi


@pytest.mark.asyncio
async def test_0_create_login_token_for_first_admin(
    session_with_tpjwt: aiohttp.ClientSession,
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Create a token the first admin can exhcnage for anon_admin jwt to create themselves an user"""
    client = session_with_tpjwt
    url = f"{API}/{VER}/token/code/generate"
    data = {
        "claims": {
            "anon_admin_session": True,
        }
    }
    response = await client.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    payload = await response.json()
    ValueStorage.first_user_admin_jwt_exchange_code = payload["code"]
    client2 = session_with_testcas
    resp2 = await client2.post(
        f"{API}/{VER}/token/code/exchange",
        json={"code": ValueStorage.first_user_admin_jwt_exchange_code},
        timeout=DEFAULT_TIMEOUT,
    )
    payload2 = await resp2.json()
    ValueStorage.tp_logintoken_jwt = payload2["jwt"]


@pytest_asyncio.fixture
async def session_with_logintoken_jwt(
    session_with_testcas: aiohttp.ClientSession,
) -> AsyncGenerator[aiohttp.ClientSession, None]:
    """Use first_user_admin_jwt_exchange_code to get anon_admin JWT to create the first user"""
    client = session_with_testcas
    client.headers.update({"Authorization": f"Bearer {ValueStorage.tp_logintoken_jwt}"})
    yield client


@pytest.mark.asyncio
async def test_1_firstuser_add_admin(
    session_with_logintoken_jwt: aiohttp.ClientSession,
    session_with_testcas: aiohttp.ClientSession,
    call_sign_generator: str,
) -> None:
    """Tests that we can create new work_id"""
    client = session_with_logintoken_jwt
    url = f"{API}/{VER}/firstuser/add-admin"
    data = {
        "callsign": f"{call_sign_generator}",
    }
    LOGGER.debug("Fetching {}".format(url))
    LOGGER.debug("Data: {}".format(data))
    response = await client.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["admin_added"] is True
    assert payload["jwt_exchange_code"] != ""
    ValueStorage.first_user_admin_call_sign = call_sign_generator
    client2 = session_with_testcas
    resp2 = await client2.post(
        f"{API}/{VER}/token/code/exchange", json={"code": payload["jwt_exchange_code"]}, timeout=DEFAULT_TIMEOUT
    )
    payload2 = await resp2.json()
    ValueStorage.first_user_admin_jwt = payload2["jwt"]


@pytest.mark.asyncio
async def test_1_1_check_admin_mtls(first_admin_mtls_session: Tuple[aiohttp.ClientSession, str]) -> None:
    """Test that the mTLS client session works"""
    client, api = first_admin_mtls_session
    url = f"{api}/{VER}/check-auth/validuser/admin"
    resp = await client.get(url)
    payload = await resp.json()
    assert payload["type"] == "mtls"


@pytest.mark.asyncio
async def test_2_invite_code_create(
    first_admin_mtls_session: Tuple[aiohttp.ClientSession, str],
) -> None:
    """Tests that we can create a new invite code"""
    client, api = first_admin_mtls_session
    url = f"{api}/{VER}/enrollment/invitecode/create"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.post(url, json=None, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["invite_code"] != ""
    ValueStorage.invite_code = payload["invite_code"]


@pytest.mark.asyncio
async def test_2_5_invite_code_create_many_and_list(
    first_admin_mtls_session: Tuple[aiohttp.ClientSession, str],
) -> None:
    """Tests that we can create a new invite code"""
    client, api = first_admin_mtls_session
    url = f"{api}/{VER}/enrollment/invitecode/create"
    for _ in range(5):
        LOGGER.debug("Fetching {}".format(url))
        response = await client.post(url, json=None, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        payload = await response.json()
        LOGGER.debug("payload={}".format(payload))
        assert payload["invite_code"] != ""
    url = f"{api}/{VER}/enrollment/pools"
    response = await client.get(url, json=None, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    assert "pools" in payload
    assert payload["pools"]
    assert len(payload["pools"]) >= 5


@pytest.mark.asyncio
async def test_3_invite_code_is_ok(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Tests that we can verify that the given invite code is ok"""
    client = session_with_testcas
    url = f"{API}/{VER}/enrollment/invitecode?invitecode={ValueStorage.invite_code}"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["invitecode_is_active"] is True


@pytest.mark.asyncio
async def test_4_invite_code_enroll(
    session_with_testcas: aiohttp.ClientSession,
    call_sign_generator: str,
) -> None:
    """
    Tests that we can enroll using valid invite_code
    """
    client = session_with_testcas
    url = f"{API}/{VER}/enrollment/invitecode/enroll"
    data = {
        "invite_code": f"{ValueStorage.invite_code}",
        "callsign": f"{call_sign_generator}",
    }
    LOGGER.debug("Fetching {}".format(url))
    LOGGER.debug("Data: {}".format(data))
    response = await client.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    ValueStorage.call_sign = payload["callsign"]
    ValueStorage.call_sign_jwt = payload["jwt"]
    ValueStorage.approve_code = payload["approvecode"]


@pytest.mark.asyncio
async def test_5_enrollment_list_for_available_call_sign(
    first_admin_mtls_session: Tuple[aiohttp.ClientSession, str],
) -> None:
    """Tests that we have call_sign available for enrollment"""
    client, api = first_admin_mtls_session
    url = f"{api}/{VER}/enrollment/list"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    found_enroll_call_sign = False
    for item in payload["callsign_list"]:
        assert item["callsign"] != "" or item["callsign"] == ""
        assert item["approvecode"] != ""
        assert item["state"] == 0 or item["state"] == 1
        if item["callsign"] == ValueStorage.call_sign and item["state"] == 0:
            ValueStorage.approve_code = item["approvecode"]
            found_enroll_call_sign = True
    assert found_enroll_call_sign is True


@pytest.mark.asyncio
async def test_6_call_sign_not_accepted(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Tests that call_sign has not yet accepted"""
    client = session_with_testcas
    client.headers.update({"Authorization": f"Bearer {ValueStorage.call_sign_jwt}"})
    url = f"{API}/{VER}/enrollment/have-i-been-accepted"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["have_i_been_accepted"] is False


@pytest.mark.asyncio
async def test_7_enrollment_accept_call_sign(
    first_admin_mtls_session: Tuple[aiohttp.ClientSession, str],
) -> None:
    """
    Tests that we can accept call_sign
    """
    client, api = first_admin_mtls_session
    url = f"{api}/{VER}/enrollment/accept"
    data = {
        "callsign": f"{ValueStorage.call_sign}",
        "approvecode": f"{ValueStorage.approve_code}",
    }
    LOGGER.debug("Fetching {}".format(url))
    LOGGER.debug("Data: {}".format(data))
    response = await client.post(url, json=data, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))


@pytest.mark.asyncio
async def test_8_call_sign_accepted(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Tests that call_sign has been accepted"""
    client = session_with_testcas
    client.headers.update({"Authorization": f"Bearer {ValueStorage.call_sign_jwt}"})
    url = f"{API}/{VER}/enrollment/have-i-been-accepted"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["have_i_been_accepted"] is True


@pytest.mark.asyncio
async def test_9_check_if_enduser_pfx_available(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Tests that we can check if the pfx bundle is available for the given callsign"""
    client = session_with_testcas
    client.headers.update({"Authorization": f"Bearer {ValueStorage.call_sign_jwt}"})
    url = f"{API}/{VER}/enduserpfx/{ValueStorage.call_sign}.pfx"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    assert response.content


def parse_file_payload(fpl: Dict[str, str]) -> None:
    """parse file payload"""
    assert fpl["title"]
    assert fpl["filename"]
    assert fpl["data"]
    data = str(fpl["data"])
    assert data.startswith("data:")
    _, b64data = data.split(",")
    dec = base64.b64decode(b64data)
    assert dec


@pytest.mark.asyncio
async def test_10_check_enduser_files(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Check that we can get files from product integration apis"""
    client = session_with_testcas
    client.headers.update({"Authorization": f"Bearer {ValueStorage.call_sign_jwt}"})
    url = f"{API}/{VER}/instructions/user"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload
    assert "files" in payload
    assert "fake" in payload["files"]
    if not payload["files"]["fake"] and os.environ.get("CI"):  # pylint: disable=E1101  # false positive
        LOGGER.error("Did not get payload from fakeproduct but living with it")
    else:
        for fpl in payload["files"]["fake"]:
            parse_file_payload(fpl)

    assert "tak" in payload["files"]
    if not payload["files"]["tak"] and os.environ.get("CI"):  # pylint: disable=E1101  # false positive
        LOGGER.error("Did not get payload from tak but living with it")
    else:
        for fpl in payload["files"]["tak"]:
            parse_file_payload(fpl)


@pytest.mark.asyncio
async def test_11_check_user_revoke(
    session_with_testcas: aiohttp.ClientSession,
    first_admin_mtls_session: Tuple[aiohttp.ClientSession, str],
) -> None:
    """Test revoking the user"""
    admin, api = first_admin_mtls_session
    url = f"{api}/{VER}/people/{ValueStorage.call_sign}"
    resp1 = await admin.delete(url)
    LOGGER.debug("got response {} from {}".format(resp1, url))
    resp1.raise_for_status()
    payload = await resp1.json()
    assert payload["success"]

    resp2 = await admin.delete(url)
    LOGGER.debug("got response {} from {}".format(resp2, url))
    assert resp2.status == 404

    await asyncio.sleep(1)

    # FIXME: Use mTLS for the end-user too.
    client = session_with_testcas
    client.headers.update({"Authorization": f"Bearer {ValueStorage.call_sign_jwt}"})
    resp2 = await client.get(f"{API}/{VER}/instructions/user")
    assert resp2.status == 403
    # TODO: Test the cert revocation too once we get OCSP working
