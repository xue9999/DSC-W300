# Sony Cyber-shot DSC-G3 Decrypted Firmware Architecture

## Decryption Status
- Firmware was successfully carved, decrypted, and verified 100% offline.
- Source Executable (`sources/DSCG3V2.exe`): `55,928,464` bytes (SHA-256: `a9698c7b3822f23d71de84ba5389453b847f6de19ab293a55ebe016490fd94d9`)
- LHA Level 2 stream carved at offset `0x744f` (length: `55,898,688` bytes).
- Container (`evidence/extracted_g3/D-G3V2.dat`): `55,898,688` bytes (SHA-256: `ea74b57161881208f177befcef003f7a0f65ae6e470e209c37f5a8da4f88dd5c`)
- Cryptographic verification: 128-byte block header HMAC-SHA1 and 20-byte payload HMAC verified across all 24 sections with zero errors.
- Manifest (`cntent.dat`): Declared `24` payload sections, checksum verified.

## Platform Facts
- Camera Model: `Sony Cyber-shot DSC-G3` (Model ID: `0x08210030`, Firmware Ver: `2.00`)
- SoC Architecture: `Sony CXD4108 BIONZ (ARM926EJ-S + µITRON Core)`
- Kernel: `Linux version 2.6.11-alp20080305 (jp06294@monet03) (gcc version 3.4.4) #1 Tue Feb 10 14:03:21 JST 2009`
- Kernel Image (`vmlinux`): `Linux kernel ARM boot executable zImage (little-endian)` (1,595,560 bytes)
- Updater RootFS (`BodyUdtr.img`): `Compressed ROMFS (CramFS, big-endian magic 0x28cd3d45)` (221,184 bytes, 48 nodes, 18 ELFs)
- System RootFS (`rootfs.img`): `Compressed ROMFS (CramFS, big-endian magic 0x28cd3d45)` (569,344 bytes, 130 nodes, 16 ELFs)
- Initial Ramdisk (`initrd.img`): `Linux rev 1.0 ext2 filesystem data (magic 0xef53)` (660,480 bytes, 6 ELFs)
- Real-Time Co-Processor Image (`av.bin`): `ARM bare-metal executable / µITRON vector image` (2,061,054 bytes)
- Total ELF Binaries/Libraries across all subsystems: `96`
- ELF Breakdown:
  - `BodyUdtr.img`: 18 ELFs
  - `bin.tar`: 4 ELFs
  - `lib.tar`: 17 ELFs
  - `fskrel1.tar`: 27 ELFs
  - `fskrel2.tar`: 8 ELFs
  - `linuxset1.tar/rootfs.img`: 16 ELFs
  - `linuxset1.tar/initrd.img`: 6 ELFs
- Web Browser Engine: `ACCESS NetFront Browser v3.4 (Flash Lite 6)`
- Application Framework: `Kinoma Platform / Fsk on Access Linux Platform`

## Storage Layout
- Storage Technology: `OneNAND Flash` (from `partinf.tbl`)
- Parsed Partitions: `12` active entries

