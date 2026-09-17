"""Cross-platform availability and immutable-output contracts."""
import io
import os
import tarfile
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cxd4108_emulator import qemu_launcher
from g3_firmware_parser import generate_architecture_markdown, safe_extract_tar

ROOT = Path(__file__).resolve().parents[1]


class RepositoryContracts(unittest.TestCase):
    def test_source_directory_does_not_imply_booted_emulator(self):
        with patch.object(qemu_launcher, 'find_qemu_binary', return_value=None), \
             patch.object(qemu_launcher, 'submodule_status', return_value=[{'state': 'empty'}]):
            result = qemu_launcher.Cxd4108QemuLauncher().get_status()
        self.assertFalse(result['qemu_available'])
        self.assertFalse(result['machine_cxd4108_verified'])
        self.assertFalse(result['emulator_boot_validated'])
        self.assertEqual(result['submodules'][0]['state'], 'empty')

    def test_arbitrary_executable_is_not_qualified_qemu(self):
        with tempfile.TemporaryDirectory() as td:
            executable = Path(td) / 'qemu-system-arm'
            executable.write_bytes(b'not qemu')
            with patch.object(qemu_launcher, 'check_machine_cxd4108', return_value=False), \
                 patch.object(qemu_launcher.shutil, 'which', return_value=None):
                self.assertIsNone(qemu_launcher.find_qemu_binary(str(executable)))

    def test_parser_refuses_preserved_output_even_with_info(self):
        for name in ('sources', 'evidence', 'evidence/extracted_g3'):
            result = subprocess.run([sys.executable, str(ROOT / 'tools/g3_firmware_parser.py'),
                                     '--output', str(ROOT / name), '--info'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('cannot overwrite preserved', result.stderr)

    def test_tar_repeat_preserves_equal_bytes_but_repairs_changed_data(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w') as archive:
            entry = tarfile.TarInfo('payload.bin')
            entry.size = 4
            archive.addfile(entry, io.BytesIO(b'data'))
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'payload.bin'
            safe_extract_tar(buffer.getvalue(), td)
            os.utime(target, (1000, 1000))
            safe_extract_tar(buffer.getvalue(), td)
            self.assertEqual(target.stat().st_mtime, 1000)
            target.write_bytes(b'edit')
            safe_extract_tar(buffer.getvalue(), td)
            self.assertEqual(target.read_bytes(), b'data')

    def test_generated_architecture_does_not_invent_a_new_hardware_result(self):
        inventory = json.loads((ROOT / 'evidence/decrypted_inventory.json').read_text())
        inventory['platform']['elf_file_count'] = 123
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / 'report.md'
            generate_architecture_markdown(inventory, output)
            content = output.read_text()
        self.assertIn('Observed ELF files: 123', content)
        self.assertIn('research descriptions', content)
        self.assertIn('Next qualification:', content)
        self.assertIn('offline experiments', content)
        self.assertNotIn('100%', content)
        self.assertNotIn('HXR-NX3', content)


if __name__ == '__main__':
    unittest.main()
