#!/usr/bin/env python3
"""Comprehensive test suite for Sony DSC-W300 AV coprocessor noise reduction NVRAM tool.

Verifies:
  1. Low-level Category 6 NVRAM buffer inspection, patching, and restoration.
  2. Exact 2-byte modification guarantee (offsets 0x3035 and 0x3036 only).
  3. Preservation of all remaining 16382 bytes in the 16384-byte NVRAM bank.
  4. SHA-256 integrity against authentic D386002E4438 camera factory dumps.
  5. File-level inspection, dry-run, in-place patching, and restoration.
  6. Senser protocol double-read bit-for-bit verification and corruption fail-closed.
  7. Dual-bank synchronization (Asys.bin and Asys2.bak).
  8. Pre-write safety backup creation with cryptographic manifests.
  9. Post-write readback double-read verification.
 10. CLI contracts, safety guardrails (refusal without --experimental-service), and JSON outputs.
 11. Cross-module interfaces in w300_stills_nr.py.

Pure standard library, 100% offline runnable.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

TOOLS_DIR = Path(__file__).resolve().parent
BUILD_W300 = TOOLS_DIR.parent / "build/w300"
for _p in (str(TOOLS_DIR), str(BUILD_W300)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import w300_nr_nvram as nr
import w300_stills_nr as stills_nr
import region_app as app
from region_protocol import ProtocolError, FileUnavailable


class TestNvramBufferPrimitives(unittest.TestCase):
    """Unit tests for low-level byte buffer inspection, patching, and restoration."""

    def setUp(self):
        # Authentic factory dump fixture
        self.stock_path = BUILD_W300 / "backups/calibration_D386002E4438/files/boot/factory/Asys.bin"
        if self.stock_path.is_file():
            self.stock_bytes = self.stock_path.read_bytes()
        else:
            # Synthetic 16384-byte fixture matching W300 Category 6 layout
            buf = bytearray(16384)
            buf[nr.OFFSET_CNR] = nr.VAL_ENABLED
            buf[nr.OFFSET_RGB] = nr.VAL_ENABLED
            self.stock_bytes = bytes(buf)

    def test_stock_bytes_properties(self):
        self.assertEqual(len(self.stock_bytes), nr.ASYS_SIZE)
        self.assertEqual(self.stock_bytes[nr.OFFSET_CNR], nr.VAL_ENABLED)
        self.assertEqual(self.stock_bytes[nr.OFFSET_RGB], nr.VAL_ENABLED)
        if self.stock_path.is_file():
            self.assertEqual(nr.sha256_bytes(self.stock_bytes), nr.STOCK_FACTORY_SHA256)

    def test_inspect_stock_bytes(self):
        info = nr.inspect_nvram_bytes(self.stock_bytes)
        self.assertTrue(info["valid"])
        self.assertEqual(info["size_bytes"], nr.ASYS_SIZE)
        self.assertEqual(info["status"], "enabled")
        self.assertFalse(info["nr_disabled"])
        self.assertEqual(info["cnr_value"], nr.VAL_ENABLED)
        self.assertEqual(info["rgb_value"], nr.VAL_ENABLED)
        if self.stock_path.is_file():
            self.assertTrue(info["is_stock_factory_hash"])
            self.assertFalse(info["is_patched_factory_hash"])

    def test_patch_nvram_bytes_exact_two_bytes(self):
        patched = nr.patch_nvram_bytes(self.stock_bytes)
        self.assertEqual(len(patched), nr.ASYS_SIZE)
        self.assertEqual(patched[nr.OFFSET_CNR], nr.VAL_DISABLED)
        self.assertEqual(patched[nr.OFFSET_RGB], nr.VAL_DISABLED)

        diffs = nr.diff_nvram(self.stock_bytes, patched)
        self.assertEqual(len(diffs), 2)
        diff_offsets = {d["offset"] for d in diffs}
        self.assertEqual(diff_offsets, {nr.OFFSET_CNR, nr.OFFSET_RGB})

        # Verify all remaining 16382 bytes are strictly untouched
        for i in range(nr.ASYS_SIZE):
            if i not in (nr.OFFSET_CNR, nr.OFFSET_RGB):
                self.assertEqual(patched[i], self.stock_bytes[i])

        if self.stock_path.is_file():
            self.assertEqual(nr.sha256_bytes(patched), nr.PATCHED_FACTORY_SHA256)

        info = nr.inspect_nvram_bytes(patched)
        self.assertTrue(info["valid"])
        self.assertEqual(info["status"], "disabled")
        self.assertTrue(info["nr_disabled"])
        if self.stock_path.is_file():
            self.assertTrue(info["is_patched_factory_hash"])

    def test_restore_nvram_bytes_round_trip(self):
        patched = nr.patch_nvram_bytes(self.stock_bytes)
        restored = nr.restore_nvram_bytes(patched)
        self.assertEqual(restored, self.stock_bytes)
        self.assertEqual(nr.sha256_bytes(restored), nr.sha256_bytes(self.stock_bytes))

        info = nr.inspect_nvram_bytes(restored)
        self.assertEqual(info["status"], "enabled")
        self.assertFalse(info["nr_disabled"])

    def test_non_standard_states_inspection(self):
        buf = bytearray(self.stock_bytes)
        # CNR=0, RGB=1
        buf[nr.OFFSET_CNR] = 0x00
        buf[nr.OFFSET_RGB] = 0x01
        info = nr.inspect_nvram_bytes(bytes(buf))
        self.assertEqual(info["status"], "cnr_disabled_rgb_enabled")
        self.assertFalse(info["nr_disabled"])

        # CNR=1, RGB=0
        buf[nr.OFFSET_CNR] = 0x01
        buf[nr.OFFSET_RGB] = 0x00
        info = nr.inspect_nvram_bytes(bytes(buf))
        self.assertEqual(info["status"], "cnr_enabled_rgb_disabled")
        self.assertFalse(info["nr_disabled"])

        # CNR=0x55, RGB=0xaa
        buf[nr.OFFSET_CNR] = 0x55
        buf[nr.OFFSET_RGB] = 0xAA
        info = nr.inspect_nvram_bytes(bytes(buf))
        self.assertIn("non_standard", info["status"])
        self.assertFalse(info["nr_disabled"])

    def test_invalid_buffer_size_handling(self):
        too_small = b"\x00" * 1024
        too_large = b"\x00" * 20000

        for b in (too_small, too_large):
            info = nr.inspect_nvram_bytes(b)
            self.assertFalse(info["valid"])
            self.assertEqual(info["status"], "invalid_size")

            with self.assertRaises(ValueError):
                nr.patch_nvram_bytes(b)
            with self.assertRaises(ValueError):
                nr.restore_nvram_bytes(b)


class TestOfflineFileOperations(unittest.TestCase):
    """Tests for local file inspection, patching, and restoration."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        # Load or generate stock file
        src = BUILD_W300 / "backups/calibration_D386002E4438/files/boot/factory/Asys.bin"
        if src.is_file():
            self.stock_data = src.read_bytes()
        else:
            b = bytearray(16384)
            b[nr.OFFSET_CNR] = 1
            b[nr.OFFSET_RGB] = 1
            self.stock_data = bytes(b)

        self.test_file = self.tmp_path / "Asys.bin"
        self.test_file.write_bytes(self.stock_data)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_inspect_file(self):
        info = nr.inspect_nvram_file(self.test_file)
        self.assertTrue(info["valid"])
        self.assertEqual(info["status"], "enabled")
        self.assertEqual(info["file_path"], str(self.test_file.resolve()))

    def test_patch_file_dry_run_leaves_file_untouched(self):
        orig_sha = nr.sha256_bytes(self.test_file.read_bytes())
        res = nr.patch_nvram_file(self.test_file, dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertFalse(res["written"])
        self.assertEqual(nr.sha256_bytes(self.test_file.read_bytes()), orig_sha)
        self.assertEqual(len(res["byte_changes"]), 2)

    def test_patch_file_separate_output(self):
        out_file = self.tmp_path / "Asys_patched.bin"
        res = nr.patch_nvram_file(self.test_file, out_path=out_file, dry_run=False)
        self.assertTrue(res["written"])
        self.assertTrue(out_file.is_file())
        # Source must be untouched
        self.assertEqual(self.test_file.read_bytes(), self.stock_data)
        # Out must be patched
        out_info = nr.inspect_nvram_file(out_file)
        self.assertTrue(out_info["nr_disabled"])
        self.assertEqual(out_info["status"], "disabled")

    def test_patch_and_restore_file_in_place(self):
        # 1. Patch in place
        res_patch = nr.patch_nvram_file(self.test_file, dry_run=False)
        self.assertTrue(res_patch["written"])
        patched_info = nr.inspect_nvram_file(self.test_file)
        self.assertTrue(patched_info["nr_disabled"])

        # 2. Restore in place
        res_restore = nr.restore_nvram_file(self.test_file, dry_run=False)
        self.assertTrue(res_restore["written"])
        restored_info = nr.inspect_nvram_file(self.test_file)
        self.assertFalse(restored_info["nr_disabled"])
        self.assertEqual(restored_info["status"], "enabled")
        self.assertEqual(self.test_file.read_bytes(), self.stock_data)

    def test_nonexistent_file_raises_not_found(self):
        with self.assertRaises(FileNotFoundError):
            nr.inspect_nvram_file(self.tmp_path / "missing.bin")
        with self.assertRaises(FileNotFoundError):
            nr.patch_nvram_file(self.tmp_path / "missing.bin")
        with self.assertRaises(FileNotFoundError):
            nr.restore_nvram_file(self.tmp_path / "missing.bin")


class TestCameraOperationsAndSafety(unittest.TestCase):
    """Tests for Senser camera interaction, double-read verification, and safety backups."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

        # Set up mock camera with factory files
        src = BUILD_W300 / "backups/calibration_D386002E4438/files/boot/factory/Asys.bin"
        if src.is_file():
            self.stock_data = src.read_bytes()
        else:
            b = bytearray(16384)
            b[nr.OFFSET_CNR] = 1
            b[nr.OFFSET_RGB] = 1
            self.stock_data = bytes(b)

        self.mock_camera = app.MockSenserCamera()
        # Ensure Asys and Asys2.bak are populated with stock data
        self.mock_camera.files[nr.PRIMARY_CAMERA_PATH] = self.stock_data
        self.mock_camera.files[nr.BACKUP_CAMERA_PATH] = self.stock_data
        self.mock_camera.files["/factory/Asys.bin"] = self.stock_data
        self.mock_camera.files["/factory/Asys2.bak"] = self.stock_data

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_double_read_camera_file_success(self):
        data, sha, path = nr.double_read_camera_file(self.mock_camera, nr.PRIMARY_CAMERA_PATH)
        self.assertEqual(len(data), nr.ASYS_SIZE)
        self.assertEqual(sha, nr.sha256_bytes(self.stock_data))
        self.assertEqual(path, nr.PRIMARY_CAMERA_PATH)
        # Verified read_file called twice
        self.assertEqual(self.mock_camera.read_counts[nr.PRIMARY_CAMERA_PATH], 2)

    def test_double_read_corruption_fails_closed(self):
        self.mock_camera.corrupt_on_second.add(nr.PRIMARY_CAMERA_PATH)
        with self.assertRaises(ProtocolError) as ctx:
            nr.double_read_camera_file(self.mock_camera, nr.PRIMARY_CAMERA_PATH)
        self.assertIn("discrepancy", str(ctx.exception))

    def test_double_read_missing_file_raises_unavailable(self):
        with self.assertRaises(FileUnavailable):
            nr.double_read_camera_file(self.mock_camera, "/boot/factory/nonexistent.bin")

    def test_inspect_camera(self):
        info = nr.inspect_camera(self.mock_camera)
        self.assertTrue(info["banks_in_sync"])
        self.assertFalse(info["nr_disabled"])
        self.assertEqual(info["status"], "enabled")
        self.assertEqual(info["primary"]["cnr_value"], 1)
        self.assertEqual(info["primary"]["rgb_value"], 1)

    def test_patch_camera_dry_run_leaves_camera_unmodified(self):
        res = nr.patch_camera(self.mock_camera, dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertFalse(res["written"])
        self.assertEqual(self.mock_camera.files[nr.PRIMARY_CAMERA_PATH], self.stock_data)
        self.assertEqual(self.mock_camera.files[nr.BACKUP_CAMERA_PATH], self.stock_data)

    def test_patch_camera_full_cycle_with_backup_and_readback(self):
        backup_dir = self.tmp_path / "test_backup"
        res = nr.patch_camera(self.mock_camera, backup_dir=backup_dir, dry_run=False)

        self.assertTrue(res["written"])
        self.assertTrue(res["verified_readback"])
        self.assertTrue(res["banks_in_sync"])
        self.assertTrue(res["nr_disabled"])
        self.assertEqual(res["status"], "SUCCESS")

        # Verify safety backup files were created on disk
        self.assertTrue((backup_dir / "Asys.bin").is_file())
        self.assertTrue((backup_dir / "Asys2.bak").is_file())
        self.assertTrue((backup_dir / "manifest.json").is_file())
        self.assertEqual((backup_dir / "Asys.bin").read_bytes(), self.stock_data)

        # Verify camera files are now patched and both banks match
        prim_after = self.mock_camera.files[nr.PRIMARY_CAMERA_PATH]
        bak_after = self.mock_camera.files[nr.BACKUP_CAMERA_PATH]
        self.assertEqual(prim_after, bak_after)
        self.assertEqual(prim_after[nr.OFFSET_CNR], 0x00)
        self.assertEqual(prim_after[nr.OFFSET_RGB], 0x00)

        # Post-patch camera inspection
        insp = nr.inspect_camera(self.mock_camera)
        self.assertTrue(insp["nr_disabled"])
        self.assertEqual(insp["status"], "disabled")
        self.assertTrue(insp["banks_in_sync"])

    def test_restore_camera_cycle(self):
        # First patch
        nr.patch_camera(self.mock_camera, dry_run=False)
        self.assertTrue(nr.inspect_camera(self.mock_camera)["nr_disabled"])

        # Then restore
        backup_dir = self.tmp_path / "prerestore_backup"
        res = nr.restore_camera(self.mock_camera, backup_dir=backup_dir, dry_run=False)
        self.assertTrue(res["written"])
        self.assertTrue(res["verified_readback"])
        self.assertFalse(res["nr_disabled"])

        # Check camera state restored to stock 0x01
        insp = nr.inspect_camera(self.mock_camera)
        self.assertFalse(insp["nr_disabled"])
        self.assertEqual(insp["status"], "enabled")
        self.assertEqual(insp["primary"]["cnr_value"], 0x01)
        self.assertEqual(insp["primary"]["rgb_value"], 0x01)
        self.assertEqual(self.mock_camera.files[nr.PRIMARY_CAMERA_PATH], self.stock_data)

    def test_restore_camera_from_backup_directory(self):
        # Create a backup dir with stock data
        saved_dir = self.tmp_path / "manual_backup"
        saved_dir.mkdir(parents=True)
        (saved_dir / "Asys.bin").write_bytes(self.stock_data)
        (saved_dir / "Asys2.bak").write_bytes(self.stock_data)

        # Patch camera
        nr.patch_camera(self.mock_camera, dry_run=False)
        self.assertTrue(nr.inspect_camera(self.mock_camera)["nr_disabled"])

        # Restore from saved dir
        res = nr.restore_camera(self.mock_camera, restore_from_dir=saved_dir, dry_run=False)
        self.assertTrue(res["written"])
        self.assertEqual(self.mock_camera.files[nr.PRIMARY_CAMERA_PATH], self.stock_data)


class TestCliAndSafetyContracts(unittest.TestCase):
    """Tests for CLI arguments, exit codes, and safety enforcement."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.test_file = self.tmp_path / "Asys.bin"
        b = bytearray(16384)
        b[nr.OFFSET_CNR] = 1
        b[nr.OFFSET_RGB] = 1
        self.test_file.write_bytes(bytes(b))

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_safety_guardrail_refuses_live_camera_write_without_flag(self):
        # Attempting live camera patch without --mock, --dry-run, or --experimental-service
        with self.assertRaises(PermissionError):
            nr.run_nr_tool("patch", target="camera", mock=False, dry_run=False, experimental_service=False)

        # CLI must exit with code 2 on safety refusal
        with contextlib.redirect_stderr(io.StringIO()):
            code = nr.main(["disable-nr", "--camera"])
            self.assertEqual(code, 2, "Live camera write without safety flag must exit with code 2")

    def test_cli_inspect_file_json(self):
        stdout_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            code = nr.main(["inspect", "--file", str(self.test_file), "--json"])
            self.assertEqual(code, 0)
        parsed = json.loads(stdout_buf.getvalue())
        self.assertTrue(parsed["valid"])
        self.assertEqual(parsed["status"], "enabled")

    def test_cli_patch_file_dry_run(self):
        stdout_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            code = nr.main(["disable-nr", "--file", str(self.test_file), "--dry-run", "--json"])
            self.assertEqual(code, 0)
        parsed = json.loads(stdout_buf.getvalue())
        self.assertTrue(parsed["dry_run"])
        self.assertFalse(parsed["written"])
        self.assertEqual(len(parsed["byte_changes"]), 2)

    def test_cli_mock_camera_inspect_and_patch(self):
        # 1. Mock inspect
        stdout_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            code = nr.main(["inspect", "--camera", "--mock", "--json"])
            self.assertEqual(code, 0)
        insp = json.loads(stdout_buf.getvalue())
        self.assertEqual(insp["operation"], "inspect_camera")

        # 2. Mock patch
        stdout_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            code = nr.main(["disable-nr", "--camera", "--mock", "--json"])
            self.assertEqual(code, 0)
        patch_res = json.loads(stdout_buf.getvalue())
        self.assertEqual(patch_res["status"], "SUCCESS")
        self.assertTrue(patch_res["written"])
        self.assertTrue(patch_res["verified_readback"])

        # 3. Mock restore
        stdout_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            code = nr.main(["enable-nr", "--camera", "--mock", "--json"])
            self.assertEqual(code, 0)
        restore_res = json.loads(stdout_buf.getvalue())
        self.assertEqual(restore_res["status"], "SUCCESS")
        self.assertTrue(restore_res["written"])

    def test_stills_nr_module_forwarding_and_cli(self):
        # Test function exports
        patched_bytes = stills_nr.patch_w300_stills_nr(self.test_file.read_bytes())
        self.assertEqual(patched_bytes[nr.OFFSET_CNR], 0x00)
        self.assertEqual(patched_bytes[nr.OFFSET_RGB], 0x00)

        restored_bytes = stills_nr.restore_w300_stills_nr(patched_bytes)
        self.assertEqual(restored_bytes[nr.OFFSET_CNR], 0x01)
        self.assertEqual(restored_bytes[nr.OFFSET_RGB], 0x01)

        # Test stills_nr CLI patch-nvram and inspect-nvram
        stdout_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            code = stills_nr.main(["inspect-nvram", "--file", str(self.test_file)])
            self.assertEqual(code, 0)
        parsed = json.loads(stdout_buf.getvalue())
        self.assertEqual(parsed["status"], "enabled")


if __name__ == "__main__":
    unittest.main()
