# G3 Senser USB descriptor and activation-request binding

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

## Result

The retained **G3** library has a concrete Senser descriptor-selection path for **VID 0x054C / PID 0x0336**. It is connected to `libsencore`'s requested internal device ID 13, the actual `sen_desc_tbl` ELF symbol/relocations, and the `gadgetcore` start ioctl. The model-specific G3 GPL header and descriptor consumer establish that the two halfwords are USB `idVendor` / `idProduct`. This is more than an isolated occurrence of `0336`.

The retained G3 Senser driver also matches the exact two 8-byte control requests used by pinned PMCA's `StartSenser` and `StopSenser` methods. The request patterns are supplied by `libusb.so` to the driver, then compared by the registered vendor callback. A successful match stops other gadget function drivers and queues the matched index as an event.

These findings resolve the **static G3 PID-branch qualification** missing from the preceding host-interface audit: the selected G3 Senser descriptor is the PID for which PMCA constructs a 1024-byte challenge-plus-key input. They do not constitute live USB enumeration, authentication, proof of a successful transition from normal camera mass-storage mode, or any W300 compatibility result.

There are **two distinct PMCA authentication stages**. In pinned `pmca/commands/usb.py:656` onwards, `senserShellCommand` first starts/authenticates a normal `SonyMscExtCmdDevice`, waits for Senser enumeration, and then starts/authenticates the `SonySenserDevice`. When the first device's PID is not `0x0336`, the authentication helper hashes only `data[:4]`. The 512+512-byte G3 match established here qualifies the static configuration for the **second stage**. It does not qualify the first stage or the normal-MSC-to-Senser transition.

## Inputs and address notation

All binary inputs remain in `evidence/` and are read as data. `inspect_usb.py` and the kernel scripts check their retained manifest hashes. The G3 provenance limitations in `evidence/g3_acquisition.md` continue to apply.

- `evidence/extracted_g3/archives_unpacked/lib/lib/libusb.so`
- `evidence/extracted_g3/archives_unpacked/lib/lib/libsencore.so`
- `evidence/extracted_g3/rootfs/initrd/bin/unified_drv.ko`
- `evidence/extracted_g3/rootfs/initrd/bin/unified_drv2.ko`

Library addresses below are ELF virtual addresses, not addresses for a W300 command. The shared libraries' `.text` addresses also equal their file offsets. For their data sections the mapping is different and the evidence JSON records both. Kernel addresses below are explicitly `.text` **section offsets of an ET_REL object**, not linked runtime addresses. Use the retained relocation annotations for its branches.

## DID 13 to the USB device descriptor

