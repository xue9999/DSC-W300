"""Verify the newly acquired offline material and reproduce bounded static decoding.

No USB, network, firmware execution, or writes to original sources/evidence.
Run with build/w300/venv/Scripts/python.exe from any working directory.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
ROOT = BUILD.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_manifest(relative, key, path_key, base):
    manifest = BUILD / relative
    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    rows = data[key] if key else data
    for row in rows:
        path = base / row[path_key]
        assert path.is_file(), str(path)
        assert path.stat().st_size == row["bytes"], str(path)
        assert sha(path) == row["sha256"].lower(), str(path)
    return {"manifest": relative, "entries_verified": len(rows), "passed": True}


checks = [
    check_manifest("downloads/w300-l3-reference/acquisition.json", "files", "path",
                   BUILD / "downloads/w300-l3-reference"),
    check_manifest("downloads/seusex-public-20260916/artifact-manifest.json", None, "file",
                   BUILD / "downloads/seusex-public-20260916"),
    check_manifest("downloads/sony-ptp-2008/download-manifest.json", None, "file",
                   BUILD / "downloads/sony-ptp-2008"),
    check_manifest("downloads/eligibility-bulletins-20260916-r1/acquisition.json", None, "path", ROOT),
]
outputs = [HERE / "fallback11" / name for name in
           ("fallback11-evidence.json", "fallback11.asm.txt")]
before = {p.name: sha(p) for p in outputs}
replay = subprocess.run([sys.executable, str(HERE / "fallback11/inspect_fallback11.py")],
                        cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
assert replay.returncode == 0, replay.stderr
after = {p.name: sha(p) for p in outputs}
assert before == after, "Static reproduction changed the recorded outputs"
diff = subprocess.run(["git", "diff", "--check", "--", "ANALYSIS_LOG.md",
                       "docs/w300/EXECUTION_PLAN.md", "docs/w300/VERIFICATION.md"],
                      cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
assert diff.returncode == 0, diff.stdout + diff.stderr
result = {
    "scope": "Resumed offline acquisition and static analysis; no hardware certification",
    "acquisition_manifests": checks,
    "fallback_reproduction": {"exit_code": replay.returncode, "outputs_identical": True,
                              "output_sha256": after, "stdout": replay.stdout.strip()},
    "documentation_diff_check": {"exit_code": diff.returncode},
    "l3_independent_review": "No material correction reported after checking source pages and scope",
    "camera_commands_sent": False,
    "new_camera_executable_acquired": False,
    "w300_language_operation_qualified": False,
    "previous_runtime_checks_repeated": False,
}
destination = HERE / "offline-resumption-checks.json"
destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
