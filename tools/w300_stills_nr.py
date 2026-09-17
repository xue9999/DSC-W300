#!/usr/bin/env python3
"""W300 offline file inventory and explicitly hypothetical menu scenarios.

No W300 firmware image or adjustment-backup format has been qualified.
The old patch/calibration APIs reject requests instead of misidentifying G3
bytes as W300 firmware. No image-quality measurements are computed here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

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
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_file(args.file)
        elif args.command == "assess-ui":
            result = assess_ui(args.nr, args.sharpness, args.iso)
        else:
            _unsupported()
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
