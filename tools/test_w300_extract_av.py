#!/usr/bin/env python3
"""Unit tests for DSC-W300 av.bin extractor and static ARM ELF payload generator."""

from pathlib import Path
import struct
import sys
import tempfile
import unittest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from tools.w300_extractor_payload import (
    ArmHelperAssembler,
    build_elf,
    make_test_payload,
    make_extractor_payload,
    ELF_MAGIC,
    ET_EXEC,
    EM_ARM,
)
from tools.w300_extract_av import (
    verify_arm_vectors,
    extract_av_binary,
    double_read_file,
    sha256_bytes,
)
from region_protocol import ProtocolError


class TestW300ExtractorPayload(unittest.TestCase):
    def test_assembler_basic(self):
        asm = ArmHelperAssembler()
        asm.label('start')
        asm.mov(0, 10)
        asm.cmp(0, 10)
        asm.beq('equal')
        asm.mov(0, 0)
        asm.label('equal')
        asm.svc(1)

        code = asm.assemble()
        self.assertEqual(len(code), 20)  # 5 instructions * 4 bytes
        # First instruction mov r0, #10: 0xe3a0000a
        self.assertEqual(code[:4], struct.pack('<I', 0xe3a0000a))

    def test_elf_header_structure(self):
        code = struct.pack('<I', 0xef900001)  # svc #0x900001
        elf = build_elf(code)

        self.assertTrue(elf.startswith(ELF_MAGIC))
        e_type, e_machine = struct.unpack('<HH', elf[16:20])
        self.assertEqual(e_type, ET_EXEC)
        self.assertEqual(e_machine, EM_ARM)
        e_entry = struct.unpack('<I', elf[24:28])[0]
        self.assertEqual(e_entry, 0x10080)

    def test_test_payload_structure(self):
        payload = make_test_payload()
        self.assertTrue(payload.startswith(ELF_MAGIC))
        self.assertIn(b'/usr/test_exec.log', payload)
        self.assertIn(b'W300_EXEC_TEST_OK\n', payload)

    def test_extractor_payload_structure(self):
        payload = make_extractor_payload()
        self.assertTrue(payload.startswith(ELF_MAGIC))
        self.assertIn(b'/dev/nflasha5', payload)
        self.assertIn(b'/tmp/m', payload)
        self.assertIn(b'/usr/av.bin', payload)
        self.assertIn(b'/usr/sa.bin', payload)
        self.assertIn(b'/usr/dump.log', payload)
        # Check dynamic 16 KB stack allocation instruction: sub sp, sp, #0x4000 (0xe24dd901)
        self.assertIn(struct.pack('<I', 0xe24dd901), payload)

    def test_verify_arm_vectors(self):
        # Construct sample ARM vector table (ldr pc, [pc, #0x18])
        mock_vecs = struct.pack('<8I', 0xe59ff018, 0xe59ff018, 0xe59ff018, 0xe59ff018,
                                       0xe59ff018, 0xe1a00000, 0xe59ff014, 0xe59ff014)
        mock_payload = mock_vecs + bytes(100)
        res = verify_arm_vectors(mock_payload)
        self.assertTrue(res['valid'])
        self.assertTrue(res['is_ldr_pc_vectors'])
        self.assertEqual(len(res['raw_vectors_hex']), 8)

    def test_verify_arm_vectors_invalid(self):
        # Under 64 bytes
        res_short = verify_arm_vectors(b'\x00' * 30)
        self.assertFalse(res_short['valid'])
        self.assertIn('smaller', res_short['reason'])

        # Invalid vector instructions
        mock_invalid = struct.pack('<8I', 0x00000000, 0x11111111, 0x22222222, 0x33333333,
                                          0x44444444, 0x55555555, 0x66666666, 0x77777777) + bytes(100)
        res_inv = verify_arm_vectors(mock_invalid)
        self.assertFalse(res_inv['valid'])


class TestW300ExtractAvFlow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_mock_extraction_flow_isolated(self):
        report = extract_av_binary(mock=True, run_canary=True, output_dir=self.output_dir)
        self.assertTrue(report['ok'])
        self.assertEqual(report['stages']['stage2_canary_test']['status'], 'SUCCESS')
        self.assertTrue(report['stages']['safety_ud_datcnv_restored']['bit_for_bit_match'])
        self.assertIn('START', report['stages']['stage4_camera_log'])
        self.assertIn('MOUNT_OK', report['stages']['stage4_camera_log'])
        self.assertIn('AV_OK', report['stages']['stage4_camera_log'])
        self.assertIn('DONE', report['stages']['stage4_camera_log'])
        self.assertTrue(report['stages']['stage5_av_bin']['arm_vectors']['valid'])
        # Artifacts written to isolated directory
        self.assertTrue((self.output_dir / 'av.bin').is_file())
        self.assertTrue((self.output_dir / 'result.json').is_file())

    def test_mock_extraction_existing_dump(self):
        report = extract_av_binary(mock=True, run_canary=True, mock_pre_extracted=True, output_dir=self.output_dir)
        self.assertTrue(report['ok'])
        self.assertNotIn('stage2_canary_test', report['stages'])
        self.assertNotIn('stage3_helper_execution', report['stages'])
        self.assertTrue(report['stages']['safety_ud_datcnv_restored']['bit_for_bit_match'])
        self.assertIn('DONE', report['stages']['stage4_camera_log'])
        self.assertTrue(report['stages']['stage5_av_bin']['arm_vectors']['valid'])
        self.assertEqual(report['stages']['stage6_cleanup']['status'], 'COMPLETE')
        self.assertTrue((self.output_dir / 'av.bin').is_file())

    def test_double_read_verification_failure(self):
        class DivergingCamera:
            def __init__(self):
                self.count = 0
            def read_file(self, path, limit=1024):
                self.count += 1
                return b'read1' if self.count == 1 else b'read2'

        cam = DivergingCamera()
        with self.assertRaises(ProtocolError):
            double_read_file(cam, '/usr/test')


if __name__ == '__main__':
    unittest.main()
