#!/usr/bin/env python3
"""
Unit and regression test suite for g3_text_poc.py.
Benchmarked against SONY_NX3_Reversal (test_nx3_text_poc.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
import unittest
import tempfile
import io
import tarfile

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from g3_text_poc import (
    patch_csv_text,
    update_manifest,
    build_block_header,
    generate_poc_firmware,
    verify_poc_image,
    require,
    patch_original_tar,
)
from g3_firmware_parser import CXD4108MsCrypter, KEY_CXD4108_MS, MANIFEST_SIZE


class TestG3TextPoc(unittest.TestCase):
    def setUp(self):
        self.crypter = CXD4108MsCrypter(KEY_CXD4108_MS)
        self.sample_csv = (
            "SETUP_TVTYPE,TV Type\n"
            "SETUP_UPDATE,Update\n"
            "SETUP_VERSION,Version\n"
            "SETUP_VIDEOOUT,Video Out\n"
        )

    def test_patch_csv_success(self):
        patched = patch_csv_text(self.sample_csv, "SETUP_VERSION", "Version", "G3 POC")
        self.assertIn("SETUP_VERSION,G3 POC\n", patched)
        self.assertNotIn("SETUP_VERSION,Version\n", patched)
        self.assertIn("SETUP_TVTYPE,TV Type\n", patched)

    def test_patch_csv_missing_key(self):
        with self.assertRaises(ValueError) as ctx:
            patch_csv_text(self.sample_csv, "NONEXISTENT_KEY", "Version", "G3 POC")
        self.assertIn("Expected exactly 1 occurrence", str(ctx.exception))

    def test_patch_csv_mismatched_old_val(self):
        with self.assertRaises(ValueError) as ctx:
            patch_csv_text(self.sample_csv, "SETUP_VERSION", "WrongOldVal", "G3 POC")
        self.assertIn("does not match expected", str(ctx.exception))

    def test_patch_csv_duplicate_key(self):
        duplicate_csv = self.sample_csv + "SETUP_VERSION,Duplicate\n"
        with self.assertRaises(ValueError) as ctx:
            patch_csv_text(duplicate_csv, "SETUP_VERSION", "Version", "G3 POC")
        self.assertIn("Expected exactly 1 occurrence", str(ctx.exception))

    def test_block_header_crypto_validity(self):
        test_payload = b"Sample payload for CXD4108 MsFirm header test"
        enc = self.crypter.cipher(test_payload)
        hdr = build_block_header(self.crypter, enc)
        self.assertEqual(len(hdr), 128)
        self.assertTrue(self.crypter.check_header_hash(hdr))
        self.assertTrue(self.crypter.check_data_hash(hdr, enc))

    def test_manifest_checksum_recalculation(self):
        # A synthetic manifest exercises metadata updates without external artifacts.
        body = '[total number of files]\ntotal_num=18\n'
        for i in range(24):
            body += ('[header]\n' if i == 0 else '[program data]\n')
            name = 'fskapp1.tar' if i == 10 else f'fixture{i}.bin'
            body += f'fnum={i:02x}\nname={name}\noffset={20480+i:08x}\nsize=1\ncksum=0\n'
        body = body.encode().ljust(MANIFEST_SIZE - 64, b' ')
        header = f'FV 02\nSV 02\n\n[alsiz]\ndatasize={len(body):08x}\n\n[hdsm]\nchksum={sum(body):08x}\n\n'.encode()
        orig_cntent = header + body
        new_cntent, meta = update_manifest(orig_cntent, 10, "fskapp1.tar", 0x2A8000)
        self.assertEqual(len(new_cntent), MANIFEST_SIZE)
        
        # Verify checksum
        hdr_chksum = int(new_cntent[:0x40].decode('ascii').split('chksum=')[1].split('\n')[0], 16)
        computed_chksum = sum(new_cntent[0x40:]) & 0xffffffff
        self.assertEqual(hdr_chksum, computed_chksum)

    def test_invalid_string_rejected(self):
        for value in ('', 'too long', 'x\ny', 'x,y', '\x00'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                patch_csv_text(self.sample_csv, 'SETUP_VERSION', 'Version', value)

    def test_tar_target_is_exact_and_unrelated_bytes_preserved(self):
        data = self.sample_csv.encode()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w') as archive:
            for name, payload in [('decoy/eng.csv', data), ('dsc/app/scripts/language/eng.csv', data)]:
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
        original = buf.getvalue()
        patched = patch_original_tar(original, 'G3 POC')
        self.assertEqual(len(patched), len(original))
        with tarfile.open(fileobj=io.BytesIO(patched)) as archive:
            self.assertEqual(archive.extractfile('decoy/eng.csv').read(), data)
            self.assertIn(b'SETUP_VERSION,G3 POC \n', archive.extractfile('dsc/app/scripts/language/eng.csv').read())
        only_decoy = io.BytesIO()
        with tarfile.open(fileobj=only_decoy, mode='w') as archive:
            info = tarfile.TarInfo('decoy/eng.csv'); info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            patch_original_tar(only_decoy.getvalue(), 'G3 POC')

    def test_generate_and_verify_real_poc(self):
        from g3_verified import trusted_source
        manifest, sections, payloads = trusted_source()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extracted = root / 'sections'; extracted.mkdir()
            for i, (section, payload) in enumerate(zip(sections, payloads)):
                (extracted / f'{i:02d}_{section["name"]}').write_bytes(payload)
            cntent = root / 'cntent.dat'; cntent.write_bytes(manifest)
            output = root / 'poc.dat'
            generate_poc_firmware('G3 POC', output, sections_dir=extracted, cntent_path=cntent)
            result = verify_poc_image(output)
            self.assertEqual(result['status'], 'OFFLINE_INTEGRITY_VERIFIED')
            self.assertEqual(result['hardware_validation'], 'not_performed')
            with self.assertRaisesRegex(ValueError, 'exists'):
                generate_poc_firmware('G3 POC', output)


if __name__ == '__main__':
    unittest.main()
