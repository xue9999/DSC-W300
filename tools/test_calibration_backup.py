"""Automated tests for DSC-W300 CCD calibration and configuration safety dump.

Verifies:
  1. CALIBRATION_TARGETS completeness (Areg, Areg2, Hreg, Preg, initreg, Asys, Hsys, etc.).
  2. Double-read SHA-256 verification (bit-for-bit identical repeat read contract).
  3. Transfer corruption detection (fails closed, writes .second forensic file).
  4. Graceful handling of unavailable files (status 0x82 FileUnavailable).
  5. Fallback path resolution for partition mounts (/factory/ vs /boot/factory/).
  6. CLI invocation, safety guardrail enforcement, and transaction logging.
  7. Fail-closed behavior when physical camera is absent.

100% offline, pure Python standard library. Zero external dependencies.
"""

from pathlib import Path
import contextlib
import io
import json
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

BUILD_W300 = Path(__file__).resolve().parents[1] / 'build/w300'
if str(BUILD_W300) not in sys.path:
    sys.path.insert(0, str(BUILD_W300))

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import region_app as app
import region_protocol as protocol
import w300_calibration_dump as dump_tool
import verify_dump as verify_tool


class TestCalibrationTargets(unittest.TestCase):
    """Verifies that all required calibration and configuration files are registered."""

    def test_all_critical_calibration_targets_present(self):
        targets = set(app.CALIBRATION_TARGETS)
        required = {
            '/boot/factory/Areg.bin',
            '/boot/factory/Areg2.bak',
            '/boot/factory/Hreg.bin',
            '/boot/factory/Hreg2.bak',
            '/boot/factory/Preg.bin',
            '/boot/factory/initreg.bin',
            '/boot/factory/Asys.bin',
            '/boot/factory/Asys2.bak',
            '/boot/factory/Hsys.bin',
            '/boot/factory/Hsys2.bak',
            '/boot/backup/Ausr.bin',
            '/boot/backup/Ausr2.bak',
            '/boot/backup/Husr.bin',
            '/boot/backup/Husr2.bak',
            '/boot/factory/brew_cnf.bin',
            '/boot/dsc/RegionInfo.xml',
            '/boot/dsc/UserInfo.xml',
            '/boot/dsc/UserInfo.bak',
            '/version.txt',
        }
        missing = required - targets
        self.assertEqual(missing, set(), f"Missing required targets in CALIBRATION_TARGETS: {missing}")

    def test_fallback_aliases_coverage(self):
        for primary, fallback in app.FALLBACK_ALIASES.items():
            self.assertTrue(primary.startswith('/boot/'))
            self.assertFalse(fallback.startswith('/boot/'))
            self.assertEqual(primary.replace('/boot', ''), fallback)


