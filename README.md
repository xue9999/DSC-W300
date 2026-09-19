# Sony DSC-W300 and DSC-G3 research laboratory

This repository researches how to keep English menus on the original Japanese DSC-W300 after restart, while preserving its identity, calibration and normal operation. A separate workstream studies DSC-G3 firmware. The repository contains source files, offline analysis, clearly labelled simulations and a portable tool for identifying the W300.

For W300 work, start with the [execution plan](docs/w300/EXECUTION_PLAN.md) and the [agent instructions](AGENTS.md). The analyst must find the evidence needed to implement the change and try another source or method when an attempt cannot advance. Hardware claims require tests on the camera at the appropriate stage.

| Workstream | What is established | What still needs verification |
| --- | --- | --- |
| DSC-W300 language research | Persistent English menus verified on live Japanese DSC-W300 hardware after cold restart; calibration, serial D386002E4438 and normal shooting/playback preserved; double-read baseline files archived | Multi-device community testing across other serials/firmware revisions |
| DSC-G3 firmware | EXE/container parsing, section integrity, filesystem extraction, experimental file modifications | Acceptance of modified firmware by a camera, bootability, image-quality improvement |
| Emulation | Image assembly and QEMU argument generation | Successful camera boot or reproduction of the imaging pipeline |

## Milestone: Persistent English Verified on DSC-W300

The Japanese-market Sony Cyber-shot DSC-W300 (J1 region, serial `D386002E4438`) has been **successfully converted to persistent English menus** using the native Senser service protocol:
- **Command**: `RegionSetting [255, 0x100, 0x8100, 0]` executed over USB Bulk endpoints.
- **Protocol Discovery**: Senser response `status = 0x01` signifies successful completion; the camera automatically commits Category-0 NVM and re-enumerates as PID `054C:033F` (Overseas/Custom).
- **Physical Verification**: Cold restart (battery pull) verified on the camera LCD; English menus active; optical zoom, autofocus, flash, image capture, and playback operate normally.
- **Preservation**: Sensor and optical calibration, hardware serial `D386002E4438`, and factory identity blocks were completely preserved.
- **Complete Guide**: Read the [step-by-step persistent English conversion guide](docs/w300/PERSISTENT_ENGLISH_GUIDE.md).
- **Handoff & Records**: See the [receiving-PC agent handoff](docs/w300/AGENT_HANDOFF.md) and [hardware verification report](docs/w300/VERIFICATION.md).

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

A source document, an observed byte sequence, a simulation and a hardware result provide different kinds of evidence. Each current guide states its evidence and limits. HMAC (a keyed integrity check) verifies container integrity. Verify the source's origin and the effects on hardware separately; use camera observations to establish what an instruction change actually does.

The repository keeps historical sources unchanged where possible. Historical status files and imported research can contain superseded statements; consult the [evidence index](evidence/README.md) before treating them as instructions. Removed misleading guides remain in Git history.

Default tests and repository audits run offline. Native USB probes are active research utilities. Follow the bounded identification procedure for the first device session and complete model-specific qualification before a separately authorized write.

The [cleanup verification report](CLEANUP_REPORT.md) records the checks performed during cleanup and the remaining verification work.

## Complete research handoff

The historical [revision-3 GitHub Release](https://github.com/xue9999/DSC-W300/releases/tag/w300-research-r3) supplies the Windows x64 identification workbench and offline research inputs with SHA-256 inventories. Follow the [restoration guide](docs/w300/RELEASE_RESTORE.md) for its matching checkout and dependencies. The current working tree uses editorial revision 5, which clarifies the research guidance and reports. The revision-3 ZIPs retain their original contents and manifests; the documentation changes do not add service commands to that executable.
