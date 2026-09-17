#!/usr/bin/env python3
"""Offline DSC-G3 text experiment with pinned source and exact-change verification.

The output proves container integrity and an isolated string substitution only.
Camera acceptance, LCD rendering and hardware behavior have not been validated.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path
import tarfile
from typing import Dict, List, Optional, Tuple

from g3_firmware_parser import (
    CXD4108MsCrypter,
    BLOCK_HEADER_SIZE,
    MANIFEST_SIZE,
    KEY_CXD4108_MS,
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
    require(new_val and len(new_val.encode('utf-8')) <= 7, 'Custom text must be 1 to 7 UTF-8 bytes')
    require(new_val.isprintable() and ',' not in new_val, 'Custom text contains forbidden characters')
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
    
    require(sections_meta[modified_section_index]['name'] == new_section_name, 'Section name mismatch')
    require(new_size > 0, 'Section size must be positive')
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


from g3_verified import (SOURCE, trusted_source, verified_extracted, assemble,
    check_output, publish, verify_expected)


def patch_original_tar(original_tar: bytes, custom_string: str) -> bytes:
    """Change only the seven-byte Version value; preserve TAR headers and all other bytes."""
    with tarfile.open(fileobj=io.BytesIO(original_tar), mode='r:') as archive:
        matches = [m for m in archive.getmembers() if m.name.removeprefix('./') == ENG_CSV_RELPATH]
        require(len(matches) == 1 and matches[0].isfile(), 'Expected exactly one regular target eng.csv')
        member = matches[0]
        original = original_tar[member.offset_data:member.offset_data + member.size]
        # Validate using CSV semantics, then pad to preserve exact member length.
        patch_csv_text(original.decode('utf-8'), DEFAULT_TARGET_KEY, DEFAULT_ORIGINAL_VAL, custom_string)
        padded = custom_string.encode('utf-8').ljust(len(DEFAULT_ORIGINAL_VAL), b' ')
        target = (DEFAULT_TARGET_KEY + ',' + DEFAULT_ORIGINAL_VAL).encode()
        replacement = (DEFAULT_TARGET_KEY + ',').encode() + padded
        lines = original.splitlines(keepends=True)
        indices = [i for i, line in enumerate(lines) if line.startswith((DEFAULT_TARGET_KEY + ',').encode())]
        require(len(indices) == 1, 'Ambiguous target row')
        i = indices[0]
        require(lines[i].rstrip(b'\r\n') == target, 'Unexpected target value')
        lines[i] = replacement + lines[i][len(target):]
        patched = b''.join(lines)
        require(len(patched) == len(original), 'Target size changed')
        return original_tar[:member.offset_data] + patched + original_tar[member.offset_data + member.size:]


def expected_poc(baseline, custom_string):
    manifest, sections, payloads = baseline
    require(sections[10]['name'] == 'fskapp1.tar', 'Unexpected text section identity')
    patched = list(payloads)
    patched[10] = patch_original_tar(payloads[10], custom_string)
    return manifest, patched


def generate_poc_firmware(custom_string=DEFAULT_POC_STRING, output_dat_path=None,
                          *, source=SOURCE, sections_dir=SECTIONS_DIR, cntent_path=None,
                          overwrite=False):
    output_dat_path = output_dat_path or REPO_ROOT / 'build/g3/D-G3V2_poc.dat'
    check_output(output_dat_path, source, overwrite)
    cntent_path = cntent_path or EXTRACTED_ROOT / 'cntent.dat'
    require(not Path(output_dat_path).resolve().is_relative_to(Path(sections_dir).resolve())
            and Path(output_dat_path).resolve() != Path(cntent_path).resolve(), 'Output collides with derived input')
    baseline = trusted_source(source)
    verified_extracted(sections_dir, cntent_path, baseline)
    manifest, payloads = expected_poc(baseline, custom_string)
    return publish(assemble(manifest, payloads, baseline.container), output_dat_path,
                   lambda path: verify_expected(path, baseline, manifest, payloads), source, overwrite)


def verify_poc_image(poc_dat_path, expected_string=DEFAULT_POC_STRING, *, source=SOURCE):
    baseline = trusted_source(source)
    manifest, payloads = expected_poc(baseline, expected_string)
    result = verify_expected(poc_dat_path, baseline, manifest, payloads)
    result.update(custom_string=expected_string, verified_sections_count=24)
    return result


def main():
    parser = argparse.ArgumentParser(description='DSC-G3 offline text experiment; hardware not validated')
    parser.add_argument('--string', default=DEFAULT_POC_STRING, help='1 to 7 UTF-8 bytes')
    parser.add_argument('--out', type=Path, default=REPO_ROOT / 'build/g3/D-G3V2_poc.dat')
    parser.add_argument('--verify-only', type=Path)
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    if args.verify_only:
        print(verify_poc_image(args.verify_only, args.string))
    else:
        output = generate_poc_firmware(args.string, args.out, overwrite=args.overwrite)
        print({'output': str(output), 'status': 'OFFLINE_INTEGRITY_VERIFIED', 'offline_only': True, 'hardware_validation': 'not_performed'})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
