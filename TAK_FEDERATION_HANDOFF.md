**TAK federation implementation handoff — 2026-10-26**

Implement two operations through RMAPI and takintegration: trust the other deployment's intermediate CA and give it the `default` group in both directions; then create an outgoing federation connection on the server selected by the external service. This document is a researched implementation plan. Application code and live federation configuration have not been changed.

The external service signs requests with a private key whose public key RMAPI already trusts. It calls each deployment's RMAPI, never TAK directly. RMAPI authenticates and authorizes the request, then calls its own takintegration using its existing product mTLS identity.

**The caller owns coordination.** It must finish trust/group setup on both servers before calling outgoing on exactly one. Do not implement hostname ordering, initiator election, a reverse connection, or a cross-server handshake in either API. This supersedes the earlier proposed lexicographic initiator rule. `slow-cheetah.solution.dev.pvarki.fi` was only an example; its absence is not a blocker or an incident.

The existing local deployment is `localmaeher.dev.pvarki.fi`. Its public HTTPS port is **4439**, and its HTTPS certificate uses a development CA. These facts affect HTTPS access and certificate downloading; federation still uses **9001** and TAK admin REST still uses **8443**.

The implementation boundaries are:

```text
External orchestration service
  -- HTTPS + signed bearer JWT --> deployment RMAPI
  -- RMAPI's product mTLS -------> local productsnginx -> takintegration
  -- takintegration admin mTLS --> local TAK REST :8443
  -- Ignite service proxy ------> TAK messaging/configuration services
```

The first arrow is public JWT authentication. The two subsequent HTTP hops use different, existing local service identities. Never forward the external bearer token or send local admin credentials to the remote CA download URL.

The exact TAK behavior was traced in `docker.io/pvarki/tak-server-dist:5.8-RELEASE-84`, local image ID `sha256:51f9220c6389b50a25b9e500e31b8555d91d684f6f6ee7f8f4decbfd46d335c1`. Its ZIP contains `tak/takserver.war`; the controller is in `WEB-INF/lib/takserver-war-5.8-RELEASE-84.jar`, configuration models in `takserver-common-5.8-RELEASE-84.jar`, and messaging implementations in `WEB-INF/classes`.

| Manual action | Exact TAK request | Effect verified in JavaScript/classes |
| --- | --- | --- |
| Upload certificate, Save | `POST /Marti/api/federatecertificates`, multipart field `file` | `FederationApi.saveFederateCertificateCA` parses X.509 and calls `FederationManager.addCA`. Updates the federation SSL cache and truststore, saves it, refreshes the federation server. Also requests HTTP connector reload through `distributed-federation-http-connector-service`. |
| List uploaded certificates | `GET /Marti/api/federatecertificates` | Response envelope `data` contains certificate summaries; identifier is `fingerPrint`. Upload itself returns no certificate identifier. |
| Manage CA groups | `GET /Marti/api/federatecagroups/{caId}` | Reads separate inbound and outbound associations. |
| Add `default`, Both | `POST /Marti/api/federatecagroups` with `{"caId":"...","group":"default","direction":"BOTH"}` | Calls both `addInboundGroupToCA` and `addOutboundGroupToCA`. Each persists federation configuration through `CoreConfigFacade.setAndSaveFederation`. |
| Back to certificate authorities | Angular navigation | No further save. |
| Save outgoing connection | `POST /Marti/api/outgoingconnections` with JSON | `FederationApi.createOutgoingConnection` validates input; `DistributedFederationManager.addOutgoingConnection` checks local duplicates, persists configuration, and initiates enabled connections. Version 2 starts `TakFigClient`. |
| Read outgoing definition/status | `GET /Marti/api/outgoingconnections/{name}` and `GET /Marti/api/outgoingconnectionstatus/{name}` | Configuration and connection state are separate. The definition lookup can return HTTP 200 with `data: null` when absent. |

