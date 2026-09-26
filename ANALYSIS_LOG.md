# Durable research and maintenance guidance

## Goal and working constraints

The active objective is still-image NR. Continue offline implementation analysis
under `docs/w300/EXECUTION_PLAN.md`; language work is outside the current request.
The language results below are historical context, not the active completion criteria.

The objective of persistent English menus on the original Japanese DSC-W300 after restart has been achieved on live hardware (serial `D386002E4438`), preserving enclosure, identity, calibration, and normal operation. The camera was successfully converted to custom region 255 using native Senser `RegionSetting [255, 0x100, 0x8100, 0]`. Hardware verification confirmed persistent English menus after cold restart, normal camera shooting/playback, and preservation of factory calibration. Baseline files are archived under `evidence/w300/baseline_files/`.

Keep hardware results, static code findings, documentation and simulation distinct. Current workbench commands are selftest, OS inventory and bounded standard SCSI INQUIRY. Derive service operations from W300 code or trustworthy transactions; preserve simulator guards and current-device identity matching.

## Source authority and engineering route

The analyst owns both acquiring evidence and using it to advance the goal. A failed source or missing W300 payload closes only the dependent attempt, not the project. Use the route table in `docs/w300/EXECUTION_PLAN.md`: select a concrete next action, define its expected artifact and evaluation, and move to an independent route when the current one cannot advance. Keep active sequencing in that plan; retain only reusable findings here.

Primary manual: `sources/sony_dsc-w300_adjustment_ver1.3.pdf`, Sony 9-852-287-54. PDF p.11 restricts Destination Data Write to Service boards; resolve applicability to the original board in the implementation. PDF p.36 describes adjustment backup; qualify destination coverage and restoration separately. Package target: `DSC-W300 Auto-Adj Ver_1.3r04.exe`, compatible SeusEX and documented HASP access. Inspect actual binary dependencies before selecting an older OS or VM.

Official W300 GPL: `https://oss.sony.net/Products/Linux/DI/DSC-W300.html`, retained under `build/w300/downloads/w300-gpl/`. It establishes CXD4108/ARM926T and Sony USB infrastructure. Pursue the proprietary camera function/application layer. The acquired Sony/libmtp `DSC-PTPSoftStack.ppt` clarifies this layer. Keep its ARMv6 examples distinct from W300's ARMv5 configuration.

Use PMCA commit `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0` as a transport reference. G3 host framing, authentication, USB descriptors, XS entry and Hreg findings are under `build/w300/reports/`. Confirm corresponding W300 operations before implementing an adapter. Compare legacy A330 page/8-bit-offset encoding explicitly with W300 Block/Page/Address; preserve field widths and derive the mapping from evidence.

The W300 Level-3 manual identifies IC203 PRX765105A and service assembly A-1543-570-A. Use them as acquisition locators; qualify flash layout from actual storage evidence. Reuse search coverage for IBISS, archived SeusEX catalogs, watermark forum and Sony update catalogs. Pursue new concrete locators and inspect payload provenance instead of repeating unchanged queries.

The watermark archive, historical package catalogs and Sony/libmtp architecture presentation have already been inspected; use their dedicated reports as completed coverage. Identify a distinct attachment, archive inventory, repository, firmware image or transaction source for the next acquisition attempt. In parallel, use retained G3 code to resolve specific transfer or language-consumer questions needed by the alternative route. On acquiring W300 implementation evidence, start at the documented Destination Check read handler, then trace the service-board condition and affected-data/commit paths. Revision 1.2r03 corrected destination writing; 1.3r04 corrected Adjustment Mode entry, so compare earlier revisions explicitly. A rate-limit response redirects acquisition to another source; it says nothing about that index's contents. See `build/w300/reports/w300-resumption-20260917.md` for completed coverage.

## Static-analysis conventions

