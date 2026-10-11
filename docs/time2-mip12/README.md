# Time2 MIP12: HeKai/HK camera, fully local

This camera has no RTSP, no ONVIF, no HTTP, no open TCP ports. Just a proprietary UDP protocol. Oh honey, that sounded like a dead end. It wasn't.

Four pages, read them in order:

| Page | What it gives you |
|------|-------------------|
| [`PROTOCOL.md`](PROTOCOL.md) | The wire protocol: discovery on UDP `:2627`, MJPEG video on UDP `:5000`, handshake, encoding (`0xE9` XOR), and the `local_port=0` fix |
| [`WIFI.md`](WIFI.md) | Cable-free provisioning: `SetLanWifi` (`MainCmd=700`) as a broadcast to `255.255.255.255:2627`, raw bencode, password XOR `0x3C`, `MacIP` is the wired MAC |
| [`EMULATOR.md`](EMULATOR.md) | How the WiFi command was captured: x86_64 emulator + ARM translation + TAP bridge + `strace` on the vendor app |
| [`HOME-ASSISTANT.md`](HOME-ASSISTANT.md) | Bridge HeKai → HTTP MJPEG → go2rtc → HA Generic Camera |

Tools in [`../../time2-mip12/`](../../time2-mip12/): `p2pcam/` client plus `wifi_setup.py`, `probe_config.py`, `wifi_sweep.py`, `wifi_brute.py`. Nothing needs a vendor account.

> Same camera, different name? Also sold as *Plug2View* / *P2PcamViewer* (Android `x.p2p.cam`). If yours speaks HeKai/HK, this applies.
