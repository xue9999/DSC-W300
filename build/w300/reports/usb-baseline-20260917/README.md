# DSC-W300 USB reference baseline — 17 September 2026

This is a live, read-only identification and host-access baseline for the connected Sony DSC-W300. It captures all device properties returned by the selected Windows queries and all configuration/interface/endpoint descriptor fields exposed by libusb enumeration. It is not a complete camera-memory dump or a recovery backup: Windows denied storage access, and internal camera data was not exposed by these methods.

Capture started at 14:59:06 UTC (16:59:06 Europe/Warsaw), with supplementary device-node capture later in the same session. Exact timestamps are in each JSON file. Host: Windows 11 Enterprise x64, build 26200; PowerShell 7.6.5; non-elevated process.

## Confirmed current identity and USB configuration

| Field | Observed value |
| --- | --- |
| Windows bus-reported model | DSC-W300 |
| VID / PID | 054C / 0341 |
| Windows USB instance serial | D386002E4438 |
| USB instance | `USB\VID_054C&PID_0341\D386002E4438` |
| Storage child | `USBSTOR\DISK&VEN_SONY&PROD_DSC&REV_1.00\D386002E4438&0` |
| Device / disk node status | OK / OK |
| USB specification / device revision | bcdUSB 0x0200 / bcdDevice 0x0100 |
| Control endpoint maximum packet | 64 bytes |
| Configuration | 1; total length 32 bytes; one interface |
| Power declaration | Self-powered; bMaxPower 1 (2 mA in USB 2.0 units) |
| Interface | 0, alternate 0; class 0x08, subclass 0x05, protocol 0x50 |
| Bulk IN | Endpoint 0x81; maximum packet 512 bytes; interval 0 |
| Bulk OUT | Endpoint 0x02; maximum packet 512 bytes; interval 0 |
| libusb topology | Bus 1, address 3, port path [4]; speed enum 3 |
| Windows location | Port_#0004.Hub_#0002 |
| Windows topology | `PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(4)` |
| USB driver | Microsoft USBSTOR; usbstor.inf; 10.0.26100.9444 |
| Disk driver | Microsoft disk; disk.inf; 10.0.26100.8972 |

The revision values above are USB/storage identification values. They do not establish the installed camera application firmware version. USB address and host topology can change after reconnection. The serial is obtained from the current Windows device instance; direct USB string retrieval failed.

## Access findings relevant to further USB work

- Windows exposes a removable D: logical drive but returns null filesystem, capacity, free space, label and volume serial. Neither Win32_DiskDrive nor Get-Disk returned the camera in the filtered storage query. This does not prove that the camera has no media.
- A directory read of D: returned access denied, followed by path-not-found. No directory listing, photograph metadata, media hashes or media image was acquired.
- The fresh standard SCSI INQUIRY attempt failed with `(5, 'CreateFile', 'Access is denied.')`. No SCSI response or submitted transaction was recorded. The existing workbench requests a read/write-capable Windows handle for its input-only INQUIRY implementation; opening that handle failed before an INQUIRY command was sent.
- The associated WPD filesystem node has problem code 10 and problem status 2147942405 (0x80070005). The USB, disk and volume PnP nodes remain present. Full related-node properties are retained separately.
- USB device stack includes USBSTOR, CSDeviceControl, ACPI and USBHUB3. Disk stack includes csadc, partmgr, disk and USBSTOR. These are relevant host-environment facts; this capture does not establish which component caused the access denial. No security policy or driver was disabled or changed.
- libusb enumeration returned the device, configuration, interface and endpoint fields. Manufacturer, product and serial string reads each failed with `NotImplementedError: Operation not supported or unimplemented on this platform`. No interface was claimed; no configuration, reset or vendor request was issued.

## Captured files

- [windows-inventory.json](windows-inventory.json): all returned PnP properties for the selected USB/storage nodes and their ancestor chain; signed-driver details; registry identity values; host and storage visibility; PnPUtil interfaces, relations, stacks and services; final identity check. Host volumes are included as context, not camera storage.
- [usb-descriptors.json](usb-descriptors.json): enumerated descriptor fields, extra-descriptor bytes, topology and exact string-read failures. This is a structured enumeration capture, not a USB packet trace.
- [storage-and-related-nodes.json](storage-and-related-nodes.json): complete returned properties for all present nodes containing the camera serial, including WPD and volume nodes; directory-access observation from this session.
- [scsi-inquiry.json](scsi-inquiry.json): exact fresh INQUIRY attempt result, copied without modification from the workbench report.
- [SHA256SUMS.json](SHA256SUMS.json): byte lengths and SHA-256 checksums for baseline files other than this checksum file itself.

## Not acquired

Internal firmware and flash, EEPROM/NVRAM, destination/region, enabled languages, current menu language, calibration, settings, internal logs, battery state, sensor state, shutter count, media capacity and media contents remain unverified. No service-mode entry, authentication, undocumented operation, camera-setting change or camera-write command was performed. Normal Windows enumeration can issue its own protocol traffic; this session did not capture that traffic.

For further USB intervention, first recheck model, VID/PID, current serial, node status and driver stack against this baseline. Resolve the Windows storage-access failure before relying on the standard INQUIRY route. Obtain separately validated W300-specific reads and a restorable backup before any internal-data modification. The access failure is not evidence of camera incompatibility and this baseline is not sufficient to restore camera internals.

## Reproduce a new capture

From the repository root, use a fresh output directory:

```powershell
.\tools\capture_windows_usb_baseline.ps1 -InstanceId 'USB\VID_054C&PID_0341\D386002E4438' -OutputDirectory '.\build\w300\reports\usb-baseline-NEW'
.\build\w300\venv\Scripts\python.exe .\tools\capture_usb_descriptors.py --output .\build\w300\reports\usb-baseline-NEW\usb-descriptors.json
.\build\w300\run.ps1 -Action Inquiry -Serial D386002E4438
```

Use the current serial from a fresh inventory. Both new capture helpers refuse an existing output destination. The descriptor helper identifies one VID/PID match; correlate its bus/port with the Windows model/serial capture when USB strings are unavailable. Supplementary WPD/volume properties in this baseline were collected separately by selecting present PnP nodes containing the current serial.
