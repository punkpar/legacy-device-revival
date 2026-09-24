# References

Vendor sources, community projects and legal authorities used to build this repo. Where a
vendor resource is **dead or discontinued**, that is noted. These links rot, and knowing
*what used to be there* is half the value.

> ⚠️ **No vendor binaries are stored in this repository.** Vendor SDKs, APKs, firmware and
> PC clients are referenced and hashed only. See [`LEGAL.md`](LEGAL.md).

---

## Time2 MIP12

### Vendor: Time2 Technology

| Resource | URL | Status |
|----------|-----|--------|
| Time2 Technology (main site) | <https://www.time2technology.com> | ⚠️ vendor site; **MIP12 discontinued** |
| MIP12 product page | <https://www.time2technology.com/product-downloads/Time2-MIP12-Wireless-Surveillance-Camera.html> | 🔴 **404 / dead**: the page is gone; the product sits under *Support → Discontinued Products* |
| MIP12 manual (PDF) | *shipped with the unit; archived locally* | ✅ (not redistributed here) |
| MIP11 manual (same family) | *archived locally* | ✅ (not redistributed here) |

**Official setup flow** (from the manual), entirely app-based: install the app → **LAN
tab** → camera appears online → **Setup WiFi** → scan → choose router → enter password →
**remove the Ethernet cable**. That last step is load-bearing: the camera only reboots onto
Wi-Fi once the cable is unplugged.

**Vendor apps named by the manual:**

| Platform | App | Note |
|----------|-----|------|
| iOS | **Plug2View** | the App Store listing also appears as "P2PcamViewer" |
| Android | **p2pcamviewer** | package `x.p2p.cam`, label "Plug&Play" |
| Windows | Time2 PC client / "SYSM Monitor" (`www.scc21.net`) | 🔴 **wrong protocol**: this is a **PPPP** client for a different camera generation (see below) |

**Windows client dead end.** `time2-latest-pc-client-setup-20170920.zip`, the only PC
client ever published, contains `PPPP_API.dll`, `IPCClientNetLib.dll`, `NasClientNetLib.dll`
and **zero** HeKai/captetown tokens. It is for a *different* camera generation and was a
**false lead** in the original research. `www.scc21.net` is likewise unrelated.

### Community & protocol sources (HeKai / HK)

| Resource | Link | Why it matters |
|----------|------|----------------|
| **`indykoning/PyPI_p2pcam`** | <https://github.com/indykoning/PyPI_p2pcam> | The base library. Commit `834f1d2` *"Add packet length for Time2 MIP12"* is literally an adaptation for our camera. |
| **`devmlb` fork / PR #3** | <https://github.com/indykoning/PyPI_p2pcam/pull/3> | Reverse-engineered the protocol from the vendor SDKs; named it **HeKai/HK**. Vendored (MIT) into `time2-mip12/p2pcam/`. |
| `jameshilliard/android-p2p-sdk3.0` | <https://github.com/jameshilliard/android-p2p-sdk3.0> | Vendor Android SDK demo: `ViewOfSettingWifi.java` shows the **client-side WiFi flow** (read 204 → scan → `setLanWifi`). |
| `jameshilliard/HKiPhoneSDKDemo20160621` | <https://github.com/jameshilliard/HKiPhoneSDKDemo20160621> | Vendor iOS SDK demo. `include/hkipc.h` **documents `SetLanWifi`** and the `flag`/`isopen` semantics; `HKCameraControl.h` shows `enum scc_param` has **no** WiFi entry. |

> ℹ️ These two `jameshilliard` repos are **mirrors/archives of vendor SDKs** hosted on
> GitHub for interoperability study. We reference them; we do not re-host them.

### Capture tooling

