# DSC-W300: preparation and verification

The active task is **still-image noise reduction**. Start with the
[current execution plan](EXECUTION_PLAN.md) and
[stills NR evidence guide](STILLS_NR_DISABLE_GUIDE.md). The previous two-byte
Asys candidate skips CNR filtering and RGB conversion while leaving RAWNR
gates unchanged; it does not establish NR off. Reproduce
the corrected mapping with `python tools/w300_stills_nr.py analyze-av`.
The language material below belongs to the earlier workstream.

The goal of enabling persistent English menus on the original Japanese DSC-W300 (model J1, serial `D386002E4438`) has been **successfully achieved and verified on live hardware**. The camera was transitioned to custom region 255 with initial language English using native Senser `RegionSetting [255, 0x100, 0x8100, 0]`. English menus persist across cold power cycles, with calibration, hardware serial, and optical/playback functions 100% intact.

For full technical details and user instructions:
- [Persistent English Conversion Guide](PERSISTENT_ENGLISH_GUIDE.md): step-by-step instructions for WinUSB, Zadig, and console execution.
- [Execution Plan](EXECUTION_PLAN.md): engineering routes, bytecode analysis, and protocol specifications.
- [Verification Record](VERIFICATION.md): live hardware trial results, Senser responses, and physical inspection records.
- [Agent Handoff](AGENT_HANDOFF.md): procedure followed on the receiving Windows PC.

## Primary findings and next engineering steps

The [Sony adjustment manual](../../sources/sony_dsc-w300_adjustment_ver1.3.pdf), document 9-852-287-54, names `DSC-W300 Auto-Adj Ver_1.3r04.exe`, SeusEX and HASP. PDF p.11 (printed 6-10) limits Destination Data Write to Service boards. Find and inspect the package to determine whether that condition permits the operation on the original board. If a source yields no package, try a W300 firmware or transaction source, or prepare the file-read route for separate validation. The adjustment package is one possible source of the required W300 evidence.

Destination codes identify regional configurations. CEE8 starts in English and includes Polish; J1 is Japanese-only. U2 offers English/NTSC, while CEE8 uses PAL. First look for an operation that changes only the language, and establish the destination's byte encoding from W300 evidence. PDF p.36 covers adjustment backups; verify backup and restoration of every data region affected by the selected operation.

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

## Keep the next step actionable

A missing package limits analysis of that package; it does not suspend the project. Use the execution plan to choose a source-acquisition task, a specific W300/G3 comparison, or preparation of bounded file acquisition. Record the question, expected evidence and acceptance check before each attempt. When a source is exhausted, retain its result and move to a different source or method. Reopen it only after a concrete change such as a new locator, accessible archive snapshot or supplied file.

Without a camera on this computer, continue acquiring evidence, analyzing code and running offline checks. Prepare a verified procedure for the receiving PC. The later camera session must record device identity, what data can be recovered and whether English menus remain after restart.

The revision-3 ZIP remains the historical executable release. The current working tree contains editorial revision 5; the revised text and manifest do not represent a rebuilt ZIP or a new hardware result.
