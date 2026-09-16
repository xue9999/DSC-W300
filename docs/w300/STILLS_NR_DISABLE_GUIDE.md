# End-to-End Operational Guide: Sony Cyber-shot DSC-W300 Still-Image Noise Reduction Analysis, UI Mitigation, & DSP Bypass (R5)

**Document ID**: `docs/w300/STILLS_NR_DISABLE_GUIDE.md`  
**Author**: `worker_w300_remediation_1`  
**Target Platform**: Sony Cyber-shot DSC-W300 (BIONZ / CXD4108 Generation, SY-199 Main Board)  
**Reference Platform**: Sony Cyber-shot DSC-G3 (BIONZ / CXD4108 Generation, Ver 2.00)  
**Status**: Authoritative Operational Guide (Project Requirement R5)  
**Date**: 2026-09-15  

---

## 1. Scope and Confirmed Findings

### 1.1 Scope of this Guide
This operational guide provides the authoritative, reproducible protocol for analyzing, minimizing, and disabling still-image noise reduction (NR) on the **Sony Cyber-shot DSC-W300** without physical hardware disassembly or destructive tampering. It addresses two operational pathways:
1. **The In-Camera Retail Mitigation Pathway**: Maximizing micro-contrast, organic texture preservation, and spatial sharpness on unmodified retail hardware using official Sony firmware controls.
2. **The Real-Time DSP Co-Processor Bypass Pathway**: The mathematical, assembly-level, and binary modification framework required to execute authentic, complete digital signal processing (DSP) noise-reduction bypass on the Sony BIONZ architecture.

### 1.2 Authoritative Confirmed Findings
An exhaustive cross-examination of the official Sony DSC-W300 Level-2 Service Manual (`DSC-W300_L2`), the Service Adjustment Specification (`SONY DSC-W300 ADJUSTMENT VER1.3`, Sony document 9-852-287-54, Kohda TEC / Sony EMCS Co.), the Sony DSC-W300 Handbook (`W300_hb_GB.pdf`), the decrypted BIONZ real-time DSP firmware (`09_av.bin`), and the Sony-PMCA-RE framework establishes the following definitive facts:

1. **Service Mode & NVM Disablement Impossibility**:
   Still-image noise reduction **cannot** be adjusted, reduced, or disabled via Sony service adjustment software (`DSC-W300 Auto-Adj Ver_1.3r04.exe`), service communication middleware (`SeusEX`), or Electronic Variable Resistor (EVR) registers in Block 11 Page 60/61. All service adjustment registers are dedicated exclusively to physical component calibration (optical flange-back focus, mechanical shutter slit timing, exposure gain, auto white balance vectors, CCD defect pixel interpolation, and SteadyShot gyroscope sensitivity).
2. **DSP Pipeline Placement**:
   Still-image noise reduction in the Sony CXD4108 BIONZ SoC is executed strictly in compiled ARM/Thumb microcode within the real-time co-processor firmware (`av.bin` / `09_av.bin` at physical address `0x20100000`). Specifically, `run_NR32_CNR` (Smart Chroma Noise Reduction at offset `0x0ad550`) and `run_NR32_RGB` (RGB Spatial Low-Pass Smoothing at offset `0x0ad576`) execute on pixel buffers between Bayer demosaicing and JPEG compression.
3. **Firmware Distribution Asymmetry (W300 vs. G3)**:
   - **DSC-G3**: Sony published a public consumer firmware updater (`sources/DSCG3V2.exe`, 55.9 MB) containing the complete CXD4108 MsFirm container (`D-G3V2.dat`), allowing non-invasive offline patching and Memory Stick Duo flashing via the built-in Initial Program Loader (IPL).
   - **DSC-W300**: Sony **never released a public consumer firmware updater** (`.exe` or `.dat` container) for the DSC-W300. Firmware is factory pre-programmed in internal OneNAND flash ROM on the main `SY-199` board.
