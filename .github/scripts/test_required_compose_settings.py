"""Contract check for the Compose deployment lists."""

from required_compose_settings import extract, extract_subdomains


compose = {
    "x-settings": "${BARE} ${NEEDED?message} ${ALSO_NEEDED:?message} ${OPTIONAL:-foo} ${EMPTY_DEFAULT-} $${ESCAPED?no}",
    "services": {
        "web": {
            "ports": ["${WEB_PORT:-443}:443", "8091-8094:8091-8094", "8890:8890/udp"],
        }
    },
}
assert extract(compose) == (["ALSO_NEEDED", "BARE", "NEEDED"], ["443", "8091-8094", "8890/udp"])

environment = {"MW_PRODUCTS": " tak, kc, cryptpad, tak, "}
compose = {"services": {"miniwerk": {"environment": environment}}}
assert extract_subdomains(compose) == [
    "cryptpad",
    "kc",
    "mtls",
    "mtls.cryptpad",
    "mtls.kc",
    "mtls.sandbox.cryptpad",
    "mtls.tak",
    "rmcryptpad",
    "sandbox.cryptpad",
    "tak",
]
environment.update(MW_PRODUCTS=" tak, ", MW_SUBDOMAINS=" mtls, admin, mtls ")
assert extract_subdomains(compose) == ["admin", "admin.kc", "admin.tak", "kc", "mtls", "mtls.kc", "mtls.tak", "tak"]
environment.update(MW_PRODUCTS="")
assert extract_subdomains(compose) == ["admin", "admin.kc", "kc", "mtls", "mtls.kc"]
