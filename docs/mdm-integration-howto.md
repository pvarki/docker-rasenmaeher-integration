# Connecting an MDM, start to finish

How to take a deployment with no device management at all and end up with Android phones that
enrol through whatever MDM a unit already runs and come back as provisioned Deploy App users —
a client certificate whose private key was generated on the phone, and no application of ours
installed to get it there.

Configuring the MDM is that MDM's business: a connector of its own where one exists, or an
operator at its console (*Part 2*). Everything else here applies to any MDM that can act as a SCEP
client, which is almost all of them.

This page is the procedure. {doc}`scep` is the architecture: what the containers are, why the
responder holds no MDM token, and what `RM_MDM_AGENT_CNS` buys.
{doc}`mdm-enrolment-protocol-choice` is why this is SCEP and not EST. Read those if you want to
know *why*; read this if you want a working device.

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
| An admin login to Deploy App | Enrolment is opened there, and nowhere else |

You do **not** need: an app on the phone, a VPN, Google Play private hosting, or anything of ours
running inside the MDM.

## The division of labour

Worth understanding before you start, because it explains why half of this is automatic and half
is a page of typing.

**Enrolment is standard, and nothing about it is specific to an MDM.** It is RFC 8894 (SCEP) plus
one convention about the certificate subject (*Appendix A*). Any MDM that can be pointed at a
SCEP CA satisfies it, with no code from us and no driver. This is the half that matters and the
half that is genuinely portable.

**Configuring the MDM is not standard.** Registering a SCEP CA, pushing applications, policy and
per-app configuration — every MDM words these differently and there is no cross-MDM API. This is
irreducibly per-MDM.

What *is* negotiable is whether a human does it. Where an MDM has an API, a connector of its own
can drive it. A connector lives in its own repository and runs on an operator's machine, never in
this stack, because it holds a token that reaches every device a unit owns. Where there is no
connector, an operator configures the same things by hand (*Part 2*). Either way the device half
is unchanged, and an MDM with no connector is slower to set up, not unsupported.

---

## Part 1 — Start fresh

### 1.1 Open enrolment when you are ready

There is nothing to set in `.env`. RASENMAEHER makes the challenge and keeps device enrolment
**closed** until an admin opens it in Deploy App: **User management → MDM**, **Open for 2
hours**. It closes itself when the time runs out, or press **Close now**. The same page shows the
SCEP URL and the challenge, with copy buttons. Every opening makes a new challenge, so give it to
the MDM each time, before devices enrol. `selftest` below takes the challenge as
`RMSCEP_CHALLENGE`.

:::{note}
**The challenge is what lets a device in while enrolment is open.** It sits in the MDM's own
configuration and travels in every device's certificate request, so it cannot be kept from
everything that enrolled. That is why every window gets a new one: a copied challenge is worth
only the window it came from.

**The window is the control.** The MDM decides who a device is: the common name of its request
becomes its callsign. So while enrolment is open, whoever holds the challenge can enrol a device
under any free name. Open it only while phones are being enrolled.
:::

While enrolment is closed the responder starts and answers, and RASENMAEHER refuses every device
before it looks at the request.

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

### 1.3 Warm up OCSP, or the first quarter hour looks broken

:::{important}
**A freshly issued responder certificate fails mTLS until the OCSP responder has signed a status
for it.** The mTLS host runs `ssl_ocsp leaf`, `scepinit` signs through ocsprest without
triggering a refresh, and the refresher runs on its own interval. So for roughly the first
fifteen minutes of a new deployment every enrolment answers 503, and the proxy redirects to
`/error?code=mtls_fail&exta=FAILED:certificate status request failed`.

Nothing is wrong. Force the refresh rather than waiting:

```bash
docker compose exec ocsprest ocsprest ocsp
```
:::

That 503 is deliberate and worth recognising: the responder answers a transient failure as 503
rather than as a signed refusal, because a signed refusal is final and would tell the device to
stop trying. `exta=NONE` in that redirect means no certificate was presented at all;
`exta=FAILED:...` means one was presented and its status could not be checked, which is this.

### 1.4 Prove the responder before you touch the MDM

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

1. Open enrolment in Deploy App (*Part 4.1*).
2. Run:

```bash
docker compose run --rm -e RMSCEP_CHALLENGE=<challenge from the MDM page> \
  rmscep rmscep selftest SELFTEST1
```

This generates a key, builds a real PKCSReq, and checks the certificate that comes back
certifies the key it generated. A pass means the responder, the challenge, the open window and
RASENMAEHER's signing path are all good, and anything still broken afterwards is on the MDM's side
of the contract.

`SELFTEST1` is now a user. Remove it under **User management**; the name stays spent.

---

## Part 2 — Connect the MDM

If your MDM has a connector, follow the connector's own guide: it does the steps below for you.
Otherwise configure them by hand, on the group this deployment's devices join rather than on the
whole estate, and **before any device enrols**:

1. **A SCEP certificate authority:** URL `https://<domain>/scep`, and the challenge from the MDM
   page. Most MDMs fetch `GetCACert` when the CA is saved, so a wrong URL fails right there.
2. **A certificate template** issued by that authority, with the subject from *Appendix A*. Its
   name becomes the Android keystore alias. A second key will not install over an existing alias,
   so pick the name once per deployment and keep it.
3. **A device policy** that lets the browser and the apps use that key on the mTLS host, and grants
   their permissions. In Android Management API terms:

   ```json
   {
     "privateKeySelectionEnabled": true,
     "choosePrivateKeyRules": [
       {"privateKeyAlias": "<template name>", "urlPattern": "(https://)?mtls\\.<domain>(:443)?(/.*)?"}
     ],
     "defaultPermissionPolicy": "GRANT"
   }
   ```

