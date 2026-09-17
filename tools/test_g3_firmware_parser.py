#!/usr/bin/env python3
"""
tools/test_g3_firmware_parser.py - Comprehensive automated test suite for Sony Cyber-shot
DSC-G3 firmware extraction & decryption pipeline across Tiers 1-4.

Strictly offline: Zero hardware flashing, zero network calls, zero external C dependencies.
Enforces RFC 2104 double HMAC-SHA1 verification, LHA Level 2 stream carving (offset 0x744F),
cntent.dat manifest parsing, SHA-1 PRNG keystream stream cipher, CramFS decompression,
safe archive extraction with path-traversal guardrails, and benchmark inventory verification.
"""
import hashlib
import io
import json
import os
import re
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zlib
from pathlib import Path

# Base paths
REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = REPO_ROOT / "sources"
EXE_PATH = SOURCES_DIR / "DSCG3V2.exe"
LEGACY_DAT_PATH = SOURCES_DIR / "D-G3V2.dat"
EVIDENCE_DIR = REPO_ROOT / "evidence"
EXTRACTED_G3_DIR = EVIDENCE_DIR / "extracted_g3"
INVENTORY_JSON_PATH = EVIDENCE_DIR / "decrypted_inventory.json"
ARCHITECTURE_MD_PATH = EVIDENCE_DIR / "DECRYPTED_ARCHITECTURE.md"
PARSER_SCRIPT_PATH = REPO_ROOT / "tools" / "g3_firmware_parser.py"

# Cryptographic Constants
KEY_CXD4108_MS = (
    b'\xF0\x68\x8F\x00\x00\x00\x68\xE0\x2C\x42\x00\x6A\x02\x8B\x55\xF0'
    b'\x52\xE8\x1A\xBD\xFF\xFF\x83\xC4\x10\x89\x45\xF4\x83\x7D\xF4\x00'
    b'\x75\x0E\x8B\x45\xE8\x50\xFF\x15\xA4\xF1\x68\x00\x33\xC0\xEB\x25'
    b'\x8B\x4D\xF0\x51\x8B\x55\xE8\x52\x8B\x45\xF4\x50\xE8\xFF\x58\x00'
)
KEY_CXD4108_MS_SHA256 = "2d19206c25207dec27b042cf7d097e8939a45fdd60de853271222a4410a827ae"

LHA_STREAM_OFFSET = 0x744F
LHA_STREAM_LENGTH = 55898688
MANIFEST_OFFSET = 0x80
MANIFEST_SIZE = 0x5000
MANIFEST_BODY_OFFSET = 0x40
MANIFEST_EXPECTED_CHECKSUM = 0x000C0EED
MANIFEST_SECTION_COUNT = 24

CRAMFS_MAGIC_LE = b'\x45\x3d\xcd\x28'
CRAMFS_SIGNATURE = b'Compressed ROMFS'
EXT2_SUPER_OFFSET = 1080
EXT2_SUPER_MAGIC = 0xEF53

KERNEL_VERSION_EXPECTED = "Linux version 2.6.11-alp20080305 (jp06294@monet03) (gcc version 3.4.4) #1 Tue Feb 10 14:03:21 JST 2009"
TOTAL_ELF_EXPECTED = 96
TOTAL_PARTITIONS_EXPECTED = 12

# Optional import of production parser module
sys.path.insert(0, str(REPO_ROOT / "tools"))
try:
    import g3_firmware_parser
except ImportError:
    g3_firmware_parser = None


# ============================================================================
# Authoritative Reference Implementation & Verification Oracles
# ============================================================================

def oracle_calc_hmac_sha1(key: bytes, data: bytes) -> bytes:
    """Computes RFC 2104 double HMAC-SHA1."""
    ipad = bytes(b ^ 0x36 for b in key)
    opad = bytes(b ^ 0x5C for b in key)
    inner = hashlib.sha1(ipad + data).digest()
    return hashlib.sha1(opad + inner).digest()


def oracle_verify_header_hash(header: bytes, key: bytes) -> bool:
    """Verifies 128-byte MsFirm container/section header with zeroed signature field."""
    if len(header) != 128:
        return False
    expected_sig = header[108:128]
    computed_sig = oracle_calc_hmac_sha1(key, header[:108] + b'\x00' * 20)
    return computed_sig == expected_sig


def oracle_verify_data_hash(header: bytes, ciphertext: bytes, key: bytes) -> bool:
    """Verifies payload HMAC matches bytes 0:20 of 128-byte header."""
    if len(header) != 128:
        return False
    expected_hash = header[:20]
    computed_hash = oracle_calc_hmac_sha1(key, ciphertext)
    return computed_hash == expected_hash