`FederationApi` receives an injected `FederationManager`. `FederationManagerProxyFactory` obtains it with `ignite.services(ClusterGroupDefinition.getMessagingClusterDeploymentGroup(ignite)).serviceProxy("distributed-federation-manager", FederationManager.class, false)`. `MessagingConfiguration` deploys `DistributedFederationManager` under that service name. Configuration saving uses the `distributed-configuration` service/cache and the configured CoreConfig file. Use REST to retain all these effects; a JNI call to `addCA` alone misses the controller's HTTP connector reload.

Facts the implementation must preserve:

- `caId` is SHA-256 over certificate DER, formatted as uppercase hexadecimal octets separated by colons. Match the returned `fingerPrint`, not subject CN, filename, or serial alone.
- Upload must be less than 1 MiB. TAK's upload handler parses a certificate but does not supply all the CA/intermediate validation the integration should enforce.
- `BOTH` reads back as `INBOUND` plus `OUTBOUND`. Repeated additions can append duplicates; read before writing and add only missing directions.
- Explicitly send `protocolVersion: 2`; the UI supplies it but the Java model defaults to 1.
- Display names allow letters, digits, underscores and whitespace, maximum 30 characters. Hyphens fail both UI and REST validation. Map a deployment label such as `fast-flounder` to `fast_flounder` for display only. Reject an overlong derived name instead of truncating and risking collisions.
- CA group defaults are copied when a peer's federate record is first created. Updating a CA's groups does not repair an existing federate record. Detect/report this during acceptance testing; peer-specific group repair is a separate operation.
- Duplicate peer connections are detected by peer certificate identity and may cause rejection/disabling. Local duplicate prevention does not replace the caller's responsibility to initiate from only one server.
- `addCA` and truststore persistence catch some exceptions internally. HTTP 200 alone does not prove success. Readback proves visible state; persistence requires a restart test.

The proposed public RMAPI contract is two fixed routes:

| Public RMAPI endpoint | Internal takintegration endpoint | Purpose |
| --- | --- | --- |
| `POST /api/v1/federation/tak/trust` | `POST /api/v1/federation/trust` | Install the remote intermediate CA and `default` inbound/outbound associations locally. |
| `POST /api/v1/federation/tak/outgoing` | `POST /api/v1/federation/outgoing` | Ensure one enabled outgoing connection to the specified peer exists locally. |

Both accept `Content-Type: application/json` and exactly this body shape, with unknown fields forbidden:

```json
{"remote_base": "fast-flounder.solution.dev.pvarki.fi"}
```

`remote_base` means a full deployment DNS hostname, optionally followed by its HTTPS port. It has no scheme, `tak.` prefix, path, credentials, query or fragment. The optional port is needed for local development:

```json
{"remote_base": "localmaeher.dev.pvarki.fi:4439"}
```

Normalize DNS to lowercase and omit explicit port 443. Validate DNS labels and port range; reject IP literals, malformed authorities and self-federation based on the local deployment hostname, ignoring port. Cross-domain deployment pairs are allowed: do not derive the remote domain from the local domain or require a shared suffix. Restrict the value to an authority, not an arbitrary URL. The server constructs only these destinations:

| Value | Production example | Development example |
| --- | --- | --- |
| CA download | `https://fast-flounder.solution.dev.pvarki.fi/ca/public/intermediate_ca.pem` | `https://localmaeher.dev.pvarki.fi:4439/ca/public/intermediate_ca.pem` |
| Federation address | `tak.fast-flounder.solution.dev.pvarki.fi` | `tak.localmaeher.dev.pvarki.fi` |
| Federation port | `9001` | `9001` |
| Display name | `fast_flounder` | `localmaeher` |

The external service uses `Authorization: Bearer <JWT>`. No login-code exchange, anonymous-admin session, user enrollment, browser cookie or client certificate is required for these two public routes. An ordinary user/session JWT is insufficient even when correctly signed.

