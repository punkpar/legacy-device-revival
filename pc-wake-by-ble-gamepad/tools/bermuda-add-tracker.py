#!/usr/bin/env python3
"""Add a device to Bermuda BLE Trilateration's tracked list (OptionsFlow only).

WHY THIS EXISTS
---------------
Bermuda has NO websocket API for this. `bermuda/get_devices` does not exist. The
only supported route is Home Assistant's config-entry **OptionsFlow**, which is
normally driven from the UI. This script drives it from the command line.

It also exists to document two things that are easy to get wrong:
  1. The schema nests its options under `data_schema[0].selector.select.options`
     -- NOT a top-level `options` key. A naive reader finds an empty list.
  2. `configured_devices` is the FULL list every time. It REPLACES; it does not
     append. Send the existing devices plus the new one, or you will drop them.

USAGE
-----
    export HA_URL=http://homeassistant.local:8123
    export HA_TOKEN=<long-lived access token>
    export BERMUDA_ENTRY=<config entry id>          # Settings -> the entry's URL

    ./bermuda-add-tracker.py list                   # show what is tracked
    ./bermuda-add-tracker.py find aa:bb:cc          # search available devices
    ./bermuda-add-tracker.py add AA:BB:CC:DD:EE:FF  # add one (UPPERCASE)

Requires only the Python standard library.

FINDING THE ENTRY ID
--------------------
Developer Tools -> Actions -> bermuda.dump_devices -> the response includes the
entry, or read Settings -> Devices & Services -> Bermuda and take the id from the
URL. The script will also auto-detect it if BERMUDA_ENTRY is unset and exactly one
bermuda entry exists.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE = (os.environ.get("HA_URL") or "").rstrip("/")
TOKEN = os.environ.get("HA_TOKEN") or ""
ENTRY = os.environ.get("BERMUDA_ENTRY") or ""


def api(path: str, method: str = "GET", body: dict | None = None) -> dict:
    if not BASE or not TOKEN:
        sys.exit("set $HA_URL and $HA_TOKEN")
    req = urllib.request.Request(
        BASE + "/api" + path,
        data=json.dumps(body or {}).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode()[:600]}


def find_entry() -> str:
    """Locate the Bermuda config entry id."""
    if ENTRY:
        return ENTRY
    data = api("/config/config_entries/entry")
    if isinstance(data, dict):
        sys.exit(f"could not list entries: {data}")
    ids = [e["entry_id"] for e in data if e.get("domain") == "bermuda"]
    if len(ids) == 1:
        return ids[0]
    if not ids:
        sys.exit("no bermuda config entry found -- is the integration installed?")
    sys.exit(f"multiple bermuda entries {ids}; set $BERMUDA_ENTRY")


def open_selectdevices(entry: str) -> tuple[str, dict]:
    """Start an options flow and advance to the device-selection step."""
    start = api("/config/config_entries/options/flow", "POST", {"handler": entry})
    flow = start.get("flow_id")
    if not flow:
        sys.exit(f"could not start flow: {start}")
    return flow, api(f"/config/config_entries/options/flow/{flow}", "POST", {"next_step_id": "selectdevices"})


def read_schema(step: dict) -> tuple[list[str], list[str]]:
    """Extract (available, currently_configured) from the step, handling the
    nested selector shape."""
    for field in step.get("data_schema") or []:
        if field.get("name") != "configured_devices":
            continue
        # The options live here -- NOT at field["options"].
        nested = (field.get("selector") or {}).get("select") or {}
        options = nested.get("options") or field.get("options") or []
        available = [o["value"] if isinstance(o, dict) else o for o in options]
        configured = [o["value"] if isinstance(o, dict) else o for o in (field.get("default") or [])]
        return available, configured
    return [], []


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["list", "find", "add"])
    p.add_argument("value", nargs="?", help="MAC fragment (find) or MAC (add)")
    args = p.parse_args()

    entry = find_entry()
    flow, step = open_selectdevices(entry)
    available, configured = read_schema(step)

    if args.command == "list":
        print(f"available: {len(available)}   tracked: {len(configured)}")
        for mac in configured:
            print(f"  tracked  {mac}")
        return

    if args.command == "find":
        needle = (args.value or "").upper()
        matches = [m for m in available if needle in m.upper()]
        print(f"matches for '{needle}': {len(matches)}")
        for mac in matches:
            suffix = "  (already tracked)" if mac in configured else ""
            print(f"  {mac}{suffix}")
        return

    # add
    mac = (args.value or "").upper()
    if not mac:
        sys.exit("add requires a MAC address")
    if mac not in available:
        sys.exit(
            f"{mac} is not in Bermuda's device list -- the proxies have not relayed it.\n"
            "Put the device in range / pairing mode first."
        )
    if mac in configured:
        print(f"already tracked: {mac}")
        return

    new = configured + [mac]
    print(f"setting configured_devices: {len(configured)} -> {len(new)}")
    result = api(f"/config/config_entries/options/flow/{flow}", "POST", {"configured_devices": new})
    if result.get("_error"):
        sys.exit(f"failed: {result}")
    print("saved. Bermuda reloads; its counters read 0 for 1-2 minutes while it rebuilds.")


if __name__ == "__main__":
    main()
