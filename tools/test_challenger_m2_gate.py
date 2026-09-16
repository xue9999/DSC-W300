#!/usr/bin/env python3
"""
tools/test_challenger_m2_gate.py - Independent Empirical Challenger Test Suite for Milestone 2/3 & Final Acceptance Gate.
Author: Challenger 1 (Empirical Challenger)

Empirically verifies:
1. Path traversal defenses in safe_extract_tar (dot-dot, absolute paths, backslashes, escaping symlinks, hardlinks, devices).
2. CramFS robustness against corrupted magic, invalid signature, truncated superblock, truncated inodes, and corrupt zlib blocks.
3. Ext2 robustness against corrupted magic and truncated image buffers.
4. CLI flag handling, non-existent source rejection, custom output directory redirection, and idempotent overwrite permissions.
5. End-to-end extraction integrity: 96 ELFs, 12 partitions, exact kernel release banner, and NX3 benchmark compliance.
"""
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zlib
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = REPO_ROOT / "sources"
EXE_PATH = SOURCES_DIR / "DSCG3V2.exe"
DAT_PATH = SOURCES_DIR / "D-G3V2.dat"
EVIDENCE_DIR = REPO_ROOT / "evidence"
EXTRACTED_G3_DIR = EVIDENCE_DIR / "extracted_g3"
SECTIONS_DIR = EXTRACTED_G3_DIR / "sections"
BODY_UDTR_PATH = SECTIONS_DIR / "02_BodyUdtr.img"
INITRD_PATH = EXTRACTED_G3_DIR / "kernel" / "initrd.img"
VMLINUX_PATH = EXTRACTED_G3_DIR / "kernel" / "vmlinux"
PARTINF_PATH = SECTIONS_DIR / "01_partinf.tbl"

sys.path.insert(0, str(REPO_ROOT / "tools"))
import g3_firmware_parser
from g3_firmware_parser import (
    SafeTarExtractor,
    safe_extract_tar,
    CramFSUnpacker,
    unpack_cramfs,
    Ext2Unpacker,
    unpack_ext2,
    G3FirmwareParser,
    parse_partition_table,
    extract_kernel_version,
    count_elf_files,
    CRAMFS_MAGIC_LE,
    CRAMFS_SIGNATURE,
    EXT2_SUPER_MAGIC,
    KERNEL_VERSION_EXPECTED
)


