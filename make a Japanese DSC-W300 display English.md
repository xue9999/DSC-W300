# DSC-W300 English conversion: verified working record

## Status and target

The camera has not been converted. No vendor USB commands, adjustment-mode entry, or camera writes have been performed. The passive Mac inventory found no attached USB devices at capture time; see `evidence/usb-baseline.json`. Camera destination, backups, and physical acceptance results are unknown.

Target: keep the enclosure closed and preserve the original camera's identity and calibration. Use **CEE8** as the preferred European destination if a validated conversion route becomes available. This is a documented symbolic destination, not a numeric NVM value. Do not infer an address or byte from it.

This working record supersedes the earlier report, preserved unchanged in [original research](sources/original-research-report.md). Unresolved citation tokens and speculative procedures in that archive are not execution instructions.

## Primary evidence and corrections

The user supplied the [W300 Adjustment Ver.1.3 manual](sources/sony_dsc-w300_adjustment_ver1.3.pdf), Sony document 9-852-287-54, August 2008, 37 PDF pages. Text is extracted alongside it; the destination table and backup page were rendered for inspection. PDF page numbers below are one-based.

| Finding | Exact source | Consequence |
|---|---|---|
| Exact application is `DSC-W300 Auto-Adj Ver_1.3r04.exe` | PDF pp. 1, 9; printed 6-8 | Search this executable/version; PDF contains no embedded software attachment |
| Destination Data Write is restricted to service boards | PDF p. 11; printed 6-10 | Official documented procedure does not establish conversion of an original retail board |
| AEP is an area grouping of CEE2, CEE8, CEE9 | Table 6-1-2, PDF p. 11 | Earlier literal-AEP dropdown requirement was wrong |
| CEE8 has initial English, selectable Polish, PAL | Same table, visually checked | Preferred destination for the requested European English configuration |
| CEE9 also defaults to English and includes Russian; CEE2 defaults to Russian | Same table | These are distinct symbolic destinations |
| J1 lists Japanese only | Same table | Consistent with Japanese-only menus, but actual camera destination must be read |
| Windows 2000/XP Home/XP Pro and HASP key + SeusEX are documented | PDF pp. 3, 4, 30 | Native Mac/Windows 11 compatibility is unproven; hardware key is an additional dependency |
| CONNECT initiates adjustment mode with a specified power/DC reconnection sequence | PDF pp. 9-10 | It is not a passive identification action |
| Successful destination write dialog instructs reset; OK automatically resets camera | Screenshot on PDF p. 11 | Earlier assumed pre-reset readback sequence was inaccurate; follow exact software behavior |
| DATA BACKUP reads/saves and loads/writes adjustment data | PDF p. 36; printed 6-35E | Coverage listed is video, LCD, camera adjustments, not proven destination or full firmware coverage |
| Backup filename is `DSC-W300_ADJBAK_xxxxxxxx_yyyymmdd.dat` | PDF p. 36 | Preserve original names and separate capture folders; never overwrite one read with another |
| END releases adjustment mode; subsequent power cycle confirms USB mode screen | PDF p. 10 | Use documented exit, not forced termination |

The service manual's [board replacement note](https://www.manualslib.com/manual/767486/Sony-Dsc-W300.html?page=5) corroborates destination programming but does not remove the restriction above. [WriteEnableTool instructions](https://www.manualslib.com/manual/767486/Sony-Dsc-W300.html?page=8) concern internal image-storage writes. They are not evidence of a destination unlock.

## Current package inventory

Recovered: W300 ADJ PDF, [official English handbook](sources/W300_hb_GB.pdf), and a pinned source checkout of [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE). File hashes and provenance are in [source manifest](sources/manifest.json).

Still missing: exact W300 Auto-Adj executable/payload, compatible SeusEX and Sony SEUS USB driver package, and HASP access for the official workflow. No W300 software binary has been acquired or executed. The PDF does not establish exact SeusEX/driver versions or Windows 11 support. A separate adjustment supplement remains unverified.

Acquisition attempts: exact executable/model web searches; Sony public support/download pages; archive-targeted searches; Internet Archive metadata queries for W300 and SeusEX; primary PMCA source and W300 issue search. These yielded documentation and unrelated consumer software, not a verified W300 adjustment executable. See [acquisition record](evidence/acquisition.md). Sony's manual directs service personnel to regional service headquarters for SeusEX/HASP; no contact message has been sent.

## Passive camera baseline

