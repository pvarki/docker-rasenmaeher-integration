# Why SCEP, and not EST or CMP

A decision record. Checked 2026-10-15; the landscape it rests on is vendor behaviour, so it has
a shelf life.

## The question

Device enrolment needs a certificate enrolment protocol. SCEP (RFC 8894) is old and widely
disliked. Two standards are better by almost every engineering measure:

- **EST** (RFC 7030) — HTTPS and PKCS#10 instead of CMS, with real renewal and CA rollover.
- **CMP** (RFC 9810, which obsoleted RFC 4210 in 2025; RFC 9483 is the lightweight profile) —
  full certificate lifecycle management: issue, key update, revocation, cross-certification.

Should we be building on either instead?

## The decision

**SCEP.** Not as a compromise — as the only protocol that reaches an Android phone through an
MDM today.

The deciding fact is narrow, checkable, and the same for both alternatives: **no MDM offers EST
or CMP for Android.** The one MDM that implements custom EST restricts it to Linux hosts, and
the one Android-side CMP implementation has been deprecated since Android 11.

This is not an argument that SCEP is the better protocol. It is not. It is the only one with
devices on the other end.

## What the MDMs actually support

| MDM / platform | Custom SCEP | Custom EST | CMP | Android |
|---|---|---|---|---|
| FleetDM | Apple, Windows, **Android** | **Linux only** | not offered | SCEP only |
| Microsoft Intune | yes, incl. Android Enterprise | no — SCEP and PKCS; Cloud PKI is SCEP-only | not found | SCEP only |
| Jamf Pro | yes (Apple estate) | no — SCEP and ACME | not found | n/a |
| Omnissa Workspace ONE | yes, generic SCEP authority | not found | not found | SCEP only |
| ManageEngine, Hexnode, Ivanti, BlackBerry UEM | yes | not found | not found | SCEP only |
| Samsung Knox CEP | yes | named | **yes, as a CMP service APK** | Samsung-only, and **deprecated at API level 30 / Knox SDK v3.4.1** with no stated replacement |
| Android Management API itself | none built in | none | none | the EMM owns the protocol; AMAPI only delegates `CERT_INSTALL` |
| Apple MDM payloads | yes | no — the payloads are ACME, SCEP, AD Certificate and PKCS#12 | no | n/a |

:::{note}
"Not found" means the vendor's documentation does not mention that protocol, which is weaker
than a vendor saying no. "Linux only" and "deprecated" are documented, and those are the cells
the decision rests on — everything else could be wrong without changing the outcome.
:::

Two rows settle it. Fleet's own guide makes custom SCEP the only certificate authority type
supporting Android and puts custom EST on Linux alone — so the MDM we have a driver for could
not use EST for our devices even if we spoke it. And Samsung's, the only Android-side CMP
implementation anywhere in the table, has been deprecated since Android 11.

## SWOT

**SCEP — what we build on**

| | |
|---|---|
| **Strengths** | Universal on Android; every MDM speaks it; keys are generated on the device; works today with no vendor cooperation |
| **Weaknesses** | Ancient design; CMS/PKCS#7 wrapping is fiddly to parse safely; one shared non-secret challenge for the estate; no standard renewal |
| **Opportunities** | RFC 8894 (2020) made it a real standard rather than a perpetual draft |
| **Threats** | It is the protocol the industry wants to retire; a future Android could deprecate paths around it |

**EST (RFC 7030) — the alternative**

| | |
|---|---|
| **Strengths** | Cleaner: HTTPS and PKCS#10, no CMS; TLS carries the security properties; proper renewal and CA rollover; the IETF's intended SCEP successor |
| **Weaknesses** | **No Android MDM path exists**; its HTTP-auth model fits our per-enrolment-code convention worse than a subject attribute does |
| **Opportunities** | Strong in IoT and network equipment; if Google or an EMM adds it, our responder could speak both |
| **Threats** | The only Android-adjacent implementation found is Samsung's, and it is deprecated. Adopting EST now means zero devices enrol |

**CMP (RFC 9810, profiled by RFC 9483) — the alternative**

| | |
|---|---|
| **Strengths** | The only one of the three that manages a certificate's whole life: issue, key update, revocation, cross-certification. Actively maintained — RFC 9810 obsoleted RFC 4210 in 2025 and added KEM public keys, which matters for post-quantum. Proven at scale in telecom, where 3GPP uses it for base station enrolment |
| **Weaknesses** | By far the heaviest of the three: its own ASN.1 message layer, its own state machine, and a surface area that RFC 9483 exists specifically to cut down. **No Android MDM path.** The lifecycle features we would be paying that complexity for are ones we do not use — we revoke at the edge and re-plan a callsign rather than key-update |
| **Opportunities** | Strong and growing in industrial and IoT PKI; the post-quantum work lands here first |
| **Threats** | The only Android-side implementation is Samsung Knox CEP, **deprecated at API level 30 (Android 11) with no stated replacement** — and Samsung-only even when it worked. Adopting CMP means writing the most complex of the three protocols for zero devices |

**ACME with device attestation — the real competitor, for a platform we do not target**

Worth naming because it is where the industry is actually moving. Apple requires ACME for
Managed Device Attestation; Jamf Pro 11 supports the payload and Intune began a phased rollout
for Apple enrolments in December 2025. It is Apple-only — there is no Android equivalent. If we
ever manage iOS devices, this is the thing to build, not EST.

## What our weaknesses cost us, and what covers them

The two SCEP weaknesses that matter are the shared challenge and the lack of renewal.

**The challenge is not the gate, and is not treated as one.** It is not a secret: it sits in the
MDM's configuration and travels in every device's request. The control is that an admin planned
the callsign, and that the request carries `<callsign>@<approval code>` — see *Appendix A* of
{doc}`mdm-integration-howto`. A design that leaned on the challenge would be badly exposed by
SCEP's weakness here; ours does not.

**Renewal is unsolved and openly so.** SCEP's renewal story is weak, and a callsign is spent once
used, so a device needing a new certificate needs a new callsign. EST would genuinely be better
here. It is not better enough to outweigh not working at all.

## What would change this

Any one of these, and this is worth reopening:

- Google adds a certificate enrolment protocol to the Android Management API. That is the one
  change that would settle this for everybody, since AMAPI is why the EMM gets to choose at all.
- An Android EMM ships supported EST or CMP — not deprecated, not Samsung-only.
- We start managing Apple devices, at which point ACME with attestation is a separate decision
  from this one and should be taken on its own merits.
- We need certificate lifecycle operations SCEP cannot express — key update or on-device
  renewal rather than re-planning a callsign. That would make CMP's complexity worth paying,
  if by then there were anywhere to spend it.

A note for whoever checks next: the protocol maturity argument has never been the deciding one
and is not worth re-researching on its own. The question is always the same — **can an Android
device, through a shipping MDM, be made to speak it?** Today, for EST and CMP, the answer is no.