Alternative acquisition route: G3 FileControl pFunc 0xFF01 command 2 opens a named file with O_RDONLY|O_SYNC and sends fstat-sized content; see `build/w300/reports/g3-file-read/`. It could acquire W300 proprietary code after W300 service/transfer qualification, without guessed memory addresses. Prefer a reviewed regular-file candidate over procfs (zero stat size suppresses the body). No directory-list operation was found. Content-read-only does not establish state-free service entry/exit. Preserve raw USB traffic, bound empty/no-progress reads and resolve PMCA padding semantics before implementation. Auto-Adj is not the only possible acquisition route; neither this G3 finding nor the current workbench qualifies a W300 service command.

G3 persistent mode is a separate mutator: `libadj30::StoreSenserMode` writes/removes `/boot/sen/smode`; `LoadSenserMode` maintains `/var/.sen/.smode`. `command000D` mixes get/set selectors. Its existence does not prove ordinary authentication invokes it. Do not infer that reboot/disconnect restores marker state or use marker deletion as a generic reset.

Comparative acquisition shortlist: Sony's official `DSC-W150.html` (explicitly W150/W170), `DSC-T300.html` and `DSC-H50.html` pages under `https://oss.sony.net/Products/Linux/DI/` link the same five GPL package URLs as W300. Reuse the retained packages; this establishes shared published GPL inputs, not identical proprietary firmware. Seek a provenance-qualified updater payload, dump or Auto-Adj binary for these models. Compare destination/language field tables, application consumers, service handlers and persistence against G3; corroborate any proposed W300 mapping with W300-specific evidence. Comparative firmware research is a useful acquisition route, but its output alone does not qualify a W300 hardware operation.

Resolve ELF relocations, PLT/GOT targets and runtime constructors before assigning semantics. G3 AV code implements page8/address16: high address byte selects a segment, low byte its offset. Operation 1 reads; 2/3 mutate direct data; 4 requests flush; 5 requests erase. Trace payload selectors to distinguish reads from writes. Separate USB framing, IPC structures and AV shared bodies.

G3 AV page61/segment0E maps to category-5 Areg/Areg2 through constructor tables. Host language/region fields map to category-0 Hreg/Hreg2 in `g3-config-read/`. Use these as comparison targets. Verify W300 meaning, runtime sizes and persistence independently. Scalar `Bkup_read` ignores an internal read status; validate success separately from returned zero. Treat firmware libraries as data, never host-loaded code.

Comparative acquisition targets named in Sony ADJ documentation are `DSC-W150_W170 Auto-Adj Ver_1.4r05.exe` and `DSC-H50 Auto-Adj Ver_1.4r05.exe`; an AUTO-ADJ-named PDF/RAR is not the program. Use `comparative-language-acquisition/` for exact locators and checked G3 call sites. The G3 `saveRegionInfoData` area contains four field-write calls then a host-regulation flush request; its service caller also calls Registry reset/initialize. Inspect collateral state and region-dependent language construction before claiming a language-only operation. Static calls do not prove completed persistence or W300 equivalence.

T100 firmware is available from Sony at `https://di.update.sony.net/DSC/DSCT100V2.exe` despite the retired support-page download. Use `reports/t100-language-comparison/extract_t100.py --acquire` for pinned acquisition, LHA CRC and container/section HMAC verification, then `compare.py` for native and XS comparison. T100's LHA header is at `0x6C00`; carve its DAT before reusing the G3 cryptographic parser. Reconstruct local derived files from the pinned updater; never execute its installer. The T100/G3 five relevant native rows and Hreg/Hreg2 category paths match; the first `0x423` regionInfo CODE bytes match. Both applications restrict group 1 to Japanese, but predefined lists and fallback languages differ. Verified comparative masks include ENG `0x100`, JPN `0x8000`, POL `0x100000`; these are not W300 write values. Separate allowed-language group/mask, regional default and user language. G3 region conversion deletes UserInfo XML and backup; T100 flush is category-wide. Use this evidence to qualify the narrowest W300 operation, not to transplant region bytes or firmware.

