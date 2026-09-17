"""Verify a research manifest or create an explicitly reviewed editorial revision."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

BASE = Path(__file__).resolve().parent


def artifact_path(base: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if (not name or relative.is_absolute() or '\\' in name or ':' in name
            or '..' in relative.parts or relative.as_posix() != name):
        raise ValueError(f'Expected a normalized relative artifact path: {name}')
    path = base / name
    if not path.resolve().is_relative_to(base.resolve()) or path.is_symlink():
        raise ValueError(f'Artifact escapes base or is a symlink: {name}')
    return path


def record(base: Path, name: str) -> dict:
    data = artifact_path(base, name).read_bytes()
    return dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def entries(data: dict) -> dict[str, dict]:
    if data.get('schema_version') != 1 or not isinstance(data.get('artifacts'), list):
        raise ValueError('Unsupported or malformed manifest')
    rows = {}
    for row in data['artifacts']:
        name = row['path']
        if name in rows:
            raise ValueError(f'Duplicate artifact: {name}')
        rows[name] = row
    return rows


def verify(base: Path, data: dict) -> None:
    for name, expected in entries(data).items():
        if record(base, name) != expected:
            raise ValueError(f'Artifact bytes differ: {name}')


def create_revision(base: Path, baseline_name: str, revision: int,
                    changes: list[str], additions: list[str]) -> dict:
    """Preserve prior pins except explicitly named maintained prose/code.

    New files require an explicit addition; unrelated local downloads and caches
    are never swept into a publication. This function does not write files.
    """
    baseline_path = artifact_path(base, baseline_name)
    if baseline_name == 'package_manifest.json':
        raise ValueError('Preserve a separate baseline before creating a revision')
    old = json.loads(baseline_path.read_text(encoding='utf-8'))
    previous = entries(old)
    if revision <= old.get('editorial_revision', 0):
        raise ValueError('Editorial revision must increase')
    for label, names in [('changes', changes), ('additions', additions)]:
        if len(names) != len(set(names)):
            raise ValueError(f'Duplicate {label}')
    changed = set(changes)
    added = set(additions)
    if changed - previous.keys():
        raise ValueError(f'Changes absent from baseline: {sorted(changed - previous.keys())}')
    if added & previous.keys() or changed & added:
        raise ValueError('Additions must be new artifact paths')
    if 'package_manifest.json' in added or baseline_name in changed:
        raise ValueError('Current and historical manifests cannot be rewritten as artifacts')
    for name in changed:
        path = artifact_path(base, name)
        maintained = name.startswith('reports/') or len(PurePosixPath(name).parts) == 1
        if not maintained or path.suffix not in {'.md', '.py', '.ps1'}:
            raise ValueError(f'Preserved data cannot be editorially changed: {name}')
    rows = {}
    differences = []
    for name, expected in previous.items():
        actual = record(base, name)
        if actual != expected:
            if name not in changed:
                raise ValueError(f'Unapproved artifact change: {name}')
            differences.append(dict(path=name, previous_sha256=expected['sha256'],
                                    current_sha256=actual['sha256']))
        rows[name] = actual
    for name in sorted(added | {baseline_name}):
        actual = record(base, name)
        if name in rows and rows[name] != actual:
            raise ValueError(f'Historical baseline changed: {name}')
        rows[name] = actual
    data = dict(old)
    data.update(editorial_revision=revision, historical_manifest=baseline_name,
                editorial_changes=differences,
                added_artifacts=sorted(rows.keys() - previous.keys()),
                artifacts=[rows[name] for name in sorted(rows)])
    verify(base, data)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['create', 'verify'])
    parser.add_argument('--baseline', help='Preserved manifest path relative to build/w300')
    parser.add_argument('--revision', type=int)
    parser.add_argument('--change', action='append', default=[], help='Explicit maintained path to update')
    parser.add_argument('--add', action='append', default=[], help='Explicit new artifact path')
    args = parser.parse_args()
    path = BASE / 'package_manifest.json'
    try:
        if args.command == 'create':
            if args.baseline is None or args.revision is None:
                parser.error('create requires --baseline and --revision')
            data = create_revision(BASE, args.baseline, args.revision, args.change, args.add)
            temporary = path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8', newline='\n')
            temporary.replace(path)
        else:
            if args.baseline or args.revision is not None or args.change or args.add:
                parser.error('revision options apply only to create')
            data = json.loads(path.read_text(encoding='utf-8'))
            verify(BASE, data)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Manifest verification failed: {error}\n')
    print(json.dumps(dict(ok=True, editorial_revision=data.get('editorial_revision'),
                          artifacts=len(data['artifacts']))))


if __name__ == '__main__':
    main()
