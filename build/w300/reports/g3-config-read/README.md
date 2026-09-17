# G3 configuration read path and field associations

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

This report isolates actual retained DSC-G3 configuration getters and five native data rows. It is **not a DSC-W300 map, USB reader, or language-change procedure**. No firmware was executed and no device was connected.

## Verified native getter

`PExtBackup.so::xs_backup_read` (VA `0x1E90`) accepts one integer argument, asks `Bkup_getDataSize` and `Bkup_getDataKind`, and selects the actual read operation. Kind 1 with at most four bytes calls `Bkup_read` at `0x22D0` and returns an XS integer. Larger kind-1 fields use `Bkup_pread` and return an array; kind 2 uses `Bkup_pread` and returns a string. Invalid argument count/type returns undefined. Negative size/kind lookup results return the error integer. `Bkup_read` itself ignores the status returned by its internal `Bkup_pread`, so a scalar zero alone is not sufficient evidence of a successful device read.

`libAppBackupApi.so::Bkup_pread` calls `CommonMethod::read`. In `libBackupCore.so`, that method checks the data ID, chooses bit-field or ordinary data read, and `readData` resolves category, offset and size from the table. `BasicMethod::read` copies from the shadow accessor through `memmove`; it does not directly read a flash file for each call. This audit has not turned those internal functions into a remotely callable service operation.

## Native field table

`libBackupTable.so::DataTable::getCategoryId` uses `id >> 24`; `getOffset` uses `(id >> 8) & 0xFFFF`. The internal lookup at `0x2204` binary-searches two arrays per category, with 20-byte rows. The descriptor table starts at `0x1E7E0`. Its pointers need ELF `R_ARM_ABS32` relocations, and its counts are initialized by `.ctors` function `0x2488` from the exported `HOST_*_NUM` constants. Reading the descriptor before applying relocations and constructor initialization incorrectly yields zero rows.

| Grammar property | Associated ID | Native array | Category | Offset | Size |
|---|---:|---|---:|---:|---:|
| `BkupID_Reg_cmn__DestinationID` | `0x00010400` | HOST_COM_REG | 0 | `0x104` | 1 |
| `BkupID_Reg_brewApp__regionData` | `0x00040000` | HOST_PROD_REG | 0 | `0x400` | 4 |
| `BkupID_Reg_brewApp__initLangData` | `0x00040400` | HOST_PROD_REG | 0 | `0x404` | 4 |
| `BkupID_Reg_brewApp__availLangData` | `0x00040800` | HOST_PROD_REG | 0 | `0x408` | 4 |
| `BkupID_Reg_brewApp__signalTypeData` | `0x00040C00` | HOST_PROD_REG | 0 | `0x40C` | 4 |

All five rows have bit size zero, bit mask zero and kind 1. The native file-category arrays associate category 0 with `/boot/factory/Hreg.bin` and `/boot/factory/Hreg2.bak`. These are G3 host configuration fields, distinct from the AV Areg bank mapped in `../g3-bank-map/`. The offsets are native category offsets; they are **not** W300 service addresses or an instruction to edit a file or flash location.

The property-to-ID associations are corroborated by the embedded grammar rather than inferred from names alone. `PExtBackupGrammar` at `0xD9DC` points to 132 symbol names and 3490 bytes of XS code. The code passes the exact hexadecimal literal strings above to `__xs__number.parse`, swaps the return value with the receiver, and installs the named property using opcode `0x7C`. The actual G3 runtime interpreter review confirms the getter, method call, swap and property-install semantics (see [the independent XS review](../g3-xs-entry/xs-review.md)). The internal implementation of `__xs__number.parse` has not been followed in this report; the exact numeric constants are therefore a strongly corroborated interpretation, not an independently executed grammar result. Native table IDs and row attributes themselves are direct binary facts.

## Application consumer and XML evidence

The independently framed `regionInfo.xsb` sets its four backup-ID properties from the matching `BkupID_*` names. At CODE offsets `0x5A2`, `0x5B0`, `0x5BE` and `0x5CC`, it invokes the `read` method for region, initial language, available languages and signal type, then invokes `makeRegionInfoFile` at `0x5DD`. This identifies an application-level consumer of the configuration fields, although the complete string-to-backup-ID wrapper and every branch have not been interpreted here.

The retained `RegionInfo_*.xml` files were read, parsed and checked against `evidence/artifact_manifest.json`. Their actual XML contains `lang`, `langGp` and `sigTyp` values. For example, `RegionInfo_JPN_1_NT.xml` contains `jpn`, `1`, `0`; the English variants contain `eng` with their own group and signal values. Names and XML values do not provide a W300 destination byte or authorize changing an entire region.

The language-constructor area pairs the literal `eng` with bytes `8A 01 00` and `jpn` with `48 00 00 80 00`. These adjacent bytes do not yet establish a value to write. First verify the constructor behavior, integer opcode semantics and use of the mask.

## Reproduction and limits

From the repository root:

```powershell
build/w300/venv/Scripts/python.exe -B build/w300/reports/g3-config-read/reproduce.py
```

This invokes static inspection, native decoding, relocation-aware data-table extraction, and grammar framing using the actual G3 runtime's remap table. It checks all firmware input hashes against the retained evidence manifest, the five exact literal/parse/property sequences, matching native rows and category-0 file paths. `verification.json` records the result and explicitly sets `w300_qualified: false`.

The helpers only regenerate files in this report directory. The original source and evidence files are unchanged. Inputs are the retained G3 `PExtBackup.so`, `libBackupTable.so`, `libAppBackupApi.so`, `libBackupCore.so`, `tinyhttp`, `regionInfo.xsb` and twelve XML files. Their acquisition/provenance limitation remains the one documented in `evidence/g3_acquisition.md`.

A W300 implementation still requires W300-specific field identification, a confirmed read transport for the original board, and a qualified preservation/recovery path. No available result here establishes that W300 uses these IDs, offsets, category files, language masks or XS application structure.
