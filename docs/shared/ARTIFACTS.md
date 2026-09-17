# Artifact integrity and storage policy

## Canonical copies

Original inputs live directly under `sources/`. The retained extraction lives under `evidence/extracted_g3/`; numbered section filenames are canonical. Documentation links refer to real files rather than organizational symlinks. Required full local inputs are retained; this project does not depend on a currently available firmware download to run its offline tests.

The [artifact manifest](../../evidence/artifact_manifest.json) records immutable file hashes, genuine firmware link targets, provenance limits, intentional content duplication and derivative relationships. Original supplied research remains source material, not operating authority. The [older source manifest](../../sources/manifest.json) is an acquisition record; its historical paths and availability statements are not a current environment report.

Multiple different firmware filesystem paths may legitimately contain identical bytes. These are preserved with a documented role. Numbered synchronization copies and organizational aliases have no separate firmware role and are removed only after byte or link-target comparison.

## Cross-platform behavior

`.gitattributes` protects source and evidence bytes from line-ending conversion. Active code and documentation use LF. Never repair a firmware hash by normalizing its content or updating the expected digest to match a damaged checkout.

Genuine firmware symlinks retain their Git link type. On Windows without link creation, Git may materialize their target text. The audit checks the recorded target in either representation; a text representation is not an executable filesystem link. No audit follows a firmware absolute link into the host filesystem.

For a Windows checkout, preserve Linux link targets using `git -c core.symlinks=false clone https://github.com/xue9999/DSC-W300.git`. Native Windows symlinks can translate `/proc/...` and relative separators, changing the recorded target bytes. The Windows CI job and fresh-checkout verifier explicitly use the text representation; Linux and macOS retain native links.

## Generated files

Version maintained scripts, reports and manifests under `build/w300/` through explicit ignore exceptions. Restore downloaded inputs and analysis dependencies from the research Release asset; transfer the portable environment using its separate ZIP. Reconstructible environments, caches and duplicate build directories remain local. Put new experimental outputs under ignored build paths or temporary directories. Do not write experimental results into retained sources/evidence. Keep source programs for native probes; compile locally rather than checking in binaries. Ghidra and QEMU are optional separately installed or built tools.

The audit is read-only:

```sh
python tools/repo_audit.py --json
```

The capability report records optional source checkouts, executable availability and emulator observations separately. Investigate hash mismatches, invalid active links and unexplained duplicates against recorded provenance before changing an artifact.

## Research checkpoints

Revision-3 release assets remain reproducible historical inputs; current research instructions and maintained reports on `main` advance through a separate revision-4 manifest. Preserve raw captures and prior measured values when updating report interpretation. If an acquisition route yields no payload, retain that scoped finding and the next source or method to try. Artifact absence should identify an acquisition task rather than suspend unrelated analysis.

## Create a reviewed manifest revision

For the revision-4 update, preserve the revision-3 `build/w300/package_manifest.json` bytes in `build/w300/manifests/package_manifest.pre-editorial-r4.json` before creating the new current manifest. Retain that checkpoint and earlier manifests unchanged. The generator reads an explicit baseline, verifies every prior artifact and records only the reviewed changes and additions.

The command shape below is a template: replace each placeholder with an individually reviewed path, repeat `--change` and `--add` as needed, and omit `--add` when no new artifacts are required. Paths are relative to `build/w300`, use forward slashes and must identify individual files; wildcards and directory-wide enrollment are not supported.

```text
python build/w300/release_manifest.py create --baseline manifests/package_manifest.pre-editorial-r4.json --revision 4 --change <existing-maintained-path> --change <another-maintained-path> --add <new-artifact-path>
python build/w300/release_manifest.py verify
```

`--change` applies to maintained `.md`, `.py` and `.ps1` files at the package root or under `reports/`. Raw captures, firmware, downloads and historical manifests cannot be revised through that option. Any changed prior artifact omitted from the explicit list is rejected; additions must be new explicit paths. The generator validates the proposed manifest before replacing `package_manifest.json` and incorporates the preserved baseline as an artifact. Review its recorded differences against the intended diff; do not update a digest merely to silence an integrity failure. Repository documentation outside `build/w300` is reviewed through Git and repository checks, not enrolled by this package-manifest command.
