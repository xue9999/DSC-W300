# Sony DSC-W300 and DSC-G3 research laboratory

This repository supplies preserved sources, reproducible offline firmware analysis, labelled simulations and a portable W300 identification environment. Continue from these verified foundations to qualify each model-specific hardware operation.

| Workstream | Established foundation | Next qualification |
| --- | --- | --- |
| DSC-W300 language research | Sony service-manual findings, historical USB observations, offline service simulator | Retail-board destination encoding, recoverable conversion, persistent English on an actual camera |
| DSC-G3 firmware | EXE/container parsing, section integrity, filesystem extraction, experimental file modifications | Acceptance of modified firmware by a camera, bootability, image-quality improvement |
| Emulation | Image assembly and QEMU argument generation | Successful camera boot or reproduction of the imaging pipeline |

## Start here

Python 3.10 or later and Git are required for repository checks. Offline Python tools use the standard library. Windows, Linux and macOS are CI targets; a configured workflow is not evidence of a completed run. Optional upstream submodules and QEMU are not prerequisites for offline tests.

```sh
python tools/repo_audit.py --json
python tools/run_checks.py
python tools/cxd4108_emulator/qemu_launcher.py status
```

The check runner writes `build/test-results.json` with environment, revision, working-tree state, failures, skips and artifact audits. Any skipped required test makes that report fail. For tests alone:

```sh
python -m unittest discover -s tools -p "test_*.py" -v
```

## Repository map

| Directory | Purpose |
| --- | --- |
| `sources/` | Byte-preserved inputs, original research and pinned optional upstreams |
| `evidence/` | Historical observations, one retained extracted G3 tree and artifact integrity manifest |
| `docs/` | Current findings and qualification steps, grouped by camera and shared tooling |
| `tools/` | Offline tools, tests and separately identified hardware-probe source code |
| `build/` | Versioned W300 scripts/reports; Release materials and local generated output |

Read [W300 findings](docs/w300/README.md), [G3 offline tools](docs/g3/README.md), [artifact policy](docs/shared/ARTIFACTS.md), [model boundaries](docs/shared/CROSS_PLATFORM_ARCHITECTURE.md), [emulation and optional tools](docs/shared/EMULATION_AND_OPENMEMORIES_CI.md), and [test contracts](TEST_INFRA.md).

## Evidence rules

A source document, an observed byte sequence, a simulation and a hardware result are different kinds of evidence. Each current guide identifies its basis and limits. HMAC verifies container integrity. Qualify provenance and hardware effects separately, using device observations to connect an instruction change with its behavior.

The repository keeps historical sources unchanged where possible. Historical status files and imported research can contain superseded statements; consult the [evidence index](evidence/README.md) before treating them as instructions. Removed misleading guides remain in Git history.

Default tests and repository audits run offline. Native USB probes are active research utilities. Follow the bounded identification procedure for the first device session and complete model-specific qualification before a separately authorized write.

The [cleanup verification report](CLEANUP_REPORT.md) records the checks actually performed during the repository cleanup and the next qualification steps.

## Complete research handoff

The matching [GitHub Release](https://github.com/xue9999/DSC-W300/releases/tag/w300-research-r3) supplies the Windows x64 workbench and offline research inputs with SHA-256 inventories. Follow the [restoration guide](docs/w300/RELEASE_RESTORE.md) to rebuild the original directory layout and run checks from retained dependencies. Revision 3 includes constructive report prose, historical manifests and the separately verified portable environment.