class TestDoubleReadVerification(unittest.TestCase):
    """Tests the bit-for-bit double read verification contract."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_mock_camera_double_read_sha256_pass(self):
        camera = app.MockSenserCamera()
        records = []
        app.store_read_with_fallback(camera, self.output_dir, '/boot/factory/Areg.bin', records)

        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertTrue(rec.get('repeat_equal'), "First and second reads must be bit-for-bit equal")
        self.assertEqual(rec['sha256'], rec['second_sha256'], "SHA-256 digests of both reads must match")
        self.assertGreater(rec['bytes'], 0)
        self.assertEqual(camera.read_counts.get('/boot/factory/Areg.bin'), 2,
                         "Camera read_file must be called exactly twice for double-read verification")

        saved_file = self.output_dir / rec['file']
        self.assertTrue(saved_file.is_file())
        self.assertEqual(app.sha(saved_file.read_bytes()), rec['sha256'])

    def test_double_read_corruption_fails_closed(self):
        camera = app.MockSenserCamera()
        camera.corrupt_on_second.add('/boot/factory/Areg.bin')
        records = []

        with self.assertRaises(protocol.ProtocolError) as ctx:
            app.store_read_with_fallback(camera, self.output_dir, '/boot/factory/Areg.bin', records)

        self.assertIn('Repeat read changed', str(ctx.exception))
        # The corrupted second read must be preserved as .second for forensic triage
        primary_file = self.output_dir / 'files/boot/factory/Areg.bin'
        second_file = self.output_dir / 'files/boot/factory/Areg.bin.second'
        self.assertTrue(primary_file.is_file())
        self.assertTrue(second_file.is_file(), "Forensic .second artifact must be created on discrepancy")
        self.assertNotEqual(primary_file.read_bytes(), second_file.read_bytes())

    def test_fallback_alias_resolution(self):
        camera = app.MockSenserCamera()
        # Remove primary /boot/factory/initreg.bin to force fallback to /factory/initreg.bin
        if '/boot/factory/initreg.bin' in camera.files:
            del camera.files['/boot/factory/initreg.bin']
        self.assertIn('/factory/initreg.bin', camera.files)

        records = []
        app.store_read_with_fallback(camera, self.output_dir, '/boot/factory/initreg.bin', records)
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertTrue(rec.get('repeat_equal'))
        self.assertEqual(rec.get('resolved_path'), '/factory/initreg.bin')
        self.assertTrue((self.output_dir / rec['file']).is_file())

    def test_unavailable_file_recorded_without_abort(self):
        camera = app.MockSenserCamera()
        # Non-existent file
        records = []
        app.store_read_with_fallback(camera, self.output_dir, '/boot/factory/nonexistent.bin', records)
        self.assertEqual(len(records), 1)
        self.assertIn('unavailable', records[0])
        self.assertNotIn('file', records[0])


class TestBackupCalibrationEndToEnd(unittest.TestCase):
    """End-to-end tests for the backup_calibration routine and CLI."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_nr_acquisition_preserves_sources_and_reports_unavailable_without_absence_claim(self):
        camera = app.MockSenserCamera()
        camera.files['/usr/lib/libusb.so'] = b'synthetic USB library fixture'
        camera.files.pop('/usr/lib/libadj11.so', None)
        originals = dict(camera.files)
        args = SimpleNamespace(mock=True, serial='D386002E4438', include_nr_implementation=True)
        report = dict(ok=False)
        with patch.object(app, 'MockSenserCamera', return_value=camera):
            app.backup_calibration(args, self.output_dir, None, report)
        summary = report['nr_implementation']
        self.assertFalse(summary['all_requested_files_verified'])
        self.assertFalse(summary['installation_absence_proven'])
        self.assertFalse(summary['live_nr_write_qualified'])
        self.assertEqual(summary['unavailable_or_inaccessible_paths'], ['/usr/lib/libadj11.so'])
        self.assertEqual(camera.write_counts, {})
        self.assertEqual(camera.files, originals)
        self.assertEqual(set(row['camera_path'] for row in report['files']),
                         set(app.CALIBRATION_TARGETS) | set(app.NR_IMPLEMENTATION))
        for path in summary['verified_paths']:
            self.assertEqual(camera.read_counts[path], 2)
            self.assertEqual((self.output_dir / 'files' / path.lstrip('/')).read_bytes(), originals[path])
        with self.assertRaises(FileExistsError):
            app.backup_calibration(args, self.output_dir, None, {})

    def test_nr_library_repeat_corruption_is_fatal_and_retained(self):
        camera = app.MockSenserCamera()
        path = '/usr/lib/libadj11.so'
        camera.files[path] = b'synthetic plugin fixture'
        camera.corrupt_on_second.add(path)
        args = SimpleNamespace(mock=True, serial='D386002E4438', include_nr_implementation=True)
        report = dict(ok=False)
        with patch.object(app, 'MockSenserCamera', return_value=camera):
            with self.assertRaises(protocol.ProtocolError):
                app.backup_calibration(args, self.output_dir, None, report)
        self.assertFalse(report['ok'])
        self.assertEqual(camera.write_counts, {})
        saved = self.output_dir / 'files/usr/lib/libadj11.so'
        self.assertEqual(saved.read_bytes(), camera.files[path])
        self.assertTrue(saved.with_name(saved.name + '.second').is_file())

    def test_nr_capture_cli_refuses_existing_directory_before_usb(self):
        argv = ['region_app.py', 'backup-calibration', '--experimental-service',
                '--include-nr-implementation', '--output', str(self.output_dir)]
        marker = self.output_dir / 'existing.txt'
        marker.write_text('preserve', encoding='utf-8')
        with patch.object(sys, 'argv', argv), patch.object(app, 'usb_modules') as usb:
            with self.assertRaises(SystemExit) as raised:
                app.main()
        self.assertEqual(raised.exception.code, 2)
        usb.assert_not_called()
        self.assertEqual(marker.read_text(encoding='utf-8'), 'preserve')

    def test_full_backup_calibration_mock_success(self):
        class DummyArgs:
            command = 'backup-calibration'
            serial = 'D386002E4438'
            experimental_service = True
            output = self.output_dir
            resume_session = None
            mock = True
            include_implementation = False

        trace = app.Trace(self.output_dir)
        report = dict(operation='backup-calibration', serial='D386002E4438', ok=False)
        try:
            app.backup_calibration(DummyArgs(), self.output_dir, trace, report)
        finally:
            trace.close()

        self.assertTrue(report['ok'])
        summary = report['summary']
        self.assertTrue(summary['double_read_sha256_verified'])
        self.assertTrue(summary['calibration_ccd_areg_saved'])
        self.assertTrue(summary['calibration_ccd_areg2_saved'])
        self.assertTrue(summary['host_hreg_saved'])
        self.assertTrue(summary['host_hreg2_saved'])
        self.assertTrue(summary['anti_tamper_preg_saved'])
        self.assertTrue(summary['partition_initreg_saved'])
        self.assertGreater(summary['files_saved'], 0)
        self.assertGreater(summary['total_bytes'], 0)

        # Check manifest.json and result.json
        manifest_path = self.output_dir / 'manifest.json'
        result_path = self.output_dir / 'result.json'
        self.assertTrue(manifest_path.is_file())
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(manifest['double_read_sha256_verified'], True)
        self.assertEqual(manifest['calibration_ccd_areg_saved'], True)

        # Verify CCD calibration files on disk
        areg_path = self.output_dir / 'files/boot/factory/Areg.bin'
        areg2_path = self.output_dir / 'files/boot/factory/Areg2.bak'
        preg_path = self.output_dir / 'files/boot/factory/Preg.bin'
        hreg_path = self.output_dir / 'files/boot/factory/Hreg.bin'
        self.assertTrue(areg_path.is_file())
        self.assertTrue(areg2_path.is_file())
        self.assertTrue(preg_path.is_file())
        self.assertTrue(hreg_path.is_file())

    def test_cli_requires_experimental_service_flag(self):
        old_argv = sys.argv
        try:
            sys.argv = ['region_app.py', 'backup-calibration', '--serial', 'D386002E4438', '--mock']
            with self.assertRaises(SystemExit) as ctx:
                app.main()
            self.assertNotEqual(ctx.exception.code, 0)
        finally:
            sys.argv = old_argv

    def test_cli_mock_full_invocation(self):
        old_argv = sys.argv
        target = self.output_dir / 'cli_backup_ą'
        captured = io.BytesIO()
        legacy_stdout = io.TextIOWrapper(captured, encoding='cp1252', errors='strict')
        try:
            sys.argv = ['region_app.py', 'backup-calibration', '--serial', 'D386002E4438',
                        '--experimental-service', '--mock', '--output', str(target)]
            with contextlib.redirect_stdout(legacy_stdout):
                code = app.main()
            legacy_stdout.flush()
            self.assertEqual(code, 0)
            self.assertIn(b'cli_backup_\\u0105', captured.getvalue())
            self.assertTrue((target / 'manifest.json').is_file())
            self.assertTrue((target / 'result.json').is_file())
            self.assertTrue((target / 'files/boot/factory/Areg.bin').is_file())
        finally:
            sys.argv = old_argv

    def test_live_fail_closed_when_camera_disconnected(self):
        """Without --mock, if camera is disconnected, must fail closed with non-zero exit."""
        class DummyArgs:
            command = 'backup-calibration'
            serial = 'D386002E4438'
            experimental_service = True
            output = self.output_dir / 'disconnected'
            resume_session = None
            mock = False
            include_implementation = False

        trace = app.Trace(self.output_dir)
        report = dict(operation='backup-calibration', serial='D386002E4438', ok=False)
        try:
            # Isolate discovery from optional authentication sources and USB packages.
            with patch.object(app, 'load_auth', return_value=(None, None)), \
                    patch.object(app, 'usb_modules', return_value=(None, None, None)), \
                    patch.object(app, 'find_one', side_effect=ValueError('No Sony camera in normal USB mode')) as find:
                with self.assertRaisesRegex(ValueError, 'No Sony camera'):
                    app.backup_calibration(DummyArgs(), self.output_dir, trace, report)
                find.assert_called_once_with(None, None, app.NORMAL_PIDS)
        finally:
            trace.close()
        self.assertFalse(report.get('ok', False), "Disconnected live camera must fail closed")

    def test_manifest_contains_cryptographic_file_manifest(self):
        old_argv = sys.argv
        target = self.output_dir / 'manifest_test'
        try:
            sys.argv = ['region_app.py', 'backup-calibration', '--serial', 'D386002E4438',
                        '--experimental-service', '--mock', '--output', str(target)]
            code = app.main()
            self.assertEqual(code, 0)
            manifest_path = target / 'manifest.json'
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            self.assertIn('file_manifest', manifest)
            file_manifest = manifest['file_manifest']
            self.assertGreaterEqual(len(file_manifest), 19)
            for row in file_manifest:
                self.assertIn('camera_path', row)
                self.assertIn('file', row)
                self.assertIn('bytes', row)
                self.assertIn('sha256', row)
                saved_bytes = (target / row['file']).read_bytes()
                self.assertEqual(len(saved_bytes), row['bytes'])
                self.assertEqual(app.sha(saved_bytes), row['sha256'])
        finally:
            sys.argv = old_argv

    def test_missing_critical_areg_fails_closed(self):
        mock_files = app.get_mock_calibration_files()
        mock_files.pop('/boot/factory/Areg.bin', None)
        mock_files.pop('/factory/Areg.bin', None)
        mock_files.pop('/boot/factory/Areg2.bak', None)
        mock_files.pop('/factory/Areg2.bak', None)

        orig_cam = app.MockSenserCamera
        app.MockSenserCamera = lambda files=None: orig_cam(files=mock_files)
        old_argv = sys.argv
        target = self.output_dir / 'missing_areg'
        try:
            sys.argv = ['region_app.py', 'backup-calibration', '--serial', 'D386002E4438',
                        '--experimental-service', '--mock', '--output', str(target)]
            code = app.main()
            self.assertEqual(code, 2, "Missing critical CCD calibration must fail closed with exit code 2")
            result_path = target / 'result.json'
            self.assertTrue(result_path.is_file())
            result = json.loads(result_path.read_text(encoding='utf-8'))
            self.assertFalse(result.get('ok'))
            self.assertIn('Critical CCD calibration', result.get('error', ''))
        finally:
            app.MockSenserCamera = orig_cam
            sys.argv = old_argv

    def test_missing_normal_mode_return_fails_closed(self):
        no_exit_dir = self.output_dir / 'no_exit'
        no_exit_dir.mkdir(parents=True, exist_ok=True)
        class DummyArgs:
            command = 'backup-calibration'
            serial = 'D386002E4438'
            experimental_service = True
            output = no_exit_dir
            resume_session = None
            mock = False
            include_implementation = False

        trace = app.Trace(no_exit_dir)
        report = dict(operation='backup-calibration', serial='D386002E4438', ok=False)
        # Mock session to yield a camera but simulate exit re-enumeration failure (normal_mode_return_observed = False)
        @contextlib.contextmanager
        def fake_failing_session(serial, tr, rep, resume=None):
            rep['normal_mode_return_observed'] = False
            yield app.MockSenserCamera()

        orig_session = app.session
        app.session = fake_failing_session
        try:
            with self.assertRaises(RuntimeError) as ctx:
                app.backup_calibration(DummyArgs(), no_exit_dir, trace, report)
            self.assertIn('Normal-mode return not observed', str(ctx.exception))
            self.assertFalse(report.get('ok', False))
        finally:
            app.session = orig_session
            trace.close()

    def test_invalid_resume_session_rejected(self):
        bad_resume_file = self.output_dir / 'bad_resume.json'
        bad_resume_file.write_text(json.dumps({
            'operation': 'capture',
            'serial': 'DIFFERENT_SERIAL',
            'normal_mode_return_observed': False,
            'identity': {'model': 'DSC-W300', 'serial': 'DIFFERENT_SERIAL', 'bus': 2, 'ports': [1]}
        }), encoding='utf-8')

        old_argv = sys.argv
        target = self.output_dir / 'resume_test'
        try:
            sys.argv = ['region_app.py', 'backup-calibration', '--serial', 'D386002E4438',
                        '--experimental-service', '--resume-session', str(bad_resume_file),
                        '--output', str(target)]
            code = app.main()
            self.assertEqual(code, 2, "Mismatched resume session must fail closed with exit code 2")
        finally:
            sys.argv = old_argv

    def test_mock_include_implementation(self):
        old_argv = sys.argv
        target = self.output_dir / 'implementation_backup'
        try:
            sys.argv = ['region_app.py', 'backup-calibration', '--serial', 'D386002E4438',
                        '--experimental-service', '--mock', '--include-implementation',
                        '--output', str(target)]
            code = app.main()
            self.assertEqual(code, 0)
            manifest = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
            self.assertGreater(manifest['files_saved'], 19,
                               "Implementation files must be saved when --include-implementation is set")
            # Verify critical implementation binaries saved
            self.assertTrue((target / 'files/usr/lib/libBackupCore.so').is_file())
            self.assertTrue((target / 'files/usr/bin/sen').is_file())
        finally:
            sys.argv = old_argv

    def test_double_read_divergence_cli_fails_closed(self):
        orig_cam = app.MockSenserCamera
        def corrupting_camera(files=None):
            cam = orig_cam(files=files)
            cam.corrupt_on_second.add('/boot/factory/Areg.bin')
            return cam

        app.MockSenserCamera = corrupting_camera
        old_argv = sys.argv
        target = self.output_dir / 'corrupt_cli'
        try:
            sys.argv = ['region_app.py', 'backup-calibration', '--serial', 'D386002E4438',
                        '--experimental-service', '--mock', '--output', str(target)]
            code = app.main()
            self.assertEqual(code, 2, "Data divergence during double-read must exit with code 2")
            result = json.loads((target / 'result.json').read_text(encoding='utf-8'))
            self.assertFalse(result.get('ok'))
            self.assertIn('Repeat read changed', result.get('error', ''))
            # Forensic artifact .second must exist
            self.assertTrue((target / 'files/boot/factory/Areg.bin.second').is_file())
        finally:
            app.MockSenserCamera = orig_cam
            sys.argv = old_argv

    def test_standalone_tool_mock_invocation(self):
        old_argv = sys.argv
        target = self.output_dir / 'standalone_backup'
        try:
            sys.argv = ['w300_calibration_dump.py', '--serial', 'D386002E4438',
                        '--experimental-service', '--mock', '--output', str(target)]
            code = dump_tool.main()
            self.assertEqual(code, 0)
            self.assertTrue((target / 'manifest.json').is_file())
            self.assertTrue((target / 'result.json').is_file())
            self.assertTrue((target / 'files/boot/factory/Areg.bin').is_file())
        finally:
            sys.argv = old_argv

    def test_standalone_tool_mock_invocation_auto_serial(self):
        """When --serial is omitted, tool should auto-default serial cleanly in mock mode."""
        old_argv = sys.argv
        target = self.output_dir / 'standalone_auto_serial'
        try:
            sys.argv = ['w300_calibration_dump.py',
                        '--experimental-service', '--mock', '--output', str(target)]
            code = dump_tool.main()
            self.assertEqual(code, 0)
            self.assertTrue((target / 'manifest.json').is_file())
            result = json.loads((target / 'result.json').read_text(encoding='utf-8'))
            self.assertTrue(result.get('ok'))
            self.assertEqual(result.get('serial'), 'D386002E4438')
        finally:
            sys.argv = old_argv

    def test_cli_mock_invocation_auto_serial(self):
        """When --serial is omitted in region_app.py backup-calibration, default is resolved."""
        old_argv = sys.argv
        target = self.output_dir / 'cli_auto_serial'
        try:
            sys.argv = ['region_app.py', 'backup-calibration',
                        '--experimental-service', '--mock', '--output', str(target)]
            code = app.main()
            self.assertEqual(code, 0)
            self.assertTrue((target / 'manifest.json').is_file())
            result = json.loads((target / 'result.json').read_text(encoding='utf-8'))
            self.assertTrue(result.get('ok'))
            self.assertEqual(result.get('serial'), 'D386002E4438')
        finally:
            sys.argv = old_argv

    def test_standalone_tool_missing_experimental_flag(self):
        old_argv = sys.argv
        try:
            sys.argv = ['w300_calibration_dump.py', '--serial', 'D386002E4438', '--mock']
            with self.assertRaises(SystemExit) as ctx:
                dump_tool.main()
            self.assertNotEqual(ctx.exception.code, 0)
        finally:
            sys.argv = old_argv


