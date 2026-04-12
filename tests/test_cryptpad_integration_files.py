"""Regression tests for CryptPad integration glue files."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NGINX_TEMPLATE = REPO_ROOT / "nginx" / "templates_consolidated" / "default.conf.template"
RMAPI_CONTAINER_INIT = REPO_ROOT / "api" / "docker" / "container-init.sh"
LOCAL_COMPOSE = REPO_ROOT / "docker-compose-local.yml"
MAIN_COMPOSE = REPO_ROOT / "docker-compose.yml"
CRYPTPAD_SSO_CONFIG = REPO_ROOT / "cryptpad" / "config" / "sso.js"
CRYPTPAD_ENTRYPOINT = REPO_ROOT / "cryptpad" / "docker" / "cryptpad" / "docker-entrypoint.sh"


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


def test_rmapi_submodule_stays_free_of_cryptpad_specific_local_host_hacks() -> None:
    """The integration must not require local-only rmcryptpad host edits in the api submodule."""
    bootstrap = _read(RMAPI_CONTAINER_INIT)
    assert "rmcryptpad.localmaeher.dev.pvarki.fi" not in bootstrap


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


def test_main_compose_cryptpad_runtime_urls_are_domain_parameterized() -> None:
    """Real deployments must build CryptPad URLs from SERVER_DOMAIN, not from local-only hostnames."""
    compose = _read(MAIN_COMPOSE)
    cryptpad_section = compose.split("###################\n# Begin: CryptPad #\n###################", maxsplit=1)[1]
    cryptpad_section = cryptpad_section.split("#################\n# End: CryptPad #\n#################", maxsplit=1)[0]
    assert (
        "CPAD_MAIN_DOMAIN: https://mtls.cryptpad.${SERVER_DOMAIN:?domain must be defined}:"
        "${NGINX_HTTPS_PRODUCT_PORT:-4626}" in cryptpad_section
    )
    assert (
        "CPAD_SANDBOX_DOMAIN: https://mtls.sandbox.cryptpad.${SERVER_DOMAIN:?domain must be defined}:"
        "${NGINX_HTTPS_PRODUCT_PORT:-4626}" in cryptpad_section
    )
    assert "CPAD_SSO_ISSUER: https://rmcryptpad.${SERVER_DOMAIN:?domain must be defined}" in cryptpad_section
    assert (
        "RMCRYPTPAD_PUBLIC_URL: https://mtls.cryptpad.${SERVER_DOMAIN:?domain must be defined}:"
        "${NGINX_HTTPS_PRODUCT_PORT:-4626}" in cryptpad_section
    )
    assert (
        "RMCRYPTPAD_PUBLIC_SANDBOX_URL: https://mtls.sandbox.cryptpad.${SERVER_DOMAIN:?domain must be defined}:"
        "${NGINX_HTTPS_PRODUCT_PORT:-4626}" in cryptpad_section
    )
    assert "RMCRYPTPAD_OIDC_ISSUER: https://rmcryptpad.${SERVER_DOMAIN:?domain must be defined}" in cryptpad_section
    assert "cryptpad.localhost" not in cryptpad_section


def test_cryptpad_oidc_discovery_uses_internal_rmcryptpad_service() -> None:
    """CryptPad server-side issuer discovery must not depend on localhost-pointing FQDN DNS."""
    local_compose = _read(LOCAL_COMPOSE)
    main_compose = _read(MAIN_COMPOSE)
    sso_config = _read(CRYPTPAD_SSO_CONFIG)
    assert "CPAD_SSO_DISCOVERY_URL: http://rmcryptpad:8000" in local_compose
    assert "CPAD_SSO_DISCOVERY_URL: http://rmcryptpad:8000" in main_compose
    assert "process.env.CPAD_SSO_DISCOVERY_URL" in sso_config


def test_productsnginx_advertises_cryptpad_fqdns_on_docker_networks() -> None:
    """CryptPad callback exchange uses public OIDC endpoint URLs and needs them resolvable in-container."""
    local_compose = _read(LOCAL_COMPOSE)
    main_compose = _read(MAIN_COMPOSE)
    for compose in (local_compose, main_compose):
        assert '- "rmcryptpad.${SERVER_DOMAIN' in compose
        assert '- "mtls.cryptpad.${SERVER_DOMAIN' in compose
        assert '- "mtls.sandbox.cryptpad.${SERVER_DOMAIN' in compose


def test_cryptpad_uses_shared_product_port_in_compose_and_nginx() -> None:
    """CryptPad should share the standard product ingress port instead of reserving its own."""
    local_compose = _read(LOCAL_COMPOSE)
    main_compose = _read(MAIN_COMPOSE)
    template = _read(NGINX_TEMPLATE)
    for compose in (local_compose, main_compose):
        assert "NGINX_HTTPS_CRYPTPAD_PORT" not in compose
        assert "NGINX_CRYPTPAD_PORT" not in compose
        assert "${NGINX_HTTPS_PRODUCT_PORT:-4626}:${NGINX_HTTPS_PRODUCT_PORT:-4626}" in compose
    assert "listen ${NGINX_CRYPTPAD_PORT} ssl;" not in template


def test_cryptpad_trusts_stack_ca_for_oidc_callback_exchange() -> None:
    """CryptPad's Node worker must trust the local stack CA when it calls public OIDC HTTPS endpoints."""
    local_compose = _read(LOCAL_COMPOSE)
    main_compose = _read(MAIN_COMPOSE)
    for compose in (local_compose, main_compose):
        assert "NODE_EXTRA_CA_CERTS: /tmp/cryptpad-extra-ca.pem" in compose
        assert "- ca_public:/ca_public" in compose


def test_cryptpad_entrypoint_builds_extra_ca_bundle_from_stack_cas() -> None:
    """The runtime entrypoint should combine all local stack trust roots into the Node extra CA bundle."""
    entrypoint = _read(CRYPTPAD_ENTRYPOINT)
    assert "/ca_public/miniwerk_ca.pem" in entrypoint
    assert "/ca_public/ca_chain.pem" in entrypoint
    assert "cryptpad-extra-ca.pem" in entrypoint
