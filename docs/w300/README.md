# DSC-W300: preparation and qualification

The goal is persistent English menus on the original Japanese DSC-W300, with identity, calibration and function preserved. Start with the [execution plan](EXECUTION_PLAN.md), [verified research](VERIFICATION.md), and [portable handoff](PORTABLE_HANDOFF.md). The prepared executable provides selftest, OS inventory and standard INQUIRY. Its hardware-language flags remain `false` pending model-specific qualification.

Continue offline analysis on this computer; use the transferable package for a later session on Windows 10/11 x64. The [Release restoration guide](RELEASE_RESTORE.md) reconstructs the research layout.

## Primary findings and next engineering steps

The [Sony adjustment manual](../../sources/sony_dsc-w300_adjustment_ver1.3.pdf), document 9-852-287-54, names `DSC-W300 Auto-Adj Ver_1.3r04.exe`, SeusEX and HASP. PDF p.11 (printed 6-10) limits Destination Data Write to Service boards. Acquire the actual package through a new concrete locator, inspect that condition and resolve applicability to the original board.

CEE8 starts in English and includes Polish; J1 is Japanese-only. U2 offers English/NTSC, while CEE8 uses PAL. Identify a language-only operation first and derive destination encoding from W300 evidence. PDF p.36 covers adjustment backups; establish backup and restoration of every region affected by the selected operation.

The pinned PMCA implementation, exact W300 GPL packages and comparative G3 decoding provide transport and architecture references. Match their operations against W300 code or reliable transactions before adding service commands. Acquisition reports record inspected sources so the next analyst can pursue new leads efficiently.

## Offline tools

```sh
python tools/w300_service_tool.py full-cycle --dry-run
python tools/w300_stills_nr.py --help
python tools/w300_evidence.py --help
```

`w300_service_tool.py` models assumed states and packets in memory and labels its outputs as simulation. Preserve its live-command refusal. Use actual W300 evidence to implement the separate hardware tool.

`w300_stills_nr.py` provides byte inventory and a hypothetical settings description. Qualify backup coverage and image-quality effects through their own measurements. Its calibration/DSP guards remain active. Use the retained G3 AV binary as comparative material through the [G3 tools](../g3/README.md).

`w300_evidence.py compare` compares complete files offline. Its macOS inventory reads `ioreg`; use the Windows workbench for Windows PnP inventory. Treat historical USB descriptors as dated observations and match current identity before each device session.