| Partition Device | Description | Start Address | Size (Bytes) | Size (MB) | Type | Valid |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/dev/nflasha1` | Updater | `0x00020000` | `2,097,152` | 2.000 MB | `0x00000000` | `0x00000001` |
| `/dev/nflasha2` | RW Data | `0x00220000` | `1,572,864` | 1.500 MB | `0x00000001` | `0x00000001` |
| `/dev/nflasha3` | HOST | `0x003A0000` | `4,194,304` | 4.000 MB | `0x00000001` | `0x00000001` |
| `/dev/nflasha4` | Warm Boot Image | `0x007A0000` | `0` | 0.000 MB | `0x00000000` | `0x00000000` |
| `/dev/nflasha5` | AV | `0x007A0000` | `3,670,016` | 3.500 MB | `0x00000001` | `0x00000001` |
| `/dev/nflasha6` | reserved | `0x00B20000` | `31,326,208` | 29.875 MB | `0x00000001` | `0x00000001` |
| `/dev/nflasha7` | reserved | `0x02900000` | `0` | 0.000 MB | `0x00000000` | `0x00000000` |
| `/dev/nflasha8` | reserved | `0x02900000` | `0` | 0.000 MB | `0x00000000` | `0x00000000` |
| `/dev/nflasha9` | reserved | `0x02900000` | `0` | 0.000 MB | `0x00000000` | `0x00000000` |
| `/dev/nflasha10` | reserved | `0x02900000` | `0` | 0.000 MB | `0x00000000` | `0x00000000` |
| `/dev/nflasha11` | storage | `0x02900000` | `131,072` | 0.125 MB | `0x00000001` | `0x00000001` |
| `/dev/nflasha12` | BGM | `0x02920000` | `19,922,944` | 19.000 MB | `0x00000001` | `0x00000001` |

## Subsystem Analysis
### 1. Dual-Core Asymmetric Architecture
- **Application Core**: ARM926EJ-S running Linux 2.6.11-alp20080305 ('Woozy Beaver', Access Linux Platform). Host for NetFront Browser, Kinoma media framework, Wi-Fi networking, and UI rendering.
- **Real-Time Core**: ARM/DSP running Sony AV RTOS (µITRON 4.0). Manages BIONZ image sensor pipeline, CCD timing, optical lens actuators, and hardware compression engines (`av.bin`, `av_udtr.bin`).
- **Inter-Processor Communication (IPC)**: ARM PrimeCell PL320 mailbox interface driven by `ipcm_pl320.ko`, `ipcm.ko`, and `ipcm_dev.ko` kernel modules in `/lib/`.

### 2. Dual RootFS Topology
- **Updater Environment (`BodyUdtr.img`)**: Standalone CramFS RAM rootfs booted during firmware flashing. Contains Sony update orchestration scripts (`BodyUdtr.sh`, `UdtrMain.sh`), diagnostic tools (`ud_datcnv`), frame buffer drivers (`cxd4108fb.ko`), and keypad drivers (`cxd4108kbd.ko`).
- **Runtime System Environment (`rootfs.img`)**: Production CramFS rootfs containing BusyBox userland, dynamic linker, system initialization scripts (`/etc/init.d/`), and kernel modules in `/lib/modules/2.6.11-alp20080305/`.
- **Initial Ramdisk (`initrd.img`)**: Ext2 filesystem containing early initialization hooks (`linuxrc`), event controller (`evctrl.ko`), logger (`blog.ko`), and unified hardware drivers (`unified_drv.ko`, `unified_drv2.ko`).

### 3. Application Stack & Frameworks
- **ACCESS NetFront Browser v3.4**: Embedded full web browser (`omgPrg00.bin`, `omgPrg01.bin`, `omgRsc00.bin`) featuring Flash Lite 6 runtime, SSL/TLS, and multi-language localized string tables (`omgLng00.csv`).
- **Kinoma / Fsk Media Platform**: Dynamic multimedia scripting engine powering the touchscreen GUI and Scrapbook photo presentation suite (`fskrel1.tar`, `fskrel2.tar`, `fskapp*.tar`). Includes FreeType rasterizer (`textenginefreetype.so`) and USB extensions (`usbExt.so`).
- **Senser Diagnostic Daemon (`sen`)**: Factory test harness and sensor calibration daemon interfacing with `/dev/mem` and `libsencore.so` (benchmarked against NX3 Tier 3 diagnostics).

## Architectural Comparison Benchmark: DSC-G3 vs. HXR-NX3
| Feature / Dimension | Sony Cyber-shot DSC-G3 (2009) | Sony HXR-NX3 (2014) |
| :--- | :--- | :--- |
| **Product Class** | Connected Consumer Compact Camera | Professional Handheld AVCHD Camcorder |
| **BIONZ ASIC** | CXD4108 (ARM926EJ-S + µITRON) | CXD90014 (Dual Cortex-A9 + µITRON) |
| **Firmware Packaging** | PE EXE -> LHA Level 2 -> MsFirm | UFU container (`DATV`, `PROV`, `FDAT`, `DEND`) |
| **Cryptographic Scheme** | Double HMAC-SHA1 (`key_cxd4108_ms`) + stream cipher | AES / Proprietary CXD90014 cipher |
| **Section Manifest** | `cntent.dat` (24 sections with 128-byte headers) | `part_image.sum` CRC32 / `partinf.conf` |
| **Linux Kernel** | 2.6.11-alp20080305 (ARMv5TEJ) | 3.0.27_nl-rt106 PREEMPT RT (ARMv7 Cortex-A9) |
| **Root Filesystem** | CramFS (`0x28cd3d45`) + ext2 initrd | ext2 (`UUID=22fcb12a...`) in LZPT compressed block |
| **Application Stack** | Access Linux Platform + Kinoma Fsk + NetFront 3.4 | `im.elf` / `libObj.so` + SUGILITE UI + `orb-server` |
| **Diagnostic Daemon** | `sen` / `libsencore.so` (early Senser) | `sen.elf` / `libsencore.so` (mature Senser protocol) |
| **Total ELF Binaries** | 96 binaries/libraries | 209 binaries/libraries |

## Key Evidence Paths
- Partition table: `evidence/extracted_g3/sections/01_partinf.tbl`
- Carved container stream: `evidence/extracted_g3/D-G3V2.dat`
- Manifest table: `evidence/extracted_g3/cntent.dat`
- Decrypted section payloads: `evidence/extracted_g3/sections/`
- Kernel artifacts: `evidence/extracted_g3/kernel/` (`vmlinux`, `initrd.img`, `rootfs.img`)
- Updater RootFS: `evidence/extracted_g3/rootfs/BodyUdtr/`
- System RootFS: `evidence/extracted_g3/rootfs/system_rootfs/`
- Initrd RootFS: `evidence/extracted_g3/rootfs/initrd/`
- Unpacked tar archives: `evidence/extracted_g3/archives_unpacked/` (12 archives)
- Machine-readable inventory: `evidence/decrypted_inventory.json`
- Canonical architecture dossier: `evidence/DECRYPTED_ARCHITECTURE.md`
