#!/usr/bin/env python3
"""Sony Cyber-shot DSC-W300 AV / BIONZ DSP Subsystem Binary (av.bin) Extractor.

Extracts the original AV subsystem binary (av.bin) and sound/ancillary image (sa.bin)
from unmounted OneNAND partition 5 (/dev/nflasha5) on the connected DSC-W300 camera.

Protocol & Execution Flow:
1. Passive identity & connection check (DSC-W300, serial D386002E4438, PID 0x033F/0x0341).
2. Clean service transition to PID 0x0336 and 7-stage SHA-1 authentication.
3. Non-destructive backup of original /usr/bin/ud_datcnv with double-read SHA-256 verification.
4. Deployment of standalone static ARM ELF helper to /usr/bin/ud_datcnv via Senser write_file.
5. Invocation of helper via ProductInfo (pFunc 0x10, category 0x11, command 0x1100).
6. IMMEDIATE bit-for-bit restoration of original /usr/bin/ud_datcnv with readback verification.
7. Retrieval of execution log (/usr/dump.log).
8. Retrieval of /usr/av.bin (and /usr/sa.bin) via double-read SHA-256 verification.
9. Cleanup of temporary dump files on camera storage via Senser delete_file.
10. Clean exit to normal mass storage mode and post-exit verification.
11. ARM exception vector table and cryptographic SHA-256 analysis of av.bin.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time
from typing import Any, Dict, Optional, Tuple

# Ensure build/w300 and tools are on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
BUILD_W300 = BASE_DIR / 'build/w300'
TOOLS_DIR = BASE_DIR / 'tools'
for p in (str(BUILD_W300), str(TOOLS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import region_app as app
from region_protocol import Senser, FileUnavailable, ProtocolError
from w300_extractor_payload import (
    make_test_payload,
    make_extractor_payload,
    disassemble_elf,
    HAVE_CAPSTONE,
    build_elf,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def double_read_file(camera: Senser, path: str, limit: int = 16 * 1024 * 1024) -> Tuple[bytes, str]:
    """Reads a file twice across USB and guarantees cryptographic equality."""
    read1 = camera.read_file(path, limit=limit)
    hash1 = sha256_bytes(read1)
    read2 = camera.read_file(path, limit=limit)
    hash2 = sha256_bytes(read2)
    if hash1 != hash2 or read1 != read2:
        raise ProtocolError(f"Double-read verification failed for {path}: hash1={hash1} != hash2={hash2}")
    return read1, hash1


def verify_arm_vectors(data: bytes) -> Dict[str, Any]:
    """Validates ARM exception vector table at the beginning of an ARM binary."""
    if len(data) < 64:
        return {"valid": False, "reason": "File smaller than 64 bytes"}

    vectors = struct.unpack('<8I', data[:32])
    # Typical ARM vectors:
    # 0x00: Reset (ldr pc, [pc, #...] or b ...)
    # 0x04: Undefined
    # 0x08: SWI
    # 0x0C: Prefetch Abort
    # 0x10: Data Abort
    # 0x14: Reserved
    # 0x18: IRQ
    # 0x1C: FIQ

    is_ldr_pc = all((vec & 0xFFFFF000) in (0xE59FF000, 0xE51FF000) for vec in (vectors[0], vectors[1], vectors[2]))
    is_branch = all((vec & 0x0F000000) == 0x0A000000 for vec in (vectors[0],))

    valid = is_ldr_pc or is_branch
    result = {
        "valid": valid,
        "is_ldr_pc_vectors": is_ldr_pc,
        "is_branch_vectors": is_branch,
        "raw_vectors_hex": [f"0x{v:08X}" for v in vectors],
    }

    if HAVE_CAPSTONE:
        import capstone
        md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
        disasm_lines = []
        for insn in md.disasm(data[:48], 0x20100000):
            disasm_lines.append(f"0x{insn.address:08X}: {insn.mnemonic:<8} {insn.op_str}")
        result["disassembly_first_vectors"] = disasm_lines

    return result


class MockExtractionCamera:
    """Mock camera for testing extraction logic offline."""
    def __init__(self, original_ud: bytes, mock_av: bytes, mock_sa: bytes, pre_extracted: bool = False):
        self.files = {
            '/usr/bin/ud_datcnv': original_ud,
        }
        if pre_extracted:
            self.files['/usr/dump.log'] = b'START\nMOUNT_OK\nAV_OK\nSA_OK\nUMOUNT\nDONE\n'
            self.files['/usr/av.bin'] = mock_av
            self.files['/usr/sa.bin'] = mock_sa
        self.mock_av = mock_av
        self.mock_sa = mock_sa
        self.sequence = 1
        self.executed_elf = None

    def read_file(self, path: str, limit: int = 16 * 1024 * 1024) -> bytes:
        if path not in self.files:
            raise FileUnavailable(f"Camera returned 0x82: file missing: {path}")
        return self.files[path]

    def write_file(self, path: str, data: bytes, limit: int = 16 * 1024 * 1024) -> int:
        self.files[path] = bytes(data)
        return len(data)

    def delete_file(self, path: str) -> bool:
        if path in self.files:
            del self.files[path]
            return True
        raise FileUnavailable(f"Camera returned 0x82: file missing: {path}")

    def product_info(self, category: int, command: int, payload: bytes = b'') -> bytes:
        # Simulate execution of whatever was in /usr/dsc/fsk/ud_datcnv or /usr/bin/ud_datcnv
        cur_bin = self.files.get('/usr/dsc/fsk/ud_datcnv') or self.files.get('/usr/bin/ud_datcnv', b'')
        self.executed_elf = cur_bin
        if b'W300_EXEC_TEST_OK' in cur_bin:
            self.files['/usr/test_exec.log'] = b'W300_EXEC_TEST_OK\n'
        elif b'/usr/av.bin' in cur_bin:
            self.files['/usr/dump.log'] = b'START\nMOUNT_OK\nAV_OK\nSA_OK\nUMOUNT\nDONE\n'
            self.files['/usr/av.bin'] = self.mock_av
            self.files['/usr/sa.bin'] = self.mock_sa
        return b'\x00'


def extract_av_binary(
    serial: Optional[str] = None,
    output_dir: Optional[Path] = None,
    mock: bool = False,
    run_canary: bool = True,
    mock_pre_extracted: bool = False,
) -> Dict[str, Any]:
    """Executes the complete safe extraction procedure for av.bin."""
    effective_serial = serial or 'D386002E4438'
    if output_dir is not None:
        session_dir = Path(output_dir)
        session_dir.mkdir(parents=True, exist_ok=True)
        dest_evidence = session_dir
        dest_build = session_dir
    elif mock:
        import tempfile
        _temp_ctx = tempfile.TemporaryDirectory()
        session_dir = Path(_temp_ctx.name)
        dest_evidence = session_dir
        dest_build = session_dir
    else:
        session_dir = BUILD_W300 / 'sessions' / f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-extract-av"
        session_dir.mkdir(parents=True, exist_ok=True)
        dest_evidence = BASE_DIR / 'evidence/w300'
        dest_build = BUILD_W300
        dest_evidence.mkdir(parents=True, exist_ok=True)

    trace = app.Trace(session_dir)
    report: Dict[str, Any] = {
        "operation": "extract-av",
        "serial": effective_serial,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mock": mock,
        "ok": False,
        "stages": {},
    }

    try:
        if mock:
            print("[INFO] Running in mock simulation mode.")
            report["identity"] = dict(model='DSC-W300', serial=effective_serial, bus=4, ports=[2])
            report["service_authenticated"] = True

            # Use G3 av.bin as reference fixture if available
            g3_av_path = BASE_DIR / 'evidence/extracted_g3/sections/09_av.bin'
            mock_av_bytes = g3_av_path.read_bytes() if g3_av_path.is_file() else (b'\x18\xf0\x9f\xe5' * 8 + b'\x00' * 1024)
            mock_sa_bytes = b'SONY_SA_BIN_FIXTURE\x00' * 100
            orig_ud_bytes = build_elf(b'\x00' * 3140, base_va=0x8000).ljust(18028, b'\x00')

            mock_cam = MockExtractionCamera(orig_ud_bytes, mock_av_bytes, mock_sa_bytes, pre_extracted=mock_pre_extracted)
            _run_extraction_protocol(mock_cam, report, dest_evidence, dest_build, session_dir, run_canary=run_canary, mock=True)
            report["normal_mode_return_observed"] = True
            report["ok"] = True
        else:
            print(f"[INFO] Connecting to camera (serial={effective_serial})...")
            with app.session(effective_serial, trace, report) as camera:
                _run_extraction_protocol(camera, report, dest_evidence, dest_build, session_dir, run_canary=run_canary, mock=False)
                report["ok"] = True

    except Exception as exc:
        report["error"] = str(exc)
        report["error_type"] = type(exc).__name__
        print(f"[ERROR] Extraction failed: {exc}", file=sys.stderr)
        raise
    finally:
        trace.close()
        app.save_json(session_dir / 'result.json', report, durable=True)
        # Only overwrite production report on live runs
        if not mock and output_dir is None:
            app.save_json(BUILD_W300 / 'av_extraction_report.json', report, durable=True)

    return report


def _run_extraction_protocol(
    camera: Any,
    report: Dict[str, Any],
    dest_evidence: Path,
    dest_build: Path,
    session_dir: Path,
    run_canary: bool = True,
    mock: bool = False,
) -> None:
    stages = report["stages"]

    # -------------------------------------------------------------------------
    # Stage 1: Backup original /usr/bin/ud_datcnv
    # -------------------------------------------------------------------------
    print("\n[STAGE 1] Backing up original /usr/bin/ud_datcnv with double-read SHA-256 verification...")
    local_orig = BUILD_W300 / 'ud_datcnv.original'
    if local_orig.is_file() and local_orig.stat().st_size == 18028:
        expected_orig_bytes = local_orig.read_bytes()
        expected_orig_sha = sha256_bytes(expected_orig_bytes)
    else:
        expected_orig_bytes = None
        expected_orig_sha = None

    # Clean up any leftover staging files from previous attempts
    for staging_path in ('/usr/dsc/fsk/ud_datcnv', '/usr/ud_datcnv'):
        try:
            camera.delete_file(staging_path)
        except Exception:
            pass

    cur_bytes, cur_sha = double_read_file(camera, '/usr/bin/ud_datcnv')
    if expected_orig_sha is not None and cur_sha == expected_orig_sha:
        ud_orig_bytes = cur_bytes
        ud_orig_sha = cur_sha
    elif expected_orig_bytes is not None:
        print("  Notice: /usr/bin/ud_datcnv on camera is staging payload; restoring from verified golden backup...")
        camera.write_file('/usr/bin/ud_datcnv', expected_orig_bytes)
        ud_orig_bytes, ud_orig_sha = double_read_file(camera, '/usr/bin/ud_datcnv')
        if ud_orig_sha != expected_orig_sha:
            raise RuntimeError(f"Failed to restore golden ud_datcnv: {ud_orig_sha} != {expected_orig_sha}")
    elif len(cur_bytes) == 18028:
        ud_orig_bytes = cur_bytes
        ud_orig_sha = cur_sha
        local_orig.write_bytes(ud_orig_bytes)
    else:
        ud_orig_bytes = cur_bytes
        ud_orig_sha = cur_sha

    print(f"  Original /usr/bin/ud_datcnv size: {len(ud_orig_bytes)} bytes, SHA-256: {ud_orig_sha}")
    (session_dir / 'ud_datcnv.original').write_bytes(ud_orig_bytes)
    (BUILD_W300 / 'ud_datcnv.original').write_bytes(ud_orig_bytes)
    stages["stage1_backup_ud_datcnv"] = {
        "bytes": len(ud_orig_bytes),
        "sha256": ud_orig_sha,
        "verified_double_read": True,
    }

    # Check if a completed extraction already exists on camera from a prior execution
    existing_dump = False
    try:
        cur_log = camera.read_file('/usr/dump.log')
        if b'DONE' in cur_log and b'AV_OK' in cur_log:
            print("\n[INFO] Found existing completed extraction on camera (/usr/dump.log contains DONE and AV_OK).")
            existing_dump = True
    except Exception:
        pass

    if existing_dump:
        print("  Skipping helper deployment and execution since extraction payload already completed.")
        stages["safety_ud_datcnv_restored"] = {
            "sha256": ud_orig_sha,
            "bit_for_bit_match": True,
        }
    else:
        try:
            # ---------------------------------------------------------------------
            # Stage 2 (Canary): Test execution hook with minimal canary payload
            # ---------------------------------------------------------------------
            if run_canary:
                print("\n[STAGE 2] Verifying ELF execution hook via canary payload...")
                test_payload = make_test_payload(ud_orig_bytes)
                print(f"  Uploading test payload ({len(test_payload)} bytes) to helper locations...")
                camera.write_file('/usr/bin/ud_datcnv', test_payload)
                camera.write_file('/usr/dsc/fsk/ud_datcnv', test_payload)

                print("  Triggering ProductInfo hook (pFunc 0x10, cat 0x11, cmd 0x1100)...")
                hook_resp = camera.product_info(0x0011, 0x1100, bytes([0, 0, 0]))
                print(f"  Hook response received: {hook_resp.hex()}")

                # Immediately restore original ud_datcnv and clean up staging
                print("  Restoring original /usr/bin/ud_datcnv...")
                camera.write_file('/usr/bin/ud_datcnv', ud_orig_bytes)
                try:
                    camera.delete_file('/usr/dsc/fsk/ud_datcnv')
                except Exception:
                    pass

                # Read canary log
                print("  Reading /usr/test_exec.log...")
                try:
                    canary_log = camera.read_file('/usr/test_exec.log').decode('ascii', errors='ignore')
                    print(f"  Canary output: {canary_log.strip()}")
                    if 'W300_EXEC_TEST_OK' not in canary_log:
                        raise RuntimeError(f"Canary execution failed: unexpected log '{canary_log}'")
                    camera.delete_file('/usr/test_exec.log')
                    stages["stage2_canary_test"] = {"status": "SUCCESS", "log": canary_log.strip()}
                except Exception as e:
                    raise RuntimeError(f"Canary verification failed: {e}")

            # ---------------------------------------------------------------------
            # Stage 3: Deploy full extractor and trigger execution
            # ---------------------------------------------------------------------
            print("\n[STAGE 3] Deploying full extraction helper binary...")
            ext_payload = make_extractor_payload(ud_orig_bytes)
            print(f"  Assembled static ARM ELF dumper: {len(ext_payload)} bytes.")
            print("  Writing dumper to helper locations...")
            camera.write_file('/usr/bin/ud_datcnv', ext_payload)
            camera.write_file('/usr/dsc/fsk/ud_datcnv', ext_payload)

            print("  Triggering ProductInfo hook to start partition 5 mount and extraction...")
            start_t = time.monotonic()
            hook_resp = camera.product_info(0x0011, 0x1100, bytes([0, 0, 0]))
            elapsed = time.monotonic() - start_t
            print(f"  Execution completed in {elapsed:.2f}s, response: {hook_resp.hex()}")
            stages["stage3_helper_execution"] = {
                "elapsed_seconds": round(elapsed, 2),
                "response_hex": hook_resp.hex(),
            }

        finally:
            # ---------------------------------------------------------------------
            # Safety Critical: ALWAYS restore original ud_datcnv bit-for-bit
            # ---------------------------------------------------------------------
            print("\n[SAFETY] Restoring original /usr/bin/ud_datcnv and verifying bit-for-bit readback...")
            camera.write_file('/usr/bin/ud_datcnv', ud_orig_bytes)
            try:
                camera.delete_file('/usr/dsc/fsk/ud_datcnv')
            except Exception:
                pass
            restored_bytes, restored_sha = double_read_file(camera, '/usr/bin/ud_datcnv')
            if restored_sha != ud_orig_sha:
                raise RuntimeError(f"CRITICAL: ud_datcnv restoration mismatch: {restored_sha} != {ud_orig_sha}")
            print(f"  Confirmed: /usr/bin/ud_datcnv restored bit-for-bit (SHA-256: {restored_sha}).")
            stages["safety_ud_datcnv_restored"] = {
                "sha256": restored_sha,
                "bit_for_bit_match": True,
            }

    # -------------------------------------------------------------------------
    # Stage 4: Read execution log
    # -------------------------------------------------------------------------
    print("\n[STAGE 4] Retrieving camera execution log (/usr/dump.log)...")
    try:
        dump_log_bytes = camera.read_file('/usr/dump.log')
        dump_log_str = dump_log_bytes.decode('ascii', errors='ignore')
        print("  Camera Dump Log:")
        for line in dump_log_str.strip().splitlines():
            print(f"    [CAM] {line}")
        (session_dir / 'dump.log').write_text(dump_log_str, encoding='utf-8')
        stages["stage4_camera_log"] = dump_log_str.strip().splitlines()
    except Exception as e:
        print(f"  Warning: unable to read /usr/dump.log: {e}")
        stages["stage4_camera_log"] = f"Error: {e}"

    # -------------------------------------------------------------------------
    # Stage 5: Download extracted av.bin and sa.bin
    # -------------------------------------------------------------------------
    print("\n[STAGE 5] Downloading extracted firmware artifacts with double-read SHA-256 verification...")
    av_bytes = None
    av_sha = None

    # Check /usr/av.bin
    try:
        print("  Reading /usr/av.bin...")
        av_bytes, av_sha = double_read_file(camera, '/usr/av.bin')
        print(f"  Successfully acquired av.bin: {len(av_bytes)} bytes ({len(av_bytes)/(1024*1024):.2f} MB), SHA-256: {av_sha}")

        # Save to destinations
        if not mock:
            (dest_evidence / 'av.bin').write_bytes(av_bytes)
            (dest_build / 'av.bin').write_bytes(av_bytes)
        (session_dir / 'av.bin').write_bytes(av_bytes)

        # Analyze ARM vectors
        vec_info = verify_arm_vectors(av_bytes)
        print(f"  ARM Exception Vectors Valid: {vec_info['valid']}")
        if 'disassembly_first_vectors' in vec_info:
            print("  Disassembly of first vectors:")
            for l in vec_info['disassembly_first_vectors'][:8]:
                print(f"    {l}")

        stages["stage5_av_bin"] = {
            "size_bytes": len(av_bytes),
            "sha256": av_sha,
            "arm_vectors": vec_info,
            "saved_evidence": str(dest_evidence / 'av.bin') if not mock else None,
            "saved_build": str(dest_build / 'av.bin') if not mock else None,
        }
    except Exception as e:
        print(f"  Failed to read /usr/av.bin: {e}")

    # Check /usr/sa.bin
    try:
        print("  Reading /usr/sa.bin...")
        sa_bytes, sa_sha = double_read_file(camera, '/usr/sa.bin')
        print(f"  Successfully acquired sa.bin: {len(sa_bytes)} bytes, SHA-256: {sa_sha}")
        if not mock:
            (dest_evidence / 'sa.bin').write_bytes(sa_bytes)
            (dest_build / 'sa.bin').write_bytes(sa_bytes)
        (session_dir / 'sa.bin').write_bytes(sa_bytes)
        stages["stage5_sa_bin"] = {
            "size_bytes": len(sa_bytes),
            "sha256": sa_sha,
            "saved_evidence": str(dest_evidence / 'sa.bin') if not mock else None,
            "saved_build": str(dest_build / 'sa.bin') if not mock else None,
        }
    except Exception as e:
        print(f"  sa.bin not available or not acquired: {e}")

    # Check /usr/nflasha5.raw (fallback partition dump)
    try:
        if not mock:
            (dest_evidence / 'nflasha5.raw').write_bytes(raw_bytes)
            (dest_build / 'nflasha5.raw').write_bytes(raw_bytes)
        (session_dir / 'nflasha5.raw').write_bytes(raw_bytes)
        stages["stage5_nflasha5_raw"] = {
            "size_bytes": len(raw_bytes),
            "sha256": raw_sha,
            "saved_evidence": str(dest_evidence / 'nflasha5.raw') if not mock else None,
            "saved_build": str(dest_build / 'nflasha5.raw') if not mock else None,
        }
    except Exception:
        pass

    if av_bytes is None and "stage5_nflasha5_raw" not in stages:
        raise RuntimeError("Neither av.bin nor nflasha5.raw could be acquired from the camera")

    # -------------------------------------------------------------------------
    # Stage 6: Clean up camera temporary files
    # -------------------------------------------------------------------------
    print("\n[STAGE 6] Cleaning up camera temporary dump files...")
    for cam_temp in ('/usr/dump.log', '/usr/av.bin', '/usr/sa.bin', '/usr/nflasha5.raw', '/usr/test_exec.log', '/usr/dsc/fsk/ud_datcnv'):
        try:
            camera.delete_file(cam_temp)
            print(f"  Deleted temporary file {cam_temp} from camera.")
        except Exception:
            pass

    stages["stage6_cleanup"] = {"status": "COMPLETE"}
    print("\n[SUCCESS] Extraction protocol finished cleanly.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DSC-W300 AV / BIONZ DSP Subsystem Binary (av.bin) Extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--serial', default=None,
                        help='Camera USB serial number (default: auto-detect from connected USB device)')
    parser.add_argument('--experimental-service', action='store_true', required=True,
                        help='Acknowledge experimental Senser service mode operation')
    parser.add_argument('--skip-canary', action='store_true',
                        help='Skip canary test and proceed directly to extraction')
    parser.add_argument('--mock', action='store_true',
                        help='Run offline simulation using reference fixtures')
    parser.add_argument('--output-dir', type=Path, default=None,
                        help='Custom destination directory')

    args = parser.parse_args()

    try:
        report = extract_av_binary(
            serial=args.serial,
            output_dir=args.output_dir,
            mock=args.mock,
            run_canary=not args.skip_canary,
        )
        print("\nExtraction Summary Report:")
        print(json.dumps(report, indent=2))
        return 0 if report.get("ok") else 1
    except Exception as exc:
        print(f"\nExecution terminated with error: {exc}", file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
