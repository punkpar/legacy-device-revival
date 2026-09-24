# Legacy Device Revival

**Orphaned device reverse engineering**: protocols, tools and working integrations for
**cheap and end-of-life devices that ship with no
documentation and no local API**, only a closed cloud app and, often, a discontinued
server. IP cameras, Android TV boxes, old smartwatches, e-readers, IoT gadgets: same
problem, different silicon.

The point is to **document the protocols and interfaces properly, so you don't have to
start from zero.** Every device here was bought cheap (or saved from a skipped bin), and
every one of them is now running fully locally: no cloud dependency and no vendor app.

Everything here is the result of packet capture, static analysis of Android/iOS SDKs and
firmware, and a lot of trial and error. Where a conclusion is *proven* it's stated as
fact; where it's still an open question it's stated as an open question.

---

## Why: re-use instead of e-waste ♻️

Most of these devices are **perfectly good hardware with a software kill-switch.** The
camera works, the box boots, the watch still keeps time. They are thrown away because
the *cloud service* behind them was shut off, the *app* was pulled from the store, or the
vendor simply walked away.

That is a **software problem, not a hardware problem**, and software problems can be
fixed. Documenting the interface is the fix:

- **Keeps working hardware in use.** A device you already own, re-homed onto your own
  server, needs no new manufacturing, no shipping, no mining.
- **Avoids the embodied carbon.** A camera or TV box has already paid its environmental
  cost in production; landfilling a working one and buying a replacement pays it *twice*.
- **Beats locked-down replacements.** The "new" version is usually the same insecure
  closed stack, often *more* locked down, with a new subscription attached.
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

- [`docs/time2-mip12/`](docs/time2-mip12/): [`PROTOCOL.md`](docs/time2-mip12/PROTOCOL.md)
  (the wire protocol), [`WIFI.md`](docs/time2-mip12/WIFI.md) (WiFi provisioning),
  [`EMULATOR.md`](docs/time2-mip12/EMULATOR.md) (how the capture was made),
  [`HOME-ASSISTANT.md`](docs/time2-mip12/HOME-ASSISTANT.md) (integration).
- [`docs/anyka-ak3918/`](docs/anyka-ak3918/): the SD-card unlock, hardening and HA
  integration.
- [`docs/hudl2/`](docs/hudl2/): rooting a **hardware-locked** Bay Trail tablet via
  `run-as` + Dirty COW, and the SELinux/capability ceiling that stops it short of a full
  root.
- [`docs/kawa-mini-3-pro/`](docs/kawa-mini-3-pro/): a SigmaStar dashcam's unauthenticated
  RTSP stream, root shell and HTTP filesystem.
- [`docs/geekmagic-smalltv-ultra/`](docs/geekmagic-smalltv-ultra/): an ESP8266 weather
  clock driven entirely by its own HTTP API, with no vendor app.
- [`docs/pc-wake-by-ble-gamepad/`](docs/pc-wake-by-ble-gamepad/): waking a powered-off PC
  from a **Bluetooth gamepad**: no wake dongle, no custom firmware, by reusing a BLE proxy
  you already own. Not a device revival, but the same "re-use what you have" idea.

| Device | Type | Chip / SoC | Protocol | Status |
|--------|------|-----------|----------|--------|
| [**Time2 MIP12**](docs/time2-mip12/) | IP camera | HeKai/HK (proprietary P2P) | UDP `:2627` discovery + UDP `:5000` video | ✅ **Fully solved**: video, config channel and **WiFi provisioning** all reverse-engineered; running cable-free |
| [**Anyka AK3918 PTZ**](docs/anyka-ak3918/) | IP camera (white "V380 clone") | Anyka AK3918 + SSV6006C | RTSP (via SD-card hack) + CGI | ✅ Unlocked, hardened, HA integrated |
| [**Tesco Hudl 2**](docs/hudl2/) | Android tablet (orphaned) | Intel Atom Bay Trail (x86_64) | ADB + `run-as` (Dirty COW) | ✅ Rooted **without a bootloader unlock**; SELinux/capability ceiling documented |
| [**KAWA MINI 3 Pro**](docs/kawa-mini-3-pro/) | Dashcam | SigmaStar (BusyBox Linux) | RTSP + telnet + thttpd HTTP | ✅ RTSP, root shell and full-filesystem HTTP documented |
| [**GeekMagic SmallTV-Ultra**](docs/geekmagic-smalltv-ultra/) | Weather clock | ESP8266 | HTTP `/set` + `/wifisave` | ✅ Provisioned and driven locally, no vendor app |

