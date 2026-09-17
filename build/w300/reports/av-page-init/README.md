# G3 reference: initialization of page 0x61 / segment 0x0E

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

This is a bounded static continuation of `../av-receiver/README.md`. It establishes where this **G3** table entry obtains its live pointer and distinguishes copying bytes into the live bank from the separate persistence request. It does not qualify a W300 command, identify a W300 language byte, or supply a device operation.

## Source and reproduction

The input is the retained `evidence/extracted_g3/sections/09_av.bin`, SHA-256 `f2554be5181f5765623b0771e6aef6ff99c8483980a1192c39db85c744bda4fb`. Its relationship to the retained DSC-G3 updater, verified decryption, ARM/Thumb mapping, scatter initialization and explicit DSC-G3 model string is documented in `../av-receiver/`. That prior work establishes code VA = file offset + `0x20100000`; the initialized data table at runtime `0x203043FC` comes from the scatter-loaded bytes at file `0x1E43FC`, not from a flat subtraction of the code base.

From the repository root, the offline reproduction is:

```powershell
& .\build\w300\venv\Scripts\python.exe .\build\w300\reports\av-page-init\inspect_page_init.py
```

The script reads the firmware as bytes, verifies its hash, the selected table record, literal addresses, both inline branch tables and the assignment instructions. It regenerates `page-init.asm.txt` and `evidence.json`. It does not import or execute firmware, access USB, or produce a packet. It uses the already isolated Capstone 5.0.6 under `build/w300/re-tools/site`. The completed run reported `ok: true`, 12 bounded code ranges and an unknown numeric runtime bank base. Inline jump tables are data in `evidence.json` and are excluded from instruction decoding.

## Live pointer initialization

The selected initial record, at file `0x1E4AB4`, is the 20-byte structure decoded as `<HBBIIIHH>`:

| Field | Initial value |
| --- | --- |
| page key | `0x61` |
| segment | `0x0E` |
| type | `3` |
| live pointer, record +4 | `0` |
| record +8 | `0x1A00` |
| default pointer slot, record +0xC | `0x202BB2E0` |
| length, record +0x10 | `256` |
| trailing halfword | `0` |

A direct Thumb BL at file `0x4216` targets the initializer at `0xEAB0`. The relevant portion of that initializer has the following explicit data flow:

1. File `0xEAB2` loads descriptor address `D = 0x200FD880`; `0xEAB8` forms mask `M = 0x80000000`. This descriptor is outside this AV image's mapped bytes. Its pointer values cannot be read from the retained image.
2. File `0xEAEE..0xEB06` takes `primary = u32(D + 0x10)` and tests `u32((primary + 0xE0) | M) == 0xAAAAAAAA`. When the comparison succeeds, it stores `primary | M` at runtime `0x20303FCC`; otherwise it stores `u32(D + 0x28) | M` there. This trace does not show a second marker check on the fallback. The two preceding branches similarly initialize adjacent slots from other descriptor offsets, but they are not the slot selected by this record.
3. The loop uses 20-byte records from `0x203043FC`, selects type 3, then selects the `0x60` page group. The inline byte table at file `0xEB48` sends low page nibble `1` to `0xEC72`.
4. The byte table at file `0xEC80` sends segment `0x0E` to `0xED34`. Those tables and their computed destinations are asserted by the reproduction script.
5. File `0xED34..0xED3C` loads the first bank pointer from `0x20303FCC`, adds `0x0D << 9` (`0x1A00`), and stores the result in record +4.

The proven expression is therefore:

```text
page61_segment0E.live_pointer = selected_bank + 0x1A00
```

The earlier receiver trace proves that its generic operation 1 returns data from this pointer plus the low address byte, while operations 2/3 copy supplied data to that location, subject to the described bounds check. Consequently, for this record the immediate destination of such a copy would be `selected_bank + 0x1A00 + address_low`. This is a live-memory expression, **not a flash offset, file offset, or W300 address**. The numeric selected bank and its physical backing are not established here.

