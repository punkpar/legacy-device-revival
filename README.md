# Orphaned Device Reverse Engineering

Notes, tools and working integrations for **cheap and end-of-life devices that ship with no
documentation and no local API** — only a closed cloud app and, often, a discontinued
server. IP cameras, Android TV boxes, old smartwatches, e-readers, IoT gadgets: same
problem, different silicon.

The goal of this repo is simple: **document the protocols and interfaces properly so you
don't have to start from zero.** Every device here was bought cheap (or saved from a
skipped bin), and every one of them is now running fully locally — no cloud dependency and
no vendor app.

Everything here is the result of packet capture, static analysis of Android/iOS SDKs and
firmware, and a lot of trial and error. Where a conclusion is *proven* it's stated as
fact; where it's still an open question it's stated as an open question.

---

## Why: re-use instead of e-waste ♻️

Most of these devices are **perfectly good hardware with a software kill-switch.** The
camera works, the box boots, the watch still keeps time — they are thrown away because
the *cloud service* behind them was shut off, the *app* was pulled from the store, or the
vendor simply walked away.

That is a **software problem, not a hardware problem** — and software problems can be
fixed. Documenting the interface is the fix:

- **Keeps working hardware in use.** A device you already own, re-homed onto your own
  server, needs no new manufacturing, no shipping, no mining.
- **Avoids the embodied carbon.** A camera or TV box has already paid its environmental
  cost in production; landfilling a working one and buying a replacement pays it *twice*.
- **Beats locked-down replacements.** The "new" version is usually the same insecure
  closed stack — often *more* locked down, with a new subscription attached.
- **Gives old tin a second life.** An Android box becomes a kiosk display or a Home
  Assistant satellite; a smartwatch becomes a sensor node or a desk clock; the cameras here
  become plain RTSP/ONVIF sources.
- **WEEE / right-to-repair in spirit.** Electronic waste is one of the fastest-growing
  waste streams. The most effective moment to intervene is *before* a still-functional
  device hits the skip.

> We don't dump firmware to "win"; we document it so an owner can keep using what they
> already paid for. If that keeps one more working device out of landfill, it was worth
> writing down.

---

## Devices

Start with the docs for the device you own:

- [`docs/time2-mip12/`](docs/time2-mip12/) — [`PROTOCOL.md`](docs/time2-mip12/PROTOCOL.md)
  (the wire protocol), [`WIFI.md`](docs/time2-mip12/WIFI.md) (WiFi provisioning),
  [`EMULATOR.md`](docs/time2-mip12/EMULATOR.md) (how the capture was made),
  [`HOME-ASSISTANT.md`](docs/time2-mip12/HOME-ASSISTANT.md) (integration).
- [`docs/anyka-ak3918/`](docs/anyka-ak3918/) — the SD-card unlock, hardening and HA
  integration.

| Device | Type | Chip / SoC | Protocol | Status |
|--------|------|-----------|----------|--------|
| [**Time2 MIP12**](docs/time2-mip12/) | IP camera | HeKai/HK (proprietary P2P) | UDP `:2627` discovery + UDP `:5000` video | ✅ **Fully solved** — video, config channel and **WiFi provisioning** all reverse-engineered; running cable-free |
| [**Anyka AK3918 PTZ**](docs/anyka-ak3918/) | IP camera (white "V380 clone") | Anyka AK3918 + SSV6006C | RTSP (via SD-card hack) + CGI | ✅ Unlocked, hardened, HA integrated |

> ℹ️ More devices will land here over time — the layout is generic (`docs/<device>/` +
> a tool folder), so Android boxes, watches and similar toys can be added without any
> restructuring. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Why these two

Both are the same *class* of device — a cheap SoC, a cloud-only app, and a proprietary or
undocumented local interface — but they sit at opposite ends of the difficulty spectrum:

- The **Anyka** has a **known exploit path** (the VGerris `Factory` SD-card trick) that
  replaces the stock app with a community build (`libre_anyka_app`). You get plain RTSP.
  The work is then **hardening** — the stock web UI has a pre-auth root RCE.
