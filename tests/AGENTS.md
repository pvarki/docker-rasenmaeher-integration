# AGENTS.md — tests (live-stack integration tests)

## Purpose
End-to-end integration tests that run against a **live, fully started RASENMAEHER stack**.
These are not unit tests — they make real HTTP calls to a running `rmlocal` or `rmdev`
environment. Use them to validate orchestration-level behavior: enrollment flows,
auth contracts, OpenAPI compliance, and CRL handling.

## Stack & Key Technologies
- **Language:** Python 3.11
- **Framework:** pytest + pytest-asyncio
- **HTTP client:** aiohttp (async)
- **Auth:** `multikeyjwt` for issuing test JWTs; mkcert CA certs for TLS validation
- **Target API:** `https://localmaeher.dev.pvarki.fi:4439/api` (default — override with `RM_API_BASE`)
- **Runtime fixtures:** `testcas/` and `testjwts/` are **empty in git** and populated at runtime by the compose `certscopy` and `jwtcopy` services

## Repository Layout
```
tests/
├── conftest.py            # Shared fixtures: sessions, JWT issuers, test data
├── test_crl_fetch.py      # CRL fetch and validation tests
├── test_openapi.py        # OpenAPI spec compliance checks
├── requirements.txt       # Test dependencies (aiohttp, pytest-asyncio, multikeyjwt, ...)
├── testcas/               # mkcert CA certs (populated at runtime by compose certscopy service)
├── testjwts/              # JWT keypairs (populated at runtime by compose jwtcopy service)
├── testscenarios/         # YAML/JSON test scenario definitions
└── validations/           # Expected response schemas / validation fixtures
```

## Development Setup
```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Override API base if not using the default localmaeher domain:
export RM_API_BASE="https://your.domain:4439/api"
```

The stack must be up before running any tests. Start it from the integration repo root:
```bash
rmlocal up   # or rmdev up
# Wait for all services to be healthy before running tests
```

## Running Tests
```bash
# Run all integration tests (from repo root)
pytest tests/ -v

# Run a specific test file
pytest tests/test_openapi.py -v

# Run tests matching a keyword
pytest tests/ -v -k "crl"

# Run with custom API base
RM_API_BASE="https://mystack.example.com:4439/api" pytest tests/ -v
```

## Key Fixtures (conftest.py)
| Fixture | Description |
|---|---|
| `session_with_testcas` | aiohttp session trusting the mkcert CA in `testcas/` |
| `tp_issuer` | JWT issuer using `testjwts/miniwerk.key` (mimics tilauspalvelu) |
| `session_with_tpjwt` | Session + valid `anon_admin_session` JWT attached |
| `admin_jwt_session` | Session + standard user JWT (`sub: pyteststuff`) |
| `session_with_invalid_tpjwt` | Session + JWT with a non-existent subject (for negative tests) |
| `call_sign_generator` | Random 8-char call sign for enrollment tests |
| `testdata` | Static dict with permit_str and user_hash values |
| `error_messages` | Dict of expected error message strings for assertion |

## Architecture Notes
**TLS trust:** Tests use mkcert CA certs from `testcas/` to trust the stack's self-signed
certificates. The `session_with_testcas` fixture loads all `*ca*.pem` files from that
directory. These files are **not committed** — they are copied in by the compose `certscopy`
service when the stack starts.

**JWT flow:** `tp_issuer` reads `testjwts/miniwerk.key` and issues signed JWTs that the
stack accepts as valid `tilauspalvelu` tokens. This key is **not committed** — it is copied
in by the compose `jwtcopy` service. The directories are empty in git intentionally.

**`RM_API_BASE` env var:** Defaults to `https://localmaeher.dev.pvarki.fi:4439/api`.
Override it if you are running the stack on a different domain or port.

## Common Agent Pitfalls
1. **Tests will fail immediately if the stack is not running.** There is no mock server.
   Always run `rmlocal up` and wait for all health checks to pass before running pytest.
2. **`testjwts/` and `testcas/` must match the running stack.** If the stack was rebuilt
   with new keys, regenerate or update the test fixtures to match.
3. **Windows users:** `conftest.py` sets `asyncio.WindowsSelectorEventLoopPolicy` to work
   around a known aiohttp/asyncio limitation. Do not remove it — it silently causes
   `RuntimeError: Event loop is closed` failures on Windows.
4. **Integration tests are stateful.** If an enrollment test creates a user, that user
   persists in the stack until the stack is wiped (`rmlocal down -v`). Running tests
   multiple times against the same stack may produce unexpected `Code already used` or
   `callsign already taken` errors.
5. **Do not move fixtures to individual test files.** The `conftest.py` at this level
   makes fixtures available to all tests. Keep shared fixtures here.

## Related Repos
- https://github.com/pvarki/docker-rasenmaeher-integration (orchestration root — must be running)
- https://github.com/pvarki/python-rasenmaeher-api (the main target API under test)
