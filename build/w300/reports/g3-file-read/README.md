# Path-based acquisition as an alternative to Auto-Adj

## Decision

The retained G3 firmware contains a real Senser file reader. It offers a concrete alternative acquisition route: obtain the W300's proprietary implementation from the owner's camera after separately qualifying service entry and transfer behavior. Finding the scarce Auto-Adj executable is therefore not the only possible way forward. This is a G3 static finding and a W300 engineering hypothesis, not a completed W300 acquisition or language conversion. The user has requested offline work without the camera for now.

## Source-backed read operation

`verify_file_read.py` reuses the existing manifest-pinned ARM ELF inspector. It never imports firmware as executable code or opens USB. The resulting `verification.json` and `file-read.asm.txt` preserve input hashes, checked instructions, resolved PLT targets and selected disassembly. The pinned PMCA source is compared byte-for-byte with commit `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0` before AST inspection.

| Layer | Retained evidence | Interpretation |
|---|---|---|
| Request | PMCA `SonySenserCamera`, pFunc `0xFF01`, command `2` | Four-byte command/filename-size header followed by Latin-1 path and NUL padding. Command 1 writes and command 3 deletes; they are separate paths. |
| Dispatch | G3 `libsencore.so`, `FileControl` at `0xED1C`; compare at `0xEDAC`, branch at `0xEDB0` | Command 2 selects `0xEF5C`, which installs callback `0xCFB4` through its PIC-relative pointer. |
| File open | Callback `0xD0C4–0xD0CC`, reader constructor `0xB3C0` | `ReadDeviceData(path, 0x1000, 0x8000)`; 32-KiB read buffer. |
| System calls | G3 `libpro00.so`, `DeviceIo::open` at `0xC2F4`, `read` at `0xC854` | Flags are forwarded to POSIX open; data comes from POSIX read. The ARM Linux flags mean O_RDONLY with O_SYNC, without creation or truncation. |
| Reported size | Reader vtable relocation `0x1B8CC`, getter `0x9D80`, `DeviceIo::size` at `0xC150` | Uses fstat-derived file size. This is not an unbounded read-to-EOF interface. |
| Response | `SendResponse` at `0x6994` | Checks stream health, sends the size, and transfers up to 1 MiB per segment. Zero reported size suppresses the body. |

`access(path, 0)` failure yields `0x82`; it does not distinguish every missing/inaccessible-file cause. Callback status 1 alone does not establish complete acquisition. The dispatcher exposes no directory-listing command.

The content read does not establish a state-free session: file access timestamps, diagnostic logging and service entry/exit may have effects. Do not use the general PMCA shell or its backend initialization as if they were an isolated file getter.

## Persistent-mode distinction

G3 `libadj30.so::StoreSenserMode` at `0x24B4` passes `/boot/sen/` and `/boot/sen/smode` to helper `0x20F4`. Its table at `0xC024` maps modes 1/2/3 to `US`/`UU`/`UD`. Recognized nonzero modes create the directory, open the marker with literal `0x1241` (O_WRONLY|O_CREAT|O_TRUNC|O_SYNC), write the selected string and sync. Zero/unmatched modes reach removal of the marker and directory, then sync; errors can leave partial state. `LoadSenserMode` at `0x2440` also maintains a mirror under `/var/.sen/.smode`, so its name does not imply a pure read.

`command000D` at `0x1E9C` is a mixed operation: selector 0 reads the mode; selector 1 with a second input byte invokes StoreSenserMode except for explicitly rejected mode 1. It must not become a generic probe. The inspected FileControl read branch does not call this mutator. This trace does not establish that ordinary PMCA authentication triggers it, or that W300 creates/restores the same marker. Keep ordinary authentication and persistent-mode setting separate. Neither reboot/disconnect nor deleting a marker is a proven restoration procedure.

## Bootstrap and transfer requirements

The G3 image contains a 31-byte regular `/version.txt`. It is a justified G3-derived candidate, but its existence on W300 is unknown. Do not start with `/proc/version`: virtual files can report zero stat size even though a direct read produces content, and this sender would omit the body. An empty response is not evidence that W300 lacks the protocol. W300's GPL configuration enables procfs and disables MTD; `/proc/mtd` is not a justified alternative.

Before implementing a camera-side trial, qualify W300 identity, entry, exit, authentication and side effects. A future receiver must enforce total size, per-read timeout and an overall deadline; abort on empty/no-progress reads; preserve every raw USB response; and validate sequence, declared size, actual bytes and segment transitions. Pinned PMCA `_readAll` has no empty-read exit, and `sendSenserPacket` discards an additional read after certain 512-byte multiples. The matching G3 device-side USB padding/ZLP behavior has not been fully resolved. These are adoption constraints, not hardware-observed W300 defects. Do not blindly remove padding reads or import another model's workaround.

The first justified later probe is a bounded command-2 read of the one reviewed regular-file path. Missing/inaccessible status stops that candidate; it does not justify broad path guessing, device-file reads, terminal activation or memory probes. If a regular-file transfer qualifies, review boot/mount evidence for a narrow list of software paths. Acquire actual W300 libraries and script containers, then validate their complete structure and repeat-read equality before analyzing them.

## How this could reach the language objective

Actual W300 libraries could expose the destination getter, language table, original-board gate and commit/restore implementation. Compare those with the known G3 host configuration and application consumers in `../g3-config-read/`. Do not write G3 field IDs or offsets to W300. A language-only operation is preferable if W300 actually exposes one; U2/CEE8 remain documented destination labels, not raw values.

Completion still requires persistent English on the original W300 board, preserved identity/calibration and ordinary operation, plus a demonstrated recovery path. No retained evidence yet establishes those outcomes. The supplied portable workbench remains unchanged and does not contain this service read.

## Reproduce

From the repository root:

```powershell
.\build\w300\venv\Scripts\python.exe -B build/w300/reports/g3-file-read/verify_file_read.py
```

The checks establish the quoted static anchors and source identity. They do not simulate or test a physical camera, establish all control-flow semantics automatically, or qualify the end-to-end USB transfer.
