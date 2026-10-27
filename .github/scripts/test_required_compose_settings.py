"""Contract check for the Compose deployment lists."""

from required_compose_settings import extract


compose = {
    "x-settings": "${BARE} ${NEEDED?message} ${ALSO_NEEDED:?message} ${OPTIONAL:-foo} ${EMPTY_DEFAULT-} $${ESCAPED?no}",
    "services": {
        "web": {
            "ports": ["${WEB_PORT:-443}:443", "8091-8094:8091-8094", "8890:8890/udp"],
        }
    },
}
assert extract(compose) == (["ALSO_NEEDED", "BARE", "NEEDED"], ["443", "8091-8094", "8890/udp"])