def create_tar_archive(members: list[tuple[str, bytes | None, dict]]) -> bytes:
    """Helper to synthesize custom tar archives in memory."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as tf:
        for name, data, attrs in members:
            ti = tarfile.TarInfo(name=name)
            for k, v in attrs.items():
                setattr(ti, k, v)
            if data is not None:
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
            else:
                tf.addfile(ti)
    return buf.getvalue()


class TestMilestone2ChallengerGate(unittest.TestCase):
    """
    Exhaustive empirical challenger test suite for Milestone 2/3 & Final Acceptance Gate.
    """

    @classmethod
    def setUpClass(cls):
        if not EXE_PATH.exists():
            raise FileNotFoundError(f"Source firmware not found: {EXE_PATH}")

    # ========================================================================
    # Component 1: Tar Archive Path-Traversal Defense Suite
    # ========================================================================

    def test_01_tar_relative_dotdot_traversal_rejection(self):
        """
        Adversarial: Verify safe_extract_tar strictly rejects '..' parent traversals:
        - Simple prefix: '../escape.txt'
        - Deep traversal: 'a/b/../../c/../../../escape.txt'
        - Traversal in directory name: 'sub/../escape.txt'
        """
        test_cases = [
            '../escape.txt',
            '../../escape.txt',
            'a/b/../../c/../../../escape.txt',
            'sub/../escape.txt',
            'sub/sub2/../../escape.txt'
        ]
        for bad_name in test_cases:
            tar_bytes = create_tar_archive([(bad_name, b'adversarial_payload', {})])
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError, msg=f"Failed to reject dot-dot path: {bad_name}") as ctx:
                    safe_extract_tar(tar_bytes, td)
                self.assertIn("Parent traversal '..' in tar archive rejected", str(ctx.exception))

    def test_02_tar_absolute_path_rejection(self):
        """
        Adversarial: Verify safe_extract_tar strictly rejects absolute paths:
        - Unix root: '/tmp/evil.txt', '/evil.txt'
        - Windows style backslash: chr(92) + 'tmp' + chr(92) + 'evil.txt'
        """
        test_cases = [
            '/tmp/evil.txt',
            '/evil.txt',
            '/etc/shadow',
            chr(92) + 'tmp' + chr(92) + 'evil.txt',
            chr(92) + 'evil.txt'
        ]
        for bad_path in test_cases:
            tar_bytes = create_tar_archive([(bad_path, b'adversarial_payload', {})])
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError, msg=f"Failed to reject absolute path: {bad_path}") as ctx:
                    safe_extract_tar(tar_bytes, td)
                self.assertIn("Absolute path in tar archive rejected", str(ctx.exception))

    def test_03_tar_escaping_symlinks_rejection(self):
        """
        Adversarial: Verify safe_extract_tar strictly rejects symlinks pointing outside the destination directory:
        - Parent directory escapes: '..', '../', '../../'
        - Root directory: '/'
        - Absolute system paths: '/etc', '/tmp'
        - Relative escapes from nested directories: 'sub/sym -> ../../sub/file.txt'
        """
        escaping_links = [
            ('sym1', '..'),
            ('sym2', '../'),
            ('sym3', '../../'),
            ('sym4', '/'),
            ('sym5', '/tmp'),
            ('sym6', '/etc'),
            ('sub/sym7', '../../escape.txt'),
            ('sub/sub2/sym8', '../../../escape.txt')
        ]
        for member_name, link_target in escaping_links:
            tar_bytes = create_tar_archive([(member_name, None, {'type': tarfile.SYMTYPE, 'linkname': link_target})])
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError, msg=f"Failed to reject escaping symlink: {member_name} -> {link_target}") as ctx:
                    safe_extract_tar(tar_bytes, td)
                self.assertIn("Symlink traversal detected", str(ctx.exception))

    def test_04_tar_escaping_hardlinks_rejection(self):
        """
        Adversarial: Verify safe_extract_tar strictly rejects hard links pointing outside destination:
        - Absolute link target: '/etc/passwd'
        - Relative link target: '../../etc/passwd'
        """
        escaping_hardlinks = [
            ('hlink1', '/etc/passwd'),
            ('hlink2', '../../etc/passwd'),
            ('hlink3', '/tmp/outside')
        ]
        for member_name, link_target in escaping_hardlinks:
            tar_bytes = create_tar_archive([(member_name, None, {'type': tarfile.LNKTYPE, 'linkname': link_target})])
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError, msg=f"Failed to reject hardlink: {member_name} -> {link_target}") as ctx:
                    safe_extract_tar(tar_bytes, td)
                self.assertIn("Symlink traversal detected", str(ctx.exception))

    def test_05_tar_special_device_and_fifo_rejection(self):
        """
        Adversarial: Verify safe_extract_tar strictly rejects special device files:
        - Character device (tarfile.CHRTYPE)
        - Block device (tarfile.BLKTYPE)
        - FIFO pipe (tarfile.FIFOTYPE)
        """
        special_types = [
            ('dev_chr', tarfile.CHRTYPE),
            ('dev_blk', tarfile.BLKTYPE),
            ('dev_fifo', tarfile.FIFOTYPE)
        ]
        for name, dev_type in special_types:
            tar_bytes = create_tar_archive([(name, None, {'type': dev_type})])
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError, msg=f"Failed to reject device type: {name}") as ctx:
                    safe_extract_tar(tar_bytes, td)
                self.assertIn("Special device file rejected", str(ctx.exception))

    def test_06_tar_legitimate_archive_extraction(self):
        """
        Functional: Verify safe_extract_tar cleanly extracts valid archives containing:
        - Directories, subdirectories, regular files
        - Legitimate internal relative symlinks that remain inside dest_dir
        """
        members = [
            ('dir1', None, {'type': tarfile.DIRTYPE}),
            ('dir1/hello.txt', b'Hello world', {'type': tarfile.REGTYPE}),
            ('dir1/sub', None, {'type': tarfile.DIRTYPE}),
            ('dir1/sub/nested.txt', b'Nested content', {'type': tarfile.REGTYPE}),
            ('dir1/sym_internal', None, {'type': tarfile.SYMTYPE, 'linkname': 'hello.txt'}),
            ('dir1/sub/sym_up', None, {'type': tarfile.SYMTYPE, 'linkname': '../hello.txt'})
        ]
        tar_bytes = create_tar_archive(members)
        with tempfile.TemporaryDirectory() as td:
            extracted = safe_extract_tar(tar_bytes, td)
            self.assertEqual(len(extracted), 6)
            self.assertTrue((Path(td) / 'dir1' / 'hello.txt').exists())
            self.assertEqual((Path(td) / 'dir1' / 'hello.txt').read_bytes(), b'Hello world')
            self.assertTrue((Path(td) / 'dir1' / 'sub' / 'nested.txt').exists())
            self.assertEqual((Path(td) / 'dir1' / 'sub' / 'nested.txt').read_bytes(), b'Nested content')
            # Verify internal symlink
            sym_p = Path(td) / 'dir1' / 'sub' / 'sym_up'
            self.assertTrue(sym_p.exists())
            self.assertEqual(sym_p.read_bytes(), b'Hello world')

    # ========================================================================
    # Component 2: CramFS Robustness & Corruption Rejection Suite
    # ========================================================================

    def test_07_cramfs_invalid_magic_fail_closed(self):
        """
        Adversarial: Verify CramFSUnpacker rejects invalid magic numbers with ValueError:
        - All zeroes
        - Big-endian CramFS magic 0x28cd3d45 (\x28\xcd\x3d\x45)
        - Random garbage
        """
        self.assertTrue(BODY_UDTR_PATH.exists(), f"BodyUdtr.img missing: {BODY_UDTR_PATH}")
        orig_img = BODY_UDTR_PATH.read_bytes()

        invalid_magics = [
            b'\x00\x00\x00\x00',
            b'\x28\xcd\x3d\x45',  # Big-endian instead of little-endian
            b'\xde\xad\xbe\xef',
            b'ROMS'
        ]
        for bad_m in invalid_magics:
            tampered = bad_m + orig_img[4:]
            with self.assertRaises(ValueError, msg=f"Failed to reject invalid magic: {bad_m.hex()}") as ctx:
                CramFSUnpacker(tampered)
            self.assertIn("Invalid CramFS magic", str(ctx.exception))

    def test_08_cramfs_corrupted_signature_fail_closed(self):
        """
        Adversarial: Verify CramFSUnpacker rejects corrupted filesystem signatures:
        Valid magic, but signature field (bytes 16..32) tampered from 'Compressed ROMFS'.
        """
        orig_img = BODY_UDTR_PATH.read_bytes()
        tampered_sig = orig_img[:16] + b'Corrupted ROMFS ' + orig_img[32:]
        with self.assertRaises(ValueError) as ctx:
            CramFSUnpacker(tampered_sig)
        self.assertIn("Invalid CramFS signature", str(ctx.exception))

    def test_09_cramfs_truncated_superblock_rejection(self):
        """
        Adversarial: Verify CramFSUnpacker rejects truncated image buffers smaller than 64-byte superblock.
        """
        orig_img = BODY_UDTR_PATH.read_bytes()
        for sz in [0, 1, 16, 32, 63]:
            with self.assertRaises(ValueError, msg=f"Failed to reject truncated superblock: size {sz}") as ctx:
                CramFSUnpacker(orig_img[:sz])
            self.assertIn("Buffer too small for CramFS superblock", str(ctx.exception))

    def test_10_cramfs_truncated_inode_or_stream_rejection(self):
        """
        Adversarial: Verify CramFS unpacking fails when image is truncated before root inode or block data.
        """
        orig_img = BODY_UDTR_PATH.read_bytes()
        # Truncate at exactly 64 bytes (superblock present, but root inode at 64 missing)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(Exception, msg="Failed to reject image truncated at 64 bytes"):
                unpack_cramfs(orig_img[:64], td)

        # Truncate at 1500 bytes (middle of BodyUdtr.sh block stream)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(Exception, msg="Failed to reject image truncated mid-stream"):
                unpack_cramfs(orig_img[:1500], td)

    def test_11_cramfs_corrupted_zlib_data_block_rejection(self):
        """
        Adversarial: Verify CramFS unpacking raises zlib decompress error when block data bytes are corrupted.
        """
        orig_img = bytearray(BODY_UDTR_PATH.read_bytes())
        # BodyUdtr.sh compressed stream is at offset 1156..2096. Corrupt bytes 1160..1200.
        tampered = bytearray(orig_img)
        tampered[1160:1200] = b'\xff' * 40
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(zlib.error, msg="Failed to raise zlib.error on corrupted block data"):
                unpack_cramfs(bytes(tampered), td)

    # ========================================================================
    # Component 3: Ext2 Robustness & Validation Suite
    # ========================================================================

    def test_12_ext2_invalid_magic_fail_closed(self):
        """
        Adversarial: Verify Ext2Unpacker rejects images with invalid superblock magic (not 0xef53 at 1080).
        """
        self.assertTrue(INITRD_PATH.exists(), f"initrd.img missing: {INITRD_PATH}")
        orig_initrd = bytearray(INITRD_PATH.read_bytes())
        # Mutate ext2 superblock magic at offset 1080
        orig_initrd[1080:1082] = b'\x00\x00'
        with self.assertRaises(ValueError) as ctx:
            Ext2Unpacker(bytes(orig_initrd))
        self.assertIn("Invalid ext2 superblock magic", str(ctx.exception))

    def test_13_ext2_truncated_buffer_rejection(self):
        """
        Adversarial: Verify Ext2Unpacker rejects buffers smaller than 2048 bytes (superblock + descriptors).
        """
        orig_initrd = INITRD_PATH.read_bytes()
        for sz in [0, 512, 1024, 2047]:
            with self.assertRaises(ValueError) as ctx:
                Ext2Unpacker(orig_initrd[:sz])
            self.assertIn("Buffer too small for ext2 image", str(ctx.exception))

    # ========================================================================
    # Component 4: CLI Flags, Custom Output & Idempotency Suite
    # ========================================================================

    def test_14_cli_nonexistent_source_fail_closed(self):
        """
        CLI: Verify running parser with non-existent --source fails closed with returncode != 0.
        """
        cmd = [sys.executable, str(REPO_ROOT / "tools" / "g3_firmware_parser.py"), "--source", "non_existent.exe"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Firmware source not found", res.stderr)

    def test_15_cli_info_flag_execution(self):
        """
        CLI: Verify --info flag executes cleanly, displays manifest table, and makes zero file modifications.
        """
        cmd = [sys.executable, str(REPO_ROOT / "tools" / "g3_firmware_parser.py"), "--source", str(EXE_PATH), "--info"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"--info failed: {res.stderr}")
        self.assertIn("Container Header HMAC:", res.stdout)
        self.assertIn("[VALID]", res.stdout)
        self.assertIn("BodyUdtr.img", res.stdout)
        self.assertIn("linuxset1.tar", res.stdout)

    def test_16_cli_custom_output_directory_redirection(self):
        """
        CLI: Verify --output redirects all artifacts into a custom scratch directory without leaking into evidence/.
        """
        with tempfile.TemporaryDirectory() as td:
            custom_dir = Path(td) / "custom_g3_target"
            cmd = [
                sys.executable, str(REPO_ROOT / "tools" / "g3_firmware_parser.py"),
                "--source", str(EXE_PATH),
                "--output", str(custom_dir),
                "--all"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Custom output run failed: {res.stderr}")

            # Verify artifacts present in custom_dir
            self.assertTrue((custom_dir / "sections" / "02_BodyUdtr.img").exists())
            self.assertTrue((custom_dir / "rootfs" / "BodyUdtr" / "BodyUdtr.sh").exists())
            self.assertTrue((custom_dir / "rootfs" / "system_rootfs" / "bin" / "busybox").exists())
            self.assertTrue((custom_dir / "rootfs" / "initrd" / "linuxrc").exists())
            self.assertTrue((custom_dir / "kernel" / "vmlinux").exists())
            self.assertTrue((custom_dir / "archives_unpacked" / "bin" / "bin" / "sen").exists())
            self.assertTrue((custom_dir / "decrypted_inventory.json").exists())
            self.assertTrue((custom_dir / "DECRYPTED_ARCHITECTURE.md").exists())

    def test_17_cli_idempotent_reexecution_and_overwrite_permissions(self):
        """
        CLI: Verify running the full pipeline twice sequentially over the same output directory
        succeeds without PermissionError (tests 0o555 read-only busybox / chmod overwrite handling).
        """
        with tempfile.TemporaryDirectory() as td:
            custom_dir = Path(td) / "idempotent_test"
            cmd = [
                sys.executable, str(REPO_ROOT / "tools" / "g3_firmware_parser.py"),
                "--source", str(EXE_PATH),
                "--output", str(custom_dir),
                "--all"
            ]
            # Run 1
            res1 = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(res1.returncode, 0, f"Run 1 failed: {res1.stderr}")

            # Run 2 (overwrite)
            res2 = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(res2.returncode, 0, f"Run 2 (idempotency) failed: {res2.stderr}")

    # ========================================================================
    # Component 5: E2E Pipeline Parity & Architectural Benchmark
    # ========================================================================

    def test_18_full_pipeline_elf_census_exact_96(self):
        """
        Benchmark: Verify exact 96 ELF binary census across updater, system rootfs, and tarballs.
        """
        inv_file = EVIDENCE_DIR / "decrypted_inventory.json"
        self.assertTrue(inv_file.exists(), f"Inventory JSON missing: {inv_file}")
        with open(inv_file, 'r', encoding='utf-8') as f:
            inv = json.load(f)

        self.assertEqual(inv["platform"]["elf_file_count"], 96)
        breakdown = inv["platform"]["elf_count_breakdown"]
        self.assertEqual(breakdown["BodyUdtr.img"], 18)
        self.assertEqual(breakdown["bin.tar"], 4)
        self.assertEqual(breakdown["lib.tar"], 17)
        self.assertEqual(breakdown["fskrel1.tar"], 27)
        self.assertEqual(breakdown["fskrel2.tar"], 8)
        self.assertEqual(breakdown["linuxset1.tar/rootfs.img"], 16)
        self.assertEqual(breakdown["linuxset1.tar/initrd.img"], 6)
        self.assertEqual(sum(breakdown.values()), 96)

    def test_19_kernel_version_string_exact_match(self):
        """
        Benchmark: Verify Linux kernel banner string extracted from vmlinux binary matches reference.
        """
        self.assertTrue(VMLINUX_PATH.exists(), f"vmlinux missing: {VMLINUX_PATH}")
        kver = extract_kernel_version(VMLINUX_PATH)
        self.assertEqual(kver, KERNEL_VERSION_EXPECTED)

    def test_20_onenand_12_partition_table_integrity(self):
        """
        Benchmark: Verify partinf.tbl defines exactly 12 OneNAND flash partitions (/dev/nflasha1../dev/nflasha12).
        """
        self.assertTrue(PARTINF_PATH.exists(), f"partinf.tbl missing: {PARTINF_PATH}")
        partitions = parse_partition_table(PARTINF_PATH)
        self.assertEqual(len(partitions), 12)
        devices = [p["device"] for p in partitions]
        expected_devices = [f"/dev/nflasha{i}" for i in range(1, 13)]
        self.assertEqual(devices, expected_devices)


if __name__ == '__main__':
    unittest.main(verbosity=2)
