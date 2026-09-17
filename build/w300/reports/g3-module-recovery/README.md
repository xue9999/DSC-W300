# Complete G3 module recovered from the retained ext2 image

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

## Result

The missing tail of the retained G3 `unified_drv.ko` is present in the preserved `initrd.img`. The earlier extraction stops at **274432 bytes**, exactly `(12 + 256) * 1024`: twelve direct blocks plus one block of 256 indirect pointers. The inode declares **303816 bytes**. The repository's `Ext2Unpacker._read_inode_data` reads only those direct and singly indirect blocks; it never follows the doubly indirect pointer and never rejects a short result.

`recover_module.py` supplies the missing block traversal in a local subclass and reads only the fixed `bin/unified_drv.ko` path. It produced the full **303816-byte** module from actual image blocks. Its entire 274432-byte prefix equals the preserved extraction. Every declared file-backed ELF section fits, and all **9102** relocation entries have valid symbol-table indices. No missing bytes, instructions or relocations were guessed.

The new file is `unified_drv.complete.ko`, SHA-256 `8d675f7071e49a75a174130ef8525767af07c157fe5f203018eb097e10aa1367`. It is an offline analysis input, not a driver for installation on this PC or a camera. It was never loaded or executed.

## Inputs and integrity

- Original image: `evidence/extracted_g3/archives_unpacked/linuxset1/initrd.img`, 660480 bytes, SHA-256 `a011eef609836a0d6bc33e827782148952f0634a7d09f2a9c9b49955e6f767be`.
- Preserved short extraction: `evidence/extracted_g3/rootfs/initrd/bin/unified_drv.ko`, SHA-256 `69b3536228712cd180c8747ae80f0548725fd628c5bc00fee9ca940c61960985`.
- Reused metadata/directory parser: `tools/g3_firmware_parser.py`; its actual source hash is recorded in the JSON. Only its Python definitions are imported, not any firmware library.

The two original inputs are verified against `evidence/artifact_manifest.json` before use. The script also reproduces the old parser's short result directly from the image and asserts that it equals the preserved extraction. The original parser, image, extracted module and artifact manifest remain unchanged. All output stays in this report directory; importing the metadata helper suppresses Python bytecode writes.

The specific inode is 14, the ext2 block size is 1024, and the report lists every actual data block and its indirection depth. This module uses no sparse blocks. The helper supports indirect traversal but is deliberately not a whole-filesystem extraction or firmware-building workflow.

## Reproduction

From the repository root:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\g3-module-recovery\recover_module.py'
```

The executed result was `ok: true`, `old_bytes: 274432`, `complete_bytes: 303816`, `prefix_identical: true`, `all_elf_sections_present: true`, `relocations: 9102`. `recovery-evidence.json` contains input/output hashes, inode evidence, complete block list and ELF checks.

An [independent review](INDEPENDENT_REVIEW.md) implemented a second reader without importing either recovery helper or the original parser. It reproduced the same complete bytes/hash from 297 real data blocks and three pointer blocks, verified inode allocation accounting and checked relocation target offsets as well as symbol indices. `independent_review.py` and `independent-review.json` preserve that executed check.

## Effect on the service investigation

This removes a concrete local extraction defect that had hidden kernel relocation data. It does not change the earlier USB report's results: that report used only relocations present in the preserved prefix and explicitly documented its then-current limit. The recovered complete module is a separate, newly pinned input for any subsequent bounded analysis.

The source acquisition limitations in `evidence/g3_acquisition.md` remain. Completeness against the ext2 inode and ELF structure is not a new Sony authenticity attestation. This remains **G3 reference evidence**, not W300 firmware, an approved W300 USB command or a language-conversion operation.
