"""Reproduce the new bounded protocol analysis, without USB or firmware execution.

Each job was source-reviewed as a static file reader before inclusion here.
Previous environment, portable-package and whole-repository checks are not repeated.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
ROOT = BUILD.parents[1]

JOBS = [
    ("reports/g3-host-interface/inspect_host.py", ["reports/g3-host-interface/inventory.json"]),
    ("reports/g3-host-interface/decode_host.py", ["reports/g3-host-interface/host-interface.asm.txt"]),
    ("reports/g3-host-interface/compare_pmca.py", ["reports/g3-host-interface/pmca-comparison.json"]),
    ("reports/av-page-init/inspect_page_init.py", ["reports/av-page-init/evidence.json", "reports/av-page-init/page-init.asm.txt"]),
    ("reports/av-page-init/linux-persistence/decode.py", ["reports/av-page-init/linux-persistence/linux-backup.asm.txt"]),
    ("reports/av-page-init/linux-persistence/tables.py", ["reports/av-page-init/linux-persistence/linux-backup-tables.txt"]),
    ("reports/g3-bank-map/inspect_bank_map.py", ["reports/g3-bank-map/bank-map.asm.txt", "reports/g3-bank-map/evidence.json"]),
    ("downloads/g3-gpl-reference/compare_gpl.py", [
        "downloads/g3-gpl-reference/g3.config", "downloads/g3-gpl-reference/w300.config",
        "downloads/g3-gpl-reference/config.diff", "downloads/g3-gpl-reference/config-comparison.json"]),
    ("reports/g3-usb-descriptor/reproduce.py", [
        "reports/g3-usb-descriptor/libusb-chain.asm.txt", "reports/g3-usb-descriptor/libsencore-chain.asm.txt",
        "reports/g3-usb-descriptor/kernel-unified_drv.ko.json", "reports/g3-usb-descriptor/kernel-unified_drv2.ko.json",
        "reports/g3-usb-descriptor/kernel-sen-driver.asm.txt", "reports/g3-usb-descriptor/descriptor-evidence.json",
        "reports/g3-usb-descriptor/g3-gpl-gadgetcore/usb_gadgetcore.h",
        "reports/g3-usb-descriptor/g3-gpl-gadgetcore/usb_gcore_desc.c",
        "reports/g3-usb-descriptor/g3-gpl-gadgetcore/usb_gcore_main.c"]),
    ("downloads/g3-gpl-reference/compare_usb_core.py", ["downloads/g3-gpl-reference/usb-core-comparison.json"]),
    ("reports/g3-module-recovery/recover_module.py", ["reports/g3-module-recovery/recovery-evidence.json",
                                                   "reports/g3-module-recovery/unified_drv.complete.ko"]),
    ("reports/g3-module-recovery/independent_review.py", ["reports/g3-module-recovery/independent-review.json"]),
    ("reports/g3-normal-entry/reproduce.py", ["reports/g3-normal-entry/entry-inventory.json",
        "reports/g3-normal-entry/entry-evidence.json", "reports/g3-normal-entry/xsb-inventory.json",
        "reports/g3-normal-entry/native-links.asm.txt", "reports/g3-normal-entry/core-normal-auth.asm.txt",
        "reports/g3-normal-entry/usb-registration.asm.txt"]),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", choices=[script for script, _ in JOBS],
                        help="Run only selected new or changed checks; default: all")
    parser.add_argument("--output", default="offline-protocol-checks.json",
                        help="Report filename within this directory")
    args = parser.parse_args()
    assert Path(args.output).name == args.output and args.output.endswith(".json")
    results = []
    for script, outputs in JOBS:
        if args.only and script not in args.only:
            continue
        before = {name: sha(BUILD / name) for name in outputs}
        run = subprocess.run([sys.executable, str(BUILD / script)], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert run.returncode == 0, (script, run.stdout, run.stderr)
        after = {name: sha(BUILD / name) for name in outputs}
        assert before == after, (script, "output changed during reproduction")
        results.append({"script": script, "script_sha256": sha(BUILD / script),
                        "exit_code": run.returncode, "outputs_identical": True,
                        "outputs": after, "stdout": run.stdout.strip()})
    docs = ["ANALYSIS_LOG.md", "docs/w300/EXECUTION_PLAN.md", "docs/w300/VERIFICATION.md"]
    for name in docs:
        data = (ROOT / name).read_text(encoding="utf-8-sig")
        assert data.endswith("\n"), name
        assert all(line == line.rstrip() for line in data.splitlines()), name
        assert not any(line.startswith(("<<<<<<<", ">>>>>>>")) for line in data.splitlines()), name
    diff = subprocess.run(["git", "diff", "--check", "--", *docs], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8")
    assert diff.returncode == 0, diff.stdout + diff.stderr
    result = {
        "scope": "Static G3 protocol analysis and exact-model official GPL comparison; no hardware qualification",
        "jobs": results,
        "documentation": {"whitespace_and_conflict_check": True, "git_diff_check": True,
                          "checkpoint_hashes": {name: sha(ROOT / name) for name in docs}},
        "camera_commands_sent": False,
        "firmware_executed": False,
        "w300_language_operation_qualified": False,
        "portable_runtime_checks_repeated": False,
    }
    (HERE / args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "jobs": len(results), "outputs_identical": True,
                      "documentation_checks_passed": True, "w300_language_operation_qualified": False}, indent=2))


if __name__ == "__main__":
    main()
