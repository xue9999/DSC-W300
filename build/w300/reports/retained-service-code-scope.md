# Retained G3 service libraries: bounded relevance to W300

Editorial revision 4; underlying measurements and captured results retain their recorded scope.

## Result and scope

The retained libraries contain real G3 service, updater and backup symbols. This bounded static inventory found **no explicit W300 model reference, legacy `USBSENSERKEYOPEN` literal, or identified bridge from SEUS Block/Page/Address to a USB request**. It therefore supplies no qualified W300 service-read operation and does not remove the gap documented in `w300-seus-addressing.md`.

This was an inventory of eleven named service libraries, not a decompilation or exhaustive proof that no related logic could exist. Absence of a string cannot establish absence of compiled functionality. The libraries were never loaded, imported or executed; original `sources/` and `evidence/` files were not changed. No dependency was installed and no camera communication took place.

## Historical material checked first

Searched `ANALYSIS_LOG.md`, current `docs/`, `tools/`, `sources/original-research-report.md`, retained textual evidence, and available build reports for the exact library names, SEUS, legacy authentication key, disassembly and tool references. No retained disassembly resolving the old Block/Page/Address translation was located.

`tools/w300_service_tool.py:91–96` attributes a SHA-1 length behavior to `libsencore.so`, but the file's opening contract explicitly identifies the tool as an offline simulator with an unvalidated W300 map. That statement is not a model-compatibility result or a substitute for a concrete legacy read routine. `docs/g3/README.md` and `evidence/g3_acquisition.md` also limit these retained inputs to G3 analysis and record provenance limits; an extracted library is not a W300 firmware acquisition.

## Exact inventory

All files are under `evidence/extracted_g3/archives_unpacked/lib/lib/`; all parsed as little-endian ELF32, machine 40 (ARM). The inventory covered `libsencore.so`, `libsenupdate.so`, `libadj30.so`, `libadj31.so`, `libadj32.so`, `libadj33.so`, `libadj36.so`, `libadj3E.so`, `libBackupCore.so`, `libBackupTable.so`, and `libAppBackupApi.so`.

For each file, `retained-service-inventory.json` records size, SHA-256, symbol table entries, relevant ASCII strings, and offsets of exact `W300`, `DSC-W300`, and `USBSENSERKEYOPEN` searches in ASCII, UTF-16LE and UTF-16BE. All those literal searches returned no matches. No identified model-name table containing W300 emerged from the inspected names/strings.

Concrete nearby symbols are listed below as locators only. File offsets refer to the hash-identified bytes in the JSON; they are not camera memory addresses or commands.

| Retained G3 file | Exact symbol | File offset; size | What this establishes |
| --- | --- | --- | --- |
| `libsencore.so` | `_Z5ParsePK12SenserPacket` | `0xce18`; 392 bytes | An actual Senser packet parser is present. Trace its payload parsing to qualify the old SEUS tuple mapping. |
| `libsencore.so` | `_Z17AdjustControlFuncPK12SenserPacket` | `0xd7f8`; 180 bytes | A G3 adjustment dispatch routine exists. No W300 qualification accompanies it. |
| `libsencore.so` | `_Z15ProductInfoFuncPK12SenserPacket` | `0xd8ac`; 444 bytes | A product-information handler exists; no W300 model literal was found. |
| `libsenupdate.so` | `ud_ReadModelInfoFile` | `0x1cb0`; 416 bytes | Model-information file handling exists. It is not an embedded W300 support table or a menu-language handler. |
| `libadj33.so` | `command0001` | `0x2bd4`; 212 bytes | A numerically named handler exists; the same library imports `_ZN12CommonMethod4readEjPv`. Continue with the call-graph and payload analysis in `retained-dispatch-analysis.md`. |
| `libadj36.so` | `command0001` | `0xcec`; 248 bytes | Another adjustment handler exists; this library imports `Bkup_pread`. Imports alone do not establish which request invokes them. |
| `libAppBackupApi.so` | `Bkup_pread` | `0x3b78`; 112 bytes | A G3 backup-read API implementation is retained. No old block/page/address signature is exposed by this symbol name. |
| `libBackupCore.so` | `_ZN12CommonMethod4readEjPv` | `0x9740`; 132 bytes | A backup read method with an unsigned integer argument and destination pointer exists. The integer's meaning for W300 is not established. |

`libBackupCore.so` also contains paths `/boot/backup/Husr.bin`, `/boot/backup/Ausr.bin`, `/boot/backup/Husr2.bak`, and `/boot/backup/Ausr2.bak` at file offsets `0xd668`, `0xd6b0`, `0xd718`, and `0xd760`. These are evidence about the retained G3 implementation. They must not be adopted as W300 backup locations or a restoration procedure.

## Reproduction and follow-up

The small standard-library-only inventory helper is `build/w300/reports/retained_service_inventory.py`. It reads ELF tables and byte strings; it does not use `ctypes`, import firmware modules or launch firmware code. Reproduce from the repository root with the already prepared environment:

```powershell
& 'build/w300/venv/Scripts/python.exe' 'build/w300/reports/retained_service_inventory.py'
```

Derived output is `retained-service-inventory.json`; the captured human-readable run output is `retained-service-symbol-summary.txt`. Existing original input hashes are preserved, not replaced by this inventory.

The inventory established concrete G3 routine locations for deeper inspection. The subsequent [dispatch analysis](retained-dispatch-analysis.md) and [AV receiver analysis](av-receiver/README.md) develop those locations into payload and handler evidence; consult them before repeating symbol searches. Acquire a W300-capable SeusEX implementation, verified W300 transaction, or W300 proprietary firmware handler and compare its serialization and entry sequence with these resolved reference layers. Follow the alternative acquisition and analysis routes in the [execution plan](../../../docs/w300/EXECUTION_PLAN.md) while that target-model evidence is being obtained. Shared architecture and library names remain comparison leads rather than W300 command specifications.
