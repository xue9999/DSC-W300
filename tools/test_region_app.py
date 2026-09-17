"""Offline protocol adversarial checks. These do not qualify camera compatibility."""
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


if __name__ == '__main__':
    unittest.main()
