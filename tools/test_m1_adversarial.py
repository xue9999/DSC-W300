#!/usr/bin/env python3
"""
tools/test_m1_adversarial.py - Adversarial Stress & Edge Case Test Suite for Milestone 1 Gate.
Empirical verification of container carving, HMAC verification, stream truncation,
section offset parsing, endianness, and fail-closed security properties.
"""
import hashlib
import io
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Add tools directory to path
TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import g3_firmware_parser
from g3_firmware_parser import (
    CXD4108MsCrypter,
    LhaStreamCarver,
    G3FirmwareParser,
    parse_manifest,
    KEY_CXD4108_MS,
    LHA_HEADER_OFFSET,
    LHA_PAYLOAD_OFFSET,
    LHA_PAYLOAD_LENGTH,
    BLOCK_HEADER_SIZE,
    MANIFEST_OFFSET,
    MANIFEST_SIZE,
    EXPECTED_CHKSUM,
    EXPECTED_SECTION_COUNT
)

EXE_PATH = REPO_ROOT / "sources" / "DSCG3V2.exe"
DAT_PATH = REPO_ROOT / "sources" / "D-G3V2.dat"


class TestMilestone1Adversarial(unittest.TestCase):
    """
    Adversarial challenge test suite for Milestone 1 container carving and crypto engine.
    """

    @classmethod
    def setUpClass(cls):
        if not EXE_PATH.exists():
            raise FileNotFoundError(f"DSCG3V2.exe not found at {EXE_PATH}")

    # ========================================================================
    # 1. Corrupted Container Headers & Fail-Closed Verification
    # ========================================================================

    def test_01_container_header_hmac_tamper_fails_closed(self):
        """
        Adversarial: Tampering with header HMAC must fail closed with clear ValueError.
        Tests multiple bit flips across the 20-byte HMAC signature.
        """
        crypter = CXD4108MsCrypter()

        # Read authentic container header from EXE
        with open(EXE_PATH, 'rb') as f:
            f.seek(LHA_PAYLOAD_OFFSET)
            orig_hdr = f.read(BLOCK_HEADER_SIZE)

        self.assertTrue(crypter.check_header_hash(orig_hdr), "Authentic header HMAC must pass")

        # Test altering individual bytes in the HMAC signature (bytes 108..127)
        for offset in [108, 115, 127]:
            tampered = bytearray(orig_hdr)
            tampered[offset] ^= 0x5A
            self.assertFalse(
                crypter.check_header_hash(bytes(tampered)),
                f"Tampered header at offset {offset} must fail HMAC check"
            )

    def test_02_container_data_hmac_tamper_fails_closed(self):
        """
        Adversarial: Tampering with data HMAC (bytes 0:20) must fail data HMAC check.
        """
        crypter = CXD4108MsCrypter()
        with open(EXE_PATH, 'rb') as f:
            f.seek(LHA_PAYLOAD_OFFSET)
            orig_hdr = f.read(BLOCK_HEADER_SIZE)
            enc_cntent = f.read(MANIFEST_SIZE)

        self.assertTrue(crypter.check_data_hash(orig_hdr, enc_cntent))

        # Tamper payload
        tampered_data = bytearray(enc_cntent)
        tampered_data[0] ^= 0x01
        self.assertFalse(crypter.check_data_hash(orig_hdr, bytes(tampered_data)))

        # Tamper data HMAC field in header
        tampered_hdr = bytearray(orig_hdr)
        tampered_hdr[0] ^= 0x01
        self.assertFalse(crypter.check_data_hash(bytes(tampered_hdr), enc_cntent))

    def test_03_container_header_padding_corruption(self):
        """
        Adversarial: Tampering with the 88 null bytes padding (bytes 20:108)
        must invalidate header verification in G3FirmwareParser.
        """
        with tempfile.TemporaryDirectory() as td:
            corrupt_exe = Path(td) / "corrupt_padding.exe"
            with open(EXE_PATH, 'rb') as f_in, open(corrupt_exe, 'wb') as f_out:
                # Copy up to padding
                f_out.write(f_in.read(LHA_PAYLOAD_OFFSET + 20))
                f_in.seek(LHA_PAYLOAD_OFFSET + 20)
                padding = bytearray(f_in.read(88))
                padding[42] = 0xAA  # corrupt padding byte
                f_out.write(padding)
                # Copy remainder of manifest
                f_out.write(f_in.read(20 + MANIFEST_SIZE))

            parser = G3FirmwareParser(corrupt_exe)
            with self.assertRaises(ValueError) as ctx:
                parser.verify_container_header()
            self.assertIn("Container header verification failed", str(ctx.exception))

    def test_04_section_header_hmac_tamper_aborts_extraction(self):
        """
        Adversarial: If a section header's HMAC is altered, extract_sections()
        must fail closed, raise ValueError, and not produce corrupted output silently.
        """
        with tempfile.TemporaryDirectory() as td:
            corrupt_exe = Path(td) / "corrupt_section_hdr.exe"
            # Read authentic manifest offset for section 0 (defhd.dat at 0x744F + 0x5000 + 128)
            sec0_hdr_offset = LHA_PAYLOAD_OFFSET + 0x5000 + 128
            # Assemble the tampered fixture before publishing the EXE once.
            # Windows may deny reopening newly written PE files for mutation.
            data = bytearray(EXE_PATH.read_bytes())
            data[sec0_hdr_offset + 127] ^= 0xFF
            corrupt_exe.write_bytes(data)

            parser = G3FirmwareParser(corrupt_exe)
            out_dir = Path(td) / "output"
            with self.assertRaises(ValueError) as ctx:
                parser.extract_sections(out_dir, dump_container=False)
            self.assertIn("Header HMAC check failed for section 0", str(ctx.exception))

    def test_05_section_payload_tamper_aborts_extraction(self):
        """
        Adversarial: Tampering 1 byte in section payload ciphertext causes data HMAC mismatch
        and raises ValueError.
        """
        with tempfile.TemporaryDirectory() as td:
            corrupt_exe = Path(td) / "corrupt_section_data.exe"
            sec0_data_offset = LHA_PAYLOAD_OFFSET + 0x5000 + 128 + 128
            data = bytearray(EXE_PATH.read_bytes())
            data[sec0_data_offset] ^= 0x01
            corrupt_exe.write_bytes(data)

            parser = G3FirmwareParser(corrupt_exe)
            out_dir = Path(td) / "output"
            with self.assertRaises(ValueError) as ctx:
                parser.extract_sections(out_dir, dump_container=False)
            self.assertIn("Data HMAC check failed for section 0", str(ctx.exception))

    def test_06_cli_fails_closed_with_clean_error(self):
        """
        Adversarial: CLI must exit with code 1 and clean error message when header HMAC is altered.
        """
        with tempfile.TemporaryDirectory() as td:
            corrupt_exe = Path(td) / "corrupt_cli.exe"
            data = bytearray(EXE_PATH.read_bytes())
            data[LHA_PAYLOAD_OFFSET + 127] = 0
            corrupt_exe.write_bytes(data)

            cmd = [
                sys.executable,
                str(TOOLS_DIR / "g3_firmware_parser.py"),
                "--source", str(corrupt_exe),
                "--output", str(Path(td) / "out"),
                "--dump-sections"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(res.returncode, 1, f"Expected returncode 1, got {res.returncode}")
            self.assertIn("Container header verification failed", res.stderr)
            # Ensure no python traceback dump in output
            self.assertNotIn("Traceback (most recent call last)", res.stdout)

    # ========================================================================
    # 2. Truncated Streams & Missing Files
    # ========================================================================

    def test_07_missing_file_handling(self):
        """Validates FileNotFoundError on non-existent input."""
        non_existent = REPO_ROOT / "sources" / "does_not_exist.exe"
        with self.assertRaises(FileNotFoundError):
            G3FirmwareParser(non_existent)

        # CLI behavior
        cmd = [
            sys.executable,
            str(TOOLS_DIR / "g3_firmware_parser.py"),
            "--source", str(non_existent)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn("Firmware source not found", res.stderr)

    def test_08_empty_zero_byte_file(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "empty.exe"
            target.write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "Unrecognized container or executable format"):
                G3FirmwareParser(target)

    def test_09_executable_truncated_before_lha_header(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "truncated.exe"
            target.write_bytes(b"MZ" + bytes(500))
            with self.assertRaisesRegex(ValueError, "File truncated before LHA header"):
                G3FirmwareParser(target)

    def test_10_executable_truncated_inside_lha_header(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "header.exe"
            target.write_bytes(b"MZ" + bytes(0x7400 - 2) + bytes.fromhex("4f002d6c"))
            with self.assertRaises((ValueError, struct.error)):
                G3FirmwareParser(target)

    def test_11_container_truncated_header(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "header.dat"
            target.write_bytes(bytes(64))
            with self.assertRaisesRegex(ValueError, "Unrecognized container or executable format"):
                G3FirmwareParser(target)

    def test_12_container_truncated_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "manifest.dat"
            with EXE_PATH.open("rb") as source:
                source.seek(LHA_PAYLOAD_OFFSET)
                target.write_bytes(source.read(128 + 500))
            parser = G3FirmwareParser(target)
            with self.assertRaises(ValueError):
                parser.verify_container_header()

    def test_13_file_truncated_during_section_extraction(self):
        """Adversarial: File truncated in middle of section payloads."""
        with tempfile.TemporaryDirectory() as td:
            trunc_file = Path(td) / "truncated.dat"
            with open(EXE_PATH, 'rb') as f:
                f.seek(LHA_PAYLOAD_OFFSET)
                # Slice container up to section 1 header only (truncate before payload completes)
                # section 1 starts at 0x5060 + 2*128 = 0x5160
                trunc_data = f.read(0x5160 + 50)  # partial section 1 header
            trunc_file.write_bytes(trunc_data)

            parser = G3FirmwareParser(trunc_file)
            out_dir = Path(td) / "out"
            with self.assertRaises(ValueError) as ctx:
                parser.extract_sections(out_dir, dump_container=False)
            self.assertIn("Truncated", str(ctx.exception))

    # ========================================================================
    # 3. Edge Cases in Section Offset & Manifest Parsing
    # ========================================================================

    def test_14_manifest_checksum_formula_tampering(self):
        """Adversarial: Corrupted manifest checksum must raise ValueError."""
        # Read decrypted manifest
        parser = G3FirmwareParser(EXE_PATH)
        raw_cntent, manifest = parser.read_manifest()

        # Tamper 1 byte in body
        corrupt_cntent = bytearray(raw_cntent)
        corrupt_cntent[0x50] ^= 0x01

        with self.assertRaises(ValueError) as ctx:
            parse_manifest(bytes(corrupt_cntent))
        self.assertIn("Manifest checksum mismatch", str(ctx.exception))

    def test_15_manifest_declared_count_mismatch(self):
        """Adversarial: Declared section count total_num mismatch raises ValueError."""
        parser = G3FirmwareParser(EXE_PATH)
        raw_cntent, _ = parser.read_manifest()
        text = raw_cntent.decode('latin1')

        # Replace total_num=18 (24) with total_num=19 (25)
        # Update arithmetic checksum so only count check triggers
        text_mod = text.replace("total_num=18", "total_num=19")
        raw_mod = bytearray(text_mod.encode('latin1'))

        # Recalculate checksum field
        new_chksum = sum(raw_mod[0x40:])
        raw_mod = bytearray(re.sub(rb'chksum=[0-9a-fA-F]+', f'chksum={new_chksum:08x}'.encode('ascii'), raw_mod))

        with self.assertRaises(ValueError) as ctx:
            parse_manifest(bytes(raw_mod))
        self.assertIn("Declared section count", str(ctx.exception))

    def test_16_section_offset_monotonicity_and_bounds(self):
        """
        Validates mathematical monotonicity of all 24 section physical offsets.
        Every section's data span must fit strictly inside the payload stream length.
        """
        parser = G3FirmwareParser(EXE_PATH)
        _, manifest = parser.read_manifest()
        sections = manifest['sections']

        prev_end = 0
        for i, s in enumerate(sections):
            phys_hdr = parser.stream_offset + s['offset'] + (i + 1) * BLOCK_HEADER_SIZE
            phys_data = phys_hdr + BLOCK_HEADER_SIZE
            phys_end = phys_data + s['size']

            self.assertGreaterEqual(
                phys_hdr,
                prev_end,
                f"Section {i} ({s['name']}) physical header overlaps previous section end"
            )
            self.assertLessEqual(
                phys_end,
                parser.stream_offset + parser.stream_length,
                f"Section {i} ({s['name']}) exceeds carved container boundaries"
            )
            prev_end = phys_end

    def test_17_manifest_too_short(self):
        """Adversarial: Manifest shorter than 64 bytes raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            parse_manifest(b"FV 02\nSV 02\n")
        self.assertIn("Manifest too short", str(ctx.exception))

    # ========================================================================
    # 4. Endianness, Block Alignment & Stream Offsets
    # ========================================================================

    def test_18_carved_dat_and_pe_exe_dual_mode_equivalence(self):
        """
        Verifies parser produces 100% bit-for-bit identical section extractions
        whether invoked with sources/DSCG3V2.exe or sources/D-G3V2.dat.
        """
        self.assertTrue(DAT_PATH.exists(), f"sources/D-G3V2.dat missing: {DAT_PATH}")

        parser_exe = G3FirmwareParser(EXE_PATH)
        parser_dat = G3FirmwareParser(DAT_PATH)

        self.assertEqual(parser_exe.stream_length, parser_dat.stream_length)

        # Check manifest equality
        raw_exe, man_exe = parser_exe.read_manifest()
        raw_dat, man_dat = parser_dat.read_manifest()

        self.assertEqual(raw_exe, raw_dat, "cntent.dat differs between EXE and DAT")
        self.assertEqual(len(man_exe['sections']), len(man_dat['sections']))

        # Check section payloads match
        with tempfile.TemporaryDirectory() as td:
            out_exe = Path(td) / "out_exe"
            out_dat = Path(td) / "out_dat"

            secs_exe = parser_exe.extract_sections(out_exe, dump_container=False)
            secs_dat = parser_dat.extract_sections(out_dat, dump_container=False)

            for s_e, s_d in zip(secs_exe, secs_dat):
                self.assertEqual(s_e['name'], s_d['name'])
                self.assertEqual(s_e['decrypted_sha256'], s_d['decrypted_sha256'])
                f_e = (out_exe / "sections" / s_e['file_name']).read_bytes()
                f_d = (out_dat / "sections" / s_d['file_name']).read_bytes()
                self.assertEqual(f_e, f_d, f"Payload mismatch for {s_e['name']}")

    def test_19_one_byte_shift_regression(self):
        """
        Adversarial: Slicing container at offset 0x7450 (1-byte shift error)
        must fail container header verification, while 0x744F succeeds.
        """
        with open(EXE_PATH, 'rb') as f:
            f.seek(0x7450)
            hdr_shifted = f.read(128)

        crypter = CXD4108MsCrypter()
        self.assertFalse(
            crypter.check_header_hash(hdr_shifted),
            "1-byte shifted header at 0x7450 must fail HMAC check"
        )
        self.assertNotEqual(
            hdr_shifted[20:-20],
            b'\0' * 88,
            "1-byte shifted header must violate null padding"
        )

    def test_20_cipher_keystream_alignment_and_involution(self):
        """
        Adversarial: Keystream XOR cipher must satisfy exact byte involution:
        cipher(cipher(P)) == P across varied sizes (1, 2, 19, 20, 21, 1024, 65536 bytes)
        and preserve leading nulls.
        """
        crypter = CXD4108MsCrypter()

        test_sizes = [1, 2, 19, 20, 21, 32, 127, 128, 1024, 65536]
        for sz in test_sizes:
            # Test with leading nulls
            test_vector = b'\x00\x00\x01\x02' + os.urandom(max(0, sz - 4))
            test_vector = test_vector[:sz]

            enc = crypter.cipher(test_vector)
            self.assertEqual(len(enc), sz, f"Ciphertext length mismatch for size {sz}")

            dec = crypter.cipher(enc)
            self.assertEqual(dec, test_vector, f"Involution failed for size {sz}")

    def test_21_stream_cipher_large_payload_benchmark(self):
        """
        Stress test: Evaluates execution time of Python int-based cipher
        on a 10.5 MB payload (size of section 19 omgPrg00.bin).
        Must complete within 3.0 seconds.
        """
        crypter = CXD4108MsCrypter()
        payload_10mb = b'X' * (10 * 1024 * 1024)

        t0 = time.perf_counter()
        enc = crypter.cipher(payload_10mb)
        t_enc = time.perf_counter() - t0

        t1 = time.perf_counter()
        dec = crypter.cipher(enc)
        t_dec = time.perf_counter() - t1

        self.assertEqual(dec, payload_10mb)
        self.assertLess(t_enc, 3.0, f"10MB encryption too slow: {t_enc:.2f}s")
        self.assertLess(t_dec, 3.0, f"10MB decryption too slow: {t_dec:.2f}s")


if __name__ == "__main__":
    unittest.main(verbosity=2)
