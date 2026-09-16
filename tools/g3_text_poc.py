#!/usr/bin/env python3
"""
Offline, fail-closed DSC-G3 custom string display proof-of-concept (POC) tool.
Benchmarked against SONY_NX3_Reversal (nx3_text_poc.py).

Modifies a visible UI string (e.g. SETUP_VERSION in eng.csv or NetFront strings in omgLng00.csv),
updates section metadata, re-encrypts all MsFirm sections with key_cxd4108_ms,
and generates a verified, bit-for-bit consistent proof-of-concept firmware image.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
from pathlib import Path
import shutil
import struct
import tarfile
import tempfile
from typing import Dict, List, Optional, Tuple

from g3_firmware_parser import (
    CXD4108MsCrypter,
    BLOCK_HEADER_SIZE,
    MANIFEST_OFFSET,
    MANIFEST_SIZE,
    KEY_CXD4108_MS,
    calculate_sha256,
    calculate_sha1,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTED_ROOT = REPO_ROOT / "evidence/extracted_g3"
SECTIONS_DIR = EXTRACTED_ROOT / "sections"
ARCHIVES_DIR = EXTRACTED_ROOT / "archives_unpacked"

ENG_CSV_RELPATH = "dsc/app/scripts/language/eng.csv"
DEFAULT_TARGET_KEY = "SETUP_VERSION"
DEFAULT_ORIGINAL_VAL = "Version"
DEFAULT_POC_STRING = "G3 POC"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def build_block_header(crypter: CXD4108MsCrypter, enc_data: bytes) -> bytes:
    """Builds a valid 128-byte MsFirm block header with dual HMAC-SHA1 signatures."""
    data_hash = crypter._calc_hash(enc_data)
    raw_hdr = data_hash + b'\0' * 88 + b'\0' * 20
    hdr_hash = crypter._calc_hash(raw_hdr)
    return raw_hdr[:-20] + hdr_hash


def patch_csv_text(
    original_text: str,
    target_key: str,
    expected_old_val: str,
    new_val: str,
) -> str:
    """
    Applies a bounded, fail-closed patch to a CSV key-value pair.
    Target format: KEY,VALUE
    """
    lines = original_text.splitlines(keepends=True)
    target_prefix = f"{target_key},"
    matched_indices = []
    
    for idx, line in enumerate(lines):
        if line.startswith(target_prefix):
            matched_indices.append(idx)
            
    require(len(matched_indices) == 1, f"Expected exactly 1 occurrence of '{target_key}', found {len(matched_indices)}")
    
    idx = matched_indices[0]
    line = lines[idx]
    current_val = line[len(target_prefix):].rstrip("\r\n")
    require(current_val == expected_old_val, f"Current value '{current_val}' does not match expected '{expected_old_val}'")
    
    # Check newline style
    newline = "\r\n" if line.endswith("\r\n") else "\n"
    lines[idx] = f"{target_key},{new_val}{newline}"
    return "".join(lines)


def repack_fskapp1_tar(fskapp1_dir: Path) -> bytes:
    """Repacks fskapp1 directory into a deterministic POSIX ustar archive."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.PAX_FORMAT) as tar:
        # Sort files deterministically
        for root, dirs, files in os.walk(fskapp1_dir):
            dirs.sort()
            files.sort()
            rel_root = os.path.relpath(root, fskapp1_dir)
            if rel_root != ".":
                tarinfo = tar.gettarinfo(root, arcname=rel_root)
                tarinfo.uid = 0
                tarinfo.gid = 0
                tarinfo.uname = "root"
                tarinfo.gname = "root"
                tarinfo.mtime = 0
                tar.addfile(tarinfo)
            for file_name in files:
                full_path = os.path.join(root, file_name)
                arcname = os.path.relpath(full_path, fskapp1_dir)
                tarinfo = tar.gettarinfo(full_path, arcname=arcname)
                tarinfo.uid = 0
                tarinfo.gid = 0
                tarinfo.uname = "root"
                tarinfo.gname = "root"
                tarinfo.mtime = 0
                with open(full_path, 'rb') as f:
                    tar.addfile(tarinfo, f)
                    
    tar_bytes = buf.getvalue()
    # Pad to 512-byte boundary if needed
    rem = len(tar_bytes) % 512
    if rem != 0:
        tar_bytes += b'\0' * (512 - rem)
    return tar_bytes


