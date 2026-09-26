"""Synthetic automatic change/restoration tests; no physical-camera verdict."""
import contextlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'build/w300'))
import region_app as app
import region_compat as compat
from region_protocol import setting_body

JAPANESE = b'<manager xmlns="http://www.kinoma.com/fskin/1"><systemData id="systemData"><lang>jpn</lang><langGp>1</langGp><sigTyp>0</sigTyp></systemData></manager>'
ENGLISH = b'<manager xmlns="http://www.kinoma.com/fskin/1"><systemData id="systemData"><lang>eng</lang><langGp>99</langGp><availableLang>eng,jpn,</availableLang><sigTyp>0</sigTyp></systemData></manager>'


def fixture(root):
    baseline=root/'baseline'; baseline.mkdir()
    bank=bytearray(2048)
    bank[0x1f0:0x1f4]=b'\xaa'*4
    struct.pack_into('<4I',bank,0x400,0,0x8000,1,0)
    files={p:bytes(64) for p in app.IMPLEMENTATION+app.STATE}
    files.update({app.STATE[0]:bytes(bank),app.STATE[1]:bytes(bank),app.STATE[2]:JAPANESE,app.PREG:bytes(app.PREG_SIZE)})
    rows=[]
    reference={'files':{}}
    for path,data in files.items():
        name='files/'+path.lstrip('/')
        target=baseline/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
        rows.append(dict(camera_path=path,file=name,bytes=len(data),sha256=app.sha(data),repeat_equal=True))
        if path in app.IMPLEMENTATION:
            reference['files'][path]=[dict(bytes=len(data),sha256=app.sha(data),model='SYNTHETIC_ONLY')]
    app.save_json(baseline/'result.json',dict(operation='capture',ok=True,normal_mode_return_observed=True,serial='TEST',files=rows))
    return baseline,files,reference


class FakeCamera:
    def __init__(self,files):
        self.files=dict(files); self.sent=[]; self.transient=False
    def read_file(self,path):
        if self.transient and self.sent and path==app.STATE[2]:
            self.transient=False
            raise app.FileUnavailable('Transient XML replacement')
        return self.files[path]
    def write_file(self,path,data):
        self.files[path]=bytes(data)
        return 0
    def set_region(self,values):
        self.sent.append(list(values))
        for path in app.STATE[:2]:
            data=bytearray(self.files[path]); struct.pack_into('<4I',data,0x400,*values)
            data[0x1f0:0x1f4]=b'\xaa'*4; self.files[path]=bytes(data)
        self.files[app.STATE[2]]=JAPANESE if values[0]==0 else ENGLISH