> 🔎 **Searching for your camera?** These devices are sold under many names:
> **Time2 MIP12**: apps *Plug2View* / *P2PcamViewer* (Android `x.p2p.cam`), HeKai/HK P2P.
> **Anyka AK3918 PTZ**: the white **V380** clone (Yi IoT cloud stack), also sold as
> **TECKIN TC100** and other white-labels. If yours runs one of those apps or SoCs, the
> docs here apply to it.

> 🔎 **Own a Hudl 2?** The technique (Dirty COW over the setuid `run-as` binary) is not
> camera-specific and the **SELinux/capability analysis applies to any Android 5.x device
> whose kernel is in the Dirty COW range (2.6.22 to 4.8.3)**; see [`docs/hudl2/`](docs/hudl2/).

> 🔎 **Own a SigmaStar dashcam?** The RTSP path `/liveRTSP/av4` and the `libmi_*` SDK
> library names are common across SigmaStar IPC/dashcam firmware, so much of
> [`docs/kawa-mini-3-pro/`](docs/kawa-mini-3-pro/) applies to sibling devices (DDPAI and
> others).

> ℹ️ More devices will land here over time. The layout is generic (`docs/<device>/` +
> a tool folder), so Android boxes, watches and similar toys can be added without any
> restructuring. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Also here: wake a PC from a Bluetooth gamepad

Not every page here is a device teardown. [`docs/pc-wake-by-ble-gamepad/`](docs/pc-wake-by-ble-gamepad/)
applies the same idea to a *capability* rather than a device: **most Bluetooth gamepads
cannot wake a PC**, and the usual fix is to buy or build a dedicated USB wake dongle. This
write-up shows the route that needs **no new hardware**: a BLE proxy on a USB port that
stays powered while the PC is off does the listening, and Home Assistant turns the resulting
advertisement into a Wake-on-LAN packet.

It is here because it shares the repo's premise: **the hardware you already own is almost
always capable enough**, and the only thing missing is documentation.

---

## Why these five

All five are the same *class* of device: a cheap SoC, a cloud-only (or dead) app, and a
proprietary or undocumented local interface. They span the difficulty range this repo is
meant to cover:

- The **Anyka** has a **known exploit path** (the VGerris `Factory` SD-card trick) that
  replaces the stock app with a community build (`libre_anyka_app`). You get plain RTSP.
  The work is then **hardening**: the stock web UI has a pre-auth root RCE.
- The **Time2 MIP12** has **no public exploit and no replacement firmware**. The only
  route is to reverse the vendor's P2P protocol itself. That's what `docs/time2-mip12/`
  documents.
- The **Hudl 2** has a **hardware-locked bootloader** and no recovery, so the *usual*
  route (unlock → custom recovery → root) is closed. The write-up shows the route that
  *does* work: a public kernel bug pointed at a setuid binary, and, honestly, exactly
  where it stops.
- The **KAWA dashcam** has **no exploit and no docs**, but it leaks everything by
  accident: RTSP, a root shell and its whole filesystem, all unauthenticated. The work is
  cataloguing (and warning about) what is already exposed.
- The **GeekMagic clock** is **closed and cloud-bound**, but documents its own HTTP API in
  the JavaScript it serves. The work is reading what the device already tells you.

