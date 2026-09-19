# W300 handoff to the receiving-PC agent

Continue the owner's goal: enable English menus on the original Japanese Sony DSC-W300, verify persistence after restart and normal operation, and preserve identity/calibration. The owner has authorized the region write and GitHub publication. This Windows PC has administrator rights and USB access; verify the current connection before acting.

## Get the app and current code

- Repository: https://github.com/xue9999/DSC-W300 — use current main and read AGENTS.md.
- Portable app: https://github.com/xue9999/DSC-W300/releases/tag/w300-region-handoff-r4
- Download W300Region-Windows-x64.zip and its SHA-256 sidecar; verify with Get-FileHash, then extract the entire ZIP to a writable folder.
- Expected ZIP SHA-256: `466f65eb424da8fbc5800c5c4d0b63968b8f5e8c8252b851c98cb25e6c4a75fb`.
- Read the included README.md for USB drivers, service-mode transition and resuming a failed acquisition. Normal PID 054C:0341 and service candidate 054C:0336 need separate usable bindings. Record the original USBSTOR binding. Do not select unrelated devices.

## First camera session

Use stable power, direct USB, Mass Storage mode, and only one connected Sony device. Previously observed identity: DSC-W300, serial D386002E4438; verify it live. From the extracted W300Region folder, run sequentially and stop on failure:

```powershell
.\W300Region.exe selftest
.\W300Region.exe doctor
.\W300Region.exe probe --serial D386002E4438 --experimental-service
.\W300Region.exe capture --serial D386002E4438 --experimental-service
```

Probe/capture enter experimental service mode but do not send RegionSetting. Preserve each complete sessions directory and raw transactions, including failures. If service mode needs a driver, follow README resume instructions; do not keep restarting the sequence blindly. Capture includes the original Hreg pair, region XML, UserInfo pair and implementation files, including optional /usr/bin/sen.

## Continue toward the actual change

Assess the completed capture with `W300Region.exe assess --baseline '<capture directory>'`. The current write path requires exact coherent reviewed component matches. Its complete reference is G3; T100 has comparative coverage. Actual W300 compatibility is NOT established. If comparison fails, analyze the captured W300 code against retained source anchors; do not bypass checks by editing hashes or approval flags.

Once the actual implementation and recovery constraints are resolved, `change --serial D386002E4438 --experimental-service --baseline '<capture directory>'` performs a real native write. The intended setting is English initially, English/Japanese available, original video standard retained. It resets user preferences. Save the baseline, result and write-intent records. Never automatically retry an uncertain write. The explicit restore-region command reapplies original regional values; it is not full preference rollback or proven hardware recovery.

After normal restart, run verify-region against the original baseline, visually confirm English menus, and test shooting/playback. Record identity, calibration-preservation evidence and each hardware result separately. Do not declare success from a command reply or synthetic tests. Push completed, verified work to main as requested by the owner.

## Evidence and current validation

- [Persistent English Conversion Guide](PERSISTENT_ENGLISH_GUIDE.md)
- [App source and operating guide](../../build/w300/reports/region-app/README.md)
- [Active execution plan](EXECUTION_PLAN.md)
- [Hardware verification record](VERIFICATION.md)
- [Native restoration constraints](../../build/w300/reports/region-app/recovery-layout.md)
- [T100 standalone service transport](../../build/w300/reports/region-app/t100-transport.md)
- [Historical research-input restoration](RELEASE_RESTORE.md) — portable capture does not require these inputs. The newer T100 source can be acquired using the pinned extract_t100.py --acquire helper if further analysis requires it.

On 2026-09-19 / 2026-09-20, the receiving-PC session successfully executed the full capture and region change on the live DSC-W300 (serial `D386002E4438`). Senser `status = 0x01` success was confirmed, the camera automatically switched from PID `054C:0341` to `054C:033F`, and persistent English menus were physically verified on the LCD after cold power-cycle restart. Optical zoom, autofocus, flash, image/video capture, and playback operate normally with hardware serial and optical/sensor calibration preserved.