- The **Time2 MIP12** has **no public exploit and no replacement firmware**. The only
  route is to reverse the vendor's P2P protocol itself. That's what `docs/time2-mip12/`
  documents.

That spread — *"there's an exploit and you just harden it"* vs *"there's nothing and you
reverse it from scratch"* — is exactly the range this repo wants to cover, whatever the
device.

---

## Repository layout

```
docs/
  LEGAL.md               Why this work is lawful (interoperability, DMCA, fair use)
  REFERENCES.md          All sources, incl. dead vendor pages + community projects
  time2-mip12/           HeKai/HK protocol notes, WiFi provisioning, HA integration
  anyka-ak3918/          SD-card hack, CGI patching, hardening, HA integration
time2-mip12/
  p2pcam/                Python HeKai/HK client (vendored, MIT)
  tools/                 discovery / handshake / config-command / WiFi-setup helpers
anyka-ak3918/
  cgi-bin/               Patched + hardened web UI scripts
  ha/                    Home Assistant integration (command_line, rest_command)
```

Each tool and script has a header comment explaining **what it does, what it expects and
why**. Nothing here needs a vendor account.

---

## ⚠️ Read this first

- **These cameras are insecure by design.** The Anyka ships with a pre-auth root command
  execution hole and root FTP/telnet. The Time2 has an unauthenticated RTSP-equivalent
  video stream and telnet with an unknown password. **Never port-forward them.** Put them
  on an isolated VLAN.
- **No vendor binaries are stored here.** We publish **original code** and **functional
  protocol descriptions** only — never the vendor's firmware, SDK, APK or `.so` files. See
  [`docs/LEGAL.md`](docs/LEGAL.md) for the reasoning (reverse engineering for
  *interoperability*).
- **No credentials are in this repo, ever.** Device keys, passwords, MACs and WiFi secrets
  are externalised and gitignored. If you find one, please report it privately — it's a
  bug. See [`SECURITY.md`](SECURITY.md).
- **This is not legal advice.** Read [`docs/LEGAL.md`](docs/LEGAL.md) before reusing any of
  this work.

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full guide. The short version:
**corrections need evidence** — a capture, a disassembly, or reproducible steps — and you
must never commit credentials or device identifiers.

Two worked examples of *how* the protocol facts here were established, both worth copying
for a new device:

1. **The WiFi command was found by instrumenting the working client, not by reading the
   firmware.** Static analysis told us *what* the command was; only a live `strace` of the
   vendor app revealed *where* it went (a broadcast to `255.255.255.255:2627`, not the
   video socket). See [`docs/time2-mip12/EMULATOR.md`](docs/time2-mip12/EMULATOR.md) for
   the full capture recipe — an x86_64 Android emulator running an `armeabi` app.
2. **A single bad assumption can hide for weeks.** `local_port=0` (see
   [`docs/time2-mip12/PROTOCOL.md`](docs/time2-mip12/PROTOCOL.md)) looked like a protocol
   bug but was a socket collision in our own client.

---

## Legal, references & security

| Document | What's in it |
|----------|--------------|
| [`docs/LEGAL.md`](docs/LEGAL.md) | Why this is lawful: interoperability, DMCA § 1201(f), fair use, the case law, and what we therefore do/do not publish. |
| [`docs/REFERENCES.md`](docs/REFERENCES.md) | Every source used — **including dead vendor pages**, community projects, and the legal authorities. |
| [`SECURITY.md`](SECURITY.md) | Coordinated disclosure (90-day) and how to report privately. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Evidence requirements and the never-commit list. |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Contributor Covenant 2.1. |

---

## Licence

Original work in this repo is released under the **MIT Licence** (see [`LICENSE`](LICENSE)).
Vendored third-party code remains under its own licence (see [`THIRD-PARTY.md`](THIRD-PARTY.md)).
Vendor SDKs, firmware and clients are **referenced, never redistributed** — see
[`docs/LEGAL.md`](docs/LEGAL.md).
