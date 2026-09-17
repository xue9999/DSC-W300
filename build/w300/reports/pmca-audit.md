# PMCA and legacy Senser audit

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

## Scope and status

Audit date: 2026-09-16. No camera commands were executed. This is source inspection, primary upstream issue review, download verification, and one offline authentication calculation. Qualify DSC-W300 hardware support through separate target-model evidence.

Inspected checkout: `build/w300/upstream/Sony-PMCA-RE`, revision `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0` (`Improve error messages`). All PMCA line references below are relative to that checkout and revision.

**Decision:** the ready-made PMCA language tweak is not a qualified W300 procedure. A concrete, separate legacy Senser protocol supplied by PMCA's maintainer is a materially better development lead than enabling USB in the repository simulator. That protocol achieved a persistent language change on a DSLR-A330, after model-specific firmware analysis. It has not been shown to use the same destination addresses on W300. The W300 transport, destination byte(s), commit operation, backup coverage, and retail-board restrictions remain to be established.

## What the pinned PMCA actually does

### Detection is active and is not a model-support test

- `pmca/commands/usb.py:175-214` enumerates Sony VID 054c and sends SCSI Inquiry or PTP GetDeviceInfo. A Sony mass-storage camera is inferred from SCSI vendor `Sony` and product `DSC` or `Camcorder` (`pmca/usb/sony.py:29-54`). This string does not identify DSC-W300.
- Constructing `MscDevice` issues Test Unit Ready before Inquiry (`pmca/usb/__init__.py:23-64`). Generic transport reset may detach a kernel driver on platforms supporting that operation (`pmca/usb/driver/generic/libusb.py:66-72`). PTP detection opens a session (`pmca/usb/__init__.py:78-80,120-133`).
- `info` additionally invokes Sony extended GetModelInfo, initializes the firmware updater, queries firmware version, and attempts lens/GPS queries (`pmca/commands/usb.py:231-269`). It is not passive OS inventory. No firmware payload is written by this command, but updater initialization is an actual protocol action.
- `serviceshell` sends a mode-switch vendor request and authenticates, waits for re-enumeration, authenticates again, calls `readHasp`, then exposes an interactive shell with write commands (`pmca/commands/usb.py:656-708`, `pmca/platform/backend/senser.py:9-10`, `pmca/platform/__init__.py:24-48`). A successful shell is not proof that a language tweak is available or safe.

### Modern service protocol and language operation

The pinned program recognizes service PIDs 02a9 and 0336 (`pmca/usb/sony.py:31`). Its startup vendor request is request 01, value 37ff, index d7aa; authentication performs three SHA1/SHA256 challenge cycles followed by a final status exchange (`pmca/usb/sony.py:890-936`). The service packet header is a little-endian structure carrying pFunc, sequence, version and related fields (`pmca/usb/sony.py:822-876`).

The language operation is a compound property covering 35 one-byte IDs starting at `0x010d008f` (`pmca/platform/backup.py:174`). `LanguageTweak` accepts 01/02 values and uses a region table to construct all-languages enablement (`pmca/platform/tweaks.py:105-135`). This is a language-availability operation, not proof that every language has resources on every camera.

In this revision, tweaks first obtain and parse a complete backup preset into `BackupPatchDataInterface` (`pmca/platform/tweaks.py:138-181`, `pmca/platform/backup.py:106-159`). `BackupFile` accepts only BK2/BK4 revisions and validates a checksum (`pmca/backup/__init__.py:54-74`). Applying a tweak rewrites the backup preset using protect mode 2, reads it back, and may write twice to restore property attributes. Therefore it must not be represented as a known one-byte W300 write. The Senser commands are adjust block 0603, read=1, write=2, save=3, preset-write=4, preset-read=5, status=6, protection=15 (`pmca/usb/sony.py:967-974,1038-1057`). None is linked by inspected evidence to a W300 destination field.

The updater route selects a matching firmware header and payload; absent an exact match it stops (`pmca/commands/usb.py:319-337,350-378`). It then initializes the updater, checks the supplied image, switches modes and transfers a firmware payload (`pmca/commands/usb.py:381-423`). There is no basis to force a G3 or another model's image for W300.

