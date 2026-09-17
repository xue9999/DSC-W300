# W300 workbench handoff — revision 3, Windows x64

Transfer the verified identification environment. In the revision-3 ZIP, `RESEARCH_PLAN.md` is the packaged research guide; for continued work use the current [repository execution plan](https://github.com/xue9999/DSC-W300/blob/main/docs/w300/EXECUTION_PLAN.md). The executable implements `selftest`, `inventory` and bounded `inquiry`; preserve the separate hardware and language-verification flags in its reports.

## Transfer

Copy `build/w300/portable/release3/W300-Workbench-Windows-x64.zip` and its `.zip.sha256` file, or obtain the same assets from the matching GitHub Release. The ZIP contains the full `W300Workbench` directory: executable, private Python and native libraries, Microsoft PowerShell 7.4.18, pinned PMCA source, licenses and revised instructions. Keep this directory intact. It runs independently of installed Python, Git, Codex or PowerShell 7 and uses the built-in Windows PnP module and Microsoft mass-storage driver.

The locally built EXE is unsigned; the included Microsoft `pwsh.exe` has a verified Microsoft signature. Diagnose OS execution-policy messages from their exact text while preserving system protections.

## Receiving-PC commands

1. Compare `Get-FileHash .\W300-Workbench-Windows-x64.zip -Algorithm SHA256` with the supplied checksum. Extract the entire ZIP into a writable directory.
2. In PowerShell in the extracted `W300Workbench` directory, run:

```powershell
.\W300Workbench.exe selftest
```

Expected: `ok: true`, `frozen_portable_executable: true`, passing source/runtime checks and a JSON report under `reports/`. `camera_communication_tested` and `w300_language_function_verified` remain false until their separate device tests.

3. When the camera is available, use a charged battery and direct USB connection in Mass Storage mode. Keep Microsoft USBSTOR and disconnect other Sony USB devices. Run:

```powershell
.\W300Workbench.exe inventory
```

Expected: Sony PnP records, current VID/PID, serial, model and driver. An empty list records empty OS enumeration. This step sends no application camera command.

4. Review identity. The current profile requires exactly one Sony `054C:0341`, model `DSC-W300`, status `OK`, and its current serial. Investigate mismatches. Then run:

```powershell
.\W300Workbench.exe inquiry --serial '<CURRENT_USB_SERIAL>'
```

The helper performs two bounded standard SCSI INQUIRY reads and records transactions. Resolve access-denied errors using an elevated terminal if required. A generic SCSI product `DSC` can be normal; selection uses current USB/PnP identity. Service entry, settings and calibration are outside these commands.

5. Retain all JSON reports. Use the current repository execution plan to continue qualified read/backup/restore and language-operation work. The ZIP's `RESEARCH_PLAN.md` records the revision-3 handoff; current research can advance independently of that historical package.

## Reproduction and validation

To build a later edition, use `build/w300/build_portable.py --output build/w300/portable/release-next` in the restored development environment. The builder accepts a new directory and preserves earlier outputs. `build/w300/validate_portable.py` validates archive hashes, relocates into a path containing spaces and Polish characters, and runs selftest and OS inventory with external Python/Git/pwsh removed from PATH. Revision-3 results are in `build/w300/reports/portable-validation-r3.json`; the prior release-2 record remains historical.

The relocation check measures packaging on the preparation Windows 11 host. Record the receiving PC's own reports for its OS and camera session. Release 3 updates instructions while retaining bounded identification behavior.

## Continue between device sessions

An empty inventory is an observation about this computer. Save its report and continue package/firmware acquisition, static protocol analysis and offline tooling. When a receiving PC has the camera, resume at current identity verification. An access or identity error pauses the affected identification command while its exact cause is investigated; it does not prevent independent research.

This revision-4 repository guidance leaves the published revision-3 ZIP and its checksums intact. No new portable build is required for the documentation update.
