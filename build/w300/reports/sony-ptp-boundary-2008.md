# Sony's 2008 PTP stack explanation: acquired attachment and interface boundary

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

Inspected 2026-09-16. No camera connection, camera write, service-software installation, or external contact.

## Result

**The actual public attachment was acquired and inspected. It corroborates a precise boundary missing from the W300 GPL tree, but contains no service packet format, command bytes, memory map, or language-changing operation.** The file is a one-slide architecture diagram, not a firmware module or software package.

Public primary sources:

- [Linus Walleij's question and Tim Bird's response](https://sourceforge.net/p/libmtp/mailman/libmtp-discuss/thread/63386a3d0812051408nc849471pd2b19d578364df36%40mail.gmail.com/).
- [Tim Bird's response, 5 December 2008](https://sourceforge.net/p/libmtp/mailman/message/21014782/).
- [Actual DSC-PTPSoftStack.ppt attachment](https://sourceforge.net/p/libmtp/mailman/attachment/49387DCE.9030409%40am.sony.com/1/).

Walleij explicitly cites the W300 GPL release while asking where the device-side PTP/MTP interface is implemented. Bird, writing from Sony, relays information gathered from colleagues and qualifies his own expertise. He explains that a proprietary userspace PTP implementation, originally ported from another OS, uses proprietary loadable kernel modules above the published gadget core. This is direct historical corroboration of the missing software layer, not a complete specification or a commitment about today's available downloads.

## Acquired files and checks

Files are under `build/w300/downloads/sony-ptp-2008/`.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `DSC-PTPSoftStack.ppt` | 35328 | `10019B69EEC38F621F00933ACA6A81C4DB81BA50EDDA7231B5FFB147CF0FAB2F` |
| `sony-reply-21014782.html` | 56296 | `7E6494F737B6C12DBDBA53076E3183C45BBC2E3289003E111032C83759AE0A64` |

The PPT has the expected OLE signature `D0 CF 11 E0 A1 B1 1A E1`. A read-only OLE scan found four streams, no VBA/macro-named stream, and no parser bounds error. It extracted text atoms without executing any slide content. Native PowerPoint then opened the file read-only, with macros force-disabled (`AutomationSecurity=3`) and no document window, and exported the one current slide to `slide-1.png`. The rendered diagram was visually inspected. Only this presentation was closed; PowerPoint was not quit. The source SHA-256 remained unchanged.

The binary contains text from earlier incremental saves; duplicate text atoms are therefore **not** extra slides. The current native slide count is one. See `ppt-static-inspection.json`, `current-slide-structure.json` and `render-verification.json`.

The web browsing tool's direct attachment reader initially rejected the PowerPoint MIME type. This was a reader-format limitation, not a missing attachment. A normal verified HTTPS file download succeeded immediately. The bundled Python lacked `olefile`; version 0.47 was installed only into this isolated download subtree's `parser-deps/` directory, leaving the shared runtime unchanged.

## What the diagram establishes

The visually inspected diagram puts the PTP application in userspace. A separate proprietary interface component sits in kernel space. Beneath that component, a GPL-marked area contains the gadget, OTG and event infrastructure in `drivers/usb/gcore/`, with the USB controller implementation in `drivers/usb/mcd/` below it. Neither proprietary component is shown inside the GPL area.

This clarifies the useful boundary: the GPL transport and dispatch infrastructure is below the implementation that interprets higher-level PTP or vendor commands. The slide itself does not map each loadable module to a particular service function and does not say that a language write uses PTP rather than a mass-storage extension.

## Correlation with the locally acquired W300 GPL tree

Read-only inspection used `build/w300/downloads/w300-gpl/extracted/linux/`:

- `include/linux/usb/gcore/usb_gadgetcore.h:35` defines `usb_gadget_func_driver`. Its `start`, `stop`, `class` and `vendor` callbacks are supplied by registered function drivers; the `start` callback receives an endpoint list. Lines 60-62 declare the registration and stop interfaces.
- `drivers/usb/gcore/usb_gcore_setup.c:1806` routes class requests to class dispatch, while line 1811 routes vendor requests to vendor dispatch. At lines 262, 301 and 327, vendor dispatch invokes a registered function driver's callback with the USB control request and ep0. This is a dispatch boundary; it does not define the missing driver's command semantics.
- `include/linux/usb/gcore/usb_gadgetcore.h:72` defines gadget-core ioctl controls for probe/remove/start/stop. These are device-kernel controls, **not USB host opcodes**, and must not be copied into a PC-side service tool as packet commands.
- Both `drivers/usb/gcore/` and `drivers/usb/mcd/` exist in the local tree, matching the slide's source paths. A filename search in that tree found no `usb_extcmd`, `usbg_storage`, or `usbg_stillimage` implementation file.

No source was modified. The finding justifies focusing any further reverse engineering on the absent function-driver/userspace layer, an actual W300 firmware image, or a real service application's communications. Adding another wrapper around GPL dispatch code would not reveal language bytes.

## Architecture caveat and exact missing targets

Bird's illustrative module metadata lists:

| Module | Reported version | Stated function |
| --- | --- | --- |
| `usb_extcmd.ko` | 01.00.000 | USB extension commands |
| `usbg_storage.ko` | 01.21.000 | Mass-storage USB function |
| `usbg_stillimage.ko` | 01.07.000 | Still-image USB function |

All three examples are marked proprietary and show an `ARMv6` vermagic suffix. The locally downloaded W300 GPL `.config:123` instead enables `CONFIG_CPU_ARM926T=y`, and `.config:84` enables `CONFIG_ARCH_CXD4108=y`. **Do not identify the example modules as W300 binaries or transplant their version/ABI assumptions to W300.** No `.ko` bytes accompany the email or slide. Use these names to locate binaries, then inspect their contents and model provenance.

## Reproduction and remaining limitation

```powershell
Invoke-WebRequest -Uri 'https://sourceforge.net/p/libmtp/mailman/attachment/49387DCE.9030409%40am.sony.com/1/' -OutFile 'build/w300/downloads/sony-ptp-2008/DSC-PTPSoftStack.ppt'
Get-FileHash -LiteralPath 'build/w300/downloads/sony-ptp-2008/DSC-PTPSoftStack.ppt' -Algorithm SHA256
```

`inspect_ppt.py` reproduces the static record scan using the isolated `parser-deps` copy of olefile. `render_readonly.ps1` reproduces the native rendering with macros disabled, without saving the source or quitting the user's PowerPoint session. The rendering step requires installed desktop PowerPoint; it is an analysis dependency, not a camera-tool dependency.

This acquisition advances the architectural evidence. It does not supply SeusEX, W300 Auto-Adj, a firmware dump, a recoverable calibration backup, or a language-writing command. No claim of working W300 service communication follows from it.