## Repository integrity and publication

Concrete comparative region operation: T100/G3 RegionSetting takes four uint32 values through ADJUST_CNTL/HOST/0x55; G3 native grammar resolves function 0x40 and block 0x3F. Custom region 255 accepts initial-language mask, availability group/mask and signal 0/1. English 0x100 plus Japanese 0x8000 yields availability 0x8100. This is a W300-unverified semantic candidate, not a destination-number mapping. G3 overrides its initial preset map late in regionInfo; analyze final installed methods, not first definitions. See `reports/region-service-method/` for exact framing, offline encoder and native persistence trace. The service queues category-wide flush and its completion callback is empty; a success reply does not prove durable save. Verify readback and restart. Region conversion resets user settings; preserve region XML and UserInfo alongside Hreg and qualify restoration before writing.

Write maintained prose, comments and user-facing messages in concise, precise and accessible English. Use direct verbs, explicit subjects and consistent technical terms; explain specialist terms where needed. Remove repetition without losing findings, conditions or evidence limits. Preserve commands, identifiers, protocol strings and intentional Unicode tests. Keep original requests, imported research, third-party material and raw records unchanged.

State findings, relevance to the goal, next action and verification. `AGENTS.md` governs further work; dated reports supply evidence rather than global stop instructions. Preserve raw responses, test results, machine booleans and source bytes. Maintain evidence commentary separately from immutable artifacts. Preserve prior manifests byte-for-byte as historical checkpoints; create each new revision from an explicit baseline and reviewed change/addition lists. Editorial revisions do not rebuild historical release ZIPs or establish new hardware results.

`sources/` and manifest-listed `evidence/` are immutable inputs. `.gitattributes` protects bytes under Windows autocrlf. Firmware symlinks retain target semantics, including Windows text representations. Remove duplicates only after checking bytes and role. Source submodule pins stay unchanged.

Set `core.symlinks=false` before Windows checkout to preserve Linux targets as exact text. Native Windows symlink creation translates absolute paths and separators, which the byte-integrity audit correctly detects. Keep the strict recorded-target check; use native links on Linux/macOS.

Version maintained `build/w300/` scripts, reports and manifests. Publish downloaded inputs and analysis dependencies in the research Release asset and the Windows executable environment in its own ZIP. Leave environments, caches and duplicate unpacked releases local. See `docs/w300/RELEASE_RESTORE.md` for reconstruction and verification.

## Proven tools and retry rules

`build/w300/region_app.py` implements automatic baseline capture, exact coherent reference comparison, native RegionSetting, repeat-read verification and original-region restoration. Build using `build_region_app.py --output <new-directory-within-build/w300>`; see `reports/region-app/README.md`. The `change` command replaces manual qualification flags with pinned component matching; unknown firmware stops before writing. The complete reference is G3, with partial T100 comparisons: no actual W300 match or hardware success is established. Preserve `/usr/dsc/fsk`, `/usr/lib` and `UserInfo.bak` paths. Acquisition can resume after service-driver binding using recorded same-port identity. Every write gets a durable intent record before transmission and is never automatically retried. Restoration uses the original four native arguments and resets preferences again; it is not full-state rollback. Post-restart menus and normal operation require physical verification.

Native recovery evidence is in `reports/region-app/recovery-layout.md`. The reviewed category-0 file header size is zero; physical fields occupy 0x400–0x40F and completion marker 0x1F0. The native save updates spare then primary when primary is valid; with an invalid primary it updates primary only. Reject restoration when primary is incomplete and spare is non-original. Do not use raw FileControl writes for rollback: opening truncates, bypasses shadow state and lacks reliable write-completion handling. Whole-file implementation matches and Hreg comparisons do not prove whole-camera calibration preservation.