Require the following signed claims. This example targets local RMAPI and authorizes trusting fast-flounder; its numeric dates are illustrative and must be replaced with current UTC Unix seconds:

```json
{
  "iss": "federation-orchestrator",
  "sub": "federation-orchestrator",
  "aud": "rasenmaeher:tak-federation:localmaeher.dev.pvarki.fi",
  "iat": 1800000000,
  "nbf": 1800000000,
  "exp": 1800000300,
  "nonce": "bfc76453-cb25-44cc-9aaa-17a85714f196",
  "federation_action": "trust",
  "remote_base": "fast-flounder.solution.dev.pvarki.fi"
}
```

The authorization rules are deliberately limited to this operation:

1. Accept only an explicit bearer header. Ignore cookies; a cookie must neither authorize the request nor override a supplied bearer token.
2. Verify using RMAPI's existing trusted public keys. Pin algorithms by key type: RSA/RS256 or EC/ES256, matching current support. Never accept a token-supplied key, fetch `jku`/`x5u`, select an arbitrary filesystem key from `kid`, or allow HS256/`none`.
3. Require nonempty string `iss` and `sub` for attribution. Trust comes from the accepted signing key, not a self-declared issuer name; no new issuer registry is needed for this task. Do not claim that the current shared key directory binds one key to a particular `iss`.
4. Require one exact string audience, `rasenmaeher:tak-federation:<local normalized deployment DNS>`. Derive it from the local manifest's `dns`, not the request Host header. The HTTPS port is intentionally not part of deployment identity.
5. Require integer `iat`, `nbf`, `exp` (reject booleans, strings and floats); enforce valid times, `iat <= nbf < exp`, and a maximum `exp - iat` of 300 seconds. Use the verifier's existing **zero clock leeway**, within the contract's maximum allowance of 30 seconds; keep caller/server clocks synchronized. Do not inherit the long development `JWT_LIFETIME`.
6. Require `federation_action` to equal the selected route (`trust` or `outgoing`) and the canonical signed `remote_base` to equal the canonical body value, including any nondefault HTTPS port. A trust token cannot create an outgoing connection or select a different peer.
7. Require a UUID nonce. After validating the body and all claims, consume it before dispatch using existing `SeenToken.use_token`. Its database unique constraint must also handle concurrent identical requests: catch the duplicate-key race and return the same replay rejection, not 500. No external effect may happen before successful nonce insertion.
8. Each retry uses a fresh nonce/token with the same requested state. A timeout may follow a successful downstream write; idempotent takintegration readbacks make such retries safe. Consumed tokens stay consumed after downstream failure. No new job or idempotency table is needed.

The installed `multikeyjwt` verifier loads `.pub` files from `JWT_PUBKEY_PATH`. Startup already copies Kraftwerk keys and optionally writes `external.pub` from `EXTERNAL_JWT_PUBKEY_B64`; Compose maps `RMAPI_EXTERNAL_JWT_PUBKEY_B64` to it. Provision **only the PEM public key** through that path; the private signing key stays with the caller. Restart/reload RMAPI workers after a key-set change because the verifier is a singleton. Removing an environment value alone does not remove an existing persisted `external.pub`.

**Updated multikeyjwt prerequisite.** The sibling checkout at `afce00e51fae6b71c914b2022d18fa84593670fa` declares version **1.8.0** and now provides audience verification and header precedence, plus per-call issuance overrides. RMAPI's `api/uv.lock` still resolves **1.7.0** (`pyproject.toml` permits `>=1.7,<2.0`). Before implementing these routes, update RMAPI's dependency floor and lockfile to a published version containing the reviewed changes, or pin that exact revision for development. Publication and installation in the running composition have not been verified; a version string in the sibling checkout is not deployment evidence. This replaces the earlier proposal to copy the library's public-key verification loop into RMAPI.

