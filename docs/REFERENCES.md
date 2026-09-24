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

## Tesco Hudl 2

### The vulnerability

| Resource | Link | Why it matters |
|----------|------|----------------|
| Dirty COW, CVE-2016-5195 (NVD) | <https://nvd.nist.gov/vuln/detail/CVE-2016-5195> | The kernel race (COW on private read-only mappings, `get_user_pages` vs `/proc/self/mem`). Affects Linux 2.6.22 to 4.8.3; this device is on **3.10.62**. |
| Dirty COW project page | <https://dirtycow.ninja> | The original disclosure and links to the public PoCs. |
| `timwr/CVE-2016-5195` | <https://github.com/timwr/CVE-2016-5195> | The widely-used **Android** port of the Dirty COW PoC (the `dcow` binary used here). **Third-party: not redistributed in this repo.** |

### Android `run-as` and SELinux

| Resource | Link | Why it matters |
|----------|------|----------------|
| Android `run-as` (source) | <https://cs.android.com/android/platform/superproject/+/master:system/core/run-as/run-as.cpp> | `run-as` is setuid-root and the entry point into the `runas` domain: the property the technique exploits. |
| Android SELinux (AOSP docs) | <https://source.android.com/docs/security/features/selinux> | Domain model; why a `uid=0` process is still confined by its domain. |
| `capabilities(7)` (Linux man-pages) | <https://man7.org/linux/man-pages/man7/capabilities.7.html> | `CAP_SYS_MODULE` and the bounding/effective sets: why `init_module()` returns `EPERM`, not `EACCES`. |
| Sean Pesce: Android kernel module loading & SELinux | <https://seanpesce.blogspot.com/> | The `init_module()` vs `finit_module()` distinction (SELinux checks the **process** vs the **file**) that the probe is built around. |

### Device references

| Resource | Link | Status |
|----------|------|--------|
| Tesco Hudl (Wikipedia) | <https://en.wikipedia.org/wiki/Tesco_Hudl> | 🔴 The Hudl line was **discontinued**; Tesco shut the Hudl services and store. |
| Intel Atom Z3735 (ARK) | <https://www.intel.com/content/www/us/en/products/sku/80274/intel-atom-processor-z3735f-2m-cache-up-to-1-83-ghz/specifications.html> | Bay Trail SoC family reference (see `docs/hudl2/README.md` §1 on the D/G suffix ambiguity). |
| Pegatron / `octagon` board | *no public documentation* | The board id (`ro.build.flavor = octagon_64p-user`) is only recoverable from the device's own build props. |

---

## KAWA MINI 3 Pro

### Vendor & device

| Resource | Link | Status |
|----------|------|--------|
| KAWA official product page | <https://www.kawa-in.com/products/mini-3-pro> | ✅ live |
| KAWA FCC filing (`2AZWZ-MINI3`) | <https://fccid.io/2AZWZ-MINI3> | ✅ schematics, block diagrams |
| KAWA user manual | <https://device.report/manual/18299064> | ✅ PDF |

### SigmaStar / dashcam reverse-engineering

| Resource | Link | Why it matters |
|----------|------|----------------|
| GoPrawn SigmaStar/MStar cam thread (archived) | <https://web.archive.org/web/20220325143203/https://www.goprawn.com/forum/sigmastar-mstar-ait-cams/12766-ait-mstar-sigmastar-cams-hacks> | The SigmaStar CGI API and LIVE555 config that name the RTSP path family. |
| DDPAI reverse-engineering write-up | <https://www.eionix.co.in/2019/10/10/reverse-engineer-ddpai-firmware.html> | Port 6200, REST API, full API list. |
| `pwrtux/visiondash` (DDPAI tool) | <https://github.com/pwrtux/visiondash/blob/main/ddpai_tool.py> | Where `/liveRTSP/av4` was confirmed; shared SDK with KAWA. |
| DashCamTalk: reverse-engineering web APIs | <https://dashcamtalk.com/forum/threads/reverse-engineering-web-api-live-feed-etc.21057/> | General dashcam RE patterns. |
| SigmaStar SDK docs (sensor-to-RTSP) | <https://doc.comake.online/d2_sigdoc_en/customer/IPC/Development/sensor_to_rtsp_en.html> | The `libmi_*` MI pipeline. |
| OpenIPC | <https://openipc.org/> | Open firmware for IP cameras (adjacent ecosystem). |
| LIVE555 | <http://www.live555.com/liveMedia/> | The RTSP server library reported in the SDP. |
| CamioCam RTSP paths | <https://github.com/CamioCam/rtsp> | Common camera RTSP path lists. |
| GitHub `topics/sigmastar` | <https://github.com/topics/sigmastar> | Community projects. |

