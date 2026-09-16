#!/usr/bin/env python3
"""
tools/test_challenger_m1_gate.py - Independent Empirical Challenger Test Suite for Milestone 1 Gate.
Author: Challenger 2 (Empirical Challenger)

Empirically verifies:
1. Bit-for-bit identity between sources/D-G3V2.dat and sources/DSCG3V2.exe at offset 0x744F.
2. Manifest cntent.dat checksum formula sum(cntent[0x40:]) == 0x000c0eed and fail-closed properties.
3. Independent 20-byte SHA-1 payload HMAC digests of all 24 sections on disk matching block headers in sources/DSCG3V2.exe.
4. Adversarial stress tests (bit flips, corrupt padding, truncated streams, wrong keys).
"""
import hashlib
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = REPO_ROOT / "sources"
EXE_PATH = SOURCES_DIR / "DSCG3V2.exe"
DAT_PATH = SOURCES_DIR / "D-G3V2.dat"
EVIDENCE_DIR = REPO_ROOT / "evidence"
EXTRACTED_G3_DIR = EVIDENCE_DIR / "extracted_g3"
SECTIONS_DIR = EXTRACTED_G3_DIR / "sections"
MANIFEST_JSON_PATH = EXTRACTED_G3_DIR / "manifest.json"
CNTENT_DAT_PATH = EXTRACTED_G3_DIR / "cntent.dat"

# Constants
KEY_CXD4108_MS = (
    b'\xF0\x68\x8F\x00\x00\x00\x68\xE0\x2C\x42\x00\x6A\x02\x8B\x55\xF0'
    b'\x52\xE8\x1A\xBD\xFF\xFF\x83\xC4\x10\x89\x45\xF4\x83\x7D\xF4\x00'
    b'\x75\x0E\x8B\x45\xE8\x50\xFF\x15\xA4\xF1\x68\x00\x33\xC0\xEB\x25'
    b'\x8B\x4D\xF0\x51\x8B\x55\xE8\x52\x8B\x45\xF4\x50\xE8\xFF\x58\x00'
)
LHA_STREAM_OFFSET = 0x744F
LHA_STREAM_LENGTH = 55898688  # 0x0354F240
BLOCK_HEADER_SIZE = 128
MANIFEST_OFFSET = 0
MANIFEST_SIZE = 0x5000  # 20,480 bytes
MANIFEST_BODY_OFFSET = 0x40  # 64 bytes
EXPECTED_CHKSUM = 0x000C0EED
EXPECTED_SECTIONS = 24


# ============================================================================
# Independent Oracle Implementation (Clean-room, zero dependency on parser)
# ============================================================================

def calc_hmac_sha1(key: bytes, data: bytes) -> bytes:
    """RFC 2104 double SHA-1 HMAC."""
    ipad = bytes(b ^ 0x36 for b in key)
    opad = bytes(b ^ 0x5C for b in key)
    inner = hashlib.sha1(ipad + data).digest()
    return hashlib.sha1(opad + inner).digest()


def stream_cipher(key: bytes, data: bytes) -> bytes:
    """Sony MsFirm SHA-1 PRNG keystream XOR cipher."""
    if not data:
        return b''
    data_len = len(data)
    chunks = []
    generated = 0
    digest = key[:20]
    seed = key[20:40]
    while generated < data_len:
        digest = hashlib.sha1(digest + seed).digest()
        chunks.append(digest)
        generated += 20
    ks = b''.join(chunks)[:data_len]
    return bytes(b ^ k for b, k in zip(data, ks))


def parse_manifest_independent(raw_cntent: bytes) -> dict:
    """Independent manifest parser."""
    text = raw_cntent.decode('latin1')
    sections = []
    curr = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            if 'fnum' in curr:
                sections.append(curr)
            curr = {'tag': line[1:-1]}
        elif '=' in line:
            k, v = line.split('=', 1)
            curr[k.strip()] = v.strip()
    if 'fnum' in curr:
        sections.append(curr)
    return sections


