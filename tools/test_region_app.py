"""Offline protocol adversarial checks. These do not qualify camera compatibility."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build/w300'))
import region_protocol as protocol
import region_app as app


class FakeIO:
    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []
    def read(self, size, timeout):
        if not self.replies:
            raise TimeoutError('No fixture response')
        data = self.replies.pop(0)
        if isinstance(data, Exception):
            raise data
        return data
    def write(self, data, timeout):
        self.sent.append(data)


def header(size, sequence=1, function=0xff01, status=1):
    return protocol.HEADER.pack(size, function, sequence, 0, 0, 0, status)


class TransferTests(unittest.TestCase):
    def test_read_request_and_body(self):
        fake = FakeIO([header(3), b'a', b'bc'])
        self.assertEqual(protocol.Senser(fake).read_file('/version.txt'), b'abc')
        self.assertEqual(fake.sent[0], bytes.fromhex(
            '1400000001ff010000000000020010002f76657273696f6e2e74787400000000'))

    def test_zero_and_missing_are_different(self):
        fake = FakeIO([header(0), header(0, sequence=2, status=0x82)])
        camera = protocol.Senser(fake)
        self.assertEqual(camera.read_file('/empty'), b'')
        with self.assertRaises(protocol.FileUnavailable):
            camera.read_file('/missing')
        self.assertEqual(camera.sequence, 3)
        self.assertFalse(camera.failed)

    def test_bad_frames_stop_session(self):
        fixtures = ([b''], [header(2), b''], [header(2), b'abc'],
                    [header(1, sequence=2)], [header(1, function=0x40)],
                    [header(20)], [header(1, status=0x82)],
                    [header(0, status=2)], [b'X' * 13])
        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                fake = FakeIO(fixture)
                camera = protocol.Senser(fake)
                with self.assertRaises(protocol.ProtocolError):
                    camera.read_file('/test', limit=10)
                before = len(fake.sent)
                with self.assertRaises(protocol.ProtocolError):
                    camera.read_file('/test')
                self.assertEqual(len(fake.sent), before)

    def test_padding_is_empty_only(self):
        for padding in (b'next header', TimeoutError('No ZLP')):
            with self.subTest(padding=padding):
                camera = protocol.Senser(FakeIO([header(512), bytes(512), padding]))
                with self.assertRaises((protocol.ProtocolError, TimeoutError)):
                    camera.read_file('/file')
        camera = protocol.Senser(FakeIO([header(512), bytes(512), b'']))
        self.assertEqual(camera.read_file('/file'), bytes(512))

    def test_segment_remaining(self):
        replies = [header(protocol.SEGMENT + 1)]
        for _ in range(protocol.SEGMENT // protocol.CHUNK):
            replies.extend([bytes(protocol.CHUNK), b''])
        replies.extend([header(1), b'Z'])
        self.assertEqual(protocol.Senser(FakeIO(replies)).read_file('/file'), bytes(protocol.SEGMENT) + b'Z')
        replies[-2] = header(2)
        with self.assertRaises(protocol.ProtocolError):
            protocol.Senser(FakeIO(replies)).read_file('/file')

    def test_deadline_and_bad_path_send_nothing(self):
        fake = FakeIO([])
        camera = protocol.Senser(fake, deadline=1, clock=lambda: 0)
        camera.clock = lambda: 2
        with self.assertRaises(protocol.ProtocolError):
            camera.read_file('/file')
        self.assertEqual(fake.sent, [])
        for path in ('relative', '/a/../b', '/a\0b'):
            with self.assertRaises(ValueError):
                protocol.Senser(fake).read_file(path)

    def test_region_outcome_not_retried(self):
        fake = FakeIO([TimeoutError('Disconnected after write')])
        camera = protocol.Senser(fake)
        with self.assertRaises(TimeoutError):
            camera.change_region(0)
        with self.assertRaises(protocol.ProtocolError):
            camera.change_region(0)
        self.assertEqual(len(fake.sent), 1)
        fake = FakeIO([header(0, function=0x40, status=0)])
        protocol.Senser(fake).change_region(1)
        self.assertEqual(fake.sent[0][-4:], b'\x01\0\0\0')

    def test_write_request_and_body(self):
        fake = FakeIO([header(0, sequence=1, function=0xff01, status=1)])
        camera = protocol.Senser(fake)
        path = '/boot/factory/Preg.bin'
        data = b'P' * 1040
        size = camera.write_file(path, data)
        self.assertEqual(size, 0)
        self.assertEqual(camera.sequence, 2)
        sent = fake.sent[0]
        # HEADER is 12 bytes: size (1068), func 0xff01, seq 1, 0, 0, 0, 0
        # Padded path length: '/boot/factory/Preg.bin' is 22 bytes, padded to 24 bytes with 2 nulls.
        # Body: 4 bytes (<HH 1, 24) + 24 bytes path + 1040 bytes data = 1068 bytes.
        # Total sent: 12 + 1068 = 1080 bytes.
        self.assertEqual(len(sent), 12 + 4 + 24 + 1040)
        hdr = protocol.HEADER.unpack(sent[:12])
        self.assertEqual(hdr, (1068, 0xff01, 1, 0, 0, 0, 0))
        cmd, path_len = struct.unpack('<HH', sent[12:16])
        self.assertEqual(cmd, 1)
        self.assertEqual(path_len, 24)
        self.assertEqual(sent[16:40], b'/boot/factory/Preg.bin\x00\x00')
        self.assertEqual(sent[40:], data)

    def test_write_error_handling(self):
        fake = FakeIO([header(0, sequence=1, function=0xff01, status=0)])
        camera = protocol.Senser(fake)
        with self.assertRaises(protocol.ProtocolError):
            camera.write_file('/test', b'data')
        self.assertTrue(camera.failed)
        with self.assertRaises(protocol.ProtocolError):
            camera.write_file('/test', b'data')

        fake_unavail = FakeIO([header(0, sequence=1, function=0xff01, status=0x82)])
        cam_unavail = protocol.Senser(fake_unavail)
        with self.assertRaises(protocol.FileUnavailable):
            cam_unavail.write_file('/test', b'data')
        self.assertFalse(cam_unavail.failed)
        self.assertEqual(cam_unavail.sequence, 2)

        fake_drain = FakeIO([header(4, sequence=1, function=0xff01, status=1), b'ACK!'])
        cam_drain = protocol.Senser(fake_drain)
        size = cam_drain.write_file('/test', b'data')
        self.assertEqual(size, 4)
        self.assertEqual(cam_drain.sequence, 2)

        fake_limit = FakeIO([header(100, sequence=1, function=0xff01, status=1)])
        cam_limit = protocol.Senser(fake_limit)
        with self.assertRaises(protocol.ProtocolError):
            cam_limit.write_file('/test', b'data', limit=50)

        fake2 = FakeIO([])
        cam2 = protocol.Senser(fake2)
        for bad_path in ('relative', '/a/../b', '/a\0b'):
            with self.assertRaises(ValueError):
                cam2.write_file(bad_path, b'data')
        with self.assertRaises(TypeError):
            cam2.write_file('/test', 'not bytes')
        with self.assertRaises(ValueError):
            cam2.write_file('/test', b'data', limit=2)
        self.assertEqual(fake2.sent, [])


class AuthenticationTests(unittest.TestCase):
    def test_both_pid_branches_and_fixed_rounds(self):
        keys = [bytes([i]) * 512 for i in range(3)]
        def reply(code, body=b''):
            return struct.pack('>HH512s', (~code) & 65535, 0, body)
        for pid in (0x0341, 0x0336):
            inputs = []
            fake = FakeIO([item for _ in range(3) for item in (reply(2, b'C' * 512), reply(4))] + [reply(6, b'\x01')])
            protocol.authenticate(fake, pid, keys, lambda value: inputs.append(value) or bytes(20))
            self.assertEqual(len(fake.sent), 7)
            self.assertEqual(inputs, [b'C' * 512 + key for key in keys] if pid == 0x0336 else [b'CCCC'] * 3)

    def test_auth_rejects_unknown_algorithm_short_and_salt(self):
        for response in (bytes(10), struct.pack('>HH512s', 0xfff7, 0, b''),
                         struct.pack('>HH512s', 0xfffd, 1, b'')):
            with self.assertRaises(protocol.ProtocolError):
                protocol.authenticate(FakeIO([response]), 0x0336, [bytes(512)] * 3, lambda _: bytes(20))


class QualificationTests(unittest.TestCase):
    def fixture(self, root):
        rows = []
        data = {}
        for path in app.STATE + app.IMPLEMENTATION:
            content = (b'<manager xmlns="http://www.kinoma.com/fskin/1"><systemData id="systemData"><lang>jpn</lang><langGp>1</langGp><sigTyp>0</sigTyp></systemData></manager>'
                       if path == app.STATE[2] else bytes(64))
            name = 'files/' + path.lstrip('/')
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            rows.append(dict(camera_path=path, file=name, bytes=len(content), sha256=app.sha(content), repeat_equal=True))
            data[path] = content
        app.save_json(root / 'result.json', dict(operation='capture', ok=True, normal_mode_return_observed=True,
                                               serial='TEST', files=rows))
        (root / 'review.txt').write_text('SYNTHETIC TEST ONLY; no hardware qualification', encoding='utf-8')
        profile = dict(schema='w300-region-qualification-v1', serial='TEST',
                       baseline_sha256=app.sha((root / 'result.json').read_bytes()),
                       arguments=[255,256,33024,0], w300_handler_verified=True, original_board_eligible=True,
                       recovery_tested=True, recovery=dict(method='synthetic', result='synthetic', evidence_file='review.txt'),
                       evidence=[dict(file='review.txt', sha256=app.sha((root/'review.txt').read_bytes()))],
                       implementation_sha256={p: app.sha(data[p]) for p in app.IMPLEMENTATION}, hreg_file_offsets=[0,4,8,12])
        return profile, data

    def test_plan_remains_unqualified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            plan = app.prepare(root)
            self.assertFalse(plan['qualified'])
            self.assertEqual(plan['proposed_arguments'], [255,256,33024,0])

    def test_profile_integrity_and_recovery_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile, _ = self.fixture(root)
            path = root / 'qualification.json'
            for key, bad in [('serial','OTHER'), ('recovery_tested',False), ('evidence',[]),
                             ('hreg_file_offsets',[0,0,8,12]), ('implementation_sha256',{}),
                             ('baseline_sha256','bad'), ('arguments',[255,256,33024,1])]:
                with self.subTest(key=key):
                    changed = dict(profile, **{key:bad})
                    path.write_text(json.dumps(changed))
                    with self.assertRaises(ValueError):
                        app.qualification(root,path,app.sha(path.read_bytes()))
            path.write_text(json.dumps(profile))
            app.qualification(root,path,app.sha(path.read_bytes()))
            with self.assertRaises(ValueError):
                app.qualification(root,path,'wrong hash')
            (root/'review.txt').write_text('altered')
            with self.assertRaises(ValueError):
                app.qualification(root,path,app.sha(path.read_bytes()))

    def test_readback_checks_whole_hreg_and_languages(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile, original = self.fixture(Path(temporary))
            updated = dict(original)
            for path in app.STATE[:2]:
                updated[path] = struct.pack('<4I',255,256,33024,0) + bytes(48)
            updated[app.STATE[2]] = b'<manager xmlns="http://www.kinoma.com/fskin/1"><systemData id="systemData"><lang>eng</lang><langGp>99</langGp><availableLang>eng,jpn,</availableLang><sigTyp>0</sigTyp></systemData></manager>'
            app.verify_changed(updated,original,profile)
            bad = dict(updated)
            bad[app.STATE[0]] = updated[app.STATE[0]][:-1] + b'X'
            with self.assertRaises(ValueError):
                app.verify_changed(bad,original,profile)
            bad = dict(updated)
            bad[app.STATE[2]] = updated[app.STATE[2]].replace(b'eng,jpn,', b'eng,')
            with self.assertRaises(ValueError):
                app.verify_changed(bad,original,profile)

    def test_apply_refuses_before_usb_without_qualification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(app,'BASE',root), patch.object(app,'usb_modules',side_effect=AssertionError('USB accessed')):
                with patch.object(sys,'argv',['app','apply','--serial','TEST','--experimental-service',
                                               '--baseline',str(root),'--qualification',str(root/'none'),
                                               '--qualification-sha256','invalid']), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(app.main(),2)

    def test_wrong_xml_structure_rejected(self):
        for xml in (b'<manager><lang>eng</lang><langGp>99</langGp><sigTyp>0</sigTyp></manager>',
                    b'<manager xmlns="http://www.kinoma.com/fskin/1"><systemData id="wrong"><lang>eng</lang><langGp>99</langGp><sigTyp>0</sigTyp></systemData></manager>'):
            with self.assertRaises(ValueError):
                app.xml_values(xml)


class SessionTests(unittest.TestCase):
    def run_session(self, fail_auth=False, fail_exit=False):
        from types import SimpleNamespace
        normal = SimpleNamespace(idProduct=0x0341, serial_number='TEST', product='DSC-W300', bus=1, port_numbers=[4])
        service = SimpleNamespace(idProduct=0x0336, bus=1, port_numbers=[4])
        core = SimpleNamespace(find=lambda **kwargs: [service])
        util = SimpleNamespace(dispose_resources=lambda device: None)
        controls = []
        class FakeUsb:
            def __init__(self, device, trace):
                self.pid = device.idProduct
            def control(self, start):
                controls.append((self.pid, start))
                if not start and fail_exit:
                    raise RuntimeError('Exit transfer failed')
        trace = SimpleNamespace(record=lambda *a, **kw: None)
        report = {}
        auth_error = RuntimeError('Auth failed') if fail_auth else None
        with patch.object(app,'load_auth',return_value=([],None)), patch.object(app,'usb_modules',return_value=(core,util,None)), \
             patch.object(app,'find_one',return_value=normal), patch.object(app,'wait_device',side_effect=[service,normal]), \
             patch.object(app,'UsbIO',FakeUsb), patch.object(app,'authenticate',side_effect=auth_error):
            if fail_auth:
                # First-stage failure skips the mode-transition wait; final normal wait must return normal.
                with patch.object(app,'wait_device',return_value=normal), self.assertRaises(RuntimeError):
                    with app.session('TEST',trace,report):
                        self.fail('Unexpected authenticated session')
            else:
                with app.session('TEST',trace,report):
                    self.assertTrue(report['service_authenticated'])
        return controls, report

    def test_successful_lifecycle_returns_normal_identity(self):
        controls, report = self.run_session()
        self.assertEqual(controls,[(0x0341,True),(0x0336,True),(0x0336,False)])
        self.assertTrue(report['normal_mode_return_observed'])

    def test_failed_auth_still_attempts_exit(self):
        controls, report = self.run_session(fail_auth=True)
        self.assertEqual(controls[-1],(0x0336,False))
        self.assertTrue(report['normal_mode_return_observed'])

    def test_failed_exit_is_not_success(self):
        _, report = self.run_session(fail_exit=True)
        self.assertFalse(report['normal_mode_return_observed'])
        self.assertIn('exit_error',report)


class SyncMirrorTests(unittest.TestCase):
    def test_sync_mirror_modifications_and_assertions(self):
        original_preg = bytearray(1040)
        original_preg[0] = 0x01  # Armed
        original_preg[0x10:0x20] = struct.pack('<4I', 0, 0, 0, 0)  # Factory Japanese
        for i in range(0x20, 1040):
            original_preg[i] = (i * 13) % 256
        original_bytes = bytes(original_preg)

        written_chunks = []
        class MockCamera:
            def __init__(self):
                self.current = bytearray(original_bytes)
            def read_file(self, path):
                if path == app.PREG:
                    return bytes(self.current)
                raise FileNotFoundError(path)
            def write_file(self, path, data):
                if path == app.PREG:
                    written_chunks.append(data)
                    self.current = bytearray(data)
                    return 0
                raise FileNotFoundError(path)

        camera = MockCamera()
        report = {}
        result = app.sync_mirror(camera, signal=0, report=report)

        self.assertEqual(len(written_chunks), 1)
        written = written_chunks[0]
        self.assertEqual(len(written), 1040)
        # Byte 0 must be 0x00 (disarmed)
        self.assertEqual(written[0], 0x00)
        # Bytes 0x10..0x1F must be English golden mirror: [255, 0x100, 0x8100, 0]
        self.assertEqual(written[0x10:0x20], struct.pack('<4I', 255, 0x100, 0x8100, 0))
        # Bytes 0x20..0x40F must be preserved identical to original
        self.assertEqual(written[0x20:1040], original_bytes[0x20:1040])
        self.assertEqual(result, written)
        self.assertTrue(report.get('mirror_synced'))
        self.assertEqual(report.get('mirror_arguments'), [255, 0x100, 0x8100, 0])

    def test_sync_mirror_signal_pal(self):
        original_preg = bytes([1] + [0] * 1039)
        class MockCamera:
            def __init__(self):
                self.data = bytearray(original_preg)
            def read_file(self, path):
                return bytes(self.data)
            def write_file(self, path, data):
                self.data = bytearray(data)
                return 0

        camera = MockCamera()
        app.sync_mirror(camera, signal=1)
        self.assertEqual(camera.data[0x10:0x20], struct.pack('<4I', 255, 0x100, 0x8100, 1))

    def test_sync_mirror_rejections(self):
        class ValidCam:
            def read_file(self, p): return bytes([1] + [0] * 1039)
            def write_file(self, p, d): pass

        for bad_signal in (2, -1, '0', None, 1.0):
            with self.assertRaises(ValueError):
                app.sync_mirror(ValidCam(), signal=bad_signal)

        class BadSizeCam:
            def read_file(self, p): return bytes(512)
            def write_file(self, p, d): pass
        with self.assertRaises(ValueError):
            app.sync_mirror(BadSizeCam(), signal=0)

        class TamperCam:
            def read_file(self, p): return bytes([1] * 1040)
            def write_file(self, p, d): pass
        with self.assertRaises(ValueError):
            app.sync_mirror(TamperCam(), signal=0)

        class CorruptCam:
            def __init__(self, corrupt_idx=0x30):
                self.count = 0
                self.corrupt_idx = corrupt_idx
            def read_file(self, p):
                self.count += 1
                if self.count == 1: return bytes(1040)
                corrupted = bytearray(1040)
                corrupted[0x10:0x20] = struct.pack('<4I', 255, 0x100, 0x8100, 0)
                corrupted[self.corrupt_idx] = 0xff
                return bytes(corrupted)
            def write_file(self, p, d): pass

        with self.assertRaisesRegex(ValueError, 'altered outside golden mirror'):
            app.sync_mirror(CorruptCam(0x30), signal=0)
        with self.assertRaisesRegex(ValueError, 'altered outside golden mirror'):
            app.sync_mirror(CorruptCam(5), signal=0)

    def test_change_permanent_and_sync_mirror_cli(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            preg_data = bytes([1] + [0] * 1039)
            hreg_data = bytes(2048)
            xml_data = b'<manager xmlns="http://www.kinoma.com/fskin/1"><systemData id="systemData"><lang>jpn</lang><langGp>1</langGp><sigTyp>0</sigTyp></systemData></manager>'
            original_files = {
                app.PREG: preg_data,
                app.STATE[0]: hreg_data,
                app.STATE[1]: hreg_data,
                app.STATE[2]: xml_data,
                app.STATE[3]: b'',
                app.STATE[4]: b'',
            }

            calls = []
            class MockLiveCamera:
                def __init__(self):
                    self.preg_bytes = bytearray(preg_data)
                def read_file(self, p):
                    calls.append(('read', p))
                    if p == app.PREG:
                        return bytes(self.preg_bytes)
                    if p in original_files:
                        return original_files[p]
                    return bytes(64)
                def write_file(self, p, d):
                    calls.append(('write', p, d))
                    if p == app.PREG:
                        self.preg_bytes = bytearray(d)
                    return 0
                def set_region(self, v):
                    calls.append(('set_region', v))

            mock_cam = MockLiveCamera()

            @contextlib.contextmanager
            def fake_session(serial, trace, report):
                report['normal_mode_return_observed'] = True
                yield mock_cam

            # 1. Test change --permanent
            sess1 = root / 'session1'
            sess1.mkdir(parents=True, exist_ok=True)
            args = argparse.Namespace(
                command='change', serial='TEST', experimental_service=True,
                baseline=root, permanent=True
            )
            report = dict(serial='TEST', ok=False, files=[], region_write_attempted=False)
            trace = app.Trace(sess1)
            try:
                with patch.object(app, 'load_capture', return_value=({'serial': 'TEST'}, original_files, 'dummy_hash')), \
                     patch.object(app.region_compat, 'assess', return_value={
                         'can_attempt_experimental_write': True,
                         'original_arguments': [0, 0, 0, 0],
                         'requested_arguments': [255, 0x100, 0x8100, 0],
                     }), \
                     patch.object(app.region_compat, 'check_state', return_value={'lang': 'eng', 'langGp': '99', 'availableLang': 'eng,jpn', 'sigTyp': '0'}), \
                     patch.object(app, 'session', fake_session):
                    app.automatic_operation(args, sess1, trace, report)
            finally:
                trace.close()

            self.assertTrue(report.get('mirror_synced'))
            self.assertTrue(report.get('permanent'))
            self.assertTrue(any(c[0] == 'set_region' for c in calls))
            self.assertTrue(any(c[0] == 'write' and c[1] == app.PREG for c in calls))
            intent_sess1 = json.loads((sess1 / 'write-intent.json').read_text())
            self.assertTrue(intent_sess1.get('permanent'))

            # 2. Test sync-mirror standalone with matching active region
            calls.clear()
            sess2 = root / 'session2'
            sess2.mkdir(parents=True, exist_ok=True)
            args_sync = argparse.Namespace(
                command='sync-mirror', serial='TEST', experimental_service=True,
                baseline=root
            )
            report_sync = dict(serial='TEST', ok=False, files=[], region_write_attempted=False)
            trace_sync = app.Trace(sess2)
            try:
                with patch.object(app, 'load_capture', return_value=({'serial': 'TEST'}, original_files, 'dummy_hash')), \
                     patch.object(app.region_compat, 'assess', return_value={
                         'can_attempt_experimental_write': True,
                         'original_arguments': [0, 0, 0, 0],
                         'requested_arguments': [255, 0x100, 0x8100, 0],
                     }), \
                     patch.object(app.region_compat, 'check_state', return_value={'lang': 'eng', 'langGp': '99', 'availableLang': 'eng,jpn', 'sigTyp': '0'}), \
                     patch.object(app, 'session', fake_session):
                    app.automatic_operation(args_sync, sess2, trace_sync, report_sync)
            finally:
                trace_sync.close()

            self.assertTrue(report_sync.get('mirror_synced'))
            self.assertTrue(report_sync.get('configuration_readback_matches'))
            self.assertEqual(report_sync.get('write_outcome'), 'saved-files-match; restart-and-visual-check-pending')
            self.assertFalse(any(c[0] == 'set_region' for c in calls))
            self.assertTrue(any(c[0] == 'write' and c[1] == app.PREG for c in calls))

            # 2b. Test sync-mirror standalone with diverged active region (e.g. Japanese active files)
            calls.clear()
            sess2b = root / 'session2b'
            sess2b.mkdir(parents=True, exist_ok=True)
            report_sync_div = dict(serial='TEST', ok=False, files=[], region_write_attempted=False)
            trace_sync_div = app.Trace(sess2b)
            try:
                with patch.object(app, 'load_capture', return_value=({'serial': 'TEST'}, original_files, 'dummy_hash')), \
                     patch.object(app.region_compat, 'assess', return_value={
                         'can_attempt_experimental_write': True,
                         'original_arguments': [0, 0, 0, 0],
                         'requested_arguments': [255, 0x100, 0x8100, 0],
                     }), \
                     patch.object(app.region_compat, 'check_state', side_effect=ValueError('Regional field values have not converged')), \
                     patch.object(app, 'session', fake_session):
                    app.automatic_operation(args_sync, sess2b, trace_sync_div, report_sync_div)
            finally:
                trace_sync_div.close()

            self.assertTrue(report_sync_div.get('mirror_synced'))
            self.assertFalse(report_sync_div.get('configuration_readback_matches'))
            self.assertIn('Regional field values have not converged', report_sync_div.get('active_region_diverged', ''))
            self.assertEqual(report_sync_div.get('write_outcome'), 'mirror-synced; active-region-differs')

            # 3. Test restore-region restores Preg.bin
            calls.clear()
            change_session_dir = root / 'session_prior_change'
            change_session_dir.mkdir(parents=True, exist_ok=True)
            (change_session_dir / 'result.json').write_text(json.dumps({
                'operation': 'change', 'serial': 'TEST', 'baseline_sha256': 'dummy_hash', 'region_write_attempted': True
            }))
            sess3 = root / 'session3'
            sess3.mkdir(parents=True, exist_ok=True)
            args_restore = argparse.Namespace(
                command='restore-region', serial='TEST', experimental_service=True,
                baseline=root, change_session=change_session_dir
            )
            report_restore = dict(serial='TEST', ok=False, files=[], region_write_attempted=False)
            trace_restore = app.Trace(sess3)
            try:
                with patch.object(app, 'load_capture', return_value=({'serial': 'TEST'}, original_files, 'dummy_hash')), \
                     patch.object(app.region_compat, 'assess', return_value={
                         'can_attempt_experimental_write': True,
                         'original_arguments': [0, 0, 0, 0],
                         'requested_arguments': [255, 0x100, 0x8100, 0],
                     }), \
                     patch.object(app.region_compat, 'check_state', return_value={'lang': 'jpn', 'langGp': '1', 'availableLang': 'jpn', 'sigTyp': '0'}), \
                     patch.object(app, 'session', fake_session):
                    app.automatic_operation(args_restore, sess3, trace_restore, report_restore)
            finally:
                trace_restore.close()

            self.assertTrue(report_restore.get('preg_restored'))
            self.assertTrue(any(c[0] == 'write' and c[1] == app.PREG and c[2] == preg_data for c in calls))
            tx_sess3 = (sess3 / 'transactions.jsonl').read_text()
            self.assertIn('restore-preg-write', tx_sess3)

            # 4. Test restore-region rejects bad baseline Preg.bin size
            bad_preg_files = dict(original_files)
            bad_preg_files[app.PREG] = bytes(512)
            sess4 = root / 'session4'
            sess4.mkdir(parents=True, exist_ok=True)
            report_bad = dict(serial='TEST', ok=False, files=[], region_write_attempted=False)
            trace_bad = app.Trace(sess4)
            try:
                with patch.object(app, 'load_capture', return_value=({'serial': 'TEST'}, bad_preg_files, 'dummy_hash')), \
                     patch.object(app.region_compat, 'assess', return_value={
                         'can_attempt_experimental_write': True,
                         'original_arguments': [0, 0, 0, 0],
                         'requested_arguments': [255, 0x100, 0x8100, 0],
                     }), \
                     patch.object(app.region_compat, 'check_state', return_value={'lang': 'jpn', 'langGp': '1', 'availableLang': 'jpn', 'sigTyp': '0'}), \
                     patch.object(app, 'session', fake_session):
                    with self.assertRaisesRegex(ValueError, 'size mismatch'):
                        app.automatic_operation(args_restore, sess4, trace_bad, report_bad)
            finally:
                trace_bad.close()

            # 5. Test restore-region fails if camera connection lacks write_file capability
            class NoWriteCam:
                def read_file(self, p):
                    if p in original_files: return original_files[p]
                    return bytes(64)
                def set_region(self, v): pass
            @contextlib.contextmanager
            def no_write_session(serial, trace, report):
                report['normal_mode_return_observed'] = True
                yield NoWriteCam()

            sess5 = root / 'session5'
            sess5.mkdir(parents=True, exist_ok=True)
            report_nw = dict(serial='TEST', ok=False, files=[], region_write_attempted=False)
            trace_nw = app.Trace(sess5)
            try:
                with patch.object(app, 'load_capture', return_value=({'serial': 'TEST'}, original_files, 'dummy_hash')), \
                     patch.object(app.region_compat, 'assess', return_value={
                         'can_attempt_experimental_write': True,
                         'original_arguments': [0, 0, 0, 0],
                         'requested_arguments': [255, 0x100, 0x8100, 0],
                     }), \
                     patch.object(app.region_compat, 'check_state', return_value={'lang': 'jpn', 'langGp': '1', 'availableLang': 'jpn', 'sigTyp': '0'}), \
                     patch.object(app, 'session', no_write_session):
                    with self.assertRaisesRegex(RuntimeError, 'does not support file writing'):
                        app.automatic_operation(args_restore, sess5, trace_nw, report_nw)
            finally:
                trace_nw.close()


if __name__ == '__main__':
    unittest.main()
