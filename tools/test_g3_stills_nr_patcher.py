"""Offline tests: provenance, allowed byte changes, generation and publication."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
from g3_stills_nr_patcher import (patch_av_bin, build_nonr_firmware, verify_nonr_dat,
    OFFSET_NR32_CNR, OFFSET_NR32_RGB, ORIGINAL_OPCODE, BYPASS_OPCODE)
from g3_verified import (trusted_source, verified_extracted, assemble, verify_expected,
    check_output, publish, SOURCE, EXTRACTED, ROOT)


class TestG3StillsNrPatcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = trusted_source()
        cls.av_bytes = cls.baseline[2][9]

    def test_patch_is_exact(self):
        patched = patch_av_bin(self.av_bytes)
        expected = bytearray(self.av_bytes)
        for offset in (OFFSET_NR32_CNR, OFFSET_NR32_RGB):
            expected[offset:offset + 2] = BYPASS_OPCODE
        self.assertEqual(patched, bytes(expected))

    def test_full_hash_rejects_mutation_away_from_opcodes(self):
        changed = bytearray(self.av_bytes); changed[123] ^= 1
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            patch_av_bin(bytes(changed))

    def test_source_hash_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'wrong.exe'; source.write_bytes(b'untrusted')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                trusted_source(source)

    def test_generation_roundtrip_and_derived_input_rejection(self):
        manifest, sections, payloads = self.baseline
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); extracted = root / 'sections'; extracted.mkdir()
            for i, (section, payload) in enumerate(zip(sections, payloads)):
                (extracted / f'{i:02d}_{section["name"]}').write_bytes(payload)
            cntent = root / 'cntent.dat'; cntent.write_bytes(manifest)
            output = root / 'nonr.dat'
            build_nonr_firmware(output, extracted, cntent)
            self.assertEqual(verify_nonr_dat(output)['status'], 'OFFLINE_INTEGRITY_VERIFIED')
            victim = extracted / ('00_' + sections[0]['name'])
            victim.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'Untrusted extracted section'):
                verified_extracted(extracted, cntent, self.baseline)
            victim.unlink()
            with self.assertRaisesRegex(ValueError, 'names/order'):
                verified_extracted(extracted, cntent, self.baseline)

    def test_source_and_evidence_output_refused(self):
        for output in (SOURCE, EXTRACTED / 'D-G3V2_nonr.dat', ROOT / 'evidence/usb-baseline.json'):
            with self.subTest(output=output), self.assertRaises(ValueError):
                check_output(output, overwrite=True)

    def test_alternate_source_filename_collision_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'renamed-firmware.exe'
            source.write_bytes(b'unchanged')
            with self.assertRaisesRegex(ValueError, 'source'):
                check_output(source, source=source, overwrite=True)
            self.assertEqual(source.read_bytes(), b'unchanged')

    def test_failed_verification_never_publishes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'out.dat'
            output.write_bytes(b'previous')
            def reject(path):
                raise ValueError('verification rejected')
            with self.assertRaises(ValueError):
                publish(b'new', output, reject, overwrite=True)
            self.assertEqual(output.read_bytes(), b'previous')
            self.assertEqual(list(Path(temporary).iterdir()), [output])
            publish(b'new', output, lambda p: None, overwrite=True)
            self.assertEqual(output.read_bytes(), b'new')

    def test_derived_input_collision_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for output in (root / 'sections' / '09_av.bin', root / 'cntent.dat'):
                with self.assertRaisesRegex(ValueError, 'collides'):
                    build_nonr_firmware(output, root / 'sections', root / 'cntent.dat', overwrite=True)

    def test_publication_race_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'out.dat'
            def concurrent_writer(staged):
                output.write_bytes(b'concurrent writer')
            with self.assertRaises(FileExistsError):
                publish(b'new', output, concurrent_writer)
            self.assertEqual(output.read_bytes(), b'concurrent writer')
            self.assertEqual(list(Path(temporary).iterdir()), [output])

    def test_container_padding_tamper_rejected(self):
        manifest, sections, payloads = self.baseline
        expected = list(payloads); expected[9] = patch_av_bin(payloads[9])
        raw = bytearray(assemble(manifest, expected, self.baseline.container))
        raw[-1] ^= 1
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'bad-padding.dat'; output.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'trailer'):
                verify_expected(output, self.baseline, manifest, expected)

    def test_unrelated_section_change_rejected_even_with_valid_hmac(self):
        manifest, sections, payloads = self.baseline
        expected = list(payloads); expected[9] = patch_av_bin(payloads[9])
        actual = list(expected); actual[0] = bytes([actual[0][0] ^ 1]) + actual[0][1:]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'bad.dat'; output.write_bytes(assemble(manifest, actual))
            with self.assertRaisesRegex(ValueError, 'section 0'):
                verify_expected(output, self.baseline, manifest, expected)


if __name__ == '__main__':
    unittest.main()
