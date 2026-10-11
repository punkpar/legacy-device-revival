# Legacy Device Revival

Here's the thing about cheap orphaned hardware, sweetie: the hardware is usually fine. It's the cloud app behind it that died.

This repo documents the **protocols, methods, and working tools** to run each device locally, with no vendor app and no cloud. Everything here was proven with packet captures, firmware analysis, and live testing. Proven facts are stated as facts. Open questions are labelled as open questions.

> Good hardware with a dead cloud service is a software problem. Software problems can be fixed. If this keeps one more working device out of landfill, it was worth writing down.

---

## Devices: pick yours, follow the method

| Device | What it is | Method that works | Status |
|--------|-----------|-------------------|--------|
| [**Time2 MIP12**](docs/time2-mip12/) | IP camera, HeKai/HK P2P (UDP `:2627` + `:5000`) | Reverse the P2P protocol: [`PROTOCOL.md`](docs/time2-mip12/PROTOCOL.md) for video, [`WIFI.md`](docs/time2-mip12/WIFI.md) for cable-free provisioning, [`HOME-ASSISTANT.md`](docs/time2-mip12/HOME-ASSISTANT.md) to serve it as MJPEG → go2rtc | ✅ Fully local, running cable-free |
| [**Anyka AK3918 PTZ**](docs/anyka-ak3918/) | White V380-clone PTZ (Anyka AK3918 + SSV6006C) | SD-card `Factory` boot trick → community `libre_anyka_app` for RTSP, then harden: [`README.md`](docs/anyka-ak3918/README.md), [`HARDENING.md`](docs/anyka-ak3918/HARDENING.md), [`HOME-ASSISTANT.md`](docs/anyka-ak3918/HOME-ASSISTANT.md) | ✅ Unlocked, hardened, in HA |
| [**Tesco Hudl 2**](docs/hudl2/) | 2014 Bay Trail tablet, bootloader hardware-locked | Dirty COW (CVE-2016-5195) over setuid `run-as`, no unlock needed. [`README.md`](docs/hudl2/README.md) for the root, [`ROOTING.md`](docs/hudl2/ROOTING.md) for exactly where it stops (SELinux + capabilities) | ✅ Rooted; ceiling documented honestly |
| [**KAWA MINI 3 Pro**](docs/kawa-mini-3-pro/) | SigmaStar dashcam (BusyBox Linux) | Nothing to exploit, it leaks everything: unauthenticated RTSP at `/liveRTSP/av4`, empty-password telnet root, whole filesystem over HTTP. One page: [`README.md`](docs/kawa-mini-3-pro/README.md) | ✅ Mapped, with hardening notes |
| [**GeekMagic SmallTV-Ultra**](docs/geekmagic-smalltv-ultra/) | ESP8266 weather clock | Read its own JavaScript: the HTTP API (`/set`, `/wifisave`) is self-documenting. [`README.md`](docs/geekmagic-smalltv-ultra/README.md) covers provisioning, API, and HA | ✅ No app, no cloud |
| [**Lenovo MIIX 520**](docs/miixpad-520/) | 2018 detachable (i5-8250U) | Honest negative result: fingerprint (Synaptics `SYNA8005`, SPI) and touchscreen (Wacom `WCOM513F`, I²C-HID) are driverless on Linux. [`FINGERPRINT.md`](docs/miixpad-520/FINGERPRINT.md) + [`TOUCHSCREEN.md`](docs/miixpad-520/TOUCHSCREEN.md). ⛔ The GPIO power-on trick **bricks the EC**, don't try it | ⚠️ Documented dead ends so you don't repeat them |
| [**Wake a PC from a BLE gamepad**](docs/pc-wake-by-ble-gamepad/) | Xbox Series pad + ESP32 BLE proxy + Home Assistant | Pad advertises when it loses its host → proxy relays → HA sends Wake-on-LAN. [`README.md`](docs/pc-wake-by-ble-gamepad/README.md). No dongle, no custom firmware | ✅ Proven end-to-end |

> 🔎 **Same device, different name?** The Time2 also ships as *Plug2View* / *P2PcamViewer* (Android `x.p2p.cam`). The Anyka white dome also ships as **TECKIN TC100** and other V380 white-labels. The KAWA `/liveRTSP/av4` path and `libmi_*` library names hold across SigmaStar IPC/dashcam firmware (DDPAI and siblings). The Hudl 2 Dirty COW + `run-as` route applies to any Android 5.x device with a kernel in the 2.6.22–4.8.3 range.

---

## Layout

```
docs/<device>/     one folder per device, the write-up lives here
<device>/          matching tool folder, scripts with header comments
docs/LEGAL.md      why this is lawful (interoperability)
docs/REFERENCES.md every source, including dead vendor pages
```

Nothing here needs a vendor account. Every script header says what it does and what it expects.

---

## ⚠️ Safety first, darling

- **These cameras are insecure by design.** The Anyka ships pre-auth root RCE plus root FTP/telnet. The Time2 has an unauthenticated video stream. The KAWA has an empty root password and serves its whole filesystem over HTTP. **Never port-forward any of them.** Isolated VLAN, always.
- **No vendor binaries here.** Original code and functional protocol descriptions only, never firmware, SDKs, APKs, or `.so` files. That's the interoperability rule; [`docs/LEGAL.md`](docs/LEGAL.md) has the reasoning.
- **No credentials, ever.** Keys, passwords, MACs, WiFi secrets stay out of the repo. Spot one? Report it privately, it's a bug. See [`SECURITY.md`](SECURITY.md).

---

## Contributing

Corrections need evidence: a capture, a disassembly, or reproducible steps. Full guide in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Licence

MIT for original work (see [`LICENSE`](LICENSE)). Vendored code keeps its own licence (see [`THIRD-PARTY.md`](THIRD-PARTY.md)).
