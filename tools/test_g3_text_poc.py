#!/usr/bin/env python3
"""
Unit and regression test suite for g3_text_poc.py.
Benchmarked against SONY_NX3_Reversal (test_nx3_text_poc.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from g3_text_poc import (
    patch_csv_text,
    update_manifest,
    build_block_header,
    generate_poc_firmware,
    verify_poc_image,
    require,
)
from g3_firmware_parser import CXD4108MsCrypter, KEY_CXD4108_MS, MANIFEST_SIZE


class TestG3TextPoc(unittest.TestCase):
    def setUp(self):
        self.crypter = CXD4108MsCrypter(KEY_CXD4108_MS)
        self.sample_csv = (
            "SETUP_TVTYPE,TV Type\n"
            "SETUP_UPDATE,Update\n"
            "SETUP_VERSION,Version\n"
            "SETUP_VIDEOOUT,Video Out\n"
        )

    def test_patch_csv_success(self):
        patched = patch_csv_text(self.sample_csv, "SETUP_VERSION", "Version", "G3 POC")
        self.assertIn("SETUP_VERSION,G3 POC\n", patched)
        self.assertNotIn("SETUP_VERSION,Version\n", patched)
        self.assertIn("SETUP_TVTYPE,TV Type\n", patched)

    def test_patch_csv_missing_key(self):
        with self.assertRaises(ValueError) as ctx:
            patch_csv_text(self.sample_csv, "NONEXISTENT_KEY", "Version", "G3 POC")
        self.assertIn("Expected exactly 1 occurrence", str(ctx.exception))

    def test_patch_csv_mismatched_old_val(self):
        with self.assertRaises(ValueError) as ctx:
            patch_csv_text(self.sample_csv, "SETUP_VERSION", "WrongOldVal", "G3 POC")
        self.assertIn("does not match expected", str(ctx.exception))

    def test_patch_csv_duplicate_key(self):
        duplicate_csv = self.sample_csv + "SETUP_VERSION,Duplicate\n"
        with self.assertRaises(ValueError) as ctx:
            patch_csv_text(duplicate_csv, "SETUP_VERSION", "Version", "G3 POC")
        self.assertIn("Expected exactly 1 occurrence", str(ctx.exception))

    def test_block_header_crypto_validity(self):
        test_payload = b"Sample payload for CXD4108 MsFirm header test"
        enc = self.crypter.cipher(test_payload)
        hdr = build_block_header(self.crypter, enc)
        self.assertEqual(len(hdr), 128)
        self.assertTrue(self.crypter.check_header_hash(hdr))
        self.assertTrue(self.crypter.check_data_hash(hdr, enc))

    def test_manifest_checksum_recalculation(self):
        # Read original cntent.dat
        cntent_path = Path("evidence/extracted_g3/cntent.dat")
        if not cntent_path.exists():
            self.skipTest("cntent.dat not available")
            
        orig_cntent = cntent_path.read_bytes()
        new_cntent, meta = update_manifest(orig_cntent, 10, "fskapp1.tar", 0x2A8000)
        self.assertEqual(len(new_cntent), MANIFEST_SIZE)
        
        # Verify checksum
        hdr_chksum = int(new_cntent[:0x40].decode('ascii').split('chksum=')[1].split('\n')[0], 16)
        computed_chksum = sum(new_cntent[0x40:]) & 0xffffffff
        self.assertEqual(hdr_chksum, computed_chksum)

    def test_full_poc_roundtrip_verification(self):
        poc_path = Path("evidence/extracted_g3/D-G3V2_poc.dat")
        if not poc_path.exists():
            self.skipTest("D-G3V2_poc.dat not generated yet")
            
        res = verify_poc_image(poc_path, "G3 POC")
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["custom_string"], "G3 POC")
        self.assertEqual(res["verified_sections_count"], 24)


if __name__ == "__main__":
    unittest.main()
