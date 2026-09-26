#!/usr/bin/env python3
"""Sony Cyber-shot DSC-W300 AV Coprocessor Noise Reduction (NR) NVRAM Control Tool.

Controls Chrominance Noise Reduction (CNR) and RGB Spatial Smoothing in Category 6
NVRAM (/boot/factory/Asys.bin and /boot/factory/Asys2.bak, 16384 bytes each).

Technical Background:
  In the DSC-W300 AV coprocessor dispatch pipeline (located at 0x2cca0..0x2cd10):
    - Offset 0x3035 controls Chrominance Noise Reduction (run_NR32_CNR).
    - Offset 0x3036 controls RGB Spatial Smoothing (run_NR32_RGB).
  In factory default NVRAM, both bytes are 0x01 (enabled / active).
  Setting both bytes to 0x00 causes the dispatch logic to branch directly to
  bypass (0x2cd14), completely disabling the aggressive "grill-me" noise reduction
  and preserving raw optical detail and sensor grain.

Safety Contracts & Guardrails:
  1. Exact 2-Byte Modification: Only offsets 0x3035 and 0x3036 are modified;
     all remaining 16382 bytes are verified bit-for-bit identical.
  2. Dual-Bank Synchronous Write: Primary (Asys.bin) and Backup (Asys2.bak)
     are always updated together to prevent NVRAM bank divergence.
  3. Pre-Write Safety Backup: Original files are automatically backed up locally
     with cryptographic manifest before any camera write.
  4. Bit-for-Bit Double-Read Verification:
     - Pre-write double-read verifies NVRAM transfer stability.
     - Post-write double-read verifies camera flash memory persistence.
  5. Dry-Run / Preview: Fully simulates and verifies changes without modifying storage.
  6. Service Safety Gate: Live writes require explicit --experimental-service.
  7. Offline Simulation: Full mock mode (--mock) supported for offline CI and verification.

Zero external dependencies; pure Python 3 standard library.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure build/w300 and tools directories are available on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
BUILD_W300 = BASE_DIR / 'build/w300'
TOOLS_DIR = BASE_DIR / 'tools'
for _p in (str(BUILD_W300), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import region_app as app
from region_protocol import Senser, FileUnavailable, ProtocolError

# Constants
ASYS_SIZE = 16384  # 0x4000 bytes
OFFSET_CNR = 0x3035  # Chrominance Noise Reduction (run_NR32_CNR)
OFFSET_RGB = 0x3036  # RGB Spatial Smoothing (run_NR32_RGB)

VAL_ENABLED = 0x01   # Stock factory default (NR enabled)
VAL_DISABLED = 0x00  # Bypass / Disabled (NR completely skipped)

PRIMARY_CAMERA_PATH = '/boot/factory/Asys.bin'
BACKUP_CAMERA_PATH = '/boot/factory/Asys2.bak'

DEFAULT_SERIAL = 'D386002E4438'

# Cryptographic reference hashes from D386002E4438 factory calibration dump
STOCK_FACTORY_SHA256 = 'a5631a11d41bc7afc639f5e7c439f2d6f31ea417253a2ff838caa448b7ebc87d'
PATCHED_FACTORY_SHA256 = '8448dccc4262f4cf0e54152b41d52a6ec6330cc12fdd94efdceeb8b2d701a7cf'


def sha256_bytes(data: bytes) -> str:
    """Computes SHA-256 hexadecimal digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def inspect_nvram_bytes(raw: bytes) -> Dict[str, Any]:
    """Analyzes Category 6 NVRAM buffer and reports NR configuration state."""
    raw_len = len(raw)
    digest = sha256_bytes(raw)
    if raw_len != ASYS_SIZE:
        return {
            "valid": False,
            "size_bytes": raw_len,
            "expected_size": ASYS_SIZE,
            "sha256": digest,
            "status": "invalid_size",
            "nr_disabled": False,
            "message": f"Invalid Category 6 NVRAM size ({raw_len} != {ASYS_SIZE})",
        }

    cnr_val = raw[OFFSET_CNR]
    rgb_val = raw[OFFSET_RGB]
    nr_disabled = (cnr_val == VAL_DISABLED and rgb_val == VAL_DISABLED)

    if nr_disabled:
        status = "disabled"
        status_description = "Noise reduction BYPASSED (both CNR and RGB spatial smoothing disabled)"
    elif cnr_val == VAL_ENABLED and rgb_val == VAL_ENABLED:
        status = "enabled"
        status_description = "Stock factory default (both CNR and RGB spatial smoothing enabled)"
    elif cnr_val == VAL_DISABLED and rgb_val == VAL_ENABLED:
        status = "cnr_disabled_rgb_enabled"
        status_description = "Non-standard (CNR disabled, RGB spatial smoothing enabled)"
    elif cnr_val == VAL_ENABLED and rgb_val == VAL_DISABLED:
        status = "cnr_enabled_rgb_disabled"
        status_description = "Non-standard (CNR enabled, RGB spatial smoothing disabled)"
    else:
        status = f"non_standard_0x{cnr_val:02x}_0x{rgb_val:02x}"
        status_description = f"Non-standard configuration (CNR=0x{cnr_val:02x}, RGB=0x{rgb_val:02x})"

    return {
        "valid": True,
        "size_bytes": raw_len,
        "sha256": digest,
        "cnr_offset": OFFSET_CNR,
        "cnr_offset_hex": f"0x{OFFSET_CNR:04x}",
        "cnr_value": cnr_val,
        "cnr_value_hex": f"0x{cnr_val:02x}",
        "rgb_offset": OFFSET_RGB,
        "rgb_offset_hex": f"0x{OFFSET_RGB:04x}",
        "rgb_value": rgb_val,
        "rgb_value_hex": f"0x{rgb_val:02x}",
        "nr_disabled": nr_disabled,
        "status": status,
        "status_description": status_description,
        "is_stock_factory_hash": (digest == STOCK_FACTORY_SHA256),
        "is_patched_factory_hash": (digest == PATCHED_FACTORY_SHA256),
    }