Add one federation-specific dependency using FastAPI's `HTTPBearer(auto_error=False)` extraction. Reject absent/malformed/non-Bearer credentials with RMAPI's 403 response, then call `Verifier.singleton().decode(credentials.credentials, audience=expected_audience)`. This path never reads cookies. Reuse the library's signature, algorithm, multi-key and time verification; catch `jwt.InvalidTokenError` as authentication failure without logging the token. Treat an unavailable/empty trusted-key set as service unavailability (503), not successful authentication.

After verified decoding and before consuming the nonce, enforce all federation rules above. The library accepts audience arrays, so additionally require `type(payload.get("aud")) is str` and equality to the exact deployment audience. It does not expose a required-claims list or leeway option: require every contract claim and exact integer timestamp types in the federation dependency, then check their ordering/lifetime. Missing timestamps must not pass merely because the library validates them only when present. Keep the audience local to this call; do not change shared verifier/issuer configuration or set global `JWT_AUDIENCE` for this feature.

`JWTBearer(audience=...)` is now supported and any Authorization header takes precedence over cookies, including invalid/empty headers. However, it still accepts a cookie when the header is absent, so it is not sufficient alone for these header-only routes. Upgrading the library also changes existing routes: unusable headers can no longer fall back to cookies, and `auto_error=False` returns `None` for invalid credentials. Run existing RMAPI cookie, bearer, token-exchange/refresh and optional mTLS-or-JWT tests as part of the dependency upgrade.

The external service can issue each request with the reviewed library directly:

```python
from uuid import uuid4
from multikeyjwt import Issuer

# The caller's own signing key is configured on this issuer.
token = Issuer.singleton().issue(
    {
        "iss": "federation-orchestrator",
        "sub": "federation-orchestrator",
        "aud": "rasenmaeher:tak-federation:localmaeher.dev.pvarki.fi",
        "nonce": str(uuid4()),
        "federation_action": "trust",
        "remote_base": "fast-flounder.solution.dev.pvarki.fi",
    },
    lifetime=60,
)
```

`issue(claims, lifetime=60)` sets `iat` and `nbf` to now and `exp` to now plus 60 seconds. Explicit `iss`/`aud` claims override configured defaults without changing the singleton; omitted claims still use configured defaults. Supply a fresh claims dictionary and nonce for every target/action/retry: `issue` mutates its input and overwrites supplied time claims. It permits empty issuer/audience overrides and nonpositive or long lifetimes as a general-purpose signer; RMAPI must still enforce the federation contract. Do not mutate `Issuer.singleton().config` between requests or use the sign CLI's default lifetime for federation tokens.

RMAPI should synchronously dispatch only to manifest product key **`tak`**, whose current local API base is `https://tak.localmaeher.dev.pvarki.fi:4626/`. Use the existing `get_session_winit()` client and fixed internal paths above; join the trailing slash correctly. Do not offer a user-selected product, path, group, federation port or TLS-disable flag. takintegration retains `MTLSHeader(auto_error=True)` and `comes_from_rm(request)` with product-proxy requests forbidden. It does not interpret the external JWT.

The existing `post_to_product` helper is useful reference but currently catches HTTP failures/timeouts/invalid responses and returns `None`. For these two routes, use a small local dispatch function built on the same mTLS session and manifest lookup so the contract can preserve known 409/422 responses, distinguish 502/504, and reject malformed success payloads. Avoid changing behavior for every existing product caller. Use a 30-second RMAPI downstream budget; bound takintegration's whole operation to 20 seconds, including locking, CA fetch and TAK calls. The global helper default is only 3 seconds and is unsuitable here. Do not wait indefinitely for a connection to become `CONNECTED`.

Both operations return HTTP **200** after successful readback, for either a change or a no-op. The same typed response shape should pass through takintegration and RMAPI. Trust example:

```json
{
  "success": true,
  "operation": "trust",
  "remote_base": "fast-flounder.solution.dev.pvarki.fi",
  "changed": true,
  "ca_fingerprint": "<uppercase colon-separated SHA-256 fingerprint>",
  "group": "default",
  "directions": ["INBOUND", "OUTBOUND"]
}
```

