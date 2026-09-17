> Historical record from the imported September 2026 research. Statements describe that investigation, not the current code or connected hardware. Consult the active guides and evidence index for current scope.

# CEE8 hardware preflight review

## Actual hardware observation

`usb-cee8-preflight-20260916.json` records a fresh macOS registry observation of Sony DSC-W300, VID:PID `054c:0341`. This confirms the USB product descriptor, not the destination, board eligibility or service protocol. No device handle was opened and no vendor, service, configuration or flash commands were sent during this review. Current destination remains unknown.

## Findings and qualification actions

- `tools/w300_service_tool.py:detect_device` accepts retail PIDs `0340` and `031b`, not the observed `0341`. Adding a PID alone would not establish protocol compatibility.
- The tool writes ASCII `CEE8` to property `0x00e70001` and a language profile based on `0x010d008f`. No independent W300 hardware capture or exact Auto-Adj binary was found establishing this destination encoding or property map. The language property addresses occur in generic PMCA code; this is not W300 validation.
- `sources/sony_dsc-w300_adjustment_ver1.3.txt:567-568` restricts Destination Data Write to Service boards. The tool's assertion that generic ID1 protection clearing unlocks retail W300 destination writing is not established by that manual.
- Mock roundtrip tests use the same assumed properties as the writer. They cannot establish physical-camera compatibility or recoverability.
- Live `full-cycle --dry-run` still switches mode, authenticates, reads assumed properties and resets the device. It must not be used as passive preflight.
- `run_full_cycle` does not persist a baseline backup before writing. Its readback occurs before reset and therefore does not prove persistence after restart.

## Disposition and next prerequisite

CEE8 conversion has not been performed. Passive preflight and local implementation/source review are complete. The next prerequisite is the exact `DSC-W300 Auto-Adj Ver_1.3r04.exe` package with its service dependencies for offline analysis, or independently documented W300-specific service transactions. Establish a bounded read, safe exit, destination encoding, retail-board eligibility and recoverable backup before performing a physical write. The available G3 updater is not a W300 substitute.

## Current continuation guidance

Use these findings to replace the former writer's assumptions with verified W300 behavior: resolve destination encoding and original-board eligibility, then specify the affected-data backup and post-restart persistence checks. Acquire the needed handler from Auto-Adj, W300 firmware or trustworthy W300 transactions. The retained G3 updater supplies targeted comparisons while this acquisition proceeds; the [current execution plan](../../docs/w300/EXECUTION_PLAN.md) defines the alternative routes.