4. **The applications**, installed at enrolment: a browser, told to send the certificate with the
   managed setting `AutoSelectCertificateForUrls` = `["{\"pattern\":\"https://mtls.<domain>\",\"filter\":{}}"]`,
   and a launcher link to `https://mtls.<domain>/`, plus whatever the deployment's users need.

Three things to get right, because they are where ports go wrong:

**The subject is the contract.** Its common name becomes the device's callsign. See
*Appendix A*.

**The MDM must know a per-device value when the device asks**, or the device must be named in the
MDM before it asks. Nobody should have to type a name into a subject per device.

**The policy fields are Android Management API.** They carry to any Android EMM built on AMAPI
and mean nothing to one that is not, and nothing at all to iOS.

If your MDM cannot put any per-device value into the subject, this design does not fit it, and
that is worth knowing on day one rather than after a day of configuration.

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

So:

1. **The MDM is configured** for this deployment. (Part 2.)
2. **Open enrolment** in Deploy App. (Part 4.1.)
3. **Enrol the phones** in the MDM as usual, as many at once as you have hands for.
4. **Leave them alone.** Do not move them between groups, do not re-apply, do not force anything,
   until the applications have finished arriving.
5. **Watch them arrive** on the MDM page, each under the name the MDM gave it. Close enrolment when the last one is in.

:::{warning}
A reset device cannot take its name back. The name is held by the device's old key, and removing
that user spends the name for good. An MDM that names phones by serial number has to give a
reset phone a different subject.
:::

---

## Part 4 — Running it day to day

### 4.1 The MDM page

In Deploy App: **User management → MDM**. It is deliberately the last item in that group.

- It shows the SCEP URL and the challenge, with copy buttons, and opens device enrolment for 2
  hours or closes it. Nothing enrols while it is closed.
- It lists the phones that have enrolled, under the names the MDM gave them, and refreshes while
  open. A phone that should not be there is removed under **User management**, like any user.

### 4.2 Changing what gets installed

Change it in the MDM, or in its connector. The responder knows no package name at all — a test
enforces that — so nothing here changes.

Remember that existing devices will not pick up the change. It applies to devices that enrol
from then on.

### 4.3 Turning enrolment off

Press **Close now** on the MDM page, or let the 2 hours run out. While enrolment is closed,
RASENMAEHER refuses every device before it looks at the request, so nothing behind it can be
guessed at. Reopening makes a new challenge, so give it to the MDM before devices enrol again.
Devices already holding certificates are unaffected.

---

## Part 5 — When it goes wrong

| Symptom | Cause |
|---|---|
| `GetCACaps` returns HTML with HTTP 200 | `location /scep` missing from the proxy; the request fell through to the SPA |
| Saving the CA in the MDM fails | Wrong URL, or the responder is not healthy. Fix before anything else |
| Every enrolment answers 503 on a new deployment | OCSP has no status for the responder's certificate yet. `docker compose exec ocsprest ocsprest ocsp` (*1.3*) |
| Proxy redirects with `exta=FAILED:certificate status request failed` | Same thing: a certificate was presented and its status could not be checked |
| Proxy redirects with `exta=NONE` | No client certificate was presented at all — a different fault from the one above |
| Certificate profile `failed`, nothing in our logs | The subject did not resolve on that phone, so no request was sent. A personally owned phone may not report its serial number; use a value the MDM has for it |
| Device enrolled but no apps | They were not on the group when it joined. Enrol it again, under a new name |
| Browser says `mtls_fail` | Both halves are needed: `choosePrivateKeyRules` says which key *may* be used, `AutoSelectCertificateForUrls` says whether the browser *sends* one. With no match the browser silently declines, which looks identical to having no certificate |
| `urlPattern` seems not to match | It is a `java.util.regex` pattern matched against the **whole** string the app passes. Chrome passes `host:port` with no scheme, so a pattern starting `https://` matches nothing; the pattern in *Part 2* takes both forms |
| Second certificate will not install | The certificate template's name is the Android keystore alias. A second key will not install over an existing alias. Keep the name stable, per deployment |
| Enrolment refused | Enrolment is closed, another key already has the name, or the name is not 3-32 letters, digits or inner hyphens |
| Everything 504s after about two days | Unrelated to MDM — the Linkerd issuer wedge. Restart in the documented order |

A refusal from the responder is **final by design**: the device is meant to stop rather than
retry a callsign it was never going to get. A 503 is the transient one — the responder could not
reach RASENMAEHER — and is deliberately not a signed refusal.

---

## Appendix A — The subject contract

The whole of what an MDM must produce, for anyone porting this.

```
CN=<callsign>
```

The common name becomes the device's callsign, in Deploy App and in every product. Exactly one
CN, 3-32 letters, digits or hyphens with none at either end, and not a name somebody else already has. Other attributes are
the MDM's business; the signer copies the subject into the certificate as it is.

What has to be true is that the MDM knows the value when the device asks: a per-device value it
has at enrolment, or a name somebody gave the device in the MDM before it asked.

A request may not ask for more than a device identity: no extended key usage beyond client
authentication, no subject alternative names, no `CA:TRUE`. The request arrives from a public
endpoint and its contents are entirely the caller's choice, so the shape of what gets issued
cannot be one of the things they choose.

## Appendix B — Settings

Set on RASENMAEHER, already in `docker-compose.yml`:

| Setting | Value | Notes |
|---|---|---|
| `RM_MDM_AGENT_CNS` | `rmscep` | Which certificate CN may enrol devices while enrolment is open. Deliberately not a product CN |

Commands:

| Command | Does |
|---|---|
| `rmscep selftest <callsign>` | Proves the responder end to end, without an MDM |