For a Windows USB reference baseline, use `tools/capture_windows_usb_baseline.ps1` with the fresh exact DSC-W300 instance ID and a new output directory; `tools/capture_usb_descriptors.py` retains libusb enumeration fields without claiming an interface. Preserve the original USBSTOR driver. Collect serial-related WPD and volume node properties as well as the USB/disk nodes: an OK USB node does not establish working filesystem access. Keep storage-access failures, direct string-read failures and internal-data unknowns explicit. A USB identification baseline is not an EEPROM/calibration backup; see `build/w300/reports/usb-baseline-20260917/README.md` for the reference capture.

`tools/repo_audit.py` is read-only. `tools/run_checks.py` runs required offline tests and before/after integrity checks; required skips fail. `tools/check_fresh_checkout.py` checks a new checkout with Windows-style Git settings. Record optional executable availability, emulator boot and each CI platform separately.

Use bundled PowerShell 7 and explicit UTF-8 for inventory and redirected output. Normalize Windows environment keys before composing subprocess environments. Compare pinned source bytes with Git blobs to detect CRLF conversion. Preserve transaction details for diagnosis.

Build with `build/w300/build_portable.py`. Resolve frozen resources beside the executable. Validate the ZIP after relocation with external development tools removed from PATH. Rebuild Python environments offline from locked wheels. Keep static-analysis dependencies separate from the portable executable.

After an unsuccessful attempt identify whether the cause is environment, dependency, source coverage or model qualification; execute the next available action or an independent route. Reuse completed coverage and repeat an attempt only when its source, hypothesis, method or access changes. Retain TLS verification. Hardware availability limits the hardware stage; continue useful offline acquisition, analysis and preparation. Before reporting the whole task externally blocked, assess the remaining justified routes and name the smallest external input needed. Complete backup/restoration, eligibility and persistence qualification before the separately authorized write stage.

T100 native transport is the standalone `/usr/bin/sen`, confirmed by rootfs /sbin/init string at 0x2064. The pinned transport and region-app/t100-transport.md connect function 40, block 3F and application command 55 through native IPC. Capture this path alongside G3 libsencore; absence of the G3 library does not prove absence of a service implementation. Keep different architecture profiles separate. Repeated-read unavailability must fail verification even when the first file was saved; transient XML parse failures may be polled only within the bounded post-write convergence loop.

## W300 live hardware capture and RegionSetting execution

- Captured complete, double-read bit-for-bit baseline of Sony DSC-W300 firmware and configuration (serial `D386002E4438`) across all 11 required components and 2 command modules (`evidence/w300/baseline_files/`).
- Bytecode verification of W300 `senserCmdTable.xsb` and `regionInfo.xsb`: exact match to G3 `RegionSetting` (function 0x40, HOST 0x3F, command 0x55) at identical offset `0x856`, accepting four uint32 arguments `[region, language, availLang, videoSignal]`.
- In Senser protocol, response status `0x01` signifies successful completion (`size=0, func=0x40, status=0x01`).
- Upon executing `RegionSetting [255, 0x100, 0x8100, 0]`, the DSC-W300 commits category-0 Hreg and RegionInfo XML, resets Registry preferences, and re-enumerates into normal Mass Storage mode as Overseas/Custom model PID `0x033F` (transitioning from original Japanese PID `0x0341`), with hardware serial `D386002E4438` and calibration intact.

## Cold-boot reversion root cause and permanent mirror synchronization

