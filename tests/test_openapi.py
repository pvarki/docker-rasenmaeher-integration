"""Get the openapi.json from the API container via NGinx proxy"""

import logging

import aiohttp
import pytest

from .conftest import DEFAULT_TIMEOUT, API, VER, OPENAPI_VER

LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_get_openapi_json(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Fetch openapi spec and check certain things exist"""
    client = session_with_testcas
    url = f"{API}/openapi.json"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = await response.json()
    LOGGER.debug("payload={}".format(payload))
    assert payload["openapi"] == f"{OPENAPI_VER}"
    assert payload["info"] is not None
    assert payload["info"]["title"] == "FastAPI"
    assert payload["paths"] is not None
    assert payload["paths"][f"/api/{VER}/healthcheck"] is not None
    assert payload["components"] is not None
    assert payload["components"]["schemas"] is not None
    assert payload["components"]["schemas"]["CertificatesRequest"] is not None
    assert payload["components"]["securitySchemes"] is not None
    assert payload["components"]["securitySchemes"]["JWTBearer"] is not None
    # TODO: Read version from api submodule if we want to check the fastapi version