class AutomaticTests(unittest.TestCase):
    def invoke(self,root,baseline,reference,camera,command,change_session=None):
        output=root/(command+str(len(list(root.iterdir())))); output.mkdir()
        args=SimpleNamespace(command=command,baseline=baseline,serial='TEST',expect='english',change_session=change_session)
        report=dict(operation=command,serial='TEST',files=[],region_write_attempted=False)
        trace=SimpleNamespace(record=lambda *a,**k:None)
        @contextlib.contextmanager
        def session(*a,**k):
            report['normal_mode_return_observed']=True
            yield camera
        with patch.object(app,'session',session),patch.object(compat,'load_reference',return_value=reference):
            app.automatic_operation(args,output,trace,report)
        return report

    def test_exact_comparison_change_verify_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); baseline,files,reference=fixture(root); camera=FakeCamera(files)
            report=self.invoke(root,baseline,reference,camera,'change')
            self.assertEqual(camera.sent,[[255,256,33024,0]])
            self.assertTrue(report['configuration_readback_matches'])
            self.assertFalse(report['recovery_hardware_tested'])
            self.invoke(root,baseline,reference,camera,'verify-region')
            self.assertEqual(len(camera.sent),1)
            change=root/'change.json'; app.save_json(change,report)
            restored=self.invoke(root,baseline,reference,camera,'restore-region',change)
            self.assertEqual(camera.sent[-1],[0,32768,1,0])
            self.assertFalse(restored['preferences_restored'])
            self.assertEqual(camera.files[app.STATE[0]],files[app.STATE[0]])

    def test_firmware_mismatch_does_not_open_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); baseline,files,reference=fixture(root)
            reference['files'][app.ESSENTIAL[0]][0]['sha256']='wrong'
            output=root/'output'; output.mkdir()
            args=SimpleNamespace(command='change',baseline=baseline,serial='TEST')
            with patch.object(compat,'load_reference',return_value=reference),patch.object(app,'session',side_effect=AssertionError('USB opened')):
                with self.assertRaisesRegex(ValueError,'differs or baseline'):
                    app.automatic_operation(args,output,None,{'files':[]})

    def test_live_drift_prevents_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); baseline,files,reference=fixture(root); camera=FakeCamera(files)
            camera.files[app.STATE[0]]=bytes(2048)
            with self.assertRaisesRegex(ValueError,'baseline changed'):
                self.invoke(root,baseline,reference,camera,'change')
            self.assertEqual(camera.sent,[])

    def test_transient_xml_does_not_resend_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); baseline,files,reference=fixture(root); camera=FakeCamera(files); camera.transient=True
            self.invoke(root,baseline,reference,camera,'change')
            self.assertEqual(len(camera.sent),1)

    def test_transient_partial_xml_does_not_resend_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); baseline,files,reference=fixture(root); camera=FakeCamera(files)
            original_read=camera.read_file
            pending=[True]
            def read(path):
                if camera.sent and path==app.STATE[2] and pending[0]:
                    pending[0]=False
                    return b'<manager'
                return original_read(path)
            camera.read_file=read
            self.invoke(root,baseline,reference,camera,'change')
            self.assertEqual(len(camera.sent),1)


    def test_durable_intent_allows_restore_when_result_was_not_saved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); baseline,files,reference=fixture(root); camera=FakeCamera(files)
            native=camera.set_region
            def interrupted(values):
                native(values)
                raise TimeoutError('Reply lost after save')
            camera.set_region=interrupted
            with self.assertRaises(TimeoutError):
                self.invoke(root,baseline,reference,camera,'change')
            intent=next(root.glob('change*/write-intent.json'))
            self.assertFalse((intent.parent/'result.json').exists())
            camera.set_region=native
            self.invoke(root,baseline,reference,camera,'restore-region',intent)
            self.assertEqual(camera.sent,[[255,256,33024,0],[0,32768,1,0]])
            self.assertEqual(camera.files[app.STATE[0]],files[app.STATE[0]])

    def test_unknown_write_outcome_never_auto_retries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); baseline,files,reference=fixture(root); camera=FakeCamera(files)
            def fail(values):
                camera.sent.append(values)
                raise TimeoutError('Reply missing')
            camera.set_region=fail
            with self.assertRaises(TimeoutError):
                self.invoke(root,baseline,reference,camera,'change')
            self.assertEqual(len(camera.sent),1)

    def test_interrupted_primary_with_changed_spare_stops_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); baseline,files,reference=fixture(root); camera=FakeCamera(files)
            report=self.invoke(root,baseline,reference,camera,'change')
            broken=bytearray(camera.files[app.STATE[0]]); broken[0x1f0:0x1f4]=bytes(4); camera.files[app.STATE[0]]=bytes(broken)
            change=root/'change.json'; app.save_json(change,report)
            with self.assertRaisesRegex(ValueError,'Incomplete primary'):
                self.invoke(root,baseline,reference,camera,'restore-region',change)
            self.assertEqual(len(camera.sent),1)

    def test_mixed_reference_models_and_missing_preferences_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            _,files,reference=fixture(Path(temporary))
            reference['files'][app.ESSENTIAL[0]][0]['model']='OTHER_SYNTHETIC'
            result=compat.assess(files,reference,app.xml_values)
            self.assertFalse(result['can_attempt_experimental_write'])
            self.assertTrue(any('coherent' in reason for reason in result['reasons']))
            reference['files'][app.ESSENTIAL[0]][0]['model']='SYNTHETIC_ONLY'
            files.pop('/boot/dsc/UserInfo.bak')
            self.assertFalse(compat.assess(files,reference,app.xml_values)['can_attempt_experimental_write'])

    def test_marker_and_setting_encoding(self):
        with self.assertRaises(ValueError): compat.hreg_values(bytes(2048))
        self.assertEqual(setting_body([0,32768,1,0]).hex(),'3f00550000000000008000000100000000000000')
        for values in ([0,1,2], [True,1,2,0], [0,-1,1,0]):
            with self.assertRaises(ValueError): setting_body(values)

    def test_final_repeat_read_unavailable_cannot_report_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); baseline,files,reference=fixture(root); camera=FakeCamera(files)
            self.invoke(root,baseline,reference,camera,'change')
            original_read=camera.read_file
            counts={}
            def read(path):
                counts[path]=counts.get(path,0)+1
                if path==app.STATE[0] and counts[path]==2:
                    raise app.FileUnavailable('Second read unavailable')
                return original_read(path)
            camera.read_file=read
            with self.assertRaisesRegex(app.ProtocolError,'Repeat read became unavailable'):
                self.invoke(root,baseline,reference,camera,'verify-region')
            self.assertEqual(len(camera.sent),1)

    def test_custom_english_baseline_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); baseline,files,reference=fixture(root)
            bank=bytearray(files[app.STATE[0]])
            struct.pack_into('<4I',bank,0x400,255,0x100,0x8100,0)
            files[app.STATE[0]]=bytes(bank); files[app.STATE[1]]=bytes(bank)

            # 1. Custom English Hreg with cold-boot reverted Japanese XML is accepted
            result=compat.assess(files,reference,app.xml_values)
            self.assertTrue(result['can_attempt_experimental_write'])
            self.assertEqual(result['original_arguments'],[255,256,33024,0])
            self.assertEqual(result['requested_arguments'],[255,256,33024,0])

            # 2. Custom English Hreg with native English XML is accepted
            files[app.STATE[2]] = b'<manager xmlns="http://www.kinoma.com/fskin/1"><systemData id="systemData"><lang>eng</lang><langGp>99</langGp><availableLang>eng,jpn,</availableLang><sigTyp>0</sigTyp></systemData></manager>'
            result_eng = compat.assess(files,reference,app.xml_values)
            self.assertTrue(result_eng['can_attempt_experimental_write'])

            # 3. Custom English Hreg without UserInfo.bak is accepted (reset by RegionSetting)
            files_no_bak = dict(files)
            files_no_bak.pop('/boot/dsc/UserInfo.bak')
            result_no_bak = compat.assess(files_no_bak,reference,app.xml_values)
            self.assertTrue(result_no_bak['can_attempt_experimental_write'])

            # 4. Custom English with mismatched language group is rejected
            files_bad_gp = dict(files)
            files_bad_gp[app.STATE[2]] = b'<manager xmlns="http://www.kinoma.com/fskin/1"><systemData id="systemData"><lang>eng</lang><langGp>1</langGp><availableLang>eng,jpn,</availableLang><sigTyp>0</sigTyp></systemData></manager>'
            self.assertFalse(compat.assess(files_bad_gp,reference,app.xml_values)['can_attempt_experimental_write'])

            # 5. Custom English with mismatched available languages is rejected
            files_bad_avail = dict(files)
            files_bad_avail[app.STATE[2]] = b'<manager xmlns="http://www.kinoma.com/fskin/1"><systemData id="systemData"><lang>eng</lang><langGp>99</langGp><availableLang>jpn,</availableLang><sigTyp>0</sigTyp></systemData></manager>'
            self.assertFalse(compat.assess(files_bad_avail,reference,app.xml_values)['can_attempt_experimental_write'])

            # 6. Custom English with unexpected language is rejected
            files_bad_lang = dict(files)
            files_bad_lang[app.STATE[2]] = b'<manager xmlns="http://www.kinoma.com/fskin/1"><systemData id="systemData"><lang>fra</lang><langGp>99</langGp><availableLang>fra,eng,</availableLang><sigTyp>0</sigTyp></systemData></manager>'
            self.assertFalse(compat.assess(files_bad_lang,reference,app.xml_values)['can_attempt_experimental_write'])


if __name__=='__main__':
    unittest.main()