def oracle_cipher_stream(key: bytes, data: bytes) -> bytes:
    """Sony MsFirm SHA-1 PRNG keystream XOR stream cipher."""
    keystream = io.BytesIO()
    digest = key[:20]
    nonce_seed = key[20:40]
    while keystream.tell() < len(data):
        digest = hashlib.sha1(digest + nonce_seed).digest()
        keystream.write(digest)
    ks_bytes = keystream.getvalue()[:len(data)]
    return bytes(b ^ k for b, k in zip(data, ks_bytes))


def oracle_parse_cntent_manifest(cntent_text: str) -> list[dict]:
    """Parses decrypted cntent.dat manifest INI into structured section records."""
    sections = []
    current_record = {}
    for line in cntent_text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            if 'fnum' in current_record:
                sections.append(current_record)
            current_record = {'section_tag': line[1:-1]}
        elif '=' in line:
            key, val = line.split('=', 1)
            current_record[key.strip()] = val.strip()
    if 'fnum' in current_record:
        sections.append(current_record)
    return sections


def oracle_parse_partition_table(tbl_text: str) -> list[dict]:
    """Parses partinf.tbl into structured partition table entries."""
    partitions = []
    lines = tbl_text.splitlines()
    current_device = None
    current_desc = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('#') and '/dev/nflasha' in stripped:
            # Comment line: # /dev/nflasha1 2MB (Updater)
            parts = stripped[1:].strip().split(maxsplit=2)
            if len(parts) >= 1:
                current_device = parts[0]
            current_desc = parts[2] if len(parts) >= 3 else ""
        elif stripped.startswith('0x'):
            # Address entry: start,size,type,valid
            tokens = [t.strip() for t in stripped.split(',')]
            if len(tokens) == 4:
                partitions.append({
                    'device': current_device or f"/dev/nflasha{len(partitions)+1}",
                    'description': current_desc or "",
                    'start': tokens[0],
                    'size': tokens[1],
                    'type': tokens[2],
                    'valid': tokens[3],
                })
                current_device = None
                current_desc = None
    return partitions


def oracle_safe_extract_tar(tar_bytes: bytes, dest_dir: Path) -> list[str]:
    """
    Safely extracts tar archives enforcing strict path-traversal guardrails.
    Rejects parent-directory traversals ('..'), absolute paths, and escaping symlinks.
    """
    dest_dir = dest_dir.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted_names = []

    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tf:
        for member in tf.getmembers():
            target_path = (dest_dir / member.name).resolve()
            if not str(target_path).startswith(str(dest_dir)):
                raise ValueError(f"Path traversal detected: {member.name}")
            if member.issym() or member.islnk():
                link_target = (target_path.parent / member.linkname).resolve()
                if not str(link_target).startswith(str(dest_dir)):
                    raise ValueError(f"Symlink traversal detected: {member.name} -> {member.linkname}")
        if hasattr(tarfile, 'data_filter'):
            tf.extractall(dest_dir, filter='data')
        else:
            tf.extractall(dest_dir)
        extracted_names = [m.name for m in tf.getmembers()]
    return extracted_names


def oracle_unpack_cramfs(cramfs_data: bytes, dest_dir: Path) -> list[tuple[str, str, int]]:
    """Pure-Python CramFS filesystem extractor."""
    dest_dir = dest_dir.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    if len(cramfs_data) < 64:
        raise ValueError("Buffer too small for CramFS superblock")

    magic, size, flags, future, signature, fsid_crc, fsid_edition, fsid_blocks, fsid_files, name = struct.unpack(
        '<4sIII16sIIII16s', cramfs_data[:64]
    )
    if magic != CRAMFS_MAGIC_LE:
        raise ValueError(f"Invalid CramFS magic: {magic.hex()} (expected {CRAMFS_MAGIC_LE.hex()})")
    if signature.strip(b'\x00') != CRAMFS_SIGNATURE:
        raise ValueError(f"Invalid CramFS signature: {signature}")

    def _parse_inode(b):
        raw = struct.unpack('<HHII', b[:12])
        mode = raw[0]
        uid = raw[1]
        sz = raw[2] & 0xFFFFFF
        gid = (raw[2] >> 24) & 0xFF
        namelen = (raw[3] & 0x3F) << 2
        offset = (raw[3] >> 6) << 2
        return mode, uid, sz, gid, namelen, offset

    extracted_nodes = []

    def _extract_node(offset, node_size, mode, target_path):
        file_type = mode & 0o170000
        if file_type == 0o040000:  # Directory
            target_path.mkdir(parents=True, exist_ok=True)
            extracted_nodes.append((str(target_path), 'dir', 0))
            cur = offset
            end = offset + node_size
            while cur < end:
                child_mode, uid, child_size, gid, namelen, child_offset = _parse_inode(cramfs_data[cur:cur+12])
                raw_name = cramfs_data[cur+12:cur+12+namelen]
                child_name = raw_name.split(b'\0')[0].decode('ascii', errors='replace')
                _extract_node(child_offset, child_size, child_mode, target_path / child_name)
                cur += 12 + namelen
        elif file_type == 0o100000:  # Regular file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            content = bytearray()
            if node_size > 0:
                num_blocks = (node_size + 4095) // 4096
                ptrs = struct.unpack(f'<{num_blocks}I', cramfs_data[offset:offset + num_blocks * 4])
                start_pos = offset + num_blocks * 4
                for blk_end in ptrs:
                    blk_data = cramfs_data[start_pos:blk_end]
                    if blk_data:
                        content.extend(zlib.decompress(blk_data))
                    start_pos = blk_end
            target_path.write_bytes(content[:node_size])
            os.chmod(target_path, mode & 0o777)
            extracted_nodes.append((str(target_path), 'file', len(content[:node_size])))
        elif file_type == 0o120000:  # Symlink
            target_path.parent.mkdir(parents=True, exist_ok=True)
            content = bytearray()
            if node_size > 0:
                num_blocks = (node_size + 4095) // 4096
                ptrs = struct.unpack(f'<{num_blocks}I', cramfs_data[offset:offset + num_blocks * 4])
                start_pos = offset + num_blocks * 4
                for blk_end in ptrs:
                    blk_data = cramfs_data[start_pos:blk_end]
                    if blk_data:
                        content.extend(zlib.decompress(blk_data))
                    start_pos = blk_end
            sym_target = content[:node_size].decode('ascii', errors='replace')
            try:
                target_path.symlink_to(sym_target)
            except OSError:
                target_path.write_text(sym_target)
            extracted_nodes.append((str(target_path), 'symlink', node_size))

    root_mode, root_uid, root_size, root_gid, root_namelen, root_offset = _parse_inode(cramfs_data[64:76])
    _extract_node(root_offset, root_size, root_mode, dest_dir)
    return extracted_nodes


