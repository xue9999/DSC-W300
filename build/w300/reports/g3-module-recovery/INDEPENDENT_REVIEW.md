# Independent review of G3 unified_drv.ko recovery

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

**PASS for this exact file and image.** The 303,816-byte output is reproduced from actual ext2 data blocks without importing `recover_module.py` or `tools/g3_firmware_parser.py`, without synthetic padding, and without executing any firmware or module. Its SHA-256 is exactly `8d675f7071e49a75a174130ef8525767af07c157fe5f203018eb097e10aa1367`.

## Direct source evidence

The source is `evidence/extracted_g3/archives_unpacked/linuxset1/initrd.img`, SHA-256 `a011eef609836a0d6bc33e827782148952f0634a7d09f2a9c9b49955e6f767be`. Both it and the historical extracted module are verified against `evidence/artifact_manifest.json`.

The independent reader parses the ext2 superblock and directory entries itself. Root inode 2 names `bin` as inode 11; that directory names `unified_drv.ko` as inode **14**. Block size is 1024 bytes, inode size 128 bytes, and the group descriptor table starts at image byte 2048. Inode 14 resides at image byte **8832**, in inode table block 7. It declares a regular file of **303,816 bytes** and **600 allocated 512-byte sectors**.

Its fifteen block roots are:

```text
direct: 111,112,113,114,115,116,117,118,119,120,121,122
single indirect: 123
double indirect: 380
triple indirect: 0
```

Block 123 supplies the next 256 data-block pointers. Double-indirect block 380 points to second-level pointer block **381**, whose first 29 entries point to data blocks **382 through 410**. The final data block contributes 712 bytes. All 297 used data blocks and all three pointer blocks are present, nonzero and mutually distinct. Their allocation accounts exactly for inode `i_blocks`: `(297 + 3) × 2 = 600` sectors.

## Cause of the historical truncation

`Ext2Unpacker._read_inode_data` in `tools/g3_firmware_parser.py`, lines 583–587, collects only the twelve direct pointers and one single-indirect block. It never traverses the double-indirect pointer at inode `i_block[13]`. Lines 588–599 return whatever those pointers cover without checking that the declared file size was reached.

For this 1024-byte-block image, that implementation stops at `(12 + 256) × 1024 = 274,432` bytes. This is exactly the preserved module length. The missing tail is **29,384 bytes**, and the recovered output's first 274,432 bytes equal the preserved module byte for byte. The defect is an extraction-algorithm limit, not a corrupt source image, absent firmware bytes, missing dependency, or camera compatibility result.

## Independent checks and scope

The standalone review concatenates the actual referenced blocks and trims only the last block to inode size. It contains no zero-fill fallback; every required pointer must identify an existing block. The resulting bytes equal `unified_drv.complete.ko` exactly.

The output is an ELF32 little-endian ARM relocatable object. All **29 section headers** and all sections with file contents are within the recovered file. All **9,102 relocation entries** have valid symbol indices and offsets within their referenced target sections. These are structural checks; no claim is made that the module has been loaded, is compatible with a running kernel, or supports W300.

I read the recovery helper before implementing this independent check. Its indirect-depth calculation is correct for this inode: direct entries use depth 0, root 12 uses depth 1, and root 13 uses depth 2. The independent result validates this concrete recovery; it is not a general audit of sparse files, triple-indirect extraction, or every ext2 feature.

## Reproduction

From the repository root:

```powershell
& .\build\w300\venv\Scripts\python.exe .\build\w300\reports\g3-module-recovery\independent_review.py
```

The completed run reports `ok: true`, 297 data blocks, three metadata blocks, 303,816 output bytes, 9,102 relocations and `synthetic_zero_fill_used: false`. It writes only `independent-review.json`; it does not rewrite the module or any source/evidence file.
