"""Check MAS can reach the mTLS proxy when registering its OIDC client."""

import json
from pathlib import Path
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("filename", ["docker-compose-local.yml", "docker-compose.yml"])
def test_mas_registration_proxy(filename: str) -> None:
    """Resolve the manifest's mTLS hostname internally and wait for its proxy."""
    result = subprocess.run(
        ["docker", "compose", "-f", str(REPO_ROOT / filename), "config", "--no-interpolate", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    services = json.loads(result.stdout)["services"]
    mas = services["mas"]
    assert "intranet" in mas["networks"]
    assert mas["environment"]["MTLS_DOMAIN"] in services["rmnginx"]["networks"]["intranet"]["aliases"]
    assert mas["depends_on"]["rmnginx"]["condition"] == "service_healthy"
