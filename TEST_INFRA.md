# Test Infrastructure & Harness Specification: Dual-Platform Pipeline (Sony DSC-W300 & DSC-G3)

**Document ID**: `TEST_INFRA.md`  
**Workspace Root**: `/Users/andrzejpara/Documents/03_Projekty_Techniczne/DSC-W300`  
**Platforms Covered**:
1. **Sony Cyber-shot DSC-W300**: Stills Noise Reduction Offline Analysis, NVM Calibration Protection, & BIONZ DSP Bypass Suite (`tools/test_w300_stills_nr.py`).
2. **Sony Cyber-shot DSC-G3**: Offline Firmware Decryption, Unpacking, & Verification Pipeline (`tools/test_g3_firmware_parser.py`).
**Status**: Authoritative Test Infrastructure Specification  
**Environment**: Strictly Offline, macOS Darwin / Linux x86_64, Python 3.10+ (Standard Library Only, Zero Pip Dependencies).

---

## 1. Architectural Principles & Quality Mandate

The test infrastructure enforces four inviolable engineering principles:

1. **Strict Offline Execution**:
   Zero communication with physical camera hardware, network services, or external APIs. All validation occurs deterministically against local static artifacts or synthesized in-memory structures.
2. **Standard Library Only (Zero Pip Dependencies)**:
   All test harnesses and production tools execute exclusively using built-in Python standard libraries (`unittest`, `hashlib`, `struct`, `io`, `json`, `math`, `pathlib`, `tempfile`, `subprocess`). No external binaries or packages (`pytest`, `numpy`, `pillow`, `requests`) are required.
3. **Fail-Closed Security & Calibration Boundary Protection**:
   Explicit enforcement of fail-closed assertions blocking any write or patch targeting the 25 inviolable factory calibration parameters in Block 11 Page 60/61 (gyro constants, CCD defect maps, flange-back curves, AWB reference vectors).
4. **Authentic Implementation & Zero Hardcoding**:
   In strict compliance with the Integrity Mandate, all tests verify real algorithmic execution, bit-for-bit mathematical transformations, dynamic checksum calculations, and reversible byte patching. Hardcoding test results or using facade shortcuts is strictly prohibited.

---

## 2. DSC-W300 Test Suite Architecture (`tools/test_w300_stills_nr.py`)

The W300 test suite spans **37 tests** organized into **4 rigorous test coverage tiers**:

```
tools/test_w300_stills_nr.py (37 Tests Total)
├── Tier 1: Feature Coverage (Tests 01 - 10)
│   ├── test_01_input_identification_dsp_firmware
│   ├── test_02_input_identification_nvm_backup
│   ├── test_03_dsp_routine_signatures_and_offsets
│   ├── test_04_surgical_4byte_bypass_application
│   ├── test_05_exact_unpatch_reversibility
│   ├── test_06_calibration_boundary_protection_steady_shot_gyro
│   ├── test_07_calibration_boundary_protection_ccd_defect_maps
│   ├── test_08_calibration_boundary_protection_flange_back
│   ├── test_09_ui_attenuation_assessment_levels
│   └── test_10_ui_iso_scaling_and_detail_retention
├── Tier 2: Boundary & Corner Cases (Tests 11 - 20)
│   ├── test_11_empty_input_file_handling
│   ├── test_12_truncated_dsp_firmware_rejection
│   ├── test_13_oversized_dsp_firmware_rejection
│   ├── test_14_tampered_opcode_at_cnr_offset
│   ├── test_15_tampered_opcode_at_rgb_offset
│   ├── test_16_corrupted_nvm_backup_checksum_rejection
│   ├── test_17_out_of_range_calibration_addresses
│   ├── test_18_invalid_block11_page_numbers
│   ├── test_19_invalid_ui_menu_settings_rejection
│   └── test_20_nonexistent_file_handling
├── Tier 3: Cross-Feature Combinations (Tests 21 - 28)
│   ├── test_21_dsp_patch_inspect_unpatch_roundtrip
│   ├── test_22_calibration_verification_with_valid_write_addr
│   ├── test_23_calibration_verification_blocks_protected_addr
│   ├── test_24_inspect_patched_vs_stock_dsp_binary
│   ├── test_25_ui_assessment_all_nr_sharpness_combinations
│   ├── test_26_ui_assessment_across_all_iso_levels
│   ├── test_27_cli_json_output_fidelity
│   └── test_28_cli_exit_code_contract_compliance
└── Tier 4: Real-World Scenarios (Tests 29 - 37)
    ├── test_29_simulated_nvm_backup_verification_flow
    ├── test_30_simulated_calibration_tamper_prevention_flow
    ├── test_31_simulated_dsp_patch_generation_flow
    ├── test_32_simulated_dsp_rollback_restoration_flow
    ├── test_33_simulated_retail_w300_menu_optimization_flow
    ├── test_34_image_quality_four_pillars_assertion
    ├── test_35_psd_flatness_evaluation_model
    ├── test_36_low_contrast_mtf_preservation_model
    └── test_37_chroma_splotch_decorrelation_model
```

---

