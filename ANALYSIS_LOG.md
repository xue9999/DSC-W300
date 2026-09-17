# Durable research and maintenance guidance

## Goal and working constraints

Prepare persistent English menus on the original Japanese DSC-W300, preserving enclosure, identity, calibration and function. Continue research and engineering offline here; the later camera session uses another Windows 10/11 x64 PC. The analyst owns acquisition and qualification. Hardware writes require the separately authorized stage.

Keep hardware results, static code findings, documentation and simulation distinct. Current workbench commands are selftest, OS inventory and bounded standard SCSI INQUIRY. Derive service operations from W300 code or trustworthy transactions; preserve simulator guards and current-device identity matching.

## Source authority and engineering route

The analyst owns both acquiring evidence and using it to advance the goal. A failed source or missing W300 payload closes only the dependent attempt, not the project. Use the route table in `docs/w300/EXECUTION_PLAN.md`: select a concrete next action, define its expected artifact and evaluation, and move to an independent route when the current one cannot advance. Keep active sequencing in that plan; retain only reusable findings here.

Primary manual: `sources/sony_dsc-w300_adjustment_ver1.3.pdf`, Sony 9-852-287-54. PDF p.11 restricts Destination Data Write to Service boards; resolve applicability to the original board in the implementation. PDF p.36 describes adjustment backup; qualify destination coverage and restoration separately. Package target: `DSC-W300 Auto-Adj Ver_1.3r04.exe`, compatible SeusEX and documented HASP access. Inspect actual binary dependencies before selecting an older OS or VM.

Official W300 GPL: `https://oss.sony.net/Products/Linux/DI/DSC-W300.html`, retained under `build/w300/downloads/w300-gpl/`. It establishes CXD4108/ARM926T and Sony USB infrastructure. Pursue the proprietary camera function/application layer. The acquired Sony/libmtp `DSC-PTPSoftStack.ppt` clarifies this layer. Keep its ARMv6 examples distinct from W300's ARMv5 configuration.

Use PMCA commit `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0` as a transport reference. G3 host framing, authentication, USB descriptors, XS entry and Hreg findings are under `build/w300/reports/`. Confirm corresponding W300 operations before implementing an adapter. Compare legacy A330 page/8-bit-offset encoding explicitly with W300 Block/Page/Address; preserve field widths and derive the mapping from evidence.

The W300 Level-3 manual identifies IC203 PRX765105A and service assembly A-1543-570-A. Use them as acquisition locators; qualify flash layout from actual storage evidence. Reuse search coverage for IBISS, archived SeusEX catalogs, watermark forum and Sony update catalogs. Pursue new concrete locators and inspect payload provenance instead of repeating unchanged queries.

The watermark archive, historical package catalogs and Sony/libmtp architecture presentation have already been inspected; use their dedicated reports as completed coverage. Identify a distinct attachment, archive inventory, repository, firmware image or transaction source for the next acquisition attempt. In parallel, use retained G3 code to resolve specific transfer or language-consumer questions needed by the alternative route. On acquiring W300 implementation evidence, start at the documented Destination Check read handler, then trace the service-board condition and affected-data/commit paths. Revision 1.2r03 corrected destination writing; 1.3r04 corrected Adjustment Mode entry, so compare earlier revisions explicitly. A rate-limit response redirects acquisition to another source; it says nothing about that index's contents. See `build/w300/reports/w300-resumption-20260917.md` for completed coverage.

## Static-analysis conventions

Alternative acquisition route: G3 FileControl pFunc 0xFF01 command 2 opens a named file with O_RDONLY|O_SYNC and sends fstat-sized content; see `build/w300/reports/g3-file-read/`. It could acquire W300 proprietary code after W300 service/transfer qualification, without guessed memory addresses. Prefer a reviewed regular-file candidate over procfs (zero stat size suppresses the body). No directory-list operation was found. Content-read-only does not establish state-free service entry/exit. Preserve raw USB traffic, bound empty/no-progress reads and resolve PMCA padding semantics before implementation. Auto-Adj is not the only possible acquisition route; neither this G3 finding nor the current workbench qualifies a W300 service command.

G3 persistent mode is a separate mutator: `libadj30::StoreSenserMode` writes/removes `/boot/sen/smode`; `LoadSenserMode` maintains `/var/.sen/.smode`. `command000D` mixes get/set selectors. Its existence does not prove ordinary authentication invokes it. Do not infer that reboot/disconnect restores marker state or use marker deletion as a generic reset.

