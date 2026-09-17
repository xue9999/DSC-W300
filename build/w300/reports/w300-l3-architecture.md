# W300 Level-3 architecture and transport evidence

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

Date: 2026-09-16. Offline acquisition and source inspection only. This work narrows firmware identification; it does not supply a language command or authorize camera reads from guessed addresses.

## Newly acquired exact-model manual

The public [ManualLib landing page](https://www.manuallib.com/file/306862/) links an actual [34-page Sony DSC-W300 Level-3 PDF](https://www.manuallib.com/download/pdf4/SONY-DSC-W300-MANUAL.PDF). It is retained as `build/w300/downloads/w300-l3-reference/sony-w300-l3-v1.1.pdf`, with extracted text and rendered relevant pages. Its cover identifies version 1.1, May 2008, Sony document 9-852-287-11. It contains a third-party watermark; this is a mirrored Sony document, not an authenticated current Sony download.

Verified manual facts:

- PDF pages 14-16, printed 4-7 through 4-9: main IC203 is **PRX765105A**, on SY-199. Page 14 connects the USB data signals to it. Page 16 depicts EMC and DDR interfaces without specifying a separate flash device or its capacity.
- PDF page 28, printed 5-12: the replacement assembly is **A-1543-570-A, SY-199 complete service board**. The note supplies IC203 only with that assembly; the IC list repeats PRX765105A on PDF page 30.
- No W300 destination address, language encoding, flash image size, or original-board eligibility test was established from these pages. The supply note concerns a replacement part; it does not identify a region-lock mechanism.

Pages 14 and 16 were rendered with the available Poppler tool and visually checked. Poppler emitted missing-display-font warnings for Symbol/ArialUnicode; the relevant Latin chip names, USB labels and wiring remained legible. The parts entry was checked in the extracted text. Do not infer an exact flash chip or memory capacity from unconnected schematic pins.

The earlier Elektrotanya listing returned a CAPTCHA before the PDF. No challenge was bypassed; the independently indexed ManualLib mirror supplied the document. A follow-up ManualsLib L2 block diagram was obtained as HTML after the web tool failed. It adds IC203's functional labels, not an internal flash specification.

## Exact-model GPL cross-check

The already acquired official W300 kernel is still the architecture authority for the software configuration. The inspected `.config` selects CXD4108/ARM926T and sets `CONFIG_CXD4105_PHYS_OFFSET=0x20400000`; the family implementation lives under `mach-cxd4105` and `arch-cxd4105`, despite this being the CXD4108 configuration.

The archive's `include/asm-arm/arch-cxd4105/memory.h` derives the RAM offset from that configuration. Its `platform.h` and `arch/arm/mach-cxd4105/mm.c` describe peripheral mappings; the latter also contains a generic SDRAM comment referring to a different base. These are kernel RAM/I/O definitions, **not a W300 persistent-storage map**. Neither an initrd address nor an A330 dump range becomes a qualified flash-read interval through this cross-check. No address was added to the workbench.

## Existing actual USB descriptor, reused for a new comparison

The preserved historical `evidence/w300/usb-transport-probe-20260916.json` already contains a standard configuration descriptor. Its 32 raw bytes describe one interface, class 08, subclass 05, protocol 50 hex, with bulk endpoints 81 IN and 02 OUT and 512-byte maximum packets. This supports Bulk-Only Transport for that recorded mode and makes a new generic descriptor utility unnecessary at this point.

That same record reports `LIBUSB_ERROR_ACCESS` when claiming the interface and explicitly leaves `camera_identity_verified` false. It is a historical descriptor observation, not a successful vendor/service exchange, present-computer detection, or validation of the user's receiving PC. Current identity must still be checked there.

## Reproduction

From the repository root:

```powershell
Get-FileHash -Algorithm SHA256 'build/w300/downloads/w300-l3-reference/sony-w300-l3-v1.1.pdf'
pdftoppm -f 14 -l 14 -scale-to 2400 -png -singlefile 'build/w300/downloads/w300-l3-reference/sony-w300-l3-v1.1.pdf' 'build/w300/downloads/w300-l3-reference/page14'
tar -xOf 'build/w300/downloads/w300-gpl/linux-kernel.tar.gz' 'linux/include/asm-arm/arch-cxd4105/memory.h'
rg -n 'CXD4105_PHYS_OFFSET|CONFIG_ARCH_CXD4108|CONFIG_CPU_ARM926T' 'build/w300/downloads/w300-gpl/extracted/linux/.config'
```

The adjacent acquisition JSON records origins, lengths and SHA-256. Exact chip-name searches can use PRX765105A as an additional locator, but a matching string alone cannot authenticate a firmware image. No new runtime, driver installation, camera interaction, or conversion function resulted from this bounded inspection.
