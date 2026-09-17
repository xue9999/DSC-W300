# G3 Linux receiver for AV backup IPC channel 0x1002

Editorial revision 4; underlying measurements and captured results retain their recorded scope.

## Conclusion

The retained G3 Linux `libAppBackupApi.so` contains an exact receiver for channel `0x1002`. Its command table maps command **1 to flush**, **2 to refresh**, and **3 to erase**. Accordingly, the AV adjustment operations identified by the parent audit as sending commands 1 and 3 are a file-backed flush request and an erase request respectively. Operation 5 must not be described as reload.

This establishes static G3 code behavior only. Qualify a W300 transport, language address, supported transaction or hardware persistence guarantee through separate target-model evidence. It also does not yet identify the AV page 0x61/segment 0x0E RAM bank as Ausr.

## Inputs and reproduction

Immutable inputs, verified against `retained-service-inventory.json` on every decoder run:

- `evidence/extracted_g3/archives_unpacked/lib/lib/libAppBackupApi.so`, SHA-256 `9ce75b37757afb5ec3934f6091992185942cc7d2a52ff98348f14b713534a699`.
- `evidence/extracted_g3/archives_unpacked/lib/lib/libBackupCore.so`, SHA-256 `56aa2595c4747b6aadc1c0c3bb7a438b15086951121024a8649254cdec61fd4b`.

Run only the static-data helpers from the repository root:

```powershell
& build/w300/venv/Scripts/python.exe build/w300/reports/av-page-init/linux-persistence/decode.py
& build/w300/venv/Scripts/python.exe build/w300/reports/av-page-init/linux-persistence/tables.py
```

`decode.py` adapts the existing report decoder without changing it. It validates all 97 AppBackupApi and 144 BackupCore PLT stub GOT targets against ELF relocation slots. `tables.py` reads ELF data and relocations; it never loads a firmware shared library as code. Outputs are `linux-backup.asm.txt` and `linux-backup-tables.txt`. Addresses below are G3 ELF virtual addresses, not host addresses or W300 camera addresses. The decoder stops each selected routine with a trailing literal pool at its confirmed final unconditional return and renders the remaining words explicitly as `.word` data. It asserts complete code-byte coverage and the return instruction at every such boundary.

## Exact receiver and command mapping

1. `BackupWatcher::start` (`libAppBackupApi.so`, 0x48B4) resolves the string `/dev/ipcm` at 0x516C, opens it with argument 2, stores the file descriptor at `this+0x14`, and calls `ioctl(fd, 0x400C4901, &registration)` with three 32-bit fields `{0, 1, 0x1002}`. The channel literal is at 0x4960.
2. `BackupWatcher::run` (0x4F68) polls that descriptor, reads 0x14 bytes at 0x4FF8, then calls `BackupWatcher::publishEvent` at 0x5018.
3. `publishEvent` (0x4D8C) reads command halfword +0, sequence halfword +2 and category halfword +4. The table at 0x51E4 contains `(1,5), (2,6), (3,7)`, mapping AV command to internal event.
4. `executeEvent` (0x4C54) dispatches internal event 5 to `CommonMethod::flush` (call 0x4D00), event 6 to `CommonMethod::refresh` (0x4D10), and event 7 to `CommonMethod::erase` (0x4D20).
5. `postAVCommand` (0x49A4) copies the first 8 response bytes into its local buffer and writes a 20-byte message to the same IPC descriptor. The all-category callback records response status in halfword +6. Thus the structure and size match the parent's observed AV sender/receiver pattern, in addition to the exact channel match.

## Category-to-file mapping

`publishEvent` uses the table at 0x51B4. Its three entries are:

| AV category selector | CommonMethod category | Main file | Spare file |
|---:|---:|---|---|
| 1 | 7 | `/boot/backup/Ausr.bin` | `/boot/backup/Ausr2.bak` |
| 2 | 6 | `/boot/factory/Asys.bin` | `/boot/factory/Asys2.bak` |
| 3 | 5 | `/boot/factory/Areg.bin` | `/boot/factory/Areg2.bak` |

Selector 0 follows the loop at 0x4EAC through all three mapped categories; it is not an empty or no-op selector. Main file names come from `FileAccesser::FILE_NAME` at 0x165E0, and spare names from `FileAccesserMeasures2BattOff::SPARE_FILE_NAME` at 0x16644. `getFileName` (0x8414) checks the category bound then indexes the main array by category. The tables report includes ELF relative relocations and exact strings.

The AV category selector is a separate command parameter. It is not the adjustment page number or a demonstrated translation of page 0x61 to a file.

## Flush and erase are backed by file-writing code

- `CommonMethod::flush` (0x99EC) gets the selected category's full size, then tail-calls `BasicMethod::flush(category, 0, size)`. For category 6 it also clears a byte at offset 0xD0 in the selected shadow before the flush call.
- `BasicMethod::flush` (0x9088) validates arguments, obtains a shadow address, locks it, checks `isDirty`, and when that check equals 1 invokes the file accessor's write virtual method at 0x9160. It clears dirty state after a successful write and releases the lock.
- `CommonMethod::erase` (0x9A9C) similarly obtains the full category size and tail-calls `BasicMethod::erase(category, 0, size)`.
- `BasicMethod::erase` (0x9308) zeroes a 0x400-byte temporary buffer and iterates over the selected category, calling the file accessor's erase virtual method with zero data. This is zero-writing logic, not a refresh of RAM from the stored file.
- The file accessor write (0x8774) and erase (0x8910) methods accept categories in mask 0xE7 and dispatch to `writeUser` (0x895C). The vtable relocations establish these targets, using a vptr address point 8 bytes after the vtable symbol.
- `writeUser` chooses main and/or spare paths according to the current file completion marker and calls `writeSafely` (0x8AA8).
- `writeSafely` calls `backupFileWrite` to clear a completion marker, write the body and then store marker 0xAAAAAAAA. `backupFileWrite` (0xACD0) calls the open, seek, write and close helpers on the selected file path.

These paths demonstrate intentional file-backed persistence and destructive file erasure in static code. They do not prove success on hardware, physical-media durability at a particular instant, safe interruption or restoration coverage.

## Bank identification remains unproven

The parent's AV initialization trace obtains its first bank through descriptor 0x200FD880 fields +0x10/+0x28 and a 0xAAAAAAAA test at bank+0xE0. The Linux routines traced here do not establish that this first bank is category 7/Ausr.

`ShadowTable::getShadowAddr` (0x6C20) indexes ELF address 0x16908. That is runtime BSS with no relocation. The size/spare arrays at 0x16458, 0x16478 and 0x16498 are zero in the retained ELF and have no relocations. `ShadowTable` constructor (0x6AB8) derives top/total from those arrays. The selected `ShadowAccesser` routines consume them and map shared memory, but the bounded trace did not locate the writer that connects these arrays to the AV descriptor. Matching completion-marker constants alone is insufficient to identify a bank.

This trace established receiver/operation/category semantics and isolated the initialization link as the next question. The subsequent [bank-map analysis](../../g3-bank-map/README.md) resolves that G3 link to category-5 Areg/Areg2 through constructor tables. Reuse that finding to frame the W300 field and persistence investigation in the [current execution plan](../../../../../docs/w300/EXECUTION_PLAN.md). No evidence input, project source, camera state or USB state was modified during the original trace.