Comparative acquisition shortlist: Sony's official `DSC-W150.html` (explicitly W150/W170), `DSC-T300.html` and `DSC-H50.html` pages under `https://oss.sony.net/Products/Linux/DI/` link the same five GPL package URLs as W300. Reuse the retained packages; this establishes shared published GPL inputs, not identical proprietary firmware. Seek a provenance-qualified updater payload, dump or Auto-Adj binary for these models. Compare destination/language field tables, application consumers, service handlers and persistence against G3; corroborate any proposed W300 mapping with W300-specific evidence. Comparative firmware research is a useful acquisition route, but its output alone does not qualify a W300 hardware operation.

Resolve ELF relocations, PLT/GOT targets and runtime constructors before assigning semantics. G3 AV code implements page8/address16: high address byte selects a segment, low byte its offset. Operation 1 reads; 2/3 mutate direct data; 4 requests flush; 5 requests erase. Trace payload selectors to distinguish reads from writes. Separate USB framing, IPC structures and AV shared bodies.

G3 AV page61/segment0E maps to category-5 Areg/Areg2 through constructor tables. Host language/region fields map to category-0 Hreg/Hreg2 in `g3-config-read/`. Use these as comparison targets. Verify W300 meaning, runtime sizes and persistence independently. Scalar `Bkup_read` ignores an internal read status; validate success separately from returned zero. Treat firmware libraries as data, never host-loaded code.

Comparative acquisition targets named in Sony ADJ documentation are `DSC-W150_W170 Auto-Adj Ver_1.4r05.exe` and `DSC-H50 Auto-Adj Ver_1.4r05.exe`; an AUTO-ADJ-named PDF/RAR is not the program. Use `comparative-language-acquisition/` for exact locators and checked G3 call sites. The G3 `saveRegionInfoData` area contains four field-write calls then a host-regulation flush request; its service caller also calls Registry reset/initialize. Inspect collateral state and region-dependent language construction before claiming a language-only operation. Static calls do not prove completed persistence or W300 equivalence.

## Repository integrity and publication

Active documentation is English and follows findings, relevance to the goal, next action and verification. `AGENTS.md` governs continuation; dated reports supply evidence rather than global stop instructions. Preserve raw responses, test results, machine booleans and source bytes. Editorial Markdown in evidence is maintained separately from immutable artifacts. Preserve prior manifests byte-for-byte as historical checkpoints; create each new revision from an explicit baseline and reviewed change/addition lists. Revision-3 ZIPs remain tied to their original release; revision-4 main does not imply a rebuilt executable.

`sources/` and manifest-listed `evidence/` are immutable inputs. `.gitattributes` protects bytes under Windows autocrlf. Firmware symlinks retain target semantics, including Windows text representations. Remove duplicates only after checking bytes and role. Source submodule pins stay unchanged.

Set `core.symlinks=false` before Windows checkout to preserve Linux targets as exact text. Native Windows symlink creation translates absolute paths and separators, which the byte-integrity audit correctly detects. Keep the strict recorded-target check; use native links on Linux/macOS.

Version maintained `build/w300/` scripts, reports and manifests. Publish downloaded inputs and analysis dependencies in the research Release asset and the Windows executable environment in its own ZIP. Leave environments, caches and duplicate unpacked releases local. See `docs/w300/RELEASE_RESTORE.md` for reconstruction and verification.

## Proven tools and retry rules

`tools/repo_audit.py` is read-only. `tools/run_checks.py` runs required offline tests and before/after integrity checks; required skips fail. `tools/check_fresh_checkout.py` checks a new checkout with Windows-style Git settings. Record optional executable availability, emulator boot and each CI platform separately.

Use bundled PowerShell 7 and explicit UTF-8 for inventory and redirected output. Normalize Windows environment keys before composing subprocess environments. Compare pinned source bytes with Git blobs to detect CRLF conversion. Preserve transaction details for diagnosis.

Build with `build/w300/build_portable.py`. Resolve frozen resources beside the executable. Validate the ZIP after relocation with external development tools removed from PATH. Rebuild Python environments offline from locked wheels. Keep static-analysis dependencies separate from the portable executable.

After an unsuccessful attempt identify whether the cause is environment, dependency, source coverage or model qualification; execute the next available action or an independent route. Reuse completed coverage and repeat an attempt only when its source, hypothesis, method or access changes. Retain TLS verification. Hardware availability limits the hardware stage; continue useful offline acquisition, analysis and preparation. Before reporting the whole task externally blocked, assess the remaining justified routes and name the smallest external input needed. Complete backup/restoration, eligibility and persistence qualification before the separately authorized write stage.