### Windows transport and dependencies

The upstream [README at the pin](https://github.com/ma1co/Sony-PMCA-RE/blob/a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0/README.md) documents native Windows mass-storage/MTP drivers for regular commands and libusb-win32 installed by Zadig for service mode. It requires replacement for the normal camera interface and, after re-enumeration, its service interface. Driver replacement is a separate operation; downloading a DLL is not installing the camera driver.

- Native MSC uses Windows SCSI pass-through and needs a removable-drive mapping (`pmca/usb/driver/windows/msc.py:64-105`). Native MTP uses Windows Portable Devices.
- PyUSB transport handles interface protocols 00/01 with CBI and 50 with bulk-only transport (`pmca/usb/driver/generic/libusb.py:26-36`). W300's actual descriptor must determine the choice.
- Service-mode switching explicitly requires `GenericUsbDriver`; the native Windows MSC wrapper cannot supply the vendor control request (`pmca/commands/usb.py:661-692`).
- `requirements.txt` includes PyUSB, pycryptodomex, Windows pywin32/comtypes, asn1crypto, axmlparserpy, certifi, pycparser, pyinstaller, pyyaml, tlslite-ng. The complete app has broader dependencies than a legacy protocol adapter. A legacy adapter needs Python plus PyUSB and a functioning USB backend; hashlib and struct are standard-library modules.
- Source audit does not itself prove the root agent's local environment startup. Consult the separate environment checks for that result.

## Primary evidence: a legacy protocol outside the normal PMCA path

The maintainer's [A330 issue #282](https://github.com/ma1co/Sony-PMCA-RE/issues/282) explicitly identifies an older generation and refers to methods working on DSC cameras of that era. This is a reason to inspect the legacy route, not a W300 compatibility guarantee.

Read the full issue with `https://api.github.com/repos/ma1co/Sony-PMCA-RE/issues/282/comments?per_page=100`; the default first page stops before the eventual success.

Two original maintainer attachments were downloaded and extracted for inspection only:

| Local relative path | Source | SHA-256 |
|---|---|---|
| `build/w300/downloads/legacy-pmca/a330-7953397.zip` | [Flash dump attachment](https://github.com/ma1co/Sony-PMCA-RE/files/7953397/a330.zip) | `86c286f8fd315a464d19b3fbf411181b466515a594e6f7de24b8e249fa9ce1bb` |
| `build/w300/downloads/legacy-pmca/a330-7998362.zip` | [Final language attachment](https://github.com/ma1co/Sony-PMCA-RE/files/7998362/a330.zip) | `cab4f3072f077c237892a9e274473fb4423a70c11e6a15eefa4a540fa6ae5ff0` |

The extracted final script `a330-7998362/a330.py` has SHA-256 `1e257cb6b6faffc4c3f0a0111ca168469478423b2c9845c8b73b09dce56f128e`.

**Do not run or import these originals against W300.** They execute device operations at module scope, select the first Sony device without checking its model, and hard-code another model's addresses. The final script contains a Python 2-style bytes/string concatenation in `saveSeus` and obsolete array `.tostring()` calls.

### Verified code facts from the final legacy script

- Lines 44-53: bulk-only SCSI Inquiry. This particular script does not auto-select CBI.
- Lines 55-56: service entry uses bmRequestType 43, request f0, value f000, index f000, payload ff repeated eight times. It differs from modern PMCA's request.
- Lines 58-67: packets are big-endian, with a 16-byte header; the length field represents total words minus one; output is padded to 0x120 bytes. Response byte 6 must be 01; payload starts at offset 0x10. A response's declared length may require a further read.
- Lines 69-74: challenge request `(cmd=1, subcmd=0, arg=1)`; take 16-byte challenge; XOR with the 16-byte ASCII key `USBSENSERKEYOPEN`; MD5 the result; submit `(cmd=1, subcmd=0, arg=2)`.
- Lines 79-80: byte read `readSeus(page, offset)` sends `(cmd=20, subcmd=10, arg=1)` and payload `00 + page_BE16 + offset_8`; the value is returned in payload byte 4. This is a concrete legacy read primitive, qualified by A330 responses only.
- Lines 82-86: byte write is subcommand 11; explicit persistence is subcommand 15. These are source facts, not an approved W300 write route.
- Lines 88-89: `enableDump` sends `(cmd=20, subcmd=f1, arg=1)`. Its name is not evidence that it is a passive read; it changes a service/terminal state.
- Lines 104-110: A330-specific destination page 6f, offset 0c, CEE5 value 33; write-enable page80/offset01 and save page60. **None of these addresses or values may be transferred to W300 by analogy.**

The flash-dump variant reads physical addresses 9f000000 through 9fffffff in 0x100-byte chunks. That range is A330-specific and must not be used as an assumed W300 flash map.

### An actual offline check against a published device transcript

Published [A330 authentication transcript](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1016376958): challenge `7ef0f51f86e7bca5309b826db1b7bc8f`, returned response `172f1588efa2c0435e493fb5f7d0b052`.

Recomputed with .NET `MD5.HashData(challenge XOR ASCII key)` on this computer: exact match. Challenge length=16 and key length=16. This verifies the extracted algorithm against a real upstream A330 transcript. It does not verify a W300 handshake.

### Persistence evidence and its limit

Earlier A330 scripts changed the returned destination byte but it reverted after reboot. The issue records these failed attempts. The final attachment is linked in [comment 1029420472](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1029420472); the owner reports success in [comment 1029441051](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1029441051) and lists languages in later comments. This is evidence that a per-model legacy adapter can work, and that readback immediately after writing is insufficient proof of persistence. It is not evidence of W300 destination addresses or backup coverage.

## Other searched evidence and interpretation

- GitHub issue search for W300, including comments, returned zero results. This does not prove impossibility.
- [DSC-T77 #464](https://github.com/ma1co/Sony-PMCA-RE/issues/464) reports modern GetModelInfo failing with sense 02/ff/ff. [DSC-TX1 #584](https://github.com/ma1co/Sony-PMCA-RE/issues/584) reports illegal-command sense 05/20/00. Both have no remedy in their comments. These strengthen the protocol-generation concern, without establishing W300 behavior.
- [DSC-TX5 #243](https://github.com/ma1co/Sony-PMCA-RE/issues/243#issuecomment-855197270) and [DSC-TX7 #176](https://github.com/ma1co/Sony-PMCA-RE/issues/176#issuecomment-587764788) show that updater support and firmware dumping can exist while language tweaks do not.
- [W170 and other old models #492](https://github.com/ma1co/Sony-PMCA-RE/issues/492) is a request without technical resolution. [W170 #695](https://github.com/ma1co/Sony-PMCA-RE/issues/695) likewise supplies no implementation.
- [TX300V #726](https://github.com/ma1co/Sony-PMCA-RE/issues/726) reports a later model's manual 35-property language operation. It cannot validate W300 and includes a service-file-transfer truncation report, which reinforces the need to verify complete backups.
- The [OpenMemories device table](https://openmemories.readthedocs.io/devices.html) is generated from `ma1co/fwtool.py/devices.yml`; its inline JavaScript emits a serviceshell checkmark unconditionally for every entry. The visual checkmark is not an individual hardware-test record. W300 is absent from the inspected current model data.

## Smallest useful adapter work

1. A no-write legacy packet encoder/parser and transcript-based authentication check would remove the modern-protocol assumption and obsolete Python calls. It must not import the original script.
2. Keep OS inventory, standard Inquiry, service-entry/authentication, and SEUS register reads as separate operations. The latter stages perform active device communication even if they issue no destination writes.
3. Require exact device selection, descriptor-based transport choice, response-size/status checks and captured raw exchanges. Stop on a mismatched or ambiguous target or malformed response. Do not brute-force commands or try guessed memory ranges.
4. Only a W300-specific source or validated W300 exchange can promote the known legacy primitives into a language-change implementation. The missing engineering input is the W300 destination mapping and persistence behavior, not another general-purpose simulator.
