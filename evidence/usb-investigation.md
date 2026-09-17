> Historical record from the imported September 2026 research. Statements describe that investigation, not the current code or connected hardware. Consult the active guides and evidence index for current scope.

# USB implementation review

Upstream: https://github.com/ma1co/Sony-PMCA-RE/tree/a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0

## Findings

- `pmca/commands/usb.py`, `infoCommand`: calls `SonyUpdaterCamera.init()` in the extended-command path. The app-install path calls `installApp`. This is not an OS-only inventory command.
- `senserShellCommand`: authentication, service-mode transition, repeat authentication, and shell launch. No such operation has been run here.
- `pmca/usb/sony.py`, `SonySenserCamera`: generic product-info, backup, file, memory, terminal commands exist. No W300-specific identifiers or verified readable ranges were found.
- `pmca/platform/backup.py`, `BackupInterface`: language support uses 35 property bytes and generic region profiles; W300 ADJ table lists 25 language columns. This difference is not proof of incompatibility, but these addresses cannot be transferred to W300 without validation.
- `pmca/backup/__init__.py`: parses BK2/BK4 backup files with a header, subsystem/property tables, and checksum. No W300 dump is available to establish that it uses this format. The documented Sony ADJ `.dat` backup is not proven equivalent to PMCA `Backup.bin`.
- `pmca/usb/driver/osx.py`: native transport expects Sony kernel interfaces. Qualify Apple Silicon compatibility against the required native interfaces.
- `pmca/usb/driver/generic/libusb.py`: reset may detach a kernel driver. Passive helper deliberately avoids this backend.

## Next technically meaningful steps

1. Obtain physical USB enumeration and confirm the device is the W300. No connected USB devices were present in the saved baseline.
2. Obtain exact Auto-Adj package for offline transaction/eligibility analysis, or obtain independent W300-specific service-protocol evidence. No raw address scan or guessed property read is warranted.
3. Establish a bounded model-specific read and safe service exit before attempting backup acquisition.
4. Only after actual format/coverage/recovery validation, assess whether a production-board conversion can preserve original data and be reversed.

## Limits

No device service session, backup dump, or native driver test has occurred. Host-only tests validate local file handling, not camera compatibility. A supported destination name alone does not supply an executable conversion method.

## Current continuation guidance

Investigate the property-layout mismatch by identifying the W300 read handler, field widths and backup coverage in W300 code or transactions. Use retained G3 framing/authentication code to design offline response tests while acquiring that W300 evidence. Current identity, bounded read and safe exit are later device checks; they need not precede this static work. Follow the [current execution plan](../docs/w300/EXECUTION_PLAN.md).
