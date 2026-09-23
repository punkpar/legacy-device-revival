# Anyka AK3918 → Home Assistant

Once RTSP is up ([README](README.md)), integrating is straightforward. The extra work is
wiring **PTZ, IR and motion** into HA via the keyed CGI wrapper.

---

## 1. Camera

Use the **Generic Camera** integration (or go2rtc — both work for plain RTSP):

| Field | Value |
|-------|-------|
| Stream Source | `rtsp://<camera>:554/vs1` (sub) or `/vs0` (main) |
| Still Image URL | `http://<camera>:3000/snapshot` (if your build serves one) |
| RTSP transport | `tcp` |

## 2. PTZ / IR via `rest_command`

Add the commands from [`ha/rest_command.yaml`](../../anyka-ak3918/ha/rest_command.yaml)
to `/config/rest_command.yaml`. Each sends the shared key via the **`X-Ptz-Key` header**
(so it never lands in a URL/log):

```yaml
rest_command:
  anyka_ptz:
    url: "http://<camera>/cgi-bin/ptz?cmd={{ cmd }}"
    headers:
      X-Ptz-Key: !secret anyka_ptz_key
```

Then a script or button can call `rest_command.anyka_ptz` with `{"cmd": "left"}`.

If you must use the query param instead, that also works (`?cmd=left&key=...`) — but the
header is preferable.

## 3. Switches (real state, not optimistic)

`command_line` switches let HA read the **actual** state back:

```yaml
command_line:
  - switch:
      name: Anyka Motion Recording
      command_on: "curl -s -H 'X-Ptz-Key: !secret anyka_ptz_key' 'http://<camera>/cgi-bin/ptz?cmd=motion_on'"
      command_off: "curl -s -H 'X-Ptz-Key: !secret anyka_ptz_key' 'http://<camera>/cgi-bin/ptz?cmd=motion_off'"
      command_state: "curl -s -H 'X-Ptz-Key: !secret anyka_ptz_key' 'http://<camera>/cgi-bin/ptz?cmd=motion'"
      value_template: "{{ 'on' in value }}"
```

See [`ha/command_line.yaml`](../../anyka-ak3918/ha/command_line.yaml) for the full set
(motion recording + night vision).

> ⚠️ **`switch.anyka_night_vision` polarity was not visually confirmed when written** (built
> at night). Verify in daylight that "on" really means day/colour.

## 4. Secrets

Add to `/config/secrets.yaml`:

```yaml
anyka_ptz_key: "<the key from the camera's /etc/jffs2/ptz.key>"
```

Never commit the key. [`ha/secrets.append.yaml.example`](../../anyka-ak3918/ha/secrets.append.yaml.example)
shows the shape with a placeholder.

---

## Entities you end up with

| Entity | Notes |
|--------|-------|
| `switch.anyka_motion_recording` | real state via `command_state` |
| `switch.anyka_night_vision` | ⚠️ verify polarity in daylight |
| `rest_command.anyka_ptz` | `{"cmd": "<direction>"}` |
| `rest_command.anyka_ptz_init` | home the axes |
| `rest_command.anyka_ir_on` / `_off` | colour / night |
| `rest_command.anyka_motion_on` / `_off` | enable / disable motion recording |
