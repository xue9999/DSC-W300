# Durable research and maintenance guidance

## Goal and working constraints

Prepare persistent English menus on the original Japanese DSC-W300, preserving enclosure, identity, calibration and function. Continue research and engineering offline here; the later camera session uses another Windows 10/11 x64 PC. The analyst owns acquisition and qualification. Hardware writes require the separately authorized stage.

Keep hardware results, static code findings, documentation and simulation distinct. Current workbench commands are selftest, OS inventory and bounded standard SCSI INQUIRY. Derive service operations from W300 code or trustworthy transactions; preserve simulator guards and current-device identity matching.

## Source authority and engineering route

Primary manual: `sources/sony_dsc-w300_adjustment_ver1.3.pdf`, Sony 9-852-287-54. PDF p.11 restricts Destination Data Write to Service boards; resolve applicability to the original board in the implementation. PDF p.36 describes adjustment backup; qualify destination coverage and restoration separately. Package target: `DSC-W300 Auto-Adj Ver_1.3r04.exe`, compatible SeusEX and documented HASP access. Inspect actual binary dependencies before selecting an older OS or VM.

Official W300 GPL: `https://oss.sony.net/Products/Linux/DI/DSC-W300.html`, retained under `build/w300/downloads/w300-gpl/`. It establishes CXD4108/ARM926T and Sony USB infrastructure. Pursue the proprietary camera function/application layer. The acquired Sony/libmtp `DSC-PTPSoftStack.ppt` clarifies this layer. Keep its ARMv6 examples distinct from W300's ARMv5 configuration.

Use PMCA commit `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0` as a transport reference. G3 host framing, authentication, USB descriptors, XS entry and Hreg findings are under `build/w300/reports/`. Confirm corresponding W300 operations before implementing an adapter. Compare legacy A330 page/8-bit-offset encoding explicitly with W300 Block/Page/Address; preserve field widths and derive the mapping from evidence.

The W300 Level-3 manual identifies IC203 PRX765105A and service assembly A-1543-570-A. Use them as acquisition locators; qualify flash layout from actual storage evidence. Reuse search coverage for IBISS, archived SeusEX catalogs, watermark forum and Sony update catalogs. Pursue new concrete locators and inspect payload provenance instead of repeating unchanged queries.

## Static-analysis conventions

Resolve ELF relocations, PLT/GOT targets and runtime constructors before assigning semantics. G3 AV code implements page8/address16: high address byte selects a segment, low byte its offset. Operation 1 reads; 2/3 mutate direct data; 4 requests flush; 5 requests erase. Trace payload selectors to distinguish reads from writes. Separate USB framing, IPC structures and AV shared bodies.

G3 AV page61/segment0E maps to category-5 Areg/Areg2 through constructor tables. Host language/region fields map to category-0 Hreg/Hreg2 in `g3-config-read/`. Use these as comparison targets. Verify W300 meaning, runtime sizes and persistence independently. Scalar `Bkup_read` ignores an internal read status; validate success separately from returned zero. Treat firmware libraries as data, never host-loaded code.

## Repository integrity and publication

Active documentation is English and follows completed work, findings, next action and verification. Preserve raw responses, test results, machine booleans and source bytes. Editorial Markdown in evidence is maintained separately from immutable artifacts. Preserve prior manifests as historical checkpoints; publish a new manifest revision for edited reports.

`sources/` and manifest-listed `evidence/` are immutable inputs. `.gitattributes` protects bytes under Windows autocrlf. Firmware symlinks retain target semantics, including Windows text representations. Remove duplicates only after checking bytes and role. Source submodule pins stay unchanged.

Version maintained `build/w300/` scripts, reports and manifests. Publish downloaded inputs and analysis dependencies in the research Release asset and the Windows executable environment in its own ZIP. Leave environments, caches and duplicate unpacked releases local. See `docs/w300/RELEASE_RESTORE.md` for reconstruction and verification.

## Proven tools and retry rules

`tools/repo_audit.py` is read-only. `tools/run_checks.py` runs required offline tests and before/after integrity checks; required skips fail. `tools/check_fresh_checkout.py` checks a new checkout with Windows-style Git settings. Record optional executable availability, emulator boot and each CI platform separately.

Use bundled PowerShell 7 and explicit UTF-8 for inventory and redirected output. Normalize Windows environment keys before composing subprocess environments. Compare pinned source bytes with Git blobs to detect CRLF conversion. Preserve transaction details for diagnosis.

Build with `build/w300/build_portable.py`. Resolve frozen resources beside the executable. Validate the ZIP after relocation with external development tools removed from PATH. Rebuild Python environments offline from locked wheels. Keep static-analysis dependencies separate from the portable executable.

After an unsuccessful attempt identify whether the cause is environment, dependency, source coverage or model qualification; select the next action accordingly. Retain TLS verification. Require fresh evidence before repeating an acquisition route. Complete backup/restoration, eligibility and persistence qualification before the separately authorized write stage.
