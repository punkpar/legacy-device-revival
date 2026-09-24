# Security Policy

## Reporting a vulnerability

This repository documents the protocols of **third-party devices**. If you find a security
issue, please report it privately first.

**Please use GitHub's private vulnerability reporting**: on this repo, go to
**Security → Report a vulnerability**. That opens a private advisory only the maintainers
can see.

Do **not** open a public issue for something exploitable before it has been disclosed
(see the timeline below).

### What is in scope

| In scope | Notes |
|----------|-------|
| A defect in **our** code (the tools, bridge, or Home Assistant integration in this repo) | e.g. an injection bug, credential leak, unsafe default. |
| A **protocol/security finding about a device** documented here | Handled as coordinated disclosure: see below. |
| A **credential or personal identifier accidentally committed** | Highest priority: report immediately; we treat it as an incident. |

### What is out of scope

- The inherent insecurity of the devices themselves, *as a report*. The docs already state
  plainly that these devices have unauthenticated streams, closed-source cloud stacks and
  (in the Anyka's case) a pre-auth command injection. That is the *subject* of the repo, not
  a new finding.
- Vulnerabilities in the **vendored** `p2pcam` library: please report those upstream to
  <https://github.com/indykoning/PyPI_p2pcam>, and let us know so we can bump it.
- Scanner output with no demonstrated impact.

---

## Coordinated disclosure timeline

For a **new** device security defect (not already documented here):

| Day | Action |
|-----|--------|
| 0 | You report privately; we acknowledge within **7 days**. |
| 0–90 | We attempt to contact the vendor/upstream and document the issue. We may publish protocol-level mitigations (e.g. "don't expose this port") immediately, because defensive guidance is not an exploit. |
| 90 | **Public disclosure** in this repo and/or the relevant upstream tracker, whether or not the vendor has responded. |

If the vendor is **unreachable** or the product is **discontinued / end-of-life**, we may
publish sooner: coordinated disclosure has no counterparty in that case, and owners need
the information to protect themselves. Both devices documented here are discontinued.

EFF's guidance on vulnerability reporting:
<https://www.eff.org/issues/coders/vulnerability-reporting-faq>

---

## Our own practices

- **No credentials in the repo, ever.** Device keys, PSKs, MACs, serials, UIDs and hostnames
  are externalised to gitignored files (`.wificreds`, `.env`, `secrets.yaml`).
- **No vendor binaries.** Only original code and functional descriptions are stored here.
  See [`docs/LEGAL.md`](docs/LEGAL.md).
- **Push protection & secret scanning** are recommended to be enabled on this repository so
  that a secret is blocked *before* it lands (GitHub → Settings → Code security).
- **Defensive framing.** We document how to *harden* these devices, and explicitly tell
  owners **not** to port-forward or expose them.

---

## Supported versions

This is a documentation-and-tools repo, not a released library. Only the **latest commit on
`main`** is supported. Fixes are applied there.
