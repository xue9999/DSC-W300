# W300 native parameter backing

Native CNR addresses on page `0x51` reach the selected category-6 Asys RAM
shadow. The link follows actual W300 descriptor loads, constructor stores and
AV row initialization. It does not establish the current camera's numeric
descriptor values or qualify a write.

Sources are the pinned `evidence/w300/av.bin` and actual W300
`evidence/w300/baseline_files/usr/lib/libBackupCore.so`. The library is
byte-identical to the retained G3 library, SHA-256
`56aa2595c4747b6aadc1c0c3bb7a438b15086951121024a8649254cdec61fd4b`.
The G3 method located the relevant code; the observations below use W300 bytes.
Library addresses are ELF virtual addresses; AV addresses are file offsets
unless explicitly marked VA.

## Linux constructor and category identity

ELF `.ctors` at `0x16050` contains `FFFFFFFF, 00006CCC, 00000000`.
Constructor `0x6CCC` uses PIC base `0x16144` and initializes category arrays.

| Property | Main | Spare |
|---|---|---|
| Physical descriptor pointer word | `0x200FD898` | `0x200FD8B0` |
| Address literal | `0x7658` | `0x76C8` |
| Word load | `0x6FD0` | `0x7464` |
| Temporary PIC slot | `+0x820`, store `0x6FD8` | `+0x7E8`, store `0x7470` |
| Category-6 pointer array slot | `0x16908 + 0x18` | `0x16498 + 0x18` |
| Final pointer store | `0x7514` | `0x755C` |
| Physical descriptor size word | `0x200FD89C` | `0x200FD8B4` |
| Size-address literal | `0x7660` | `0x76D0` |
| Category-6 size array slot | `0x16478 + 0x18` | `0x16458 + 0x18` |
| Final size store | `0x75AC` | `0x75F8` |

The main pointer's temporary index is saved at `0x6FDC`, reloaded at `0x7504`,
then used at `0x750C`. The spare index is retained in `r8` and used at `0x7554`.
Both final stores use category index 6 (`6 * 4 = 0x18`). Filename slot `0x165F8`
points to `/boot/factory/Asys.bin` at `0xD698`; slot `0x1665C` points to
`/boot/factory/Asys2.bak` at `0xD748`.

## AV selection and live row pointers

AV `0xEAAA` obtains descriptor `D = 0x200FD880` from literal `0xEDC0`.
Load `0xEACC` reads `D+0x18`, the same main pointer input as Linux above.
The code tests the word at `(main+0xE0) | 0x80000000` against `0xAAAAAAAA`.
If equal, `0xEADA..0xEADC` stores `main | 0x80000000` at VA `0x2032B584`.
Otherwise `0xEAE0..0xEAE4` reads `D+0x30`, the same spare pointer input,
and stores its alias in that slot. This fallback branch contains no second
validity-marker check; do not infer one.

Initialization dispatches page family `0x50` through `0xEC10` to `0xE764`.
That helper obtains state base VA `0x2032B580` from literal `0xEA38` and loads
state+4 at `0xE77E`, recovering the selected Asys pointer.

- Page `0x51`, segment `0x22`: `0xE972 -> 0xE99E` adds `0x3000`;
  `0xE9A4` stores the live row pointer.
- Page `0x51`, segment `0x23`: `0xE970 -> 0xE9AA` adds `0x3100`;
  `0xE9B0` stores the live row pointer.

The native handler adds the address's low byte within the row. Consequently:

```text
page 0x51 / address 0x2235 -> selected Asys shadow + 0x3035
page 0x51 / address 0x2345 -> selected Asys shadow + 0x3145
```

Both rows have length `0x100`, and both one-byte accesses lie within those
rows. Normal and alternate CNR therefore use the same selected backing, at
different offsets. This conclusion does not come from a filename or marker
match alone: both AV and Linux consume the same physical descriptor words.

## Static table size cross-check

Actual W300 `libBackupTable.so` has SHA-256
`9c61845bb02d0d4e44a962732bb8a4a6340f5b61185610e8d4d844383be14bb8`.
Its exported `TblSysInit` symbol has ELF VA `0x15754` and extent `0x9000`
(36,864 bytes). This is an initializer-object extent, not an observed live
Asys capacity. Its 24 `R_ARM_ABS32` relocations occupy twelve variation-pointer
slots in each package record at `0xB098/0xB0D8` (relocations
`0xB0A8..0xB0D4` and `0xB0E8..0xB114`). Both records identify package
category 1, with offset/size pairs `(0,0x400)` and `(0x400,0x400)`.

`PackageTable::getData` at `0x2734` selects `group*0x40 + variation*4`
and loads record+0x10 at `0x2754`. The generic consumer in actual BackupCore,
`CommonMethod::packageWrite` at `0x9CF8`, checks group/variation, obtains
category/offset/size/data through the supplied package interface, then calls
`BasicMethod::write` through PLT `0x6178` at `0x9DD8`. The constructor stores
that supplied interface at object+0x14 (`0x9484`). With this table interface,
the selected chunks belong to category 1. The generic consumer's externally
supplied binding is not a proof of a whole-object category-6 initialization.

The inspected package interface has eight records: `getGroupNum` at `0x2680`
returns 8, `getCategoryId` at `0x26A8` reads record word 0, and `getSize` at
`0x2704` reads word +8. Both use table VA `0xB018`, stride `0x40`. The records
contain categories `0,0,1,1,2,2,3,4`, with respective sizes
`0x400,0x400,0x400,0x400,0x400,0x800,0,0`. None supplies category 6.
Do not interpret following bytes beyond the declared count as extra records or
substitute these package sizes for the physical descriptor values.

## Expected logical Asys size

Actual W300 `libBackupCore.so` exports `CategoryTable::getCategorySize` at
ELF VA `0x6948`. It rejects category IDs above 7, constructs table `0xD57C`
through PIC base `0x16144`, and returns the category-indexed word at `0x6970`.
The eight sizes are `0x800, 0x800, 0xC00, 0, 0, 0x2800, 0x4000, 0x4000`.
Category-6 slot `0xD594` therefore specifies **0x4000 bytes (16 KiB)**.

This establishes an expected logical-size check for Asys and supports the
existing offline parser's `ASYS_SIZE=16384`. Both CNR offsets and their complete
0x100-byte rows lie within that logical extent. It does not observe the current
physical descriptor capacities, pointer values, selected copy or validity state.
Do not substitute this expected size for runtime descriptor verification.

## Remaining qualification

The current camera's pointer and size values, selected copy and validity-marker
state have not been observed. Numeric bounds for the entire live category cannot
be invented from row lengths, synthetic fixtures or compiled defaults. The
constructor reads genuine runtime descriptor inputs through physical-memory
mapping; the library does not embed their current numeric values.

This report closes category identity, pointer provenance, primary/spare selection
logic and the two CNR rows' relative scope. It does not close plugin selection,
service entry/exit, implicit persistence, or preservation/restoration of the RAM
change across normal shooting. The [active plan](../../../../docs/w300/EXECUTION_PLAN.md)
keeps those experiment prerequisites separate from measured NR efficacy.