def update_manifest(
    original_cntent: bytes,
    modified_section_index: int,
    new_section_name: str,
    new_size: int,
) -> Tuple[bytes, List[Dict[str, int | str]]]:
    """Updates section size, offsets, and chksums in cntent.dat."""
    lines = original_cntent.decode('ascii', errors='ignore').split('\n')
    sections_meta: List[Dict[str, int | str]] = []
    
    # Parse existing sections from original cntent
    current_sec: Dict[str, int | str] = {}
    for l in lines:
        if l.startswith('[') and l.endswith(']'):
            tag = l[1:-1].strip()
            if tag in ('header', 'program data'):
                current_sec = {}
                sections_meta.append(current_sec)
        elif '=' in l and current_sec is not None:
            k, v = l.split('=', 1)
            current_sec[k.strip()] = v.strip()
            
    require(len(sections_meta) == 24, f"Expected 24 sections, found {len(sections_meta)}")
    require(0 <= modified_section_index < 24, f"Invalid section index {modified_section_index}")
    
    # Update size for modified section
    sections_meta[modified_section_index]['size'] = f"{new_size:x}"
    
    # Recalculate offsets sequentially
    running_offset = MANIFEST_SIZE
    for s in sections_meta:
        s['offset'] = f"{running_offset:08x}"
        running_offset += int(str(s['size']), 16)
        
    # Rebuild cntent body
    body_lines = [
        "[total number of files]",
        f"total_num={len(sections_meta):x}",
        "",
    ]
    for i, s in enumerate(sections_meta):
        header_tag = "[header]" if i == 0 else "[program data]"
        body_lines.extend([
            header_tag,
            f"fnum={int(str(s['fnum']), 16):02x}",
            f"name={s['name']}",
            f"offset={s['offset']}",
            f"size={s['size']}",
            f"cksum={s.get('cksum', '0')}",
            f"progress=00000000",
            f"encrypt=yes",
            "",
        ])
    body_str = "\n".join(body_lines)
    # Pad body to size - 0x40 with spaces (matching original format)
    target_body_len = MANIFEST_SIZE - 0x40
    body_bytes = body_str.encode('ascii').ljust(target_body_len, b' ')
    
    # Header
    chksum = sum(body_bytes) & 0xffffffff
    hdr_str = f"FV 02\nSV 02\n\n[alsiz]\ndatasize={target_body_len:08x}\n\n[hdsm]\nchksum={chksum:08x}\n\n"
    hdr_bytes = hdr_str.encode('ascii')
    require(len(hdr_bytes) == 0x40, f"Header size mismatch: {len(hdr_bytes)} != 0x40")
    
    new_cntent = hdr_bytes + body_bytes
    require(len(new_cntent) == MANIFEST_SIZE, f"cntent.dat size mismatch: {len(new_cntent)} != {MANIFEST_SIZE}")
    return new_cntent, sections_meta


