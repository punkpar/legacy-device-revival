# Time2 MIP12 → Home Assistant

Because the camera has **no RTSP**, you cannot point Home Assistant's generic camera
straight at it. The trick is to run a tiny **bridge** that speaks HeKai and re-serves the
video as ordinary **HTTP MJPEG**, then let **go2rtc** turn that into RTSP/H.264 for HA.

```text
camera  --HeKai UDP :2627/:5000-->  bridge  --HTTP MJPEG-->  go2rtc  --RTSP H.264-->  HA
```

## 1. The bridge

A minimal Python bridge (see `../../time2-mip12/`) performs the handshake, receives MJPEG
and serves:

| Endpoint | Purpose |
|----------|---------|
| `/stream` | continuous MJPEG (`multipart/x-mixed-replace`) |
| `/frame.jpg` | single JPEG snapshot |
| `/health` | JSON — `{"ok": bool, "frame_age_s": float}` |

Two non-obvious requirements:

- **`local_port=0`** — the client must bind an ephemeral UDP port, *not* `:5000`
  ([PROTOCOL.md §4](PROTOCOL.md)).
- **`network_mode: host`** — UDP broadcast discovery on `:2627` cannot cross a Docker
  bridge network, so the container must share the host's network namespace.

## 2. go2rtc

Add the bridge as a source. 🔴 **`#video=h264` is mandatory** — MJPEG does not survive
RTSP, and HA's live view needs H.264:

```yaml
streams:
  time2:
    - ffmpeg:http://<bridge-host>:8099/stream#video=h264
```

Then in Home Assistant use the **Generic Camera** integration:

| Field | Value |
|-------|-------|
| Stream Source | `rtsp://<go2rtc-host>:8554/time2` |
| Still Image URL | `http://<go2rtc-host>:1984/api/frame.jpeg?src=time2` |
| RTSP transport | `tcp` |
| Verify SSL | off |

## 3. Gotchas that cost real time

- **`#video=h264`** — omit it and you get
  `codecs not matched: video:JPEG => video:H264`.
- **Docker `COPY` preserves file ownership/permissions.** If your bridge runs as a
  non-root user and your source files are `640 root:root`, the container crash-loops with
  `[Errno 13] Permission denied`. Use `COPY --chown=<user>:<user>`. Do **not** use
  `--chmod=644` — that also strips the execute bit from any *directory* it copies, breaking
  traversal.
- **The camera is single-client.** Only one session at a time. Stop the bridge before
  running your own probes, or they'll fight over the camera.
- **HA Generic Camera title** auto-derives from the URL host and can collide with another
  camera entry; rename it via the config-entry API if needed.
