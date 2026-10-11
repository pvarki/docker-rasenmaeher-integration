# Connecting an MDM, start to finish

How to take a deployment with no device management at all and end up with Android phones that
enrol through whatever MDM a unit already runs and come back as provisioned Deploy App users —
a client certificate whose private key was generated on the phone, and no application of ours
installed to get it there.

FleetDM is the worked example because it is the one with a driver. Everything in *Part 2B*
applies to any MDM that can act as a SCEP client, which is almost all of them.

This page is the procedure. {doc}`scep` is the architecture: what the containers are, why the
responder holds no MDM token, and what `RM_MDM_AGENT_CNS` buys. Read that if you want to know
*why*; read this if you want a working device.

:::{important}
**Two things decide almost every failure in this document, and neither is ours.**

Applications install on managed Android **at enrolment and at no other time**. A device that has
already joined never picks up anything added afterwards.

A callsign is **spent** once it has been used. A device that enrolled with the wrong setup cannot
be rescued by fixing the setup and retrying — it needs a fresh callsign.

Arm everything first. Enrol second. There is no third chance.
:::

## Before you start

| You need | Why |
|---|---|
| A deployment with a public DNS name and a working `mtls.<domain>` | The MDM reaches `/scep` over HTTPS; devices present their certificate to the mTLS host |
| Admin access to an MDM | Someone has to register a certificate authority in it |
| An admin login to Deploy App | Callsigns are planned there, and nowhere else |

You do **not** need: an app on the phone, a VPN, Google Play private hosting, or anything of ours
running inside the MDM.

## The division of labour

Worth understanding before you start, because it explains why half of this is automatic and half
is a page of typing.

**Enrolment is standard.** It is RFC 8894 (SCEP) plus one convention about the certificate
subject. Any MDM that can be pointed at a SCEP CA satisfies it, with no code from us.

**Everything else is not.** Pushing applications, policy and per-app configuration has no
standard. Every MDM has its own API and always will. That part is a driver — we have one for
Fleet — or a person following instructions.

So `rmscep mdm-apply` has two modes. Against Fleet it does the work. Against anything else it
prints what to type:

```bash
docker compose run --rm rmscep rmscep mdm-apply --mdm manual
```

That changes nothing and talks to nothing. It is the honest version of "works with any MDM".

---

## Part 1 — Start fresh

### 1.1 Set the challenge

In `.env` on the deployment:

```bash
RMSCEP_CHALLENGE=<some long random string>
```

:::{note}
**The challenge is not a secret.** It sits in the MDM's own configuration and travels in every
device's certificate request. It keeps casual noise off a public endpoint; it is not the control.

The control is that an admin planned the callsign, and that the request carries
`<callsign>@<approval code>` — the code is what proves the MDM was told to give *this* device
*that* callsign. Treating the challenge as the gate is the mistake this design exists to avoid.
:::

Leave it empty and the responder starts, answers, and refuses to enrol anything.

### 1.2 Bring the stack up

```bash
docker compose pull
docker compose up -d
```

`scepinit` runs once, has the deployment CA sign the responder's client identity, and exits.
`rmscep` then starts. Check both:

```bash
docker compose ps rmscep
docker compose logs scepinit
```

`rmscep` must reach `healthy`. Its healthcheck is deliberately only about itself — it does not
probe RASENMAEHER, or every hiccup over there would restart this container.

### 1.3 Prove the responder before you touch the MDM

Do this now. If it fails, nothing in Part 2 can work, and debugging it through an MDM is
miserable because a failing MDM sends no request at all and your logs stay silent.

```bash
curl "https://<domain>/scep?operation=GetCACaps"
```

Expect a capability list containing `SHA-256` and `POSTPKIOperation`.

:::{warning}
**HTTP 200 is not proof.** If `location /scep` is missing from the proxy, the request falls
through to the SPA and you get 200 with an HTML page. Assert on the *body*, not the status.
:::

Then the real thing, which exercises the whole path including RASENMAEHER:

1. Plan a throwaway callsign in Deploy App (*Part 4.1*), and note its code.
2. Run:

```bash
docker compose run --rm rmscep rmscep selftest SELFTEST1 --code A1B2C3D4
```

`--code` is the approval code on its own. The tool builds `<callsign>@<code>` itself — the
`CALLSIGN@CODE` form is what you give the *MDM*, not this.

This generates a key, builds a real PKCSReq, and checks the certificate that comes back
certifies the key it generated. A pass means the responder, the challenge, the planned callsign
and RASENMAEHER's signing path are all good, and anything still broken afterwards is on the
MDM's side of the contract.

That callsign is now spent. Plan a different one for the real device.

---

## Part 2A — Connect FleetDM

### 2A.1 Register the SCEP CA — by hand, once

:::{important}
`mdm-apply` does **not** create the certificate authority. It looks for one by name and fails
with `no certificate authority named 'RMSCEP'` if it is missing. This step is manual and there
is no way around it.
:::

In Fleet, add a certificate authority:

| Field | Value |
|---|---|
| Type | Custom SCEP proxy (`custom_scep_proxy`) |
| Name | `RMSCEP` — must match `certificate.authority` in `mdm/template.json` |
| URL | `https://<domain>/scep` |
| Challenge | your `RMSCEP_CHALLENGE` |

Fleet fetches `GetCACert` when you save, so a wrong URL fails immediately. That makes saving it
the cheapest end-to-end proof you have.

### 2A.2 Give the driver a token

Fleet's API token is supplied at run time and never mounted into the running responder.
Something that can reach every device a unit owns has no business also being an internet-facing
parser.

```bash
install -m 0600 /dev/null ./mdm/.token
printf '%s' '<fleet api token>' > ./mdm/.token
```

`mdm/.token` is the path `docker-compose.yml` expects (`RMSCEP_MDM_TOKEN_PATH`). Keep it out of
git.

### 2A.3 State what the deployment needs

```bash
docker compose run --rm \
  -e RMSCEP_MDM_URL=https://<your fleet> \
  -e RMSCEP_MDM_TOKEN_FILE=/mdm/token \
  -v "$PWD/mdm/.token:/mdm/token:ro" \
  rmscep rmscep mdm-apply
```

Validate first with `--dry-run` if you are editing the template.

This creates the team if needed (`RMSCEP_MDM_TEAM`, default `rmscep`), makes the apps available
and marks them install-at-enrolment, uploads the device policy, publishes the launcher web app,
and creates the certificate template pointing at the `RMSCEP` authority.

**Do this before any device enrols.** Applications land on the *group*, and a device only picks
them up as it joins.

### 2A.4 Turn on the reconciler

```bash
COMPOSE_PROFILES=mdm docker compose up -d scepreconcile
```

Why this exists is in *Part 3*. In short: a device enrols before anyone has named it, so its
first certificate request always fails, and Fleet never retries a failed certificate profile.
The reconciler asks again — only for hosts that are now named *and* still failing.

---

## Part 2B — Connect any other MDM

```bash
docker compose run --rm rmscep rmscep mdm-apply --mdm manual
```

It prints, in order, exactly what to configure: the SCEP CA, the certificate template and its
subject, the device policy as Android Management API JSON, and the applications with their
managed configuration.

Three things to get right, because they are where ports go wrong:

**The subject is the contract.** The common name must be the callsign. Some *other* attribute
must carry `<callsign>@<approval code>`. See *Appendix A*.

**The MDM must let you set a per-device string, after enrolment.** The subject is built from it,
and it cannot be set before the device exists.

**The policy fields are Android Management API.** They carry to any Android EMM built on AMAPI
and mean nothing to one that is not, and nothing at all to iOS.

If your MDM has no equivalent of a per-host operator-set string, this design does not fit it,
and that is worth knowing on day one rather than after a day of configuration.

---

## Part 3 — Enrol a device, in the order that works

Three facts decide this order, and each was learned by getting it wrong.