1. Power on the camera with a charged battery and connect its data-capable multi-terminal USB cable to the Mac. In HOME > Settings > Main Settings > Main Settings 2, select USB Connect > Mass Storage. Exact Japanese screen navigation must be matched to the physical display; do not guess icon positions.
2. Run from this folder: `python3 tools/w300_evidence.py inventory --output evidence/usb-connected.json`. Choose a new output filename for each capture. This reads macOS's existing device registry only; it does not open a camera USB handle or install drivers. A Sony VID is not enough to establish W300 identity.
3. Once storage is positively associated with this camera, copy its photos to separate local backup folders and compare file hashes. Do not format storage. Capture card and internal storage separately, following handbook instructions when changing media with power off.
4. Record physical model/serial privately, current menus and settings, any errors, and a new sample JPEG. Photograph language settings. If English is already offered, select it through the normal menu and test persistence before considering service programming.
5. Record baseline shooting, playback, autofocus, zoom, flash, movie, internal/card storage, and USB results. Unknown remains unknown.

Sony handbook references: [official source](https://www.sony.jp/cyber-shot/emdown/data/W300_hb_GB.pdf), pp. 87 (USB mode), 94 (language setting), 103-108 (connection/copying), 111-112 (Mac), 126 (connection troubleshooting).

## USB research route

The official restriction triggers software investigation, not a blind attempt to write CEE8. It does not by itself prove that a closed-enclosure conversion is impossible.

- Recover the exact W300 application and inspect it offline before connecting hardware. Identify destination-related read/write transactions and the service-board eligibility test. Do not assume this test is only a host GUI check or that bypassing it is sufficient.
- Establish whether programming is one-time, whether service flags change, what data/checksums are affected, and whether the original destination can be restored through USB. The manual does not answer these points.
- PMCA source inspection found no literal W300 model support entry, and the focused repository issue search returned no W300 results. Neither absence proves incompatibility. Its service transport remains a research lead, not a verified W300 route.
- `pmca/commands/usb.py:infoCommand` invokes updater initialization on the extended-command path and app-install communication on another path. Do not use stock `info` as passive identification here.
- `senserShellCommand` starts authentication and mode switching; `SonySenserCamera` exposes backup, memory, file, and terminal operations, including writes. Generic backup identifiers have not been mapped to W300 records. Do not probe guessed address ranges or run a general shell on this camera.
- The macOS native backend expects Sony kernel-driver interfaces. The libusb path can detach a kernel driver during reset. Neither has been validated on this Apple Silicon Mac/W300 combination. Do not weaken Mac security or replace drivers merely to try an unsupported command.
- If evidence establishes a safe model-specific read route, implement a narrowly bounded reader with explicit identity checks and immutable outputs. Do not add a writer until write scope, integrity handling, and USB recovery have been validated on separate same-model hardware or controlled evidence of equivalent strength.

## Backup and conversion gate

The current helper supports only passive inventory and **offline** comparison:

`python3 tools/w300_evidence.py compare backup-A.dat backup-B.dat --output evidence/backup-comparison.json`

It compares all bytes, reports sizes/hashes and bounded difference offsets, and exits 1 on differences. It does not parse or normalize an unknown Sony format. Matching empty files or matching opaque files are not a valid service backup by themselves. File inputs must remain unchanged during comparison.

Before any destination write, require: verified model and original destination; compatible stable service transport; two consistent nonempty captures of every affected record; established backup coverage and restore procedure; a proven production-board method; understood reset behavior; stable documented power setup; and demonstrated rollback. A rendered menu table, matching backup hashes, or enabled Data Write button does not satisfy these requirements alone.

If the official workflow is ultimately applicable, follow the exact W300 procedure with CEE8, including its reset/completion dialog and destination readback. The source documents AC-LS5 and the appropriate USB/A/V/DC multi-use cable for adjustment setup. Do not silently substitute a battery-only service-mode sequence for its DC reconnection instructions.

Exclude USB serial input, unrelated calibration, raw register writes, another model's payload, and Aging. Aging can format full media and reset counters (ADJ pp. 33-35). Do not invoke it for acceptance testing.

## Acceptance and recovery

All physical results are currently **not tested**: persistent English across three normal power cycles and battery removal/reinsertion; shooting/playback; focus/zoom; flash; movie; available storage; USB transfer; identity retention; destination readback.

Success requires photographs of English menus and recorded physical results, not merely a tool success dialog. Document any PAL/region default change.

On write failure, retain the message and connection state, use only established W300 recovery, and restore this camera's own data when coverage and restore semantics are known. Do not automatically repeat a failed write or assume service access survives. Loss of USB enumeration is a stop condition for writes; the enclosure remains closed.

Next dependencies: connect the camera for passive inventory; obtain the exact W300 service package or independently validate a W300 USB read protocol. Conversion is incomplete until those dependencies and the write/recovery gates are resolved.
