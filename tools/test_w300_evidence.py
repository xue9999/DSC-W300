"""Offline tests; never communicate with hardware."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from w300_evidence import compare, usb_records


class EvidenceTests(unittest.TestCase):
    def test_inventory_nested_and_unknown_identity(self):
        tree = [{'IORegistryEntryChildren': [
            {'idVendor': 0x054c, 'idProduct': 0x1234,
             'USB Product Name': 'Sony Camera'},
            {'idVendor': 123, 'idProduct': 456}]}]
        rows = usb_records(tree)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['vendor_id'], '054c')
        self.assertIsNone(rows[0]['serial'])
        self.assertEqual(usb_records([{'IORegistryEntryName': 'Root'}]), [])

    def test_comparison_detects_change_and_truncation(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d)/'a', Path(d)/'b'
            a.write_bytes(b'A' * (1024 * 1024) + b'BC')
            b.write_bytes(b'A' * (1024 * 1024) + b'BD')
            result = compare(a, b)
            self.assertFalse(result['identical'])
            self.assertEqual(result['first_different_offsets'], [1024 * 1024 + 1])
            b.write_bytes(a.read_bytes()[:-1])
            self.assertEqual(compare(a, b)['different_byte_positions'], 1)
            b.write_bytes(a.read_bytes())
            self.assertTrue(compare(a, b)['identical'])

    def test_empty_equality_is_not_coverage_proof(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d)/'a', Path(d)/'b'
            a.touch(); b.touch()
            result = compare(a, b)
            self.assertTrue(result['identical'])
            self.assertIn('unknown', result['coverage'])

    def test_difference_output_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d)/'a', Path(d)/'b'
            a.write_bytes(b'A' * 1000); b.write_bytes(b'B' * 1000)
            result = compare(a, b)
            self.assertEqual(result['different_byte_positions'], 1000)
            self.assertEqual(len(result['first_different_offsets']), 128)
            self.assertTrue(result['offsets_truncated'])

    def test_cli_never_overwrites_and_returns_difference_status(self):
        with tempfile.TemporaryDirectory() as d:
            a, b, out = [Path(d)/s for s in ('a', 'b', 'out.json')]
            a.write_bytes(b'A'); b.write_bytes(b'B')
            cmd = [sys.executable, str(Path(__file__).with_name('w300_evidence.py')),
                   'compare', str(a), str(b), '--output', str(out)]
            result = subprocess.run(cmd, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(out.read_text())['identical'])
            original = out.read_bytes()
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)
            self.assertEqual(out.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