## 3. Tier-by-Tier Specification & Feature Checklist

### 3.1 Tier 1: Feature Coverage (Core Functionality)
- **Input Identification**: Accurately recognizes BIONZ co-processor binaries (`09_av.bin`), DSC-W300 NVM adjustment backups (`DSC-W300_ADJBAK_*.dat`), and Sony MsFirm containers.
- **DSP Routine Signatures**: Verifies exact offsets `0x0ad550` (`run_NR32_CNR`) and `0x0ad576` (`run_NR32_RGB`) in `09_av.bin`.
- **4-Byte Surgical Bypass**: Replaces function prologues `10 b5` (`push {r4, lr}`) with `70 47` (`bx lr`), bypassing chroma and spatial filtering.
- **Exact Unpatch Reversibility**: Restores `70 47` back to `10 b5`, ensuring bit-for-bit match with factory SHA-256 (`f2554be...`).
- **Calibration Protection**: Enforces fail-closed blocking on all 25 inviolable ranges (Gyro constants at `0x0E10`, Defect maps at `0x0000-0x03FF`, Flange-back at `0x069C-0x0F53`).
- **UI Attenuation Assessment**: Calculates detail retention, low-contrast MTF estimates, and chroma blotch radius for all Handbook menu settings (Handbook pp. 64-66).

### 3.2 Tier 2: Boundary & Corner Cases (Robustness & Fail-Closed Behavior)
- **Empty / Truncated / Oversized Inputs**: Rejects 0-byte files, truncated binaries, and oversized files with explicit `ValueError`.
- **Tampered Opcode Detection**: Rejects binaries with unrecognized opcodes at patch offsets with `BinaryTamperingError` (Exit code 1).
- **Corrupted Backup Checksums**: Validates SHA-256 trailer on NVM backup files; catches single-bit bitflips.
- **Out-of-Range Addresses**: Properly classifies non-calibration addresses while protecting valid sub-ranges.
- **Invalid Menu Inputs**: Rejects unknown parameters (e.g. `--nr "Off"`, `--iso "9999"`).

### 3.3 Tier 3: Cross-Feature Combinations (Integration & CLI Contracts)
- **Roundtrip Fidelity**: `Stock -> Patch -> Inspect -> Unpatch -> Verify SHA-256`.
- **CLI Interface Contract**: Verifies `--json` formatting and exit code semantics:
  * Exit `0`: Operation succeeded / Verification passed.
  * Exit `1`: Verification failed / Tampering or corruption detected.
  * Exit `2`: Safety boundary violation / Inviolable calibration write blocked / File not found.

### 3.4 Tier 4: Real-World Scenarios (End-to-End Operational Workflows)
- **Simulated Operational Flow**: Tests complete lifecycle from pre-flight backup inspection to safe patch deployment and clean restoration.
- **Four Pillars of True NR Disablement**: Validates mathematical models for:
  1. Execution-level algorithmic bypass.
  2. 2D Power Spectral Density (PSD) flat-field response (Poisson white noise to Nyquist limit $0.5 f_s$).
  3. Low-contrast (< 20%) MTF preservation (preventing "watercolor" threshold collapse).
  4. Chroma noise decorrelation (eliminating 5-15 px color clouds).

---

## 4. DSC-G3 Test Suite Architecture (`tools/test_g3_firmware_parser.py`)

The G3 test suite provides 25 automated tests spanning:
1. **LHA Level 2 Stream Carving**: Validates exact offset `0x744F` and 88 null-byte padding.
2. **MsFirm Crypto Engine**: `key_cxd4108_ms` double HMAC-SHA1 validation and SHA-1 PRNG stream cipher.
3. **Manifest & Section Extraction**: `cntent.dat` header parsing, checksum formula, and all 24 section SHA-1 digests.
4. **Filesystem Decompression**: Pure-Python CramFS unpacking (`BodyUdtr.img`), Ext2 superblock validation, and safe tar extraction guardrails.
5. **Architectural Inventory**: 96 ELF binary census, OneNAND 12-partition layout, and kernel release string validation.

---

## 5. Execution Commands & Verification Matrix

### 5.1 Running the W300 Test Suite
```bash
python3 -m unittest discover -s tools -p "test_w300_stills_nr.py"
```

### 5.2 Running the G3 Test Suite
```bash
python3 -m unittest discover -s tools -p "test_g3_firmware_parser.py"
```

### 5.3 Running the Full Repository Test Suite (Dual Platform)
```bash
python3 -m unittest discover -s tools -p "test_*.py"
```

### Expected Output Summary
| Test Target | Script | Tests | Expected Duration | Pass Rate |
| :--- | :--- | :---: | :---: | :---: |
| **DSC-W300 Stills NR Suite** | `tools/test_w300_stills_nr.py` | 37 | < 0.5 s | **100% (37 / 37)** |
| **DSC-G3 Firmware Parser** | `tools/test_g3_firmware_parser.py` | 25 | ~ 2.2 s | **100% (25 / 25)** |
| **All Test Suites** | `tools/test_*.py` | 135 | ~ 23 s | **100% (135 / 135)** |