1. **Applications install at enrolment and at no other time.** The group must already carry them.
2. **A configuration profile reaches a device when the *profile* changes, not when the device
   arrives.** A profile uploaded before a device joined is never delivered to it.
3. **A policy rewritten while applications are installing stops them installing.** The policy
   never settles long enough for the store to finish.

Facts 2 and 3 pull in opposite directions. That is the trap, and it is why "force it until it
works" makes things worse.

So, per device:

1. **`mdm-apply` has already run** for this deployment. (Part 2.)
2. **Plan the callsign** in Deploy App and note the device name it gives you —
   `CALLSIGN@CODE`. (Part 4.1.)
3. **Enrol the phone** in the MDM as usual.
4. **Leave it alone.** Do not move it between groups, do not re-apply, do not force anything,
   until the applications have finished arriving.
5. **Name the host.** In Fleet this is the host's IdP email
   (`PUT /api/latest/fleet/hosts/<id>/device_mapping`, `source: "idp"`). Set it to
   `CALLSIGN@CODE` exactly. It cannot be set earlier, because there was no host to name.
6. **Make the profile change**, which is what delivers it:
   ```bash
   docker compose run --rm ... rmscep rmscep mdm-apply --force-certificate
   ```
   Or just wait — the reconciler does this on its own within `RMSCEP_MDM_RECONCILE_INTERVAL`
   (default 300s).

Between steps 3 and 5 the device asks for a certificate with an unresolved subject and is
refused. **That is expected and harmless**: the responder refuses it before asking RASENMAEHER,
so the callsign is not spent and the device simply tries again.

:::{warning}
A device that has already enrolled cannot be rescued by repeating any of this. Its callsign is
spent and its new key will not match the certificate that callsign already holds. Give it a
fresh callsign and enrol it again.
:::

---

## Part 4 — Running it day to day

### 4.1 Planning callsigns

In Deploy App: **User management → MDM**. It is deliberately the last item in that group.

- **Add devices** takes one callsign, a numbered series (`KORPPI1`…`KORPPI10`), or a pasted CSV
  list — units mostly use their own names (`KORPPI`, `KIRVES`), so all three exist.
- Each planned device shows the name to give the MDM: `CALLSIGN@CODE`. Copy it, or export the
  table as CSV for a hundred phones.
- **Connection** shows the SCEP URL and the challenge, so an admin never has to read them off
  the server.

A device planned here is marked, so it does not clutter the approve-users queue a human
enrolment lands in. Nobody can approve it by hand, either — only the agent may complete it, and
only with the device's own request.

### 4.2 Changing what gets installed

Edit `mdm/template.json` and run `mdm-apply` again. The responder knows no package name at all —
a test enforces that — so this file is the whole of it.

Remember that existing devices will not pick up the change. It applies to devices that enrol
from then on.

### 4.3 Rotating the challenge

Change `RMSCEP_CHALLENGE` in `.env`, restart `rmscep`, and update the CA in the MDM. Devices
already holding certificates are unaffected; the challenge is only used at enrolment.

---

## Part 5 — When it goes wrong

| Symptom | Cause |
|---|---|
| `GetCACaps` returns HTML with HTTP 200 | `location /scep` missing from the proxy; the request fell through to the SPA |
| Saving the CA in the MDM fails | Wrong URL, or the responder is not healthy. Fix before anything else |
| `no certificate authority named 'RMSCEP'` | Part 2A.1 was skipped, or the name does not match `certificate.authority` |
| Certificate profile stuck at `failed`, host is named | Expected on first enrolment. The reconciler fixes it; `--force-certificate` does it now |
| Certificate profile `failed`, host is **not** named | Name it first (Part 3 step 5). Forcing achieves nothing |
| Device enrolled but no apps | They were not on the group when it joined. Fresh callsign, enrol again |
| Browser says `mtls_fail` | Both halves are needed: `choosePrivateKeyRules` says which key *may* be used, `AutoSelectCertificateForUrls` says whether the browser *sends* one. With no match the browser silently declines, which looks identical to having no certificate |
| `urlPattern` seems not to match | It is a `java.util.regex` pattern matched against the **whole** URL. It needs a trailing `.*` — a browser asks for `https://host/`, and a pattern stopping at the host matches nothing |
| Second certificate will not install | The template name is the Android keystore alias. A second key will not install over an existing alias. Keep the name stable, per deployment |
| Enrolment refused, callsign was planned | The code is missing or wrong in the subject. Check the per-host string is exactly `CALLSIGN@CODE` |
| Everything 504s after about two days | Unrelated to MDM — the Linkerd issuer wedge. Restart in the documented order |

