"""Test the CRL fetching via Nginx and API container"""
import logging

import requests
import aiohttp
import pytest

from .conftest import DEFAULT_TIMEOUT, API, VER

LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_localmaeher_fetch_crl(
    session_with_testcas: aiohttp.ClientSession,
) -> None:
    """Test that we can get CRL via https api dns name"""
    client = session_with_testcas
    url = f"{API}/{VER}/utils/crl"
    LOGGER.debug("Fetching {}".format(url))
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    assert response.status == 200


@pytest.mark.asyncio
async def test_localmaeher_fetch_crl_sslfail() -> None:
    """Make sure the tls check fails when CA certs are not loaded in"""
    async with aiohttp.ClientSession() as client:
        url = f"{API}/{VER}/utils/crl"
        LOGGER.debug("Fetching {}".format(url))
        with pytest.raises(aiohttp.ClientConnectorCertificateError):
            response = await client.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()


def test_localhost_fetch_crl() -> None:
    """Test that we can get CRL via the direct localhost access to rasenmaeher"""
    url = f"http://127.0.0.1:8000/api/{VER}/utils/crl"
    response = requests.get(url, json=None, headers=None, verify=False, timeout=DEFAULT_TIMEOUT.total)
    assert response.status_code == 200