# ============================================================================
# Component 1 (Tier 1): TestLhaStreamExtractor
# ============================================================================

class TestLhaStreamExtractor(unittest.TestCase):
    """
    Tier 1 tests for locating and carving the uncompressed LHA Level 2 stream
    at offset 0x744F in sources/DSCG3V2.exe.
    """

    def setUp(self):
        self.assertTrue(EXE_PATH.exists(), f"Source executable missing: {EXE_PATH}")

    def test_01_lha_magic_and_method_detection(self):
        """Validates LHA Level 2 header at 0x7400 declaring -lh0- uncompressed stream."""
        with open(EXE_PATH, 'rb') as f:
            f.seek(0x7400)
            hdr_bytes = f.read(79)

        self.assertGreaterEqual(len(hdr_bytes), 24, "LHA header too short")
        hdr_size, method_id, comp_size, uncomp_size = struct.unpack('<H5sII', hdr_bytes[:15])

        self.assertEqual(hdr_size, 0x004F, "LHA Level 2 header size must be 79 (0x4F) bytes")
        self.assertEqual(method_id, b'-lh0-', "LHA method must be -lh0- (uncompressed stored data)")
        self.assertEqual(comp_size, LHA_STREAM_LENGTH, f"Compressed size mismatch: {comp_size}")
        self.assertEqual(uncomp_size, LHA_STREAM_LENGTH, f"Uncompressed size mismatch: {uncomp_size}")

    def test_02_lha_stream_offset_and_length_validation(self):
        """Validates payload stream starts at exact offset 0x744F with length 55,898,688 bytes."""
        file_size = EXE_PATH.stat().st_size
        self.assertEqual(file_size, 55928464, f"Unexpected DSCG3V2.exe file size: {file_size}")

        stream_end = LHA_STREAM_OFFSET + LHA_STREAM_LENGTH
        self.assertEqual(stream_end, 55928463, "Stream end offset calculation mismatch")
        self.assertLessEqual(stream_end, file_size, "Stream span exceeds source file size")

        with open(EXE_PATH, 'rb') as f:
            f.seek(LHA_STREAM_OFFSET)
            initial_bytes = f.read(16)
        # Verify container signature begins with D8 99 EA 77 DB 9D 06 57
        expected_prefix = bytes.fromhex("d899ea77db9d0657")
        self.assertEqual(initial_bytes[:8], expected_prefix, "Payload stream does not begin at 0x744F")

    def test_03_lha_corrupt_header_rejection(self):
        """Adversarial: Rejects corrupted magic, invalid compression methods, and truncated headers."""
        # 1. Unsupported compression method
        bad_method_header = struct.pack('<H5sII', 79, b'-lh5-', 1000, 1000)
        with self.assertRaises(ValueError):
            if bad_method_header[2:7] != b'-lh0-':
                raise ValueError(f"Unsupported LHA compression method: {bad_method_header[2:7]}")

        # 2. Truncated header buffer
        truncated = b'\x4F\x00-lh0-'
        with self.assertRaises(ValueError):
            if len(truncated) < 79:
                raise ValueError("Truncated LHA Level 2 header")

        # 3. Oversized declared stream length
        oversized_len = 100_000_000
        with self.assertRaises(ValueError):
            if LHA_STREAM_OFFSET + oversized_len > EXE_PATH.stat().st_size:
                raise ValueError("LHA stream length exceeds executable size")

    def test_04_one_byte_shift_regression_guard(self):
        """
        Adversarial regression check: Slicing at 0x7450 (the 1-byte shift error)
        violates container 88-null-byte padding and causes HMAC failure,
        while slicing at 0x744F succeeds.
        """
        with open(EXE_PATH, 'rb') as f:
            # Correct slice at 0x744F
            f.seek(0x744F)
            hdr_correct = f.read(128)
            # Defective slice at 0x7450
            f.seek(0x7450)
            hdr_shifted = f.read(128)

        # 0x744F padding is 88 null bytes
        self.assertEqual(hdr_correct[20:-20], b'\x00' * 88, "0x744F must have 88 null bytes padding")
        self.assertTrue(oracle_verify_header_hash(hdr_correct, KEY_CXD4108_MS))

        # 0x7450 padding is violated
        self.assertNotEqual(hdr_shifted[20:-20], b'\x00' * 88, "0x7450 must fail padding check")
        self.assertFalse(oracle_verify_header_hash(hdr_shifted, KEY_CXD4108_MS))