That spread (*"there's an exploit and you just harden it"* vs *"there's nothing and you
reverse it from scratch"* vs *"the door is welded shut, here's the window"* vs *"it's wide
open, here's the map"*) is the range this repo covers, whatever the device.

---

## Repository layout

```
docs/
  LEGAL.md               Why this work is lawful (interoperability, DMCA, fair use)
  REFERENCES.md          All sources, incl. dead vendor pages + community projects
  time2-mip12/           HeKai/HK protocol notes, WiFi provisioning, HA integration
  anyka-ak3918/          SD-card hack, CGI patching, hardening, HA integration
  hudl2/                 run-as + Dirty COW rooting, SELinux/capability ceiling
  kawa-mini-3-pro/       SigmaStar dashcam: RTSP, root shell, HTTP filesystem
  geekmagic-smalltv-ultra/  ESP8266 clock: HTTP API, provisioning, HA integration
  pc-wake-by-ble-gamepad/  Wake a PC from a BLE gamepad using a proxy you already own
time2-mip12/
  p2pcam/                Python HeKai/HK client (vendored, MIT)
  tools/                 discovery / handshake / config-command / WiFi-setup helpers
anyka-ak3918/
  cgi-bin/               Patched + hardened web UI scripts
  ha/                    Home Assistant integration (command_line, rest_command)
hudl2/
  exploit/               Original payload, SELinux probe, inline-syscall optimizer, re-root
pc-wake-by-ble-gamepad/
  tools/                 BLE advert watcher, Bermuda tracker add, IRK verifier, HA package
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
  protocol descriptions** only, never the vendor's firmware, SDK, APK or `.so` files. See
  [`docs/LEGAL.md`](docs/LEGAL.md) for the reasoning (reverse engineering for
  *interoperability*).
- **No credentials are in this repo, ever.** Device keys, passwords, MACs and WiFi secrets
  are externalised and gitignored. If you find one, please report it privately; it's a
  bug. See [`SECURITY.md`](SECURITY.md).
- **This is not legal advice.** Read [`docs/LEGAL.md`](docs/LEGAL.md) before reusing any of
  this work.

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full guide. The short version:
**corrections need evidence** (a capture, a disassembly, or reproducible steps), and you
must never commit credentials or device identifiers.

Worked examples of *how* the protocol facts here were established, both worth copying
for a new device:

1. **The WiFi command was found by instrumenting the working client, not by reading the
   firmware.** Static analysis told us *what* the command was; only a live `strace` of the
   vendor app revealed *where* it went (a broadcast to `255.255.255.255:2627`, not the
   video socket). See [`docs/time2-mip12/EMULATOR.md`](docs/time2-mip12/EMULATOR.md) for
   the full capture recipe: an x86_64 Android emulator running an `armeabi` app.
2. **A single bad assumption can hide for weeks.** `local_port=0` (see
   [`docs/time2-mip12/PROTOCOL.md`](docs/time2-mip12/PROTOCOL.md)) looked like a protocol
   bug but was a socket collision in our own client.

---

## Legal, references & security

| Document | What's in it |
|----------|--------------|
| [`docs/LEGAL.md`](docs/LEGAL.md) | Why this is lawful: interoperability, DMCA § 1201(f), fair use, the case law, and what we therefore do/do not publish. |
| [`docs/REFERENCES.md`](docs/REFERENCES.md) | Every source used, **including dead vendor pages**, community projects, and the legal authorities. |
| [`SECURITY.md`](SECURITY.md) | Coordinated disclosure (90-day) and how to report privately. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Evidence requirements and the never-commit list. |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Contributor Covenant 2.1. |

---

## Licence

Original work in this repo is released under the **MIT Licence** (see [`LICENSE`](LICENSE)).
Vendored third-party code remains under its own licence (see [`THIRD-PARTY.md`](THIRD-PARTY.md)).
Vendor SDKs, firmware and clients are **referenced, never redistributed**. See
[`docs/LEGAL.md`](docs/LEGAL.md).
