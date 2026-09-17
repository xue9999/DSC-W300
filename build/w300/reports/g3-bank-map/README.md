# G3 AV bank to Linux backup category: missing link resolved

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

**For the retained DSC-G3 components, AV page `0x61`, segment `0x0E` belongs to category 5: the Areg bank backed by `/boot/factory/Areg.bin` and `/boot/factory/Areg2.bak`.** The link follows the same two descriptor fields into the Linux category arrays. It does not rely on filename similarity or the common completion marker. This result supersedes only the bank-to-category uncertainty in `../av-page-init/README.md` and its Linux findings. Those completed reports remain unchanged.

This is static G3 evidence. Qualify W300 compatibility, the meaning of particular bytes, a safe language write, successful hardware persistence, or a recovery procedure through separate target-model evidence.

## Inputs and narrow route

The new analysis reads only retained `libBackupCore.so` as an ELF byte array. SHA-256: `56aa2595c4747b6aadc1c0c3bb7a438b15086951121024a8649254cdec61fd4b`; path: `evidence/extracted_g3/archives_unpacked/lib/lib/libBackupCore.so`. Its hash is checked against the preserved library inventory and an explicit expected hash. No target library was imported or executed.

The existing symbol inventory names getters for `ShadowTable` but not the writer of its initially zero arrays. The ELF `.ctors` section at VA `0x16050` contains `0xFFFFFFFF`, `0x6CCC`, `0`; the middle word has `R_ARM_RELATIVE` relocation type 23. `_init` at `0x6728` traverses that constructor list. Thus `0x6CCC` is a constructor entry supplied by ELF metadata, not a guessed start discovered by broad instruction scanning.

The selected constructor ends with an unconditional return at `0x7608`. Its code ends at `0x760C`; `0x760C..0x76E8` contains referenced literal data. The constructor, `_init`, and the two array getters are the four decoded ranges. Inline literals are printed as `.word` data rather than instructions.

## Exact descriptor-to-category chain

All addresses in this section are ELF VAs unless explicitly identified as descriptor addresses. The library's PIC base is `0x16144`, calculated by `0x6CD4/0x6CDC` from a PC-relative literal. The string resolved at `0xD5C4` is exactly **`/dev/mem`**. The constructor opens that path read-only and repeatedly calls `mmap` for a 0x1000-byte region using offset `0x200FD000`; it reads words from the mapped descriptor and unmaps the region. These are descriptions of static code, not operations run during this audit.

| Stage | Main bank pointer | Spare bank pointer |
| --- | --- | --- |
| Descriptor word read | `0x200FD890` | `0x200FD8A8` |
| Descriptor-relative identity | AV descriptor `0x200FD880 + 0x10` | AV descriptor `0x200FD880 + 0x28` |
| Literal supplying descriptor address | `0x7648` | `0x76B8` |
| Word read instruction | `0x6F28` | `0x73C0` |
| Temporary store instruction | `0x6F30` | `0x73CC` |
| Temporary location | PIC base + `0x828` = `0x1696C` | PIC base + `0x7F0` = `0x16934` |
| Final category array | `0x16908` (`getShadowAddr`) | `0x16498` (`getShadowSpareAddr`) |
| Final store instruction | `0x7508` | `0x7550` |
| Store offset in array | `0x14` = 5 × 4 | `0x14` = 5 × 4 |
| Category index | **5** | **5** |

The primary path saves the temporary index at frame offset `-0x44` (`0x6F34`), retrieves it at `0x74F8`, loads the pointer at `0x7500`, then writes `[array + 0x14]` at `0x7508`. The spare path keeps the temporary index in `sb`, loads `[PIC + sb]` at `0x754C` and writes `[array + 0x14]` at `0x7550`. No adjustment page number is inferred from those array indices.

The getters independently confirm the array purposes: `ShadowTable::getShadowAddr` at `0x6C20` indexes `0x16908`, while `getShadowSpareAddr` at `0x6CA0` indexes `0x16498`. The same constructor also fills the previously zero arrays at `0x16478` and `0x16458` from descriptor size fields. For category 5, the main size comes from `0x200FD894` and is stored at `0x75A0` into `0x16478 + 0x14`; the spare size comes from `0x200FD8AC` and is stored at `0x75EC` into `0x16458 + 0x14`. Their numeric runtime contents remain unknown; this audit does not need to guess them to identify category 5.

The already established AV initialization uses exactly these descriptor words to select its first bank, applies its `0x80000000` address mask, then sets the page61/segment0E live pointer to that selected bank plus `0x1A00`. Therefore the AV pointer is to the main or spare **category-5 bank**, with the AV-side address mask. Actual numeric bank bases and runtime selection were not observed.

The existing file-category evidence is also asserted directly from this ELF: category-5 slots in `FileAccesser::FILE_NAME` (`0x165E0`) and `FileAccesserMeasures2BattOff::SPARE_FILE_NAME` (`0x16644`) resolve through relative relocations to the exact Areg paths. The separate IPC receiver maps AV category selector **3** to Linux category **5**. That selector is a persistence category parameter; it is not the page number.

## What this changes, and what it does not

The missing G3 category link is now established: page61/segment0E is Areg, not Ausr. The earlier observation of separate operation 4/flush and operation 5/erase can therefore be associated with a specific G3 category selector. This report does not assemble a command or recommend sending one.

The prior persistence limitations still apply. `flush` checks `isDirty`; a direct AV copy has not been shown here to meet that condition. Erase writes zero-filled data and selector 0 affects all three AV categories. The trace identifies file-backed persistence code, not a completed transaction or a verified durability/restore guarantee.

The location under `/boot/factory/` and the symbol names identify the storage category. They do not prove which bytes represent calibration, destination, language or other factory settings. In particular, this result cannot justify replacing the entire bank or interpreting the G3 default contents as values for W300.

No W300-specific proprietary image or communication trace has been introduced. The W300 host/service protocol, byte semantics, exact backup/restore coverage and original-board applicability remain separate requirements.

## Reproduction and completed checks

From the repository root:

```powershell
& .\build\w300\venv\Scripts\python.exe .\build\w300\reports\g3-bank-map\inspect_bank_map.py
```

The helper uses the already isolated Capstone runtime under `build/w300/re-tools/site`. It verifies the source hash, constructor relocation, PIC base, `/dev/mem` string, exact descriptor literals, intermediate and final store instruction words, array addresses and category-5 filenames. It regenerates `bank-map.asm.txt` and `evidence.json`. The completed result is `ok: true`, `category: 5`, `main_file: /boot/factory/Areg.bin`, `w300_qualified: false`.

All new files are under this report directory. Sources, evidence, preceding reports and main project documentation were not edited. The decoder executed only on this computer as an offline analysis tool; no firmware code or USB operation was executed.
