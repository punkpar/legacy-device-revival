# Contributing

Thanks for being here. This repo exists to document device protocols and interfaces
**properly**, so that the next person doesn't have to start from zero. Contributions that
make the record more accurate and more useful are very welcome.

---

## The one rule: claims need evidence

This is a reverse-engineering repo, so **"I think it works like X" is not enough.** Any
correction to a protocol claim must come with one of:

- a **packet capture** (redacted; see below), or
- a **disassembly** / decompilation with the address or offset, or
- **reproducible steps** anyone can follow on the same device/firmware.

If you found something by trial and error, that's fine: show the *reproducible steps* and
say which part is inference. Mark clearly what is **proven** vs **hypothesised**. We'd rather
have "unknown, here's what I tried" than a confident guess.

---

## 🔴 Never commit credentials or identifiers

Before you open a PR, make sure it contains **none of the following**:

- Wi-Fi SSIDs / PSKs, device passwords, access codes, pairing keys
- MAC addresses, serial numbers, UIDs / HKIDs, IMEIs
- Public IPs, personal hostnames, real personal domains

Use obviously-fake placeholders (`MyNetwork`, `hunter2`, `aa:bb:cc:dd:ee:ff`,
`CAMID0000000`-style example IDs). Secret files (`.wificreds`, `.env`, `secrets.yaml`,
`*.pcap`) are gitignored; keep them that way.

> If a secret *is* committed, treat it as an incident: rotate it, and tell us via
> [`SECURITY.md`](SECURITY.md) so we can purge history.

---

## Ways to contribute

| Contribution | What we want |
|--------------|--------------|
| **Protocol corrections** | Capture + the exact byte you're disputing. |
| **New device write-ups** | A `docs/<device>/` folder following the existing structure. |
| **Home Assistant integrations** | Working YAML, with the HA version you tested on. |
| **Tools** | Original code, a header comment explaining *what/why*, and a `--dry-run` default where anything is transmitted. |
| **Docs fixes** | Typos, dead links, clarifications: always welcome. |

---

## Style

- **Docs live in `docs/<device>/`** as Markdown. Lead with the facts, then the story, then
  the open questions. Every non-obvious byte should be explained.
- **Tools live beside the device** (`time2-mip12/tools/`, `anyka-ak3918/`), one file per
  purpose, with a docstring header.
- **Prefer Python stdlib** for tools: no heavy dependencies, so they run anywhere.
- **Explicit beats clever.** Name constants after what they *are* (e.g. `SETWIFI_HEADER`,
  `XOR_KEY = 0x3C`) and comment the magic.
- **State the licence.** New original code is contributed under this repo's MIT licence
  (see [`LICENSE`](LICENSE)); vendored code keeps its own licence and goes in
  [`THIRD-PARTY.md`](THIRD-PARTY.md).

---

## Legal

By contributing you agree your original contribution is licensed under this repo's **MIT
licence**. Please do **not** contribute vendor binaries, decompiled vendor source, or
anything you obtained under an NDA or a "no reverse engineering" agreement. Read
[`docs/LEGAL.md`](docs/LEGAL.md) before submitting anything derived from a vendor binary.

---

## Opening a pull request

1. Fork, branch, make your change.
2. Check it against the "one rule" and the "never commit" list above.
3. Describe **what you changed and why**, and include your evidence.
4. Small, focused PRs get reviewed fastest.

There is no CLA: the MIT licence covers inbound contributions (GitHub's default
"inbound = outbound" under its Terms of Service).

---

## Code of conduct

Participation is covered by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Be decent.
