# AGENTS.md — docker-rasenmaeher-integration

## Purpose
This is the **orchestration root** for Deploy App (codename RASENMAEHER): a Docker Compose
mono-integration that assembles 15+ microservices into a unified, mission-critical identity and
deployment platform. All service directories are git submodules; this repo only owns the compose files, nginx configs, pg_init
scripts, and integration tests.

**This file is the authoritative starting point for AI agents working anywhere in this repo.**
Read it first; then open the `AGENTS.md` inside the specific submodule directory you are working in.

## Supported Platforms
- **Linux** — fully tested, primary development platform
- **macOS** — fully tested
- **Windows** — NOT tested; known issues with Docker SSH agent forwarding and volume paths.
  If you must use Windows, use WSL2 with the Docker Desktop WSL2 backend — do not use Git Bash.

## Stack & Key Technologies
- **Orchestration:** Docker Compose (three variants: production, local, dev)
- **Languages across services:** Python 3.11, Go, Java, TypeScript, Nginx
- **Database:** PostgreSQL 15 + PostGIS 3.4 (central, shared across all services)
- **Identity:** Keycloak 23 (OIDC/OAuth2) + OpenLDAP (user federation)
- **PKI:** cfssl (internal CA) + miniwerk (Let's Encrypt / mkcert orchestrator)
- **Reverse proxy:** Nginx with gomplate templating, mTLS enforcement
- **Versioning:** bump-my-version (`bump2version`), version tracked in `version.yml`
- **CI:** GitHub Actions (`.github/workflows/build.yml`)

## Projects

### Root orchestration files
- Docker Compose orchestration root for the whole platform
- Owns `docker-compose.yml`, `docker-compose-local.yml`, `docker-compose-dev.yml`, `.env` template handling, shared versioning, and top-level integration behavior
- **Owns**: compose wiring, service dependencies, networks, shared volumes, integration test entrypoints
- **Does not own**: service internals inside submodules

### `api/` - Core REST API and identity broker
- Main backend for enrollment, auth checks, user lifecycle, product description aggregation, and proxying toward product integrations
- Sits between the UI and product services in browser-facing flows
- **Dependencies**: postgres, keycloak, nginx, product integrations

### `uiv2/` - Main web frontend shell
- React/Vite frontend for enrollment, admin tools, product cards, and hosting modular product UI
- Loads products dynamically through `rmapi` and `/ui/<shortname>/...`
- **Dependencies**: `api/`, nginx, theme assets, product UI bundles exposed through shared volumes

### `keycloak/` - IAM and federation layer
- Keycloak plus OpenLDAP integration for authentication and identity management
- Provides the OIDC/auth backbone used by the rest of the platform
- **Dependencies**: postgres, OpenLDAP, init scripts, cfssl/miniwerk-provided cert material

### `miniwerk/` - Certificate orchestrator
- Handles Let's Encrypt or mkcert flows and writes per-product manifests into shared Kraftwerk volumes
- Bootstraps domains, certs, and other service startup material for the stack
- **Dependencies**: shared Docker volumes, DNS, external ACME or local cert tooling

### `cfssl/` - Internal CA and OCSP
- Internal certificate authority, certificate issuance support, and OCSP/CRL material for mTLS flows
- Critical for trust between internal services and product API access
- **Dependencies**: miniwerk startup, nginx, product clients, `rmapi`

### `nginx/` - Reverse proxy and TLS edge
- Runs the main public ingress and the product API ingress
- Terminates TLS, enforces mTLS on product-side traffic, and exposes browser-facing routes for UI, API, and shared product assets
- **Dependencies**: cert material from miniwerk/cfssl, all upstream services, compose/env wiring from this root repo

### `pg_init/` - Database schema ownership
- Owns shared PostgreSQL initialization and schema creation across the platform
- First place to inspect when a service appears to have a broken DB contract
- **Dependencies**: postgres container startup

### `kw_product_init/` - Product certificate bootstrap
- Go-based init utility that prepares per-product certificate/config material
- Part of the early startup chain for product onboarding
- **Dependencies**: miniwerk, cfssl, shared volumes

### `kc_client_init/` - Keycloak client bootstrap
- Go-based init utility that provisions Keycloak clients needed by platform services
- Used during startup and environment initialization
- **Dependencies**: keycloak readiness, compose env config

### Product integration services
Each product integration has its own submodule with a full `AGENTS.md`. Open the relevant
submodule directory to read its purpose, architecture, and development instructions.
All product integrations follow the same pattern: they implement the lifecycle callback API,
expose a `/api/v2/description/{language}` endpoint, and optionally serve UI assets into the
`ui_files` shared volume. See `fpintegration/` for the canonical reference implementation
and `uiv2/AGENTS.md` for the full Modular UI Integration Spec.

### Product platforms and support services

#### `takserver/` - TAK platform
- Multi-container TAK Server stack managed as a submodule
- Backing platform behind the TAK integration layer

#### `synapse/` - Matrix homeserver
- Backing Matrix platform used by Matrix-related integrations
- Check `pg_init/` first for DB/config ownership issues before changing synapse internals

#### `mediamtx.yml` / MediaMTX
- Streaming platform config used alongside `mtxauthz`
- Depends on auth hooks, nginx exposure, and cert material

### `tests/` - Live-stack integration tests
- End-to-end verification against a running stack
- Best place to validate orchestration-level regressions after changing compose wiring, auth flows, or integration contracts
- **Dependencies**: full environment up and healthy

### `docs/` - Sphinx documentation
- Platform documentation for components, setup, and releases
- Update when orchestration behavior, required setup, or architecture contracts change

## Development Setup
```bash
# 1. Clone with all submodules
git clone --recurse-submodules -j8 git@github.com:pvarki/docker-rasenmaeher-integration.git
cd docker-rasenmaeher-integration

# 2. Create .env (must be literally named .env)
cp example_env.sh .env
# Edit .env: set SERVER_DOMAIN, all passwords, MW_LE_EMAIL, MW_LE_TEST=true for local

# 3. Set shell aliases (add to your shell profile or run per session)
alias rmlocal="PVARKI_DOCKER_REPO=localhost:5050/ docker compose -p rmlocal \
  -f docker-compose-local.yml"
alias rmdev="PVARKI_DOCKER_REPO=localhost:5050/ docker compose -p rmdev \
  -f docker-compose-local.yml -f docker-compose-dev.yml"

# 4. First-time only: populate the local Docker registry from ghcr.io
# The stack uses a local registry (localhost:5050) to cache pre-built images.
# On a fresh machine the registry is empty — pull and retag all pvarki images first:
source .env
IMAGES=$(PVARKI_DOCKER_REPO=localhost:5050/ docker compose -p rmlocal \
  -f docker-compose-local.yml config 2>/dev/null \
  | grep "image: localhost:5050/" | sed 's/.*image: //' | sort -u)
echo "$IMAGES" | while read img; do
  ghimg=$(echo "$img" | sed 's|localhost:5050/|ghcr.io/|')
  docker pull "$ghimg" && docker tag "$ghimg" "$img" && docker push "$img"
done

# 5. Build and start (local mode)
rmlocal build
rmlocal up

# Dev mode (hot-reload, UI at https://localmaeher.dev.pvarki.fi:4439)
rmdev build
rmdev up

# 5. First admin enrollment code
docker compose exec -it rmapi /bin/bash -c "rasenmaeher_api addcode"
```

**Required DNS records** (all pointing to your WAN address):
`domain`, `kc.domain`, `tak.domain`, `bl.domain`, `mtx.domain`, `mtls.domain`,
`mtls.kc.domain`, `mtls.tak.domain`, `mtls.bl.domain`, `mtls.mtx.domain`

**Required open ports:** 80, 443, 8089, 8443, 8446, 9446, 4626, 4627, 4666, 1936, 8322, 8890, 9888, 9889, 9996

## Running Tests
Integration tests require the live stack to be running first.
```bash
# Install test deps
pip install -r tests/requirements.txt

# Run all integration tests
pytest tests/ -v

# Pre-commit hooks
pre-commit install --install-hooks
pre-commit run --all-files
```

## Code Conventions
- Python services: `pylintrc` at repo root enforced via pre-commit
- Commit messages: conventional commits (`docs:`, `feat:`, `fix:`, `chore:`)
- Versioning: `bump-my-version bump patch` — do **not** edit `version.yml` manually
- Submodule changes: work in the submodule's own repo, then bump pointer here
- `.env` variable names are documented in `example_env.sh`

## Architecture Notes
**Startup dependency chain** (order matters):
```
miniwerk (HEALTHY)
  → cfssl + ocsp (HEALTHY)
    → postgres (HEALTHY)
      → keycloak → keycloak-init (COMPLETED)
        → rmapi, takserver suite, blapi, matrixrmapi, synapse, rmmtxauthz
          → rmnginx, mediamtx, productsnginx
```

**Kraftwerk volume pattern:** `miniwerk` writes a JSON manifest per product to a shared
Docker volume (`kraftwerk_shared_<product>`). Each service reads its manifest on startup to
get its domain, certificates, and secrets. Never bypass this pattern.

**Two nginx instances:**
- `rmnginx` (port 443): serves Deploy App UI and core API
- `productsnginx` (port 4626/4627): aggregates all product integration APIs with mTLS

**pg_init/ owns all database schemas.** If a service's DB is broken, check `pg_init/`
init scripts before touching the service submodule.

**mTLS enforcement:** All inter-service product API calls go through `productsnginx` with
client-certificate validation. Test with `curl --cert` or use the provided test fixtures.

## Ecosystem Map

| Compose service   | Submodule / image                | Port(s)                   | Role                                |
|-------------------|----------------------------------|---------------------------|-------------------------------------|
| rmapi             | api/                             | 8000                      | Core REST API, identity broker      |
| uiv2 / rmui       | uiv2/                            | 4439 (dev), 443           | Web UI / Deploy App frontend        |
| miniwerk          | miniwerk/                        | 80 (internal)             | Certificate orchestration           |
| keycloak          | keycloak/                        | 9443 / 8080 (int)         | IAM / OIDC provider                 |
| openldap          | (image: bitnami/openldap)        | 1636                      | LDAP backing Keycloak               |
| cfssl             | cfssl/                           | 8888 / 8889 / 8887        | Internal CA + OCSP                  |
| kwinit            | kw_product_init/                 | (init only)               | Product cert generation             |
| kcinit            | kc_client_init/                  | (init only)               | Keycloak client provisioning        |
| takconfig         | takserver/                       | 8089-8094, 8443, 9000-9002| TAK Server 5.x                      |
| takrmapi          | takintegration/                  | 8003                      | TAK ↔ RASENMAEHER bridge           |
| blapi             | battlelog/                       | 3000 / 4666               | Event log / visualization           |
| matrixrmapi       | matrixrmapi/                     | 8012                      | Matrix ↔ RASENMAEHER bridge        |
| synapse           | synapse/                         | 8008 (internal)           | Matrix homeserver                   |
| rmmtxauthz        | mtxauthz/                        | 8005                      | MediaMTX auth hook                  |
| mediamtx          | (image: bluenviron/mediamtx)     | 1936/8322/8890/9888/9889  | Video streaming server              |
| rmnginx           | nginx/                           | 80, 443                   | TLS termination, main routing       |
| productsnginx     | nginx/                           | 4626, 4627                | Products aggregator / mTLS          |
| postgres          | (image: postgis/postgis)         | 5432 (internal)           | Central database                    |
| fpintegration     | fpintegration/                   | 8001                      | Reference product integration API   |

## Integration API Contract
- OpenAPI spec for the core API (dump with Docker build target `openapi`):
  `docker build --ssh default --target openapi -t rasenmaeher_api:openapi . && docker run --rm rasenmaeher_api:openapi`
- BattleLog OpenAPI: https://pvarki.github.io/typescript-liveloki-app/
- Agents must not break the enrollment API contract (`/api/v1/enroll/*`, `/api/v1/product/*`).

## How to Add a Product Integration
Adding a new product to the platform involves changes in three places:

**1. New integration submodule** (own repo, e.g. `python-rasenmaeher-<name>`)
- Implement the user lifecycle callback endpoints: `POST /api/v1/users/created`, `revoked`, `promoted`, `demoted`
- Implement `GET /api/v2/description/{language}` returning `ProductDescriptionExtended`
- Add a Kraftwerk manifest reader on startup (reads from the shared `kraftwerk_shared_<name>` volume)
- Optional: implement `POST /api/v2/clients/data/` and add a `ui/` folder for product UI assets

**2. This repo** (`docker-rasenmaeher-integration`)
- Add the submodule: `git submodule add <repo_url> <name>/`
- Add compose service block to `docker-compose.yml` (and local/dev variants)
- Wire the `kraftwerk_shared_<name>` volume and `ui_files` volume if the product has UI
- Add nginx server block in `nginx/templates_consolidated/` for the product API ingress
- Add DB init script in `pg_init/` if the product needs its own database
- Register the product with miniwerk so it gets a domain + cert

**3. `api/` submodule** (`python-rasenmaeher-api`)
- Register the product shortname in `rmapi` so it appears in descriptions and proxy routing

See `fpintegration/AGENTS.md` for the minimal reference implementation and
`uiv2/AGENTS.md` for the Modular UI Integration Spec.

## Submodule Update Workflow
```bash
# Update one submodule to its latest main
git submodule update --remote <submodule-dir>
git add <submodule-dir>
git commit -m "chore: update <name> submodule pointer"

# Never update all submodules blindly — update one, verify tests, then commit.
```
Never edit files inside a submodule directory from this repo — work in the submodule's own
repo and then bump the pointer here.

## Secret Management
- All secrets live in `.env` (never committed — listed in `.gitignore`)
- Template with placeholder values: `example_env.sh` (safe to commit)
- Secrets injected as Docker Compose environment variables; no secret manager in local mode
- Production: rotate passwords per-environment; use `uuidgen -r` for UUID values
- JWT signing key lives at `/data/persistent/private/rm_jwtsign.key` inside the `rmapi` container
- **Never commit** `.env`, `*.jks`, `*.pem`, `*.key`, or any file containing real passwords

## Common Agent Pitfalls
1. **`.env` naming is mandatory.** Docker Compose will silently ignore any file not named
   exactly `.env`. `example.env`, `local.env`, `.env.local` — all fail. No exceptions.
2. **Never run `rmlocal` and `rmdev` simultaneously.** They share Docker networks by name.
   Always `down` one before starting the other; use `down -v` when switching to wipe volumes.
3. **OpenLDAP + Keycloak-init race condition on first `up`.** This is known and expected.
   Run `up` a second time — do not attempt to "fix" the init scripts or add sleep hacks.
   Keycloak takes 3–5 minutes to finish its Java startup; wait for it to become healthy
   before concluding that other services are broken.
4. **Stale CRL causes `ocsprest` to be unhealthy when reusing old volumes.** If you start
   the stack with an existing `ca_public` volume from a previous run, the CRL timestamp
   will be too old and ocsprest reports unhealthy. Fix: `rmdev down -v` to wipe volumes,
   then start fresh. This is not a blocker for a clean first-time run.
5. **Do not `git submodule update --remote` across all submodules at once.** Submodule pointers
   are intentional version pins. Update one at a time, run integration tests, then commit.
6. **`pg_init/` owns `homeserver.yaml` for Synapse.** If Matrix is broken, look here first —
   not in the `synapse/` submodule.
7. **Nginx config is load-order sensitive.** Adding a new service requires a corresponding
   nginx server block in `nginx/templates_consolidated/` — missing it silently breaks routing.
8. **Do not use Git Bash on Windows.** It breaks Docker SSH agent forwarding and volume paths.
   Use WSL2 or PowerShell with the Docker Desktop WSL2 backend.
9. **Windows is not a tested platform.** This stack has been validated on Linux and macOS.
   Running on Windows (even with WSL2) may encounter unresolved edge cases. Use Linux or
   macOS for reliable results.

## Related Repos
- https://github.com/pvarki/python-rasenmaeher-api
- https://github.com/pvarki/react-rasenmaeher-ui-v2
- https://github.com/pvarki/python-rasenmaeher-fpapi
- https://github.com/pvarki/python-miniwerk
- https://github.com/pvarki/python-pvarki-cfssl
- https://github.com/pvarki/docker-rasenmaeher-keycloak
- https://github.com/pvarki/go-rasenmaeher-kw_product_init
- https://github.com/pvarki/go-rasenmaeher-kc_client_init
- https://github.com/pvarki/docker-rasenmaeher-takserver
- https://github.com/pvarki/python-rasenmaeher-takintegration
- https://github.com/pvarki/typescript-liveloki-app
- https://github.com/pvarki/python-rasenmaeher-matrixrmapi
- https://github.com/pvarki/docker-rasenmaeher-synapse
- https://github.com/pvarki/python-rasenmaeher-mtxauthz
- https://github.com/pvarki/docker-rasenmaeher-nginx
