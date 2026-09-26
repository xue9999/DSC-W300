#!/usr/bin/env python3
"""W300 offline file inventory, hypothetical menu scenarios, and AV coprocessor NR control.

Provides both:
  1. Offline byte inspection and hypothetical menu scenarios for baseline testing.
  2. Safe Category 6 NVRAM modification (/boot/factory/Asys.bin and Asys2.bak)
     to disable AV coprocessor CNR and RGB spatial smoothing (offsets 0x3035 and 0x3036).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

# Ensure tools dir is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
BUILD_W300 = REPO_ROOT / "build/w300"
for _p in (str(TOOLS_DIR), str(BUILD_W300)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from w300_nr_nvram import (
    ASYS_SIZE,
    OFFSET_CNR,
    OFFSET_RGB,
    VAL_ENABLED,
    VAL_DISABLED,
    inspect_nvram_bytes,
    patch_nvram_bytes,
    restore_nvram_bytes,
    diff_nvram,
    inspect_nvram_file,
    patch_nvram_file,
    restore_nvram_file,
    inspect_camera,
    patch_camera,
    restore_camera,
    run_nr_tool,
)

W300_NR_LEVELS = ["Toward -", "Normal", "Toward +"]
W300_SHARPNESS_LEVELS = ["Toward -", "Normal", "Toward +"]
W300_ISO_LEVELS = ["AUTO", "80", "100", "200", "400", "800", "1600", "3200", "6400"]


def inspect_file(file_path):
    path = Path(file_path)
    raw = path.read_bytes()
    return {"file": str(path.resolve()), "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "format": "unverified_binary",
            "hardware_validated": False, "simulation": False,
            "note": "Byte inventory only; model, calibration coverage and recovery are unverified."}


def _unsupported(*args, **kwargs):
    raise ValueError("Unsupported for W300: no qualified firmware or adjustment-backup format. "
                     "G3 offline byte patches do not establish W300 compatibility or NR efficacy.")


verify_calibration = _unsupported
patch_av_bin = _unsupported
unpatch_av_bin = _unsupported
patch_dsp_file = _unsupported
unpatch_dsp_file = _unsupported
validate_calibration_write = _unsupported

# Primary NVRAM NR patch and restore interfaces
patch_w300_stills_nr = patch_nvram_bytes
restore_w300_stills_nr = restore_nvram_bytes
patch_w300_nvram_nr = patch_nvram_file
restore_w300_nvram_nr = restore_nvram_file


def assess_ui(nr="Normal", sharpness="Normal", iso="400"):
    """Record a hypothetical menu configuration, without estimating its effect."""
    aliases = {"-": "Toward -", "minus": "Toward -", "normal": "Normal",
               "+": "Toward +", "plus": "Toward +", "toward -": "Toward -",
               "toward +": "Toward +"}
    nr = aliases.get(nr.lower(), nr)
    sharpness = aliases.get(sharpness.lower(), sharpness)
    iso = str(iso).upper()
    if nr not in W300_NR_LEVELS or sharpness not in W300_SHARPNESS_LEVELS or iso not in W300_ISO_LEVELS:
        raise ValueError("Unsupported menu scenario value")
    return {"simulation": True, "hardware_validated": False,
            "scenario": {"noise_reduction": nr, "sharpness": sharpness, "iso": iso},
            "measured": False, "nr_disable_verified": False,
            "note": "Hypothetical settings only. No attenuation, detail retention or image-quality prediction."}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    # Legacy contract commands
    inspect = sub.add_parser("inspect", help="Inventory bytes; do not identify firmware or calibration")
    inspect.add_argument("file", type=Path)

    ui = sub.add_parser("assess-ui", help="Record an explicitly hypothetical menu scenario")
    ui.add_argument("--nr", default="Normal")
    ui.add_argument("--sharpness", default="Normal")
    ui.add_argument("--iso", default="400")

    for name in ("patch-dsp", "unpatch-dsp"):
        cmd = sub.add_parser(name, help="Unsupported W300 compatibility command; always refuses")
        cmd.add_argument("in_file", type=Path)
        cmd.add_argument("out_file", type=Path)

    calibration = sub.add_parser("verify-calibration", help="Unsupported; always refuses")
    calibration.add_argument("file", type=Path)

    # NVRAM NR control commands
    patch_nr = sub.add_parser("patch-nvram", help="Disable CNR/RGB noise reduction in Asys NVRAM")
    patch_nr.add_argument("--file", type=Path, default=None, help="Local NVRAM file to patch")
    patch_nr.add_argument("--out", type=Path, default=None, help="Output destination file")
    patch_nr.add_argument("--camera", action="store_true", help="Patch connected camera")
    patch_nr.add_argument("--mock", action="store_true", help="Use offline mock camera")
    patch_nr.add_argument("--dry-run", action="store_true", help="Preview modifications")
    patch_nr.add_argument("--experimental-service", action="store_true", help="Required safety flag for live writes")
    patch_nr.add_argument("--serial", default=None, help="Camera USB serial")

    restore_nr = sub.add_parser("restore-nvram", help="Restore stock factory NR in Asys NVRAM")
    restore_nr.add_argument("--file", type=Path, default=None, help="Local NVRAM file to restore")
    restore_nr.add_argument("--out", type=Path, default=None, help="Output destination file")
    restore_nr.add_argument("--camera", action="store_true", help="Restore connected camera")
    restore_nr.add_argument("--mock", action="store_true", help="Use offline mock camera")
    restore_nr.add_argument("--dry-run", action="store_true", help="Preview modifications")
    restore_nr.add_argument("--experimental-service", action="store_true", help="Required safety flag for live writes")
    restore_nr.add_argument("--restore-from", type=Path, default=None, help="Directory to restore from")
    restore_nr.add_argument("--serial", default=None, help="Camera USB serial")

    inspect_nr = sub.add_parser("inspect-nvram", help="Inspect NVRAM NR flags at offsets 0x3035 and 0x3036")
    inspect_nr.add_argument("--file", type=Path, default=None, help="Local NVRAM file to inspect")
    inspect_nr.add_argument("--camera", action="store_true", help="Inspect connected camera")
    inspect_nr.add_argument("--mock", action="store_true", help="Use offline mock camera")
    inspect_nr.add_argument("--serial", default=None, help="Camera USB serial")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_file(args.file)
        elif args.command == "assess-ui":
            result = assess_ui(args.nr, args.sharpness, args.iso)
        elif args.command == "patch-nvram":
            target = "file" if args.file is not None else "camera"
            result = run_nr_tool("patch", target=target, file_path=args.file, out_file=args.out,
                                 mock=args.mock, dry_run=args.dry_run,
                                 experimental_service=args.experimental_service, serial=args.serial)
        elif args.command == "restore-nvram":
            target = "file" if args.file is not None else "camera"
            result = run_nr_tool("restore", target=target, file_path=args.file, out_file=args.out,
                                 mock=args.mock, dry_run=args.dry_run,
                                 experimental_service=args.experimental_service, serial=args.serial,
                                 restore_from=args.restore_from)
        elif args.command == "inspect-nvram":
            target = "file" if args.file is not None else "camera"
            result = run_nr_tool("inspect", target=target, file_path=args.file,
                                 mock=args.mock, serial=args.serial)
        else:
            _unsupported()
        print(json.dumps(result, indent=2))
        return 0
    except PermissionError as exc:
        print(f"SAFETY ERROR: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2 if "Unsupported" in str(exc) else 1


if __name__ == "__main__":
    sys.exit(main())
