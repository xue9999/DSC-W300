"""Run required offline checks and write an environment-specific JSON report."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def audit() -> dict:
    result = subprocess.run([sys.executable, str(ROOT / 'tools/repo_audit.py'), '--json'],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    return {'exit_code': result.returncode, 'result': json.loads(result.stdout),
            'stderr': result.stderr}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT / 'build/test-results.json')
    args = parser.parse_args()
    os.environ['PYTHONUTF8'] = '1'
    os.chdir(ROOT)
    before = audit()
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tools'), pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after = audit()
    success = (result.wasSuccessful() and not result.skipped and
               before['exit_code'] == after['exit_code'] == 0)
    report = {
        'status': 'passed' if success else 'failed',
        'scope': 'offline code, artifacts and simulation contracts; no hardware qualification',
        'hardware_validation': 'not_performed',
        'started_utc': started, 'duration_seconds': round(time.monotonic() - clock, 3),
        'environment': {'python': sys.version, 'platform': platform.platform()},
        'revision': git('rev-parse', 'HEAD'),
        'working_tree_changes': git('status', '--porcelain'),
        'tests_run': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skipped': [(str(t), why) for t, why in result.skipped],
        'failure_details': [(str(t), trace) for t, trace in result.failures + result.errors],
        'audit_before': before, 'audit_after': after,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Offline report: {args.report} ({report["status"]})')
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