def patch_nvram_bytes(raw: bytes) -> bytes:
    """Disables CNR and RGB noise reduction by setting offsets 0x3035 and 0x3036 to 0x00.

    Ensures that strictly and solely offsets 0x3035 and 0x3036 are modified.
    """
    if len(raw) != ASYS_SIZE:
        raise ValueError(f"Invalid Category 6 NVRAM size: expected {ASYS_SIZE} bytes, got {len(raw)}")

    buf = bytearray(raw)
    buf[OFFSET_CNR] = VAL_DISABLED
    buf[OFFSET_RGB] = VAL_DISABLED

    # Verify no accidental modification occurred outside designated offsets
    diff_offsets = [i for i in range(ASYS_SIZE) if buf[i] != raw[i]]
    for idx in diff_offsets:
        if idx not in (OFFSET_CNR, OFFSET_RGB):
            raise ValueError(f"Integrity check failed: unauthorized modification at offset {idx:#x}")

    return bytes(buf)


def restore_nvram_bytes(raw: bytes) -> bytes:
    """Restores stock factory NR by setting offsets 0x3035 and 0x3036 back to 0x01.

    Ensures that strictly and solely offsets 0x3035 and 0x3036 are modified.
    """
    if len(raw) != ASYS_SIZE:
        raise ValueError(f"Invalid Category 6 NVRAM size: expected {ASYS_SIZE} bytes, got {len(raw)}")

    buf = bytearray(raw)
    buf[OFFSET_CNR] = VAL_ENABLED
    buf[OFFSET_RGB] = VAL_ENABLED

    diff_offsets = [i for i in range(ASYS_SIZE) if buf[i] != raw[i]]
    for idx in diff_offsets:
        if idx not in (OFFSET_CNR, OFFSET_RGB):
            raise ValueError(f"Integrity check failed: unauthorized modification at offset {idx:#x}")

    return bytes(buf)


def diff_nvram(before: bytes, after: bytes) -> List[Dict[str, Any]]:
    """Computes byte-level difference between two NVRAM buffers."""
    if len(before) != len(after):
        raise ValueError(f"Buffer length mismatch: {len(before)} != {len(after)}")
    diffs = []
    for idx in range(len(before)):
        if before[idx] != after[idx]:
            diffs.append({
                "offset": idx,
                "offset_hex": f"0x{idx:04x}",
                "before": before[idx],
                "before_hex": f"0x{before[idx]:02x}",
                "after": after[idx],
                "after_hex": f"0x{after[idx]:02x}",
            })
    return diffs


# ============================================================================
# File Operations
# ============================================================================

