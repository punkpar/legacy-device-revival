# Hardening the Anyka AK3918 camera

The stock firmware and the common community SD payload both ship **wide open**. This page
documents the holes and how they were closed.

> If you run this camera and have **not** applied these patches, assume anyone on your LAN
> has root on it. Don't port-forward it.

---

## 1. The pre-auth root RCE (critical)

The stock web UI's `cgi-bin/header` contained:

```sh
for i in $QUERY_STRING; do eval $i; done
```

`eval` on unescaped query input = **command execution as root, with no login**, e.g.:

```sh
curl 'http://<camera>/cgi-bin/webui?x=;telnetd;'
```

### The fix

Replace `eval` with an explicit **whitelist** and `export` (which assigns `name=value`
*without* evaluating the value). Only known setting names are accepted; anything else is
dropped. See [`cgi-bin/header`](../../anyka-ak3918/cgi-bin/header).

### Regression test (must keep passing)

```sh
curl -s "http://<camera>/cgi-bin/webui?x=;touch%20/tmp/PWNED;"
# then on the camera:
ls /tmp/PWNED      # must be ABSENT
```

---

## 2. Root FTP + root Telnet

The stock/community payload enables **root FTP** and **root telnet**, blank/lazy passwords.
Turn them off.

In `gergesettings.txt` (both copies):

```text
run_ftp=0
run_telnet=0
```

---

## 3. Settings are silently wiped by unsubmitted checkboxes

The stock `settings_submit.sh` wrote each parameter only when it appeared in the query
string. **Unchecked checkboxes are omitted by browsers**, so saving any settings page
reset `run_ftp`/`run_telnet` (the security settings) to empty, i.e. **re-enabled them**.

### The fix

An omitted parameter now **keeps its existing value** instead of being blanked. See
[`cgi-bin/settings_submit.sh`](../../anyka-ak3918/cgi-bin/settings_submit.sh).

---

## 4. The PTZ daemon is unauthenticated

`/tmp/ptz.daemon` accepts plain text from anyone who can write to it. The web UI therefore
exposes a **keyed, whitelisted** CGI wrapper ([`cgi-bin/ptz`](../../anyka-ak3918/cgi-bin/ptz)):

- requires a shared key (query `key=` or `X-Ptz-Key` header),
- **whitelists** the command; anything else → `bad command`,
- uses only shell built-ins + `sed`/`grep`/`cat` (no `tr`/`cut`/`base64` in this busybox).

The key itself is a file on the camera (`/etc/jffs2/ptz.key`) and a Home Assistant
`!secret`. **It is never committed.**

---

## 5. Things that cannot be fixed

| Issue | Why |
|-------|-----|
| **RTSP has no authentication** | `libre_anyka_app` has no auth option. |
| **Microphone always on** | no mute/volume code; only standalone demo tools exist and they don't integrate. |
| **Telnet password unknown (stock)** | the stock shell password is custom and unpublished. |

**Mitigation: VLAN-isolate the camera. Never expose it to the internet.**

---

## Checklist

- [ ] `eval` replaced with a whitelist in `cgi-bin/header`
- [ ] RCE regression test passes (no `/tmp/PWNED`)
- [ ] `run_ftp=0` and `run_telnet=0` in **both** `gergesettings.txt` copies
- [ ] web UI password set
- [ ] PTZ keyed wrapper in place; key not in any repo
- [ ] camera on an isolated VLAN
- [ ] no port-forward / tunnel route to it