---

## GeekMagic SmallTV-Ultra

| Resource | Link | Why it matters |
|----------|------|----------------|
| Vendor repo `GeekMagicClock/smalltv-ultra` | <https://github.com/GeekMagicClock/smalltv-ultra> | Per-model firmware; the source of the version/downgrade warning. |
| Custom firmware: `bvweerd/geekmagic-tv-esp8266` | <https://github.com/bvweerd/geekmagic-tv-esp8266> | MIT ESP8266 replacement (local, random AP password, mDNS). |
| Custom firmware fork: `aydarik/geekmagic-tv-esp8266` | <https://github.com/aydarik/geekmagic-tv-esp8266> | EU characters, themes, messaging. |
| Home Assistant integration: `adrienbrault/geekmagic-hacs` | <https://github.com/adrienbrault/geekmagic-hacs> | Renders HA dashboards on the clock via Pillow/Blitz. |
| ESPHome (adjacent ESP ecosystem) | <https://esphome.io/> | For replacing the stock firmware with a fully local build. |

---

## Wake a PC from a Bluetooth gamepad

### Prior art

| Source | Link | Notes |
|--------|------|-------|
| PC Wake Dongle (kungaa) | <https://github.com/kungaa/PC-wake-dongle> | The reference implementation: a Pico W / Pico 2 W USB dongle (TinyUSB HID + BTstack LE scan + lwIP) that wakes a PC on a BLE device's advert. Its **"What works / what doesn't"** table is the clearest public statement of the Bluetooth-Classic vs BLE split: Xbox Series pads advertise; DualSense / DualShock 4 / Switch Pro (Classic only) cannot. |
| DS5Dongle (awalol) | <https://github.com/awalol/DS5Dongle> | Origin of the USB remote-wakeup state machine the PC Wake Dongle reuses. |
| ESPHome `bluetooth_proxy` | <https://esphome.io/components/bluetooth_proxy/> | The component that does the listening. |
| Bermuda BLE Trilateration (agittins) | <https://github.com/agittins/bermuda> | Turns proxy-relayed adverts into a `device_tracker`. |
| HA `private_ble_device` | <https://www.home-assistant.io/integrations/private_ble_device/> | Required if the device rotates its address (IRK path). |
| Bluetooth Core Spec, Vol 6 Part B §1.3.2.2 | <https://www.bluetooth.com/specifications/specs/core-specification/> | Defines the `ah` resolving function and the RPA layout used by `verify-irk.py`. |

### Vendor documentation (BIOS standby-USB settings)

| Source | Link | Notes |
|--------|------|-------|
| ASRock FAQ 444 | <https://www.asrock.com/support/faq.asp?id=444> | "USB port power can be turned off by **enabling** Deep Sleep… adjust to *Enabled in S5*." |
| ASRock TSDQA-132 (PDF) | <https://www.asrock.com/support/qa/TSDQA-132.pdf> | The same answer as a technical Q&A sheet. |

> The exact menu path differs per vendor and per board: ASRock uses **Deep Sleep**,
> ASUS/MSI use **ErP Ready**, Gigabyte uses **ErP**. See
> [`pc-wake-by-ble-gamepad/README.md`](pc-wake-by-ble-gamepad/README.md) Step 0.

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
