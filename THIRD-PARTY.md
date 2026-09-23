# Third-party components

All **original** work in this repository is MIT-licensed (see [`LICENSE`](LICENSE)).
This file records the third-party and vendor material that this repo builds on, so the
provenance is clear.

---

## Vendored code

### `time2-mip12/p2pcam/`

A Python implementation of the HeKai/HK ("P2P") LAN protocol, vendored with a small
protocol patch for the Time2 MIP12.

- **Upstream**: `indykoning/PyPI_p2pcam`
- **Licence**: **MIT** — Copyright (c) 2019 Indy Koning
- **Patch**: commit adding packet-length handling for the Time2 MIP12, plus a fork PR
  (`devmlb` #3). The `local_port=0` fix (see `docs/time2-mip12/PROTOCOL.md`) is applied
  on top.

Retain the upstream MIT notice when redistributing.

---

## Vendor material referenced (NOT redistributed)

The vendor SDKs, apps and firmware discussed in the docs are **the vendor's copyright**.
They are analysed but **not** included in this repository. Where a filename or symbol is
quoted, it is for interoperability research only.

| Artifact | Owner | Included? |
|----------|-------|-----------|
| `x.p2p.cam` (P2PcamViewer app) | Time2 / HeKai SDK vendor | ❌ not included |
| `libcaptetown1.so`, `libchinalink.so`, `libsystem.so` | HeKai SDK vendor | ❌ not included |
| `hkipc.h`, `HKCameraControl.h` (SDK headers) | HeKai SDK vendor | ❌ not included |
| Anyka stock firmware / `anyka_ipc` binaries | Anyka | ❌ not included |
| VGerris `Anyka_ak3918_hacking_journey` SD-card payload | VGerris (community) | ❌ not included — see upstream |

The Anyka SD-card exploit itself is **community work by VGerris**
(`github.com/VGerris/Anyka_ak3918_hacking_journey`). This repo documents *how to use it
and harden the result*; get the payload from upstream.

---

## If you believe something here is misattributed

Open an issue and it'll be fixed or removed.
