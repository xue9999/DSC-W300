#!/usr/bin/env python3
"""
Production tool to generate a Stills Noise Reduction Disabled firmware container
(D-G3V2_nonr.dat) for the Sony Cyber-shot DSC-G3.

Bypasses run_NR32_CNR (Chroma NR) and run_NR32_RGB (Spatial Smoothing) in sections/09_av.bin,
recalculates manifest checksums, re-encrypts with key_cxd4108_ms, and verifies 100%
cryptographic header and payload integrity.
"""

from __future__ import annotations

import argparse
import io
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from g3_firmware_parser import (
    CXD4108MsCrypter,
    BLOCK_HEADER_SIZE,
    MANIFEST_SIZE,
    KEY_CXD4108_MS,
    calculate_sha256,
)
from g3_text_poc import build_block_header, update_manifest

EXTRACTED_ROOT = REPO_ROOT / "evidence/extracted_g3"
SECTIONS_DIR = EXTRACTED_ROOT / "sections"
AV_BIN_PATH = SECTIONS_DIR / "09_av.bin"
CNTENT_PATH = EXTRACTED_ROOT / "cntent.dat"

# Exact verified offsets in 09_av.bin (Memory Address - 0x20100000)
OFFSET_NR32_CNR = 0x0AD550  # run_NR32_CNR (Chroma Noise Reduction)
OFFSET_NR32_RGB = 0x0AD576  # run_NR32_RGB (RGB Spatial Smoothing)

ORIGINAL_OPCODE = b"\x10\xb5"  # push {r4, lr}
BYPASS_OPCODE   = b"\x70\x47"  # bx lr (immediate return)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def patch_av_bin(av_bytes: bytes) -> bytes:
    """Applies the 4-byte surgical in-place bypass to 09_av.bin."""
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


def build_nonr_firmware(
    out_dat_path: Path,
    sections_dir: Path = SECTIONS_DIR,
    cntent_path: Path = CNTENT_PATH,
) -> Path:
    """Builds a complete, verified D-G3V2_nonr.dat container."""
    require(sections_dir.exists(), f"Sections directory missing: {sections_dir}")
    require(cntent_path.exists(), f"Manifest missing: {cntent_path}")
    
    # 1. Load original 09_av.bin and patch it
    av_orig_path = sections_dir / "09_av.bin"
    require(av_orig_path.exists(), f"Missing {av_orig_path}")
    patched_av = patch_av_bin(av_orig_path.read_bytes())
    
    # 2. Update manifest
    orig_cntent = cntent_path.read_bytes()
    new_cntent, _ = update_manifest(orig_cntent, 9, "av.bin", len(patched_av))
    
    # 3. Load all 24 section payloads
    section_files = sorted([f for f in sections_dir.iterdir() if f.is_file() and f.name[:2].isdigit()])
    require(len(section_files) == 24, f"Expected 24 sections, found {len(section_files)}")
    
    crypter = CXD4108MsCrypter(KEY_CXD4108_MS)
    out_buf = io.BytesIO()
    
    # Encrypt cntent.dat (Section 0)
    enc_cntent = crypter.cipher(new_cntent)
    f_hdr = build_block_header(crypter, enc_cntent)
    out_buf.write(f_hdr + enc_cntent)
    
    # Encrypt each section with its 128-byte header
    for i, sf in enumerate(section_files):
        payload = patched_av if i == 9 else sf.read_bytes()
        enc_payload = crypter.cipher(payload)
        sec_hdr = build_block_header(crypter, enc_payload)
        out_buf.write(sec_hdr + enc_payload)
        
    final_bytes = out_buf.getvalue()
    out_dat_path.parent.mkdir(parents=True, exist_ok=True)
    out_dat_path.write_bytes(final_bytes)
    return out_dat_path


