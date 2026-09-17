# DSC-W300 execution plan — research handoff revision 3

Prepare persistent English menus on the original Japanese DSC-W300 while preserving identity, calibration and normal operation. The supplied W300Workbench implements `selftest`, OS `inventory` and bounded standard `inquiry`. Continue from these verified foundations to qualify the model-specific language operation. Camera communication and language qualification remain recorded as `false` until measured on the target device.

## Selected engineering direction

Use Sony-PMCA-RE commit `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0` as the transport reference. Retained G3 code matches its 12-byte Senser framing and SHA1 authentication branch for service PID `0x0336`. Sony's separate W300 and G3 GPL packages establish a common CXD4108/ARMv5 platform with different kernel revisions. Confirm W300 service identity, authentication, segmented address encoding and persistence against W300 code or documented transactions before adding camera operations.

Follow a new concrete package locator for `DSC-W300 Auto-Adj Ver_1.3r04.exe`, compatible SeusEX and its HASP requirements. Acquisition reports identify inspected catalogs, downloaded contents and follow-up targets. Inspect actual binaries and dependencies before choosing the operating system or a VM. Use G3 Hreg, AV and XS findings to frame precise W300 comparisons.

The [resumption assessment](../../build/w300/reports/w300-resumption-20260917.md) confirms that the named historical catalog/archive routes have already been inspected without obtaining the missing W300 payload. A fresh implementation artifact or trustworthy W300 trace is needed to advance qualification. On acquisition, start with the documented Destination Check read handler before the original-board gate, language fields and persistence path.

An alternative to external package acquisition is now grounded in retained G3 code: [Senser FileControl command 2 reads a named regular file](../../build/w300/reports/g3-file-read/README.md). After separately qualifying W300 service entry, exit and bounded transfer behavior, this may provide the W300 proprietary libraries directly. Use the reviewed regular-file bootstrap, not procfs; do not assume G3 paths or commands work on W300. This route remains offline research and is not implemented in the portable workbench.

The analyst owns package acquisition, protocol qualification and implementation. Continue these offline tasks without connecting a camera to the preparation computer. The later camera session uses a separate Windows 10/11 x64 computer.

## Local tools and environment

Repository: `C:\Users\apara01\OneDrive - Kearney\Documents\ChatGPT\W300\DSC-W300`.

- Portable revision 3: `build/w300/portable/release3/W300-Workbench-Windows-x64.zip`, also supplied as a GitHub Release asset. It includes Python/libraries and Microsoft PowerShell 7.4.18.
- Development entry point: `build/w300/w300_workbench.py`; wrapper: `build/w300/run.ps1`.
- Build source: `build/w300/build_portable.py`; locked dependencies and wheels are covered by the research asset.
- Offline launch check: `build/w300/pmca_offline.py` initializes the local USB runtime and displays the actual pinned PMCA program's help.
- Restore research inputs using [RELEASE_RESTORE.md](RELEASE_RESTORE.md). Transfer the portable ZIP according to [PORTABLE_HANDOFF.md](PORTABLE_HANDOFF.md).

## First session with the camera

1. Extract the whole portable ZIP into a writable directory. In PowerShell, from `W300Workbench`, run:

```powershell
.\W300Workbench.exe selftest
```

Expected: `ok: true`, `frozen_portable_executable: true`, verified dependencies and source hashes. The flags `camera_communication_tested` and `w300_language_function_verified` describe separate hardware milestones and remain false in this offline check.

2. For identification, use a charged battery, connect the original W300 directly by USB, turn it on and select Mass Storage mode. Disconnect other Sony USB devices. Keep Microsoft's USBSTOR driver. Decline Windows formatting or initialization prompts. Run:

```powershell
.\W300Workbench.exe inventory
```

Expected: PnP description, current instance ID/serial, VID/PID, driver details and saved JSON. `sony_devices: []` records an empty enumeration. Inventory reads OS properties without an application camera command.

3. Review the report. The current profile requires exactly one Sony device, VID `054C`, PID `0341`, status `OK`, model `DSC-W300`, and its current serial. The PID is based on historical W300 observations; investigate any mismatch before proceeding.

4. After matching the current identity, run:

```powershell
.\W300Workbench.exe inquiry --serial '<CURRENT_USB_SERIAL>'
```

The helper sends SCSI INQUIRY (`0x12`): a five-byte header read followed by a bounded identification read through one volume handle. Windows pass-through requires read/write handle access; both commands request input data. Diagnose access-denied reports and use an elevated terminal if needed for this operation.

Expected: manufacturer `Sony`, actual product/revision, command and response bytes, and report path. The SCSI product may be `DSC`; exact model selection comes from current USB/PnP data. The helper retains transaction details and performs no automatic retries or vendor commands.

5. Preserve the reports and compare actual responses with the profile. The following engineering stage adds qualified service reads, baseline settings and affected-data backup. Identification reads identity only; language, destination and calibration need their own model-qualified reads.

## Qualification for the separately authorized write stage

Complete each item with W300-specific evidence and record exact bytes, expected responses and recovery:

| Work item | Evidence and verification |
|---|---|
| Original-board eligibility | Resolve Auto-Adj's `Service board` condition in code or documented W300 behavior. Retain the original board and identity. |
| Language-only operation | Identify the field and allowed values, then qualify the narrowest update. Use destination conversion only if necessary and record its effects. |
| Baseline and recovery | Read current settings and preserve every affected region. Verify backup coverage and restoration, including identity/calibration preservation, before the write trial. |
| Service session | Establish entry, read, response-validation and exit; identify volatile versus persistent effects. |
| Persistence | Establish the exact commit/save operation and post-restart readback. Distinguish RAM update, EEPROM Write and flash Save. |
| Environment and power | Inspect program, driver architecture/signature and HASP dependencies. The documented adjustment setup uses AC-LS5 with the appropriate DC-input multi-use cable. |

Sony's adjustment manual, PDF p.11, restricts Destination Data Write to Service boards. PDF p.36 describes adjustment backups; establish destination coverage separately. `SERIAL` and `ADJBAK` protect different data. `WriteEnableTool.exe` concerns user image-storage access. Keep calibration, identity, initialization and cross-model firmware outside the language task.

U2 starts in English/NTSC; CEE8 starts in English/PAL. Derive bytes and side effects from the implementation. Auto-Adj's destination-completion OK dialog resets the camera and belongs to the later write stage. Comparative G3 erase/flush code and contemporary Sony service-board behavior guide inspection; confirm equivalent operations on W300.

After the separately authorized qualified write, verify settings readback, unchanged identity/calibration, English menus after power-off/restart, and normal shooting/playback. Record each result independently.

See [VERIFICATION.md](VERIFICATION.md) for measured results and acquisition routes. The [qualification worklist](../../build/w300/reports/w300-readiness-audit/README.md) turns those findings into the next engineering steps.