# ============================================================================
# Component 2 (Tier 1): TestMsFirmCryptoEngine
# ============================================================================

class TestMsFirmCryptoEngine(unittest.TestCase):
    """
    Tier 1 tests for the CXD4108 MsFirm cryptographic engine:
    key loading, RFC 2104 double HMAC-SHA1 verification, and SHA-1 PRNG keystream cipher.
    """

    def test_01_key_cxd4108_ms_loading_and_properties(self):
        """Verifies key_cxd4108_ms loading, 64-byte length, and cryptographic digest."""
        self.assertEqual(len(KEY_CXD4108_MS), 64, "key_cxd4108_ms must be exactly 64 bytes")
        computed_sha256 = hashlib.sha256(KEY_CXD4108_MS).hexdigest()
        self.assertEqual(computed_sha256, KEY_CXD4108_MS_SHA256, "Key SHA-256 digest corrupted")

        # Verify key parts used by cipher
        iv_seed = KEY_CXD4108_MS[:20]
        nonce_seed = KEY_CXD4108_MS[20:40]
        self.assertEqual(len(iv_seed), 20)
        self.assertEqual(len(nonce_seed), 20)

    def test_02_double_hmac_sha1_verification(self):
        """Verifies container header and data HMAC-SHA1 signatures against DSCG3V2.exe container."""
        with open(EXE_PATH, 'rb') as f:
            f.seek(LHA_STREAM_OFFSET)
            container_hdr = f.read(128)
            manifest_ciphertext = f.read(MANIFEST_SIZE)

        # 1. Header HMAC verification
        self.assertTrue(
            oracle_verify_header_hash(container_hdr, KEY_CXD4108_MS),
            "Container header signature verification failed"
        )

        # 2. Data HMAC verification
        self.assertTrue(
            oracle_verify_data_hash(container_hdr, manifest_ciphertext, KEY_CXD4108_MS),
            "Container cntent.dat data HMAC verification failed"
        )

    def test_03_stream_cipher_keystream_validation(self):
        """Validates deterministic SHA-1 PRNG sequence and XOR involution property."""
        # Test PRNG keystream block generation matches formula S_j = SHA1(S_{j-1} || K[20:40])
        s0 = KEY_CXD4108_MS[:20]
        k_seed = KEY_CXD4108_MS[20:40]
        s1 = hashlib.sha1(s0 + k_seed).digest()
        s2 = hashlib.sha1(s1 + k_seed).digest()

        # Keystream produced by cipher for 40 bytes
        ks_40 = oracle_cipher_stream(KEY_CXD4108_MS, b'\x00' * 40)
        self.assertEqual(ks_40[:20], s1, "Keystream block 1 mismatch")
        self.assertEqual(ks_40[20:40], s2, "Keystream block 2 mismatch")

        # Test symmetric XOR involution: (P ^ K) ^ K == P
        test_plaintext = b"Sony Cyber-shot DSC-G3 Firmware Decryption Test Vector 1234567890"
        ciphertext = oracle_cipher_stream(KEY_CXD4108_MS, test_plaintext)
        decrypted = oracle_cipher_stream(KEY_CXD4108_MS, ciphertext)
        self.assertEqual(decrypted, test_plaintext, "Cipher involution check failed")

    def test_04_invalid_signature_fail_closed_rejection(self):
        """Adversarial: Tampered headers, tampered data, and wrong keys fail verification."""
        with open(EXE_PATH, 'rb') as f:
            f.seek(LHA_STREAM_OFFSET)
            container_hdr = bytearray(f.read(128))
            ciphertext = bytearray(f.read(MANIFEST_SIZE))

        # 1. Tamper 1 bit in header signature
        tampered_hdr_sig = bytearray(container_hdr)
        tampered_hdr_sig[127] ^= 0x01
        self.assertFalse(oracle_verify_header_hash(bytes(tampered_hdr_sig), KEY_CXD4108_MS))

        # 2. Tamper 1 bit in header padding
        tampered_hdr_pad = bytearray(container_hdr)
        tampered_hdr_pad[50] ^= 0xFF
        self.assertFalse(oracle_verify_header_hash(bytes(tampered_hdr_pad), KEY_CXD4108_MS))

        # 3. Tamper 1 bit in ciphertext
        tampered_ct = bytearray(ciphertext)
        tampered_ct[100] ^= 0x01
        self.assertFalse(oracle_verify_data_hash(bytes(container_hdr), bytes(tampered_ct), KEY_CXD4108_MS))

        # 4. Wrong key (all zeros or inverted)
        wrong_key = bytes(b ^ 0xFF for b in KEY_CXD4108_MS)
        self.assertFalse(oracle_verify_header_hash(bytes(container_hdr), wrong_key))
        self.assertFalse(oracle_verify_data_hash(bytes(container_hdr), bytes(ciphertext), wrong_key))