def generate_poc_firmware(
    custom_string: str = DEFAULT_POC_STRING,
    output_dat_path: Optional[Path] = None,
) -> Path:
    """
    Generates a full fail-closed POC firmware file (D-G3V2_poc.dat).
    """
    if output_dat_path is None:
        output_dat_path = EXTRACTED_ROOT / "D-G3V2_poc.dat"
        
    crypter = CXD4108MsCrypter(KEY_CXD4108_MS)
    
    # 1. Read original cntent.dat
    cntent_orig_path = EXTRACTED_ROOT / "cntent.dat"
    require(cntent_orig_path.exists(), f"Missing {cntent_orig_path}")
    orig_cntent = cntent_orig_path.read_bytes()
    
    # 2. Modify eng.csv inside temporary working copy of fskapp1
    fskapp1_orig_dir = ARCHIVES_DIR / "fskapp1"
    require(fskapp1_orig_dir.exists(), f"Missing {fskapp1_orig_dir}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_fskapp1 = Path(tmpdir) / "fskapp1"
        shutil.copytree(fskapp1_orig_dir, tmp_fskapp1)
        
        eng_csv_path = tmp_fskapp1 / ENG_CSV_RELPATH
        require(eng_csv_path.exists(), f"Missing {eng_csv_path}")
        
        orig_text = eng_csv_path.read_text(encoding="utf-8")
        patched_text = patch_csv_text(orig_text, DEFAULT_TARGET_KEY, DEFAULT_ORIGINAL_VAL, custom_string)
        eng_csv_path.write_text(patched_text, encoding="utf-8")
        
        # Repack fskapp1.tar
        repacked_fskapp1 = repack_fskapp1_tar(tmp_fskapp1)
        
    # Section 10 is 10_fskapp1.tar
    sec_10_idx = 10
    
    # 3. Update manifest
    new_cntent, sections_meta = update_manifest(orig_cntent, sec_10_idx, "fskapp1.tar", len(repacked_fskapp1))
    
    # 4. Load all section payloads
    section_files = sorted([f for f in SECTIONS_DIR.iterdir() if f.is_file() and f.name[:2].isdigit()])
    require(len(section_files) == 24, f"Expected 24 section files, found {len(section_files)}")
    
    section_payloads: List[bytes] = []
    for i, sf in enumerate(section_files):
        if i == sec_10_idx:
            section_payloads.append(repacked_fskapp1)
        else:
            section_payloads.append(sf.read_bytes())
            
    # 5. Assemble encrypted container
    out_buf = io.BytesIO()
    
    # Encrypt cntent.dat (offset 0)
    enc_cntent = crypter.cipher(new_cntent)
    cntent_hdr = build_block_header(crypter, enc_cntent)
    out_buf.write(cntent_hdr + enc_cntent)
    
    # Encrypt each section with its 128-byte header
    for i, payload in enumerate(section_payloads):
        enc_payload = crypter.cipher(payload)
        sec_hdr = build_block_header(crypter, enc_payload)
        out_buf.write(sec_hdr + enc_payload)
        
    final_bytes = out_buf.getvalue()
    output_dat_path.write_bytes(final_bytes)
    return output_dat_path


def verify_poc_image(poc_dat_path: Path, expected_string: str = DEFAULT_POC_STRING) -> Dict[str, object]:
    """
    Verifies that the generated POC image passes all cryptographic checks and contains the custom string.
    """
    require(poc_dat_path.exists(), f"File does not exist: {poc_dat_path}")
    crypter = CXD4108MsCrypter(KEY_CXD4108_MS)
    
    with open(poc_dat_path, 'rb') as f:
        # Check cntent.dat header
        cntent_hdr = f.read(BLOCK_HEADER_SIZE)
        require(crypter.check_header_hash(cntent_hdr), "cntent.dat header hash check failed")
        
        enc_cntent = f.read(MANIFEST_SIZE)
        require(crypter.check_data_hash(cntent_hdr, enc_cntent), "cntent.dat data hash check failed")
        dec_cntent = crypter.cipher(enc_cntent)
        
        # Verify cntent checksum
        chksum_val = int(dec_cntent[:0x40].decode('ascii').split('chksum=')[1].split('\n')[0], 16)
        require((sum(dec_cntent[0x40:]) & 0xffffffff) == chksum_val, "cntent.dat body checksum failed")
        
        # Parse sections
        lines = dec_cntent.decode('ascii').splitlines()
        sections = []
        cur = {}
        for l in lines:
            if l.startswith('[') and l.endswith(']'):
                tag = l[1:-1].strip()
                if tag in ('header', 'program data'):
                    cur = {}
                    sections.append(cur)
            elif '=' in l and cur is not None:
                k, v = l.split('=', 1)
                cur[k.strip()] = v.strip()
                
        require(len(sections) == 24, f"Expected 24 sections, found {len(sections)}")
        
        verified_sections = []
        fskapp1_tar_data = None
        
        # Verify each section
        for i, s in enumerate(sections):
            name = s['name']
            offset = int(str(s['offset']), 16)
            size = int(str(s['size']), 16)
            
            # File location = offset + (i + 1) * BLOCK_HEADER_SIZE
            expected_pos = offset + (i + 1) * BLOCK_HEADER_SIZE
            f.seek(expected_pos)
            hdr = f.read(BLOCK_HEADER_SIZE)
            require(crypter.check_header_hash(hdr), f"Section {i} ({name}) header hash failed")
            
            enc_payload = f.read(size)
            require(crypter.check_data_hash(hdr, enc_payload), f"Section {i} ({name}) data hash failed")
            
            dec_payload = crypter.cipher(enc_payload)
            verified_sections.append({
                "index": i,
                "name": name,
                "size": size,
                "sha256": calculate_sha256(dec_payload),
            })
            
            if name == "fskapp1.tar":
                fskapp1_tar_data = dec_payload
                
    require(fskapp1_tar_data is not None, "fskapp1.tar section not found in container")
    
    # Extract eng.csv from repacked fskapp1.tar and confirm custom string
    found_target_string = False
    with tarfile.open(fileobj=io.BytesIO(fskapp1_tar_data), mode='r') as tar:
        for member in tar.getmembers():
            if member.name.endswith("eng.csv"):
                f = tar.extractfile(member)
                if f:
                    csv_text = f.read().decode('utf-8')
                    if f"{DEFAULT_TARGET_KEY},{expected_string}" in csv_text:
                        found_target_string = True
                        break
                        
    require(found_target_string, f"Custom string '{expected_string}' not found in unpacked eng.csv")
    
    return {
        "status": "PASS",
        "custom_string": expected_string,
        "verified_sections_count": len(verified_sections),
        "total_file_size": poc_dat_path.stat().st_size,
        "sha256": calculate_sha256(poc_dat_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sony DSC-G3 Custom String Display POC Generator")
    parser.add_argument("--string", default=DEFAULT_POC_STRING, help="Custom string to inject into SETUP_VERSION")
    parser.add_argument("--out", type=Path, default=EXTRACTED_ROOT / "D-G3V2_poc.dat", help="Output .dat path")
    parser.add_argument("--verify-only", type=Path, help="Verify an existing POC .dat file")
    
    args = parser.parse_args()
    
    if args.verify_only:
        res = verify_poc_image(args.verify_only, args.string)
        print("Verification Result:", res)
        return 0
        
    print(f"Generating DSC-G3 POC firmware with string: '{args.string}'")
    out_path = generate_poc_firmware(args.string, args.out)
    print(f"POC image written: {out_path} ({out_path.stat().st_size:,} bytes)")
    
    print("Verifying generated image...")
    res = verify_poc_image(out_path, args.string)
    print("Verification PASSED:", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
