# libgphoto2: scope of the DSC-W300 lead

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

## Result

This lead does **not** provide a DSC-W300 language-change operation or a verified alternate USB identity. The authoritative current `camlibs/ptp2/library.c` has neither a DSC-W300 model entry nor USB product ID `0x029d`. The proposed SwiftMTP entry attributing that combination to libgphoto2 cannot be reproduced from the inspected upstream revision. Do not use it to replace the previously observed W300 identity, `054c:0341`, or to assert that `029d` is its PTP-mode ID.

Static inspection only: no camera communication, imports, program execution, or settings writes were performed for this check. The negative finding is limited to the four pinned PTP sources below; it is not a claim about every historical libgphoto2 revision or a proof that W300 can never expose a language operation.

## Provenance and reproducibility

Authoritative upstream: [gphoto/libgphoto2 commit 5672d510447bed26aa4c5d646665e768281bc680](https://github.com/gphoto/libgphoto2/commit/5672d510447bed26aa4c5d646665e768281bc680), resolved from `master` for this inspection; commit date 2026-09-02T07:46:49Z. Four files were acquired directly from `raw.githubusercontent.com` at that exact commit into `build/w300/downloads/libgphoto-reference/`.

| File, originally under `camlibs/ptp2/` | Bytes | SHA-256 |
| --- | ---: | --- |
| `library.c` | 385435 | `2d6dd02a9bf3d581e368c8f4f4976210e03f3c0797a34f47ccab0ba74c8faccb` |
| `config.c` | 498367 | `d95ff9d39c3b9852e27ea961c3158650ede7475a8232451acf09896da07ef5d8` |
| `ptp.c` | 389543 | `3826338690d2ea3b4641f85e64c9f7f3a1d1a3b021a8011113fa19cdfdd38d44` |
| `ptp.h` | 233182 | `1b3811ade47db01935bd55ac8c6d2a249a8c7c4baad0517eda0c8a65c5cb12b6` |

Reproduce the key searches from the repository root:

```powershell
rg -n -i 'W300|029d' build/w300/downloads/libgphoto-reference
rg -n 'sony_capturetarget|StillImageStoreDestination|SettingsSaveEnable|SettingsReadEnable|SettingsSaveReadState' build/w300/downloads/libgphoto-reference
rg -n -i 'language|locale' build/w300/downloads/libgphoto-reference
```

The first command has no matches (exit code 1). Search results from the remaining commands were inspected in their enclosing vendor/configuration contexts.

## What the authoritative source actually supplies

- The model table structure holds model name, USB vendor/product IDs, and device flags (`library.c:851–856`). The Sony section comments that many Sony PTP cameras share IDs; `Sony:PTP` is `054c:004e` at line 1068. Nearby real entries include DSC-W200 PTP mode, `054c:02f8`, at line 1121 and DSC-W130 PTP mode, `054c:0343`, at line 1125. None of those entries establishes W300 support or a language operation. [Pinned model table](https://github.com/gphoto/libgphoto2/blob/5672d510447bed26aa4c5d646665e768281bc680/camlibs/ptp2/library.c#L1067-L1140).
- Sony's `StillImageStoreDestination` is explicitly **Capture Target**: values `sdram`, `card`, and `card+sdram` in `config.c:11098–11103`; registered as `capturetarget` at line 11930. Its definition is `0xD222` (`ptp.h:3538`) and its descriptive name is Capture Target (`ptp.c:7502`). It concerns where captured images are stored; it is not the service manual's sales destination data. [Pinned values](https://github.com/gphoto/libgphoto2/blob/5672d510447bed26aa4c5d646665e768281bc680/camlibs/ptp2/config.c#L11098-L11103), [pinned handler registration](https://github.com/gphoto/libgphoto2/blob/5672d510447bed26aa4c5d646665e768281bc680/camlibs/ptp2/config.c#L11930).
- `SettingsSaveEnable`, `SettingsReadEnable`, and `SettingsSaveReadState` are Sony property definitions `0xD271`–`0xD273` (`ptp.h:3595–3597`) with corresponding display names (`ptp.c:7557–7559`). No matching configuration handlers or W300 qualification were found in the inspected files. These names do not establish a backup/restore mechanism for this camera. [Pinned definitions](https://github.com/gphoto/libgphoto2/blob/5672d510447bed26aa4c5d646665e768281bc680/camlibs/ptp2/ptp.h#L3595-L3597).
- No Sony menu-language property definition or handler was found in these sources. Language hits were in other vendors' contexts, including Kodak, Nikon 1, Fuji, and Olympus; MTP `LanguageLocale` is an object property. They do not identify a W300 menu-language address or writable setting.
- The source's Sony extended initialization is conditional on advertised operation support; `library.c:714` tests `PTP_OC_SONY_SDIO_GetExtDeviceInfo` before the SDIO connection sequence at lines 721–722. The existence of generic Sony SDIO code is not model-specific evidence that W300 implements those operations. [Pinned condition and connection](https://github.com/gphoto/libgphoto2/blob/5672d510447bed26aa4c5d646665e768281bc680/camlibs/ptp2/library.c#L705-L725).

## Why the SwiftMTP proposal is not stronger evidence

[SwiftMTP-dev PR 96](https://github.com/EffortlessMetrics/SwiftMTP-dev/pull/96) claims its Sony entries were sourced from libgphoto2 `camlibs/ptp2/library.c`. The local snapshot is `build/w300/reports/continuation/swiftmtp-pr96.json`. Its proposed W300 entry is `sony-dsc-w300-029d`, `054c:029d`, PTP interface class/subclass/protocol `06/01/01`, with `hooks: []`, `status: proposed`, `confidence: medium`, and `evidenceRequired: [community-validation]`. The JSON consists of transfer/timeout/quirk settings and generic operation flags; it contains no menu-language or service-destination operation.

Verified conclusion: the PR is an unvalidated transfer-configuration proposal whose claimed model/ID provenance was not reproduced from the pinned primary source. A different W300 PTP identity remains only a possible explanation, not an established fact. This lead adds neither the missing W300-specific setting map nor a tested persistent write/restore procedure, so it does not remove the current execution-plan limitation.