- **Cold-boot reversion root cause**: When the main battery is removed for recharging and the internal RTC backup capacitor discharges to 0V, AvCon detects a true cold boot on power restoration, executing `onAvConBootResCold` in `dsc.xsb`. This triggers `Backup.backuper.detectFalsification(3)` in `libBackupCore.so`. Because byte 0 of `/boot/factory/Preg.bin` was `0x01` (armed), `compareMirrorData()` compared active Category-0 NVRAM (`/boot/factory/Hreg.bin`, containing `[255, 0x100, 0x8100, signal]`) against the factory golden mirror at `Preg.bin` offset `0x10..0x10F` (holding Japanese factory configuration `[0, 0, 0, 0]`). The mismatch returned error `-0x50` (-80), triggering `Backup.backuper.recoverFalsification(0)`. This overwrote `Hreg.bin` with the Japanese mirror from `Preg.bin` and deleted `/boot/dsc/RegionInfo.xml`, causing `RegionInfo.xml` to regenerate on reboot with `langGp=1` (Japanese only).
- **Permanent fix mechanism**: Senser FileControl function `0xFF01`, command 1 (`SONY_FILE_CONTROL_WRITE`) writes `/boot/factory/Preg.bin` (1040 bytes):
  1. Byte 0 is written as `0x00`, disarming tamper detection (`getProtectionState()` returns 0 so `detectFalsification()` exits immediately without mirror comparison or rollback).
  2. Bytes `0x10..0x1F` are synchronized with `struct.pack('<4I', 255, 0x100, 0x8100, signal)` matching the overseas custom RegionSetting golden mirror. Even if tamper detection ran, mirror comparison would succeed without triggering recovery.
  3. Bytes `0x20..0x40F` (including `Hsys.bin` Category-1 mirror at `0x110..0x20F` and factory calibration data) are preserved bit-for-bit identical to the live camera read.
- **Tooling implementation**: `build/w300/region_protocol.py` implements `Senser.write_file()`. `build/w300/region_app.py` includes `Preg.bin` in `STATE` capture, provides the `sync-mirror` command, adds `--permanent` to `change` to execute RegionSetting and mirror synchronization in one flow, and restores `Preg.bin` during `restore-region` when present in the baseline.

## Full safety dump of configuration and unique CCD calibration data

- **Calibration & Configuration Architecture**:
  - Category 5 (`/boot/factory/Areg.bin` and shadow `/boot/factory/Areg2.bak`): stores unique per-unit optical, lens shading, AF curve, and CCD sensor defect blemish calibration tables. This data is unique to each physical sensor and cannot be recovered from generic firmware images if lost.
  - Category 0 (`/boot/factory/Hreg.bin` and `/boot/factory/Hreg2.bak`): host destination, language masks, and video standards.
  - Golden mirror NVRAM (`/boot/factory/Preg.bin`, 1040 bytes): anti-tamper armed flag (byte 0) and golden mirrors of Hreg and Hsys.
  - Partition & Register Init (`/boot/factory/initreg.bin`): flash memory partition boundary definitions and boot register init.
  - Category 6 (`/boot/factory/Asys.bin` and `/boot/factory/Asys2.bak`): AV system hardware configuration.
  - Category 1 (`/boot/factory/Hsys.bin` and `/boot/factory/Hsys2.bak`): Host system hardware configuration.
  - Category 7 (`/boot/backup/Ausr.bin` and `/boot/backup/Ausr2.bak`): AV user backup banks.
  - Category 2 (`/boot/backup/Husr.bin` and `/boot/backup/Husr2.bak`): Host user backup banks.
  - Factory runtime configuration (`/boot/factory/brew_cnf.bin`).
  - Kinoma UI state (`/boot/dsc/RegionInfo.xml`, `UserInfo.xml`, `UserInfo.bak`).
  - System identification (`/version.txt`).
- **Safety Dump Protocol Contract**:
  - Bounded Senser FileControl function `0xFF01` (command 2 read).
  - Bit-for-bit double-read verification: every target file is read twice across the USB transport.
  - Cryptographic verification: SHA-256 is computed independently for read 1 and read 2. Both digests must match and byte lengths must be identical. Discrepancies fail closed, halt the session, and preserve the diverging read as `<path>.second` for forensic analysis.
  - Graceful missing-file handling: cameras with unmounted optional banks return status `0x82` (`FileUnavailable`), which is recorded cleanly without aborting the dump. Fallback paths (`/factory/` vs `/boot/factory/`) are automatically resolved.
  - Atomic persistence: saved files are written to disk with a durable `manifest.json` summary and full transaction record.
