# Official G3 and W300 GPL release cross-check

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

## Result

Sony's official G3 and W300 source releases use **different kernel download URLs and different kernel archives**, but their included configurations select the **same CXD4108 / ARM926T / ARMv5 platform**, RAM base and Sony USB-core options. This is stronger than a similarity inferred from camera age, and weaker than identical platform software. It does **not** establish that the proprietary service implementation, authentication, packet format, destination data or persistence operation is shared.

The [official DSC-G3 source page](https://oss.sony.net/Products/Linux/DI/DSC-G3.html) was downloaded as HTML and its actual links parsed. They were compared with the retained acquisition record for the [official DSC-W300 release](https://oss.sony.net/Products/Linux/DI/DSC-W300.html). Four non-kernel package URLs are exactly the same: BusyBox, dosfstools, netbase and psmisc. They were **not downloaded again**. Only the different G3 kernel was acquired.

## Package and configuration comparison

Both kernel URLs use `https://prodgpl.blob.core.windows.net/download/DI/common/` and filename `linux-kernel.tar.gz`, but the intervening object identifiers differ:

| Property | W300 retained official release | G3 newly acquired official release |
| --- | --- | --- |
| Kernel object identifier | `oVBUKPxBbmKO+N9GN8qBeQ` | `gJAvq2V+EbaMAb9NvrrKTA` |
| Archive size | 35,784,585 bytes | 35,810,795 bytes |
| SHA-256 | `97cb9298b593ac4a565ab3a9ac6fac45c30f016fe66f3e555eb5494428882834` | `cbb03d206740f0bcc8ed9efc90e1f48786f427188954616ed618a3cb7597e90a` |
| `linux/.config` version comment | `2.6.11-alp20070919` | `2.6.11-alp20080305` |
| `CONFIG_ARCH_CXD4108` | `y` | `y` |
| `CONFIG_CPU_ARM926T`, `CONFIG_CPU_32v5` | both `y` | both `y` |
| `CONFIG_CXD4105_PHYS_OFFSET` | `0x20400000` | `0x20400000` |
| Sony USB layers | `USB_MCD_CD`, `USB_EVENT`, `USB_OTG_CORE`, `USB_GADGET_CORE` enabled | Same enabled values |

The extracted `.config` files are not identical. The complete diff is retained: G3 disables `CONFIG_SYSCTL`, adds disabled `CONFIG_KLOG`/`CONFIG_ZONE_RO` declarations, changes the kernel command line's reserved-memory and initrd parameters, and changes the exception-log path. The source version and generation comments also differ. The observed `.config` files are source-distribution configurations, **not a measurement of either individual camera's running firmware**.

The RAM and initrd values are boot/kernel configuration data. They are not a flash-dump range or SEUS address mapping. The contemporary Sony PTP attachment's separate ARMv6 example modules must likewise not override this exact-model ARM926T evidence.

## Narrow USB ABI comparison

A follow-up compared the exact three published files used to interpret the retained G3 service descriptor and start ioctl. Each was read directly from both hash-verified official archives. These three files are **byte-identical between the W300 and G3 packages**:

- `linux/include/linux/usb/gcore/usb_gadgetcore.h`
- `linux/drivers/usb/gcore/usb_gcore_desc.c`
- `linux/drivers/usb/gcore/usb_gcore_main.c`

This establishes a shared published gadget-core interface, descriptor consumer and start implementation in that bounded scope. It strengthens the platform comparison beyond matching configuration flags. It does not supply or compare the absent proprietary W300 function driver, service application, language map or original-board test. It does not show that either individual camera runs these exact source bytes.

Reproduce with `build/w300/downloads/g3-gpl-reference/compare_usb_core.py` using the prepared Python. `usb-core-comparison.json` records all three member hashes and both archive pins. The helper ran successfully and reported `identical_members: 3`; it performs no extraction, build, network or USB operation.

## Retained evidence and reproduction

Under `build/w300/downloads/g3-gpl-reference/`:

- `DSC-G3.html` and `page-comparison.json`: acquired official model page, hash and exact links; matches to the existing W300 acquisition record.
- `linux-kernel.tar.gz` and `kernel-acquisition.json`: actual new G3 archive, origin, length and SHA-256.
- `g3.config`, `w300.config`, `config.diff`, `config-comparison.json`: archive-read comparison, configuration hashes and selected settings.

The W300 archive was read from its existing local path and was not downloaded again. Both local archive hashes were computed for this comparison. Tar members were read directly; no archive was broadly extracted, and no kernel was built or executed.

From the repository root, reproduce the offline archive/configuration comparison with the existing environment:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\downloads\g3-gpl-reference\compare_gpl.py'
```

The retained helper is the same comparison body used successfully for these outputs. It performs no network or USB access. Matching open-source CPU/USB configuration does not imply matching proprietary code; the independently observed G3 service framing still requires separate W300 qualification.
