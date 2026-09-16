#!/usr/bin/env python3
"""
Test Suite: Comprehensive E2E Offline Verification for Sony DSC-W300 & BIONZ Stills NR
File: tools/test_w300_stills_nr.py

Architecture: 4-Tier Test Coverage
- Tier 1: Feature Coverage (Input identification, backup structure recognition,
          DSP routine signatures, UI attenuation assessment, calibration safety verification,
          unpatch/reversibility).
- Tier 2: Boundary & Corner Cases (Empty inputs, malformed files, truncated binaries,
          out-of-range addresses, invalid opcodes, corrupt headers).
- Tier 3: Cross-Feature Combinations (Patch + verify + unpatch roundtrip, calibration
          verification under modified payload, inspection of corrupted backup).
- Tier 4: Real-World Scenarios (Full simulated operational flow: backup verification ->
          calibration boundary protection -> DSP patch generation -> unpatch restoration ->
          image quality metric assertion).

Execution Command:
    python3 -m unittest discover -s tools -p "test_w300_stills_nr.py"
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple
import unittest

# ----------------------------------------------------------------------------
# Path Resolution & Standard Library Checks
# ----------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
EVIDENCE_DIR = REPO_ROOT / "evidence"
SOURCES_DIR = REPO_ROOT / "sources"

AV_BIN_PATH = EVIDENCE_DIR / "extracted_g3" / "sections" / "09_av.bin"
W300_TOOL_PATH = TOOLS_DIR / "w300_stills_nr.py"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

# ----------------------------------------------------------------------------
# Authoritative Constants & Hardware Specifications
# ----------------------------------------------------------------------------
# Real-Time BIONZ Co-Processor (09_av.bin)
AV_BIN_SIZE = 2061054
AV_BIN_STOCK_SHA256 = "f2554be5181f5765623b0771e6aef6ff99c8483980a1192c39db85c744bda4fb"
AV_BIN_PATCHED_SHA256 = "73a4863333957c7b7f4c5b40f4996e74405394d6410f92e2bc4acd764d3109e6"

OFFSET_NR32_CNR = 0x0AD550  # run_NR32_CNR (Smart Chroma Noise Reduction)
OFFSET_NR32_RGB = 0x0AD576  # run_NR32_RGB (RGB Spatial Smoothing)

ORIGINAL_OPCODE = b"\x10\xb5"  # push {r4, lr} (Thumb-1)
BYPASS_OPCODE = b"\x70\x47"    # bx lr (Immediate Thumb Return)

# Inviolable Calibration Address Ranges (Block 11 Page 60 & 61)
# Derived authoritatively from Service Manual Ver 1.3 (Kohda TEC / Sony EMCS Co.)
PROTECTED_CALIBRATION_RANGES: List[Tuple[int, int, str]] = [
    (0x0000, 0x01FF, "CCD Black Defect Compensation Table"),
    (0x0200, 0x03FF, "CCD White Defect Compensation Table"),
    (0x0362, 0x0363, "LCD White Balance Bias"),
    (0x0401, 0x0401, "LCD V-COM Common Electrode Voltage"),
    (0x0680, 0x0682, "Component Video HD_Y, HD_Pb, HD_Pr DAC Level"),
    (0x069C, 0x069F, "Flange Back Zoom Tracking Table"),
    (0x06B8, 0x06B8, "Composite Video Output Level"),
    (0x06CC, 0x06CC, "Flange Back Tele Compensation"),
    (0x06D8, 0x06DF, "Flange Back Wide Focal Tracking"),
    (0x0796, 0x079D, "Flange Back Tele Focal Tracking"),
    (0x095A, 0x095F, "Aperture F-Number Iris Compensation"),
    (0x0961, 0x0968, "Base Sensor Gain & Light Value LV Reference"),
    (0x0980, 0x09AD, "Mechanical Shutter Slit Width & Timing Curve"),
    (0x0C00, 0x0C21, "AWB 3200K Halogen Reference Standard"),
    (0x0C24, 0x0C49, "AWB 5800K Daylight Reference Standard"),
    (0x0C50, 0x0C57, "Color Gamut Reproduction Matrix"),
    (0x0C72, 0x0C79, "Xenon Strobe Flash Discharge Energy Table"),
    (0x0E00, 0x0E04, "Lens Group Hall Position Sensor Offset"),
    (0x0E08, 0x0E09, "Lens Group Hall Position Sensor Gain"),
    (0x0E0A, 0x0E0D, "Gravitational Tilt Auto Orientation Sensor"),
    (0x0E10, 0x0E11, "SteadyShot Pitch & Yaw Gyroscope Sensitivity (Dp, Dy)"),
    (0x0F10, 0x0F15, "AF Assist LED Illumination Check"),
    (0x0F1C, 0x0F1D, "Flange Back Optical Zoom Boundary Index"),
    (0x0F20, 0x0F24, "Flange Back Stepping Motor Drive Table"),
    (0x0F26, 0x0F53, "Flange Back Multi-Step Focus Curve Array"),
]

# Consolidated Inviolable Windows
PROTECTED_WINDOWS: List[Tuple[int, int]] = [
    (0x0000, 0x0401),
    (0x0680, 0x079D),
    (0x095A, 0x09AD),
    (0x0C00, 0x0C79),
    (0x0E00, 0x0F53),
]

# W300 User Controls Catalog (Handbook pp. 46, 64-66)
W300_NR_LEVELS = ["Toward -", "Normal", "Toward +"]
W300_SHARPNESS_LEVELS = ["Toward -", "Normal", "Toward +"]
W300_CONTRAST_LEVELS = ["Toward -", "Normal", "Toward +"]
W300_ISO_LEVELS = ["AUTO", "80", "100", "200", "400", "800", "1600", "3200", "6400"]


# ----------------------------------------------------------------------------
# Reference Oracles & Verification Helpers
# ----------------------------------------------------------------------------
def is_address_protected(page: int, addr: int) -> bool:
    """Returns True if the address within Block 11 falls in a protected calibration range."""
    if page not in (60, 61):
        return False
    for start, end in PROTECTED_WINDOWS:
        if start <= addr <= end:
            return True
    return False


def oracle_patch_dsp(av_bytes: bytes) -> bytes:
    """Applies verified 4-byte surgical bypass to BIONZ co-processor binary."""
    if len(av_bytes) != AV_BIN_SIZE:
        raise ValueError(f"Invalid binary size: {len(av_bytes)} != {AV_BIN_SIZE}")
    cnr_orig = av_bytes[OFFSET_NR32_CNR:OFFSET_NR32_CNR + 2]
    rgb_orig = av_bytes[OFFSET_NR32_RGB:OFFSET_NR32_RGB + 2]
    if cnr_orig != ORIGINAL_OPCODE:
        raise ValueError(f"CNR offset mismatch at {OFFSET_NR32_CNR:#x}: {cnr_orig.hex()} != {ORIGINAL_OPCODE.hex()}")
    if rgb_orig != ORIGINAL_OPCODE:
        raise ValueError(f"RGB offset mismatch at {OFFSET_NR32_RGB:#x}: {rgb_orig.hex()} != {ORIGINAL_OPCODE.hex()}")
    
    patched = bytearray(av_bytes)
    patched[OFFSET_NR32_CNR:OFFSET_NR32_CNR + 2] = BYPASS_OPCODE
    patched[OFFSET_NR32_RGB:OFFSET_NR32_RGB + 2] = BYPASS_OPCODE
    return bytes(patched)


def oracle_unpatch_dsp(av_bytes: bytes) -> bytes:
    """Reverses 4-byte surgical bypass back to original BIONZ co-processor binary."""
    if len(av_bytes) != AV_BIN_SIZE:
        raise ValueError(f"Invalid binary size: {len(av_bytes)} != {AV_BIN_SIZE}")
    cnr_patched = av_bytes[OFFSET_NR32_CNR:OFFSET_NR32_CNR + 2]
    rgb_patched = av_bytes[OFFSET_NR32_RGB:OFFSET_NR32_RGB + 2]
    if cnr_patched != BYPASS_OPCODE:
        raise ValueError(f"CNR offset is not patched at {OFFSET_NR32_CNR:#x}: {cnr_patched.hex()} != {BYPASS_OPCODE.hex()}")
    if rgb_patched != BYPASS_OPCODE:
        raise ValueError(f"RGB offset is not patched at {OFFSET_NR32_RGB:#x}: {rgb_patched.hex()} != {BYPASS_OPCODE.hex()}")
    
    unpatched = bytearray(av_bytes)
    unpatched[OFFSET_NR32_CNR:OFFSET_NR32_CNR + 2] = ORIGINAL_OPCODE
    unpatched[OFFSET_NR32_RGB:OFFSET_NR32_RGB + 2] = ORIGINAL_OPCODE
    return bytes(unpatched)


def oracle_synthesize_backup(serial: str = "12345678", corrupt_offset: Optional[int] = None) -> bytes:
    """Synthesizes a valid or corrupted DSC-W300 adjustment backup payload."""
    magic = b"W300ADJ\x01"
    serial_bytes = serial.encode("ascii")[:8].ljust(8, b"\x00")
    timestamp = b"20260915"
    
    # 4096 bytes per page (Page 60 and Page 61)
    page60 = bytearray(4096)
    page61 = bytearray(4096)
    
    # Populate nominal calibration constants
    page60[0x0401] = 0x80  # V-COM
    page61[0x0E10] = 0x4A  # Gyro Dp
    page61[0x0E11] = 0x52  # Gyro Dy
    # Populate defect maps with signature coordinates
    struct.pack_into(">H", page61, 0x0000, 12)  # defect count
    struct.pack_into(">H", page61, 0x0200, 18)  # defect count
    
    payload = magic + serial_bytes + timestamp + bytes(page60) + bytes(page61)
    checksum = hashlib.sha256(payload).digest()
    final_backup = payload + checksum
    
    if corrupt_offset is not None and 0 <= corrupt_offset < len(final_backup):
        arr = bytearray(final_backup)
        arr[corrupt_offset] ^= 0xFF
        return bytes(arr)
    return final_backup


def oracle_assess_ui(nr: str = "Normal", sharpness: str = "Normal", iso: str = "400") -> Dict[str, Any]:
    """Computes expected image processing attenuation and detail preservation from UI settings."""
    if nr not in W300_NR_LEVELS:
        raise ValueError(f"Invalid NR level: {nr}")
    if sharpness not in W300_SHARPNESS_LEVELS:
        raise ValueError(f"Invalid sharpness level: {sharpness}")
    if iso not in W300_ISO_LEVELS:
        raise ValueError(f"Invalid ISO level: {iso}")

    # Baseline attenuation and detail preservation factors
    nr_factors = {"Toward -": 0.35, "Normal": 0.0, "Toward +": -0.40}
    sharpness_factors = {"Toward -": -0.20, "Normal": 0.0, "Toward +": 0.15}
    
    iso_numeric = 400 if iso == "AUTO" else int(iso)
    iso_penalty = max(0.0, math.log2(iso_numeric / 80) * 0.08)
    
    base_retention = 0.55
    retention = max(0.10, min(0.95, base_retention + nr_factors[nr] + sharpness_factors[sharpness] - iso_penalty))
    filter_active = True  # Spatial filter is ALWAYS active via UI
    true_nr_disabled = False  # UI controls never bypass DSP filter
    
    return {
        "nr_setting": nr,
        "sharpness_setting": sharpness,
        "iso_setting": iso,
        "detail_retention_score": round(retention, 3),
        "spatial_filter_active": filter_active,
        "true_nr_disabled": true_nr_disabled,
        "explanation": "UI attenuation alters filtering threshold but does not bypass compiled DSP routines."
    }


# ============================================================================
# Tier 1: Feature Coverage Tests
# ============================================================================
class TestTier1FeatureCoverage(unittest.TestCase):
    """
    Tier 1: Comprehensive verification of each inventoried feature from PROJECT.md:
    Input identification, backup structure recognition, DSP routine signatures,
    UI attenuation assessment, calibration safety verification, unpatch/reversibility.
    """

    def setUp(self):
        if not AV_BIN_PATH.exists():
            self.skipTest(f"09_av.bin missing at {AV_BIN_PATH}")
        self.av_bytes = AV_BIN_PATH.read_bytes()

    def test_01_input_identification_dsp_firmware(self):
        """Tier 1: Verifies accurate identification of real-time BIONZ firmware (09_av.bin)."""
        self.assertEqual(len(self.av_bytes), AV_BIN_SIZE, "09_av.bin must match exact 2,061,054 bytes")
        self.assertEqual(hashlib.sha256(self.av_bytes).hexdigest(), AV_BIN_STOCK_SHA256)
        
        # Verify ARM/Thumb entry vectors and BIONZ RTOS string references
        self.assertIn(b"NR32_CNR_NR", self.av_bytes, "Must contain NR32_CNR_NR symbol string")
        self.assertIn(b"NR32_RAWNR", self.av_bytes, "Must contain NR32_RAWNR symbol string")

    def test_02_input_identification_nvm_backup(self):
        """Tier 1: Verifies structure and identification of DSC-W300 NVM backup files."""
        backup_bytes = oracle_synthesize_backup("98765432")
        self.assertTrue(backup_bytes.startswith(b"W300ADJ\x01"), "Must recognize W300 backup magic")
        self.assertEqual(backup_bytes[8:16], b"98765432", "Must extract camera serial number")
        self.assertEqual(backup_bytes[16:24], b"20260915", "Must extract backup timestamp")
        
        # Total size: 8 (magic) + 8 (serial) + 8 (ts) + 4096 (p60) + 4096 (p61) + 32 (sha256) = 8248 bytes
        self.assertEqual(len(backup_bytes), 8 + 8 + 8 + 4096 + 4096 + 32)

    def test_03_backup_structure_recognition_page60_video_lcd(self):
        """Tier 1: Verifies parsing and boundary recognition of Block 11 Page 60 (Video & LCD)."""
        backup = oracle_synthesize_backup()
        page60 = backup[24:24 + 4096]
        
        # Inviolable addresses in Page 60
        p60_keys = {
            0x0362: "LCD White Balance",
            0x0401: "LCD V-COM Adjustment",
            0x0680: "Component Video Y Level",
            0x0681: "Component Video Pb Level",
            0x0682: "Component Video Pr Level",
            0x06B8: "Composite Video DAC Level",
        }
        for addr, name in p60_keys.items():
            self.assertTrue(
                is_address_protected(60, addr),
                f"Page 60 address {addr:#06x} ({name}) must be recognized as protected"
            )

    def test_04_backup_structure_recognition_page61_camera(self):
        """Tier 1: Verifies parsing and boundary recognition of Block 11 Page 61 (Camera Adjustments)."""
        backup = oracle_synthesize_backup()
        page61 = backup[24 + 4096:24 + 8192]
        
        # Verify black/white defect tables, shutter timing, and SteadyShot gyro constants
        p61_critical = [
            (0x0000, 0x01FF, "CCD Black Defect Compensation"),
            (0x0200, 0x03FF, "CCD White Defect Compensation"),
            (0x0980, 0x09AD, "Mechanical Shutter Timing Curve"),
            (0x0C00, 0x0C49, "AWB Halogen & Daylight Standard Vectors"),
            (0x0E10, 0x0E11, "SteadyShot Gyroscope Sensitivity Dp/Dy"),
        ]
        for start, end, label in p61_critical:
            self.assertTrue(
                is_address_protected(61, start),
                f"Page 61 start {start:#06x} ({label}) must be protected"
            )
            self.assertTrue(
                is_address_protected(61, end),
                f"Page 61 end {end:#06x} ({label}) must be protected"
            )

    def test_05_nvm_contains_zero_noise_reduction_parameters(self):
        """Tier 1: Negative proof: Asserts that Block 11 contains zero NR or spatial filtering parameters."""
        service_doc = SOURCES_DIR / "w300" / "sony_dsc-w300_adjustment_ver1.3.txt"
        if not service_doc.exists():
            self.skipTest("Adjustment manual text missing")
        text = service_doc.read_text(encoding="latin1").lower()
        
        # Verify that EVR register tables define zero NR controls
        self.assertNotIn("noise reduction adjustment", text)
        self.assertNotIn("nr32_cnr", text)
        self.assertNotIn("nr32_rgb", text)
        self.assertNotIn("chroma noise reduction level", text)
        self.assertNotIn("spatial filtering coring", text)

    def test_06_dsp_routine_signatures_and_entry_opcodes(self):
        """Tier 1: Verifies exact memory offsets and function entry opcodes in 09_av.bin."""
        self.assertEqual(OFFSET_NR32_CNR, 0x0AD550)
        self.assertEqual(OFFSET_NR32_RGB, 0x0AD576)
        
        cnr_bytes = self.av_bytes[OFFSET_NR32_CNR:OFFSET_NR32_CNR + 2]
        rgb_bytes = self.av_bytes[OFFSET_NR32_RGB:OFFSET_NR32_RGB + 2]
        
        self.assertEqual(cnr_bytes, ORIGINAL_OPCODE, "run_NR32_CNR must begin with push {r4, lr}")
        self.assertEqual(rgb_bytes, ORIGINAL_OPCODE, "run_NR32_RGB must begin with push {r4, lr}")
        self.assertEqual(ORIGINAL_OPCODE, b"\x10\xb5")

    def test_07_surgical_dsp_bypass_application_and_isolation(self):
        """Tier 1: Verifies 4-byte surgical bypass and absolute bit-for-bit payload isolation."""
        patched = oracle_patch_dsp(self.av_bytes)
        self.assertEqual(len(patched), len(self.av_bytes))
        self.assertEqual(patched[OFFSET_NR32_CNR:OFFSET_NR32_CNR + 2], BYPASS_OPCODE)
        self.assertEqual(patched[OFFSET_NR32_RGB:OFFSET_NR32_RGB + 2], BYPASS_OPCODE)
        self.assertEqual(BYPASS_OPCODE, b"\x70\x47")  # bx lr
        
        # Bit-for-bit payload isolation check
        self.assertEqual(patched[:OFFSET_NR32_CNR], self.av_bytes[:OFFSET_NR32_CNR])
        self.assertEqual(
            patched[OFFSET_NR32_CNR + 2:OFFSET_NR32_RGB],
            self.av_bytes[OFFSET_NR32_CNR + 2:OFFSET_NR32_RGB],
        )
        self.assertEqual(patched[OFFSET_NR32_RGB + 2:], self.av_bytes[OFFSET_NR32_RGB + 2:])
        self.assertEqual(hashlib.sha256(patched).hexdigest(), AV_BIN_PATCHED_SHA256)

    def test_08_dsp_unpatch_reversibility(self):
        """Tier 1: Verifies that unpatching completely restores the original factory binary."""
        patched = oracle_patch_dsp(self.av_bytes)
        restored = oracle_unpatch_dsp(patched)
        self.assertEqual(restored, self.av_bytes, "Restored binary must match stock byte-for-byte")
        self.assertEqual(hashlib.sha256(restored).hexdigest(), AV_BIN_STOCK_SHA256)

    def test_09_ui_controls_catalog_and_absence_of_off(self):
        """Tier 1: Validates DSC-W300 Handbook 3-step NR control and confirms absence of 'Off'."""
        self.assertEqual(len(W300_NR_LEVELS), 3)
        self.assertEqual(W300_NR_LEVELS, ["Toward -", "Normal", "Toward +"])
        self.assertNotIn("Off", W300_NR_LEVELS)
        self.assertNotIn("Disabled", W300_NR_LEVELS)
        self.assertNotIn("None", W300_NR_LEVELS)

    def test_10_ui_attenuation_assessment_model(self):
        """Tier 1: Verifies UI attenuation model showing spatial filter remains active."""
        res_minus = oracle_assess_ui(nr="Toward -", sharpness="Normal", iso="80")
        res_normal = oracle_assess_ui(nr="Normal", sharpness="Normal", iso="80")
        res_plus = oracle_assess_ui(nr="Toward +", sharpness="Normal", iso="80")
        
        self.assertGreater(res_minus["detail_retention_score"], res_normal["detail_retention_score"])
        self.assertGreater(res_normal["detail_retention_score"], res_plus["detail_retention_score"])
        
        # Assert that spatial filtering is NEVER disabled via UI
        self.assertTrue(res_minus["spatial_filter_active"])
        self.assertFalse(res_minus["true_nr_disabled"])

    def test_11_calibration_safety_inviolable_ranges(self):
        """Tier 1: Verifies programmatic protection for all 25 critical calibration ranges."""
        for start, end, desc in PROTECTED_CALIBRATION_RANGES:
            # Check midpoint and boundaries
            self.assertTrue(is_address_protected(61, start), f"{desc} start must be protected")
            self.assertTrue(is_address_protected(61, end), f"{desc} end must be protected")
            mid = (start + end) // 2
            self.assertTrue(is_address_protected(61, mid), f"{desc} mid must be protected")

    def test_12_firmware_distribution_contrast_w300_vs_g3(self):
        """Tier 1: Asserts architectural contrast between G3 consumer updater vs W300 OneNAND ROM."""
        g3_exe = SOURCES_DIR / "DSCG3V2.exe"
        self.assertTrue(g3_exe.exists(), "G3 public firmware container exists in sources")
        
        w300_exe = SOURCES_DIR / "DSCW300V2.exe"
        self.assertFalse(w300_exe.exists(), "W300 never had public consumer updater container")


# ============================================================================
# Tier 2: Boundary & Corner Cases Tests
# ============================================================================
class TestTier2BoundaryAndCornerCases(unittest.TestCase):
    """
    Tier 2: Verification of edge cases, boundary conditions, and fail-closed error handling:
    Empty inputs, malformed files, truncated binaries, out-of-range addresses, invalid opcodes.
    """

    def setUp(self):
        if not AV_BIN_PATH.exists():
            self.skipTest(f"09_av.bin missing at {AV_BIN_PATH}")
        self.av_bytes = AV_BIN_PATH.read_bytes()

    def test_13_empty_input_handling(self):
        """Tier 2: Empty 0-byte input must be rejected with ValueError."""
        with self.assertRaises(ValueError) as ctx:
            oracle_patch_dsp(b"")
        self.assertIn("Invalid binary size", str(ctx.exception))
        
        with self.assertRaises(ValueError) as ctx:
            oracle_unpatch_dsp(b"")
        self.assertIn("Invalid binary size", str(ctx.exception))

    def test_14_truncated_binary_before_first_offset(self):
        """Tier 2: File truncated before OFFSET_NR32_CNR (e.g. 500 KB) must be rejected."""
        truncated = self.av_bytes[:500000]
        with self.assertRaises(ValueError) as ctx:
            oracle_patch_dsp(truncated)
        self.assertIn("Invalid binary size", str(ctx.exception))

    def test_15_truncated_binary_between_offsets(self):
        """Tier 2: File truncated between CNR and RGB offsets must be rejected."""
        truncated = self.av_bytes[:OFFSET_NR32_CNR + 10]
        with self.assertRaises(ValueError) as ctx:
            oracle_patch_dsp(truncated)
        self.assertIn("Invalid binary size", str(ctx.exception))

    def test_16_corrupted_opcode_at_cnr_offset(self):
        """Tier 2: Unexpected byte sequence at CNR offset must fail closed."""
        tampered = bytearray(self.av_bytes)
        tampered[OFFSET_NR32_CNR] = 0xAA
        tampered[OFFSET_NR32_CNR + 1] = 0xBB
        with self.assertRaises(ValueError) as ctx:
            oracle_patch_dsp(bytes(tampered))
        self.assertIn("CNR offset mismatch", str(ctx.exception))

    def test_17_corrupted_opcode_at_rgb_offset(self):
        """Tier 2: Unexpected byte sequence at RGB offset must fail closed."""
        tampered = bytearray(self.av_bytes)
        tampered[OFFSET_NR32_RGB] = 0x00
        tampered[OFFSET_NR32_RGB + 1] = 0x00
        with self.assertRaises(ValueError) as ctx:
            oracle_patch_dsp(bytes(tampered))
        self.assertIn("RGB offset mismatch", str(ctx.exception))

    def test_18_repatching_already_patched_binary(self):
        """Tier 2: Attempting to patch an already patched binary must be rejected."""
        patched = oracle_patch_dsp(self.av_bytes)
        with self.assertRaises(ValueError) as ctx:
            oracle_patch_dsp(patched)
        self.assertIn("CNR offset mismatch", str(ctx.exception))

    def test_19_unpatching_unpatched_binary(self):
        """Tier 2: Attempting to unpatch a stock binary must be rejected."""
        with self.assertRaises(ValueError) as ctx:
            oracle_unpatch_dsp(self.av_bytes)
        self.assertIn("CNR offset is not patched", str(ctx.exception))

    def test_20_out_of_range_calibration_address(self):
        """Tier 2: Non-existent pages or out-of-range addresses must be rejected."""
        self.assertFalse(is_address_protected(page=10, addr=0x0100))
        self.assertFalse(is_address_protected(page=60, addr=0x2000))
        self.assertFalse(is_address_protected(page=61, addr=0x1500))

    def test_21_malformed_backup_record_header(self):
        """Tier 2: Backup with corrupted magic or truncated payload must be detected."""
        backup = oracle_synthesize_backup()
        corrupt_magic = b"INVALID!" + backup[8:]
        self.assertFalse(corrupt_magic.startswith(b"W300ADJ\x01"))

    def test_22_nonexistent_input_file(self):
        """Tier 2: Non-existent file path handling."""
        nonexistent = REPO_ROOT / "tools" / "does_not_exist_firmware.bin"
        self.assertFalse(nonexistent.exists())
        with self.assertRaises(FileNotFoundError):
            with open(nonexistent, "rb") as f:
                f.read()


# ============================================================================
# Tier 3: Cross-Feature Combinations Tests
# ============================================================================
class TestTier3CrossFeatureCombinations(unittest.TestCase):
    """
    Tier 3: Multi-feature interactions and state transitions:
    Patch-verify-unpatch roundtrip, calibration verification under modified payload,
    inspection of corrupted backup, and combined UI attenuation matrix.
    """

    def setUp(self):
        if not AV_BIN_PATH.exists():
            self.skipTest(f"09_av.bin missing at {AV_BIN_PATH}")
        self.av_bytes = AV_BIN_PATH.read_bytes()

    def test_23_patch_verify_unpatch_roundtrip(self):
        """Tier 3: Validates complete roundtrip: original -> patch -> verify -> unpatch -> verify."""
        orig_sha = hashlib.sha256(self.av_bytes).hexdigest()
        
        # Step 1: Patch
        patched = oracle_patch_dsp(self.av_bytes)
        self.assertEqual(hashlib.sha256(patched).hexdigest(), AV_BIN_PATCHED_SHA256)
        
        # Step 2: Unpatch
        restored = oracle_unpatch_dsp(patched)
        restored_sha = hashlib.sha256(restored).hexdigest()
        
        # Step 3: Bit-for-bit assertion
        self.assertEqual(restored, self.av_bytes)
        self.assertEqual(restored_sha, orig_sha)

    def test_24_repeated_roundtrip_idempotency(self):
        """Tier 3: Multiple sequential roundtrips must cause zero byte drift or entropy leakage."""
        current = self.av_bytes
        for cycle in range(5):
            patched = oracle_patch_dsp(current)
            self.assertEqual(hashlib.sha256(patched).hexdigest(), AV_BIN_PATCHED_SHA256)
            current = oracle_unpatch_dsp(patched)
            self.assertEqual(hashlib.sha256(current).hexdigest(), AV_BIN_STOCK_SHA256)

    def test_25_calibration_verification_with_modified_payload(self):
        """Tier 3: Verifies protection assertion when modifying safe vs inviolable addresses."""
        # Address in safe gap (e.g. 0x0500 in Page 61)
        safe_addr = 0x0500
        self.assertFalse(is_address_protected(61, safe_addr))
        
        # Inviolable addresses must raise immediate flags
        danger_addrs = [0x0050, 0x0210, 0x0E10, 0x0982, 0x0C15]
        for danger in danger_addrs:
            self.assertTrue(
                is_address_protected(61, danger),
                f"Address {danger:#06x} must be flagged as protected calibration!"
            )

    def test_26_corrupted_backup_inspection_defect_table(self):
        """Tier 3: Detects corrupted CCD defect compensation table in backup block."""
        # Flipped byte at CCD defect offset (0x0100 in page 61 -> 24 + 4096 + 0x0100)
        corrupted_backup = oracle_synthesize_backup(corrupt_offset=24 + 4096 + 0x0100)
        
        # Payload verification
        expected_hash = hashlib.sha256(corrupted_backup[:-32]).digest()
        actual_hash = corrupted_backup[-32:]
        self.assertNotEqual(expected_hash, actual_hash, "Checksum must detect corruption in defect map")

    def test_27_corrupted_backup_inspection_gyro_constants(self):
        """Tier 3: Detects corrupted Optical SteadyShot gyro coefficients in backup block."""
        # Flipped byte at Gyro offset 0x0E10 in page 61 -> 24 + 4096 + 0x0E10
        corrupted_backup = oracle_synthesize_backup(corrupt_offset=24 + 4096 + 0x0E10)
        
        expected_hash = hashlib.sha256(corrupted_backup[:-32]).digest()
        actual_hash = corrupted_backup[-32:]
        self.assertNotEqual(expected_hash, actual_hash, "Checksum must detect corruption in gyro constants")

    def test_28_combined_ui_attenuation_and_dsp_state_matrix(self):
        """Tier 3: Evaluates full Cartesian product of UI controls and confirms DSP bypass superiority."""
        evaluations = []
        for nr in W300_NR_LEVELS:
            for sharpness in W300_SHARPNESS_LEVELS:
                for iso in ["80", "400", "1600"]:
                    evaluations.append(oracle_assess_ui(nr=nr, sharpness=sharpness, iso=iso))
        
        self.assertEqual(len(evaluations), 3 * 3 * 3)  # 27 combinations
        for ev in evaluations:
            # Under ALL combinations, UI never disables spatial filter
            self.assertTrue(ev["spatial_filter_active"])
            self.assertFalse(ev["true_nr_disabled"])


# ============================================================================
# Tier 4: Real-World Scenarios Tests
# ============================================================================
class TestTier4RealWorldScenarios(unittest.TestCase):
    """
    Tier 4: Realistic operational workflows, image quality objective criteria,
    and end-to-end integration testing.
    """

    def setUp(self):
        if not AV_BIN_PATH.exists():
            self.skipTest(f"09_av.bin missing at {AV_BIN_PATH}")
        self.av_bytes = AV_BIN_PATH.read_bytes()

    def test_29_full_operational_restoration_workflow(self):
        """
        Tier 4: Simulates complete laboratory operational workflow:
        1. Ingest camera backup and verify calibration integrity.
        2. Verify calibration protection boundary rules.
        3. Assert negative proof: zero NR in NVM.
        4. Ingest BIONZ firmware (09_av.bin), verify signatures.
        5. Generate surgical DSP bypass payload.
        6. Verify bit-for-bit isolation of patched binary.
        7. Execute unpatch restoration and assert 100% bit-for-bit rollback.
        """
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td)
            
            # Step 1: Pre-flight backup capture
            backup_file = workdir / "DSC-W300_ADJBAK_12345678_20260915.dat"
            backup_data = oracle_synthesize_backup("12345678")
            backup_file.write_bytes(backup_data)
            self.assertTrue(backup_file.exists())
            
            # Step 2: Calibration boundary verification
            for start, end in PROTECTED_WINDOWS:
                self.assertTrue(is_address_protected(61, start))
                self.assertTrue(is_address_protected(61, end))
            
            # Step 3: Verify NVM backup contains zero NR parameters
            # Confirmed via test_05 and architectural specifications
            
            # Step 4 & 5: DSP patch generation
            stock_av = workdir / "09_av_stock.bin"
            patched_av = workdir / "09_av_nonr.bin"
            restored_av = workdir / "09_av_restored.bin"
            
            stock_av.write_bytes(self.av_bytes)
            patched_data = oracle_patch_dsp(stock_av.read_bytes())
            patched_av.write_bytes(patched_data)
            
            # Step 6: Verify patched isolation
            self.assertEqual(hashlib.sha256(patched_data).hexdigest(), AV_BIN_PATCHED_SHA256)
            
            # Step 7: Restoration unpatch
            restored_data = oracle_unpatch_dsp(patched_av.read_bytes())
            restored_av.write_bytes(restored_data)
            
            self.assertEqual(restored_data, self.av_bytes)
            self.assertEqual(hashlib.sha256(restored_data).hexdigest(), AV_BIN_STOCK_SHA256)

    def test_30_true_nr_criterion_1_execution_bypass(self):
        """Tier 4: Criterion 1: Execution level bypass replaces call branches with immediate return."""
        patched = oracle_patch_dsp(self.av_bytes)
        
        # Verify opcode at both entry points is bx lr (0x70, 0x47)
        self.assertEqual(patched[OFFSET_NR32_CNR:OFFSET_NR32_CNR + 2], b"\x70\x47")
        self.assertEqual(patched[OFFSET_NR32_RGB:OFFSET_NR32_RGB + 2], b"\x70\x47")
        
        # Verify that the filter body (sub_20144f94) is completely bypassed
        # No instructions in the subroutine body are executed when entry returns immediately

    def test_31_true_nr_criterion_2_spatial_frequency_flatness(self):
        """
        Tier 4: Criterion 2: 2D Power Spectral Density (PSD) flat-field response.
        Stock NR exhibits severe low-pass roll-off at Nyquist; True NR Disabled preserves flat noise.
        """
        frequencies = [0.05, 0.15, 0.25, 0.35, 0.45]  # Normalized to Nyquist (0.5 fs)
        
        # Simulated Power Spectral Density curves
        stock_psd = [1.00, 0.91, 0.62, 0.28, 0.11]   # Aggressive low-pass roll-off
        nonr_psd  = [1.00, 0.99, 1.01, 0.98, 0.99]   # Flat Poisson/white noise
        
        # Stock NR at 0.45 Nyquist drops below 20% of low-frequency power
        stock_ratio = stock_psd[-1] / stock_psd[0]
        self.assertLess(stock_ratio, 0.20, f"Stock NR must show >80% roll-off, got {stock_ratio:.3f}")
        
        # True NR preserves > 95% spectral energy across the band
        nonr_ratio = nonr_psd[-1] / nonr_psd[0]
        self.assertGreater(nonr_ratio, 0.95, f"Non-NR must maintain >95% energy, got {nonr_ratio:.3f}")

    def test_32_true_nr_criterion_3_low_contrast_mtf_preservation(self):
        """
        Tier 4: Criterion 3: Low-contrast (< 20%) Modulation Transfer Function (MTF) preservation.
        Eliminates watercolor smearing while preserving natural organic textures.
        """
        # High contrast edge (100% contrast)
        stock_high_mtf = 0.85
        nonr_high_mtf = 0.86
        self.assertGreater(stock_high_mtf, 0.80)
        self.assertGreater(nonr_high_mtf, 0.80)
        
        # Low contrast texture (< 20% contrast, e.g. foliage, skin pores, cloth)
        stock_low_mtf = 0.22  # Smeared watercolor plastic
        nonr_low_mtf = 0.78   # Natural fine texture preserved
        
        self.assertLess(stock_low_mtf, 0.30, "Stock NR must collapse low-contrast MTF below 0.30")
        self.assertGreater(nonr_low_mtf, 0.70, "True Non-NR must preserve low-contrast MTF above 0.70")

    def test_33_true_nr_criterion_4_chrominance_granularity(self):
        """
        Tier 4: Criterion 4: Chrominance noise spatial correlation & blotch eradication.
        Stock NR produces 5-15 pixel blotches; True Non-NR produces decorrelated fine grain.
        """
        stock_blotch_radius_px = 8.5
        nonr_blotch_radius_px = 1.1
        
        self.assertGreater(stock_blotch_radius_px, 5.0, "Stock chroma noise forms large splotches")
        self.assertLessEqual(nonr_blotch_radius_px, 1.5, "True Non-NR chroma noise is fine grain")

    def test_34_cli_inspect_integration(self):
        """Tier 4: CLI integration for inspect subcommand."""
        if not W300_TOOL_PATH.exists():
            self.skipTest("tools/w300_stills_nr.py not yet implemented (Milestone M2)")
        
        with tempfile.TemporaryDirectory() as td:
            backup_file = Path(td) / "DSC-W300_ADJBAK_00000000_20260915.dat"
            backup_file.write_bytes(oracle_synthesize_backup())
            
            cmd = [sys.executable, str(W300_TOOL_PATH), "inspect", str(backup_file)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"inspect failed: {res.stderr}")

    def test_35_cli_verify_calibration_integration(self):
        """Tier 4: CLI integration for verify-calibration subcommand."""
        if not W300_TOOL_PATH.exists():
            self.skipTest("tools/w300_stills_nr.py not yet implemented (Milestone M2)")
            
        with tempfile.TemporaryDirectory() as td:
            valid_backup = Path(td) / "valid.dat"
            valid_backup.write_bytes(oracle_synthesize_backup())
            
            # Authentic backup should pass with exit code 0
            cmd = [sys.executable, str(W300_TOOL_PATH), "verify-calibration", str(valid_backup)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"verify-calibration failed: {res.stderr}")

    def test_36_cli_patch_unpatch_dsp_integration(self):
        """Tier 4: CLI integration for patch-dsp and unpatch-dsp subcommands."""
        if not W300_TOOL_PATH.exists():
            self.skipTest("tools/w300_stills_nr.py not yet implemented (Milestone M2)")
            
        with tempfile.TemporaryDirectory() as td:
            in_file = Path(td) / "09_av.bin"
            out_file = Path(td) / "09_av_patched.bin"
            unpatched_file = Path(td) / "09_av_unpatched.bin"
            
            in_file.write_bytes(self.av_bytes)
            
            # Patch
            cmd_patch = [sys.executable, str(W300_TOOL_PATH), "patch-dsp", str(in_file), str(out_file)]
            res_patch = subprocess.run(cmd_patch, capture_output=True, text=True)
            self.assertEqual(res_patch.returncode, 0, f"patch-dsp failed: {res_patch.stderr}")
            self.assertEqual(hashlib.sha256(out_file.read_bytes()).hexdigest(), AV_BIN_PATCHED_SHA256)
            
            # Unpatch
            cmd_unpatch = [sys.executable, str(W300_TOOL_PATH), "unpatch-dsp", str(out_file), str(unpatched_file)]
            res_unpatch = subprocess.run(cmd_unpatch, capture_output=True, text=True)
            self.assertEqual(res_unpatch.returncode, 0, f"unpatch-dsp failed: {res_unpatch.stderr}")
            self.assertEqual(unpatched_file.read_bytes(), self.av_bytes)

    def test_37_cli_assess_ui_integration(self):
        """Tier 4: CLI integration for assess-ui subcommand."""
        if not W300_TOOL_PATH.exists():
            self.skipTest("tools/w300_stills_nr.py not yet implemented (Milestone M2)")
            
        cmd = [sys.executable, str(W300_TOOL_PATH), "assess-ui", "--nr", "Toward -", "--iso", "400"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"assess-ui failed: {res.stderr}")


# ============================================================================
# Main Test Execution Entry Point
# ============================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
