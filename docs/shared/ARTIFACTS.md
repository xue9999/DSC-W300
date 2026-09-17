# Artifact integrity and storage policy

## Canonical copies

Original inputs live directly under `sources/`. The retained extraction lives under `evidence/extracted_g3/`; numbered section filenames are canonical. Documentation links refer to real files rather than organizational symlinks. Required full local inputs are retained; this project does not depend on a currently available firmware download to run its offline tests.

The [artifact manifest](../../evidence/artifact_manifest.json) records immutable file hashes, genuine firmware link targets, provenance limits, intentional content duplication and derivative relationships. Original supplied research remains source material, not operating authority. The [older source manifest](../../sources/manifest.json) is an acquisition record; its historical paths and availability statements are not a current environment report.

Multiple different firmware filesystem paths may legitimately contain identical bytes. These are preserved with a documented role. Numbered synchronization copies and organizational aliases have no separate firmware role and are removed only after byte or link-target comparison.

## Cross-platform behavior

`.gitattributes` protects source and evidence bytes from line-ending conversion. Active code and documentation use LF. Never repair a firmware hash by normalizing its content or updating the expected digest to match a damaged checkout.

Genuine firmware symlinks retain their Git link type. On Windows without link creation, Git may materialize their target text. The audit checks the recorded target in either representation; a text representation is not an executable filesystem link. No audit follows a firmware absolute link into the host filesystem.

## Generated files

Version maintained scripts, reports and manifests under `build/w300/` through explicit ignore exceptions. Restore downloaded inputs and analysis dependencies from the research Release asset; transfer the portable environment using its separate ZIP. Reconstructible environments, caches and duplicate build directories remain local. Put new experimental outputs under ignored build paths or temporary directories. Do not write experimental results into retained sources/evidence. Keep source programs for native probes; compile locally rather than checking in binaries. Ghidra and QEMU are optional separately installed or built tools.

The audit is read-only:

```sh
python tools/repo_audit.py --json
```

The capability report records optional source checkouts, executable availability and emulator observations separately. Investigate hash mismatches, invalid active links and unexplained duplicates against recorded provenance before changing an artifact.