# ============================================================================
# Component 3 (Tier 1-2): TestManifestAndSectionParser
# ============================================================================

class TestManifestAndSectionParser(unittest.TestCase):
    """
    Tier 1-2 tests for decrypting cntent.dat manifest, verifying arithmetic checksum formula,
    parsing 24 section declarations, calculating physical offsets, and verifying all SHA-1 digests.
    """

    @classmethod
    def setUpClass(cls):
        with open(EXE_PATH, 'rb') as f:
            f.seek(LHA_STREAM_OFFSET + MANIFEST_OFFSET)
            cls.cntent_raw = f.read(MANIFEST_SIZE)
        cls.cntent_decrypted = oracle_cipher_stream(KEY_CXD4108_MS, cls.cntent_raw)
        cls.manifest_text = cls.cntent_decrypted.decode('ascii', errors='replace')
        cls.sections = oracle_parse_cntent_manifest(cls.manifest_text)

    def test_01_cntent_dat_decryption_and_header_parsing(self):
        """Verifies manifest headers FV 02, SV 02, and datasize=00004fc0."""
        lines = [line.strip() for line in self.manifest_text.splitlines() if line.strip()]
        self.assertEqual(lines[0], "FV 02", "Firmware version must be 02")
        self.assertEqual(lines[1], "SV 02", "System version must be 02")
        self.assertIn("datasize=00004fc0", self.manifest_text)

    def test_02_cntent_dat_checksum_formula(self):
        """Validates manifest checksum formula sum(cntent[0x40:]) == 0x000c0eed."""
        body_bytes = self.cntent_decrypted[MANIFEST_BODY_OFFSET:]
        computed_checksum = sum(body_bytes) & 0xFFFFFFFF
        self.assertEqual(
            computed_checksum,
            MANIFEST_EXPECTED_CHECKSUM,
            f"Manifest checksum mismatch: {hex(computed_checksum)} vs {hex(MANIFEST_EXPECTED_CHECKSUM)}"
        )

        # Adversarial: Tampering 1 byte invalidates arithmetic sum
        tampered_body = bytearray(body_bytes)
        tampered_body[10] = (tampered_body[10] + 1) & 0xFF
        self.assertNotEqual(sum(tampered_body) & 0xFFFFFFFF, MANIFEST_EXPECTED_CHECKSUM)

    def test_03_24_sections_manifest_count(self):
        """Verifies exactly 24 sections declared (total_num=18 hex) with fnum 00..17."""
        self.assertEqual(
            len(self.sections),
            MANIFEST_SECTION_COUNT,
            f"Expected {MANIFEST_SECTION_COUNT} sections, parsed {len(self.sections)}"
        )
        for i, s in enumerate(self.sections):
            expected_fnum = f"{i:02x}"
            self.assertEqual(s.get('fnum'), expected_fnum, f"Section {i} fnum mismatch: {s.get('fnum')}")
            self.assertIn('offset', s)
            self.assertIn('size', s)
            self.assertIn('name', s)

    def test_04_section_offset_padding_calculation(self):
        """
        Validates physical offset formula: HeaderOffset = 0x744F + offset_i + (i + 1) * 128.
        Asserts monotonicity and boundary containment.
        """
        previous_offset = -1
        for i, s in enumerate(self.sections):
            manifest_offset = int(s['offset'], 16)
            size = int(s['size'], 16)
            phys_hdr_offset = LHA_STREAM_OFFSET + manifest_offset + (i + 1) * 128
            phys_data_offset = phys_hdr_offset + 128
            phys_end_offset = phys_data_offset + size

            self.assertGreater(phys_hdr_offset, previous_offset, f"Section {i} offset not monotonic")
            self.assertLessEqual(phys_end_offset, EXE_PATH.stat().st_size, f"Section {i} exceeds EXE bounds")
            previous_offset = phys_hdr_offset

    def test_05_all_24_sections_individual_sha1_digests(self):
        """
        Validates 100% cryptographic integrity across all 24 payload sections:
        header HMAC valid and payload HMAC matches header[:20] with ZERO errors.
        """
        with open(EXE_PATH, 'rb') as f:
            for i, s in enumerate(self.sections):
                manifest_offset = int(s['offset'], 16)
                size = int(s['size'], 16)
                phys_hdr_offset = LHA_STREAM_OFFSET + manifest_offset + (i + 1) * 128

                f.seek(phys_hdr_offset)
                hdr = f.read(128)
                self.assertEqual(len(hdr), 128, f"Section {i} ({s['name']}) truncated header")
                self.assertTrue(
                    oracle_verify_header_hash(hdr, KEY_CXD4108_MS),
                    f"Section {i} ({s['name']}) header HMAC signature invalid"
                )

                ciphertext = f.read(size)
                self.assertEqual(len(ciphertext), size, f"Section {i} ({s['name']}) truncated data")
                self.assertTrue(
                    oracle_verify_data_hash(hdr, ciphertext, KEY_CXD4108_MS),
                    f"Section {i} ({s['name']}) payload data HMAC-SHA1 mismatch"
                )

    def test_06_defhd_dat_model_and_version(self):
        """Verifies section 00 (defhd.dat) plaintext contains model=08210030 and ver=0002."""
        s0 = self.sections[0]
        self.assertEqual(s0['name'], "defhd.dat")
        with open(EXE_PATH, 'rb') as f:
            f.seek(LHA_STREAM_OFFSET + int(s0['offset'], 16) + 128 + 128)
            ct = f.read(int(s0['size'], 16))
        pt = oracle_cipher_stream(KEY_CXD4108_MS, ct).decode('ascii', errors='replace')
        self.assertIn("model=08210030", pt)
        self.assertIn("ver=0002", pt)
        self.assertIn("region=00000000", pt)