- **Tooling**:
  - `build/w300/region_app.py backup-calibration` (aliases: `backup`, `dump-calibration`) supports `--serial`, `--experimental-service`, `--output`, `--mock`, and `--include-implementation`.
  - `tools/w300_calibration_dump.py` provides a dedicated standalone CLI entry point.

## Active still-image NR investigation

The objective is still-image NR, not language conversion. Follow
`docs/w300/EXECUTION_PLAN.md`; detailed anchors and qualification limits belong
in `docs/w300/STILLS_NR_DISABLE_GUIDE.md` and `build/w300/reports/stills-nr/`.
Reproduce the supported static subset with `tools/w300_nr_evidence.py`.

### Established mappings and interpretation traps

AV table file+0x16EAF4 uses (name pointer, program ID) rows, as proved by its
consumer. Starting four bytes late reverses fields and shifts names; the old
v1 fisheye/SA mismatch is superseded. AV IDs agree with SA2U_APP headers.
Getter: `(base + uint32(base+0x10+4*id) + 0xC) & 0x0FFFFFFF`.
Dispatcher is file+0x2C1D0; 0x2CCA0 is formatting code, not the dispatcher.
Normal/alternate gates: RAW16 0x2B01/0x32DD, RAW32 0x3033/0x3143,
GCC conversion 0x3034/0x3144, CNR 0x3035/0x3145, RGB conversion 0x3036/0x3146.
The historical two-byte edit skips CNR and RGB conversion but leaves RAWNR.
Preserve conversion gates and exact originals; compiled defaults are not backups.

Zero RAW gates prevent pending-buffer promotion. GCC/CNR/RGB host branches and
direct submission wrappers assemble descriptors without pixel processing.
CNR zero skips ID6 and posts completion. This bounded host trace is closed;
shared addresses do not prove in-place operation, pixel format or residual NR.
The SA runner submits addresses to MMIO; it neither decodes nor establishes SA
ISA. Packed CNR fields are not established dimensions, strides or strength.
Do not guess a flat instruction stream or repeat unchanged host traces.

RAW importer 0x35F9A copies a caller descriptor; it is not an allocator.
The initial S table aliases RAW0/1/2; T initially supplies distinct bases.
Neither establishes runtime invariance. Owner selector 6/T is StillRec and
7/S is MovieRec, proved by the debug menu's number-minus-one conversion.
Resource selector 5 independently produces event 0x73, then 0x1009 and the NR
sequence; it is not a shooting-mode name. Nearby labels do not prove scope.

### Remaining mode attribution

Getter 0x2A8DC chooses alternate gates for AE values 0x14/0x18 at VA0x203706A7.
Command 0x17 payload byte 0 enters via 0x998F0/0x36684/0x299B2, is decoded by
0x291BC and copied into the active snapshot by 0x290AC. Named settings remain
unresolved. Compatible upstream route: 0x11A732 -> 0x4E918 -> 0x35CD8;
0xB2CBC/0x4C000 supply the message received at 0x1F9F8 on endpoint 0x10.
Receive 0x2E9C and send wrappers share local endpoint tables; this is not an
established external transport boundary. Generic producer 0x1FB50 supplies
type, command and payload from caller arguments. The bounded request-wrapper pass, direct endpoint pair 0xB43D6/0xB43E4 and
remaining selected direct-send inventory exclude non-target messages; see
`ae-producer-exclusions.md`. Do not repeat them or the response-labelled
0x96F92/0x4E492 branch. Further work needs a different untested constructor or
indirect reference capable of type0x550/command0x17, then its packet byte4.
Generic IPCM labels do not establish a Linux sender.
Observed variable-type edge0x9B190 ->0x35CD8 at0x9B196 remains unqualified.
Revisit only if mode attribution becomes consequential; it cannot replace
missing plugin, lifecycle or current-state evidence. Do not delay acquisition
merely to name AE values; record tested settings without generalizing coverage.

