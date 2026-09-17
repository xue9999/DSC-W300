# Official DSC-W300 GPL source audit

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

## Outcome

The official W300 source packages were located, downloaded, and inspected on 2026-09-16. They provide direct, model-linked evidence of a **CXD4108 / ARM926T Linux 2.6.11-alp** software platform and Sony's USB gadget infrastructure. They do **not** supply the SEUS/SENSER application protocol, destination properties, original-board eligibility logic, or a qualified W300 read adapter. No USB operation, kernel build, firmware build, or camera write was performed.

This is new W300-specific source evidence, independent of any DSC-G3 firmware. The downloadable kernel's bundled configuration is not a measurement of the user's individual camera or a full W300 firmware image.

## Proven acquisition route

- Current official source page: <https://oss.sony.net/Products/Linux/DI/DSC-W300.html>.
- Official category page linking that exact model: <https://oss.sony.net/Products/Linux/DI/category01.html>.
- Distribution notice read: <https://oss.sony.net/Products/Linux/notice.html>.
- Local download directory: `build/w300/downloads/w300-gpl/`.
- The exact returned HTML is saved as `DSC-W300.html`; every package URL, byte count and SHA-256 is saved in `acquisition.json`.

The historical `/Products/Linux/Download/DSC-W300.html` URLs could not be opened by the web tool. Searching Sony's current OSS category found the `DI/DSC-W300.html` page. Windows `curl` failed with `CRYPT_E_NO_REVOCATION_CHECK`; the already prepared Python venv's standard-library `urllib.request.urlopen` downloaded successfully using its normal TLS certificate verification. No TLS-verification bypass was used. The venv does not include `requests`, so no additional package was installed merely to download these files.

| Downloaded file | Bytes | Role |
|---|---:|---|
| `linux-kernel.tar.gz` | 35,784,585 | W300-linked Linux source tree, configuration, Sony USB/controller code |
| `sony-target-rel-busybox-1.01-010502di6.src.rpm` | 1,183,366 | BusyBox sources, configuration, build specification and patches |
| `sony-target-rel-dosfstools-2.11-010501.src.rpm` | 74,733 | FAT utility sources and patches |
| `sony-target-rel-netbase-4.06-010501.src.rpm` | 52,925 | Network baseline configuration |
| `sony-target-rel-psmisc-21.6-010501.src.rpm` | 228,020 | Process utility sources and patches |

The kernel SHA-256 is `97cb9298b593ac4a565ab3a9ac6fac45c30f016fe66f3e555eb5494428882834`. Packages were obtained from the `prodgpl.blob.core.windows.net` links published by Sony's exact W300 page, not from a guessed neighbouring-model download.

## Contents and reproducible evidence

The kernel has 10,004 archive members. All regular-file contents were scanned inside the archive; a 364-file subset containing USB sources, relevant headers, CXD4108 configuration, SoC sources and the top-level configuration was extracted under `extracted/`. Extraction admitted regular files only and verified each resolved destination remained under the extraction directory. The original archive remains available for complete reinspection.

Saved evidence files:

- `kernel-file-list.txt`: complete kernel archive member list.
- `keyword-hits.tsv`: archive-wide hits for service, destination and backup terms, with source member and line.
- `targeted-symbol-hits.json`: archive-wide matches for `usb_gadgetcore_register_driver`, `USBSENSERKEYOPEN`, `SONYDSC`, `SONYSEN`, `seus`, `senser`, `DSC-W300`, `ADJBAK`, `EEPROM` and `BKUP`.
- `*.src.rpm.files.txt`: actual member listings for all four RPMs, generated with Windows `tar -tf`.

The extracted subset supports navigation. The complete content search read every regular-file member directly from `linux-kernel.tar.gz`.

## Architecture evidence

Paths below are relative to `build/w300/downloads/w300-gpl/extracted/`.

- `linux/Makefile:1-4`: version 2.6.11 with `-alp` suffix.
- `linux/.config:83-84`: CXD4105 disabled, `CONFIG_ARCH_CXD4108=y`.
- `linux/.config:123-124`: ARM926T, ARMv5 CPU.
- `linux/.config:193`: initrd-based Linux command line; this is a configuration value, not permission or an instruction to read that RAM range on the camera.
- `linux/.config:622-638`: Sony MCD controller, USB event, OTG core and gadget core are enabled.
- `linux/.config:615`: the ordinary `CONFIG_USB` host stack is disabled. This does not mean the camera lacks USB: Sony's separate device/controller stack is explicitly enabled.
- `linux/.config:204`: standard MTD is disabled. Qualify the flash layout or rule out proprietary storage drivers through separate target-model evidence.

## Exact USB layer boundary

Sony's `linux/include/linux/usb/gcore/usb_gadgetcore.h:35-49` defines `usb_gadget_func_driver` and separate class/vendor request callbacks. At `:60` it declares `usb_gadgetcore_register_driver`.

`linux/drivers/usb/gcore/usb_gcore_setup.c:240-349` implements generic dispatch of vendor-specific control requests. Interface and endpoint requests are routed to matching function drivers. For device/other recipients (`:320-344`), it walks registered function drivers and calls each `vendor` callback; a callback accepts, stalls, or passes the request through. The code does not interpret the legacy SENSER control request or supply its payload. If no handler accepts, it returns an error.

The complete archive search found the registration symbol only in its header declaration, definition, diagnostic string and export. It found **no actual caller registering a camera function driver**, and no `USBSENSERKEYOPEN`, `SONYDSC`, `SONYSEN`, SEUS/SENSER handler or ADJBAK implementation. The generic USB dispatcher is present; the camera function-driver implementation needed to explain the service packets is not present in the reviewed kernel source. This source-level boundary is stronger evidence than an absent model-name keyword alone.

The ordinary Linux gadget examples and host-storage code included in the full source tree are not evidence of the shipping camera's service command implementation. Likewise, generic EEPROM and filesystem backup references are not destination settings.

The BusyBox source RPM contains an `insmod` configuration and patches, as well as telnet applet build settings. Qualify an accessible shell, running telnet service, valid USB network interface, or a way to load code on the user's camera through separate target-model evidence. Those utilities cannot be used as a bridge without independent access evidence.

## Implication for the minimal adapter

This release supports investigating the legacy CXD4108-era transport rather than assuming modern PMCA backup formats. It does **not** validate the A330 script's `0x6f:0x0c` destination address, its `0x80:0x01` write-enable operation, its save page, the MD5 challenge-response handshake on W300, or the legacy packet sizes. None of those values should be copied into a W300 write path on the basis of this GPL release.

A useful next input is a W300 application/function-driver binary, exact Auto-Adj payload, or a qualified W300 service-session trace. The current GPL source narrows the missing layer to camera-specific USB function/application code. Building this kernel or a QEMU environment would not recreate that missing layer and would not establish an executable language conversion.

## Small reproduction checks

Run from the repository root:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'build/w300/downloads/w300-gpl/linux-kernel.tar.gz'
tar -tf 'build/w300/downloads/w300-gpl/linux-kernel.tar.gz'
rg -n 'CONFIG_ARCH_CXD4108|CONFIG_CPU_ARM926T|CONFIG_USB_GADGET_CORE' 'build/w300/downloads/w300-gpl/extracted/linux/.config'
rg -n 'usb_gadgetcore_register_driver|func_drv->vendor' 'build/w300/downloads/w300-gpl/extracted/linux/drivers/usb/gcore'
```

`acquisition.json` is the complete package URL/hash record. All new materials are under `build/w300/`; `sources/` and `evidence/` were left unchanged.