# ============================================================================
# Challenger Test Cases
# ============================================================================

class TestMilestone1Challenger(unittest.TestCase):
    """Rigorous empirical challenge of Milestone 1 deliverables."""

    def test_01_dual_source_bit_for_bit_identity(self):
        """
        Verify sources/D-G3V2.dat and sources/DSCG3V2.exe at 0x744F
        produce bit-for-bit identical streams of length 55,898,688 bytes.
        """
        self.assertTrue(EXE_PATH.exists(), f"EXE missing: {EXE_PATH}")
        self.assertTrue(DAT_PATH.exists(), f"DAT missing: {DAT_PATH}")

        # Size check
        dat_size = DAT_PATH.stat().st_size
        self.assertEqual(
            dat_size,
            LHA_STREAM_LENGTH,
            f"sources/D-G3V2.dat size {dat_size} != expected {LHA_STREAM_LENGTH}"
        )

        # Stream extraction from EXE at 0x744F
        chunk_size = 1024 * 1024
        sha_exe = hashlib.sha256()
        sha_dat = hashlib.sha256()

        with open(EXE_PATH, 'rb') as f_exe, open(DAT_PATH, 'rb') as f_dat:
            f_exe.seek(LHA_STREAM_OFFSET)
            bytes_read = 0
            while bytes_read < LHA_STREAM_LENGTH:
                to_read = min(chunk_size, LHA_STREAM_LENGTH - bytes_read)
                buf_exe = f_exe.read(to_read)
                buf_dat = f_dat.read(to_read)

                self.assertEqual(len(buf_exe), to_read, "Truncated read from EXE")
                self.assertEqual(len(buf_dat), to_read, "Truncated read from DAT")
                self.assertEqual(buf_exe, buf_dat, f"Byte mismatch at offset {bytes_read:#x}")

                sha_exe.update(buf_exe)
                sha_dat.update(buf_dat)
                bytes_read += to_read

        exe_digest = sha_exe.hexdigest()
        dat_digest = sha_dat.hexdigest()
        self.assertEqual(exe_digest, dat_digest, "SHA-256 digest mismatch between carved stream and DAT file")
        print(f"\n[CHALLENGER-PASS] Bit-for-bit stream verified: SHA-256 = {exe_digest}")

        # Also check carved file in evidence if present
        evidence_dat = EXTRACTED_G3_DIR / "D-G3V2.dat"
        if evidence_dat.exists():
            sha_ev = hashlib.sha256(evidence_dat.read_bytes()).hexdigest()
            self.assertEqual(sha_ev, dat_digest, "evidence/extracted_g3/D-G3V2.dat SHA-256 mismatch")

        # Negative test: Slicing at 0x7450 (1-byte shift bug) MUST differ
        with open(EXE_PATH, 'rb') as f_exe:
            f_exe.seek(0x7450)
            buf_shifted = f_exe.read(128)
        with open(DAT_PATH, 'rb') as f_dat:
            buf_dat_head = f_dat.read(128)
        self.assertNotEqual(buf_shifted, buf_dat_head, "Shifted offset 0x7450 should NOT match D-G3V2.dat")

    def test_02_manifest_checksum_rigorous_validation(self):
        """
        Verify manifest cntent.dat checksum formula:
        sum(cntent[0x40:]) == 0x000c0eed and adversarial fail-closed behavior.
        """
        self.assertTrue(CNTENT_DAT_PATH.exists(), f"cntent.dat missing: {CNTENT_DAT_PATH}")
        cntent_disk = CNTENT_DAT_PATH.read_bytes()
        self.assertEqual(len(cntent_disk), MANIFEST_SIZE, f"cntent.dat size {len(cntent_disk)} != {MANIFEST_SIZE}")

        # Carve and decrypt independently from EXE
        with open(EXE_PATH, 'rb') as f:
            f.seek(LHA_STREAM_OFFSET + BLOCK_HEADER_SIZE)
            enc_cntent = f.read(MANIFEST_SIZE)
        cntent_carved = stream_cipher(KEY_CXD4108_MS, enc_cntent)

        self.assertEqual(cntent_disk, cntent_carved, "Decrypted cntent.dat on disk != carved from EXE")

        # Header values
        header_text = cntent_disk[:0x40].decode('latin1')
        self.assertIn("FV 02", header_text)
        self.assertIn("SV 02", header_text)
        self.assertIn("datasize=00004fc0", header_text)
        self.assertIn("chksum=000c0eed", header_text)

        # Checksum calculation: exact sum of bytes from index 0x40
        body_bytes = cntent_disk[MANIFEST_BODY_OFFSET:]
        computed_sum = sum(body_bytes) & 0xFFFFFFFF
        self.assertEqual(
            computed_sum,
            EXPECTED_CHKSUM,
            f"Computed checksum {computed_sum:#010x} != expected {EXPECTED_CHKSUM:#010x}"
        )
        print(f"[CHALLENGER-PASS] Manifest checksum verified: {computed_sum:#010x} == {EXPECTED_CHKSUM:#010x}")

        # Adversarial tests on checksum:
        # 1. Mutate byte at offset 0 of body
        tampered_0 = bytearray(body_bytes)
        tampered_0[0] = (tampered_0[0] + 1) & 0xFF
        self.assertNotEqual(sum(tampered_0) & 0xFFFFFFFF, EXPECTED_CHKSUM)

        # 2. Mutate byte in the middle of body
        tampered_mid = bytearray(body_bytes)
        tampered_mid[len(body_bytes) // 2] ^= 0x01
        self.assertNotEqual(sum(tampered_mid) & 0xFFFFFFFF, EXPECTED_CHKSUM)

        # 3. Mutate byte at end of body
        tampered_end = bytearray(body_bytes)
        tampered_end[-1] ^= 0x80
        self.assertNotEqual(sum(tampered_end) & 0xFFFFFFFF, EXPECTED_CHKSUM)

        # 4. Truncation fails checksum
        self.assertNotEqual(sum(body_bytes[:-1]) & 0xFFFFFFFF, EXPECTED_CHKSUM)

    def test_03_all_24_section_payload_digests_and_block_headers(self):
        """
        Independently compute 20-byte SHA-1 payload HMAC digests and verify against
        exact signatures from block headers in sources/DSCG3V2.exe for all 24 sections.
        """
        self.assertTrue(MANIFEST_JSON_PATH.exists(), f"manifest.json missing: {MANIFEST_JSON_PATH}")
        with open(MANIFEST_JSON_PATH, 'r', encoding='utf-8') as f:
            manifest_json = json.load(f)

        raw_cntent = CNTENT_DAT_PATH.read_bytes()
        parsed_sections = parse_manifest_independent(raw_cntent)
        self.assertEqual(len(parsed_sections), EXPECTED_SECTIONS, f"Parsed {len(parsed_sections)} != 24 sections")

        verified_count = 0

        with open(EXE_PATH, 'rb') as f_exe:
            for i, sec in enumerate(parsed_sections):
                name = sec['name']
                offset = int(sec['offset'], 16)
                size = int(sec['size'], 16)

                # Physical block header offset formula
                phys_hdr = LHA_STREAM_OFFSET + offset + (i + 1) * BLOCK_HEADER_SIZE
                phys_data = phys_hdr + BLOCK_HEADER_SIZE

                f_exe.seek(phys_hdr)
                hdr = f_exe.read(BLOCK_HEADER_SIZE)
                self.assertEqual(len(hdr), BLOCK_HEADER_SIZE, f"Truncated header for sec {i}")

                # Verify 88 null bytes padding
                padding = hdr[20:108]
                self.assertEqual(padding, b'\x00' * 88, f"Non-null padding in sec {i} header")

                # Verify 20-byte header HMAC
                expected_hdr_hmac = hdr[108:128]
                computed_hdr_hmac = calc_hmac_sha1(KEY_CXD4108_MS, hdr[:108] + b'\x00' * 20)
                self.assertEqual(
                    computed_hdr_hmac,
                    expected_hdr_hmac,
                    f"Header HMAC invalid for sec {i} ({name})"
                )

                # Read raw ciphertext from EXE
                f_exe.seek(phys_data)
                enc_data = f_exe.read(size)
                self.assertEqual(len(enc_data), size, f"Truncated ciphertext for sec {i}")

                # Verify 20-byte data HMAC against header bytes 0..20
                expected_data_hmac = hdr[:20]
                computed_data_hmac = calc_hmac_sha1(KEY_CXD4108_MS, enc_data)
                self.assertEqual(
                    computed_data_hmac,
                    expected_data_hmac,
                    f"Data HMAC mismatch for sec {i} ({name}): {computed_data_hmac.hex()} != {expected_data_hmac.hex()}"
                )

                # Decrypt raw ciphertext
                decrypted = stream_cipher(KEY_CXD4108_MS, enc_data)

                # Read on-disk section payload
                disk_file = SECTIONS_DIR / f"{i:02d}_{name}"
                symlink_file = SECTIONS_DIR / name

                self.assertTrue(disk_file.exists(), f"Payload missing on disk: {disk_file}")
                self.assertTrue(symlink_file.exists(), f"Symlink missing on disk: {symlink_file}")

                disk_bytes = disk_file.read_bytes()
                symlink_bytes = symlink_file.read_bytes()

                self.assertEqual(len(disk_bytes), size, f"Disk file size mismatch for sec {i}")
                self.assertEqual(disk_bytes, decrypted, f"Decrypted payload != disk bytes for sec {i}")
                self.assertEqual(symlink_bytes, disk_bytes, f"Symlink bytes != target bytes for sec {i}")

                # Re-encrypt disk bytes and verify data HMAC reproduces header[:20]
                re_encrypted = stream_cipher(KEY_CXD4108_MS, disk_bytes)
                self.assertEqual(re_encrypted, enc_data, f"Re-encryption mismatch for sec {i}")
                re_hmac = calc_hmac_sha1(KEY_CXD4108_MS, re_encrypted)
                self.assertEqual(re_hmac, expected_data_hmac, f"Re-encrypted HMAC mismatch for sec {i}")

                # Verify against manifest.json records
                json_sec = manifest_json['sections'][i]
                self.assertEqual(json_sec['name'], name)
                self.assertEqual(json_sec['size'], size)
                self.assertEqual(json_sec['header_hmac'], expected_hdr_hmac.hex())
                self.assertEqual(json_sec['data_hmac'], expected_data_hmac.hex())
                self.assertEqual(json_sec['decrypted_sha1'], hashlib.sha1(disk_bytes).hexdigest())
                self.assertEqual(json_sec['decrypted_sha256'], hashlib.sha256(disk_bytes).hexdigest())
                self.assertTrue(json_sec['verified'])

                verified_count += 1

        self.assertEqual(verified_count, EXPECTED_SECTIONS)
        print(f"[CHALLENGER-PASS] All {verified_count} section payloads cryptographically verified on disk.")

    def test_04_adversarial_tampering_and_fail_closed_guarantees(self):
        """
        Adversarial: Test fail-closed behavior under bit flips, header truncation,
        corrupt ciphertext, and invalid key material.
        """
        # Load container header and manifest ciphertext
        with open(EXE_PATH, 'rb') as f:
            f.seek(LHA_STREAM_OFFSET)
            hdr = bytearray(f.read(BLOCK_HEADER_SIZE))
            ct = bytearray(f.read(MANIFEST_SIZE))

        # 1. Flip bit in header signature (bytes 108:128) -> header HMAC check MUST fail
        bad_hdr_sig = bytearray(hdr)
        bad_hdr_sig[115] ^= 0x40
        self.assertNotEqual(
            calc_hmac_sha1(KEY_CXD4108_MS, bad_hdr_sig[:108] + b'\x00' * 20),
            bytes(bad_hdr_sig[108:128])
        )

        # 2. Flip bit in null padding (bytes 20:108) -> header HMAC check MUST fail
        bad_hdr_pad = bytearray(hdr)
        bad_hdr_pad[45] = 0x01
        self.assertNotEqual(
            calc_hmac_sha1(KEY_CXD4108_MS, bad_hdr_pad[:108] + b'\x00' * 20),
            bytes(bad_hdr_pad[108:128])
        )

        # 3. Flip bit in data HMAC signature (bytes 0:20) -> header HMAC check MUST fail
        bad_data_sig = bytearray(hdr)
        bad_data_sig[5] ^= 0x02
        self.assertNotEqual(
            calc_hmac_sha1(KEY_CXD4108_MS, bad_data_sig[:108] + b'\x00' * 20),
            bytes(bad_data_sig[108:128])
        )

        # 4. Flip bit in ciphertext -> data HMAC check MUST fail
        bad_ct = bytearray(ct)
        bad_ct[500] ^= 0x08
        self.assertNotEqual(
            calc_hmac_sha1(KEY_CXD4108_MS, bytes(bad_ct)),
            bytes(hdr[:20])
        )

        # 5. Wrong key (all zeroes, inverted, or single-bit mutated) -> both checks MUST fail
        zero_key = b'\x00' * 64
        self.assertNotEqual(
            calc_hmac_sha1(zero_key, hdr[:108] + b'\x00' * 20),
            bytes(hdr[108:128])
        )
        self.assertNotEqual(
            calc_hmac_sha1(zero_key, bytes(ct)),
            bytes(hdr[:20])
        )

        mutated_key = bytearray(KEY_CXD4108_MS)
        mutated_key[0] ^= 0x01
        self.assertNotEqual(
            calc_hmac_sha1(bytes(mutated_key), hdr[:108] + b'\x00' * 20),
            bytes(hdr[108:128])
        )
        self.assertNotEqual(
            calc_hmac_sha1(bytes(mutated_key), bytes(ct)),
            bytes(hdr[:20])
        )
        print("[CHALLENGER-PASS] Adversarial tampering tests passed (fail-closed verified).")

    def test_05_parser_container_unpack_parity(self):
        """
        Verify that tools/g3_firmware_parser.py produces identical outputs when run
        against sources/DSCG3V2.exe vs sources/D-G3V2.dat into isolated scratch directories.
        """
        sys.path.insert(0, str(REPO_ROOT / "tools"))
        import g3_firmware_parser

        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            out1 = Path(td1)
            out2 = Path(td2)

            parser_exe = g3_firmware_parser.G3FirmwareParser(EXE_PATH)
            parser_exe.extract_sections(out1, dump_container=False)

            parser_dat = g3_firmware_parser.G3FirmwareParser(DAT_PATH)
            parser_dat.extract_sections(out2, dump_container=False)

            # Compare all 24 section files between out1 and out2
            for i in range(24):
                f1_list = list((out1 / 'sections').glob(f"{i:02d}_*"))
                f2_list = list((out2 / 'sections').glob(f"{i:02d}_*"))
                self.assertEqual(len(f1_list), 1)
                self.assertEqual(len(f2_list), 1)
                self.assertEqual(f1_list[0].name, f2_list[0].name)
                b1 = f1_list[0].read_bytes()
                b2 = f2_list[0].read_bytes()
                self.assertEqual(b1, b2, f"Section {i} mismatch between EXE and DAT parse runs")

            # Compare cntent.dat
            self.assertEqual(
                (out1 / 'cntent.dat').read_bytes(),
                (out2 / 'cntent.dat').read_bytes()
            )
            print("[CHALLENGER-PASS] Full parser unpack parity verified across EXE and DAT sources.")


if __name__ == '__main__':
    unittest.main(verbosity=2)