Outgoing example:

```json
{
  "success": true,
  "operation": "outgoing",
  "remote_base": "fast-flounder.solution.dev.pvarki.fi",
  "changed": false,
  "display_name": "fast_flounder",
  "address": "tak.fast-flounder.solution.dev.pvarki.fi",
  "port": 9001,
  "protocol_version": 2,
  "enabled": true,
  "connection_status": "CONNECTED"
}
```

`connection_status` is TAK's observed status string, or null if not yet available. `success` means configuration was verified, not that traffic delivery was proved. Returning `CONNECTING` is valid; a later fresh-token retry reads status without creating another connection.

| HTTP status | Contract meaning |
| --- | --- |
| 403 | Missing/invalid JWT, untrusted signing key, invalid or missing claims, expired token, wrong audience/action/peer, or consumed nonce. No product dispatch. Keep RMAPI's existing 403 authentication convention. |
| 422 | Invalid request shape/authority, self-federation, or unsupported derived display name. |
| 404 | The deployment has no manifest product `tak`; no dispatch. |
| 409 | Required local CA/groups are missing, or an existing outgoing definition conflicts, including an administratively disabled connection. Never silently overwrite or re-enable it. |
| 502 | Remote CA fetch/TLS/content failure, invalid CA certificate, unexpected TAK/product response, or failed configuration readback. Downstream authentication failure is a service failure, not a caller JWT failure. |
| 503 | Local authentication/replay state is unavailable, or another local federation operation could not acquire the lock within its budget. No claimed success. |
| 504 | Operation deadline exceeded. State may already have changed; retry with a fresh token. |

For application errors use FastAPI's `detail` object with `code`, `stage`, `message` and `may_have_changed`; retain normal FastAPI schema-validation details for malformed bodies. Suggested stages are `authorize`, `dispatch`, `fetch_ca`, `upload_ca`, `groups`, `outgoing`, and `verify`. Do not return raw downstream HTML, bearer tokens, private paths or credentials. Audit accepted/denied operations with the existing audit helper: verified issuer/subject, action, canonical peer, nonce, result and failed stage. Log the matched public-key fingerprint when available. Do not log JWTs.

The trust implementation in takintegration should:

1. Validate/authenticate before making network requests. Download the fixed remote intermediate URL using a separate, credential-free HTTPS client with certificate/hostname verification, no redirects, a short fetch timeout and a streamed size limit strictly below 1 MiB.
2. Require exactly one PEM X.509 certificate, a current validity interval, `BasicConstraints.ca = true`, and a non-root intermediate; enforce `keyCertSign` when KeyUsage is present. Do not substitute the remote root, full CA chain or public HTTPS certificate. Use installed `cryptography`.
3. Under a lock shared across takintegration workers, list federation CAs and upload only if this fingerprint is missing. Reuse `RestHelpers.helpers` for the local TAK admin session and base URL; use multipart `file` with filename `intermediate_ca.pem`.
4. Read back the CA, get its exact `fingerPrint`, and read CA groups. Add `default/BOTH` if neither direction exists; add only `INBOUND` or `OUTBOUND` when one is missing. Preserve other groups and CA settings.
5. Verify both entries before success. On partial failure, report the stage and leave already successful work for an idempotent retry. Do not delete pre-existing trust or attempt broad rollback.

Use the existing `filelock` dependency, with an async-capable lock or offloaded blocking acquisition, rather than blocking FastAPI's event loop. Serialize all federation read-modify-write operations from this service, not only requests for one peer. TAK UI/manual writers are outside this lock; tests must not run competing manual changes.

