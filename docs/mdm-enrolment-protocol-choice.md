# Why SCEP, and not EST

A decision record. Checked 2026-10-15; the landscape it rests on is vendor behaviour, so it has
a shelf life.

## The question

Device enrolment needs a certificate enrolment protocol. SCEP (RFC 8894) is old and widely
disliked. EST (RFC 7030) is its intended replacement: HTTPS and PKCS#10 instead of CMS, with
real renewal and CA rollover. Should we be building on EST instead?

## The decision

**SCEP.** Not as a compromise — as the only protocol that reaches an Android phone through an
MDM today.

The deciding fact is narrow and checkable: **no MDM offers EST for Android.** Even the one MDM
that implements custom EST at all restricts it to Linux hosts.

## What the MDMs actually support

| MDM / platform | Custom SCEP | Custom EST | Android |
|---|---|---|---|
| FleetDM | Apple, Windows, **Android** | **Linux only** | SCEP only |
| Microsoft Intune | yes, incl. Android Enterprise | no — SCEP and PKCS; Cloud PKI is SCEP-only | SCEP only |
| Jamf Pro | yes (Apple estate) | no — SCEP and ACME | n/a |
| Omnissa Workspace ONE | yes, generic SCEP authority | not found | SCEP only |
| ManageEngine, Hexnode, Ivanti, BlackBerry UEM | yes | not found | SCEP only |
| Samsung Knox CEP | yes | named, but **deprecated** at API level 30 / Knox SDK 3.4.1, and not shipped as its own CEP package | Samsung-only |
| Android Management API itself | none built in | none | the EMM owns the protocol; AMAPI only delegates `CERT_INSTALL` |
| Apple MDM payloads | yes | no — the payloads are ACME, SCEP, AD Certificate and PKCS#12 | n/a |

:::{note}
"Not found" means the vendor's documentation does not mention EST, which is weaker than a vendor
saying no. "Linux only" and "deprecated" are documented, and those are the two cells the decision
rests on.
:::

The row that settles it is Fleet's: its own guide makes custom SCEP the only certificate
authority type supporting Android, and puts custom EST on Linux alone. The MDM we have a driver
for could not use EST for our devices even if we spoke it.

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

- Google adds a certificate enrolment protocol to the Android Management API.
- An Android EMM ships supported EST — not deprecated, not Samsung-only.
- We start managing Apple devices, at which point ACME with attestation is a separate decision
  from this one and should be taken on its own merits.
