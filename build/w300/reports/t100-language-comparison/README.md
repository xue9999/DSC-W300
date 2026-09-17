# T100 firmware acquisition and language comparison with G3

## Result

An additional Sony CXD4108 firmware has been acquired and dissected: **DSC-T100 updater version 2**, released by Sony on 19 April 2007. The original executable contains firmware version `0723`, model `07210001`, in its decrypted `defhd.dat`. Its 18 sections pass the CXD4108 container and section HMAC checks. The retained G3 firmware supplies the second comparison point.

The acquired T100 kernel independently corroborates the platform: `archives_unpacked/linuxset1/vmlinux` contains `ARM-CXD4108` at file offset `0x139F30` and `Linux version 2.6.11-alp20070122`, built on 27 March 2007, at `0x136BC0`. Its exact bytes are pinned in `extraction.json`; the SoC comparison does not rely solely on the external firmware-tool model list.

The comparison strongly supports a shared region/language architecture across these two cameras: the five relevant native configuration rows match, the category-0 backing files match, and the first `0x423` bytes of `regionInfo.xsb` CODE are identical. Application language groups and fallback behavior nevertheless differ. **These results support targeted W300 research; they do not establish W300 field values or a camera write procedure.**

The important functional distinction is between the **allowed-language group/list**, **regional default language**, and **user-selected language**. Changing the last of these alone may leave the regional restriction in place. The Japanese group in both compared applications exposes only Japanese even though their packages contain other language resources.

## Source and reproducibility