def verify_nonr_dat(dat_path: Path) -> Dict[str, object]:
    """Verifies that a generated non-NR .dat image passes all cryptographic checks."""
    require(dat_path.exists(), f"File missing: {dat_path}")
    crypter = CXD4108MsCrypter(KEY_CXD4108_MS)
    
    with open(dat_path, "rb") as f:
        # Check cntent.dat block
        cntent_hdr = f.read(BLOCK_HEADER_SIZE)
        require(crypter.check_header_hash(cntent_hdr), "cntent header hash check failed")
        
        enc_cntent = f.read(MANIFEST_SIZE)
        require(crypter.check_data_hash(cntent_hdr, enc_cntent), "cntent data hash check failed")
        dec_cntent = crypter.cipher(enc_cntent)
        
        chksum_val = int(dec_cntent[:0x40].decode('ascii').split('chksum=')[1].split('\n')[0], 16)
        require((sum(dec_cntent[0x40:]) & 0xffffffff) == chksum_val, "cntent body checksum mismatch")
        
        # Parse sections
        lines = dec_cntent.decode('ascii').splitlines()
        sections = []
        cur: Dict[str, str] = {}
        for l in lines:
            if l.startswith('[') and l.endswith(']'):
                tag = l[1:-1].strip()
                if tag in ('header', 'program data'):
                    cur = {}
                    sections.append(cur)
            elif '=' in l and cur is not None:
                k, v = l.split('=', 1)
                cur[k.strip()] = v.strip()
                
        require(len(sections) == 24, f"Expected 24 sections, got {len(sections)}")
        
        av_decrypted = None
        for i, s in enumerate(sections):
            name = s['name']
            offset = int(s['offset'], 16)
            size = int(s['size'], 16)
            
            f.seek(offset + (i + 1) * BLOCK_HEADER_SIZE)
            hdr = f.read(BLOCK_HEADER_SIZE)
            require(crypter.check_header_hash(hdr), f"Section {i} ({name}) header hash failed")
            
            enc_payload = f.read(size)
            require(crypter.check_data_hash(hdr, enc_payload), f"Section {i} ({name}) data hash failed")
            
            dec_payload = crypter.cipher(enc_payload)
            if name == "av.bin":
                av_decrypted = dec_payload
                
    require(av_decrypted is not None, "av.bin section missing from container")
    
    # Confirm patch presence in decrypted av.bin
    cnr_val = av_decrypted[OFFSET_NR32_CNR:OFFSET_NR32_CNR + 2]
    rgb_val = av_decrypted[OFFSET_NR32_RGB:OFFSET_NR32_RGB + 2]
    require(cnr_val == BYPASS_OPCODE, f"CNR patch missing: {cnr_val.hex()} != {BYPASS_OPCODE.hex()}")
    require(rgb_val == BYPASS_OPCODE, f"RGB patch missing: {rgb_val.hex()} != {BYPASS_OPCODE.hex()}")
    
    return {
        "status": "PASS",
        "file": str(dat_path),
        "size": dat_path.stat().st_size,
        "sha256": calculate_sha256(dat_path),
        "cnr_bypassed": True,
        "rgb_bypassed": True,
        "sections_verified": 24,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sony DSC-G3 Stills Noise Reduction Disabling Patcher")
    parser.add_argument("--out", type=Path, default=EXTRACTED_ROOT / "D-G3V2_nonr.dat", help="Output .dat file path")
    parser.add_argument("--verify-only", type=Path, help="Verify an existing non-NR .dat file")
    
    args = parser.parse_args()
    
    if args.verify_only:
        res = verify_nonr_dat(args.verify_only)
        print("Verification Result:", res)
        return 0
        
    print(f"Generating DSC-G3 Non-NR Firmware Container -> {args.out}")
    out_file = build_nonr_firmware(args.out)
    print(f"[+] Successfully created: {out_file} ({out_file.stat().st_size:,} bytes)")
    
    print("Verifying cryptographic and structural integrity...")
    res = verify_nonr_dat(out_file)
    print("[+] Verification Result:", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
