"""W300 offline contracts; no camera or image-quality validation is claimed."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import w300_stills_nr as nr
import w300_nr_evidence as evidence


class OfflineStillsContracts(unittest.TestCase):
    def test_w300_programs_and_gates_from_pinned_code(self):
        report = evidence.analyze(evidence.AV.read_bytes())
        mapping = {s['name']:(s['normal_gate']['bank_offset'], s['alternate_gate']['bank_offset'])
                   for s in report['stages']}
        self.assertEqual(mapping, {
            'NR16_RAWNR':(0x2b01,0x32dd), 'NR32_RAWNR':(0x3033,0x3143),
            'NR32_CNR_2GCC':(0x3034,0x3144), 'NR32_CNR_NR':(0x3035,0x3145),
            'NR32_CNR_2RGB':(0x3036,0x3146)})
        self.assertFalse(report['live_write_qualified'])
        self.assertFalse(report['nr_disable_verified'])

    def test_av_version_guard_and_truncated_input(self):
        data = evidence.AV.read_bytes()
        for bad in (b'', data[:-1], data[:0x2c430] + bytes([data[0x2c430]^1]) + data[0x2c431:]):
            with self.assertRaisesRegex(ValueError, 'Unreviewed'):
                evidence.analyze(bad)

    def test_native_skip_and_dirty_contracts_reject_changed_implementations(self):
        av = evidence.AV.read_bytes()
        contract = evidence.raw_skip_contract(av)
        self.assertTrue(contract['native_skip_preserves_input_buffer_selection'])
        self.assertFalse(contract['all_nr_removed_verified'])
        broken = bytearray(av)
        broken[0x2bf56:0x2bf58] = b'\x02\xd0'  # Reverse the bypass condition.
        with self.assertRaisesRegex(ValueError, 'bypass condition'):
            evidence.raw_skip_contract(broken)
        core = evidence.BACKUP_CORE.read_bytes()
        self.assertFalse(evidence.backup_dirty_contract(core)['explicit_dirty_mark_required'])
        self.assertFalse(evidence.backup_dirty_contract(core)['persistence_qualified'])
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            evidence.backup_dirty_contract(core[:-1])

    def test_program_consumer_resolves_sa_indices_without_shift(self):
        av = evidence.AV.read_bytes()
        report = evidence.compare_program_container(evidence.SA.read_bytes(), av)
        self.assertTrue(report['static_name_index_alignment_verified'])
        self.assertFalse(report['runtime_container_observed'])
        entry = next(r for r in report['entries'] if r['program_id'] == 6)
        self.assertEqual(entry['av_name'], 'NR32_CNR_NR')
        self.assertEqual(entry['sa_header'], 'NR32_CNR0.07')
        self.assertEqual(entry['sa_payload_offset'], 0x13a28)
        names = evidence.program_names(av)
        self.assertEqual(names[0]['name'], 'JPG_SORT')
        self.assertEqual(names[8]['name'], 'RF_FISHEYE')
        self.assertEqual(len(names),24)
        self.assertEqual(names[6]['row_offset'],0x16eb24)
        broken = bytearray(av)
        broken[0x1a3a2:0x1a3a4] = b'\x20\x68'  # Wrong: ID from row[0], not row[4].
        with self.assertRaisesRegex(ValueError, 'consumer layout'):
            evidence.program_names(broken)
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            evidence.compare_program_container(b'SA2U_APP',av)

    def test_unknown_and_deceptive_names_are_only_byte_inventories(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, payload in (("empty.dat", b""), ("DSC-W300_ADJBAK.dat", b"X" * 8248),
                                  ("fake.bin", b"W300ADJ\x01" + b"X" * 9000)):
                path = Path(tmp) / name
                path.write_bytes(payload)
                report = nr.inspect_file(path)
                self.assertEqual(report["format"], "unverified_binary")
                self.assertFalse(report["hardware_validated"])
                self.assertEqual(report["sha256"], hashlib.sha256(payload).hexdigest())
                self.assertNotIn("calibration_preserved", report)
                with self.assertRaisesRegex(ValueError, "Unsupported for W300"):
                    nr.verify_calibration(path)

    def test_patch_compatibility_refuses_without_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "g3.bin", Path(tmp) / "out.bin"
            source.write_bytes(b"original")
            for fn in (nr.patch_dsp_file, nr.unpatch_dsp_file):
                with self.assertRaises(ValueError):
                    fn(source, output)
            self.assertFalse(output.exists())
            self.assertEqual(source.read_bytes(), b"original")

    def test_hypothetical_scenario_has_no_estimated_measurements(self):
        for setting in nr.W300_NR_LEVELS:
            report = nr.assess_ui(setting, "Normal", "80")
            self.assertTrue(report["simulation"])
            self.assertFalse(report["hardware_validated"])
            self.assertFalse(report["measured"])
            self.assertFalse(report["nr_disable_verified"])
            self.assertEqual(report["scenario"]["noise_reduction"], setting)
            self.assertNotIn("attenuation", report)
        with self.assertRaises(ValueError):
            nr.assess_ui("Off")

    def test_cli_json_and_refusal(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(nr.main(["assess-ui", "--nr", "minus"]), 0)
        self.assertTrue(json.loads(output.getvalue())["simulation"])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(nr.main(["patch-dsp", "missing.bin", "out.bin"]), 2)


if __name__ == "__main__":
    unittest.main()
