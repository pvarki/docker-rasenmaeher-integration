"""The conftest.py provides fixtures for the entire directory.
Fixtures defined can be used by any test in that package without needing to import them."""
from typing import Dict, AsyncGenerator
import platform
import logging
import string
import random
from pathlib import Path
import ssl
import asyncio
import uuid
import os

import aiohttp
import pytest
import pytest_asyncio
from libadvian.logging import init_logging
from multikeyjwt import Issuer


init_logging(logging.DEBUG)
LOGGER = logging.getLogger(__name__)
CA_PATH = Path(__file__).parent / "testcas"
JWT_PATH = Path(__file__).parent / "testjwts"
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=25.0)
OPENAPI_VER = "3.1.0"
API = os.environ.get("RM_API_BASE", "https://localmaeher.dev.pvarki.fi:4439/api")  # pylint: disable=E1101
VER = "v1"

# pylint: disable=W0621

# mypy: disable-error-code="attr-defined"
if platform.system() == "Windows":
    # Workaround for 'RuntimeError: Event Loop is closed'
    # https://github.com/encode/httpx/issues/914
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture
async def session_with_testcas() -> AsyncGenerator[aiohttp.ClientSession, None]:
    """aiohttp session with the mkcert CA enabled"""
    ssl_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    LOGGER.info("Loading local CA certs from {}".format(CA_PATH))
    for cafile in CA_PATH.glob("*ca*.pem"):
        if not cafile.is_file():
            continue
        LOGGER.debug("Adding cert {}".format(cafile))
        ssl_ctx.load_verify_locations(str(cafile))
    conn = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=conn) as session:
        yield session


@pytest.fixture(scope="session")
def tp_issuer() -> Issuer:
    """Issuer initialized with miniwerk key"""
    keyfile = JWT_PATH / "miniwerk.key"
    issuer = Issuer(
        privkeypath=keyfile,
        keypasswd=None,
    )
    return issuer


@pytest_asyncio.fixture
async def session_with_tpjwt(
    session_with_testcas: aiohttp.ClientSession, tp_issuer: Issuer
) -> AsyncGenerator[aiohttp.ClientSession, None]:
    """Add 'tilauspalvelu' single use JWT to session"""
    session = session_with_testcas
    token = tp_issuer.issue(
        {
            "sub": "tpadminsession",
            "anon_admin_session": True,
            "nonce": str(uuid.uuid4()),
        }
    )
    session.headers.update({"Authorization": f"Bearer {token}"})
    yield session


@pytest_asyncio.fixture
async def admin_jwt_session(
    session_with_testcas: aiohttp.ClientSession, tp_issuer: Issuer
) -> AsyncGenerator[aiohttp.ClientSession, None]:
    """JWT session for existing test user"""
    session = session_with_testcas
    token = tp_issuer.issue(
        {
            "sub": "pyteststuff",
        }
    )
    session.headers.update({"Authorization": f"Bearer {token}"})
    yield session


@pytest_asyncio.fixture
async def session_with_invalid_tpjwt(
    session_with_testcas: aiohttp.ClientSession, tp_issuer: Issuer
) -> AsyncGenerator[aiohttp.ClientSession, None]:
    """Add 'tilauspalvelu' single use JWT to session"""
    session = session_with_testcas
    token = tp_issuer.issue(
        {
            "sub": "invalidasdfar33",
            "anon_admin_session": True,
            "nonce": str(uuid.uuid4()),
        }
    )
    session.headers.update({"Authorization": f"Bearer {token}"})
    yield session


@pytest.fixture
def call_sign_generator() -> str:
    """Return random work_id"""
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))


# FIXME: rename this, or if only needed in one test file=module, move it there
@pytest.fixture
def testdata() -> Dict[str, str]:
    """Return values needed for tests"""
    return {
        "permit_str": "PaulinTaikaKaulinOnKaunis_PaulisMagicPinIsBuuutiful!11!1",
        "user_hash": "PerPerPerjantaiPulloParisee",
    }


# FIXME: if duplicate firstuser, it returns only HTTP Error 500
@pytest.fixture
def error_messages() -> Dict[str, str]:
    """Return values needed for verifying error messages in tests"""
    return {
        "NO_USERS_FOUND": "No users found...",
        "FIRSTUSER_API_IS_DISABLED": "/firstuser API is disabled",
        "NOT_FOUND": "Not Found",
        "INVITECODE_NOT_VALID": "Not found",
        "WORK_ID_NOT_FOUND": "Not found",
        "EXTRA_FIELDS": "extra fields not permitted",
        "FIELD_REQUIRED": "field required",
        "VALUE_MISSING": "value_error.missing",
        "BODY_TEMP_ADMIN_CODE": "body temp_admin_code",
        "BODY_INVITE_CODE": "body invite_code",
        "FORBIDDEN": "Forbidden",
        "CODE_ALREADY_USED": "Code already used",
        "INVITECODE_TAKEN": "Error. callsign/callsign already taken.",
    }