The outgoing implementation should validate the same peer, verify that its current intermediate fingerprint and both CA groups are already configured locally, and inspect outgoing definitions by both derived display name and address/port. Fetching the peer's intermediate again is acceptable; it identifies the exact prerequisite instead of trusting a CN. Do not auto-run trust from outgoing. If an equivalent enabled connection exists, return a no-op and its status. If the same name or destination has conflicting settings, return 409. A different display name for the same otherwise equivalent destination can be reported as the existing connection rather than creating a duplicate. There is no automatic failover, reenabling, or peer selection.

For a new definition, POST these UI-equivalent settings, replacing the example name/address:

```json
{
  "displayName": "fast_flounder",
  "address": "tak.fast-flounder.solution.dev.pvarki.fi",
  "port": 9001,
  "enabled": true,
  "protocolVersion": 2,
  "reconnectInterval": 30,
  "unlimitedRetries": true,
  "tls": true,
  "useToken": false
}
```

Read back the definition and current status. Do not change `allowDuplicate`. A locally visible incoming connection is diagnostic information; the API does not use it to elect an initiator or claim it can prove the remote server has no outgoing configuration. Caller coordination remains the rule.

The caller's workflow is therefore: trust B on A; trust A on B; wait for both success responses; outgoing to B on A **or** outgoing to A on B, according to the caller's own choice. Each step has its own target audience, operation/peer-bound JWT and fresh nonce. On partial preparation failure, retry that preparation before initiating. No calls to the example slow-cheetah deployment are required.

Local validation already performed, read-only:

| Check | Observed result |
| --- | --- |
| `GET https://localmaeher.dev.pvarki.fi:4439/api/v1/healthcheck` | 200, deployment `localmaeher`, RMAPI `1.19.2+260912`. |
| Same request using `--cacert tests/testcas/miniwerk_ca.pem` | 200 with TLS verification enabled. Prefer this to `--insecure`. |
| `GET ...:4439/ca/public/intermediate_ca.pem` | Certificate downloaded; subject `OU=RASENMAEHER,CN=LOCALMAEHER`, issuer `OU=Base CA,CN=LOCALMAEHER BaseCA`. |
| `GET ...:4439/api/v1/check-auth/jwt` without token | 403. No signed federation request was executed. |
| Local TAK GETs using takintegration's existing admin cert/key | `/federatecertificates`, `/outgoingconnections`, `/activeconnections` all returned 200. |
| Local outgoing definitions | **One already exists.** Do not delete, replace, toggle or use it as a disposable test fixture. |
| Served outgoing-creation HTML versus inspected WAR | Same SHA-256: `aec021d25cdf74f7857937942b27ad90194cb30255d0a8308be0982b86648df4`. |

Reproduce the safe public health check from the repository root:

```sh
curl --fail --show-error --silent \
  --cacert tests/testcas/miniwerk_ca.pem \
  https://localmaeher.dev.pvarki.fi:4439/api/v1/healthcheck
```

For a future remote-CA download targeting this development deployment, mount its development HTTPS CA into the calling test container and use a trust bundle containing that CA plus the system roots, for example through `SSL_CERT_FILE` and `ssl.create_default_context()`. Do not add a request-controlled `verify=false`, globally disable TLS verification, or confuse `tests/testcas/miniwerk_ca.pem` (HTTPS trust) with `intermediate_ca.pem` (TAK federation trust). Ensure the calling container resolves the development hostname to the intended host; its loopback address refers to that container. Local-host self-federation must still be rejected.

For a future authenticated smoke test, call `https://localmaeher.dev.pvarki.fi:4439/api/v1/federation/tak/trust` with a fresh external-service token and a controlled real peer. New routes are not implemented by this handoff. Use mocks/fixtures for the absent example peer. Do not restart or rebuild the currently running composition merely to validate this document, and do not start `rmdev` alongside `rmlocal`.

The implementation should touch these places, following their existing local conventions:

| Repository | Proposed changes |
| --- | --- |
| `api` | Upgrade/lock multikeyjwt to a version containing the reviewed changes. Add `web/api/federation/{__init__,schema,views}.py`; register in `web/api/router.py`; add the narrow header-only federation dependency in `web/api/middleware`, reusing `Verifier.decode(..., audience=...)`, `jwtinit`, `SeenToken`, `mtlsinit` and audit context. Keep the fixed product dispatch local to this feature. Add focused auth/dispatch tests, upgrade regression tests and contract documentation. |
| `takintegration` | Add `api/federation.py`, request/response schemas and router registration; add federation methods to `takutils/tak_rest_helpers.py` using existing HTTP helpers; add focused tests and document the two internal routes. No new JNI bindings. |
| Integration root | Only a development trust-bundle mount/env override if needed for container-based tests against `:4439`; no production TLS relaxation or port changes. |
| `takserver` | No application/config edits required. Existing template enables v2/9001 and has a separate federation truststore. Preserve administrator-managed peer/group configuration. |

Extend takintegration's `tests/test_comes_from_rm.py` with **valid federation request bodies** for the new endpoints; its existing user payload would otherwise cause 422 and hide authorization failures. Reuse RMAPI's external-key fixture pattern (`issuer_cl` in `tests/conftest.py`) and call `issuer_cl.issue(fresh_claims, lifetime=60)` with the target audience and operation claims. For malformed/missing time-claim tests, sign test payloads directly with PyJWT and fixture keys because `Issuer.issue` always replaces those claims. Do not reuse generic admin-session claims as federation authorization. Pin contract examples in tests in both submodules; do not add a shared package just for these schemas.

Required acceptance checks:

- RMAPI rejects missing/untrusted/expired/wrong-algorithm tokens; cookies alone; ordinary user tokens; wrong audience, action or peer; missing/overlong lifetime; replay; and concurrent duplicate nonce requests. These cases must make zero product calls.
- Reject audience arrays even when they contain the expected audience, non-integer/boolean or missing timestamps, empty issuer/subject, and malformed Authorization headers even alongside a valid cookie. A valid bearer token must work alongside an invalid or unrelated cookie. Empty/unavailable key sets return 503 without dispatch. Confirm consecutive requests for different deployment audiences do not change issuer/verifier defaults.
- A valid trusted external signature causes exactly one local mTLS dispatch to the fixed `tak` endpoint, without forwarding the bearer token or allowing a caller-chosen URL. Known conflicts and timeouts retain the documented status; malformed downstream success is rejected.
- Trust sends the exact multipart field, handles `fingerPrint`, preserves unrelated CAs/groups, repairs a partial direction once, and is a no-op on repeat. Invalid/oversize/expired/root/non-CA/multiple-cert inputs and TLS/redirect failures make no TAK mutation.
- Outgoing sends version 2, TLS, port 9001 and a valid display name; repeated requests create one definition; conflicting/disabled existing entries are untouched. Test the caller's selected initiator in either direction: no hostname-order rejection is allowed.
- Partial write followed by timeout can be retried with a fresh JWT without duplicate groups or connections. HTTP success without readback postconditions is rejected.
- On two controlled servers, run both trust steps, one outgoing step, verify `default` traffic both ways, then verify trust/groups/outgoing survive restart. Existing-federate group behavior and persisted-file failures need explicit coverage. The active local composition alone does not prove a two-server exchange.

The useful source anchors are below. Paths are relative to this handoff unless explicitly temporary. Line numbers may move; symbols are the stable reference.