class TestVerifyDumpTool(unittest.TestCase):
    """Tests for the verify_dump verification tool."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backup_dir = Path(self.temp_dir.name) / 'calibration_test'
        old_argv = sys.argv
        try:
            sys.argv = ['region_app.py', 'backup-calibration',
                        '--experimental-service', '--mock', '--output', str(self.backup_dir)]
            code = app.main()
            self.assertEqual(code, 0)
        finally:
            sys.argv = old_argv

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_verify_dump_pass_on_valid_backup(self):
        ok, details = verify_tool.verify_dump(self.backup_dir)
        self.assertTrue(ok, f"Verification failed with errors: {details.get('errors')}")
        self.assertEqual(details['errors'], [])
        self.assertGreaterEqual(details['verified_files_count'], 19)

    def test_verify_dump_fails_on_corrupted_file(self):
        areg = self.backup_dir / 'files/boot/factory/Areg.bin'
        data = bytearray(areg.read_bytes())
        data[0] ^= 0xFF
        areg.write_bytes(bytes(data))

        ok, details = verify_tool.verify_dump(self.backup_dir)
        self.assertFalse(ok)
        self.assertTrue(any('SHA-256 mismatch' in err for err in details['errors']))

    def test_verify_dump_fails_on_mirror_mismatch(self):
        areg2 = self.backup_dir / 'files/boot/factory/Areg2.bak'
        data = bytearray(areg2.read_bytes())
        data[4] ^= 0x55
        areg2.write_bytes(bytes(data))

        ok, details = verify_tool.verify_dump(self.backup_dir)
        self.assertFalse(ok)
        self.assertTrue(any('Mirror pair discrepancy' in err for err in details['errors']))

    def test_verify_dump_fails_on_missing_manifest(self):
        (self.backup_dir / 'manifest.json').unlink()
        ok, details = verify_tool.verify_dump(self.backup_dir)
        self.assertFalse(ok)
        self.assertTrue(any('Missing manifest.json' in err for err in details['errors']))


if __name__ == '__main__':
    unittest.main()