A refusal from the responder is **final by design**: the device is meant to stop rather than
retry a callsign it was never going to get. A 503 is the transient one — the responder could not
reach RASENMAEHER — and is deliberately not a signed refusal.

---

## Appendix A — The subject contract

The whole of what an MDM must produce, for anyone porting this.

```
CN=<callsign>, <any other attribute>=<callsign>@<approval code>
```

The common name is the callsign and nothing else. Exactly one CN; it is compared exactly, not as
a substring, because the mTLS edge authorises on the CN it reads off the certificate.

Any attribute *other* than the common name must carry `<callsign>@<approval code>`. Which one is
the MDM's business — OU is used in the template because every MDM's subject template can write
it. The code is what proves the MDM assigned this device this callsign; without it the last gate
on a public endpoint is a short, guessable name.

In Fleet's variable syntax that is:

```
CN=$FLEET_VAR_HOST_END_USER_IDP_USERNAME_LOCAL_PART,OU=$FLEET_VAR_HOST_END_USER_IDP_USERNAME
```

— the host's IdP email is set to `CALLSIGN@CODE`, and Fleet renders the local part into the CN.
Your MDM will spell this differently. What has to be true is that it can put an operator-set,
per-device string into the subject.

A request may not ask for more than a device identity: no extended key usage beyond client
authentication, no subject alternative names, no `CA:TRUE`. The request arrives from a public
endpoint and its contents are entirely the caller's choice, so the shape of what gets issued
cannot be one of the things they choose.

:::{note}
The approval code ends up in the issued certificate, because the signer copies the request's
subject verbatim. It is spent by then and inert, but it is a known wart rather than a design
intent.
:::

## Appendix B — Settings

Set on the deployment, in `.env`:

| Setting | Default | Notes |
|---|---|---|
| `RMSCEP_CHALLENGE` | *(empty)* | Required. Not a secret. Empty means nothing enrols |
| `RMSCEP_MDM_TEAM` | `rmscep` | The group devices join |
| `RMSCEP_MDM_URL` | *(empty)* | Only for `mdm-apply` / the reconciler |
| `RMSCEP_MDM_RECONCILE_INTERVAL` | `300` | Seconds |
| `RMSCEP_MDM_TOKEN_PATH` | `./mdm/.token` | Mounted only into `scepreconcile` |

Set on RASENMAEHER, already in `docker-compose.yml`:

| Setting | Value | Notes |
|---|---|---|
| `RM_MDM_AGENT_CNS` | `rmscep` | Which certificate CN may complete a planned enrolment. Deliberately not a product CN |
| `RM_MDM_SCEP_CHALLENGE` | `${RMSCEP_CHALLENGE}` | So the admin UI can show it |

Commands:

| Command | Does |
|---|---|
| `rmscep selftest <callsign>` | Proves the responder end to end, without an MDM |
| `rmscep mdm-apply` | States the template to Fleet |
| `rmscep mdm-apply --mdm manual` | Prints what to configure by hand. Changes nothing |
| `rmscep mdm-apply --dry-run` | Validates the template and stops |
| `rmscep mdm-apply --force-policy` | Re-uploads the policy, to reach a host that just joined |
| `rmscep mdm-apply --force-certificate` | Asks again for hosts named after they enrolled |
| `rmscep mdm-reconcile` | The same, but only when it would change something |
