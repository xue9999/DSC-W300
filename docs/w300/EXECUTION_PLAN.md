# DSC-W300 execution plan — persistent English, editorial revision 4

Prepare persistent English menus on the original Japanese DSC-W300 while preserving identity, calibration and normal operation. The supplied W300Workbench implements `selftest`, OS `inventory` and bounded standard `inquiry`. Continue from these verified foundations to qualify the model-specific language operation. Camera communication and language qualification remain recorded as `false` until measured on the target device.

## Engineering routes and next actions

Use Sony-PMCA-RE commit `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0` as the transport reference. Retained G3 code matches its 12-byte Senser framing and SHA1 authentication branch for service PID `0x0336`. Sony's separate W300 and G3 GPL packages establish a common CXD4108/ARMv5 platform with different kernel revisions. Confirm W300 service identity, authentication, segmented address encoding and persistence against W300 code or documented transactions before adding camera operations.

The analyst owns acquisition and qualification. Work through the following routes according to the evidence currently available. Each attempt must answer a concrete question and produce an artifact or a bounded finding that selects the next action. Auto-Adj is a preferred source for the documented service operation; firmware and transaction evidence provide alternative entries.

| Route | Action to execute | Result and evaluation | Transition if this attempt cannot advance |
|---|---|---|---|
| Auto-Adj / SeusEX acquisition | Use retained package inventories to select an uninspected attachment, CD inventory or repository locator for `DSC-W300 Auto-Adj Ver_1.3r04.exe` and its dependencies. Inspect archives and embedded model/version before selecting an OS or VM. | Preserve source context and original bytes; distinguish an executable payload from a manual or catalog entry. Trace Destination Check first, then board eligibility and affected-data/commit paths. | Record exactly which locator was covered, then select a distinct source or the firmware/transaction route. Earlier versions are comparison inputs because 1.2r03 and 1.3r04 corrected relevant behavior. |
| W300 firmware or transaction acquisition | Search concrete W300 updater/dump references using the retained model, IC and board locators; inspect existing provenance-qualified captures for request/response context. | Identify actual W300 proprietary code or a complete attributable transaction, including input, response and state. Follow its destination getter, language consumer and persistence path. | Use the file-acquisition preparation below and comparative analysis to identify specific software paths or protocol questions. A filename alone remains a locator. |
| File-acquisition preparation | Trace retained G3 entry/exit and the command-2 sender against pinned PMCA framing; resolve the 512-byte padding behavior, failure responses and persistent-mode separation. Prepare bounded offline transfer fixtures for those questions. | Produce a reviewed framing/lifecycle specification and receiver test cases with declared-size, sequence, timeout and no-progress handling. Preserve raw responses in the eventual receiver design. | If one lifecycle detail needs W300 evidence, record that dependency and continue independent framing, parsing or source-acquisition work. Execute a camera trial only in its qualified later stage. |
| Comparative language analysis | Follow the retained G3 region/language reads and writes through application consumers and flush/reset calls; use the named W150/W170 and H50 Auto-Adj versions as distinct acquisition targets. | Produce a field/consumer/side-effect comparison tied to exact source anchors and explicit W300 verification questions. Shared GPL URLs are already known and need no duplicate download. | End a comparison when it no longer answers a concrete W300 question; return its locators and test requirements to the acquisition routes. |

The [resumption assessment](../../build/w300/reports/w300-resumption-20260917.md) records completed catalog/archive coverage. Reuse it to choose a different source or method. Acquiring W300-specific implementation evidence is an active work item; its absence does not suspend the independent tasks in this table.

The [Senser FileControl command-2 analysis](../../build/w300/reports/g3-file-read/README.md) supplies the source anchors for the file-acquisition route. After qualifying W300 service entry, exit and transfer behavior, this may provide proprietary libraries directly from the owner's camera. Qualify the reviewed regular-file candidate against W300; procfs can report zero stat size and suppress the transfer body. The current workbench implements identification only, so receiver preparation remains offline work until model qualification and the later camera session.

The analyst owns package acquisition, protocol qualification and implementation. Continue these offline tasks without connecting a camera to the preparation computer. The later camera session uses a separate Windows 10/11 x64 computer.

## Continuation and completion rules

1. Select an available action from the route table, state the question and expected evidence, then perform it. Prefer work that removes a dependency on the route to persistent English.
2. On failure, record the attempted source/method and bounded result. Close that attempt and execute the next justified alternative. Revisit it when the source, hypothesis, method or access changes.
3. When an operation requires unavailable hardware or external access, name that dependency and complete useful independent work. Prepare a precise handoff containing the required input, intended operation and expected observation.
4. Before ending the whole task as externally blocked, review all remaining justified routes and explain why each lacks an executable useful action. Do not substitute repeated searches, restated limitations or unrelated G3 analysis for progress.
5. Report research artifacts as research progress. Completion of the language objective requires the camera-level results at the end of this plan.

For a missing package, continue distinct package/firmware sources and transfer preparation. For an exhausted archive, preserve its coverage and change the source or method. For an absent camera, continue offline analysis and prepare the receiving-PC procedure. These situations restrict specific operations; none alone closes the research task.

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

Use the work items below to direct acquisition and analysis now. Hardware execution of a dependent operation follows its model-specific qualification; independent offline tasks continue while evidence is acquired. Record exact bytes, expected responses and recovery:

| Work item | Next offline result | W300 evidence and verification |
|---|---|---|
| Original-board eligibility | Extract the documented restriction and identify the corresponding condition through Auto-Adj or W300 implementation/transaction evidence. | Resolve the `Service board` condition for the original board; preserve its identity. |
| Language-only operation | Trace region/language consumers and collateral writes in acquired code; compare G3 anchors to formulate W300 tests. | Identify field, allowed values and narrowest update. Use destination conversion only if necessary and record its effects. |
| Baseline and recovery | Map documented backup commands to data coverage and list every region affected by the candidate operation. | Read current settings, preserve affected regions and verify restoration with identity/calibration preservation before the write trial. |
| Service session | Produce a lifecycle and bounded-transfer specification from the source anchors, marking W300-specific questions. | Establish entry, read, response-validation and exit; identify volatile versus persistent effects. |
| Persistence | Trace save/flush callers and distinguish RAM, EEPROM Write and flash Save in implementation evidence. | Establish the exact commit/save operation and post-restart readback. |
| Environment and power | Inspect actual program, driver architecture/signature and HASP dependencies; prepare receiving-PC requirements. | Validate the resulting setup. The documented adjustment setup uses AC-LS5 with the appropriate DC-input multi-use cable. |

Sony's adjustment manual, PDF p.11, restricts Destination Data Write to Service boards. PDF p.36 describes adjustment backups; establish destination coverage separately. `SERIAL` and `ADJBAK` protect different data. `WriteEnableTool.exe` concerns user image-storage access. Keep calibration, identity, initialization and cross-model firmware outside the language task.

U2 starts in English/NTSC; CEE8 starts in English/PAL. Derive bytes and side effects from the implementation. Auto-Adj's destination-completion OK dialog resets the camera and belongs to the later write stage. Comparative G3 erase/flush code and contemporary Sony service-board behavior guide inspection; confirm equivalent operations on W300.

After the separately authorized qualified write, verify settings readback, unchanged identity/calibration, English menus after power-off/restart, and normal shooting/playback. Record each result independently.

See [VERIFICATION.md](VERIFICATION.md) for measured results and acquisition routes. The [qualification worklist](../../build/w300/reports/w300-readiness-audit/README.md) turns those findings into the next engineering steps.
