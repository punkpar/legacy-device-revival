# Time2 MIP12 — HeKai/HK P2P protocol

A reverse-engineered reference for the **Time2 MIP12** (and, by extension, other cameras
in the HeKai/HK "captetown" family) that expose **no RTSP, no ONVIF, no HTTP and no open
TCP ports**. The only local interface is a proprietary UDP protocol.

> **Provenance:** everything below was derived from (a) official HeKai Android/iOS SDKs
> mirrored on GitHub, (b) static analysis of the *shipping* vendor app's native libraries,
> and (c) live packet capture against the camera. Where a claim is unverified it says so.

**Contents**

- [1. Device fingerprint](#1-device-fingerprint)
- [2. The vendor app](#2-the-vendor-app)
- [3. Discovery (`:2627`)](#3-discovery-2627)
- [4. Video session (`:5000`)](#4-video-session-5000)
- [5. The config channel](#5-the-config-channel) — **the interesting part**
- [6. WiFi setup](WIFI.md)
- [7. Home Assistant integration](HOME-ASSISTANT.md)

---

## 1. Device fingerprint

The MIP12 is a 2016-era P2P camera. As observed on the wire:

| Property | Value (example — your camera will differ) |
|----------|-------------------------------------------|
| Discovery port | UDP `2627` |
| Video port | UDP `5000` |
| Protocol family | HeKai/HK (a.k.a. "captetown" from the vendor lib name) |
| Device ID | a short alphanumeric string, e.g. `<DEVICE-ID>` |
| HKID | a 4-digit numeric id, e.g. `5000` |
| Camera MAC | vendor OUI **Deutschmann Automation** (`00:14:11`) |
| Open TCP ports | **telnet (23) only** — no web, no RTSP |
| Native lib | `libcaptetown1.so` (Android, `armeabi`) |

**There is no RTSP.** This is proven by binary audit: zero RTSP/ONVIF protocol strings
across the camera's binaries. Any guide claiming you can enable RTSP by flipping a config
flag is wrong — the server simply isn't in the firmware.

---

## 2. The vendor app

The official **phone** guide names it directly:

> "Download the **P2PcamViewer APP** from the Apple Appstore or the Google Playstore."

| | |
|---|---|
| Package | `x.p2p.cam` |
| Label | "Plug&Play" |
| Version studied | 8.19.05.22 (built 2019-05-22) |
| Size | ~6.1 MB |
| Native libs | `lib/armeabi/libcaptetown1.so`, `libchinalink.so`, `libsystem.so`, `libSCCodec.so`, `libvoiceRecog.so` |
| ABI | **`armeabi` (32-bit) only** — will **not** install on arm64-only phones |
| minSdk / targetSdk | 7 / 19 |

`libcaptetown1.so` **is** the protocol library — it is the same family as the public SDK
headers (`hkipc.h`, `HKCameraControl.h`) and is the single most useful artifact for
understanding the protocol. Its JNI entry points (`Java_x1_Studio_Core_OnlineService_*`)
map directly onto SDK function names.

> ⚠️ **Separate the protocols.** Time2 sold cameras across *two* protocol generations.
> The **bundled Windows client** ("Time2 Surveillance Pro") is **PPPP**, not HeKai — it
> links `PPPP_API.dll` / `IPCClientNetLib.dll` and contains **zero** HeKai tokens. If you
> try to talk to a HeKai camera with the PPPP client you will get nothing, forever.
> Identifying which protocol your camera speaks is step one.

The `armeabi`-only restriction is the main practical obstacle: modern phones can't run the
app, so you cannot capture its traffic without an old 32-bit ARM device.

---

## 3. Discovery (`:2627`)

The client broadcasts a UDP discovery datagram and listens for replies.

```text
00 00 <len_lo> <len_hi>
<command<<4 | 0x02> 0C 1D <inner_len_lo> <inner_len_hi> 00 00 00 00
TIME=3600;endTime=<unix+3600>;MainCmd=LocalData;userType=hkclient;status=1;Prot=<port>;MacIP=<marker>;
```

It is sent to `255.255.255.255` **and** each interface broadcast address.

Replies come in two shapes:

1. **Framed replies** starting `00 00` with the length in the shifted outer-length field.
2. **Inner discovery packets** where `data[0] >> 4 == COMMAND_LAN_REFRESH`, dictionary body
   from byte 9.

Fields are aliased: `HKID` / `hkid` / `DevID` / `DSTHKID` are all the device id; `Prot` /
`UDPPort` / `Port` are all the port. The scanner ignores its own echo by matching the
`MacIP` marker it generated.

There is also a 13-byte **ack** form:

```text
00 00 d0 00 <cmd_lo> <flag> 20 09 00 <pipe_lo> <pipe_hi> 00 00
```

See [`p2pcam/lan_scanner.py`](../../time2-mip12/p2pcam/lan_scanner.py) for a working
implementation of discovery.

---

## 4. Video session (`:5000`)

Video is MJPEG inside UDP. Every framed packet:

```text
[0-1]   packet counter (uint16 LE)
[2-3]   outer length = total_packet_len << 4
[4]     inner_cmd
[5]     inner_flag1
[6]     inner_flag2
[7-8]   inner payload length
[9-12]  inner_extra (4 bytes)
[13+]   payload body
```

### Handshake sequence

1. Send **Ping 1** ×3, wait for the ack.
2. Send **Ping 2** ×9.
3. Send **`HK_RES_REQ`** (request the video session).
4. Poll with **`ICMD2`** until the camera answers **`SessionCreate`**.
5. Send **`SessionStart`**.
6. Receive MJPEG fragments; ACK camera `ICMD1` polls; send a *continue* packet every 5
   fragments.
7. Stop with **`SessionDelete`**.

### Exact packet bodies

```text
Ping 1:  00 00 d0 00 82 0c 00 09 00 d1 07 00 00
Ping 2:  00 00 d0 00 a2 0c 40 09 00 d1 07 00 00

HK_RES_REQ:
id=<hkid>;ftN0=video.vbVideo.MPEG4;ftN1=net.0;ftN2=HKPCPresent.HKPCPresent;
opN2=<sid>;Callid=<callid>;sidN=<sid>;AsCode=337;MainCmd=HK_RES_REQ;user=Lan user;

ICMD2 poll:    d4:ICMD2:293:SEQ1:<hkid>:GUARDSEQ1:<seq>

SessionStart:  MainCmd=SessionStart;sidN=<sid>;ftN0=HKPCPresent.HKPCPresent;
               FD0=4;ftN1=net.1024;FD1=1024;

ICMD1 ACK:     d4:ICMD1:293:lastreq1:<hkid>:SEQ3:<seq>e

SessionDelete: sidN=<sid>;MainCmd=SessionDelete;coz=;
```

### Encoding — 🔴 the critical detail

- **Dictionary-style** bodies: keep the **first 2 bytes** plain ASCII, **XOR the rest with
  `0xE9`**.
- **`ICMD`-style** bodies: **XOR every byte** with `0xE9`.

MJPEG frames arrive as fragments where `data[4:]` is the payload; `FF D8` starts a frame,
`FF D9` ends it. The client must answer camera `ICMD1` polls and send continue packets, or
the stream stalls.

### 🔴 `local_port=0` is mandatory

A naive client binds its local UDP socket to `:5000` to match the camera. This **collides
with the camera's own session** — the *first* connection works and every later one stalls
forever at the ping stage. **Bind to an ephemeral port instead (`local_port=0`).**

---

## 5. The config channel

This is the part that is least documented publicly, and the most useful. It comes in **two
distinct shapes**, and conflating them was the source of a long-standing bug.

| Shape | Used by | Destination | Body encoding |
|-------|---------|-------------|---------------|
| **Broadcast write** | `SetLanWifi` (`700`) | `255.255.255.255:2627` | plain bencode, **no XOR**; 13-byte header with cmd id in byte[9] |
| **Dict-style read** | `204`, `703` | the camera (post-handshake) | bencode, first 2 bytes plain, rest XOR `0xE9` |

### 🔴 `SetLanWifi` is a **broadcast on `:2627`**

For a long time this project believed *all* config rode the video socket (`:5000`) with a
fixed envelope. **That was wrong.** The decisive capture:

```
sendto(71, "\0\0p\n2I\35\243\0d\0\0\0d7:MainCmd3:7006:isopen1:15:MacIP…", 167,
       MSG_NOSIGNAL,
       {sin_port=htons(2627), sin_addr=inet_addr("255.255.255.255")})
```

Destination **`255.255.255.255:2627`** — the discovery port. Layout is a simple **13-byte
header** (`00 00 70 0a 32 49 1d a3 00 64 00 00 00`, byte[9] = `0x64` = cmd id `100`) followed
by the bencode body. See [WIFI.md](WIFI.md) for the full frame.

### The dict-style read (`204` / `703`)

These ride the **video socket** after the handshake and are encoded like the rest of the
dictionary protocol: **bencode with the first 2 bytes plain and the remainder XOR `0xE9`**.

```python
# e.g. "d7:MainCmd3:2042:id4:5000e" -> first 2 bytes plain, rest ^ 0xE9
def ben(d):
    out = b"d"
    for k, v in d.items():
        kb = str(k).encode()
        vb = (b"i%de" % v) if isinstance(v, int) else str(v).encode()
        out += b"%d:%s" % (len(kb), kb) + b"%d:%s" % (len(vb), vb)
    return out + b"e"
```

### Command IDs

| `MainCmd` | Meaning |
|-----------|---------|
| `700` | **SetLanWifi** — set WiFi credentials (broadcast write) |
| `703` | `DoLanGetWifiSid` — scan neighbouring SSIDs |
| `204` | read device / WiFi info (`HK_CMD_WIFI_IP_INTO`) |

`700` was confirmed from `libcaptetown1.so` JNI `SetLanWifi` (`@0xb8dd`): the code loads the
**strings** `"MainCmd"` and `"700"` and calls `DictSetStr`. (`0x2BC` == 700.) Note the value
is a *string*, not an immediate — a plain `movw`/`.rodata` literal scan will not find it,
which is why it was long thought "unverified".

### The `204` read — worked example

Sending `d7:MainCmd3:2042:id4:5000e` (dict-style encode) makes the camera return a
bencoded dict:

```python
{'id': '...', 'ver': '6', 'Sensitivity': '0', 'Reselution': '0', 'rate': '15',
 'hue': '30', 'brightness': '22', 'saturation': '18', 'contrast': '30',
 'frequency': '50', 'qualite': '2', 'Flag': '2', 'irate': '0', 'bitrate': '5',
 'highorlow': '0', 'ioin': '0', 'cbrorvbr': '0', 'ControlPT': '10',
 'audioAlarm': '1', 'ThermalAlarm': '0', 'channel': '1',
 'event': 'eventInbandDesc', 'MainCmd': '17', 'subResource': 'video.vbVideo.MPEG4'}
```

That's the **video parameter** read. The reply is intermittent — the camera only answers
when it isn't mid-JPEG-frame, so retry.

### The `700` (WiFi) dict keys

Recovered from the JNI by walking every `ldr rX, [pc, #imm]` + its following
`add rX, pc` (the strings are PIC-relative and invisible to naive scanning). The **values
actually observed on the wire** are in the right-hand column — where they differ from the
JNI defaults, the capture wins.

| Key | Set as | Notes / observed value |
|-----|--------|------------------------|
| `MainCmd` | Str | `"700"` |
| `isopen` | Str (observed) | `"1"` enable / `"0"` AP-mode — JNI builds it as an Int, the app sends a string |
| `wifisid` | Str | SSID |
| `wifipassword` | Str | PSK — **XOR `0x3C` over the whole string** |
| `MacIP` | Str | **the camera's *wired* MAC** — see below |
| `safetype` | Str | `auto` observed (`WPA2PSK` / `WPAPSK` / `WEP` / `none` also seen in the JNI) |
| `encrytype` | Str | `auto` observed (`AES` / `auto` in the JNI) |
| `safeoption` | Str | WEP option (empty otherwise) |
| `bootproto` | Str | `dhcp` / `static` |
| `Ip` | Str | static IP |
| `netmask` | Str | |
| `netwet` | Str | gateway |
| `dns0`, `dns1` | Str | DNS |

🔴 **`MacIP` is the *wired* (Ethernet) MAC, not the WiFi MAC.** The earlier note on this
page said the opposite, and it was wrong. Confirmed by capture: the value sent matches the
camera's Ethernet MAC — the one visible via `arp` while the camera is still cabled.

Note the **native** names differ from the app's Java-side names (`mac`, `ip`, `dns`,
`option`): the app's Java layer passes its own names into the JNI, and the **native layer
remaps them**. The dict that actually goes on the wire uses the names above.

### ✅ Resolution

The camera did **not** process `MainCmd=700` on `:5000` — the command is a **broadcast on
`:2627`**. Once that was corrected the write was accepted and the camera joined WiFi.
Full details in **[WIFI.md](WIFI.md)**.

---

## Tools

`../../time2-mip12/` contains:

| File | Purpose |
|------|---------|
| `p2pcam/` | Vendored, MIT-licensed HeKai/HK client (discovery, handshake, MJPEG). **Includes the `local_port=0` fix.** |
| `tools/probe_config.py` | Send an arbitrary bencoded `MainCmd` (dict-style read) and print the reply. |
| `tools/wifi_setup.py` | **The solved `SetLanWifi` broadcast** — builds and sends the 167-byte frame. |
| `tools/wifi_sweep.py` | Sweep envelopes / probe `703` SSID scans. |
| `tools/wifi_brute.py` | Sweep `InnerCmd`/command-id variants when probing. |

## Attribution

- Protocol insight builds on [`indykoning/PyPI_p2pcam`](https://github.com/indykoning/PyPI_p2pcam)
  (MIT) and the `devmlb` fork/PR.
- SDK headers were studied from [`jameshilliard/HKiPhoneSDKDemo20160621`](https://github.com/jameshilliard/HKiPhoneSDKDemo20160621)
  and [`jameshilliard/android-p2p-sdk3.0`](https://github.com/jameshilliard/android-p2p-sdk3.0).
