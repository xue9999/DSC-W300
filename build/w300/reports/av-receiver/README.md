# Retained G3 AV receiver: concrete segmented-address handler

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

## Result

The retained **G3** updater contains an AV receiver implementation, not only Linux forwarding wrappers. Its `09_av.bin` contains an actual dispatcher and a handler that takes an **8-bit page key plus a 16-bit segmented address**, with distinct read and write operations. This supersedes the earlier bounded Linux-only result **for G3**: the 16-bit field implementation is now located. Qualify the meaning of the W300 service manual's Block/Page/Address fields, W300 transport/authentication, W300 destination values, persistence or original-board eligibility through separate target-model evidence.

No camera command, firmware execution, firmware-library import, emulator, payload generator or device adapter was used. All new outputs are in this directory. `sources/` and `evidence/` were read only.

## Provenance and identification

The retained input is `sources/DSCG3V2.exe`, SHA-256 `a9698c7b3822f23d71de84ba5389453b847f6de19ab293a55ebe016490fd94d9`. As documented by `evidence/g3_acquisition.md`, this is an imported input with historical provenance limitations, not a newly verified delivery from Sony.

`inspect_av.py` checked the EXE hash, exact identity of its LHA payload with `sources/D-G3V2.dat`, manifest HMAC/checksum, and the HMACs and freshly decrypted bytes of six selected sections against their preserved extracted files. HMAC here proves the container relationship, not manufacturer authenticity. Existing safe parser code was reused; the executable and firmware bytes were never run.

| Section | Observed identity and scope |
| --- | --- |
| `00_defhd.dat` | Container model text `08210030`, version `0002`. |
| `09_av.bin` | 2,061,054 bytes; SHA-256 `f2554be5181f5765623b0771e6aef6ff99c8483980a1192c39db85c744bda4fb`. ARM exception vectors and service/IPC receiver code. Literal `DSC-G3` at file offset `0x1C7EE8`. This is the selected candidate. |
| `03_av_udtr.bin` | Separate 2,145,694-byte AV updater variant with ARM vectors and Senser/IPCM strings; not substituted for the normal AV image. |
| `08_sa.bin` | Header begins `SA2U_APP3.08`; the service strings searched were absent. No receiver interpretation claimed. |
| `19_omgPrg00.bin` | Explicit Renesas HI7700/4 and Interpeak/ITRON strings; separate image family, not treated as the ARM AV receiver. |
| `20_omgPrg01.bin` | Separate OMG section; no receiver interpretation claimed. |

Exact `W300` and `DSC-W300` searches in `09_av.bin` returned no ASCII, UTF-16LE or UTF-16BE occurrences. Exact `DSC-G3` is present in ASCII. Short `G3` also occurs in instruction/data bytes and is not used as model evidence. Absence of a W300 name does not prove absence of shared code.

## Address mapping established before interpreting references

The normal AV image uses base `0x20100000` for the code examined here. Three independent byte relationships support it:

- The first ARM vector loads its target from file `+0x20`, whose value is `0x2010003C`; file `+0x3C` begins the reset sequence.
- The literal at file `+0xE5B0` is `0x20262078`, exactly addressing the embedded `tsk_senser` text at file `+0x162078`. The callback literal at `+0xE58C` similarly points to Thumb function `0x2010E27D`.
- The scatter-initialization loop at file `+0x120` locates its table at `+0x1E3850`. That table references the observed copy/zero routines `0x20100158` and `0x20100180`. Its first copy maps source `0x202E3A78` to destination `0x20303A78` for `0x1365C` bytes.

Consequently, the receiver's initialized table at runtime VA `0x203043FC` corresponds to file `+0x1E43FC`; treating that runtime address as a simple code-base offset would be wrong. A single reference row was inspected: page key `0x61`, segment `0x0E`, type 3, length 256 at file `+0x1E4AB4`. Its initial data pointer is **zero**. This proves a G3 table structure and a required runtime initialization, not an available calibration value or W300 address. No page contents or language values were extracted or mapped.

## End-to-end relationship and the two different buffers

There are two objects which must not be confused:

- **I**: a 20-byte IPC control/request structure exchanged by Linux through `/dev/ipcm`.
- **P**: the AV shared-memory body, starting with the four bytes obtained by Linux `AdjustControlFunc` through `Serialize(SenserIfReceive, ..., 4)`, followed by the remainder of the received body. The page and address fields below are offsets in **P**, not offsets in I and not a newly qualified host-USB packet format.

The chain is supported by these exact routines:

1. In `libsencore.so`, `AdjustControlFunc` obtains the four-byte header; when plugin creation returns null, the high nibble of its first byte selects `AdjustCommunication`. Header byte `0x11` selects table entry 1 and wrapper ELF VA `0xE894` (previous report `../fallback11/`).
2. Wrapper `0xE894` builds I: `I[0]=1`, `I[1]=packet[0xB]`, `I16[2]=packet16[6]`, `I32[4]=packet32[0]`, `I16[8]=packet16[4]`, `I[0xC]=header[0]`, `I16[0xE]=header16[2]`; other bytes begin zero. Thus `0x11` is a selector value in this G3 path, not a discovered W300 block mapping.
3. Linux helper `0xE104` opens `/dev/ipcm`; the actual ioctl argument at ELF VA `0x129A0` is the three-word sequence `(0, 1, 0x1001)`. Helper `0xDD84` writes and reads 20 bytes. The returned shared-memory address is mapped through `/dev/kmem`. Already received body bytes are copied to that buffer; a `MemoryData` object receives the remaining body using `SenserIfRcvPhys`. The GOT symbols for header input, received-byte count, body input and response output are resolved in `linux-body-bridge-evidence.json`.
4. The AV task at file `+0xE2BA` registers channel `0x1001`, callback `+0xE27C`, a destination structure, and length `0x14`. Its callback converts I to a 16-byte internal task message: `M[0]=1`, `M[4]=I[0]`, `M[1]=I[1]`, `M16[2]=I16[2]`, and for `I[0]==1`, `M16[6]=I16[8]`, `M32[8]=I32[4]`. This explicitly connects the Linux 20-byte structure to the receiving task.
5. The task allocates/returns the body buffer and records the function category from M. After the body is filled, Linux `AVCommunicationCommand::DoExecute` at ELF VA `0xF014` submits a subsequent control structure with operation 4. The AV task's operation-4 branch at file `+0xE39A` obtains the saved buffer and routes category `0x40` to file `+0x221E0`; category `0x30` takes a different branch.
6. Dispatcher `+0x221E0` reads `P16[2]`. Selected special operations have separate paths. Its general low-command branch calls `+0x225B4`, which contains the page/address access below. Larger commands additionally distinguish `P[0]`; selector `0x11` can route to `+0x6B6E8`, whose semantics were not expanded here. Therefore selecting `0x11` alone does not make every command a read.

The Senser source-name string is also tied to actual code: Thumb `ADR` at file `+0x57780` computes the exact address of `src\\senser\\sys_senser.c` at `+0x578CC`. That nearby routine handles a different dispatch branch; the reference corroborates the service-code area and is not the sole basis for identifying the page handler.

## Verified G3 page/address semantics and limits

All offsets below refer to **P**, the AV shared body. Halfwords are loaded by little-endian ARM instructions; this does not by itself define every outer host transport field.

| Field | Source instructions and observed use |
| --- | --- |
| Operation | `P16[2]`; `+0x225C6`, `+0x22676`. Operation 1 enters the read branch; operations 2 and 3 enter a data-copy write branch for table types 2/3. Operations 4/5 and larger commands follow other paths. |
| Length | `P16[6]`; checked against remaining table capacity in read/write branches. |
| Page key | `P[9]`; loaded at `+0x225CC`. Alias helper `+0x21E5C` maps keys `0x10→0x56` and `0x11→0x66`; other keys pass through. The general path requires the resulting key in `0x40..0x7F`. |
| 16-bit segmented address | `P16[0xA]`; loaded at `+0x225D2`. Its high byte selects a table segment (`+0x22642–0x22648`); its low byte is the offset within that segment (`+0x226E6–0x226EC`). The lookup matches both page key and segment. |
| Write data | Starts at `P+0xC`; operations 2/3 copy the requested length to the selected runtime data pointer plus the low-byte offset (`+0x226AE–0x226C2`). This is a real mutation path in G3. |
| Read data | Operation 1 reads a byte at the selected runtime pointer plus low offset (`+0x22702–0x22706`), then returns that pointer plus offset and the requested length (`+0x2270C–0x2271E`). |

`+0x21E10` computes capacity by summing the matched page's consecutive segment lengths starting at the address high byte. The direct read/write branch requires `low_byte(address) + length <= computed_capacity`; failure selects status `0x81`. Missing/unsupported page/type paths select `0x80`. These are internal G3 statuses, not promised responses from W300 or a host API.

The copy interpretation was checked against the actual callee, not just an assumed calling convention. `BLX` at file `+0x226C2` targets ARM VA `0x20257D98`, file `+0x157D98`. Its code through final `BX LR` at `+0x157EB4` loads bytes/words from `r1` and stores them through `r0`, with `r2` controlling length. This includes the byte alignment path (`+0x157DA8/+0x157DB8`), aligned multiword path (`+0x157E58/+0x157E5C`) and tail-byte path (`+0x157E9C/+0x157EA8`). At this call site, `r1=P+0xC` and `r0=runtime_pointer+offset`; therefore the examined operation-2/3 path does copy supplied data into the selected memory. The complete bounded callee and byte assertions are retained with the receiver analysis.

An earlier transaction-allocation branch also checks its requested-size field against `0x10C`. That field comes from I; this check does not establish a valid host buffer length. Table type 4 has a separate handler at `+0x2279C`, outside the qualified direct type-2/3 interpretation. The initial table contains null data pointers, so apparently valid field values do not by themselves establish that a runtime read will work.

The read branch changes response/transaction bookkeeping and calls a reporting function at `+0x96E44`. Its complete side effects were not audited. This report establishes the direction of the direct data access, not a globally side-effect-free service session. No language/destination meaning or persistence was recovered.

## Reproduction and evidence

From the repository root, using the existing isolated environment:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\av-receiver\inspect_av.py'
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\av-receiver\decode_receiver.py'
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\av-receiver\linux_body_bridge.py'
```

All three ran successfully. `inventory.json` retains the selected container metadata, hashes, model searches and service strings. `receiver-evidence.json` records asserted address relationships, the channel match, initialized-table mapping, the one reference row and the direct data-copy callee. `receiver.asm.txt` contains eleven explicitly bounded code ranges, with file offsets and derived G3 virtual addresses. The Linux bridge output covers three named functions, stops at verified returns before their literal pools, and verifies all 137 PLT-to-GOT relocation targets. The bootstrap-vector output likewise stops before its literal pools.

The exact remaining qualification gap is now narrower: a W300-specific receiver/trace or actual SeusEX implementation must show that its service fields and entry/authentication match this G3 path. The G3 implementation removes an uncertainty about the existence of a contemporary page8/address16 design; it does not supply that cross-model proof or the desired language operation.