| Evidence | Location |
| --- | --- |
| Trusted key provisioning | [jwtinit.py](api/src/rasenmaeher_api/jwtinit.py), [container-init.sh](api/docker/container-init.sh), `docker-compose-local.yml` RMAPI environment. The README key example currently names a private-key file; do not copy that mistake. |
| Reviewed JWT library | Sibling [issuer.py](../python-multikeyjwt/src/multikeyjwt/jwt/issuer.py), [verifier.py](../python-multikeyjwt/src/multikeyjwt/jwt/verifier.py), [jwtbearer.py](../python-multikeyjwt/src/multikeyjwt/middleware/jwtbearer.py), [issuance/verification tests](../python-multikeyjwt/tests/test_issueverify.py), and [middleware tests](../python-multikeyjwt/tests/middleware/test_middleware.py). Local paths require the sibling checkout. |
| Existing nonce storage | [nonces.py](api/src/rasenmaeher_api/db/nonces.py), `SeenToken.use_token`, unique `token` column. |
| Existing dispatch and its error loss | [productapihelpers.py](api/src/rasenmaeher_api/productapihelpers.py), `_method_to_product`; [mtlsinit.py](api/src/rasenmaeher_api/mtlsinit.py), `get_session_winit`. |
| Product-side authorization | [usercrud.py](takintegration/src/takrmapi/api/usercrud.py), `comes_from_rm`; [authorization tests](takintegration/tests/test_comes_from_rm.py). |
| Local TAK admin client | [tak_rest_helpers.py](takintegration/src/takrmapi/takutils/tak_rest_helpers.py), [tak_helpers.py](takintegration/src/takrmapi/takutils/tak_helpers.py), [tak_init.py](takintegration/src/takrmapi/takutils/tak_init.py). The existing local TAK SSL helper disables verification; do not use it for public CA downloads. |
| Persistent federation setup | [CoreConfig.tpl](takserver/templates/CoreConfig.tpl), [coreconfig.py](takserver/scripts/coreconfig.py), [TAK README](takserver/README.rst). |
| Exact UI requests | WAR members `Marti/certificates/js/{controllers,services}.js`, `Marti/federation/js/{controllers,services}.js`, `Marti/federation/partials/newOutgoingConnection.html`. |
| Exact backend methods | `com.bbn.marti.network.FederationApi`; `tak.server.grid.FederationManagerProxyFactory`; `tak.server.federation.DistributedFederationManager`; `com.bbn.marti.remote.config.{CoreConfigFacade,DistributedConfiguration}`; `tak.server.federation.{TakFigClient,FederationServer}`. |

The original TAK investigation inspected `api` **dedb0ccf682c8cac0d5348304b5bbcde08a45c22**, `takintegration` **1d93fe588cca85235d332d6e9a7960d06eb3b9e3**, and `takserver` **5d8433a2e4db23bc18230a8630c556ce68085346**. That investigation read installed multikeyjwt 1.7.0 locally and in the running RMAPI container. This handoff's authentication plan now targets sibling multikeyjwt **afce00e51fae6b71c914b2022d18fa84593670fa**, including audience/header changes (`b573cba`, `5880f00`), per-call lifetime (`ca7d750`), and issuer/audience claim overrides (`17860fc`). It does not imply the running RMAPI has been upgraded.

Review of the new library commits after `5880f00` found no blocking issues for this plan. The review covered issuance callers, singleton-default preservation, RSA/EC tests, existing audience/header behavior, and removal of unused Docker Hub login steps. The complete sibling test suite passed: **126 tests**, **80.93% coverage**, Python **3.13.15**, with four existing warnings from 1024-bit RSA test keys. Tests loaded the sibling source using `PYTHONPATH=src` with RMAPI's configured development interpreter; no installed package was replaced. Assumed use is concurrent service requests with fresh per-request claim dictionaries. CI Docker pulls, the other Python versions, published package availability, and RMAPI's upgrade regression suite were not run in this documentation review.

Temporary extraction/decompilation evidence remains under `/tmp/tak-federation-5.8.LRdfo2/` (`unpacked/Marti`, `decompiled`). The artifact/member/symbol references above allow reproduction after that directory is removed. No private keys, bearer tokens or full deployment manifests are included in this handoff.

Not performed: implementation, authenticated federation POSTs, certificate/group changes, service restarts, or a two-server traffic test. Existing peer group repair, CA rotation/removal and automatic rollback are outside this initial contract; successful visible readback still needs persistence and interoperability testing before release.
