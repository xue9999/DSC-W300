# Restore the revision-3 research handoff

Git contains maintained code, documentation, reports and manifests at their original paths. The matching GitHub Release supplies two ZIP assets and their SHA-256 sidecars:

- `W300-Workbench-Windows-x64.zip`: the independently runnable identification environment.
- `W300-Research-Offline-r3.zip`: downloaded research inputs, 21 locked environment wheels, Capstone 5.0.6, a pinned PMCA Git bundle, Python 3.12 x64 base runtime and the historical editorial baseline. Every file has a repository-relative path, byte length and SHA-256 in `RESEARCH_MANIFEST.json`.

The preserved baseline and earlier manifests are historical verification records. The published ZIPs retain revision-3 instructions and bytes. Current `main` uses revision-4 research documentation and a new manifest checkpoint; this update does not rebuild those ZIPs. Raw sources, captured replies, machine booleans and prior measured results preserve their meaning.

## Restore on Windows x64

1. Clone `https://github.com/xue9999/DSC-W300.git` and check out the commit targeted by this Release. Keep the four canonical submodule pins as supplied. Standard Git and PowerShell are used for reconstruction; the asset supplies the matching Python runtime and analysis dependencies.
2. Download both assets and checksum files from the same Release. Compare each `Get-FileHash -Algorithm SHA256` result against its sidecar before extraction.
3. From the repository root, extract the research archive. Its entries already include `build/w300/`; do not extract into that subdirectory or flatten the paths. Use a fresh checkout to preserve existing local files:

```powershell
Expand-Archive -LiteralPath 'C:\Transfer\W300-Research-Offline-r3.zip' -DestinationPath '.'
& '.\build\w300\runtime\python312\python.exe' '.\build\w300\release_bundle.py' restore 'C:\Transfer\W300-Research-Offline-r3.zip'
.\build\w300\restore_environment.ps1
```

The restore command validates every archive entry, checks existing bytes and reconstructs `build/w300/upstream/Sony-PMCA-RE` from its offline Git bundle at commit `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0`. The environment script checks Python 3.12 x64, creates `build/w300/venv`, installs locked wheels without network access, installs Capstone into `build/w300/re-tools/site`, checks dependencies and runs the actual workbench selftest. Use a new `-EnvironmentName venv-...` if preserving an existing environment.

4. Run the offline checks from the repository root:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\tools\repo_audit.py' --json
& '.\build\w300\venv\Scripts\python.exe' '.\tools\run_checks.py'
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\release_manifest.py' verify
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\verify_offline_protocol.py' --output offline-protocol-replay-local.json
```

Report scripts resolve their inputs relative to the repository layout. Prior reports contain the original host paths as dated observations; use the current root for commands. Reproduction can refresh derived outputs, so validate the delivered manifest before replay and retain any subsequent report separately.

5. For camera identification, extract the independent workbench ZIP into a writable directory and run `W300Workbench.exe selftest`. Follow `PORTABLE_HANDOFF.md` inside that package. The preparation computer needs no camera connection.

## Build a new portable edition

The research asset retains the official PowerShell 7.4.18 ZIP and locked PyInstaller dependency. From the restored repository:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\build_portable.py' --output '.\build\w300\portable\release-next'
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\validate_portable.py' --archive '.\build\w300\portable\release-next\W300-Workbench-Windows-x64.zip' --destination '.\build\w300\portable\relocation next ąę' --report '.\build\w300\reports\portable-validation-next.json'
```

Each build and validation uses a new output path. Preserve earlier reports and publish new manifest revisions for edited maintained files. The runtime and input checks measure offline preparation; camera communication and language persistence have their own qualification steps in the execution plan.

## Continue from the historical release on current main

The steps above reproduce the revision-3 release at its matching commit. For current research, use a separate current-`main` checkout. Run that checkout's `build/w300/release_bundle.py restore` with Python 3.12 from the restored historical environment, passing `--destination` with the current checkout's absolute path.

The restore command processes the entire research asset; it has no selective-input option. It verifies every entry and every existing destination before writing absent files, then reconstructs the pinned PMCA checkout. The asset contains inputs, wheels, runtime, bundles and `RESTORE_RESEARCH.md`; that last file remains the historical release guide, not the active repository instructions. A differing existing file causes refusal before extraction. Resolve the specific conflict or use a fresh destination rather than overwrite files. Keep the historical release checkout as the reproduction baseline.

Verify current files against the current package manifest before replaying analyses. Acquisition and offline implementation preparation continue according to the current execution plan; the absence of a camera affects only the later device measurements.