Sony's [T100 support page](https://www.sony.com/electronics/support/downloads/W0002671) identifies `DSCT100V2.exe`, its purpose, applicable model and release date. It says download service ended in March 2021. The concrete payload URL comes from the [pinned OpenMemories-CI workflow](https://github.com/ma1co/OpenMemories-CI/blob/4f8c6367a75e9afd02bc684425e3fbff424b2223/.github/workflows/ci.yml). A direct TLS-verified GET to [Sony's updater server](https://di.update.sony.net/DSC/DSCT100V2.exe) succeeded. No updater executable or extracted camera code was executed.

| Artifact | Verified result |
|---|---|
| Original updater | `build/w300/downloads/related-firmware/DSCT100V2.exe`; 15,978,538 bytes |
| SHA-256 | `e5ecfbeef87a5708536f51b6d2479bffde58394d71c2752337382716d9e72d67` |
| LHA member | `D-T100V2.dat`; 15,950,816 bytes; header at `0x6C00`, data at `0x6C49`; member CRC-16 verified |
| Container | Manifest checksum valid; header and data HMACs valid; 18 independently verified sections |
| Extracted inputs | 192 regular files represented in [extraction.json](extraction.json); Linux/ARM application libraries, XS scripts, XML, language CSVs and factory defaults |
| Extraction method | Existing CXD4108 cryptography and safe TAR extraction, wrapped by [extract_t100.py](extract_t100.py); no G3-specific expected section count imported |

The original G3 EXE carver expects its LHA header at `0x7400`; it rejects T100 at that step. The new wrapper validates T100's actual LHA layout and passes the carved DAT to the existing parser. It does not relax the G3 parser or overwrite source/evidence inputs. Extracted factory files are updater defaults, not a dump of the user's camera.

From the repository root, using the existing research environment:

```powershell
.\build\w300\venv\Scripts\python.exe -B build/w300/reports/t100-language-comparison/extract_t100.py --acquire
.\build\w300\venv\Scripts\python.exe -B build/w300/reports/t100-language-comparison/compare.py
```

The first command downloads only if the pinned updater is absent. It validates length, SHA-256, LHA member CRC, manifest and section HMACs. The second validates each analyzed input against its extraction/evidence pin and emits the selected instruction ranges, native disassembly, XML values and [comparison.json](comparison.json). Native disassembly uses the existing Capstone research dependency. Downloads and reconstructed extraction trees remain local; source acquisition records and exact input hashes make them reproducible. No GitHub publication is claimed.

## Identical native fields and backing files

Both `PExtBackupGrammar` implementations associate these names with the same numeric literal IDs through the verified literal/parse/property-install sequence. Both `libBackupTable.so` files contain matching 20-byte rows. Each row is `[ID, size, bit size, bit mask, kind]`; bit size and bit mask are zero, and kind is 1.

| Property suffix | ID | Category offset | Size | T100 row file offset / ELF VA |
|---|---:|---:|---:|---|
| `cmn__DestinationID` | `0x00010400` | `0x104` | 1 | `0x2C6C` / `0xAC6C` |
| `brewApp__regionData` | `0x00040000` | `0x400` | 4 | `0x2BF4` / `0xABF4` |
| `brewApp__initLangData` | `0x00040400` | `0x404` | 4 | `0x2C08` / `0xAC08` |
| `brewApp__availLangData` | `0x00040800` | `0x408` | 4 | `0x2C1C` / `0xAC1C` |
| `brewApp__signalTypeData` | `0x00040C00` | `0x40C` | 4 | `0x2C30` / `0xAC30` |

T100 native code computes category as `ID >> 24` and offset as `(ID >> 8) & 0xFFFF`. Category 0 resolves through the relocated pointer arrays to `/boot/factory/Hreg.bin` and `/boot/factory/Hreg2.bak`, as on G3. See [native-fields.asm.txt](native-fields.asm.txt). These are category-relative offsets, **not USB addresses or raw flash offsets**. The string-to-number parse implementation has not been independently executed; literal values, property installation and native numeric rows corroborate the association statically.

## Allowed languages: shared structure, different policies

The actual application reads `Registry.KEY_REGION / systemData.langGp` and selects `availableLang`. The selected instruction output includes the integer cases, branch destinations and their exact strings.

| Group / behavior | T100 | G3 |
|---|---|---|
| 0 | All 25 listed languages | Same list |
| 1 | `jpn` only | `jpn` only |
| 2 | `eng,fre,spa,ita,tch,sch` | Same list |
| 3 | European set including `eng`, `pol` and `rus` | Same list |
| 4 | `eng,spa,por,tch,sch,kor,per,ara,tha,mal` | Also includes `fre` |
| 5 | No explicit arm in this consumer | European set without `rus` |
| 99 | Reads `systemData.availableLang` | Same property |
| Unmatched group | Falls back to `jpn` | Falls back to `eng` |

T100 anchors: `dsc.xsb` CODE `0xC4A6–0xC656`; group-1 literal `0xC568`; default `0xC646`. G3 anchors: CODE `0x1660B–0x1680F`; group-1 literal `0x166D4`; default `0x167FF`. The complete case lists are in `comparison.json` and the two `*-dsc.xsb.txt` files.

The T100 package includes 25 language CSVs, including English and Polish. Its Japanese region XML nevertheless specifies `lang=jpn`, `langGp=1`, `sigTyp=0`. This demonstrates a configuration-based restriction within the compared package. It does not prove which resources a Japanese W300 contains.

The shared `LanguageData` initialization has these now-resolved integer masks:

| Language | Mask | Shared CODE offset / bytes |
|---|---:|---|
| English | `0x00000100` | `0x210` / `8a0100` |
| Japanese | `0x00008000` | `0x2AA` / `4800008000` |
| Polish | `0x00100000` | `0x322` / `4800100000` |

The constructor stores `langName` and `value`. T100's available-language builder tests each value with bitwise AND at CODE `0xAD8`, skipping a language on a zero intersection. This distinguishes a language bit mask from a numbered predefined group. The native integer, inequality, branch and AND handlers were inspected in the actual T100 `tinyhttp`; see [t100-selected-handlers.asm.txt](t100-selected-handlers.asm.txt). These masks are comparative static facts, not proposed W300 write values.

T100's actual `fxRemapIDs` at VA `0x9CA7C` supplies the operand framing. Its dispatch table at `0x9CAB0` matches the G3 operand classes after a `0x8A60` address translation. The [native remapper disassembly](t100-remapper.asm.txt) verifies the handler layouts. All encountered short relative branches land on framed boundaries. This does not establish a full interpreter or every possible runtime path.

## Region conversion changes more than language selection

Both script paths write four fields and request a host-regulation flush. T100 write calls are CODE `0x637`, `0x645`, `0x653`, `0x661`, followed by `flush` at `0x672`. G3 calls are `0x631`, `0x63F`, `0x64D`, `0x65B`, then `0x66C`.

T100's service caller is in `senserModule.xsb`: `makeRegionInfoFile` at `0x121AD`, save at `0x121C6`, Registry reset/initialize at `0x121D0`/`0x121DA`, language initialization at `0x12200`, `_setLanguage` at `0x1220D`, video initialization at `0x1221A`, and the response following `OK` at `0x12227`. G3 separates this caller into `senserCmdTable.xsb`, with a `SUCCESS` response. Shared design therefore does not imply identical service script organization or response text.

The G3 `deleteUserInfoFiles` path at CODE `0xB89–0xC15` deletes both `/boot/dsc/UserInfo.xml` and its `.bak` counterpart, using configured paths. The initial user XML covers a broad set of preferences. The region path must therefore be assessed for collateral settings changes. G3's `_setLanguage` separately reads the user language and uses the regional default when it is empty, then calls `langManager.setLanguage`.

T100 native `CommonMethod::flush` gets the category size and calls `BasicMethod::flush` with offset zero: a category-wide flush. Static call sites, an empty G3 `onFlushComplete` body and a subsequent service success response do not prove a completed durable write. This comparison did not establish full error propagation, recovery or post-restart behavior.

## Other acquisition coverage and next action

The closest same-year shortlist remains W150/W170, T300 and H50. Their published GPL inputs match W300's previously acquired packages. Current model support listings and bounded English/Russian/Chinese binary searches yielded no additional camera updater or dump. This is scoped coverage, not proof that no dump exists. Three Archive.org candidates describe PC application CDs: `sonypictutil-3294892020` (W150/W170), `sonypictutil_202307` (H50), and `sony-cybershot-dsc-t300`. Their ISO bytes were not downloaded or inspected; they are lower-priority software-disc leads, not acquired firmware. The T700 PMB Language Fix Tool is a PC application tool, not camera-language evidence.

For W300, prioritize qualifying the category-0 field layout and language consumer using actual W300 code, Auto-Adj or a trustworthy service trace. The comparison supplies five specific fields, backing-file candidates and consumer patterns to look for; it narrows the question substantially. If external payload acquisition cannot supply that code, continue the already identified path-based file-read preparation for the later camera session. Do not transplant the complete T100/G3 firmware or factory files.

Once W300 evidence is available, inspect the narrowest allowed-language/default-language operation before selecting the broader region-conversion routine. Resolve service transport, original-board eligibility, affected-data backup/restoration and actual persistence separately. Persistent English on the original W300 remains unverified.
