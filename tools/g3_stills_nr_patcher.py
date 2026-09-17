#!/usr/bin/env python3
"""Offline DSC-G3 AV instruction-bypass experiment.

Only the exact four-byte change and container integrity are verified. The names
CNR/RGB describe historical candidate interpretations; noise-reduction behavior,
image quality, camera acceptance and safe execution have not been validated.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from g3_firmware_parser import (
    calculate_sha256,
)

EXTRACTED_ROOT = REPO_ROOT / "evidence/extracted_g3"
SECTIONS_DIR = EXTRACTED_ROOT / "sections"
AV_BIN_PATH = SECTIONS_DIR / "09_av.bin"
CNTENT_PATH = EXTRACTED_ROOT / "cntent.dat"

# Candidate offsets in the pinned DSC-G3 image; hardware semantics unvalidated.
OFFSET_NR32_CNR = 0x0AD550  # run_NR32_CNR (Chroma Noise Reduction)
OFFSET_NR32_RGB = 0x0AD576  # run_NR32_RGB (RGB Spatial Smoothing)

ORIGINAL_OPCODE = b"\x10\xb5"  # push {r4, lr}
BYPASS_OPCODE   = b"\x70\x47"  # bx lr (immediate return)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def patch_av_bin(av_bytes: bytes) -> bytes:
    """Applies the 4-byte surgical in-place bypass to 09_av.bin."""
    require(calculate_sha256(av_bytes) == 'f2554be5181f5765623b0771e6aef6ff99c8483980a1192c39db85c744bda4fb', 'Untrusted DSC-G3 AV SHA-256')
    require(len(av_bytes) == 2061054, f"Unexpected 09_av.bin size: {len(av_bytes)} != 2061054")
    
    # Verify expected original bytes
    cnr_bytes = av_bytes[OFFSET_NR32_CNR:OFFSET_NR32_CNR + 2]
    rgb_bytes = av_bytes[OFFSET_NR32_RGB:OFFSET_NR32_RGB + 2]
    
    require(cnr_bytes == ORIGINAL_OPCODE, f"CNR offset mismatch at {OFFSET_NR32_CNR:#x}: {cnr_bytes.hex()} != {ORIGINAL_OPCODE.hex()}")
    require(rgb_bytes == ORIGINAL_OPCODE, f"RGB offset mismatch at {OFFSET_NR32_RGB:#x}: {rgb_bytes.hex()} != {ORIGINAL_OPCODE.hex()}")
    
    buf = bytearray(av_bytes)
    buf[OFFSET_NR32_CNR:OFFSET_NR32_CNR + 2] = BYPASS_OPCODE
    buf[OFFSET_NR32_RGB:OFFSET_NR32_RGB + 2] = BYPASS_OPCODE
    
    return bytes(buf)


from g3_verified import (SOURCE, trusted_source, verified_extracted, assemble,
    check_output, publish, verify_expected)


def expected_nonr(baseline):
    manifest, sections, payloads = baseline
    require(sections[9]['name'] == 'av.bin', 'Unexpected AV section identity')
    patched = list(payloads)
    patched[9] = patch_av_bin(payloads[9])
    return manifest, patched


def build_nonr_firmware(out_dat_path=None, sections_dir=SECTIONS_DIR, cntent_path=CNTENT_PATH,
                       *, source=SOURCE, overwrite=False):
    out_dat_path = out_dat_path or REPO_ROOT / 'build/g3/D-G3V2_nonr.dat'
    check_output(out_dat_path, source, overwrite)
    require(not Path(out_dat_path).resolve().is_relative_to(Path(sections_dir).resolve())
            and Path(out_dat_path).resolve() != Path(cntent_path).resolve(), 'Output collides with derived input')
    baseline = trusted_source(source)
    verified_extracted(sections_dir, cntent_path, baseline)
    manifest, payloads = expected_nonr(baseline)
    return publish(assemble(manifest, payloads, baseline.container), out_dat_path,
                   lambda path: verify_expected(path, baseline, manifest, payloads), source, overwrite)


def verify_nonr_dat(dat_path, *, source=SOURCE):
    baseline = trusted_source(source)
    manifest, payloads = expected_nonr(baseline)
    result = verify_expected(dat_path, baseline, manifest, payloads)
    result.update(cnr_return_patch_present=True, rgb_return_patch_present=True)
    return result


def main():
    parser = argparse.ArgumentParser(description='DSC-G3 offline AV instruction experiment; hardware not validated')
    parser.add_argument('--out', type=Path, default=REPO_ROOT / 'build/g3/D-G3V2_nonr.dat')
    parser.add_argument('--verify-only', type=Path)
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    if args.verify_only:
        print(verify_nonr_dat(args.verify_only))
    else:
        output = build_nonr_firmware(args.out, overwrite=args.overwrite)
        print({'output': str(output), 'status': 'OFFLINE_INTEGRITY_VERIFIED', 'offline_only': True, 'hardware_validation': 'not_performed'})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