1. In `libsencore.so`, `Usb::initialize_usb_interface` calls `usbif_initialize` at `0x8A14` to obtain its interface. `Usb::handle_input`, in its connection-event path, sets `r1 = 13` at `0x8514` and calls that interface's function at offset `+0x0C` (`0x8518–0x851C`). This is an internal device selection number, distinct from the USB PID.
2. In `libusb.so`, `usbif_initialize` copies its `0xA4`-byte API template from ELF VA `0x187BC` at `0x5C7C–0x5C8C`. The template slot `+0x0C` holds `0x6314`, with a retained `R_ARM_RELATIVE` relocation. That wrapper calls `usbproduct_conv_did` and then `CUsbSvc::start` at `0x6418`. The converter only remaps inputs 0 and 12 in the inspected drive-type branches; input 13 is retained. This describes the successful code path, not a claim that every preceding allocation/registration succeeds on hardware.
3. `CUsbSvc::start` stores an accepted DID at object offset `+0xA0` at `0x9584`; its bound includes 13. `CUsbSvc::createGadget` subsequently loads that state and indexes the actual `ptbl_did` symbol (`0xA278–0xA284`). Its GOT reference resolves through a retained `R_ARM_GLOB_DAT` relocation.
4. `ptbl_did` is VA `0x193E4`. Entry 13 at VA `0x19418` points, through `R_ARM_RELATIVE`, to record `0x19598`. That record begins with internal ID 13. Its field at `+0x0C`, VA `0x195A4`, has an `R_ARM_ABS32` relocation to **`sen_desc_tbl`**, VA `0x18AC0`, file offset `0x10AC0`.
5. `createGadget` loads the record's `+0x0C` pointer at `0xA28C`, places it first in a 12-byte argument structure, and passes the structure through **ioctl `0x400CE203`** at `0xA308`. The file descriptor came from opening **`/dev/usb/gadgetcore`**, with the string pointer resolved from the same library's actual address mapping.
6. The separate, official [G3 GPL distribution](https://oss.sony.net/Products/Linux/DI/DSC-G3.html) supplies `usb_gadgetcore_start_info` and `USB_IOC_GADGETCORE_START` in `usb_gadgetcore.h:72–100`. With its 32-bit pointer ABI this is the same 12-byte structure and ioctl. Its `_usb_gadget_desc_table` at lines 211–223 contains two 16-byte speed records followed by vendor/product halfwords at `+0x20/+0x22`. These bytes in `sen_desc_tbl` are `4C 05 36 03`, therefore **054C:0336**.
7. The G3 GPL `usb_gcore_main.c:189–237` handles the start operation, saves this descriptor table and connects the gadget. `usb_gcore_desc.c:440–441` copies `us_id_vendor` and `us_id_product` into the host-facing USB device descriptor. This is evidence from the published G3 source, not a new verification that every instruction of the retained proprietary firmware's running kernel matches that source.

Only those three required files were extracted from the already downloaded, model-specific G3 kernel archive into `g3-gpl-gadgetcore/`. No archive was downloaded again and no kernel was built. Its archive SHA256 is `cbb03d206740f0bcc8ed9efc90e1f48786f427188954616ed618a3cb7597e90a`; individual member hashes are recorded in `descriptor-evidence.json`.

## Exact activation/deactivation requests to driver events

`CUsbGadgetSen::on_create` resolves a 16-byte literal table at **libusb VA/file `0x10294`**. Its `LDM/STM` at `0xCDAC/0xCDC8` copies the table to the stack. It sets the auxiliary pointer and length 16 in the probe structure and sends **ioctl `0x4034E000`** at `0xCE44`.

The table is two complete USB setup packets. Multi-byte setup fields use little-endian order:

| Pattern index | Setup bytes | bmRequestType | bRequest | wValue | wIndex | wLength | Corresponding pinned PMCA constant |
|---:|---|---:|---:|---:|---:|---:|---|
| 0 | `43 01 FF 37 AA D7 00 00` | `0x43` | `1` | `0x37FF` | `0xD7AA` | `0` | `SONY_VendorRequest_StartSenser` |
| 1 | `43 01 00 C8 55 28 00 00` | `0x43` | `1` | `0xC800` | `0x2855` | `0` | `SONY_VendorRequest_StopSenser` |

Pinned PMCA revision `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0` supplies these tuples in `SonySenserAuthDevice`; its generic libusb backend combines OUT, VENDOR and OTHER for `bmRequestType 0x43`. `verify_descriptor.py` verifies both actual source files against their Git blobs at that revision, reads the tuples with AST literal evaluation and compares their packed bytes with the table. It does not import the PMCA USB backend.

The corresponding preserved kernel path is established independently in [kernel-report.md](kernel-report.md) and `kernel-sen-driver.asm.txt`:

- The ioctl handler at `.text:0x1A450` handles `0x4034E000`, obtains the userspace structure through `usbg_cmn_copy_probe_info`, and installs the callback `.text:0x1A248` in the function driver's vendor slot before `usb_gadgetcore_register_driver`.
- The helper copies the auxiliary buffer referenced by offsets `+0x2C/+0x30`. The ioctl path then copies 16 bytes into the table used by that callback at `.text:0x1A5E0–0x1A5EC`.
- The callback compares the incoming USB request against table entries 0 and 1 with `memcmp(..., 8)` at `.text:0x1A290`. After a match, it calls `usb_gadgetcore_stop_other_driver` at `.text:0x1A2A0`. Only on its zero result does it call `usb_event_add_queue` at `.text:0x1A2C8`, with event value 7 and a four-byte payload containing the matched index 0 or 1.

This is a proven static request-to-event path **once this Senser function driver is registered**. It is not evidence that sending the same request to an ordinary mass-storage session will itself start the Senser process, enumerate PID 0336, or complete authentication. No such host interaction was attempted. End-to-end event dispatch, timeout/re-enumeration behavior and safe normal-mode return were not newly executed or qualified by this bounded audit.

## Integrity and reproduction

The retained `unified_drv.ko` is truncated after 274432 bytes although its section table describes file-backed content through byte 303816. Its `.text`, data, full symbol/string tables and all relocations used for the above callback path are present. The tail of `.rel.text` and later relocation sections are missing. The scripts retain that limitation and do not synthesize absent relocation entries. The complete `unified_drv2.ko` adds no named USB/Senser implementation. See the kernel report for precise coverage.

From the repository root, the single offline reproduction command is:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\g3-usb-descriptor\reproduce.py'
```

The constituent ELF inspections, selected library decodes, kernel inspections/decodes and `verify_descriptor.py` ran successfully during this audit. The combined wrapper regenerates bounded final library listings and invokes those same retained checks. It requires the prepared Python, local Capstone installation, Git, pinned PMCA checkout, retained G3 binary inputs and previously downloaded G3 GPL archive. It performs no network access or USB operations and does not load or execute the firmware. `descriptor-evidence.json` records the concrete bindings and hashes; `libusb-chain.asm.txt` and `libsencore-chain.asm.txt` contain the final library ranges, and `kernel-sen-driver.asm.txt` contains the relocation-aware kernel ranges. Earlier individual `libusb-*.asm.txt` files are exploratory supporting listings; the final chain listings stop before literal pools.

This report adds a G3-specific static resolution to the earlier [host-interface audit](../g3-host-interface/README.md). It does not change that audit's historical scope. Use these G3 findings to qualify W300 service entry, actual USB PID, authentication, language representation, persistence, original-board eligibility and restoration against W300 evidence. No camera setting or calibration data was read or written.