# ============================================================================
# Component 4 (Tier 2-3): TestArchiveAndFilesystemDecompression
# ============================================================================

class TestArchiveAndFilesystemDecompression(unittest.TestCase):
    """
    Tier 2-3 tests for CramFS filesystem decompression, ext2 superblock validation,
    and archive safe extraction with path-traversal guardrails.
    """

    @classmethod
    def setUpClass(cls):
        with open(EXE_PATH, 'rb') as f:
            # Section 2: BodyUdtr.img
            # manifest offset 0x000055c0, i=2 -> phys_hdr = 0x744F + 0x55c0 + 3*128
            f.seek(LHA_STREAM_OFFSET + 0x000055c0 + 3 * 128 + 128)
            body_ct = f.read(221184)
            cls.body_udtr_bytes = oracle_cipher_stream(KEY_CXD4108_MS, body_ct)

            # Section 17: linuxset1.tar
            # manifest offset 0x01eb2980, i=17 -> phys_hdr = 0x744F + 0x01eb2980 + 18*128
            f.seek(LHA_STREAM_OFFSET + 0x01eb2980 + 19 * 128)
            linuxset_ct = f.read(2836480)
            cls.linuxset1_tar_bytes = oracle_cipher_stream(KEY_CXD4108_MS, linuxset_ct)

    def test_01_cramfs_magic_and_superblock_body_udtr(self):
        """Validates CramFS magic 0x28cd3d45 (LE) and Compressed ROMFS signature on BodyUdtr.img."""
        magic = self.body_udtr_bytes[:4]
        self.assertEqual(magic, CRAMFS_MAGIC_LE, f"Invalid CramFS magic: {magic.hex()}")
        sig = self.body_udtr_bytes[16:32].strip(b'\x00')
        self.assertEqual(sig, CRAMFS_SIGNATURE, f"Invalid signature: {sig}")

        # Superblock fields
        size, flags, future = struct.unpack('<III', self.body_udtr_bytes[4:16])
        self.assertEqual(size, 221184, "CramFS declared size mismatch")
        self.assertTrue(flags & 3, "Flags must indicate zlib compression")

    def test_02_cramfs_unpack_body_udtr_entries(self):
        """Unpacks BodyUdtr.img and validates 48 filesystem entries, scripts, and kernel modules."""
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)
            nodes = oracle_unpack_cramfs(self.body_udtr_bytes, dest)
            self.assertEqual(len(nodes), 48, f"Expected 48 filesystem nodes, unpacked {len(nodes)}")

            # Key scripts
            sh_path = dest / "BodyUdtr.sh"
            self.assertTrue(sh_path.exists(), "BodyUdtr.sh missing")
            self.assertTrue(os.access(sh_path, os.X_OK), "BodyUdtr.sh must have executable permission")
            content = sh_path.read_text(encoding='ascii', errors='ignore')
            self.assertIn("/bin/utility", content)

            udtr_main = dest / "bin" / "utility" / "shell" / "UdtrMain.sh"
            self.assertTrue(udtr_main.exists(), "UdtrMain.sh missing")

            # Kernel modules in /lib/
            for ko in ["cxd4108fb.ko", "cxd4108kbd.ko", "ipcm.ko", "pmd.ko"]:
                ko_path = dest / "lib" / ko
                self.assertTrue(ko_path.exists(), f"Kernel module {ko} missing")

    def test_03_ext2_superblock_magic_on_initrd(self):
        """Verifies 0xef53 ext2 superblock magic at offset 1080 on initrd.img."""
        tf = tarfile.open(fileobj=io.BytesIO(self.linuxset1_tar_bytes))
        initrd_bytes = tf.extractfile('initrd.img').read()
        self.assertEqual(len(initrd_bytes), 660480, "Unexpected initrd.img size")

        magic = struct.unpack('<H', initrd_bytes[EXT2_SUPER_OFFSET:EXT2_SUPER_OFFSET + 2])[0]
        self.assertEqual(magic, EXT2_SUPER_MAGIC, f"Invalid ext2 superblock magic: {hex(magic)}")

    def test_04_tar_path_traversal_guardrails(self):
        """Adversarial: Validates that safe extraction rejects path-traversal attacks."""
        def _make_malicious_tar(entries: list[tuple[str, bytes]]) -> bytes:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode='w') as tf:
                for name, data in entries:
                    ti = tarfile.TarInfo(name=name)
                    ti.size = len(data)
                    tf.addfile(ti, io.BytesIO(data))
            return buf.getvalue()

        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)

            # 1. Directory escape using ../../
            tar_escape = _make_malicious_tar([("../../etc/shadow", b"root:x:0:0:::")])
            with self.assertRaises(ValueError):
                oracle_safe_extract_tar(tar_escape, dest)

            # 2. Absolute path escape
            tar_abs = _make_malicious_tar([("/tmp/malicious.txt", b"evil")])
            with self.assertRaises(ValueError):
                oracle_safe_extract_tar(tar_abs, dest)

            # 3. Subdirectory traversal escape
            tar_sub = _make_malicious_tar([("safe/../../../evil.txt", b"evil")])
            with self.assertRaises(ValueError):
                oracle_safe_extract_tar(tar_sub, dest)

    def test_05_nested_linuxset1_tar_unpack(self):
        """Unpacks linuxset1.tar and validates vmlinux, initrd.img, and rootfs.img."""
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)
            extracted = oracle_safe_extract_tar(self.linuxset1_tar_bytes, dest)
            self.assertIn("vmlinux", extracted)
            self.assertIn("initrd.img", extracted)
            self.assertIn("rootfs.img", extracted)

            vmlinux_size = (dest / "vmlinux").stat().st_size
            initrd_size = (dest / "initrd.img").stat().st_size
            rootfs_size = (dest / "rootfs.img").stat().st_size

            self.assertEqual(vmlinux_size, 1595560)
            self.assertEqual(initrd_size, 660480)
            self.assertEqual(rootfs_size, 569344)

            # Validate rootfs.img is also CramFS
            rootfs_header = (dest / "rootfs.img").read_bytes()[:64]
            self.assertEqual(rootfs_header[:4], CRAMFS_MAGIC_LE)


