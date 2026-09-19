#!/usr/bin/env python3
"""Read-only integrity, local Markdown-link and dependency audit. Never repairs files.

The artifact manifest records an integrity baseline, not vendor authenticity or
hardware validation. Firmware symlinks are checked as target text without being
followed, including Git's ordinary-file representation on Windows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent


def safe_path(root: Path, name: str) -> Path:
    """Reject ambiguous or escaping manifest paths without following the leaf link."""
    p = PurePosixPath(name)
    if not name or p.is_absolute() or '\\' in name or ':' in name or '..' in p.parts:
        raise ValueError(f"Unsafe artifact path: {name!r}")
    path = root.joinpath(*p.parts)
    if root.resolve() not in path.parent.resolve().parents and path.parent.resolve() != root.resolve():
        raise ValueError(f"Artifact parent escapes repository: {name}")
    return path


def artifact_bytes(path: Path, kind: str) -> bytes:
    if kind == 'symlink':
        return os.readlink(path).encode('utf-8') if path.is_symlink() else path.read_bytes()
    if path.is_symlink():
        raise ValueError('Regular artifact unexpectedly replaced with a symlink')
    return path.read_bytes()


def verify_artifacts(root: Path, manifest: dict) -> list[str]:
    errors = []
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('artifacts'), list):
        return ['Unsupported or malformed artifact manifest']
    seen = set()
    for item in manifest['artifacts']:
        try:
            name = item['path']
            if name in seen:
                raise ValueError(f'Duplicate manifest path: {name}')
            seen.add(name)
            if item['kind'] not in ('file', 'symlink'):
                raise ValueError(f'Unsupported artifact kind: {name}')
            if not re.fullmatch(r'[0-9a-f]{64}', item['sha256']) or not item.get('role'):
                raise ValueError(f'Malformed hash or missing role: {name}')
            data = artifact_bytes(safe_path(root, name), item['kind'])
            if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError(f'Artifact bytes differ: {name}')
            if item['kind'] == 'symlink' and data != item['target'].encode('utf-8'):
                raise ValueError(f'Symlink target differs: {name}')
        except (KeyError, TypeError, ValueError, OSError) as exc:
            errors.append(str(exc))
    return errors


def verify_duplicates(manifest: dict) -> list[str]:
    """Every equal-content regular-file group needs an explicit retention reason."""
    groups = {}
    for item in manifest.get('artifacts', []):
        if item.get('kind') == 'file':
            groups.setdefault(item.get('sha256'), []).append(item['path'])
    expected = {digest: sorted(paths) for digest, paths in groups.items() if len(paths) > 1}
    declared = {}
    errors = []
    for group in manifest.get('retained_duplicates', []):
        if not group.get('reason') or group.get('sha256') in declared:
            errors.append('Duplicate exception needs one unique hash and a reason')
        declared[group.get('sha256')] = sorted(group.get('paths', []))
    if expected != declared:
        errors.append('Unexplained or stale duplicate groups in artifact manifest')
    return errors


def covered_artifact_paths(root: Path) -> set[str]:
    """Immutable material only; editorial Markdown and submodule contents excluded."""
    found = set()
    submodules = {'OpenMemories-CI', 'Sony-PMCA-RE', 'fwtool.py', 'qemu'}
    for prefix in ('sources', 'evidence'):
        for directory, dirs, files in os.walk(root / prefix, followlinks=False):
            if Path(directory) == root / 'sources':
                dirs[:] = [d for d in dirs if d not in submodules]
            for filename in files + [d for d in dirs if (Path(directory) / d).is_symlink()]:
                path = Path(directory) / filename
                name = path.relative_to(root).as_posix()
                if name == 'evidence/artifact_manifest.json':
                    continue
                if prefix == 'evidence' and path.suffix.lower() == '.md':
                    continue
                if prefix == 'sources' and path.suffix.lower() == '.md' and name != 'sources/original-research-report.md':
                    continue
                found.add(name)
    return found


def verify_local_links(root: Path, documents: list[Path] | None = None) -> list[str]:
    """Check relative Markdown destinations; external URLs and anchors stay offline."""
    if documents is None:
        documents = list(root.glob('*.md')) + list((root / 'docs').rglob('*.md'))
        # Historical evidence and original research retain their original links;
        # their dated context does not describe current checkout navigation.
        documents += [root / 'evidence/README.md', root / 'evidence/DECRYPTED_ARCHITECTURE.md']
        documents += [p for p in (root / 'sources').glob('*/README.md')]
    errors = []
    for document in documents:
        if not document.is_file():
            continue
        content = re.sub(r'```.*?```', '', document.read_text(encoding='utf-8'), flags=re.S)
        destinations = re.findall(r'\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)', content)
        destinations += re.findall(r'^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)', content, flags=re.M)
        for dest in destinations:
            dest = dest.strip('<>')
            parsed = urlsplit(dest)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = document.parent / unquote(parsed.path)
            if not path.exists():
                errors.append(f'{document.relative_to(root).as_posix()}: missing link {dest}')
    return errors


def git_bin() -> str:
    found = shutil.which('git')
    if found:
        return found
    for c in [
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Git/cmd/git.exe',
        Path('C:/Program Files/Git/cmd/git.exe'),
        Path('C:/Program Files (x86)/Git/cmd/git.exe'),
    ]:
        if c.is_file():
            return str(c)
    return 'git'


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output([git_bin(), '-C', str(root), *args], stderr=subprocess.DEVNULL, text=True).strip()


def submodule_status(root: Path = REPO_ROOT) -> list[dict]:
    """Inspect gitlinks without fetching sources or executing a dependency binary."""
    try:
        lines = _git(root, 'ls-files', '-s').splitlines()
    except (OSError, subprocess.CalledProcessError):
        return []
    result = []
    for line in lines:
        meta, name = line.split('\t', 1)
        mode, expected, _ = meta.split()
        if mode != '160000':
            continue
        path = root / name
        actual = None
        dirty = None
        if not path.exists():
            state = 'missing'
        elif not any(path.iterdir()):
            state = 'empty'
        elif not (path / '.git').exists():
            state = 'uninitialized'
        else:
            try:
                actual = _git(path, 'rev-parse', 'HEAD')
                dirty = bool(_git(path, 'status', '--porcelain'))
                state = 'pinned' if actual == expected else 'mismatch'
            except (OSError, subprocess.CalledProcessError):
                state = 'uninitialized'
        executable = None
        if name == 'sources/qemu':
            candidates = [path / 'arm-softmmu/qemu-system-arm', path / 'build/qemu-system-arm']
            if os.name == 'nt':
                candidates += [p.with_suffix('.exe') for p in candidates]
            executable = next((str(p) for p in candidates if p.is_file() and os.access(p, os.X_OK)), None)
            executable = executable or shutil.which('qemu-system-arm')
        result.append(dict(path=name, expected_commit=expected, actual_commit=actual,
                           state=state, dirty=dirty, executable_available=bool(executable),
                           executable_path=executable, executable_capabilities_verified=False))
    return result


def audit(root: Path = REPO_ROOT, manifest_path: Path | None = None) -> dict:
    root = root.resolve()
    manifest_path = manifest_path or root / 'evidence/artifact_manifest.json'
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        errors = verify_artifacts(root, manifest) + verify_duplicates(manifest)
        declared = {entry['path'] for entry in manifest.get('artifacts', [])}
        actual = covered_artifact_paths(root)
        errors += [f'Unmanifested artifact: {p}' for p in sorted(actual - declared)]
        errors += [f'Manifest artifact absent from material scope: {p}' for p in sorted(declared - actual)]
    except (OSError, ValueError, TypeError, KeyError) as exc:
        manifest = {}
        errors = [f'Cannot validate manifest: {exc}']
    errors += verify_local_links(root)
    dependencies = submodule_status(root)
    errors += [f'Submodule revision differs: {s["path"]}' for s in dependencies if s['state'] == 'mismatch']
    errors += [f'Submodule has local changes: {s["path"]}' for s in dependencies if s.get('dirty')]
    return {'ok': not errors, 'scope': 'offline file integrity and local links; no hardware validation',
            'artifacts_checked': len(manifest.get('artifacts', [])), 'errors': errors,
            'dependencies': dependencies}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=REPO_ROOT)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--json', action='store_true', help='Print machine-readable report to stdout')
    args = parser.parse_args()
    result = audit(args.root, args.manifest)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{'PASS' if result['ok'] else 'FAIL'}: {result['artifacts_checked']} artifacts; {result['scope']}")
        for error in result['errors']:
            print(f'ERROR: {error}')
        for dep in result['dependencies']:
            print(f"{dep['path']}: {dep['state']}; executable available={dep['executable_available']}; capabilities unverified")
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
