"""Check MAS can reach the mTLS proxy when registering its OIDC client."""

import json
import os
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
    assert mas["depends_on"]["matrixrmapi"]["condition"] == "service_started"
    credentials = next(volume for volume in mas["volumes"] if volume["target"] == "/matrix_data")
    assert credentials["source"] == "matrix_data"
    assert credentials["read_only"] is True


@pytest.mark.parametrize("missing", [None, "public/mtlsclient.pem", "private/mtlsclient.key"])
def test_mas_bootstrap_identity(tmp_path: Path, missing: str | None) -> None:
    """Require both credentials and link them without copying stale identities."""
    script = (REPO_ROOT / "mas_runtime" / "prepare_manifest.sh").read_text(encoding="utf-8")
    for directory in ("matrix_data", "data", "pvarki"):
        (tmp_path / directory).mkdir()
        script = script.replace(f"/{directory}", str(tmp_path / directory))
    # Stop at the service boundary: this test runs bootstrap, not the MAS server.
    script = script.replace("exec /usr/bin/tini -- /opt/mas/scripts/mas-entrypoint.sh", "exit 0")
    for filename in ("public/mtlsclient.pem", "private/mtlsclient.key"):
        path = tmp_path / "matrix_data" / filename
        path.parent.mkdir()
        if filename != missing:
            path.write_text("test identity", encoding="utf-8")
    (tmp_path / "pvarki" / "kraftwerk-init.json").write_text("{}", encoding="utf-8")
    result = subprocess.run(
        ["bash", "-c", script],
        env={**os.environ, "KCDOMAIN": "kc.example.test", "KCREALM": "test"},
        capture_output=True,
        text=True,
        check=False,
    )
    if missing:
        assert result.returncode != 0
        assert "Matrix mTLS identity is not ready" in result.stderr
        return
    assert result.returncode == 0, result.stderr
    for filename in ("public/mtlsclient.pem", "private/mtlsclient.key"):
        link = tmp_path / "data" / filename
        source = tmp_path / "matrix_data" / filename
        assert link.is_symlink()
        assert link.resolve() == source
        source.write_text("renewed identity", encoding="utf-8")
        assert link.read_text(encoding="utf-8") == "renewed identity"
