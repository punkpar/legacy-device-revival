# Legal & Ethical Posture

> **This is not legal advice.** It explains the reasoning behind how this project is
> published: the same reasoning used by comparable reverse-engineering projects. If you
> are unsure about your own use, consult a lawyer. The Electronic Frontier Foundation's
> [Coders' Rights Project](https://www.eff.org/issues/coders) can help you find one.

This document exists because the repo documents **proprietary protocols** belonging to
third parties. That is legitimate, well-trodden work, but only when it is framed and
scoped correctly. Here is the frame, and how this repo stays inside it.

---

## 1. The purpose is **interoperability**, not circumvention

Everything here was done to make **devices we own** work with software we control
(Home Assistant, `go2rtc`, our own bridges) **without the vendor's cloud app**.

That goal has specific legal protection:

- **DMCA § 1201(f)** (17 U.S.C. § 1201(f)), the *reverse-engineering exception*, permits
  circumvention of an access control **solely to identify and analyse the elements
  necessary to achieve interoperability** of an **independently created** program.
  ([Cornell LII](https://www.law.cornell.edu/wex/reverse_engineering),
  [EFF FAQ](https://www.eff.org/issues/coders/reverse-engineering-faq))
- **Fair use** (17 U.S.C. § 107): courts have repeatedly found that *intermediate*
  copying for the purpose of learning functional interface specifications is a fair use,
  provided the resulting program is original.

The corollary is just as important: **this project only studies the interface, and ships
only original implementations of it.** It never redistributes the vendor's code.

---

## 2. The case law this rests on

| Case | Holding relevant here |
|------|-----------------------|
| *Sega Enterprises v. Accolade*, 977 F.2d 1510 (9th Cir. 1992) | Disassembling firmware to learn the interface was fair use; the resulting games were original code. |
| *Sony Computer Entertainment v. Connectix*, 203 F.3d 596 (9th Cir. 2000) | Intermediate copying of a BIOS to build an emulator was fair use. |
| *Atari Games v. Nintendo*, 975 F.2d 832 (Fed. Cir. 1992) | Reverse engineering to learn the lock interface was a fair use, **but** using a copy obtained improperly, or copying more than necessary, was not. Lesson: **obtain the device legally, and copy no more than the interface.** |
| *Compaq v. Procom*, 908 F. Supp. 1409 (S.D. Tex. 1995) | Verbatim copying of creative parameter values was infringing. Lesson: **express facts functionally; do not reproduce creative content.** |
| *Davidson & Associates v. Jung* (Blizzard/BnetD), 422 F.3d 630 (8th Cir. 2005) | ⚠️ The cautionary tale: a **mass-market EULA that banned reverse engineering was enforced**, and the DMCA interoperability exception did **not** save the defendants because their use was not authorised. Lesson: **be aware of any EULA/TOS you agreed to.** |
| *DVD CCA v. Bunner*, 31 Cal.4th 864 (Cal. 2003) | Trade-secret claim over reverse-engineered facts; a concurrence rejected the idea that a consumer-form EULA redefines "improper means". |

The pattern: **interoperability on hardware you legitimately own, expressed as
functional facts, implemented in your own code, is the protected zone.**

---

## 3. What this repo does, and does not do

| ✅ We do | ❌ We do not |
|---------|-------------|
| Document the wire protocol in functional terms (ports, packet layouts, field meanings). | Ship the vendor's firmware, SDK, APK, or `.so` binaries. |
| Provide **original** Python/bash implementations of public interfaces. | Redistribute disassembled/decompiled vendor code. |
| Publish hashes and short hex excerpts **of our own captures**. | Publish captures containing credentials or personal data. |
| Say plainly which findings are proven and which are open. | Provide tools or keys to defeat encryption *for unauthorised access*. |
| Vendor third-party code **only** under its own licence, with notice. | Include any device credential, PSK, MAC, serial, or UID. |

We also deliberately **do not** publish a working bypass for the devices' own access
controls, beyond what is required to interoperate locally. Where a device is insecure,
that is documented in the hardening notes so owners can *close* the hole. See
[`anyka-ak3918/HARDENING.md`](anyka-ak3918/HARDENING.md).

---

## 4. EULA / TOS awareness

The strongest legal risk in reverse engineering is **contract**, not copyright. A EULA or
terms-of-service you agreed to can restrict reverse engineering, and courts have enforced
those terms (*Blizzard/BnetD*).

**Our position:** the vendor applications studied here were obtained as free public
downloads, and were **not** accompanied by a negotiated agreement or an accepted
"no-reverse-engineering" contract in the course of this work. Where a vendor offers
explicit terms, that is noted in [`REFERENCES.md`](REFERENCES.md). If you re-do this work,
**read any terms you are asked to accept first.**

---

## 5. Responsible disclosure

Findings about *security defects* in these devices are handled separately from protocol
documentation:

- We follow **coordinated disclosure**: see [`../SECURITY.md`](../SECURITY.md).
- We do **not** publish a working exploit for a device credential/authentication bypass
  where the vendor is reachable and a fix is plausible.
- Device families that are **end-of-life and unsupported** (the devices here are
  discontinued) are documented openly, because coordinated disclosure is moot and owners
  need the information to protect themselves.

EFF's guidance on vulnerability reporting:
<https://www.eff.org/issues/coders/vulnerability-reporting-faq>

---

## 6. Jurisdiction caveat

The analysis above is **U.S.-centric** because that is where most of the settled precedent
sits. Rules differ elsewhere: for example, **EU Software Directive Article 6** permits
reverse engineering for interoperability and holds that contracts cannot override it.
Check your own jurisdiction, and see [`REFERENCES.md`](REFERENCES.md) for sources.

---

## 7. Why we publish at all

Devices like these are sold with **no documentation, no support, and no future**. When the
vendor's cloud is switched off (as it already has been for the discontinued devices here),
the hardware becomes e-waste *unless someone documents how it works*.

Publishing the interface is what lets an owner keep using hardware they paid for, and what
keeps otherwise-orphaned devices out of landfill. It also turns them into *donors*: an old
camera becomes an RTSP source, an old Android box becomes a kiosk or a voice satellite, an
old watch becomes a sensor node. **Re-use is the best recycling**: it needs no new
manufacturing, no shipping, and avoids paying a device's embodied carbon twice.