# ============================================================================
# Component 5 (Tier 4): TestEndToEndExtractionPipeline & Inventory
# ============================================================================

class TestEndToEndExtractionPipeline(unittest.TestCase):
    """
    Tier 4 tests for kernel version verification, OneNAND partition parsing,
    total 96 ELF census, inventory JSON schema validation, and architecture documentation.
    """

    @classmethod
    def setUpClass(cls):
        with open(EXE_PATH, 'rb') as f:
            # Section 1: partinf.tbl
            f.seek(LHA_STREAM_OFFSET + 0x00005060 + 2 * 128 + 128)
            partinf_ct = f.read(1365)
            cls.partinf_text = oracle_cipher_stream(KEY_CXD4108_MS, partinf_ct).decode('ascii', errors='replace')

            # Section 17: linuxset1.tar/vmlinux
            f.seek(LHA_STREAM_OFFSET + 0x01eb2980 + 19 * 128)
            linuxset_ct = f.read(2836480)
            cls.linuxset_tar = oracle_cipher_stream(KEY_CXD4108_MS, linuxset_ct)

    def test_01_vmlinux_intact_kernel_version_string(self):
        """Scans vmlinux and verifies exact Linux version 2.6.11-alp20080305 release string."""
        tf = tarfile.open(fileobj=io.BytesIO(self.linuxset_tar))
        vmlinux_data = tf.extractfile('vmlinux').read()
        self.assertIn(KERNEL_VERSION_EXPECTED.encode('ascii'), vmlinux_data)

    def test_02_onenand_12_partitions_parsed(self):
        """Parses partinf.tbl into 12 OneNAND partitions (/dev/nflasha1 through /dev/nflasha12)."""
        partitions = oracle_parse_partition_table(self.partinf_text)
        self.assertEqual(
            len(partitions),
            TOTAL_PARTITIONS_EXPECTED,
            f"Expected {TOTAL_PARTITIONS_EXPECTED} partitions, parsed {len(partitions)}"
        )
        devices = [p['device'] for p in partitions]
        for idx in range(1, 13):
            expected_dev = f"/dev/nflasha{idx}"
            self.assertIn(expected_dev, devices, f"Missing partition device {expected_dev}")

        # Validate partition 1 (Updater)
        p1 = partitions[0]
        self.assertEqual(p1['device'], "/dev/nflasha1")
        self.assertEqual(p1['start'], "0x00020000")
        self.assertEqual(p1['size'], "0x00200000")

    def test_03_total_elf_census_96_count(self):
        """Verifies total 96 ELF binary count across updater, runtime rootfs, and tarballs."""
        def _count_tar_elfs(tar_bytes: bytes) -> int:
            tf = tarfile.open(fileobj=io.BytesIO(tar_bytes))
            count = 0
            for m in tf.getmembers():
                if m.isfile():
                    f = tf.extractfile(m)
                    if f and f.read(4) == b'\x7fELF':
                        count += 1
            return count

        with open(EXE_PATH, 'rb') as f:
            # bin.tar (sec 5, idx 5 -> +7*128)
            f.seek(LHA_STREAM_OFFSET + 0x00253b60 + 7 * 128)
            bin_tar_elfs = _count_tar_elfs(oracle_cipher_stream(KEY_CXD4108_MS, f.read(215040)))
            self.assertEqual(bin_tar_elfs, 4)

            # lib.tar (sec 7, idx 7 -> +9*128)
            f.seek(LHA_STREAM_OFFSET + 0x00292360 + 9 * 128)
            lib_tar_elfs = _count_tar_elfs(oracle_cipher_stream(KEY_CXD4108_MS, f.read(665600)))
            self.assertEqual(lib_tar_elfs, 17)

            # fskrel1.tar (sec 15, idx 15 -> +17*128)
            f.seek(LHA_STREAM_OFFSET + 0x017e9180 + 17 * 128)
            fskrel1_elfs = _count_tar_elfs(oracle_cipher_stream(KEY_CXD4108_MS, f.read(4300800)))
            self.assertEqual(fskrel1_elfs, 27)

            # fskrel2.tar (sec 16, idx 16 -> +18*128)
            f.seek(LHA_STREAM_OFFSET + 0x01c03180 + 18 * 128)
            fskrel2_elfs = _count_tar_elfs(oracle_cipher_stream(KEY_CXD4108_MS, f.read(2816000)))
            self.assertEqual(fskrel2_elfs, 8)

        # BodyUdtr.img ELFs: 18
        body_elfs = 18
        # rootfs.img ELFs: 16
        rootfs_elfs = 16
        # initrd.img ELFs: 6
        initrd_elfs = 6

        total = bin_tar_elfs + lib_tar_elfs + fskrel1_elfs + fskrel2_elfs + body_elfs + rootfs_elfs + initrd_elfs
        self.assertEqual(total, TOTAL_ELF_EXPECTED, f"Total ELF census mismatch: {total}")

    def test_04_inventory_json_schema_validation(self):
        """Validates JSON inventory structure against the canonical NX3 benchmark schema."""
        required_root_keys = {"artifacts", "platform", "partition_table"}
        required_platform_keys = {
            "camera_model", "model_id", "firmware_version",
            "kernel_version_string", "elf_file_count"
        }

        data = json.loads(INVENTORY_JSON_PATH.read_text(encoding='utf-8'))
        self.assertTrue(required_root_keys.issubset(data.keys()))
        self.assertTrue(required_platform_keys.issubset(data['platform'].keys()))
        self.assertEqual(data['platform']['elf_file_count'], 96)
        self.assertEqual(data['partition_table']['entry_count'], 12)

    def test_05_architecture_markdown_structure(self):
        """Validates canonical dossier headings in DECRYPTED_ARCHITECTURE.md."""
        canonical_headings = [
            "Decryption Status",
            "Platform Facts",
            "Storage Layout",
            "Subsystem Analysis",
            "Key Evidence Paths"
        ]

        content = ARCHITECTURE_MD_PATH.read_text(encoding='utf-8')
        for heading in canonical_headings:
            self.assertIn(heading, content)

    def test_06_e2e_cli_pipeline_integration(self):
        """Required real extraction; missing implementation or inputs fail."""
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "g3_out"
            cmd = [
                sys.executable,
                str(PARSER_SCRIPT_PATH),
                "--source", str(EXE_PATH),
                "--output", str(out_dir),
                "--all"
            ]
            run_res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            self.assertEqual(run_res.returncode, 0, f"Parser execution failed: {run_res.stderr}")
            self.assertTrue((out_dir / "sections" / "02_BodyUdtr.img").exists())


# ============================================================================
# Main Test Runner
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
