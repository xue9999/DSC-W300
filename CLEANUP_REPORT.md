# Repository cleanup verification report

This report records the local cleanup completed on 2026-09-16. It records the checks performed within that cleanup scope; it does not establish permanent readiness or validate hardware operations.

## Delivered changes

- Restored 88 artifacts affected by checkout line-ending conversion from exact Git bytes. Added attributes that preserve sources and firmware evidence with Windows autocrlf enabled.
- Removed 428 verified artifact aliases, redundant copies and compiled/tool binaries. Preserved originals, one extracted firmware set, genuine firmware symlinks and source code for native probes. Removed a further 13 superseded editorial paths; all historical versions remain in Git.
- Added a manifest covering 821 immutable artifacts, including symlink targets, provenance limits and 13 explained groups of intentional identical content.
- Replaced misleading operational guides with English model-specific documentation and an evidence index. Historical records are labelled; original research is not treated as operational authority.
- Restricted W300 service tooling to labelled simulation or refusal; removed false calibration qualification, estimated photographic measurements and G3 patching presented as W300 functionality.
- Strengthened G3 generators with trusted full-source identity, verification of all input sections, exact isolated changes, preserved manifest/container padding, and verified atomic output publication. Source/evidence output collisions are refused.
- Regenerated the two retained G3 experimental images after the earlier versions failed the new exact-change checks. Their new hashes, commands and limits are recorded in the artifact manifest.
- Added read-only repository auditing, environment-specific test reporting, fresh-checkout verification and a four-job CI configuration. Corrected optional dependency and QEMU availability reporting.

## Verification performed

| Check | Observed result |
| --- | --- |
| Windows local required suite | 252 tests, 0 failures, 0 errors, 0 skips |
| Fresh checkout required suite | 252 tests, 0 failures, 0 errors, 0 skips |
| Checkout settings | `core.autocrlf=true`, `core.symlinks=false` |
| Artifact/link audit before and after each suite | Passed; 821 artifacts checked |
| Fresh extraction comparison | 794 retained payload files/link targets matched; no mismatches |
| Original source hashes with historical acquisition pins | All three recorded PDF/research-source hashes matched |
| Original repository index | Unchanged by fresh-checkout verification |

Host: `Windows-11-10.0.26200-SP0`. Python: `3.13.14`.

Base revision: `5dbb647e22ddd32cf108fe8daf9bb0a71b61a1a8`. At that recorded checkpoint the implementation was an uncommitted local change. Tested snapshot tree: `c20a5b0e8106b9771618d5e3da5b14f0b4979397`. This report and its README navigation link were added after the test snapshot; code and artifacts were not changed afterward.

The generated local reports are `build/test-results.json`, `build/fresh-checkout-results.json`, `build/extraction-comparison.json` and `build/pre-cleanup-inventory.json`. They are intentionally ignored outputs. The fresh checkout is retained at `C:\Users\apara01\AppData\Local\Temp\dsc-fresh-check-0iqlmclu\checkout` for inspection.

## Next research and qualification

CI is configured for Windows/Linux/macOS with Python 3.13, plus Linux with Python 3.10. Those hosted CI jobs were not executed or published during this local work. Only the Windows reports above support platform execution claims.

All four optional submodules remain uninitialized; their commits remain pinned. QEMU is unavailable. No emulator boot, macOS native compilation, active network gateway or camera operation was performed.

Continue W300 work through the acquisition and analysis routes in the [current execution plan](docs/w300/EXECUTION_PLAN.md). Use verified G3 container changes as the baseline for separate camera acceptance, installation, recovery and image-quality checks. This dated cleanup checkpoint preceded Git publication; its observations remain historical. The revision-3 Release handoff records that later release. The current working tree contains editorial revision 5 of the research guidance.

## Reproduce

```sh
python tools/repo_audit.py --json
python tools/run_checks.py
python tools/check_fresh_checkout.py
```

See [repository guide](README.md), [artifact policy](docs/shared/ARTIFACTS.md), [test contracts](TEST_INFRA.md) and [artifact manifest](evidence/artifact_manifest.json).
