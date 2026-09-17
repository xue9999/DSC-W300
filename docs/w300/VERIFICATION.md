# W300 preparation verification — research documentation revision 5

Historical checks below were performed on 2026-09-16 on Windows 11 x64, build 26200. The later camera session uses a separate Windows 10/11 x64 computer. This preparation used offline analysis and OS inventory; camera settings, identity and calibration were preserved. Historical revision-3 publication checks are recorded separately in `build/w300/reports/release-r3-verification.json`.

## Evidence milestones and next actions

| Milestone | Measured result or next qualification |
|---|---|
| Program acquired | Pinned Sony-PMCA-RE source and six original legacy A330 script archives retained |
| Program started | PMCA console startup/help passed under Python 3.12.14; Windows driver modules imported and local libusb DLL loaded |
| Reproducible environment | Locked wheels retained; separate environment rebuilt with `--no-index`; dependency check and selftest passed |
| Portable revision 2 | ZIP relocated into a path containing spaces and Polish characters; 1317 hashes verified; frozen selftest and OS inventory passed with external Python/Git/pwsh removed from PATH |
| W300 language qualification | Current verification flag is false; establish the model-specific operation, encoding, eligibility and persistence |
| Camera communication | OS inventory returned zero Sony devices; capture actual replies during the later receiving-PC session |
| English language change | Reserved for the separately authorized write stage |
| Write-procedure qualification | Complete affected-data backup/restoration and original-board eligibility before the write trial |

## Executed checks

- `pmca_offline.py`: exit 0; the actual pinned program prints help after USB-runtime initialization. Output is in `pmca-startup-verified.txt`.
- `w300_workbench.py selftest`: dependency versions, native-driver imports, DLL loading, commit identity and seven reviewed source hashes passed.
- Offline replay of a published A330 challenge/response reproduced the maintainer's MD5 output exactly. Treat this as a legacy-codec check and qualify W300 authentication separately.
- Five workbench tests passed, covering ambiguous/wrong devices and truncated or invalid responses. Their identities are synthetic test fixtures.
- Windows inventory succeeded and returned zero Sony devices. It queried PnP properties without an application camera command.
- `restore_environment.ps1` rebuilt dependencies solely from local wheels; `pip check` and selftest passed. See `environment-offline-rebuild.txt`.
- Repository integrity checks passed for 821 preserved artifacts, with zero errors. The historical result is `build/w300/reports/final-audit.json`.
- Portable revision 2 selftest and inventory exited zero after relocation; the included PowerShell supplied inventory. This measures packaging on the preparation host. Record the receiving PC's own results during its session.
- PowerShell 7.4.18 ZIP matched official release metadata. Its `pwsh.exe` Authenticode status was Valid, signed by Microsoft Corporation; see `portable-powershell-signature.json`.

## Findings and engineering follow-up

| Work performed | Concrete finding | Next action and verification |
|---|---|---|
| Pinned PMCA code inspection | Modern language tweak uses backup-property/layout assumptions; G3 transport analysis matches specific framing/authentication paths. | Derive W300 field and service mappings from W300 code or transactions; verify exact responses. |
| Python/USB setup | Installing and explicitly loading `libusb-package` resolved the initial backend-DLL issue. | Reuse the locked environment and run its selftest. |
| Pinned source comparison | Windows CRLF conversion changed seven reviewed files; restoring exact Git blobs made all hashes match. | Preserve LF source bytes and recheck pins after restoration. |
| Inventory subprocess | Windows PowerShell 5 policy prevented startup; PowerShell 7 with explicit UTF-8 completed inventory. | Use the bundled runtime and preserve exact diagnostic output. |
| Auto-Adj acquisition | Inspected Archive.org, eServiceInfo, regional searches and public code indexes yielded manuals, locators and a real driver ZIP. | Follow a new binary-bearing W300 Auto-Adj/SeusEX lead; inspect package contents, dependencies and board eligibility. |
| Sony driver candidate | Actual ZIP contains unsigned x86 SYS/DLL, no catalog; INF includes PID 0341. | Keep it for static analysis; obtain and inspect the driver required by the actual service package for the selected OS. |
| Exact W300 GPL packages | Downloaded all five linked packages; they describe CXD4108/ARM926T and Sony USB infrastructure. | Pursue the proprietary function/application handler identified by callback boundaries. |
| Firmware and owner-source acquisition | Repair/archive entries contain manuals, PMB or owner observations; a language answer points to DSC-WX300. | Reuse saved source coverage and qualify a new W300-specific binary/trace from internal model evidence. |
| PDF locator audit | All 512 indirect objects inspected; 46 internal GoTo actions, empty external-reference list, zero parser errors. | Use the documented exact program name and service references to pursue a new package source. |
| IBISS and SeusEX catalogs | Sony portal requires account access; old directory returned 404; catalog redirects led to an old IP landing page. `SeusEX_x64_128200.zip` is a concrete filename lead. | Locate actual payload through a new accessible source; verify architecture, model support and HASP requirements. |
| Local filenames and Git objects | Bounded checks retained their scope and results in local-service reports. | Use a new exact locator instead of repeating the same filename/history searches. |
| SEUS address comparison | W300 UI exposes Block/Page/Address; A330 wrapper uses an 8-bit offset. | Resolve each field's USB encoding from actual W300 implementation; preserve width and avoid guessed truncation. |
| Board/power documentation | Destination Data Write is restricted to Service boards; adjustment setup specifies AC-LS5 and appropriate DC-input cable. | Resolve original-board eligibility and affected-data recovery in the selected implementation. |

