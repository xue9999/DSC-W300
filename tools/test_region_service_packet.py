"""Independent wire fixture and coherent-input bounds; no camera support claim."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'build/w300/reports/region-service-method/packet.py'
SPEC = importlib.util.spec_from_file_location('region_packet', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RegionPacketTests(unittest.TestCase):
    def test_comparative_fixture(self):
        self.assertEqual(MODULE.custom_packet(0), bytes.fromhex(
            '1400000040000000000000003f005500ff000000000100000081000000000000'))

    def test_incoherent_or_truncated_inputs_rejected(self):
        for kwargs in ({'sequence': -1}, {'sequence': 65536},
                       {'sequence': True}, {'sequence': 0, 'available': 2},
                       {'sequence': 0, 'available': 0x8000},
                       {'sequence': 0, 'signal': 2},
                       {'sequence': 0, 'language': 0x101}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                MODULE.custom_packet(**kwargs)

    def test_sequence_and_pal_fields(self):
        packet = MODULE.custom_packet(0x1234, signal=1)
        self.assertEqual(packet[6:8], b'\x34\x12')
        self.assertEqual(packet[28:32], b'\x01\0\0\0')
