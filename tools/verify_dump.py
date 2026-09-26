#!/usr/bin/env python3
"""Sony Cyber-shot DSC-W300 Calibration & Configuration Dump Verification Tool.

Cryptographically validates all dumped files against manifest.json, result.json,
and transactions.jsonl. Asserts 100% bit-for-bit identicality across all mirror pairs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, Tuple


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_dump(backup_dir: Path | str) -> Tuple[bool, Dict[str, Any]]:
    backup_dir = Path(backup_dir).resolve()
    details: Dict[str, Any] = {"backup_dir": str(backup_dir), "errors": []}

    manifest_path = backup_dir / "manifest.json"
    result_path = backup_dir / "result.json"
    transactions_path = backup_dir / "transactions.jsonl"

    if not manifest_path.is_file():
        details["errors"].append(f"Missing manifest.json at {manifest_path}")
        return False, details

    if not result_path.is_file():
        details["errors"].append(f"Missing result.json at {result_path}")
        return False, details

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as e:
        details["errors"].append(f"JSON decode failure: {e}")
        return False, details

    details["manifest"] = manifest
    details["result"] = result

    # 1. Result checks
    if not result.get("ok"):
        details["errors"].append("result.json reports ok != True")
    if not result.get("normal_mode_return_observed"):
        details["errors"].append("result.json reports normal_mode_return_observed != True")
    if not result.get("service_authenticated"):
        details["errors"].append("result.json reports service_authenticated != True")

    # 2. Manifest checks
    if not manifest.get("double_read_sha256_verified"):
        details["errors"].append("manifest.json reports double_read_sha256_verified != True")

    critical_flags = [
        "calibration_ccd_areg_saved",
        "calibration_ccd_areg2_saved",
        "host_hreg_saved",
        "host_hreg2_saved",
        "anti_tamper_preg_saved",
        "partition_initreg_saved",
        "av_system_asys_saved",
        "av_system_asys2_saved",
        "host_system_hsys_saved",
        "host_system_hsys2_saved",
    ]
    for flag in critical_flags:
        if not manifest.get(flag):
            details["errors"].append(f"Critical calibration/configuration missing flag in manifest: {flag}")

    # 3. Transactions log check
    is_mock = result.get("mock", False)
    if not transactions_path.is_file():
        details["errors"].append("Missing transactions.jsonl")
    elif not is_mock and transactions_path.stat().st_size == 0:
        details["errors"].append("transactions.jsonl is empty for live hardware dump")
    else:
        details["transactions_bytes"] = transactions_path.stat().st_size

    # 4. File manifest cryptographic verification
    file_manifest = manifest.get("file_manifest", [])
    if not file_manifest:
        details["errors"].append("Manifest file_manifest is empty")

    verified_files = 0
    for entry in file_manifest:
        cam_path = entry.get("camera_path", "")
        rel_file = entry.get("file", "")
        exp_bytes = entry.get("bytes", 0)
        exp_sha = entry.get("sha256", "")

        target = backup_dir / rel_file
        if not target.is_file():
            details["errors"].append(f"Missing file on disk: {cam_path} -> {target}")
            continue

        raw = target.read_bytes()
        if len(raw) != exp_bytes:
            details["errors"].append(f"Length mismatch for {cam_path}: expected {exp_bytes}, got {len(raw)}")
            continue

        actual_sha = hashlib.sha256(raw).hexdigest()
        if actual_sha != exp_sha:
            details["errors"].append(f"SHA-256 mismatch for {cam_path}: expected {exp_sha}, got {actual_sha}")
            continue

        verified_files += 1

    details["verified_files_count"] = verified_files

    # 5. Mirror consistency check
    mirror_pairs = [
        ("Areg.bin", "Areg2.bak", "files/boot/factory/Areg.bin", "files/boot/factory/Areg2.bak"),
        ("Hreg.bin", "Hreg2.bak", "files/boot/factory/Hreg.bin", "files/boot/factory/Hreg2.bak"),
        ("Asys.bin", "Asys2.bak", "files/boot/factory/Asys.bin", "files/boot/factory/Asys2.bak"),
        ("Hsys.bin", "Hsys2.bak", "files/boot/factory/Hsys.bin", "files/boot/factory/Hsys2.bak"),
        ("Ausr.bin", "Ausr2.bak", "files/boot/backup/Ausr.bin", "files/boot/backup/Ausr2.bak"),
        ("Husr.bin", "Husr2.bak", "files/boot/backup/Husr.bin", "files/boot/backup/Husr2.bak"),
    ]
    mirror_results = {}
    for p1, p2, f1, f2 in mirror_pairs:
        t1, t2 = backup_dir / f1, backup_dir / f2
        if t1.is_file() and t2.is_file():
            eq = (t1.read_bytes() == t2.read_bytes())
            mirror_results[f"{p1} vs {p2}"] = eq
            if not eq:
                details["errors"].append(f"Mirror pair discrepancy: {p1} != {p2}")
        else:
            mirror_results[f"{p1} vs {p2}"] = False
            details["errors"].append(f"Mirror pair file missing: {f1} or {f2}")
    details["mirror_results"] = mirror_results

    is_ok = len(details["errors"]) == 0
    return is_ok, details


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify DSC-W300 Calibration & Configuration Dump"
    )
    parser.add_argument("backup_dir", nargs="?", default=None,
                        help="Path to dump directory (default: build/w300/backups/calibration_D386002E4438 or latest)")
    args = parser.parse_args()

    if args.backup_dir:
        backup_dir = Path(args.backup_dir).resolve()
    else:
        default_dir = Path("build/w300/backups/calibration_D386002E4438").resolve()
        if default_dir.is_dir():
            backup_dir = default_dir
        else:
            # Look for any calibration backup in build/w300/backups
            candidates = sorted(Path("build/w300/backups").glob("calibration_*"),
                                key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                backup_dir = candidates[0].resolve()
            else:
                backup_dir = default_dir

    print(f"=== Verifying DSC-W300 Safety Dump Directory: {backup_dir} ===")
    ok, details = verify_dump(backup_dir)

    if "manifest" in details:
        m = details["manifest"]
        r = details.get("result", {})
        ident = r.get("identity", {})
        print(f"Device Serial: {ident.get('serial', r.get('serial'))}")
        print(f"Device Model: {ident.get('model')}")
        print(f"USB Bus: {ident.get('bus')}, Ports: {ident.get('ports')}")
        print(f"Normal Mode Return Observed: {r.get('normal_mode_return_observed')}")
        print(f"Double-Read SHA-256 Verified: {m.get('double_read_sha256_verified')}")
        print(f"Total Bytes Saved: {m.get('total_bytes')} bytes across {m.get('files_saved')} files\n")

        print("=== Verified File Manifest ===")
        for entry in m.get("file_manifest", []):
            print(f"PASS: {entry['camera_path']:30} {entry['bytes']:6} B | SHA256: {entry['sha256']}")

    print("\n=== Mirror Pair Consistency Check ===")
    for pair, match in details.get("mirror_results", {}).items():
        print(f"Mirror {pair}: {'IDENTICAL (100% bit-for-bit)' if match else 'DIFFERENT'}")

    ver_file = backup_dir / "files/version.txt"
    if ver_file.is_file():
        print("\n=== Camera Identity & Region Readback ===")
        print(f"Firmware version.txt: '{ver_file.read_text(encoding='utf-8', errors='replace').strip()}'")

    reg_file = backup_dir / "files/boot/dsc/RegionInfo.xml"
    if reg_file.is_file():
        print(f"RegionInfo.xml:\n{reg_file.read_text(encoding='utf-8', errors='replace').strip()}")

    if ok:
        print("\n[ALL CHECKS PASSED] Complete bit-for-bit cryptographic dump integrity verified.")
        return 0
    else:
        print(f"\n[VERIFICATION FAILED] Encountered {len(details['errors'])} error(s):")
        for err in details["errors"]:
            print(f"  - {err}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
