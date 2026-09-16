# CEE8 procedure repair: partial, hardware conversion not achieved

## Completed host changes

- `tools/w300_service_tool.py detect` delegates to passive OS inventory and recognizes the observed DSC-W300 product descriptor without assuming PID 0340/031b or opening libusb.
- Dry-run, including direct controller construction, uses an offline mock and never initializes USB transport. Simulation logs are explicitly labelled.
- Live service CLI operations are rejected before constructing the controller. Controller transport entry points also reject operation without the offline model.
- Incomplete Senser payloads are rejected instead of being accepted as complete property values.
- Removed the fallback that attempted 35 property writes after a rejected language-mask write without validating responses.
- Protocol documentation now distinguishes simulation assumptions from hardware evidence.

## Additional source contradictions

`sources/Sony-PMCA-RE/pmca/platform/backup.py` defines 0x01070148 as `palNtscSelector`, not PAL output mode. Its model-code field is five bytes; the experiment treats it as a model-name string. `getRegion()` obtains the region from backup status, not from the experiment's invented destination property. None of these generic PMCA paths establish W300 compatibility.

`sources/Sony-PMCA-RE/pmca/commands/usb.py:senserShellCommand` sends start and authenticates before waiting for service re-enumeration, then authenticates on the service interface. The experimental transport waited for re-enumeration before its first authentication. Correcting this ordering alone cannot establish model compatibility or justify destination writes.

## Verification

`python3 -m unittest discover -s tools -p 'test_w300*py'`: 124 tests passed. New regression tests ensure USB backend construction is impossible during dry-run and rejected live commands, mock passive inventory accepts PID 0341, and incomplete responses fail. The existing truncation test was corrected to require rejection until the entire response is reconstructed.

CLI passive detection again reported Sony DSC-W300 at 054c:0341. CLI dry-run completed solely against a simulated J1 device; the printed J1 destination and other simulated properties are not readings from the physical camera. No hardware service command or camera write was performed.

## External dependency

The user has confirmed no exact Auto-Adj package or installed service system is available and requested writing or simulating a replacement. The existing simulator was run through its full mock conversion; output is `cee8-offline-simulation-20260916.txt`. This is a successful execution of the assumed model only, not evidence for its assumptions and not a physical language change.

Additional passive `ioreg` inspection identifies the actual DSC-W300 interface as class 8, subclass 5, protocol 80 (0x50), with `IOUSBMassStorageInterfaceNub` as exclusive owner. Thus the connected device IS already in Mass Storage; no user mode change is justified from the PID difference. No service traffic was sent to obtain this finding.

Searches for the exact model plus Senser, PMCA, Seus, Auto-Adj, 1.3r04 and CEE8 did not recover a qualified package or independent W300 transaction capture. The official Sony support page lists PlayMemories Home, not the adjustment package:
https://www.sony.com/electronics/support/compact-cameras-dsc-w-series/dsc-w300

The exact Auto-Adj package or independently documented W300 service transactions remain necessary to establish the region encoding and recovery route. Availability of the package alone would not prove retail-board conversion eligibility. Physical English persistence after restart remains unachieved.
