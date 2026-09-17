"""Adversarial offline tests for the read-only repository auditor."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import repo_audit


class ArtifactAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'evidence').mkdir()
        self.data = b'first\nsecond\n'
        self.path = self.root / 'evidence/sample.dat'
        self.path.write_bytes(self.data)
        self.entry = dict(path='evidence/sample.dat', kind='file', bytes=len(self.data),
                          sha256=hashlib.sha256(self.data).hexdigest(), role='test fixture')
        self.manifest = dict(schema_version=1, artifacts=[self.entry], retained_duplicates=[])

    def test_exact_bytes_and_crlf_corruption(self):
        self.assertEqual(repo_audit.verify_artifacts(self.root, self.manifest), [])
        self.path.write_bytes(self.data.replace(b'\n', b'\r\n'))
        self.assertIn('Artifact bytes differ', repo_audit.verify_artifacts(self.root, self.manifest)[0])

    def test_same_size_mutation_is_rejected(self):
        self.path.write_bytes(self.data.replace(b'first', b'wrong'))
        self.assertTrue(repo_audit.verify_artifacts(self.root, self.manifest))

    def test_symlink_text_and_native_link_have_same_contract(self):
        target = b'/proc/self/fd'
        self.path.write_bytes(target)
        self.entry.update(kind='symlink', target=target.decode(), bytes=len(target), sha256=hashlib.sha256(target).hexdigest())
        self.assertEqual(repo_audit.verify_artifacts(self.root, self.manifest), [])
        # Native Windows symlink creation requires developer mode; mock only the
        # platform operation, while checking the same target-byte contract.
        with patch.object(Path, 'is_symlink', return_value=True), patch('repo_audit.os.readlink', return_value=target.decode()):
            self.assertEqual(repo_audit.artifact_bytes(self.path, 'symlink'), target)
        self.path.write_bytes(target + b'\n')
        self.assertTrue(repo_audit.verify_artifacts(self.root, self.manifest))

    def test_manifest_rejects_escape_duplicate_and_invalid_kind(self):
        self.entry['path'] = '../outside'
        self.assertTrue(repo_audit.verify_artifacts(self.root, self.manifest))
        self.entry['path'] = 'evidence/sample.dat'
        self.manifest['artifacts'].append(self.entry.copy())
        self.assertTrue(repo_audit.verify_artifacts(self.root, self.manifest))
        self.manifest['artifacts'].pop()
        self.entry['kind'] = 'directory'
        self.assertTrue(repo_audit.verify_artifacts(self.root, self.manifest))

    def test_manifest_version_is_checked(self):
        self.manifest['schema_version'] = 999
        self.assertTrue(repo_audit.verify_artifacts(self.root, self.manifest))

    def test_duplicate_requires_exact_explicit_group_and_reason(self):
        entry = dict(self.entry, path='evidence/other.dat')
        self.manifest['artifacts'].append(entry)
        self.assertTrue(repo_audit.verify_duplicates(self.manifest))
        group = dict(sha256=entry['sha256'], paths=[self.entry['path'], entry['path']], reason='Two distinct source filesystem paths')
        self.manifest['retained_duplicates'] = [group]
        self.assertEqual(repo_audit.verify_duplicates(self.manifest), [])
        group['paths'].append('not/a/file')
        self.assertTrue(repo_audit.verify_duplicates(self.manifest))

    def test_links_spaces_external_fragment_and_missing(self):
        doc = self.root / 'README.md'
        (self.root / 'file with spaces.txt').write_text('example')
        doc.write_text('[file](<file with spaces.txt>) [remote](https://example.test/a) [section](#section)\n')
        self.assertEqual(repo_audit.verify_local_links(self.root), [])
        doc.write_text('[broken](missing.txt)')
        self.assertEqual(len(repo_audit.verify_local_links(self.root)), 1)

    def test_unmanifested_artifact_detected_and_audit_is_read_only(self):
        path = self.root / 'evidence/artifact_manifest.json'
        path.write_text(json.dumps(self.manifest))
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = repo_audit.audit(self.root)
        self.assertTrue(result['ok'], result['errors'])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        (self.root / 'evidence/extra.dat').write_bytes(b'new')
        self.assertIn('Unmanifested artifact: evidence/extra.dat', repo_audit.audit(self.root)['errors'])

    def test_empty_directory_is_not_initialized_submodule(self):
        path = self.root / 'sources/qemu'
        path.mkdir(parents=True)
        with patch('repo_audit._git', return_value='160000 ' + 'a' * 40 + ' 0\tsources/qemu'), patch('repo_audit.shutil.which', return_value=None):
            state = repo_audit.submodule_status(self.root)[0]
        self.assertEqual(state['state'], 'empty')
        self.assertIsNone(state['actual_commit'])
        self.assertFalse(state['executable_available'])

    def test_wrong_revision_and_dirty_state_are_distinct(self):
        path = self.root / 'sources/qemu'
        path.mkdir(parents=True)
        (path / '.git').write_text('gitdir: ignored-test-fixture')
        with patch('repo_audit._git', side_effect=['160000 ' + 'a' * 40 + ' 0\tsources/qemu', 'b' * 40, ' M file']), patch('repo_audit.shutil.which', return_value=None):
            state = repo_audit.submodule_status(self.root)[0]
        self.assertEqual(state['state'], 'mismatch')
        self.assertTrue(state['dirty'])


if __name__ == '__main__':
    unittest.main()