def inspect_nvram_file(path: Path) -> Dict[str, Any]:
    """Inspects a local NVRAM binary file on disk."""
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")
    raw = p.read_bytes()
    info = inspect_nvram_bytes(raw)
    info["file_path"] = str(p)
    return info


def patch_nvram_file(in_path: Path, out_path: Optional[Path] = None, dry_run: bool = False) -> Dict[str, Any]:
    """Patches a local NVRAM binary file to disable noise reduction."""
    src = Path(in_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Source file not found: {src}")
    raw = src.read_bytes()
    before_info = inspect_nvram_bytes(raw)
    if not before_info["valid"]:
        raise ValueError(f"Cannot patch invalid NVRAM file: {before_info.get('message')}")

    patched = patch_nvram_bytes(raw)
    after_info = inspect_nvram_bytes(patched)
    changes = diff_nvram(raw, patched)

    dst = Path(out_path).resolve() if out_path is not None else src
    written = False
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(patched)
        written = True

    return {
        "operation": "patch_file",
        "source_file": str(src),
        "destination_file": str(dst),
        "dry_run": dry_run,
        "written": written,
        "before": before_info,
        "after": after_info,
        "byte_changes": changes,
        "nr_disabled": True,
    }


def restore_nvram_file(in_path: Path, out_path: Optional[Path] = None, dry_run: bool = False) -> Dict[str, Any]:
    """Restores stock factory NR (0x01) on a local NVRAM binary file."""
    src = Path(in_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Source file not found: {src}")
    raw = src.read_bytes()
    before_info = inspect_nvram_bytes(raw)
    if not before_info["valid"]:
        raise ValueError(f"Cannot restore invalid NVRAM file: {before_info.get('message')}")

    restored = restore_nvram_bytes(raw)
    after_info = inspect_nvram_bytes(restored)
    changes = diff_nvram(raw, restored)

    dst = Path(out_path).resolve() if out_path is not None else src
    written = False
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(restored)
        written = True

    return {
        "operation": "restore_file",
        "source_file": str(src),
        "destination_file": str(dst),
        "dry_run": dry_run,
        "written": written,
        "before": before_info,
        "after": after_info,
        "byte_changes": changes,
        "nr_disabled": False,
    }


# ============================================================================
# Camera Senser Protocol Operations
# ============================================================================

def double_read_camera_file(camera: Any, target_path: str) -> Tuple[bytes, str, str]:
    """Reads a file twice across Senser protocol and verifies bit-for-bit identity.

    Tries the target path and any partition mount fallback aliases.
    Returns: (data_bytes, sha256_hex, resolved_camera_path).
    Raises: ProtocolError if repeat read diverges, FileUnavailable if absent.
    """
    candidates = [target_path]
    if target_path in app.FALLBACK_ALIASES:
        candidates.append(app.FALLBACK_ALIASES[target_path])
    elif target_path.startswith('/factory/'):
        candidates.append('/boot' + target_path)

    last_unavail = None
    for attempt in candidates:
        try:
            read1 = camera.read_file(attempt)
            read2 = camera.read_file(attempt)
            if read1 != read2:
                raise ProtocolError(f"Double-read verification failed for {attempt}: bit-for-bit discrepancy across reads")
            h = sha256_bytes(read1)
            return read1, h, attempt
        except FileUnavailable as exc:
            last_unavail = exc
            continue

    raise FileUnavailable(f"File {target_path} unavailable on camera (candidates={candidates}): {last_unavail}")


def inspect_camera(camera: Any) -> Dict[str, Any]:
    """Performs bit-for-bit double-read inspection of camera NVRAM banks."""
    primary_bytes, primary_sha, primary_path = double_read_camera_file(camera, PRIMARY_CAMERA_PATH)
    backup_bytes, backup_sha, backup_path = double_read_camera_file(camera, BACKUP_CAMERA_PATH)

    primary_info = inspect_nvram_bytes(primary_bytes)
    primary_info["camera_path"] = primary_path
    backup_info = inspect_nvram_bytes(backup_bytes)
    backup_info["camera_path"] = backup_path

    banks_in_sync = (primary_bytes == backup_bytes)

    return {
        "operation": "inspect_camera",
        "primary": primary_info,
        "backup": backup_info,
        "banks_in_sync": banks_in_sync,
        "nr_disabled": primary_info.get("nr_disabled", False) and backup_info.get("nr_disabled", False),
        "status": primary_info.get("status"),
        "status_description": primary_info.get("status_description"),
    }


def patch_camera(
    camera: Any,
    backup_dir: Optional[Path] = None,
    dry_run: bool = False,
    trace: Optional[Any] = None,
) -> Dict[str, Any]:
    """Patches camera NVRAM banks to disable noise reduction (sets 0x3035 and 0x3036 to 0x00).

    Protocol Flow:
      1. Bit-for-bit double-read of primary and backup banks.
      2. Verification of bank integrity and 16384-byte boundaries.
      3. Generation of patched buffers in memory and strict verification of 2-byte diff.
      4. If dry_run: return preview without writing.
      5. Creation of verified local backup of original files before writing.
      6. Senser write of patched primary buffer to /boot/factory/Asys.bin.
      7. Senser write of patched backup buffer to /boot/factory/Asys2.bak.
      8. Post-write double-read readback verification of both banks.
      9. Guarantee of bank synchronicity and exact match with expected patched buffer.
    """
    # 1. Double-read primary and backup banks
    prim_bytes, prim_sha, prim_path = double_read_camera_file(camera, PRIMARY_CAMERA_PATH)
    bak_bytes, bak_sha, bak_path = double_read_camera_file(camera, BACKUP_CAMERA_PATH)

    prim_info = inspect_nvram_bytes(prim_bytes)
    bak_info = inspect_nvram_bytes(bak_bytes)

    if not prim_info["valid"] or not bak_info["valid"]:
        raise ValueError(f"Cannot patch: invalid NVRAM bank size (primary={len(prim_bytes)}, backup={len(bak_bytes)})")

    # 2. Compute patched buffers
    prim_patched = patch_nvram_bytes(prim_bytes)
    bak_patched = patch_nvram_bytes(bak_bytes)

    prim_diff = diff_nvram(prim_bytes, prim_patched)
    bak_diff = diff_nvram(bak_bytes, bak_patched)

    report: Dict[str, Any] = {
        "operation": "patch_camera",
        "dry_run": dry_run,
        "primary_camera_path": prim_path,
        "backup_camera_path": bak_path,
        "primary_sha_before": prim_sha,
        "backup_sha_before": bak_sha,
        "primary_sha_expected": sha256_bytes(prim_patched),
        "backup_sha_expected": sha256_bytes(bak_patched),
        "byte_changes": prim_diff,
        "written": False,
        "verified_readback": False,
        "banks_in_sync": False,
    }

    if dry_run:
        report["message"] = "Dry-run successful: planned 2-byte patch previewed, no camera writes executed."
        report["nr_disabled"] = True
        return report

    # 3. Create safety backup
    if backup_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = BUILD_W300 / 'backups' / f"nr_prepatch_{ts}"
    backup_path_obj = Path(backup_dir).resolve()
    backup_path_obj.mkdir(parents=True, exist_ok=True)

    backup_prim_file = backup_path_obj / "Asys.bin"
    backup_bak_file = backup_path_obj / "Asys2.bak"
    backup_prim_file.write_bytes(prim_bytes)
    backup_bak_file.write_bytes(bak_bytes)

    backup_manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "purpose": "Safety backup before disabling AV coprocessor noise reduction",
        "primary": {"path": prim_path, "bytes": len(prim_bytes), "sha256": prim_sha},
        "backup": {"path": bak_path, "bytes": len(bak_bytes), "sha256": bak_sha},
    }
    app.save_json(backup_path_obj / "manifest.json", backup_manifest, durable=True)
    report["backup_directory"] = str(backup_path_obj)

    # 4. Write patched primary and backup to camera
    if trace:
        trace.record('patch-nr-write-primary', path=prim_path, bytes=len(prim_patched))
    camera.write_file(prim_path, prim_patched)

    if trace:
        trace.record('patch-nr-write-backup', path=bak_path, bytes=len(bak_patched))
    camera.write_file(bak_path, bak_patched)

    report["written"] = True

    # 5. Post-write readback double-read verification
    readback_prim, readback_prim_sha, _ = double_read_camera_file(camera, prim_path)
    readback_bak, readback_bak_sha, _ = double_read_camera_file(camera, bak_path)

    if readback_prim != prim_patched:
        raise RuntimeError(
            f"CRITICAL: Primary bank post-write readback mismatch! Expected {sha256_bytes(prim_patched)}, got {readback_prim_sha}"
        )
    if readback_bak != bak_patched:
        raise RuntimeError(
            f"CRITICAL: Backup bank post-write readback mismatch! Expected {sha256_bytes(bak_patched)}, got {readback_bak_sha}"
        )
    if readback_prim != readback_bak:
        raise RuntimeError("CRITICAL: Primary and backup banks diverged after write!")

    report["verified_readback"] = True
    report["banks_in_sync"] = True
    report["primary_sha_after"] = readback_prim_sha
    report["backup_sha_after"] = readback_bak_sha
    report["nr_disabled"] = True
    report["status"] = "SUCCESS"
    report["message"] = (
        "AV coprocessor noise reduction successfully disabled and verified. "
        "Offsets 0x3035 and 0x3036 set to 0x00 on primary and backup banks."
    )
    return report


def restore_camera(
    camera: Any,
    backup_dir: Optional[Path] = None,
    restore_from_dir: Optional[Path] = None,
    dry_run: bool = False,
    trace: Optional[Any] = None,
) -> Dict[str, Any]:
    """Restores camera NVRAM banks to stock factory default NR (0x01).

    If restore_from_dir is given, reads original Asys.bin/Asys2.bak from that directory.
    Otherwise, applies restore_nvram_bytes (sets 0x3035 and 0x3036 back to 0x01).
    """
    prim_bytes, prim_sha, prim_path = double_read_camera_file(camera, PRIMARY_CAMERA_PATH)
    bak_bytes, bak_sha, bak_path = double_read_camera_file(camera, BACKUP_CAMERA_PATH)

    if restore_from_dir is not None:
        r_dir = Path(restore_from_dir).resolve()
        rf_prim = r_dir / "Asys.bin"
        rf_bak = r_dir / "Asys2.bak"
        if not rf_prim.is_file() or not rf_bak.is_file():
            raise FileNotFoundError(f"Restore directory {r_dir} must contain Asys.bin and Asys2.bak")
        prim_target = rf_prim.read_bytes()
        bak_target = rf_bak.read_bytes()
        if len(prim_target) != ASYS_SIZE or len(bak_target) != ASYS_SIZE:
            raise ValueError(f"Restore source files must be exactly {ASYS_SIZE} bytes")
    else:
        prim_target = restore_nvram_bytes(prim_bytes)
        bak_target = restore_nvram_bytes(bak_bytes)

    prim_diff = diff_nvram(prim_bytes, prim_target)
    bak_diff = diff_nvram(bak_bytes, bak_target)

    report: Dict[str, Any] = {
        "operation": "restore_camera",
        "dry_run": dry_run,
        "primary_camera_path": prim_path,
        "backup_camera_path": bak_path,
        "primary_sha_before": prim_sha,
        "backup_sha_before": bak_sha,
        "primary_sha_expected": sha256_bytes(prim_target),
        "backup_sha_expected": sha256_bytes(bak_target),
        "byte_changes": prim_diff,
        "written": False,
        "verified_readback": False,
        "banks_in_sync": False,
    }

    if dry_run:
        report["message"] = "Dry-run successful: planned restore previewed, no camera writes executed."
        report["nr_disabled"] = False
        return report

    # Create safety backup of current state
    if backup_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = BUILD_W300 / 'backups' / f"nr_prerestore_{ts}"
    backup_path_obj = Path(backup_dir).resolve()
    backup_path_obj.mkdir(parents=True, exist_ok=True)
    (backup_path_obj / "Asys.bin").write_bytes(prim_bytes)
    (backup_path_obj / "Asys2.bak").write_bytes(bak_bytes)
    app.save_json(backup_path_obj / "manifest.json", {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "purpose": "Safety backup before restoring stock NR",
        "primary_sha256": prim_sha,
        "backup_sha256": bak_sha,
    }, durable=True)
    report["backup_directory"] = str(backup_path_obj)

    # Write target buffers
    if trace:
        trace.record('restore-nr-write-primary', path=prim_path, bytes=len(prim_target))
    camera.write_file(prim_path, prim_target)

    if trace:
        trace.record('restore-nr-write-backup', path=bak_path, bytes=len(bak_target))
    camera.write_file(bak_path, bak_target)

    report["written"] = True

    # Post-write readback double-read verification
    readback_prim, readback_prim_sha, _ = double_read_camera_file(camera, prim_path)
    readback_bak, readback_bak_sha, _ = double_read_camera_file(camera, bak_path)

    if readback_prim != prim_target:
        raise RuntimeError("CRITICAL: Primary bank post-restore readback mismatch!")
    if readback_bak != bak_target:
        raise RuntimeError("CRITICAL: Backup bank post-restore readback mismatch!")
    if readback_prim != readback_bak:
        raise RuntimeError("CRITICAL: Primary and backup banks diverged after restore!")

    report["verified_readback"] = True
    report["banks_in_sync"] = True
    report["primary_sha_after"] = readback_prim_sha
    report["backup_sha_after"] = readback_bak_sha
    report["nr_disabled"] = False
    report["status"] = "SUCCESS"
    report["message"] = "Stock factory NR successfully restored and verified (offsets 0x3035 and 0x3036 set to 0x01)."
    return report


# ============================================================================
# High-Level Operational Dispatcher
# ============================================================================

def run_nr_tool(
    action: str,
    target: str = "camera",
    file_path: Optional[Path] = None,
    out_file: Optional[Path] = None,
    mock: bool = False,
    dry_run: bool = False,
    experimental_service: bool = False,
    serial: Optional[str] = None,
    backup_dir: Optional[Path] = None,
    restore_from: Optional[Path] = None,
) -> Dict[str, Any]:
    """Dispatches requested NR NVRAM operation with strict safety enforcement."""
    if target == "file":
        if file_path is None:
            raise ValueError("Target is 'file' but no --file path was specified")
        if action == "inspect":
            return inspect_nvram_file(file_path)
        elif action in ("patch", "disable"):
            return patch_nvram_file(file_path, out_file, dry_run=dry_run)
        elif action in ("restore", "enable"):
            return restore_nvram_file(file_path, out_file, dry_run=dry_run)
        else:
            raise ValueError(f"Unknown file action: {action}")

    elif target == "camera":
        # Safety gate: Live writes strictly require --experimental-service
        if not mock and not dry_run and action in ("patch", "disable", "restore", "enable"):
            if not experimental_service:
                raise PermissionError(
                    "Safety refusal: live camera write requires explicit --experimental-service flag."
                )

        if mock:
            camera = app.MockSenserCamera()
            for p in (PRIMARY_CAMERA_PATH, BACKUP_CAMERA_PATH, '/factory/Asys.bin', '/factory/Asys2.bak'):
                if len(camera.files.get(p, b'')) != ASYS_SIZE:
                    buf = bytearray(ASYS_SIZE)
                    buf[OFFSET_CNR] = VAL_ENABLED
                    buf[OFFSET_RGB] = VAL_ENABLED
                    camera.files[p] = bytes(buf)

            if action == "inspect":
                return inspect_camera(camera)
            elif action in ("patch", "disable"):
                return patch_camera(camera, backup_dir=backup_dir, dry_run=dry_run)
            elif action in ("restore", "enable"):
                return restore_camera(camera, backup_dir=backup_dir, restore_from_dir=restore_from, dry_run=dry_run)
            else:
                raise ValueError(f"Unknown camera action: {action}")
        else:
            # Live camera via USB Senser protocol session
            eff_serial = serial or DEFAULT_SERIAL
            session_dir = BUILD_W300 / 'sessions' / f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-nr-{action}"
            session_dir.mkdir(parents=True, exist_ok=True)
            trace = app.Trace(session_dir)
            report_dict: Dict[str, Any] = {"operation": f"nr_{action}", "serial": eff_serial, "ok": False}
            try:
                with app.session(eff_serial, trace, report_dict) as live_camera:
                    if action == "inspect":
                        res = inspect_camera(live_camera)
                    elif action in ("patch", "disable"):
                        res = patch_camera(live_camera, backup_dir=backup_dir, dry_run=dry_run, trace=trace)
                    elif action in ("restore", "enable"):
                        res = restore_camera(live_camera, backup_dir=backup_dir, restore_from_dir=restore_from, dry_run=dry_run, trace=trace)
                    else:
                        raise ValueError(f"Unknown camera action: {action}")
                    report_dict["result"] = res
                    report_dict["ok"] = True
                    return res
            finally:
                trace.close()
                app.save_json(session_dir / "result.json", report_dict, durable=True)
    else:
        raise ValueError(f"Unknown target: {target}")


# ============================================================================
# CLI Implementation
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Subcommand: inspect
    inspect_parser = sub.add_parser("inspect", help="Inspect NVRAM NR status (offsets 0x3035 & 0x3036)")
    inspect_parser.add_argument("--file", type=Path, default=None, help="Inspect local NVRAM file")
    inspect_parser.add_argument("--camera", action="store_true", help="Inspect live camera NVRAM")
    inspect_parser.add_argument("--mock", action="store_true", help="Use offline mock camera")
    inspect_parser.add_argument("--serial", default=None, help="Camera USB serial number")
    inspect_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # Subcommand: disable-nr / patch
    for cmd_name in ("disable-nr", "patch"):
        p_parser = sub.add_parser(cmd_name, help="Disable CNR and RGB noise reduction (set 0x3035 and 0x3036 to 0x00)")
        p_parser.add_argument("--file", type=Path, default=None, help="Patch local NVRAM file")
        p_parser.add_argument("--out", type=Path, default=None, help="Output path for patched local file")
        p_parser.add_argument("--camera", action="store_true", help="Patch connected camera NVRAM")
        p_parser.add_argument("--mock", action="store_true", help="Use offline mock camera")
        p_parser.add_argument("--dry-run", action="store_true", help="Preview modifications without writing")
        p_parser.add_argument("--experimental-service", action="store_true", help="Safety gate required for live camera writes")
        p_parser.add_argument("--serial", default=None, help="Camera USB serial number")
        p_parser.add_argument("--backup-dir", type=Path, default=None, help="Directory to save pre-patch backup")
        p_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # Subcommand: enable-nr / restore
    for cmd_name in ("enable-nr", "restore"):
        r_parser = sub.add_parser(cmd_name, help="Restore stock factory NR (set 0x3035 and 0x3036 back to 0x01)")
        r_parser.add_argument("--file", type=Path, default=None, help="Restore local NVRAM file")
        r_parser.add_argument("--out", type=Path, default=None, help="Output path for restored local file")
        r_parser.add_argument("--camera", action="store_true", help="Restore connected camera NVRAM")
        r_parser.add_argument("--mock", action="store_true", help="Use offline mock camera")
        r_parser.add_argument("--dry-run", action="store_true", help="Preview modifications without writing")
        r_parser.add_argument("--experimental-service", action="store_true", help="Safety gate required for live camera writes")
        r_parser.add_argument("--serial", default=None, help="Camera USB serial number")
        r_parser.add_argument("--restore-from", type=Path, default=None, help="Directory with original Asys.bin to restore from")
        r_parser.add_argument("--backup-dir", type=Path, default=None, help="Directory to save pre-restore backup")
        r_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    cmd = args.command
    if cmd in ("disable-nr", "patch"):
        action = "patch"
    elif cmd in ("enable-nr", "restore"):
        action = "restore"
    else:
        action = "inspect"

    target = "file" if getattr(args, "file", None) is not None else "camera"

    try:
        result = run_nr_tool(
            action=action,
            target=target,
            file_path=getattr(args, "file", None),
            out_file=getattr(args, "out", None),
            mock=getattr(args, "mock", False),
            dry_run=getattr(args, "dry_run", False),
            experimental_service=getattr(args, "experimental_service", False),
            serial=getattr(args, "serial", None),
            backup_dir=getattr(args, "backup_dir", None),
            restore_from=getattr(args, "restore_from", None),
        )

        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            print(f"[{result.get('operation', cmd).upper()}] Status: {result.get('status', 'OK')}")
            if "status_description" in result:
                print(f"  Configuration: {result['status_description']}")
            if "nr_disabled" in result:
                print(f"  NR Bypassed (Off): {result['nr_disabled']}")
            if "written" in result:
                print(f"  Written to storage: {result['written']}")
            if "dry_run" in result and result["dry_run"]:
                print("  Mode: DRY-RUN (storage unmodified)")
            if "backup_directory" in result:
                print(f"  Safety Backup Saved: {result['backup_directory']}")
            if "byte_changes" in result:
                print("  Byte modifications:")
                for ch in result["byte_changes"]:
                    print(f"    Offset {ch['offset_hex']}: 0x{ch['before']:02x} -> 0x{ch['after']:02x}")
        return 0

    except PermissionError as exc:
        print(f"SAFETY ERROR: {exc}", file=sys.stderr)
        return 2
    except (ValueError, FileNotFoundError, ProtocolError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
