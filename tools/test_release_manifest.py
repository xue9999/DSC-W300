"""Editorial revisions preserve raw evidence and require explicit publication scope."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'build/w300/release_manifest.py'
spec = importlib.util.spec_from_file_location('release_manifest', SCRIPT)
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)


class EditorialManifestTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name)
        for name, value in [('reports/guide.md', b'Original finding\n'),
                            ('reports/trace.json', b'{"verified":false}\n')]:
            path = self.base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        self.old = dict(schema_version=1, editorial_revision=3,
                        camera_communication_verified=False,
                        w300_language_write_verified=False, pmca_commit='pinned',
                        artifacts=[manifest.record(self.base, name) for name in
                                   ['reports/guide.md', 'reports/trace.json']])
        self.baseline = self.base / 'manifests/r3.json'
        self.baseline.parent.mkdir()
        self.original = (json.dumps(self.old) + '\n').encode()
        self.baseline.write_bytes(self.original)

    def create(self, changes=(), additions=(), revision=4):
        return manifest.create_revision(self.base, 'manifests/r3.json', revision,
                                        list(changes), list(additions))

    def test_explicit_revision_preserves_baseline_raw_flags_and_ignores_unlisted_files(self):
        (self.base / 'reports/guide.md').write_text('Finding and next action\n')
        (self.base / 'reports/new.json').write_text('{"camera_io":false}\n')
        (self.base / 'unrelated.bin').write_bytes(b'unreviewed')
        data = self.create(['reports/guide.md'], ['reports/new.json'])
        manifest.verify(self.base, data)
        self.assertEqual(self.baseline.read_bytes(), self.original)
        self.assertEqual(data['editorial_revision'], 4)
        self.assertFalse(data['camera_communication_verified'])
        self.assertFalse(data['w300_language_write_verified'])
        rows = manifest.entries(data)
        self.assertEqual(rows['reports/trace.json'], self.old['artifacts'][1])
        self.assertNotIn('unrelated.bin', rows)
        self.assertEqual(data['historical_manifest'], 'manifests/r3.json')

    def test_unapproved_editorial_change_is_rejected(self):
        (self.base / 'reports/guide.md').write_text('Changed')
        with self.assertRaisesRegex(ValueError, 'Unapproved'):
            self.create()

    def test_raw_data_change_cannot_be_authorized_as_editorial(self):
        (self.base / 'reports/trace.json').write_text('{"verified":true}')
        for changes in [[], ['reports/trace.json']]:
            with self.assertRaises(ValueError):
                self.create(changes)

    def test_missing_input_does_not_drop_a_pin(self):
        (self.base / 'reports/trace.json').unlink()
        with self.assertRaises(OSError):
            self.create()

    def test_rejects_bad_revision_duplicate_paths_and_escape(self):
        for revision in [2, 3]:
            with self.assertRaises(ValueError):
                self.create(revision=revision)
        for names in [['reports/guide.md'], ['../outside'], ['/absolute'],
                      ['reports/new.json', 'reports/new.json'], ['package_manifest.json']]:
            with self.assertRaises(ValueError):
                self.create(additions=names)
        self.old['artifacts'].append(self.old['artifacts'][0])
        with self.assertRaisesRegex(ValueError, 'Duplicate artifact'):
            manifest.entries(self.old)


if __name__ == '__main__':
    unittest.main()