## Evidence map

Paths are relative to the repository root. Restore large inputs through [RELEASE_RESTORE.md](RELEASE_RESTORE.md).

- `build/w300/reports/pmca-audit.md`, `legacy-dsc-vs-a330.md`: source paths, side effects, original attachments and offline codec evidence.
- `build/w300/reports/auto-adj-acquisition.md`, `adjustment-collections.md`, `ibiss-acquisition.md`, `seusex-public-acquisition-20260916.md`: actual inspected contents and acquisition routes.
- `build/w300/reports/w300-package-locators.md`, `w300-seus-addressing.md`, `service-board-audit.md`: PDF object inspection, field-width comparison, separate SERIAL/ADJBAK scope, power and reset behavior.
- `build/w300/reports/w300-gpl-audit.md`, `w300-l3-architecture.md`, `sony-ptp-boundary-2008.md`: exact-model source, PRX765105A/A-1543-570-A locators and proprietary-layer boundaries.
- `build/w300/reports/libgphoto-w300-scope.md`, `local-service-package-check.md`, `w300-firmware-followup.md`: bounded alternative-source checks.
- `build/w300/reports/w300-package-source/`, `w300-watermark-archive/`, `w300-owner-source/`: historical Sony catalogs, 4707 distinct successful watermark URL captures, and primary owner posts.
- `build/w300/reports/retained-service-code-scope.md`, `retained-dispatch-analysis.md`, `fallback11/`, `av-receiver/`, `av-page-init/`: static read/write selectors, IPC forwarding, page8/address16, runtime banks, erase/flush behavior.
- `build/w300/reports/g3-host-interface/`, `g3-usb-descriptor/`, `g3-normal-entry/`: authentication, framing, descriptor consumer and service startup. G3 service PID 0x0336 is the comparison target; establish the actual W300 service PID independently.
- `build/w300/reports/g3-module-recovery/`: complete 303816-byte G3 module recovered from the actual image, including double-indirect blocks; preserved 274432-byte extraction is its exact prefix; 9102 relocation entries checked.
- `build/w300/reports/g3-bank-map/`: G3 AV category-5 Areg/Areg2 mapping.
- `build/w300/reports/g3-xs-entry/`, `g3-entry-events/`, `g3-config-read/`: XS grammar, authentication-to-application callback path and category-0 Hreg language/region associations. Match corresponding W300 operations before implementing a camera adapter.
- `build/w300/reports/offline-resumption-checks.json`, `offline-protocol-checks.json`, `offline-xs-checks.json`: historical static-reproduction results. Current revisions use distinct filenames.
- `build/w300/reports/portable-validation.json`: historical release-2 relocation; `portable-validation-r3.json`: historical revision-3 portable validation; revision 4 updates repository research documentation without replacing that ZIP.
- `build/w300/package_manifest.json`: current revision's artifact hashes. `build/w300/manifests/` preserves prior verification checkpoints. `build/w300/reports/release-r3-verification.json` records historical revision-3 publication preparation.

The four canonical submodule pins are preserved. Research uses the separate pinned PMCA checkout under `build/w300/upstream/`, restored from the Release Git bundle. Use [EXECUTION_PLAN.md](EXECUTION_PLAN.md) for the first-contact sequence and the model-specific qualification worklist.

## Use verification gaps to select work

For each property that has not been measured, define an evidence-collection, analysis or device-test task in the execution plan. Establish W300 behavior from W300 code or trustworthy transactions; use G3 comparisons to identify fields and handlers to examine. Continue those comparisons while seeking a new W300 source, and prepare a file-read procedure with defined transfer limits as an alternative to obtaining the adjustment package.

A false hardware-verification flag preserves the current measurement state. It is not an instruction to stop acquisition, implementation preparation or offline checks. Change it only when its corresponding device test supplies the required evidence.
