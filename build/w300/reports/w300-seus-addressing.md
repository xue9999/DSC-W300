# W300 SEUS addressing: implementing the model-specific mapping

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

## Finding

The W300 manual establishes a real SeusEX UI read operation and documented calibration locations. Map its Block/Page/Address fields to USB serialization using exact W300 code or transactions. The A330 helper exposes an unsigned-byte offset, while the manual includes `Address:0E10`; resolve that representation difference before adapting the wrapper.

No camera commands, imports of acquired scripts, speculative adapter implementation, or calibration/settings writes were performed. This report concerns service reads; standard USB/OS identity acquisition does not resolve this protocol gap.

## What is established for W300

Source: `sources/sony_dsc-w300_adjustment_ver1.3.txt`, corresponding to the retained original PDF.

- Manual page 6-23, text lines 1237–1249, expressly instructs reading `Block:11, Page:61, Address:0E10` as Dp and `Address:0E11` as Dy. It also says the Auto-Adj program can save those previous sensor data to a PC file. These are **angular-velocity-sensor calibration values**, not language fields.
- Manual page 6-29, text lines 1522–1549, defines separate Block, Page and Address selection, all in hexadecimal; selecting pages/addresses obtains displayed data, and `[Read]` refreshes it. The text does not provide maximum field widths, USB opcodes, argument encoding, payload layout, or response validation.
- The same section, lines 1510–1520, documents connection through SeusEX with a HASP key. It does not identify a raw USB challenge/response algorithm. Lines 1535–1544 distinguish transient `[Set]`, EEPROM `[Write]`, and flash `[Save]`; a generic write followed by immediate readback is not equivalent to persistent storage.
- Manual page 6-10, text lines 567–585, limits Destination Data Write to the Service board and identifies Destination Check as a real way to query the existing destination. Its underlying read function and the service-board eligibility test are not disclosed.

The known calibration addresses are useful anchors once a W300-capable read implementation is available. They do not by themselves establish how to form a USB request or locate the destination/language setting.

## What the legacy A330 code actually encodes

Final source: `build/w300/downloads/legacy-pmca/a330-7998362/a330.py`, [maintainer attachment 7998362](https://github.com/ma1co/Sony-PMCA-RE/files/7998362/a330.zip).

| Code | Source fact | Limit for W300 |
| --- | --- | --- |
| Lines 17–24 | `dump16be` is `struct.pack('>H', value)`; `dump8` is `struct.pack('B', value)`. | The offset argument is 0–255; passing `0x0E10` cannot encode the full address. |
| Lines 79–80 | `readSeus(page, i)` sends command `0x20`, subcommand `0x10`, argument `1`, with four-byte data `00 + page_BE16 + offset_U8`. It extracts one byte at offset 4 of the returned payload. | There is no block parameter or explanation of the constant leading byte. The variable names do not establish the wire fields' semantics for another model. |
| Lines 58–67 | The legacy packet is big-endian, with a 16-byte header; status byte 6 must be 1; returned payload begins at offset `0x10`. | These source details and the A330 transcripts qualify the legacy implementation for the observed A330 exchanges only. |
| Lines 76–77 | A separate memory read uses a BE32 address plus two BE16 fields. | It reads a different address space. No mapping from W300 Block/Page/Address to this memory space is present. |
| Lines 55–56, 69–74, 88–89 | Service entry, MD5 challenge/response, and `enableDump` are separate active operations. | A read helper's name does not make the preceding service-entry sequence passive or establish W300 acceptance. |

Do not truncate `0E10` to `10`, concatenate the manual fields into a guessed integer, reinterpret the constant zero as a block, or copy an A330 page to produce a W300 command. The source establishes none of those translations. Equally, the unsigned-byte wrapper alone does not exclude a wider address space or alternate operation in the original protocol; its implementation simply does not disclose one.

The earliest acquired attachment `early-dsc-reference/a330-7874849/a330.py:70–71` contains only a flat BE32 memory-read primitive. It has no SEUS block/page/address reader. The later source uses different authentication and memory-read arguments; the maintainer links the corrected dump implementation to decrypting the A330 updater in [comment 1023584809](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1023584809). The [initial reference to DSC cameras of the era](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1013561924) names no DSC model and supplies no W300 mapping.

## Narrow follow-up: the first published SEUS model-ID read

The saved primary discussion points to one additional attachment immediately preceding a real SEUS reply: [comment 1018627161](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1018627161), [attachment 7914900](https://github.com/ma1co/Sony-PMCA-RE/files/7914900/a330.zip), and [A330 response 1018808731](https://github.com/ma1co/Sony-PMCA-RE/issues/282#issuecomment-1018808731). That attachment was acquired and statically inspected; it was not run or imported.

New local reference files under `build/w300/downloads/legacy-pmca/addressing-reference/`:

- `a330-7914900.zip`: SHA-256 `1b7d5799da621df3843ba139e3df326b69fd60e1ed2a21b1f167d7eb547fbf02`.
- `a330-7914900.py`: sole archive member, 4396 bytes; SHA-256 `b0cec76ee4fc1b726c21dd4b7e876b4619f4cab126ef9a7d0c20f847f2dbef7a`.

Lines 83–84 encode the **same** `00 + page_BE16 + offset_U8` read as the final script. Lines 151–153 read page `0x30`, offsets `0x88`–`0x8B`; the linked A330 transcript returns `00 08 52 00`. It supplies a concrete A330 request/response example, but no wider address or independent block handling. The source contains exploratory command loops at lines 98–135 and 143–149, so it must remain a reference file, not a first-contact tool. There is no new W300 primitive to extract from it.

## Why current PMCA does not supply the bridge

Pinned checkout: `build/w300/upstream/Sony-PMCA-RE`, revision `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0`.

In `pmca/usb/sony.py:949–952,990–995`, the modern adjustment header contains a 16-bit category and command. The parameter named `block` is this category, not an established equivalent of the W300 manual's block selector. `readBackup` at lines 1038–1039 uses category `0x603`, command 1, and a little-endian 32-bit property ID; `readMemory` at lines 1025–1026 uses a separate flat-memory service. No function translates W300 Block/Page/Address to either namespace. The different service-entry and authentication protocols are recorded in `pmca-audit.md`.

## Exact missing engineering input

The smallest useful source would be the W300-capable **SeusEX register-read implementation or a trustworthy W300 exchange captured from it**, showing all of the following:

1. The necessary connection/service-entry sequence and authentication, with a verified W300 identity and mode.
2. How a known complete tuple such as manual Block/Page/Address is serialized, including any separate block-selection operation and byte order; data width and count must be explicit.
3. Its successful response, error/status handling, and whether the read reflects current working data or nonvolatile storage. A comparison with the actual SeusEX display would distinguish a plausible-looking response from the intended value.

An inspectable W300 Auto-Adj executable plus its SeusEX API dependencies could alternatively identify the exact calls for Destination Check and the block/page/address read interface. A W300 firmware image containing the relevant dispatcher could also establish the protocol. The already acquired Sony GPL material does not contain that proprietary implementation; processor architecture alone cannot supply it.

Even a qualified calibration read would only remove the transport/addressing obstacle. Preparing a language write would additionally require the W300 destination/language mapping, the original-board eligibility condition, persistence semantics, and backup/restore coverage. Those remain independent requirements. There is currently no evidence-backed W300 service-read command to include in the portable first-contact procedure.
