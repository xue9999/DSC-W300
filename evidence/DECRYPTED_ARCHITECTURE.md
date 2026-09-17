# DSC-G3 offline extraction summary

## Decryption Status
This report describes a reproducible offline extraction. Hashes and container HMACs establish recorded integrity checks; provenance and hardware behavior have separate qualification steps.

## Platform Facts
Model/architecture/browser labels in the imported profile are research descriptions. Counts, extracted strings and byte hashes are separately reproducible; descriptive labels are not hardware measurements.
- Model profile: `Sony Cyber-shot DSC-G3`
- Extracted kernel string: `Linux version 2.6.11-alp20080305 (jp06294@monet03) (gcc version 3.4.4) #1 Tue Feb 10 14:03:21 JST 2009`
- Observed ELF files: 96
- Declared payload section count: 24

## Storage Layout
Parsed table entries: 12. A table entry can be unused; it is not necessarily an active partition.

| Device | Offset | Size | Valid field |
| --- | --- | --- | --- |
| `/dev/nflasha1` | `0x00020000` | `0x00200000` | `0x00000001` |
| `/dev/nflasha2` | `0x00220000` | `0x00180000` | `0x00000001` |
| `/dev/nflasha3` | `0x003A0000` | `0x00400000` | `0x00000001` |
| `/dev/nflasha4` | `0x007A0000` | `0x00000000` | `0x00000000` |
| `/dev/nflasha5` | `0x007A0000` | `0x00380000` | `0x00000001` |
| `/dev/nflasha6` | `0x00B20000` | `0x01DE0000` | `0x00000001` |
| `/dev/nflasha7` | `0x02900000` | `0x00000000` | `0x00000000` |
| `/dev/nflasha8` | `0x02900000` | `0x00000000` | `0x00000000` |
| `/dev/nflasha9` | `0x02900000` | `0x00000000` | `0x00000000` |
| `/dev/nflasha10` | `0x02900000` | `0x00000000` | `0x00000000` |
| `/dev/nflasha11` | `0x02900000` | `0x00020000` | `0x00000001` |
| `/dev/nflasha12` | `0x02920000` | `0x01300000` | `0x00000001` |

## Subsystem Analysis
The retained payload contains updater/runtime filesystems and application archives for static inspection. Use G3 findings as comparative material and qualify equivalent W300 firmware and calibration operations against W300 evidence.
AV instruction edits and text-resource edits are offline experiments. Next qualification: verify installation, boot, recovery and image-quality effects on the target camera.

## Key Evidence Paths
- source_executable: `sources/DSCG3V2.exe`; SHA-256: `a9698c7b3822f23d71de84ba5389453b847f6de19ab293a55ebe016490fd94d9`
- msfirm_container: `sources/D-G3V2.dat`; SHA-256: `ea74b57161881208f177befcef003f7a0f65ae6e470e209c37f5a8da4f88dd5c`
- manifest_cntent: `evidence/extracted_g3/cntent.dat`; SHA-256: `31002b511c255d8d1df2f86d09a70c476ed142a3f7103630041babf53cbe9bb5`
- updater_body_img: `evidence/extracted_g3/sections/02_BodyUdtr.img`; SHA-256: `f69752fbeaaf9e51a2b6df45c7f1e0babd1f065584e5cce0d62507c4184f44a6`
- linux_set_archive: `evidence/extracted_g3/sections/17_linuxset1.tar`; SHA-256: `68043560cc56eb6457d823db8a9890ba9c20b1943b60a9a2b058ef5408220972`
- av_rtos_image: `evidence/extracted_g3/sections/09_av.bin`; SHA-256: `f2554be5181f5765623b0771e6aef6ff99c8483980a1192c39db85c744bda4fb`

Paths in this generated report refer to the extraction run. Historical copies can contain historical paths. See the active repository guides and artifact manifest for canonical retained locations.

## Current research use

Choose a specific W300 protocol or language-field question from the [execution plan](../docs/w300/EXECUTION_PLAN.md), locate its G3 analogue in the retained extraction and record the W300 evidence needed to test the mapping. This makes the architecture summary a route to a bounded analysis task while preserving the distinction between static findings and later device measurements.
