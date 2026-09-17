# Early DSC-era assumptions versus the later A330 implementation

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

## Result and boundary

The earliest maintainer attachment differs materially from the final A330 implementation: it assumes a control/bulk mass-storage command route, submits a zero-filled authentication response without obtaining a challenge, sends a zero packet-length field, and attempts memory offsets starting at zero with a different command argument. These are useful distinctions for future protocol analysis. **They do not identify a DSC-W300 command, address, authentication method, flash map or language operation.**

Exactly three new attachments were downloaded into `build/w300/downloads/legacy-pmca/early-dsc-reference/`. Only their source text was inspected. No script was imported or executed, no USB operation was performed, and previously retained files were not modified. The final A330 script and the later A330 dump script were already present and were read for comparison.

## Primary provenance

The source discussion is [Sony-PMCA-RE issue 282](https://github.com/ma1co/Sony-PMCA-RE/issues/282). The local complete comments snapshot is `build/w300/reports/pmca-issue-282-comments.json`.

| Attachment | Maintainer comment | ZIP bytes | ZIP SHA-256 |
|---|---|---:|---|
| [7874849](https://github.com/ma1co/Sony-PMCA-RE/files/7874849/a330.zip) | [1013667116](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1013667116) | 1093 | `db214dffa04fa4963e443b40db8466c3fe31b25599fe9c857ff9fa2a4cc2ad69` |
| [7890406](https://github.com/ma1co/Sony-PMCA-RE/files/7890406/a330.zip) | [1015544237](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1015544237) | 1089 | `c90fe261bba5b94266764df616c112505325a628c4529a9a713d34df14440d31` |
| [7892025](https://github.com/ma1co/Sony-PMCA-RE/files/7892025/a330.zip) | [1015787452](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1015787452) | 1096 | `dd39b626b7f540d568cebb7ae69754a966bf3bac047018993221411a2d3f37ca` |

Local archive names are `a330-<attachment-id>.zip`; each extracted script is `a330-<attachment-id>/a330.py` beneath the new directory. Each archive contains that one Python file.

Extracted script hashes:

- 7874849: `45932af7d43664f029a3e930a8560415a4b681b2875fd3e0b50cffb0972d9153`
- 7890406: `c8effc39ad1f9d4983328d688b077cf63284835d9874e619d935dbd0a04c0ce6`
- 7892025: `5f6218191ac709e2ccfc52e76cf063f9809207377a79d21fb006f34429fc83bb`

The maintainer's [initial comment](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1013561924) says the proposed experiments derive from methods used on DSC cameras of that era. It does not name one of those DSC models. The scripts are all named `a330.py`, select any device with VID 054c and have no W300 identity check.

## Static differences and what established them

Line numbers below refer to the respective extracted original `a330.py` files. Final means the already retained `build/w300/downloads/legacy-pmca/a330-7998362/a330.py`.

| Aspect | Earliest script 7874849 | Second/third scripts | Final A330 | Evidence limit |
|---|---|---|---|---|
| Standard Inquiry transport | Lines 42-45: 12-byte SCSI command sent using a class/interface control transfer, followed by bulk IN; control/bulk style, with no interrupt-status read | 7890406 lines 43-48 changes to a `USBC` bulk-only wrapper and reads the 13-byte status wrapper; third retains it | Lines 44-49 retains bulk-only | Actual A330 descriptor has interface protocol 50; this correction is based on A330 evidence, not W300 |
| Service-entry request | Lines 51-52: request f0, value/index f000, eight ff bytes | Unchanged | Lines 55-56: unchanged | Shared script bytes, not a W300 acceptance result |
| Service length field | Line 55: literal big-endian zero | Still zero at line 58 | Line 59: `3 + len(data) // 4` | The reason the earliest devices could accept zero is not specified |
| Authentication | Lines 67-68: directly submits stage 2 with sixteen zero bytes | Same attempt at lines 70-71 | Lines 69-74: stage-1 challenge, XOR with ASCII key, MD5, stage-2 response | Later maintainer explicitly reports the shortcut does not work on A330; no named DSC result accompanies it |
| Memory read | Lines 70-71: command 30/subcommand21, default final argument zero; address BE32, value4 BE16, size BE16 | Same | Lines 76-77: final argument 10; same payload structure | Command argument meaning is not documented for W300 |
| Dump range | Lines 88-91: 00000000 through 007fffff, chunks100 | Same, lines 91-94 | Final language script does not run a dump; already retained 7953397 dump variant uses 9f000000 through 9fffffff | Neither range is a qualified W300 physical or logical map |
| SEUS byte reads/writes/persistence | Absent | Absent | Lines 79-86 add these primitives; lines 104-110 use A330 destination/write-enable/save addresses | Earliest code supplies no language mapping at all |

The third attachment is a Python-version repair attempt: its hex printer iterates `bytearray(data)` and its Inquiry read adds `bytes(...)`. It does not supply another DSC transport or address map. The conversation subsequently records further Python 2 conversion fixes, which are outside this three-download scope.

The original [A330 descriptor and failed first attempt](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1014891722) show USB PID 03a8, product DSLR-A330, interface class08/subclass06/protocol50. Inquiry times out with the initial control/bulk script. The maintainer then supplies the bulk-only version in comment1015544237. This is a concrete transport mismatch and correction; it is not a failed W300 attempt.

The maintainer later [states that the authentication shortcut fails on A330](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1015878435), then [supplies a challenge-response version](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1016188694). After [decrypting the A330 updater](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1023584809), the maintainer supplies the already retained 7953397 flash-dump version. Therefore the later corrected memory arguments and dump range are supported by model-specific A330 investigation, not merely by chronological proximity to a DSC camera.

## Consequence for W300 work

The earliest attachment preserves an additional research hypothesis: the source DSC generation may use control/bulk Inquiry and a permissive older service handler. This is an inference from source differences plus the maintainer's unspecific DSC statement. It is **not** sufficient justification to send zero authentication, malformed length fields or guessed memory offsets to W300.

No inspected attachment or relevant comment identifies a named DSC model, W300 USB service reply, W300 safe memory-read address, W300 destination byte, or W300 persistence command. The initial zero-based 8 MiB range must not be relabeled as an ARM/CXD4108 flash map, and the later 9f000000 A330 range must not be transferred to W300. Processor-architecture knowledge does not supply that missing address-space/protocol mapping.

Use the actual W300 USB descriptor to select normal mass-storage transport. Native Windows standard INQUIRY delegates transport details to its driver and remains the prepared first-contact method. Qualification of any later legacy service operation still requires W300-specific evidence or a justified, separately reviewed acquisition operation. These originals must remain reference material rather than executable W300 tools.
