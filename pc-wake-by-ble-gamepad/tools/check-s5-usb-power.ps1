# check-s5-usb-power.ps1 - decide whether a USB port stays powered when the PC is off
#
# WHY THIS EXISTS
# ---------------
# The whole "wake the PC with a BLE gamepad" trick depends on ONE thing: a USB port
# that keeps supplying 5 V when the machine is in S5 (soft off). That is a BIOS
# setting, and the setting NAMES are inconsistent across vendors:
#
#   ASRock : Advanced -> ACPI Configuration -> "Deep Sleep"
#              [Disabled] / [Enabled in S5] / [Enabled in S4 & S5]
#              Enabling it TURNS USB POWER OFF in S5.
#   ASRock : some boards also have "USB Power Delivery in Soft Off State (S5)"
#              Enabling it KEEPS USB powered.
#   ASUS   : Advanced -> APM Configuration -> "ErP Ready"
#   MSI    : Settings -> Advanced -> Power Management -> "ErP Ready"
#   Gigabyte: Settings -> Platform Power -> "ErP"
#
# "ErP", "Deep Sleep" and "EuP" are energy regulations requiring near-zero standby
# draw -- enabling them removes USB power. The safe answer is DISABLE them.
#
# 🔴 THE ONLY TEST THAT MATTERS is empirical: shut the machine down and see whether
#    the USB device still answers. This script gathers what Windows can tell you
#    beforehand, to point you at the right BIOS page.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File check-s5-usb-power.ps1
#   powershell -ExecutionPolicy Bypass -File check-s5-usb-power.ps1 -ListSerial

param([switch]$ListSerial)

$ErrorActionPreference = 'Continue'

Write-Output "=============================================================="
Write-Output "  S5 USB power / wake diagnostic"
Write-Output "=============================================================="
Write-Output ""

# --- 1. Which sleep states does the FIRMWARE offer? --------------------------
Write-Output "--- 1. Available sleep states (powercfg /a) ---"
powercfg /a
Write-Output ""
Write-Output "  Reading: you want 'Standby (S3)' present. S5 is not listed -- it is the"
Write-Output "  plain 'shut down' state. If Hibernate is missing, that is a firmware"
Write-Output "  limitation and does not affect this scheme."
Write-Output ""

# --- 2. Which devices are armed to wake the system? --------------------------
Write-Output "--- 2. Devices currently ARMED to wake the system ---"
powercfg /devicequery wake_armed
Write-Output ""

# --- 3. Which devices COULD be armed? ----------------------------------------
Write-Output "--- 3. Devices that COULD be armed (wake_programmable) ---"
powercfg /devicequery wake_programmable
Write-Output ""
Write-Output "  Note: a Bluetooth radio here is useful for S3 wakes but is NOT needed for"
Write-Output "  this scheme -- the proxy does the listening, and the NIC sends the wake."
Write-Output "  What you DO need is the Ethernet NIC in the 'wake_armed' list above."
Write-Output ""

# --- 4. USB serial bridges = likely BLE-proxy candidates ---------------------
Write-Output "--- 4. USB serial bridges (a BLE proxy shows up here) ---"
$bridges = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
    Where-Object { $_.InstanceId -match 'VID_10C4&PID_EA60|VID_1A86&PID_7523|VID_303A' }

if (-not $bridges) {
    Write-Output "  (none found -- no ESP32 / serial bridge is currently plugged in)"
}
else {
    foreach ($b in $bridges) {
        Write-Output ("  " + $b.FriendlyName + "   [" + $b.InstanceId + "]")
        if ($ListSerial) {
            $props = Get-PnpDeviceProperty -InstanceId $b.InstanceId -ErrorAction SilentlyContinue
            foreach ($k in @('DEVPKEY_Device_LocationInfo', 'DEVPKEY_Device_Parent')) {
                $p = $props | Where-Object { $_.KeyName -eq $k }
                if ($p) { Write-Output ("      " + ($k -replace 'DEVPKEY_Device_', '') + " = " + $p.Data) }
            }
        }
    }
}
Write-Output ""
Write-Output "  A CP2102 (10C4:EA60) or CH340 (1A86:7523) bridge is an ESP32. Note the"
Write-Output "  LocationInfo / Parent -- that identifies WHICH physical port it is on."
Write-Output ""

# --- 5. The empirical test ---------------------------------------------------
Write-Output "=============================================================="
Write-Output "  THE ONLY TEST THAT MATTERS"
Write-Output "=============================================================="
Write-Output ""
Write-Output "  Windows cannot tell you whether a port stays powered in S5. Measure it:"
Write-Output ""
Write-Output "    1. Note your proxy's IP address."
Write-Output "    2. Shut this machine down FULLY  (not sleep -- S5, 'power off')."
Write-Output "    3. From ANOTHER machine on the network:"
Write-Output ""
Write-Output "         ping -c 3 <PROXY_IP>"
Write-Output "         timeout 3 bash -c \"echo > /dev/tcp/<PROXY_IP>/6053\" && echo ALIVE"
Write-Output ""
Write-Output "    4. Answers while the PC is off  -> the port is live. Proceed."
Write-Output "       Dead                          -> change the BIOS setting (section above)"
Write-Output "                                        or use a wall charger instead."
Write-Output ""
Write-Output "  A LIT MOUSE PROVES NOTHING. Many boards feed standby 5 V to USB *and*"
Write-Output "  light peripheral LEDs. Only a network response from the proxy counts."
Write-Output ""
Write-Output "  DONE."
