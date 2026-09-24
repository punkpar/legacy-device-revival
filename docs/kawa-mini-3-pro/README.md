# KAWA MINI 3 Pro dashcam: RTSP and a root shell on a SigmaStar dashcam

The **KAWA MINI 3 Pro** (project `CJ4513`, FCC ID `2AZWZ-MINI3`) is a cheap 2K dashcam
built on a **SigmaStar** SoC running a BusyBox Linux. Out of the box it is app-only: the
vendor app (`com.kawa.auto`) joins the camera's own WiFi access point and previews the
stream. There is no documented local interface.

In practice it exposes **three unauthenticated interfaces** on its access point: an
**RTSP** stream, a **telnet root shell** (empty password) and an **HTTP server that serves
the entire root filesystem**. This page documents all three, plus the hardware map and the
SigmaStar API references that helped crack it.

**Contents:** [1. Hardware](#1-hardware) · [2. Network](#2-network) ·
[3. RTSP stream](#3-rtsp-stream) · [4. Root access](#4-root-access) ·
[5. HTTP filesystem](#5-http-filesystem) · [6. Security](#6-security-findings) ·
[7. API references](#7-sigmastar-api-references)

> ⚠️ **This is an app-only device with no hardening at all.** Do not port-forward it. Put
> it on an isolated network. The interfaces below are for **owners** who want local access
> to hardware they own, and to *close* the holes, not open them.

---

## 1. Hardware

| | |
|---|---|
| Brand / model | KAWA **MINI 3 Pro** Gen 2 (T-Screen), project `CJ4513` |
| FCC ID | `2AZWZ-MINI3` |
| SoC | **SigmaStar** (kernel 4.9.84, BusyBox Linux) |
| Sensor | **GalaxyCore GC2083** MIPI |
| Recording | 2304×1296 (2K) H.265 to microSD |
| RTSP preview | 640×360 H.264 @ 30 fps |
| Display | ST7710S SPI LCD, 160×80 |
| Storage | microSD 16 to 256 GB (Class 10+) |
| Power | 5 V 1.5 A USB-C, **supercapacitor** (no Li-ion) |
| WiFi | 2.4 GHz 802.11 b/g/n, **AP mode only** |
| Firmware | `CJ4513-V4513.241024.01` |
| App | KAWA AUTO (`com.kawa.auto`) |

**Buttons:** power (1 s on, hold 3 s off, click to toggle WiFi), double-click toggles
audio recording, triple-click formats the microSD, 5× click factory-resets.

> ⚠️ **It needs a microSD card to run.** Without one, the `cardv` process crashes during
> audio init and the camera enters a crash loop. Fit a card before doing anything else.

---

## 2. Network

The camera is a **self-contained access point**; it is not on your LAN until you make it
join one (see [§4](#4-root-access) for the STA-mode route).

```
        WiFi AP  SSID: KAWA_MINI3Pro_<suffix>
   camera  <----------------------------->  phone / laptop
  192.168.0.1                                192.168.0.x

  open ports on the camera:
    23  telnet  (root, empty password)
    80  http    (thttpd, serves the whole rootfs)
    554 rtsp    (no auth)
```

| | |
|---|---|
| AP SSID | `KAWA_MINI3Pro_<suffix>` (a per-unit suffix) |
| AP password | `12345678` (factory default, printed on the label) |
| Camera IP | `192.168.0.1` |
| Client IP | `192.168.0.x` (DHCP) |

Connect a spare radio to the AP:

```sh
nmcli device wifi connect 'KAWA_MINI3Pro_<suffix>' password '12345678' ifname wlan0
# then: ip -4 addr show wlan0  ->  192.168.0.x/24
```

---

## 3. RTSP stream

**The URL:**

```
rtsp://192.168.0.1/liveRTSP/av4
```

No authentication. Use TCP transport.

| Property | Value |
|----------|-------|
| Codec | H.264 Main Profile, Level 3.0 |
| Resolution | **640×360** (sub-stream) |
| Frame rate | 30 fps |
| Audio | none |
| RTSP server | **LIVE555** Streaming Media v2016.08.07 |
| SDP title | `ww live test` |

```sh
ffplay -rtsp_transport tcp rtsp://192.168.0.1/liveRTSP/av4
ffmpeg -rtsp_transport tcp -i rtsp://192.168.0.1/liveRTSP/av4 -frames:v 1 snap.jpg
ffmpeg -rtsp_transport tcp -i rtsp://192.168.0.1/liveRTSP/av4 -t 10 -c:v copy clip.mp4
```

**How it was found.** The path came from the SigmaStar SDK convention: both DDPAI and KAWA
share the same SDK, and the DDPAI tooling
([`pwrtux/visiondash`](https://github.com/pwrtux/visiondash)) uses `/liveRTSP/av4`. The
same LIVE555 path naming applies here.

**Paths that do NOT work** (all 404): `/liveRTSP/av0` to `av3`, `av5` to `av8`, `/liveRTSP/v1` to `v4`
(the GoPrawn alternate, absent on KAWA), `/txRTSP/*`, `/live/av4`.

**Why 640×360 and not 2K?** The RTSP stream is the **phone preview**, sized for 2.4 GHz
WiFi. The full 2304×1296 recording goes to the SD card and is not exposed over RTSP. There
is no higher-resolution RTSP path; getting one would mean modifying the `cardv` binary.

---

## 4. Root access

**The root password is empty.**

```
crypt("", "qd") = qdGt8T0XjiWXI      # /etc/passwd
```

BusyBox `telnetd` runs from boot, so:

```sh
telnet 192.168.0.1
# login:    root
# password: (just press Enter)
```

Everything is then readable and writable as root. A scripted login (e.g. `expect`) works
too; note that some terminals and IDEs intercept output containing the literal string
`Password:`, so write the expect script to a file and run it rather than inlining it.

### Making it join your LAN (STA mode)

The camera ships AP-only. To put it on your network you set STA credentials through the
SigmaStar config (see [`settings.txt`](#key-files) and the API references in §7), then
point your NVR/Home Assistant at `rtsp://<camera-ip>/liveRTSP/av4`.

---

## 5. HTTP filesystem

`thttpd/2.29` on port 80 serves the **entire root filesystem without authentication**.
Anything on the AP can read every file.

### Key files

```
/config/settings.txt         camera settings (incl. WiFi credentials, in the clear)
/etc/passwd                  root password hash
/etc/init.d/rcS              boot script
/bootconfig/config.ini       ~28 KB hardware config
/bootconfig/board.ini        board settings
/config/factory.sh           factory test
/lib/libmi_*.so              SigmaStar SDK libraries
/bin, /sbin, /usr/bin        BusyBox utilities
```

### `settings.txt` (structure)

```ini
Resolution=2304x1296
EnCodingType=H265
AudioRec=ON
Camera.WiFi.SSID=<ssid>
Camera.WiFi.PassWD=<psk>          # stored in plaintext
Camera.Menu.sys.info.ver=V4513.241024.01
```

> 🔴 The WiFi PSK is stored in **plaintext** and served over **plain HTTP**. That is the
> clearest reason to keep this camera off any shared network.

### SigmaStar SDK libraries present

```
libmi_sys  libmi_vif  libmi_isp  libmi_vpe  libmi_venc  libmi_ai   libmi_ao
libmi_disp libmi_sensor libmi_panel libmi_gyro libmi_vdisp libmi_gfx libmi_rgn
libmi_iqserver libIPC_msg libmi_common
```

This is the standard SigmaStar "MI" (Media Interface) stack: the same library names appear
across SigmaStar IPC firmware, which is what makes the SDK references in §7 useful.

---

## 6. Security findings

| Severity | Finding |
|----------|---------|
| 🔴 Critical | **Unauthenticated filesystem** over HTTP (entire rootfs) |
| 🔴 Critical | **Empty root password** (trivially crackable DES crypt in `/etc/passwd`) |
| 🔴 Critical | **Telnet on boot** as root |
| 🔴 Critical | No HTTPS anywhere |
| 🟡 Medium | WiFi PSK stored in plaintext and served over HTTP |
| 🟡 Medium | No firewall; every service is reachable on the AP interface |

**Hardening (owner-side):** change the root password and the AP password, disable
`telnetd` in `/etc/init.d/rcS`, and stop `thttpd` if you do not need it. Keep the device
on an isolated VLAN regardless; none of these services should ever be internet-facing.

---

## 7. SigmaStar API references

These are **not** used by KAWA itself (it runs `thttpd` with no CGI handler), but they are
the reference material that identified the SoC and the RTSP path, and they apply to the
wider SigmaStar family.

### GoPrawn SigmaStar CGI API (from a Wayback Machine archive)

```sh
http://<camera>/cgi-bin/Config.cgi?action=get&property=*
http://<camera>/cgi-bin/Config.cgi?action=set&property=Camera.Menu.VideoRes&value=1080P30
```

| Property | Meaning |
|----------|---------|
| `Camera.Menu.VideoRes` | video resolution |
| `Camera.Preview.H264.w/h` | preview stream size |
| `Camera.Preview.H264.bitrate` | preview bitrate |
| `Ass.CSnkNode.2.Name` | RTSP H.264 path (`/liveRTSP/av4`) |
| `Ass.SrcNode.3.Name` | audio source (`AUDIO.0`, EncAAC) |
| `Net.WIFI_STA.AP.1.SSID` | STA SSID |
| `Net.WIFI_STA.AP.1.CryptoKey` | STA PSK |

### DDPAI API command names (from firmware string extraction)

KAWA does **not** implement this API, but the command vocabulary is useful when reversing
other SigmaStar dashcams:

```
API_RequestSessionID  API_GetBaseInfo  API_AuthModify  API_GetStorageInfo
API_MmcFormat  API_SetRouterAuth  API_GetRouterStatus  API_EquipOpenRtsp
API_RecordOpt  API_Reboot  API_RestartWifi  API_SetApMode  API_WpsConnect
APP_PlaybackListReq  APP_PlaybackLiveSwitch  APP_DeleteEvent  APP_StopDownload
```

---

## See also

- [`docs/REFERENCES.md`](../REFERENCES.md): the SigmaStar / GoPrawn / DDPAI sources used.
- [`THIRD-PARTY.md`](../../THIRD-PARTY.md): what is and is not redistributed.
- [`docs/LEGAL.md`](../LEGAL.md): why publishing this is lawful.
