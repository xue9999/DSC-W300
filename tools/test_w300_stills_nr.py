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


class OfflineStillsContracts(unittest.TestCase):
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
