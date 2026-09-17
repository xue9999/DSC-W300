# Retained G3 kernel-module USB audit

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

This is static analysis of two retained G3 files as data. No firmware was executed, no module was loaded, and no USB traffic was sent. Section offsets below are ELF relocatable-object offsets, never W300 camera addresses.

## Results

The retained `unified_drv.ko` contains a concrete SENSER driver registration and request-matching path. The two request patterns come from userspace; this module audit does not establish their literal bytes or a USB VID/PID. `unified_drv2.ko` provides no additional named USB/SENSER/gadgetcore implementation in its complete symbol table.

| Evidence | `.text` offset | File offset | Meaning established by code and retained relocations |
|---|---:|---:|---|
| `usbg_cmn_copy_probe_info` | `0xb480` | `0xb4b4` | Copies a `0x34`-byte userspace structure; copies referenced auxiliary data at structure offsets `+0x2c` and length `+0x30`. |
| SENSER request callback | `0x1a248` | `0x1a27c` | Reads private data through context `+0x6c`; compares its two consecutive 8-byte entries against the incoming second argument. |
| Callback `memcmp` import | `0x1a290` | `0x1a2c4` | Comparison length is exactly 8; entry index is 0 or 1. |
| Stop other USB driver | `0x1a2a0` | `0x1a2d4` | On a match calls the imported `usb_gadgetcore_stop_other_driver` with context `+0x34`. The call must return zero to proceed. |
| Queue event | `0x1a2c8` | `0x1a2fc` | Calls imported `usb_event_add_queue`, with `r3=7`, payload length 4 and payload containing the matched entry index. This establishes how the code queues the event, not what the userspace event handler eventually does. |
| SENSER ioctl handler | `0x1a450` | `0x1a484` | Handles ioctl `0x4034e000` registration and `0x0000e001` unregistration. Literal locations are `.text:0x1b0e0` and `.text:0x1b0dc`, respectively. |
| Copy userspace probe data | `0x1a534` | `0x1a568` | Calls `usbg_cmn_copy_probe_info`. |
| Install request callback | `0x1a584`–`0x1a588` | `0x1a5b8`–`0x1a5bc` | Loads relocated `.text:0x1a248` and stores it at context `+0x5c` (driver record `+0x28`, because its base is context `+0x34`). |
| Register driver | `0x1a58c` | `0x1a5c0` | Calls imported `usb_gadgetcore_register_driver` with context `+0x34`. |
| Copy request pattern table | `0x1a5e0`–`0x1a5ec` | `0x1a614`–`0x1a620` | Copies 16 bytes from the userspace auxiliary buffer into the private table used by the request callback. |
| Unregister driver | `0x1a608` | `0x1a63c` | Calls `usb_gadgetcore_unregister_driver`, then clears probe data. |

The module therefore supports tracing the request patterns back to the userspace library. The code does not provide those patterns as a verified static table here. It also does not establish the gadgetcore descriptor layout: `usb_gadgetcore_register_driver` and `usb_gadgetcore_stop_other_driver` are undefined imports. The relevant consumer is outside these two modules.

## Integrity limitation

`unified_drv.ko` has 274432 bytes, but its ELF section table declares stored content through byte 303816. Its full `.text`, `.init.text`, `.data`, `.rodata`, `.symtab` (774 symbols) and `.strtab` are present. Its `.rel.text` begins at 231000 and declares 64080 bytes, but only 43432 bytes, or 5429 complete relocation entries, remain. The later relocation sections are absent. This is a property of the retained input, not a parser/dependency failure. Missing relocation entries were not reconstructed or guessed. In particular, `init_usbg_sen` exists at `.init.text:0x910`, file `0x2a5b0`, size `0x100`, but its relocation section is unavailable.

`unified_drv2.ko` is 90548 bytes and all declared file-backed sections fit. Its full table has 177 symbols and 2400 relocation entries. No symbol names match USB, SENSER or gadgetcore. This absence of matching names does not prove that the entire file is unrelated to USB.

## Reproduction

Run from the repository root using the prepared Python and Capstone installation:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\g3-usb-descriptor\kernel-inspect.py'
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\g3-usb-descriptor\kernel-decode.py'
```

Both commands ran successfully. The JSON inventories retain input SHA256, section bounds, full symbols, and every available relocation. `kernel-sen-driver.asm.txt` contains selected code with resolved retained branch/ABS32 annotations. ARM branch destinations displayed by raw Capstone on `ET_REL` files are not linked addresses; use the relocation annotations. The initial `kernel-selected.asm.txt` is preliminary raw decoding and is superseded for control-flow interpretation by `kernel-sen-driver.asm.txt`.

These findings concern the retained G3 module only. They do not establish W300 firmware compatibility, the current W300 USB PID, successful authentication, language data addresses, a persistence command, or safe original-board destination programming.