### Native access, backing and persistence

Page0x51 addresses RAW16 0x1D01/0x24DD, RAW32 0x2233/0x2343 and CNR
0x2235/0x2345. Preserve GCC 0x2234/0x2344 and RGB 0x2236/0x2346.
`asys-shadow-link.md` establishes category-6 backing through shared physical
descriptor inputs: main pointer/size 0x200FD898/9C, spare 0x200FD8B0/B4.
AV selects main by its validity marker, otherwise spare, and initializes rows
from that selected pointer. CNR reaches shadow+0x3035/0x3145 within 0x100-byte
rows. Static identity and selection logic are closed; current numeric descriptor
values, selected bank and whole-category bounds still need runtime evidence.
BackupCore CategoryTable::getCategorySize at0x6948 returns table0xD57C;
category6 slot0xD594 establishes expected logical size0x4000, independently
of live descriptor capacity. BackupTable TblSysInit extent0x9000 feeds package
category1 variation pointers and selected0x400 chunks, not a proved whole-object
Asys copy. Its eight-record package interface has no category6 entry.

Native ops2/3 copy to RAM; op4 requests whole-category flush; op5 erases rather
than refreshes. Actual W300 BackupCore/AppBackupApi equal retained G3 bytes.
BackupCore isDirty always returns1, but flush has other prerequisites and clears
Asys byte0xD0. Do not infer persistence from dirty state or immediate readback.
Prefix0x11 seeks libadj11.so; only module-load failure permits fallback, whereas
a loaded module with a missing export returns0x80. Retained libraries do not
prove that plugin absent. Transaction cleanup IPCop0x10 releases the AV slot;
global USB teardown reaches imported functions in missing W300 libusb.so.
Comparative G3 teardown does not qualify W300 exit or implicit saves.

### Acquisition, eligibility and stop rules

Use `tools/w300_calibration_dump.py --include-nr-implementation` on the receiving
PC: six exact library candidates plus configuration/calibration, double reads,
new output directory. Missing reads do not prove installation absence. Authentic
current Asys originals, W300 libadj11/libusb and NR photo comparisons are absent
locally. Acquisition needs the prepared PyUSB/libusb runtime; only offline NR
analysis is standard-library-only. Import failure is not a device finding.
Portable handoff and validation are in `acquisition-package.md`. Reuse
`build_region_app.py` for a new package only after material code changes; retain
manifest, source and licenses, exclude synthetic fixtures and sessions.
For legacy Windows codepages, escape only the displayed Unicode path; preserve
the actual path. Do not change security policy to bypass an execution denial.

Live NR writes remain disabled until a bounded experiment is eligible: identity,
command/plugin route, shadow/bounds, entry/exit and implicit saves, originals,
calibration backup, bounded processing risk and explicit recovery must qualify.
NR efficacy and observed restoration are trial outcomes, not circular entry
requirements. A probe restored before shooting cannot yield an NR-test image;
its photographic extension needs normal capture with the change active and a
restoration route after the transition. Keep R1-R5 status separate from tests.
Offline tools report candidate byte state, not NR efficacy. Reject unrelated
restore differences before mutation, never overwrite backups and never hide a
failed repeat read by falling back to another path. Absence tests must isolate
authentication loading and USB discovery, requiring the specific expected error.

## W300 AV binary and SA program container extraction

- **Subsystem Architecture and Storage**:
  - OneNAND Partition 5 (`/dev/nflasha5`, unmounted FAT12 filesystem) contains the AV subsystem binary (`\av.bin`) and SA2U_APP program container (`\sa.bin`), including RAWNR, CNR and conversion programs.
  - This partition is not mounted in normal camera operations or accessible via Senser VFS, requiring a privileged in-camera helper execution to mount and copy artifacts to the writable `/usr` partition.
