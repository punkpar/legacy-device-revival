# Anyka AK3918 PTZ camera — "white V380 clone"

Notes and hardened artifacts for a cheap **Anyka AK3918**-based PTZ IP camera (the white
dome, sold under many names — it looks and behaves like a "V380 clone"). Stock, it is
**cloud-only**: no RTSP, no ONVIF, closed app.

This page documents how it was unlocked, what runs afterwards, and how the stock firmware's
**pre-auth root RCE** was closed.

**Contents:** [1. Hardware](#1-hardware) · [2. The SD-card hack](#2-the-sd-card-factory-hack) ·
[3. What runs now](#3-what-runs-now) · [4. Control](#4-ptz--ir--motion-control) ·
[5. Hardening](HARDENING.md) · [6. Home Assistant](HOME-ASSISTANT.md)

---

## 1. Hardware

| | |
|---|---|
| SoC | **Anyka AK3918** |
| Sensor | `gc1084` (`isp_gc1084.conf`) |
| WiFi | **SSV6006C** (`ssv6x5x.ko`) — station mode |
| Stock firmware | cloud-only, Yi IoT stack |
| Stock AP fallback | SSID `CAM_<serial>` / password `12345678` |

Both the sensor and the WiFi chip are on the community *supported* list, which matters for
[the hack](#2-the-sd-card-factory-hack) — see the warning there.

## 2. The SD-card `Factory` exploit

The camera's own boot scripts will run a script from **its SD card** if the card carries a
`Factory/` directory. This is the well-known **VGerris Anyka** technique
([VGerris/Anyka_ak3918_hacking_journey](https://github.com/VGerris/Anyka_ak3918_hacking_journey)).

The elegant part: **nothing is written to the camera's flash**. Pull the card and it boots
stock again. `rootfs_modified` stays `0`.

After the hack the camera runs a community userspace app, **`libre_anyka_app`**, which
provides proper **RTSP** — which the stock firmware never had.

> 🔴 **Do NOT flash the upstream prebuilt images blindly.** The community images are built
> for specific sensor/WiFi pairings. If yours differs (e.g. `gc1084` + `ssv6x5x`), the
> prebuilt image **will not work** and may leave the camera unbootable until you re-card it.
> Match your hardware first.

## 3. What runs now

| Component | Role |
|-----------|------|
| `libre_anyka_app` | the RTSP server (replaces the stock cloud app) |
| `ptz_daemon` (+ `/tmp/ptz.daemon` FIFO) | pan/tilt motor control |
| busybox `httpd` | tiny web UI |
| `app_restarter.sh` | supervisor — restarts the app if it dies |

### Streams

| Purpose | URL | Format |
|---------|-----|--------|
| Main | `rtsp://<camera>:554/vs0` | 1280×720 H.264 |
| Sub | `rtsp://<camera>:554/vs1` | 640×360 H.264 |
| Audio | (muxed) | PCM A-law 8000 Hz mono |

### Audit the ports you expose

After the hack, check what's listening and turn off what you don't need. The stock payload
ships wide open (see [HARDENING.md](HARDENING.md)). A hardened camera should expose only:

| Port | Service |
|------|---------|
| 80 | web UI |
| 554 | RTSP |
| 3000 | snapshot |

FTP (21) and telnet (23) should be **off**.

## 4. PTZ / IR / motion control

The PTZ daemon reads simple text commands from a FIFO:

```sh
echo right > /tmp/ptz.daemon
```

Commands: `init up down left right left_up right_up left_down right_down`
plus IR (`init_ir`, `set_ir_cut 1` = colour/day, `set_ir_cut 0` = night) and motion.

Because the daemon has no auth, the web UI exposes a **keyed CGI wrapper**
(`cgi-bin/ptz`, see [`cgi-bin/`](../../anyka-ak3918/cgi-bin/)) that:
- requires a shared key (query param `key=` **or** the `X-Ptz-Key` header),
- **whitelists** the command — no arbitrary input reaches the shell.

🔴 **The shared key must live outside any repo.** On the camera it's a file
(`/etc/jffs2/ptz.key`); in Home Assistant it's `!secret`. See
[`ha/secrets.append.yaml.example`](../../anyka-ak3918/ha/secrets.append.yaml.example).

> ⚠️ **Motion on/off restarts the app** (it's a startup flag), so RTSP drops for a few
> seconds when you toggle it.

## 5. Busybox quirks worth knowing

This busybox is minimal:

- **No `tr`, no `cut`, no `base64`** available to CGI scripts. Use `sed`, `grep`, `cat` and
  shell built-ins only.
- **`webui.hash` must include the `md5sum` `  -` suffix.** Generate with
  `echo "$salt$pw" | md5sum > webui.hash`. Using `printf` drops the suffix and login can
  never succeed.
- **Both `gergesettings.txt` copies must be edited.** There is an SD copy and a live copy;
  they are diffed at boot and, if different, the SD copy wins **and the camera reboots**.
- **FTP cannot read block devices** (`550` on `/dev/mtdblock4`). Dump to `/mnt/` first if
  you must.

## 6. Warning

- **RTSP is unauthenticated and cannot be password-protected.** `libre_anyka_app` has no
  auth option. **LAN only — never port-forward.**
- **The microphone is always on** and there is no mute in the app.
- The stock firmware had a **pre-auth root RCE**; if you did not patch it, anyone on your
  LAN has root. See [HARDENING.md](HARDENING.md).
