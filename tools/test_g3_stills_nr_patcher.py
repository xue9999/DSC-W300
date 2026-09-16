#!/usr/bin/env python3
"""
Unit and regression test suite for g3_stills_nr_patcher.py.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from g3_stills_nr_patcher import (
    patch_av_bin,
    build_nonr_firmware,
    verify_nonr_dat,
    OFFSET_NR32_CNR,
    OFFSET_NR32_RGB,
    ORIGINAL_OPCODE,
    BYPASS_OPCODE,
)


class TestG3StillsNrPatcher(unittest.TestCase):
    def setUp(self):
        self.sections_dir = Path("evidence/extracted_g3/sections")
        self.av_path = self.sections_dir / "09_av.bin"
        if not self.av_path.exists():
            self.skipTest("09_av.bin missing")
        self.av_bytes = self.av_path.read_bytes()

    def test_patch_offsets_validity(self):
        self.assertEqual(self.av_bytes[OFFSET_NR32_CNR:OFFSET_NR32_CNR + 2], ORIGINAL_OPCODE)
        self.assertEqual(self.av_bytes[OFFSET_NR32_RGB:OFFSET_NR32_RGB + 2], ORIGINAL_OPCODE)

    def test_patch_application(self):
        patched = patch_av_bin(self.av_bytes)
        self.assertEqual(len(patched), len(self.av_bytes))
        self.assertEqual(patched[OFFSET_NR32_CNR:OFFSET_NR32_CNR + 2], BYPASS_OPCODE)
        self.assertEqual(patched[OFFSET_NR32_RGB:OFFSET_NR32_RGB + 2], BYPASS_OPCODE)
        # Verify isolation: other bytes unchanged
        self.assertEqual(patched[:OFFSET_NR32_CNR], self.av_bytes[:OFFSET_NR32_CNR])
        self.assertEqual(patched[OFFSET_NR32_CNR + 2:OFFSET_NR32_RGB], self.av_bytes[OFFSET_NR32_CNR + 2:OFFSET_NR32_RGB])
        self.assertEqual(patched[OFFSET_NR32_RGB + 2:], self.av_bytes[OFFSET_NR32_RGB + 2:])

    def test_mismatched_byte_rejection(self):
        corrupted = bytearray(self.av_bytes)
        corrupted[OFFSET_NR32_CNR] = 0x00
        with self.assertRaises(ValueError) as ctx:
            patch_av_bin(bytes(corrupted))
        self.assertIn("CNR offset mismatch", str(ctx.exception))

    def test_verified_dat_roundtrip(self):
        dat_path = Path("evidence/extracted_g3/D-G3V2_nonr.dat")
        if not dat_path.exists():
            self.skipTest("D-G3V2_nonr.dat missing")
        res = verify_nonr_dat(dat_path)
        self.assertEqual(res["status"], "PASS")
        self.assertTrue(res["cnr_bypassed"])
        self.assertTrue(res["rgb_bypassed"])
        self.assertEqual(res["sections_verified"], 24)


if __name__ == "__main__":
    unittest.main()