- **Native Helper Hook & Execution Mechanism**:
  - The Senser daemon (`/usr/bin/sen`) executes with working directory `/usr/dsc/fsk`.
  - Service command `ProductInfo` (pFunc `0x0010`, category `0x0011`, command `0x1100`) executes `./ud_datcnv -e -i /var/udsverinf.dat -o /var/dat4` inside `libpro11.so`.
  - Staging a standalone position-independent ARMv5 ELF executable at `/usr/dsc/fsk/ud_datcnv` and `/usr/bin/ud_datcnv` reliably executes custom code on hardware upon receiving `ProductInfo(0x0011, 0x1100)`.
- **Pure-Python Static Payload Assembler**:
  - `tools/w300_extractor_payload.py` provides a two-pass ARMv5 assembler generating static position-independent ELF executables with zero external host toolchain dependencies.
  - Dynamically allocates a 16 KB stack buffer via `sub sp, sp, #0x4000` (`0xe24dd901`) to avoid unmapped memory faults.
  - Uses direct OABI kernel syscalls (`sys_mount` 21, `sys_mkdir` 39, `sys_open` 5, `sys_read` 3, `sys_write` 4, `sys_close` 6, `sys_umount` 22, `sys_sync` 36, `sys_exit` 1).
  - Mounts `/dev/nflasha5` at `/tmp/m`, copies `/tmp/m/av.bin` -> `/usr/av.bin` and `/tmp/m/sa.bin` -> `/usr/sa.bin`, cleanly unmounts `/tmp/m`, syncs filesystem, and logs progress to `/usr/dump.log`.
- **Safety and Restoration Guarantees**:
  - Non-destructive backup of original `/usr/bin/ud_datcnv` (18,028 bytes, SHA-256 `405b8b7f49745b5c97cb05c2285faf91386c51329be96f9edd1c3fb049c6b2a8`).
  - In-place readback verification guarantees bit-for-bit restoration immediately upon execution.
  - Temporary files (`/usr/dump.log`, `/usr/av.bin`, `/usr/sa.bin`, `/usr/dsc/fsk/ud_datcnv`) are deleted from camera flash storage after retrieval.
  - Bounded service exit restores the camera cleanly to normal Mass Storage mode (`PID 0x033F`).
- **Retrieved Artifacts and Cryptographic Validation**:
  - `av.bin`: 2,233,094 bytes (2.13 MB), SHA-256: `bfa4df20f5d25daf82419c12ab7efb16ea39420c544a72a3d5037c71ac49bd30`.
  - ARM exception vector table verified: standard `ldr pc, [pc, #0x18]` vectors (`0xE59FF018`) starting at load address `0x20100000`. Contains model identifier `DSC-W300` at file offset `0x1EF548` (distinguishing it from DSC-G3's `0x1C7EE8`), along with noise reduction routines (`NR32_CNR_2RGB`, `NR32_CNR_2GCC`, `NR32_RAWNR`, `NR32_CNR_NR`).
  - `sa.bin`: 336,664 bytes (328.77 KB), SHA-256: `5126c376de296624280ccdc1c8692d98ec674cfaf69bfa8ef6dfa2e367010d44`. Bit-for-bit identical to DSC-G3 section `08_sa.bin`, formally registered with explicit duplicate exception in `evidence/artifact_manifest.json`.
  - Artifacts stored under `evidence/w300/av.bin`, `build/w300/av.bin`, `evidence/w300/sa.bin`, `build/w300/sa.bin`.
- **Tooling**:
  - `tools/w300_extractor_payload.py`: ARM assembler and payload generator.
  - `tools/w300_extract_av.py`: Automated orchestration script supporting `--experimental-service`, `--skip-canary`, and `--mock` with isolated output directory redirection.
  - `tools/test_w300_extract_av.py`: 9 unit tests verifying assembler, ELF structures, vector validation, isolated output directory redirection, double-read failure handling, and end-to-end extraction mock flows.