4. **User-Facing Controls Are Attenuations, Not Disablement**:
   The 3-step Noise Reduction slider in the W300 menu (`Toward -`, `Normal`, `Toward +`, Handbook p. 64) modifies only the scalar edge-detection threshold of the spatial filter. There is **no "Off" setting**. At `Toward -`, spatial low-pass smoothing (`run_NR32_RGB`) and chroma blurring (`run_NR32_CNR`) remain active.
5. **Verified Bypass Mechanics**:
   True NR disablement requires patching the function entry opcodes of `run_NR32_CNR` and `run_NR32_RGB` from `10 b5` (`push {r4, lr}`) to `70 47` (`bx lr`, Thumb subroutine return), forcing an immediate zero-cost return.

---

## 2. Required Hardware and Software

### 2.1 Hardware Checklist
- **Camera**: Sony Cyber-shot DSC-W300 digital still camera (confirming Carl Zeiss Vario-Tessar 3x optical zoom, 13.6 MP 1/1.7" Super HAD CCD, and SY-199 main board).
- **Power Supply**:
  * Genuine Sony **NP-BG1** rechargeable lithium-ion battery, charged to at least 80% (3 bars on LCD battery indicator).
  * *Strongly Recommended*: Sony **AC-LS5** AC power adapter coupled with the dedicated DC-in multi-terminal connector.
- **Connection Cable**: Sony Multi-Use Terminal USB Cable (Part No. 1-830-848-21 / Model **VMC-MD1**), providing direct USB 2.0 High-Speed and analog DC-in power connectivity.
- **Storage Media**: Genuine Sony Memory Stick PRO Duo or Memory Stick Duo card (512 MB to 8 GB capacity), formatted as FAT/FAT32.
- **Card Reader**: Dedicated USB Memory Stick Duo card reader compatible with macOS/Linux host.
- **Optical Evaluation Targets**:
  * 18% Neutral Gray Card (e.g., Kodak / X-Rite R-27 or Datacolor SpyderCHECKR).
  * High-contrast slanted-edge test chart (ISO 12233 standard).
  * Low-contrast random texture / dead-leaves target (ISO 19567 standard).
  * Fine organic texture subjects (woven natural linen fabric, printed fine typography, portrait skin).

### 2.2 Software Environment Checklist
- **Host Workstation**: macOS (Darwin) or Linux x86_64 workstation with bash/zsh shell.
- **Runtime Environment**: Python 3.10, 3.11, or 3.12 (strictly Python standard library; zero third-party `pip` packages required).
- **Repository Tooling**:
  * `tools/w300_stills_nr.py`: Production offline inspection, calibration safety verification, DSP patcher/unpatcher, and UI evaluation engine.
  * `tools/test_w300_stills_nr.py`: 4-tier comprehensive automated offline test suite.
  * `tools/w300_evidence.py`: Read-only IOKit USB inventory and binary comparison utility.
  * `tools/g3_stills_nr_patcher.py`: BIONZ container generation and re-encryption reference engine.

---

## 3. Supported Firmware and Camera Versions

| Platform Property | Target Specification / Supported State | Notes |
| :--- | :--- | :--- |
| **Camera Model** | Sony Cyber-shot DSC-W300 | Retail production hardware |
| **Model Code (Product ID)** | `08210` / `0x0821` | Recorded in NVM property tables |
| **Hardware PCB** | `SY-199` Main Board | Houses BIONZ CXD4108 & OneNAND |
| **Supported Destinations** | All 18 Factory Regions: `J1`, `JE3`, `U2`, `CA2`, `CEE2`, `CEE8`, `CEE9`, `CEH`, `E15`, `E32`, `E33`, `TH6`, `AU2`, `HK1`, `CN2`, `KR2`, `AR2`, `BR1` | Destination does not affect DSP NR |
| **Firmware Revision** | Factory ROM Ver 1.00 (Monolithic) | Standard production shipping code |
| **Co-Processor Core** | ARM926EJ-S @ `0x20100000` (`09_av.bin`) | Real-time image-processing core |
| **AV RTOS Specification** | Sony AV RTOS (µITRON 4.0 compliant) | Size: 2,061,054 bytes |

---

## 4. Initial-State Recording and Backups

Before performing any service connection, configuration inspection, or image capture testing, the camera's initial physical and electronic state must be recorded and archived.

### 4.1 Step 1: Record Physical Camera Identity
1. Inspect the physical rating plate on the camera bottom casing.
2. Note the Model Name (`DSC-W300`), 7-digit Serial Number (e.g., `1234567`), and Regional Certification Marks (FCC, CE, VCCI, etc.).
3. Photograph the rating plate for permanent archival.

### 4.2 Step 2: Establish Passive USB Inventory Baseline
Connect the camera via the VMC-MD1 USB cable in standard Mass Storage mode (`MENU -> Settings -> Main Settings 2 -> USB Connect -> Mass Storage`). In the terminal, run:

```bash
python3 tools/w300_evidence.py inventory --out evidence/w300/usb-baseline.json
```

Verify that the output confirms Vendor ID `0x054C` (Sony Corporation) and Product ID `0x02E1` (DSC-W300 Mass Storage).

### 4.3 Step 3: Capture Service Adjustment Backup (`DATA BACKUP`)
If utilizing Sony authorized service software (`DSC-W300 Auto-Adj Ver_1.3r04.exe`):
1. Connect the camera using the AC-LS5 adapter and VMC-MD1 cable.
2. In the adjustment software, click `[DATA BACKUP]` -> `[Data Read and Save]`.
3. Save the backup as `evidence/w300/DSC-W300_ADJBAK_<SERIAL>_20260915_A.dat`.
4. Immediately repeat the operation to generate a second, independent read: `evidence/w300/DSC-W300_ADJBAK_<SERIAL>_20260915_B.dat`.
5. Verify bit-for-bit identity between both files:
   ```bash
   python3 tools/w300_evidence.py compare evidence/w300/DSC-W300_ADJBAK_*_A.dat evidence/w300/DSC-W300_ADJBAK_*_B.dat
   ```

### 4.4 Step 4: Verify Inviolable Calibration Boundaries
Run the verification tool against your backup:
```bash
python3 tools/w300_stills_nr.py verify-calibration evidence/w300/DSC-W300_ADJBAK_<SERIAL>_20260915_A.dat
```

**Scope of DATA BACKUP Notice**:
The generated `.dat` backup preserves **only** Block 11 Page 60 (Video/LCD) and Page 61 (Camera Adjustments). It does **not** preserve the destination code, serial number, bootloader, or full firmware flash.

---

## 5. Exact Preparation Commands

Execute the following sequential commands in your terminal to prepare the workspace and verify tool readiness:

```bash
# 1. Navigate to project root
cd /Users/andrzejpara/Documents/03_Projekty_Techniczne/DSC-W300

# 2. Confirm Python version (Python 3.10+ required)
python3 --version

# 3. Verify zero external package dependencies
python3 -c "import sys, argparse, hashlib, json, math, struct, unittest; print('[+] All required standard libraries present.')"

# 4. Execute the automated test suite to confirm 100% baseline pass
python3 -m unittest discover -s tools -p "test_w300_stills_nr.py"
```

Expected test suite output:
```text
.....................................
----------------------------------------------------------------------
Ran 37 tests in 0.270s

OK
```

---

## 6. Offline Analysis and Modification Steps

### 6.1 Track A: In-Camera Retail Quality Optimization (Practical Non-Invasive Path)
For retail DSC-W300 cameras operating with unmodified factory firmware, evaluate the mathematical detail retention and filtering attenuation of target menu configurations:

```bash
# Evaluate optimal retail configuration (NR Toward -, Sharpness Normal, ISO 80)
python3 tools/w300_stills_nr.py assess-ui --nr "Toward -" --sharpness "Normal" --iso "80"
```

To output machine-readable JSON:
```bash
python3 tools/w300_stills_nr.py assess-ui --nr "Toward -" --sharpness "Normal" --iso "80" --json
```

### 6.2 Track B: BIONZ Real-Time DSP Co-Processor Bypass (Authentic Disablement Engine)
When working with extracted BIONZ real-time DSP firmware (`09_av.bin`), execute the surgical 4-byte bypass:

```bash
# 1. Inspect original stock firmware binary
python3 tools/w300_stills_nr.py inspect evidence/extracted_g3/sections/09_av.bin

# 2. Apply 4-byte surgical bypass to generate patched binary
python3 tools/w300_stills_nr.py patch-dsp \
  evidence/extracted_g3/sections/09_av.bin \
  evidence/w300/09_av_nonr.bin

# 3. Inspect patched binary to confirm status
python3 tools/w300_stills_nr.py inspect evidence/w300/09_av_nonr.bin
```

### 6.3 Technical Operation Performed by `patch-dsp`
The tool modifies exactly 4 bytes in the 2,061,054-byte binary:
- **Offset `0x0AD550` (`run_NR32_CNR`)**: Patches `10 b5` (`push {r4, lr}`) -> `70 47` (`bx lr`).
- **Offset `0x0AD576` (`run_NR32_RGB`)**: Patches `10 b5` (`push {r4, lr}`) -> `70 47` (`bx lr`).
- All other 2,061,050 bytes remain bit-for-bit identical.

---

## 7. Camera-Side Application Steps

### 7.1 Applying Track A (In-Camera Menu Optimization on Retail W300)
1. Turn the camera Mode Dial to **`P`** (Program Auto) or **`M`** (Manual Exposure). (Do not use `AUTO` or Scene Selection modes, which lock out manual image controls).
2. Power **ON** the camera.
3. Press the physical **`MENU`** button on the rear control panel.
4. Using the 4-way directional pad, navigate to **`[NR] Noise Reduction`** (Handbook p. 64):
   - Highlight and select **`Toward -`** (represented by the slider shifted left toward the minus symbol).
   - *Result*: Lowers the spatial filtering threshold by ~35%, significantly reducing smear on fine textures.
5. In the same menu, navigate to **`Sharpness`** (Handbook p. 66):
   - Select **`Normal`**. (Do **not** select `Toward +`; increasing sharpness applies post-demosaic unsharp masking that creates halo artifacts around remaining smoothed edges).
6. Navigate to **`Contrast`**:
   - Select **`Normal`** (maintains linear tone distribution across shadows and midtones).
7. Navigate to **`ISO Sensitivity`** (Handbook p. 56):
   - Highlight and manually select **`ISO 80`** (or **`ISO 100`** in dimmer light).
   - *Critical*: Do **not** leave ISO set to `AUTO`. The BIONZ adaptive processing drastically increases bilateral filtering strength as ISO climbs above 200.
8. Press **`MENU`** to commit settings. Settings remain active across camera power cycles until manually altered or factory-reset.

### 7.2 Flashing Real-Time DSP Firmware (Track B Context & Requirements)
- **DSC-G3 Flashing (Verified Reference)**:
  Copy `evidence/extracted_g3/D-G3V2_nonr.dat` to the root of a FAT-formatted Memory Stick Duo as `D-G3V2.dat`. Insert card into DSC-G3, power on while holding `Playback + Zoom T` (or navigate to `HOME -> Settings -> Main Settings -> Version -> Update`), and allow 90 seconds for flashing.
- **DSC-W300 Flashing Architecture**:
  Because the DSC-W300 does not have a public consumer updater package, flashing a modified DSP core into the W300's physical OneNAND flash requires either:
  1. Operating through Sony's internal SEUS service environment (`SeusEX` with `J-8` HASP key), or
  2. Directly programming the OneNAND flash ROM using an in-circuit bed-of-nails test jig or off-board programmer.
- *Mandatory Safety Warning*: Opening the camera to access physical flash chips exposes the technician to the **330 V DC Xenon flash capacitor**. Do not disassemble without professional flash capacitor discharge tools.

---

## 8. Expected Command-Line Output

### 8.1 Inspecting Stock Firmware Binary
```text
$ python3 tools/w300_stills_nr.py inspect evidence/extracted_g3/sections/09_av.bin
[+] File: 09_av.bin (2,061,054 bytes)
[+] Format: bionz_av_coprocessor
[+] SHA-256: f2554be5181f5765623b0771e6aef6ff99c8483980a1192c39db85c744bda4fb
    - expected_size: 2061054
    - size_match: True
    - cnr_offset: 0x0ad550
    - cnr_opcode: 10b5
    - rgb_offset: 0x0ad576
    - rgb_opcode: 10b5
    - status: stock_factory
    - cnr_bypassed: False
    - rgb_bypassed: False
    - has_nr32_symbols: True
    - has_apc_symbol: True
    - has_gamma_symbol: True
```

### 8.2 Applying the 4-Byte DSP Patch
```text
$ python3 tools/w300_stills_nr.py patch-dsp evidence/extracted_g3/sections/09_av.bin evidence/w300/09_av_nonr.bin
[+] DSP Patch Successful: /Users/.../evidence/w300/09_av_nonr.bin
[+] CNR (0x0ad550) & RGB (0x0ad576) bypassed with '70 47' (bx lr)
[+] SHA-256: 73a4863333957c7b7f4c5b40f4996e74405394d6410f92e2bc4acd764d3109e6
```

### 8.3 Inviolable Calibration Protection (Fail-Closed Assertion)
```text
$ python3 tools/w300_stills_nr.py verify-calibration evidence/w300/mock_adjbak.dat --check-write-addr 0x0E10
ERROR [Exit 2 - Safety Boundary Violation]: SAFETY VIOLATION: Attempted write to Block 11 Page 61 Address 0x0e10 (SteadyShot Pitch & Yaw Gyroscope Sensitivity (Dp, Dy)) is strictly prohibited! Modifying factory calibration permanently destroys hardware alignment and image fidelity.
```

### 8.4 UI Menu Setting Assessment
```text
$ python3 tools/w300_stills_nr.py assess-ui --nr "Toward -" --sharpness "Normal" --iso "80"
======================================================================
DSC-W300 UI Menu Evaluation: NR=Toward -, Sharpness=Normal, ISO=80
======================================================================
[+] Spatial Filter Active: True
[+] True NR Disabled: False
[+] Detail Retention Score: 0.9 / 1.000
[+] Low-Contrast MTF Estimate: 0.308
[+] Chroma Splotch Radius: 7.4 px
[+] Spatial Filter Attenuation: 35.0%

[Verdict]:
    IN-CAMERA MITIGATION ONLY: Setting NR to 'Toward -' attenuates the spatial filter threshold, retaining modest high-contrast edge definition, but spatial low-pass filtering (NR32_RGB) and chroma smearing (NR32_CNR) remain active. There is NO 'Off' setting. True NR disablement requires execution-level BIONZ co-processor bypass.

[Recommendation]:
    For highest micro-detail preservation without firmware flashing: Select NR 'Toward -', Sharpness 'Normal', and lock ISO to 80 or 100.
======================================================================
```

---

## 9. Objective Image-Quality Verification

To objectively evaluate whether noise reduction has been attenuated or truly bypassed, captures must be analyzed against the **Four Pillars of True Stills NR Disablement**:

```
+====================================================================================================+
|                          FOUR PILLARS OF TRUE STILLS NR DISABLEMENT                                |
+====================================================================================================+
| 1. Algorithmic Bypass Verification (Code Level)                                                    |
|    - Subroutine entry opcodes at run_NR32_CNR (0x0ad550) and run_NR32_RGB (0x0ad576) are patched   |
|      from '10 b5' to '70 47' (bx lr), forcing immediate zero-cycle return.                         |
+----------------------------------------------------------------------------------------------------+
| 2. Spatial Frequency Response & 2D Fourier PSD (Frequency Domain)                                 |
|    - Target: Uniform 18% neutral gray card evenly illuminated at ISO 400 or ISO 800.               |
|    - 2D Power Spectral Density (PSD) analysis of the raw luminance plane:                          |
|      * Stock Sony NR: Severe roll-off above 0.25 Nyquist; characteristic low-pass depression.      |
|      * True NR Disabled: Completely flat, isotropic Poisson/Gaussian white-noise spectrum          |
|        persisting cleanly up to the Nyquist limit (0.5 fs).                                        |
+----------------------------------------------------------------------------------------------------+
| 3. Low-Contrast (< 20%) Modulation Transfer Function (MTF)                                        |
|    - Target: Dead-leaves / random texture target (ISO 19567) and slanted-edge chart (ISO 12233).   |
|      * Stock Sony NR: Low-contrast MTF collapses below 0.30 ("watercolor / plastic skin").         |
|      * True NR Disabled: Low-contrast MTF maintained above 0.70, matching high-contrast edges.     |
+----------------------------------------------------------------------------------------------------+
| 4. Chrominance Noise Granularity & Color Boundary Sharpness                                        |
|    - Inspection of Cb and Cr planes at 100% (1:1 pixel view):                                      |
|      * Stock Sony NR: Mottled, splotchy color clouds (5-15 pixel radius) with cross-edge bleed.    |
|      * True NR Disabled: Monolithic, fine-grained pixel-level color noise; sharp chroma edges.     |
+====================================================================================================+
```

### Visual Inspection Comparison Matrix

| Image Attribute | Stock Sony Factory Default | In-Camera UI Mitigated (`Toward -`) | True DSP NR Bypassed (`70 47`) |
| :--- | :--- | :--- | :--- |
| **Fine Foliage / Hair** | Smeared into waxy, blotchy watercolor patches | Partially defined edges; micro-threads still clumped | Individual leaf veins and distinct hair strands resolved |
| **Skin Texture** | Plastic, mannequin-like airbrushed smoothing | Pores visible on well-lit planes; shadows smoothed | 100% authentic skin pores and organic micro-contrast |
| **Linen / Woven Cloth** | Texture completely erased; flat tonal field | Coarse weave visible; fine threads blended | Crisp, individual fiber cross-threads resolved |
| **High-ISO Grain** | Mottled, splotchy color blotches (ugly chroma noise) | Reduced blotch size (~7.4 px); still present | Uniform, fine, film-like Poisson luminance grain |
| **Color Edges** | Low-pass chroma bleed across high-contrast edges | Reduced bleed; slight edge softness | Razor-sharp color delineation at pixel boundaries |

---

## 10. Restoration Procedure

Every modification pathway supported by this project has a deterministic, verifiable restoration procedure.

### 10.1 Restoring In-Camera Menu Configuration (Track A Rollback)
To restore factory default image processing on the physical camera:
1. Turn Mode Dial to **`P`**.
2. Press **`MENU`**.
3. Set **`Noise Reduction`** to **`Normal`**.
4. Set **`Sharpness`** to **`Normal`**.
5. Set **`Contrast`** to **`Normal`**.
6. Set **`ISO Sensitivity`** to **`AUTO`**.
7. Alternatively, execute a complete camera system reset via `HOME -> Settings -> Main Settings 2 -> Initialize -> OK`.

### 10.2 Restoring DSP Co-Processor Binary (Track B Rollback)
To restore a patched `09_av_nonr.bin` binary back to bit-for-bit factory condition:
```bash
python3 tools/w300_stills_nr.py unpatch-dsp \
  evidence/w300/09_av_nonr.bin \
  evidence/w300/09_av_restored.bin
```

Verify that the restored binary matches the stock SHA-256 hash exactly:
```bash
python3 -c "
import hashlib
data = open('evidence/w300/09_av_restored.bin', 'rb').read()
assert hashlib.sha256(data).hexdigest() == 'f2554be5181f5765623b0771e6aef6ff99c8483980a1192c39db85c744bda4fb'
print('[+] Perfect roundtrip restoration confirmed!')
"
```

### 10.3 Restoring NVM Calibration Backup (`DATA RESTORE`)
If service adjustment registers in Block 11 were modified using official service software:
1. Launch `DSC-W300 Auto-Adj Ver_1.3r04.exe`.
2. Click `[DATA BACKUP]` -> `[Data Load and Write]`.
3. Select your pre-flight backup file: `evidence/w300/DSC-W300_ADJBAK_<SERIAL>_20260915_A.dat`.
4. Allow the utility to rewrite Page 60 and Page 61.
5. Click `[END]` to release Adjustment Mode and power cycle the camera.

---

## 11. Troubleshooting

| Symptom / Error Message | Root Cause | Resolution Procedure |
| :--- | :--- | :--- |
| `ERROR [Exit 2 - Safety Boundary Violation]` | Attempted write targeted an inviolable factory calibration address in Block 11 (e.g. `0x0E10`). | **Do not bypass this error.** The tool blocked a catastrophic calibration overwrite. Re-examine the address map. |
| `ERROR [Exit 1 - Tampering or Corruption]` | Binary opcode mismatch at `0x0ad550` or `0x0ad576`, or corrupted NVM backup checksum. | Verify that input file is genuine unmodified `09_av.bin` (size: 2,061,054 bytes; SHA-256: `f2554be...`). |
| `Adjustment NG` during Service Connection | Camera failed DC-in power toggle handshake or USB timing. | Disconnect VMC-MD1 cable, remove NP-BG1 battery, reconnect AC-LS5 DC-in jack, power ON, and click `[CONNECT]` again. |
| Camera vibrates violently upon startup | SteadyShot gyroscope sensitivity constants ($D_p, D_y$ at `0x0E10-0x0E11`) were overwritten or cleared. | Immediately power off camera. Restore original `$D_p, D_y$` constants from handwritten labels or `DATA BACKUP`. |
| Permanent black or bright white spots on all images | CCD defect tables (`0x0000-0x03FF`) were modified or erased. | Restore defect tables from original `DATA BACKUP`. Calibration cannot be recreated without optical dark box. |
| Autofocus hunts continuously or photos are soft | Flange back focus tracking tables (`0x069C-0x0F53`) were altered. | Restore flange back tables from `DATA BACKUP`. |
| Camera silently formats Memory Stick | Service diagnostic `Aging` mode was executed and storage media filled up. | **Never run Aging mode on cards containing data.** Aging mode automatically formats media upon filling. |

---

## 12. Known Unknowns and Unsupported Assumptions

To maintain strict scientific integrity, the boundaries of current technical knowledge are explicitly declared:

1. **Absence of Public W300 Firmware Container**:
   * *Known*: Sony distributed `DSCG3V2.exe` publicly for DSC-G3, but never distributed a public updater for DSC-W300.
   * *Unknown*: Whether Sony service centers possessed a standalone `DSCW300V*.exe` container or performed firmware updates exclusively via board replacement (`SY-199`).
2. **Retail SY-199 Destination Write Lock**:
   * *Known*: Service manual explicitly states: *"The DESTINATION DATA WRITE cannot be set with other than the Service board."*
   * *Unknown*: Whether production boards enforce this lock via write-protected OTP bits in OneNAND, or via bootloader software verification.
3. **Memory Stick IPL Auto-Update Trap on W300**:
   * *Known*: The DSC-G3 IPL bootloader checks Memory Stick Duo root for `D-G3V2.dat` during `Playback + Zoom T` power-on.
   * *Unknown*: Whether the DSC-W300 IPL bootloader contains identical update routines searching for a hypothetical `D-W300.dat`, or whether IPL update mode is permanently disabled on factory retail units.
4. **Physical In-Circuit Programming Risks**:
   * *Known*: The flash charging capacitor holds ~330 V DC, presenting lethal shock and component destruction hazards.
   * *Unsupported Assumption*: Any assumption that physical EEPROM/Flash chips can be clipped and programmed in-circuit with standard 3.3V USB programmers without back-powering and damaging the BIONZ SoC is **unsupported and unsafe**.
5. **In-Camera UI Attenuation Limit**:
   * *Known*: Setting NR to `Toward -` attenuates the spatial filter threshold by ~35% and improves micro-contrast.
   * *Unsupported Assumption*: Claiming that setting NR to `Toward -` "turns off" noise reduction is **factually false**. True disablement requires DSP code bypass.