| Tool | Link | Use |
|------|------|-----|
| Android Emulator | <https://developer.android.com/studio/run/emulator> | Running the `armeabi`-only vendor app on x86_64 (ARM translation). |
| `strace` | <https://strace.io> | The decisive capture: `sendto()` revealed the broadcast to `255.255.255.255:2627`. |
| `mksquashfs` / `squashfs-tools` | <https://github.com/plougher/squashfs-tools> | Firmware unpacking (Anyka). |
| `arp-scan` | <https://github.com/royhills/arp-scan> | Finding the camera by MAC OUI on the LAN. |
| `tcpdump` / Wireshark | <https://www.tcpdump.org> · <https://www.wireshark.org> | Packet analysis. |

---

## Anyka AK3918 PTZ ("V380 clone")

### The exploit path

| Resource | Link | Why it matters |
|----------|------|----------------|
| **VGerris: *Anyka AK3918 hacking journey*** | <https://github.com/VGerris/Anyka_ak3918_hacking_journey> | The SD-card `Factory/` trick: the camera's own `service.sh` runs `/mnt/Factory/config.sh` from the card. Basis for running `libre_anyka_app`. ⚠️ **Its prebuilt images are for a *different* camera** (sensor `h63`, Realtek 8188 Wi-Fi); do **not** flash them onto a `gc1084`/`ssv6x5x` unit. |
| `libre_anyka_app` (streamer) | distributed within the VGerris project | The RTSP server that replaces the stock `anyka_ipc`. |

### Hardware notes

| Item | Value / link |
|------|--------------|
| SoC | Anyka **AK3918** |
| Image sensor | **GC1084** (`isp_gc1084.conf`) |
| Wi-Fi | **SSV6006C** (`ssv6x5x.ko`) |
| Cloud stack | Yi IoT / "V380" family |

Both sensor + Wi-Fi parts are on the community supported list for the AK3918 SD-card
hack.

### Home Assistant

| Integration | Link |
|-------------|------|
| Generic Camera | <https://www.home-assistant.io/integrations/generic/> |
| `go2rtc` | <https://github.com/AlexxIT/go2rtc> |
| `command_line` | <https://www.home-assistant.io/integrations/command_line/> |
| `rest_command` | <https://www.home-assistant.io/integrations/rest_command/> |

---

## Legal authorities

| Source | Link |
|--------|------|
| EFF: Coders' Rights, Reverse Engineering FAQ | <https://www.eff.org/issues/coders/reverse-engineering-faq> |
| EFF: Vulnerability Reporting FAQ | <https://www.eff.org/issues/coders/vulnerability-reporting-faq> |
| 17 U.S.C. § 1201 (DMCA anti-circumvention) | <https://www.law.cornell.edu/uscode/text/17/1201> |
| 17 U.S.C. § 107 (fair use) | <https://www.law.cornell.edu/uscode/text/17/107> |
| Cornell LII: reverse engineering (Wex) | <https://www.law.cornell.edu/wex/reverse_engineering> |
| EU Software Directive, Art. 6 (decompilation) | <https://www.wipo.int/wipolex/en/text/126915> |

Case law cited in [`LEGAL.md`](LEGAL.md): *Sega v. Accolade* (977 F.2d 1510, 9th Cir. 1992);
*Sony v. Connectix* (203 F.3d 596, 9th Cir. 2000); *Atari Games v. Nintendo* (975 F.2d 832,
Fed. Cir. 1992); *Compaq v. Procom* (908 F. Supp. 1409, S.D. Tex. 1995); *Davidson v. Jung*
(422 F.3d 630, 8th Cir. 2005); *DVD CCA v. Bunner* (31 Cal.4th 864, Cal. 2003).

---

## Third-party code

| Component | Licence | Upstream |
|-----------|---------|----------|
| `p2pcam` (vendored, `time2-mip12/p2pcam/`) | MIT | <https://github.com/indykoning/PyPI_p2pcam> |
| `libre_anyka_app` (not vendored; recipe only) | see upstream | VGerris project |

Full attribution and licence texts: [`../THIRD-PARTY.md`](../THIRD-PARTY.md).
