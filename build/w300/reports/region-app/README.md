# W300 Region Console v2 — automatic comparison and native writes

This Windows x64 application implements an automatic capture/compare/change/readback
workflow and an explicit native regional-settings restoration command. It no longer
requires hand-editing qualification booleans for that workflow.

**W300 hardware success is still unverified.** The app writes only when the acquired
implementation is an exact match to one coherent reviewed reference family and the
original files pass integrity checks. Unknown code stops before the write. The
currently complete reference family is G3; T100 supplies additional comparison
inputs but lacks a separately reviewed libsencore transport component. We do not
know whether the W300 files will meet this deliberately conservative test. A
rejection can mean compatible but different firmware; it requires analysis, not
changing a JSON approval flag. The program is not a guaranteed W300 converter.

The requested outcome is English initially, English and Japanese available, and
the observed original video standard retained. RegionSetting also resets user
preferences. It does not intentionally change serial identity or calibration.
Whole-camera preservation still needs hardware verification.

## Start on the receiving Windows PC

Extract the whole ZIP into a writable folder and keep all contents together.
Python, Git and Codex are not needed. START.cmd runs selftest and displays help;
it does not communicate with the camera. In PowerShell inside the folder:

```powershell
.\W300Region.exe selftest
.\W300Region.exe doctor
```

Doctor inspects descriptors; descriptor access does not prove that bulk transfers
work. Commands save a new directory under sessions with JSON results and a raw
transactions.jsonl. Keep complete directories, including failed sessions.

Use stable power, a direct USB connection and Mass Storage mode. Disconnect other
Sony USB devices. Your previously observed W300 serial is D386002E4438. The app
requires the exact live DSC-W300 product string and serial before normal-mode
entry and again after exit. Host bus/port coordinates are captured fresh.

