# GeekMagic SmallTV-Ultra: an open weather clock with a documented HTTP API

The **GeekMagic SmallTV-Ultra** is a cheap 240×240 desk weather clock built on an
**ESP8266**. Stock, it is configured entirely through a Chinese phone app and phones home
to OpenWeather and the GeekMagic cloud. But it also runs a **small HTTP server** whose own
JavaScript spells out **every endpoint**: so it can be provisioned and driven entirely
locally, with no app and no cloud account.

**Contents:** [1. Hardware](#1-hardware) · [2. Provisioning without the app](#2-provisioning-without-the-app) ·
[3. HTTP API](#3-http-api) · [4. Firmware](#4-firmware) · [5. Security](#5-security) ·
[6. Home Assistant](#6-home-assistant-integration) · [7. Lessons](#7-lessons)

> ⚠️ **`/set` and `/wifisave` are unauthenticated.** Anyone who can reach the device can
> reconfigure it (or factory-reset it). Keep it on an isolated network. The
> [custom firmware](#5-custom-firmware-researched-not-flashed) fixes the open-AP exposure
> if you need it.

---

## 1. Hardware

| | |
|---|---|
| Model | SmallTV-**Ultra** |
| MCU | **ESP8266** (not ESP32) |
| Display | 240×240 |
| Storage | ~3 MB total, ~1.2 MB free |
| Open ports | **tcp/80 only** (no telnet/FTP/SSH) |
| Firmware | `Ultra-V9.0.51` |
| Vendor repo | [`GeekMagicClock/smalltv-ultra`](https://github.com/GeekMagicClock/smalltv-ultra) |

> 🔴 **Model matters.** The vendor ships separate firmware per model and warns that
> flashing the wrong one **bricks** the display. The **Ultra** is the plain ESP8266 unit;
> the **Pro** is the ESP32 model with a touch sensor. Confirm your model before flashing
> anything.

---

## 2. Provisioning without the app

On first boot (or after a reset) the device broadcasts an **open AP called `GIFTV`** and
runs a small HTTP config server on that AP's gateway address. Its JavaScript exposes the
endpoints, so no app is required.

```sh
# 1. Join the open AP (no PSK) from a machine with a spare radio
nmcli dev wifi connect GIFTV

# 2. Hand it your real network (SSID + PSK). Use the gateway address the AP hands out.
curl "http://<ap-gateway>/wifisave?s=MyNetwork&p=<PSK>"      # -> OK

# 3. The device reboots; GIFTV disappears. Find it on the LAN by its station MAC
arp-scan --localnet | grep -i <oui>
```

> ⚠️ The AP's gateway address may collide with the default gateway on your own home
> network. While attached to `GIFTV`, HTTP to that address is ambiguous; bind probes to
> the WiFi interface, or wait and use the device's station IP.

### 🔑 The AP-BSSID to station-MAC trick

The AP BSSID has the **locally-administered bit set** (the second-least-significant bit of
the first octet). Clear that bit to get the **station MAC** the device uses on your LAN:

```
AP BSSID:      aa:bb:cc:dd:ee:ad      (locally-administered bit SET)
station MAC:   aa:bb:cc:dd:ee:ad  ->  clear 0x02  ->  a8:bb:cc:dd:ee:ad
```

Use the station MAC to identify the device on the LAN instead of sweeping blindly, and to
set a DHCP reservation.

> The AP only stays up for a short window after power-on (the vendor changelog notes the
> `GIFTV` AP "starts for 1 minute after power on; if no clients connect it will be
> closed"). Be ready to join it quickly, or trigger a reset to bring it back.

---

## 3. HTTP API

All plain `GET` unless noted. The device's own web console at `http://<device-ip>/`
redirects to `/settings.html`, and its `js/*.js` files document the rest.

### Readers

| Endpoint | Returns |
|----------|---------|
| `/v.json` | model + firmware, e.g. `{"m":"SmallTV-Ultra","v":"Ultra-V9.0.51"}` |
| `/config.json` | SSID + masked PSK |
| `/city.json` | `{"ct","t","mt","cd","loc"}`; `t` = UTC offset **in hours** |
| `/tz.json` | `{"tz_auto":1,"tz_off":480}` (`tz_off` in minutes) |
| `/unit.json` | `{"w_u","t_u","p_u"}` |
| `/space.json` | `{"total":…,"free":…}` bytes |
| `/filelist?dir=/image` | HTML table of files (⚠️ repeats each row 3×) |
| `/wifi.json` | WiFi scan list |

### Setters: `GET /set?...`

| Param | Meaning |
|-------|---------|
| `cd1=<city\|id>&cd2=1000` | **location** (the important one) |
| `w_u=`, `t_u=`, `p_u=` | wind / temperature / pressure units |
| `w_i=` | weather refresh (minutes) |
| `tz_auto=<0\|1>&tz_offset=<min>` | timezone mode |
| `brt=`, `theme=`, `gif=`, `img=`, `hour=`, `colon=`, `font=` | appearance |
| `fkey=` / `key=` | your own OpenWeather API key |
| `reboot=1` | reboot |
| 🔴 `reset=1` | **FACTORY RESET. Never call it by accident.** |

Uploads: **`POST /doUpload?dir=/image/`** (multipart). Responses are `OK` on success,
`FAIL` on a bad/unknown key.

> ⚠️ Note the asymmetry: the **setter** uses `cd1`/`cd2`, while the **reader**
> `city.json` uses `cd`. Easy to get wrong.

### Example: set location and UK units

```sh
curl "http://<device-ip>/set?cd1=<City>&cd2=1000"          # -> loc "<City>,GB"
curl "http://<device-ip>/set?w_u=mile/h&t_u=%C2%B0C&p_u=hPa"
```

Leave `tz_auto=1`: the UTC offset is derived from the city, so **DST is handled
automatically** (verified by the firmware changelog below).

### Features that do NOT exist on this build

`stock.html`, `daytimer.html`, `bili.html` and `monitor.html` all **404**. No stocks, no
crypto, no Bilibili, no PC-monitor page. Do not promise them.

---

## 4. Firmware

### ⚠️ The device can be AHEAD of the vendor

```
device        : Ultra-V9.0.51
vendor latest : Ultra-V9.0.50    (published folder list)
```

**There was nothing newer to install; "updating" would have been a downgrade.** Relevant
changelog:

```
V9.0.50  1) manual/auto timezone option.  2) fix DST time-sync problem.
V9.0.48  1) weather-payload time-sync fallback (NTP blocked -> use OWM dt).
V9.0.22  AP GIFTV starts for 1 minute after power on; closed if no clients connect.
```

> ✅ **Always diff the device's reported version against the vendor's published folders
> before "updating".** Vendor repos routinely lag the factory build.

Update mechanism: **`POST /update`** with a `.bin`, **same family only**. Check the md5;
the vendor warns that antivirus can corrupt `firmware.bin`.

---

## 5. Security

| Severity | Finding |
|----------|---------|
| 🟡 Medium | **Unauthenticated `/set` and `/wifisave`**: anyone on the network can reconfigure or factory-reset the device. |
| 🟡 Medium | **Open AP (`GIFTV`)** on first boot: anyone nearby can provision it. |
| 🟡 Medium | **Cloud dependency**: phones home to OpenWeather and the GeekMagic cloud; closed-source firmware. |

Not internet-facing by default, but treat it as an untrusted IoT device: isolate it, and do
not expose port 80 through any tunnel.

### Custom firmware (researched, NOT flashed)

Two MIT-licensed ESP8266 projects target the **Ultra**:

| | repo | notes |
|---|------|-------|
| original | [`bvweerd/geekmagic-tv-esp8266`](https://github.com/bvweerd/geekmagic-tv-esp8266) | v2.2.4 |
| fork | [`aydarik/geekmagic-tv-esp8266`](https://github.com/aydarik/geekmagic-tv-esp8266) | adds EU characters, themes, messaging, countdown |

**Gain:** fully local (no GeekMagic cloud, no vendor OWM key), **random AP password**
(closes the open-`GIFTV` exposure), mDNS (no DHCP reservation needed), live `POST
/api/update`.

**Lose:** the **stock weather app**: the custom firmware shows a simplified clock unless
Home Assistant feeds it.

🔴 **The first flash MUST be UART.** OTA from stock does not work (both projects say so).
That means opening the case and a **3.3 V (never 5 V)** TTL adapter on TX/RX/GND. The
`bvweerd` project ships a UART pinout image.

---

## 6. Home Assistant integration

**[`adrienbrault/geekmagic-hacs`](https://github.com/adrienbrault/geekmagic-hacs)** renders
dashboards *inside* HA with Pillow/Blitz (no browser, no external service) and pushes them
to the device. Its docs list the **SmallTV-Ultra (stock firmware)** as fully supported.

- Install: copy `custom_components/geekmagic` into your HA config and restart core. Its
  dependencies (`pillow`, `palettable`, `blitz-py`) install automatically.
- The integration exposes entities such as `sensor.<clock>_status`,
  `image.<clock>_display_preview`, `number.<clock>_brightness`,
  `select.<clock>_display`, `switch.<clock>_view_cycling` and
  `button.<clock>_refresh_display`.

### 🔴 Configuration is WebSocket-only

The options flow exposes only `reset_defaults`. Widget/screen configuration lives on
**WebSocket** commands:

```
geekmagic/views/list | /get | /create | /update | /delete | /duplicate
geekmagic/devices/list | /assign_views | /settings
geekmagic/preview/render | geekmagic/entities/list
```

Widget schema is `{"type","slot","entity_id"}`; a `grid_2x2` layout uses slots 0 to 3. Drive
these with a WebSocket client against `ws://<ha-host>:8123/api/websocket`, authenticating
with a long-lived token.

> 🔴 **`<clock>_display` is the MANUAL selection, not the cycled view.** It stays on one
> name while cycling happens. To verify cycling, read `current_view_index` from
> `geekmagic/devices/list` and watch it flap on the cycle interval.

### 🔴 The panel is ground truth, not the preview entity

`image.<clock>_display_preview` can go **stale** (its state froze at one timestamp while
the device cycled fine minutes later). Verify against the device:

```sh
curl -s http://<device-ip>/image/dashboard.jpg -o /tmp/dash.jpg   # live panel content
curl -s http://<device-ip>/filelist?dir=/image/                   # files + sizes
```

`/image/dashboard.jpg` **is** the live panel. Its `Content-Length`/md5 alternate as slides
rotate; that is the ground-truth cycling signal. (`/image/dashboard.jpeg` 404s.)

> ⚠️ **Do not identify a slide by its file size.** Sizes change with every redesign; a
> slide that was the smaller JPEG can become the larger one. Identify by **content** (OCR
> a word, or a distinctive colour region) or by the alternation, never a remembered byte
> count.

### 🔴 The cycling period is quantised by the refresh interval

The cycle check lives inside the coordinator's update loop and only runs **on a refresh**.
So the real period is the **first refresh at or after** the configured interval: a 15 s
`cycle_interval` with a 10 s `refresh_interval` measured ~30 s, not 15 s. Sample at ≤1 s
resolution or you will under-report it.

---

## 7. Lessons

- **The device documents itself.** The web console's own JavaScript was the complete API
  reference. Before reverse-engineering, read what the device already serves.
- **The AP BSSID leaks the station MAC** (clear the locally-administered bit). A neat,
  reusable trick for any ESP-based device that comes up as a soft-AP.
- **Check the version before you "update".** Factory firmware is often newer than the
  vendor's published folders; flashing the "latest" can be a downgrade or a brick.
- **Verify against the hardware.** Preview entities and cached images go stale; the
  device's own `/image/dashboard.jpg` is the truth.

---

## See also

- [`docs/REFERENCES.md`](../REFERENCES.md): the vendor repo, the custom-firmware forks and
  the HA integration.
- [`docs/LEGAL.md`](../LEGAL.md): why publishing this is lawful.
