"""Regression tests for CryptPad integration glue files."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NGINX_TEMPLATE = REPO_ROOT / "nginx" / "templates_consolidated" / "default.conf.template"
RMAPI_CONTAINER_INIT = REPO_ROOT / "api" / "docker" / "container-init.sh"
LOCAL_COMPOSE = REPO_ROOT / "docker-compose-local.yml"
MAIN_COMPOSE = REPO_ROOT / "docker-compose.yml"
CRYPTPAD_SSO_CONFIG = REPO_ROOT / "cryptpad" / "config" / "sso.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_products_vhost_is_tls_default_server() -> None:
    """Keep non-SNI traffic on the shared product vhost."""
    template = _read(NGINX_TEMPLATE)
    assert "listen ${NGINX_HTTPS_PORT} ssl default_server;" in template


def test_rmcryptpad_proxy_forwards_client_verify_header() -> None:
    """rmcryptpad expects the verification result header on protected routes."""
    template = _read(NGINX_TEMPLATE)
    _, rmcryptpad_server = template.split("server_name rmcryptpad.${NGINX_HOST};", maxsplit=1)
    rmcryptpad_server, _ = rmcryptpad_server.split("\nserver {", maxsplit=1)
    assert "proxy_set_header X-SSL-Client-Verify $ssl_client_verify;" in rmcryptpad_server


def test_rmapi_local_bootstrap_maps_rmcryptpad_hostname() -> None:
    """Local rmapi calls need a host mapping for the CryptPad product API host."""
    bootstrap = _read(RMAPI_CONTAINER_INIT)
    assert "rmcryptpad.localmaeher.dev.pvarki.fi" in bootstrap


def test_local_compose_keeps_cryptpad_manifest_hosts_explicit() -> None:
    """MiniWerk needs explicit host overrides for CryptPad's non-standard hostnames."""
    compose = _read(LOCAL_COMPOSE)
    assert 'MW_CRYPTPAD__API_HOST: "rmcryptpad"' in compose
    assert 'MW_CRYPTPAD__USER_HOST: "mtls.cryptpad"' in compose


def test_main_compose_keeps_cryptpad_manifest_hosts_explicit() -> None:
    """Production compose should generate the same CryptPad manifest hosts."""
    compose = _read(MAIN_COMPOSE)
    assert 'MW_CRYPTPAD__API_HOST: "rmcryptpad"' in compose
    assert 'MW_CRYPTPAD__USER_HOST: "mtls.cryptpad"' in compose


def test_cryptpad_oidc_discovery_uses_internal_rmcryptpad_service() -> None:
    """CryptPad server-side issuer discovery must not depend on localhost-pointing FQDN DNS."""
    local_compose = _read(LOCAL_COMPOSE)
    main_compose = _read(MAIN_COMPOSE)
    sso_config = _read(CRYPTPAD_SSO_CONFIG)
    assert "CPAD_SSO_DISCOVERY_URL: http://rmcryptpad:8000" in local_compose
    assert "CPAD_SSO_DISCOVERY_URL: http://rmcryptpad:8000" in main_compose
    assert "process.env.CPAD_SSO_DISCOVERY_URL" in sso_config