The receiving PC must permit the required USB access. A portable EXE cannot bypass
Windows device permissions. For driver setup use the official
[libusb Windows guide](https://github.com/libusb/libusb/wiki/Windows) and
[Zadig](https://zadig.akeo.ie/). Driver installation requires administrator rights.
Current libusb guidance prefers WinUSB for compatible devices; the older pinned
PMCA code recommended libusb-win32. Neither binding has yet been validated with
this W300 by this app. Normal device 054C:0341 and service candidate 054C:0336 have
separate bindings. Select only the camera, never a USB hub or another peripheral,
and record the original USBSTOR binding for restoration afterward. The app does
not install drivers, request elevation or disable device-control software.

## First test and driver transition

```powershell
.\W300Region.exe probe --serial D386002E4438 --experimental-service
```

This attempts the candidate two-stage service authentication, reads /version.txt
twice, attempts service exit and verifies the original normal-mode identity. It
sends no regional-setting command. Service mode itself can have incidental state
or logging effects; the trial is explicitly experimental.

If Windows exposes service PID 0336 without a usable driver, install its binding.
If the camera remains in service mode, keep the same PC, camera and physical port,
then resume using the failed acquisition result:

```powershell
.\W300Region.exe probe --serial D386002E4438 --experimental-service --resume-session '.\sessions\<FAILED-PROBE>\result.json'
```

Resume accepts only a previous probe/capture with recorded W300 identity and
unresolved exit, and correlates exactly one Sony 0336 device on the recorded port.
It is not supported for a write operation. Do not reuse a resume record after
moving the device or changing PCs. Exit failure remains explicit; unplugging or
rebooting is not described as a proven repair of service state.

## Automatic region-change command

After reviewing a successful probe and setting up both driver bindings:

```powershell
.\W300Region.exe change --serial D386002E4438 --experimental-service
```

This command will send a real RegionSetting write if its automatic checks pass.
It performs these stages:

1. Capture /version.txt, both Hreg files, RegionInfo.xml, UserInfo.xml, UserInfo.bak,
   and the reviewed runtime/native/script paths. Read each file twice and hash it.
2. Return to normal mode and save a complete original baseline under the change
   session's baseline directory. A failed capture prevents further work.
3. Compare complete sizes and SHA-256 hashes of all required implementation files
   against one coherent reference family. Matching names or an early bytecode
   prefix never grants compatibility. Require complete original backups, valid
   0xAAAAAAAA completion markers, equal 2048-byte Hreg banks, consistent Japanese
   regional configuration and the original signal type.
4. Enter a fresh service session, re-read the implementation and all five original
   configuration files, and reject any drift before writing.
5. Flush the local write-intent journal and send exactly one native RegionSetting
   request with [255, 0x100, 0x8100, original_signal]. Never retry that write.
6. Poll readback for up to 30 seconds. Require expected fields, completion markers,
   no unrelated Hreg changes, and English/English+Japanese XML. Preserve final
   repeat-equal readbacks, attempt exit and verify the original normal identity.

If code differs, compatibility.json names every missing or different component.
No write is sent in that case. Return the complete capture for inspection; do not
edit the bundled reference hashes to force a match. The check is conservative and
can reject firmware that later analysis may establish as compatible.

To acquire or inspect separately, or reuse an unchanged successful capture:

```powershell
.\W300Region.exe capture --serial D386002E4438 --experimental-service
.\W300Region.exe assess --baseline '.\sessions\<CAPTURE>'
.\W300Region.exe change --serial D386002E4438 --experimental-service --baseline '.\sessions\<CAPTURE>'
```

If automatic capture fails during the service-driver transition, its resumable
result is sessions/<CHANGE>/baseline/result.json. Use capture with --resume-session
to produce a fresh complete capture, then pass that directory as --baseline.
A FileControl status 0x82 means missing OR inaccessible; the app does not pretend
that missing required files have been backed up. Alternative paths need evidence.

## Restart verification

After successful save readback, perform the reviewed normal shutdown/restart and
run the following against the ORIGINAL baseline:

```powershell
.\W300Region.exe verify-region --serial D386002E4438 --experimental-service --baseline '.\sessions\<CHANGE>\baseline' --expect english
```

This checks current implementation, both Hreg banks and regional XML without a
region write. The app cannot observe a human power cycle or the camera's visible
menu. Its persistent_english_verified flag therefore remains false. Record the
actual restart, English menus, Japanese availability and shooting/playback test
separately. Immediate reply/readback is not a durable-success claim.

## Restore original regional settings

A separate explicit command reissues the four original values through the native
RegionSetting handler. It never blindly overwrites Hreg or UserInfo files:

```powershell
.\W300Region.exe restore-region --serial D386002E4438 --experimental-service --baseline '.\sessions\<CHANGE>\baseline' --change-session '.\sessions\<CHANGE>\result.json'
```

The referenced change may have succeeded or have an uncertain outcome, but must
match this serial and original baseline. Restoration checks the same actual
implementation, rejects unrelated Hreg changes, sends one native request, and
verifies both banks and original regional XML values. It restores regional
settings only. User preferences reset by RegionSetting are NOT reconstructed;
preferences_restored remains false. Hardware recovery has not been demonstrated.

If the process or PC stopped before result.json was written, pass the change
session's write-intent.json instead. The app writes and fsyncs this record before
the USB request. Its presence means that transmission may have occurred, not that
the camera accepted or saved the change; restoration still checks current state.

An interrupted primary-bank save with a non-original spare is explicitly refused:
the native writer's invalid-primary branch updates only primary, so one operation
cannot be claimed to repair both banks. Do not keep rerunning change or restore
when a response is missing. The report keeps write_outcome uncertain until disk
readback establishes it. Use the captured evidence to engineer the specific repair.
See recovery-layout.md for exact native source anchors and other recovery limits.

After a successful original-region restoration and normal restart, use
verify-region with --expect original and the same original baseline.

## Included implementation and validation limits

The package includes source/region_app.py, region_protocol.py, region_compat.py,
the build scripts, pinned authentication source, reference hashes, dependencies
and licenses. Legacy apply/verify/prepare commands remain for previous reviewed
profiles; the v2 workflow uses change/assess/verify-region and no manual profile.

Protocol inputs are pinned Sony-PMCA-RE commit
a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0 and retained T100/G3 code. File response
headers preserve function/sequence/flags, segments carry remaining size capped at
1 MiB, and bodies use 32-KiB chunks. Extra empty reads after 512-byte multiples
remain a PMCA-derived expectation; unexpected bytes are preserved and rejected.
No empty-read loop, broad path scan, terminal activation, raw flash write, USB
reset, automatic driver detach or generic service-shell initialization is used.

Offline tests exercise real host code with synthetic devices. They do not prove
W300 compatibility, original-board eligibility, recovery or persistent English.
The next decisive evidence is the actual W300 capture and its observed behavior.

The revised capture also requests `/usr/bin/sen`, a T100 startup-path-backed alternative to G3 libsencore. This optional artifact supports later W300 analysis and does not relax the write checks. Repeat-read unavailability is a verification failure; incomplete XML is retried only during the bounded save-convergence wait, without resending the write.