## Initialization defaults do not identify language or calibration

After filling the table, file `0xED9E..0xEDAE` tests the first byte of this selected bank. A zero value or a value greater than or equal to `0x23` causes a call to the local control function at `0xE658` with arguments `0xF001, 0x60`.

The `0xF001` branch at file `0xE704..0xE73A` iterates type-3 entries in the requested page group and copies their default data into their live pointers. The `0xF002` branch at `0xE6BE..0xE702` performs the corresponding copy for a particular page/segment pair. Both obtain the source by dereferencing record +0xC, the destination from record +4 and the length from record +0x10; both call the copy routine already independently decoded at `0x20257D98` in the preceding receiver report.

For the selected record, the word at `0x202BB2E0` is `0x202BB1E0`, pointing to 256 bytes present in the AV image. The script confirms that pointer and range without exporting or interpreting the default contents. These branches are mutations of live bank data; they are not a demonstrated flash-save primitive.

The table and initialization code do not name the contents of this page as language, destination, user preferences or calibration. Having a built-in default and a writable live pointer does not distinguish those purposes. **This analysis cannot classify page 0x61 / segment 0x0E as safe user settings or exclude calibration.**

## Separate persistence request and its limit

The generic receiver has a distinct path for operations 4/5, at file `0x225E4..0x22624`. Both construct a request for IPC channel `0x1002`. Operation 4 sets the first request halfword to `1`; operation 5 sets it to `3`. Both put the transaction identifier at +2 and the body byte at +4 into request halfword +4. These are distinct from operations 2/3, which copy data into the live bank.

The Linux endpoint is examined independently in `linux-persistence/FINDINGS.md`, with symbol, relocation and code evidence. It establishes the following internal mapping in the retained G3 libraries:

| AV generic operation | IPC command | Linux method |
| --- | --- | --- |
| 4 | 1 | `CommonMethod::flush` |
| No equivalent claimed here | 2 | `CommonMethod::refresh` |
| 5 | 3 | `CommonMethod::erase` |

The endpoint maps request selector 1 to category 7 (`/boot/backup/Ausr.bin`), 2 to category 6 (`/boot/factory/Asys.bin`), and 3 to category 5 (`/boot/factory/Areg.bin`); selector 0 iterates all three. The separate endpoint analysis follows the write path, including the erase path's zero-filled data. **Operation 5 is an erase request in this G3 implementation, not an alternative save or a read.**

`flush` is conditional: `BasicMethod::flush` tests `isDirty` before invoking the file writer. This report does not prove that a preceding direct AV copy meets that condition. `CommonMethod::flush` also clears shadow byte `0xD0` for category 6 before calling the generic flush method. Thus even the separate flush path must not be characterized as an unconditional byte-preserving commit primitive.

The AV callback at file `0xE242` treats response halfword +6 equal to zero as status 1 and a nonzero value as status `0x80`, preserves the transaction identifier and queues the response. This static code identifies the expected internal completion mapping; no actual device response or successful persistence was observed.

The subsequent [bank-map analysis](../g3-bank-map/README.md) resolves the G3 bank-to-file link through constructor tables: page 0x61 / segment 0x0E belongs to category-5 Areg/Areg2. Continue with field semantics, affected-data recovery and the corresponding W300 implementation.

## Consequence for the W300 work

The new result replaces an unknown live pointer with a reproducible initialization expression and proves that the G3 reference has separate copy, flush and erase paths. It is not evidence that those byte fields, memory layout, IPC implementation, file categories or control operations exist unchanged in DSC-W300. No W300-specific firmware, approved Auto-Adj implementation or W300 communication trace was introduced by this analysis.

The remaining prerequisites for any safe W300 application are still the W300-specific host-to-service mapping, the exact page contents and language/destination semantics, a qualified preservation/restore mechanism and, if this architecture applies at all, the correct bank persistence mapping. This report supplies no device command and authorizes no write.
