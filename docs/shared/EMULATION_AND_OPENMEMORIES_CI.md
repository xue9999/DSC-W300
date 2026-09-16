# Sony CXD4108 Emulation & OpenMemories-CI Integration Guide

This guide documents the integration of [`ma1co/OpenMemories-CI`](https://github.com/ma1co/OpenMemories-CI), [`ma1co/fwtool.py`](https://github.com/ma1co/fwtool.py), and [`ma1co/qemu`](https://github.com/ma1co/qemu) into this repository, explaining how the emulation subsystem operates and how it advances both the **DSC-G3** and **DSC-W300** research goals.

---

## 1. Architectural Foundations

### The CXD4108 "Prius" SoC
Both the **Sony Cyber-shot DSC-G3** and **DSC-T100 / DSC-W90** share the Sony **CXD4108** BIONZ application-specific integrated circuit (ASIC).

```
+-----------------------------------------------------------------------------------+
|                            SONY CXD4108 BIONZ SoC                                 |
+-----------------------------------------------------------------------------------+
|  ARM926EJ-S Application Core   <---- Inter-Core Bus ---->  µITRON Real-Time Core  |
|  - Linux 2.6.x OS Kernel                                   - Lens/CCD/Motor Ctrl  |
|  - Brew / FSK GUI Framework                                - Real-Time DSP Engine |
+-----------------------------------------------------------------------------------+
|  Peripherals:                                                                     |
|  - Flash / NAND Controller (0x00000000) -> Samsung OneNAND (64MB)                 |
|  - DDR RAM (0x20000000, 64MB)           -> Boot & Runtime memory                  |
|  - SDHCI / MMC Controller (0x50000000)  -> Internal Mass Storage / Memory Stick   |
|  - SIO0 Serial Bus                      -> Power Management IC (SC901572 / MB89083)|
|  - SIO1 Serial Bus                      -> Battery Authenticator (NEC uPD79F)     |
|  - ADC0 Channel Matrix                  -> Buttons (Zoom, Play) & Resistive Touch |
|  - PL011 UART Channels                  -> Debug / System Console                 |
+-----------------------------------------------------------------------------------+
```

---

## 2. Directory Structure & Integrated Upstreams

Upstream source trees are preserved in `sources/` and cross-referenced in `sources/shared/`:

```
sources/
├── OpenMemories-CI/         # ma1co's CI test suite and firmware runner
├── fwtool.py/               # Sony firmware archive, CramFS, and partition unpacker
├── qemu/                    # ma1co's QEMU fork implementing 'cxd4108' machine
├── Sony-PMCA-RE/            # Reverse-engineered USB protocol and backup tools
├── DSCG3V2.exe              # Sony official DSC-G3 firmware updater executable
└── D-G3V2.dat               # Decrypted raw MsFirm payload
```

Our local Python tooling lives in `tools/cxd4108_emulator/`:
* [`tools/cxd4108_emulator/flash_builder.py`](file:///Users/andrzejpara/Documents/03_Projekty_Techniczne/DSC-W300/tools/cxd4108_emulator/flash_builder.py): Pure-Python implementation of the Sony SDM partition table, OneNAND spare area framing, and factory calibration structures.
* [`tools/cxd4108_emulator/qemu_launcher.py`](file:///Users/andrzejpara/Documents/03_Projekty_Techniczne/DSC-W300/tools/cxd4108_emulator/qemu_launcher.py): Hardware peripheral discovery, QEMU CLI synthesis, and subsystem status verification.
* [`tools/test_cxd4108_emulator.py`](file:///Users/andrzejpara/Documents/03_Projekty_Techniczne/DSC-W300/tools/test_cxd4108_emulator.py): 7 automated unit tests covering SDM tables, OneNAND framing, MBR layout, and calibration flags.

---

## 3. Flash Memory Map (Sony SDM & OneNAND)

The camera's internal NAND storage is partitioned using Sony's proprietary **SDM Partition Table** format:

* **Sector Size**: 512 bytes (`0x200`)
* **Header Magic**: `8246` (`0x38 0x32 0x34 0x36`)
* **Header Version**: `1.00` (`0x31 0x2E 0x30 0x30`)

### Partition Table Layout
| Partition Index | Target Mount / Role | Content / Filesystem | Size (Typical) |
| :--- | :--- | :--- | :--- |
| **Partition 1** | `/boot` (Updater) | Updater `vmlinux` kernel + CramFS `initrd.img` | 2 MB (`0x200000`) |
| **Partition 2** | `/factory` & `/backup` | Calibration data (`Asys.bin`, `Areg.bin`, `Hsys.bin`, `Hreg.bin`) | 1.5 MB (`0x180000`) |
| **Partition 3** | `/boot` (Main) | Main `vmlinux` kernel + CramFS `rootfs.img` | 4 MB (`0x400000`) |
| **Partition 5** | `/av` | DSP / Audio-Video Microcode (`av.bin`, `sa.bin`) | 3.5 MB (`0x380000`) |
| **Partition 6** | `/usr` & App | Userland binaries, FSK GUI framework, fonts (`bin.tar`, `fskapp.tar`) | 16 MB (`0x1000000`) |
| **Partition 11**| MMC / Storage | FAT32 Internal Storage image | ~16 MB (`0xFFFE00`) |

---

## 4. Key Reversal Breakthroughs for DSC-W300

Analysis of `OpenMemories-CI/tests/test_cxd4108.py` directly resolves the mystery surrounding language selection and destination persistence on the **DSC-W300** and related models:

### 1. The Destination Byte Location
In `Partition 2` (`/factory/` and `/backup/`), the camera destination is stored at byte offset **`0x00`** in `Asys.bin` and mirrored in `Areg.bin`:
```python
# Synchronize destination byte from Asys to Areg:
Areg.bin = Asys.bin[0:1] + Areg.bin[1:]
```

### 2. Supported Symbolic Destination Enums
| Destination ID | Symbolic Region | Language Set & Behaviors |
| :---: | :---: | :--- |
| `0x01` | **J1** | Japanese Domestic (Japanese only) |
| `0x02` | **UC2** | North America (English, French, Spanish) |
| `0x03` | **CEE8** | Europe (English default, Polish, German, French, Italian, etc.) |
| `0x04` | **CEE9** | Eastern Europe (English default, Russian, etc.) |
| `0x05` | **E32** | Asia / Oceania (English, Traditional Chinese) |
| `0x06` | **KR2** | Korea (Korean, English) |
| `0x07` | **CN2** | China Domestic (Simplified Chinese, English) |

### 3. Hardware Feature Flags in `Asys.bin` & `Hreg.bin`
* `Asys.bin[0x2A5]`: Touchscreen controller enable (`0x01` = Active, e.g. G3; `0x00` = Disabled, e.g. W90/W300).
* `Asys.bin[0x2A6]`: Automatic lens cover motor enable (`0x01` = Active).
* `Hreg.bin[0x400]`: Video standard selector (`0x02` = NTSC, `0x01` = PAL).

---

## 5. Compiling and Running QEMU with CXD4108

### Prerequisites
* Xcode Command Line Tools (`xcode-select --install`)
* Host development packages (`pkg-config`, `glib`, `pixman` available via Homebrew)

### Building `sources/qemu`
```bash
cd sources/qemu
./configure --target-list=arm-softmmu --disable-docs --disable-tools --disable-user
make -j$(sysctl -n hw.ncpu)
```
Upon completion, the compiled binary resides at `sources/qemu/arm-softmmu/qemu-system-arm`.

### Checking Tooling Status
Run from the repository root:
```bash
python3 tools/cxd4108_emulator/qemu_launcher.py status
```

### Generating QEMU Launch Command
```bash
# Print launch arguments for DSC-G3:
python3 tools/cxd4108_emulator/qemu_launcher.py print-args --model g3 --nand nand.dat --mmc mmc.dat

# Print launch arguments for DSC-W90:
python3 tools/cxd4108_emulator/qemu_launcher.py print-args --model w90 --nand nand.dat
```

---

## 6. Safe Firmware Verification Workflow

Using the emulator, we can verify modified firmware from [`tools/g3_text_poc.py`](file:///Users/andrzejpara/Documents/03_Projekty_Techniczne/DSC-W300/tools/g3_text_poc.py) safely:
1. Generate custom signed firmware using `g3_text_poc.py --string "TEST STRING"`.
2. Extract the updated section payload (`fskapp1.tar`).
3. Build `nand.dat` using `Cxd4108FlashBuilder`.
4. Boot `qemu-system-arm -machine cxd4108` in headless QMP mode.
5. Capture a framebuffer screendump via QMP `screendump screen.ppm` and verify menu strings without ever risking real camera hardware.
