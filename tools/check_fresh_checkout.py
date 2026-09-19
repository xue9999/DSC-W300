"""Verify local changes in a fresh Windows-style checkout without staging/committing.

An alternate index captures the current worktree. A separate local clone checks
out that tree with autocrlf=true and symlinks=false, then runs required checks.
The temporary checkout is retained for inspection; no original index is changed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


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


def main() -> int:
    scratch = Path(tempfile.mkdtemp(prefix='dsc-fresh-check-')).resolve()
    checkout = scratch / 'checkout'
    index = scratch / 'snapshot.index'
    git_path = git_bin()
    git_dir = str(Path(git_path).parent) if Path(git_path).is_file() else ''
    env_path = f"{git_dir};{os.environ.get('PATH', '')}" if git_dir else os.environ.get('PATH', '')
    environment = dict(os.environ, GIT_INDEX_FILE=str(index), PYTHONUTF8='1', PATH=env_path)

    def git(*args, cwd=ROOT, env=None):
        return subprocess.check_output([git_path, *args], cwd=cwd, env=env,
                                       stderr=subprocess.PIPE, text=True).strip()

    original_index = ROOT / '.git/index'
    # get the correct index path even if this tool is run from a Git worktree
    original_index = Path(git('rev-parse', '--path-format=absolute', '--git-path', 'index'))
    before = original_index.read_bytes()
    git('read-tree', 'HEAD', env=environment)
    git('add', '--all', env=environment)
    tree = git('write-tree', env=environment)
    if original_index.read_bytes() != before:
        raise RuntimeError('Original Git index unexpectedly changed')
    git('clone', '--shared', '--no-checkout', str(ROOT), str(checkout))
    git('config', 'core.autocrlf', 'true', cwd=checkout)
    git('config', 'core.symlinks', 'false', cwd=checkout)
    git('read-tree', tree, cwd=checkout)
    git('checkout-index', '--all', cwd=checkout)
    print(f'Fresh checkout: {checkout}\nSnapshot tree: {tree}', flush=True)
    result = subprocess.run([sys.executable, 'tools/run_checks.py'], cwd=checkout,
                            env=dict(os.environ, PYTHONUTF8='1'))
    report = checkout / 'build/test-results.json'
    destination = ROOT / 'build/fresh-checkout-results.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    if report.exists():
        data = json.loads(report.read_text(encoding='utf-8'))
        data['snapshot_tree'] = tree
        data['checkout_directory'] = str(checkout)
        data['checkout_settings'] = {'core.autocrlf': True, 'core.symlinks': False}
        data['original_index_unchanged'] = original_index.read_bytes() == before
        destination.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    if original_index.read_bytes() != before:
        raise RuntimeError('Original Git index unexpectedly changed')
    print(f'Fresh checkout report: {destination}')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
