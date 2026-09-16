#!/usr/bin/env python3
"""Adversarial Challenge & Stress Test Harness for Sony DSC-W300 Service Tool.

Target: tools/w300_service_tool.py
Agent: challenger_service_1 (Empirical Challenger)

Test Categories:
- Category A: Malformed Packets & Corrupted Byte Headers
- Category B: Corrupted Challenge/Response Authentication Digests
- Category C: Out-of-Order Command Sequences & State Machine Violations
- Category D: Safety Guardrail Strict Exit Code 2 Enforcement
- Category E: Fail-Closed --dry-run Non-Volatile Memory Invariance
- Category F: Cryptographic Fault Invariant & EVR Page Boundary Stress
"""

from __future__ import annotations

import binascii
import contextlib
import hashlib
import io
from pathlib import Path
import random
import struct
import subprocess
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
TOOL_SCRIPT_PATH = TOOLS_DIR / "w300_service_tool.py"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from w300_service_tool import (
    _left_rotate,
    sha1,
    sha1_faulty,
    SenserWireProtocol,
    Cee8Payload,
    W300MockUsbCamera,
    W300ServiceController,
    build_parser,
    main,
)


class BaseAdversarialTestCase(unittest.TestCase):
    """Base test case with stdout/stderr redirection for clean execution."""

    def setUp(self):
        super().setUp()
        self._stdout_trap = io.StringIO()
        self._stderr_trap = io.StringIO()
        self._out_ctx = contextlib.redirect_stdout(self._stdout_trap)
        self._err_ctx = contextlib.redirect_stderr(self._stderr_trap)
        self._out_ctx.__enter__()
        self._err_ctx.__enter__()

    def tearDown(self):
        self._err_ctx.__exit__(None, None, None)
        self._out_ctx.__exit__(None, None, None)
        super().tearDown()


# ============================================================================
# Category A: Malformed Packets and Corrupted Byte Headers
# ============================================================================

class TestCategoryAMalformedPackets(BaseAdversarialTestCase):
    """Stress-tests wire parser and mock camera against malformed/truncated packets."""

    def setUp(self):
        super().setUp()
        self.protocol = SenserWireProtocol()
        self.camera = W300MockUsbCamera(destination="J1")

    def test_parse_packet_undersized_headers(self):
        """Headers strictly shorter than 12 bytes must raise ValueError."""
        truncated_samples = [
            b"",
            b"\x00",
            b"\x01\x02",
            b"\x00\x00\x00\x00",
            b"A" * 7,
            b"B" * 11,
        ]
        for sample in truncated_samples:
            with self.subTest(sample_len=len(sample)):
                with self.assertRaises(ValueError) as ctx:
                    self.protocol.parse_packet(sample)
                self.assertIn("Packet too short", str(ctx.exception))

    def test_parse_packet_declared_size_exceeds_buffer(self):
        """Header with declared payload size exceeding actual received buffer."""
        # 12-byte header declaring 100-byte payload, but buffer is only 16 bytes total (4 bytes payload)
        header = struct.pack(
            SenserWireProtocol.HEADER_FORMAT,
            100,  # size = 100
            SenserWireProtocol.PFUNC_ADJUST_CONTROL,
            1, 0, 0, 0, 0
        )
        packet = header + b"1234"
        parsed = self.protocol.parse_packet(packet)
        # Verify parser behavior on truncated payload
        self.assertEqual(parsed['size'], 100)
        self.assertEqual(len(parsed['payload']), 4)  # payload is truncated to actual available

    def test_parse_auth_packet_undersized_inputs(self):
        """AuthPackets shorter than 516 bytes must fail with ValueError."""
        short_buffers = [
            b"",
            b"\x00" * 2,
            b"\x00" * 4,
            b"\x00" * 100,
            b"\x00" * 515,
        ]
        for buf in short_buffers:
            with self.subTest(buf_len=len(buf)):
                with self.assertRaises(ValueError) as ctx:
                    self.protocol.parse_auth_packet(buf)
                self.assertIn("AuthPacket too short", str(ctx.exception))

    def test_camera_auth_phase_rejects_truncated_packet(self):
        """Mock camera in unauthenticated state rejects packets under 516 bytes."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)  # switch to Senser
        self.assertEqual(self.camera.auth_state, 0)
        with self.assertRaises(ValueError) as ctx:
            self.camera.bulk_write(b"\x00" * 200)
        self.assertIn("Expected 516-byte AuthPacket", str(ctx.exception))

    def test_camera_auth_phase_rejects_unknown_command_id(self):
        """AuthPacket with invalid command opcode (e.g. cmd=99) fails closed."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        bad_packet = self.protocol.build_auth_packet(cmd=99)
        with self.assertRaises(ValueError) as ctx:
            self.camera.bulk_write(bad_packet)
        self.assertIn("Unknown auth command", str(ctx.exception))

    def test_camera_operational_phase_truncated_adjust_payload(self):
        """Authenticated camera receiving AdjustControl frame with payload < 4 bytes."""
        # Complete full authentication
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        # Step 1
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=1))
        self.camera.bulk_read()
        # Step 2
        digest = sha1_faulty(self.camera.auth_challenge[:4])
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest))
        self.camera.bulk_read()
        # Step 3
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=5))
        self.camera.bulk_read()
        self.assertEqual(self.camera.auth_state, 2)

        # Send AdjustControl packet with truncated payload (2 bytes instead of >= 4 bytes for cat+cmd)
        truncated_packet = self.protocol.build_packet(
            p_func=SenserWireProtocol.PFUNC_ADJUST_CONTROL,
            payload=b"\x06\x03",  # only category, missing cmd
            pad_to_512=False,
        )
        with self.assertRaises(struct.error):
            self.camera.bulk_write(truncated_packet)

    def test_camera_operational_phase_truncated_property_id(self):
        """Authenticated camera receiving BackupRead frame with truncated prop_id."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        # Authenticate
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=1))
        self.camera.bulk_read()
        digest = sha1_faulty(self.camera.auth_challenge[:4])
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest))
        self.camera.bulk_read()
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=5))
        self.camera.bulk_read()

        # BackupRead requires Category (2) + Cmd (2) + PropId (4) = 8 bytes.
        # Send only 6 bytes (2 bytes prop_id).
        bad_payload = struct.pack('<HH', SenserWireProtocol.CAT_BACKUP, SenserWireProtocol.CMD_BACKUP_READ) + b"\x00\x01"
        packet = self.protocol.build_packet(SenserWireProtocol.PFUNC_ADJUST_CONTROL, bad_payload, pad_to_512=False)
        with self.assertRaises(struct.error):
            self.camera.bulk_write(packet)

    def test_camera_operational_phase_empty_id1_lock_param(self):
        """Authenticated camera receiving ID1 lock toggle with missing parameter byte."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        # Authenticate
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=1))
        self.camera.bulk_read()
        digest = sha1_faulty(self.camera.auth_challenge[:4])
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest))
        self.camera.bulk_read()
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=5))
        self.camera.bulk_read()

        # CMD_BACKUP_ID1_LOCK with 0-byte param
        payload = struct.pack('<HH', SenserWireProtocol.CAT_BACKUP, SenserWireProtocol.CMD_BACKUP_ID1_LOCK)
        packet = self.protocol.build_packet(SenserWireProtocol.PFUNC_ADJUST_CONTROL, payload, pad_to_512=False)
        with self.assertRaises(IndexError):
            self.camera.bulk_write(packet)

    def test_camera_operational_unknown_pfunc_fallback(self):
        """Authenticated camera receiving unknown pFunc (0x9999) responds with fallback header."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        # Authenticate
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=1))
        self.camera.bulk_read()
        digest = sha1_faulty(self.camera.auth_challenge[:4])
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest))
        self.camera.bulk_read()
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=5))
        self.camera.bulk_read()

        # Send unknown pFunc 0x9999
        pkt = self.protocol.build_packet(p_func=0x9999, payload=b"test_payload")
        self.camera.bulk_write(pkt)
        resp = self.protocol.parse_packet(self.camera.bulk_read())
        self.assertEqual(resp['pFunc'], 0x9999)
        self.assertEqual(resp['response'], 0)

    def test_camera_operational_unknown_category_fallback(self):
        """Authenticated camera receiving unknown category under AdjustControl falls back to resp=0."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        # Authenticate
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=1))
        self.camera.bulk_read()
        digest = sha1_faulty(self.camera.auth_challenge[:4])
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest))
        self.camera.bulk_read()
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=5))
        self.camera.bulk_read()

        # Category 0x7777, Cmd 0x0001
        payload = struct.pack('<HH', 0x7777, 0x0001) + b"hello"
        pkt = self.protocol.build_packet(SenserWireProtocol.PFUNC_ADJUST_CONTROL, payload)
        self.camera.bulk_write(pkt)
        resp = self.protocol.parse_packet(self.camera.bulk_read())
        self.assertEqual(resp['response'], 0)


# ============================================================================
# Category B: Corrupted Challenge/Response Authentication
# ============================================================================

class CorruptStep1Camera(W300MockUsbCamera):
    """Subclass that returns algorithm ret=1 (e.g. MD5) in Step 1."""
    def bulk_write(self, data: bytes) -> int:
        if self.auth_state == 0 and len(data) >= 4:
            raw_cmd, salt = struct.unpack('>HH', data[:4])
            cmd = ((~raw_cmd) & 0xFFFF) - salt
            if cmd == 1:
                self.auth_state = 1
                # Return ret=1 (invalid algorithm)
                resp_cmd = (~(1 + 0)) & 0xFFFF
                self.tx_buffer = bytearray(struct.pack('>HH', resp_cmd, 0) + (b'\x00' * 512))
                return len(data)
        return super().bulk_write(data)


class CorruptStep3Camera(W300MockUsbCamera):
    """Subclass that returns status=0x00 (FAILURE) in Step 3."""
    def bulk_write(self, data: bytes) -> int:
        if self.auth_state == 1 and len(data) >= 4:
            raw_cmd, salt = struct.unpack('>HH', data[:4])
            cmd = ((~raw_cmd) & 0xFFFF) - salt
            if cmd == 5:
                # Step 3 with status=0x00
                resp_cmd = (~6) & 0xFFFF
                resp_data = bytes([0x00]) + (b'\x00' * 511)
                self.tx_buffer = bytearray(struct.pack('>HH', resp_cmd, 0) + resp_data)
                return len(data)
        return super().bulk_write(data)


class TestCategoryBAuthenticationCorruptions(BaseAdversarialTestCase):
    """Stress-tests authentication state machine against bit-flips, forgery, and desync."""

    def setUp(self):
        super().setUp()
        self.camera = W300MockUsbCamera(destination="J1")
        self.controller = W300ServiceController(mock_camera=self.camera)
        self.protocol = SenserWireProtocol()

    def test_auth_step1_invalid_algorithm_code_raises_permission_error(self):
        """If camera returns algorithm != 2 (e.g. ret=1 MD5), controller must abort."""
        bad_cam = CorruptStep1Camera(destination="J1")
        ctrl = W300ServiceController(mock_camera=bad_cam)
        ctrl.switch_to_senser_mode()

        with self.assertRaises(PermissionError) as ctx:
            ctrl.authenticate_senser()
        self.assertIn("Unexpected auth algorithm requested", str(ctx.exception))

    def test_auth_step2_corrupted_digest_rejected_and_resets_auth_state(self):
        """Corrupted digest bytes in step 2 must fail and reset camera auth_state to 0."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        # Step 1
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=1))
        self.camera.bulk_read()
        self.assertEqual(self.camera.auth_state, 1)

        # Step 2: send corrupted digest (bit-flipped)
        true_digest = bytearray(sha1_faulty(self.camera.auth_challenge[:4]))
        true_digest[0] ^= 0xFF  # corrupt first byte
        bad_payload = bytes([0x01]) + bytes(true_digest)
        step2_pkt = self.protocol.build_auth_packet(cmd=3, data=bad_payload)

        with self.assertRaises(PermissionError) as ctx:
            self.camera.bulk_write(step2_pkt)
        self.assertIn("Cryptographic challenge failed", str(ctx.exception))
        # Critical security invariant: auth state must be reset to unauthenticated (0)
        self.assertEqual(self.camera.auth_state, 0)

    def test_auth_step2_standard_sha1_rejected(self):
        """Standard SHA-1 (without faulty length truncation) must be rejected."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=1))
        self.camera.bulk_read()

        bogus_digest = hashlib.sha1(b"random_wrong_challenge").digest()
        bad_payload = bytes([0x01]) + bogus_digest
        step2_pkt = self.protocol.build_auth_packet(cmd=3, data=bad_payload)

        with self.assertRaises(PermissionError):
            self.camera.bulk_write(step2_pkt)
        self.assertEqual(self.camera.auth_state, 0)

    def test_auth_step2_invalid_flag_rejected(self):
        """Step 2 packet with correct digest but flag == 0x00 instead of 0x01."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=1))
        self.camera.bulk_read()

        digest = sha1_faulty(self.camera.auth_challenge[:4])
        bad_flag_payload = bytes([0x00]) + digest  # flag 0x00 instead of 0x01
        step2_pkt = self.protocol.build_auth_packet(cmd=3, data=bad_flag_payload)

        with self.assertRaises(PermissionError):
            self.camera.bulk_write(step2_pkt)
        self.assertEqual(self.camera.auth_state, 0)

    def test_auth_step3_rejected_status_raises_permission_error(self):
        """Step 3 returning status != 0x01 raises PermissionError in controller."""
        bad_cam = CorruptStep3Camera(destination="J1")
        ctrl = W300ServiceController(mock_camera=bad_cam)
        ctrl.switch_to_senser_mode()

        with self.assertRaises(PermissionError) as ctx:
            ctrl.authenticate_senser()
        self.assertIn("Auth finalization rejected by camera", str(ctx.exception))
        self.assertFalse(ctrl.authenticated)

    def test_auth_replay_attack_rejected(self):
        """Replaying a response computed for challenge A against camera with challenge B fails."""
        cam_a = W300MockUsbCamera(destination="J1")
        cam_b = W300MockUsbCamera(destination="J1")
        cam_b.auth_challenge = b"\xde\xad\xbe\xef\x01\x02\x03\x04"

        # Obtain response digest from cam_a
        cam_a.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        cam_a.bulk_write(self.protocol.build_auth_packet(cmd=1))
        _, _, data_a = self.protocol.parse_auth_packet(cam_a.bulk_read())
        digest_a = sha1_faulty(data_a[:4])

        # Attempt replay against cam_b
        cam_b.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        cam_b.bulk_write(self.protocol.build_auth_packet(cmd=1))
        cam_b.bulk_read()

        replay_pkt = self.protocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest_a)
        with self.assertRaises(PermissionError):
            cam_b.bulk_write(replay_pkt)
        self.assertEqual(cam_b.auth_state, 0)


# ============================================================================
# Category C: Out-of-Order Command Sequences & State Transitions
# ============================================================================

class TestCategoryCOutOfOrderSequences(BaseAdversarialTestCase):
    """Stress-tests state machine order-of-operation constraints."""

    def setUp(self):
        super().setUp()
        self.camera = W300MockUsbCamera(destination="J1")
        self.protocol = SenserWireProtocol()

    def test_bulk_write_while_in_mass_storage_mode_fails(self):
        """Attempting bulk write while camera is in MASS_STORAGE mode must raise ConnectionError."""
        self.assertEqual(self.camera.mode, "MASS_STORAGE")
        with self.assertRaises(ConnectionError) as ctx:
            self.camera.bulk_write(b"\x00" * 516)
        self.assertIn("Cannot bulk write: camera not in Senser mode", str(ctx.exception))

    def test_auth_step2_before_step1_fails(self):
        """Sending Step 2 verification before Step 1 challenge must raise sequence PermissionError."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        self.assertEqual(self.camera.auth_state, 0)

        # Direct Step 2 (cmd=3)
        pkt = self.protocol.build_auth_packet(cmd=3, data=bytes([0x01]) + (b"\x00" * 20))
        with self.assertRaises(PermissionError) as ctx:
            self.camera.bulk_write(pkt)
        self.assertIn("Auth protocol sequence error: step 2 without step 1", str(ctx.exception))

    def test_write_destination_while_unauthenticated_fails(self):
        """Attempting to write destination property before authentication."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        self.assertEqual(self.camera.auth_state, 0)

        # Build Senser bulk write packet
        write_pkt = self.protocol.build_write_prop(Cee8Payload.PROP_DESTINATION, b"CEE8")
        # In auth_state < 2, bulk_write interprets this as an AuthPacket.
        # Since it is a Senser bulk packet (512-padded, header starting with size=8), cmd unpack is bogus
        with self.assertRaises(ValueError):
            self.camera.bulk_write(write_pkt)

    def test_write_destination_while_service_board_locked_returns_error_5(self):
        """Attempting to write CEE8 destination while ID1 is locked returns resp=5 (Access Denied)."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        # Authenticate cleanly
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=1))
        self.camera.bulk_read()
        digest = sha1_faulty(self.camera.auth_challenge[:4])
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest))
        self.camera.bulk_read()
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=5))
        self.camera.bulk_read()
        self.assertEqual(self.camera.auth_state, 2)
        self.assertTrue(self.camera.id1_locked)

        # Attempt to write PROP_DESTINATION
        write_pkt = self.protocol.build_write_prop(Cee8Payload.PROP_DESTINATION, b"CEE8")
        self.camera.bulk_write(write_pkt)
        resp_raw = self.camera.bulk_read()
        resp = self.protocol.parse_packet(resp_raw)

        self.assertEqual(resp['response'], 5)  # 0x05 Access Denied / Service Board Required
        self.assertEqual(self.camera.rejected_write_count, 1)
        # Invariant: staging RAM and flash store MUST remain unchanged
        self.assertEqual(self.camera.staging_ram[Cee8Payload.PROP_DESTINATION], b"J1\x00\x00")
        self.assertEqual(self.camera.flash_store[Cee8Payload.PROP_DESTINATION], b"J1\x00\x00")

    def test_reboot_discards_uncommitted_staging_ram(self):
        """Rebooting camera before commit_flash discards uncommitted staging RAM changes."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        # Authenticate
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=1))
        self.camera.bulk_read()
        digest = sha1_faulty(self.camera.auth_challenge[:4])
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest))
        self.camera.bulk_read()
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=5))
        self.camera.bulk_read()

        # Unlock ID1
        self.camera.bulk_write(self.protocol.build_id1_lock(lock=False))
        self.camera.bulk_read()
        self.assertFalse(self.camera.id1_locked)

        # Write CEE8 to staging RAM
        self.camera.bulk_write(self.protocol.build_write_prop(Cee8Payload.PROP_DESTINATION, b"CEE8"))
        self.camera.bulk_read()
        self.assertEqual(self.camera.staging_ram[Cee8Payload.PROP_DESTINATION], b"CEE8")
        self.assertEqual(self.camera.flash_store[Cee8Payload.PROP_DESTINATION], b"J1\x00\x00")

        # Now reboot without calling commit_flash (CMD_BACKUP_SAVE)
        self.camera.control_request(0x43, 0x01, 0xC800, 0x2855)
        self.assertEqual(self.camera.mode, "MASS_STORAGE")
        self.assertEqual(self.camera.reboot_count, 1)

        # Critical invariant: staging RAM was restored from flash (J1), and ID1 is re-locked
        self.assertEqual(self.camera.staging_ram[Cee8Payload.PROP_DESTINATION], b"J1\x00\x00")
        self.assertEqual(self.camera.flash_store[Cee8Payload.PROP_DESTINATION], b"J1\x00\x00")
        self.assertTrue(self.camera.id1_locked)

    def test_id1_relock_blocks_subsequent_writes(self):
        """Unlocking ID1, performing a write, re-locking ID1, then attempting another write."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        # Authenticate
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=1))
        self.camera.bulk_read()
        digest = sha1_faulty(self.camera.auth_challenge[:4])
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest))
        self.camera.bulk_read()
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=5))
        self.camera.bulk_read()

        # Unlock ID1
        self.camera.bulk_write(self.protocol.build_id1_lock(lock=False))
        self.camera.bulk_read()
        self.assertFalse(self.camera.id1_locked)

        # Write 1 succeeds
        self.camera.bulk_write(self.protocol.build_write_prop(Cee8Payload.PROP_DESTINATION, b"CEE8"))
        r1 = self.protocol.parse_packet(self.camera.bulk_read())
        self.assertEqual(r1['response'], 0)

        # Re-lock ID1
        self.camera.bulk_write(self.protocol.build_id1_lock(lock=True))
        r_lock = self.protocol.parse_packet(self.camera.bulk_read())
        self.assertEqual(r_lock['response'], 0)
        self.assertTrue(self.camera.id1_locked)

        # Write 2 (attempting to alter language mask while re-locked) must fail with 5
        self.camera.bulk_write(self.protocol.build_write_prop(Cee8Payload.PROP_LANG_BASE, Cee8Payload.LANG_MASK_CEE8))
        r2 = self.protocol.parse_packet(self.camera.bulk_read())
        self.assertEqual(r2['response'], 5)
        self.assertEqual(self.camera.rejected_write_count, 1)

    def test_unlocked_write_to_non_protected_property(self):
        """Non-regional property (e.g. PROP_SERIAL) can be written even if ID1 is locked."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        # Authenticate
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=1))
        self.camera.bulk_read()
        digest = sha1_faulty(self.camera.auth_challenge[:4])
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest))
        self.camera.bulk_read()
        self.camera.bulk_write(self.protocol.build_auth_packet(cmd=5))
        self.camera.bulk_read()
        self.assertTrue(self.camera.id1_locked)

        # Write to PROP_SERIAL (non-regional)
        new_serial = struct.pack('<I', 9999999)
        pkt = self.protocol.build_write_prop(Cee8Payload.PROP_SERIAL, new_serial)
        self.camera.bulk_write(pkt)
        resp = self.protocol.parse_packet(self.camera.bulk_read())
        self.assertEqual(resp['response'], 0)  # Allowed because not a regional property!
        self.assertEqual(self.camera.staging_ram[Cee8Payload.PROP_SERIAL], new_serial)

    def test_idempotent_destination_flip_flop(self):
        """Full programmatic flip: J1 -> CEE8 -> J1."""
        controller = W300ServiceController(mock_camera=self.camera)

        # Step 1: J1 -> CEE8
        controller.run_full_cycle()
        self.assertEqual(self.camera.flash_store[Cee8Payload.PROP_DESTINATION], b"CEE8")
        self.assertEqual(self.camera.flash_store[Cee8Payload.PROP_VIDEO_OUT], b"\x01")

        # Step 2: CEE8 -> J1 manually with fresh controller session (representing separate CLI invocation)
        controller2 = W300ServiceController(mock_camera=self.camera)
        controller2.switch_to_senser_mode()
        controller2.authenticate_senser()
        controller2.unlock_service_board()

        p_dest = self.protocol.build_write_prop(Cee8Payload.PROP_DESTINATION, b"J1\x00\x00")
        controller2.transfer_bulk(p_dest)
        p_lang = self.protocol.build_write_prop(Cee8Payload.PROP_LANG_BASE, Cee8Payload.LANG_MASK_J1)
        controller2.transfer_bulk(p_lang)
        p_vid = self.protocol.build_write_prop(Cee8Payload.PROP_VIDEO_OUT, bytes([0x00]))
        controller2.transfer_bulk(p_vid)
        controller2.commit_flash()
        controller2.reset_device()

        # Read back via fresh session
        controller3 = W300ServiceController(mock_camera=self.camera)
        info = controller3.read_destination_info()
        self.assertEqual(info['destination'], "J1")
        self.assertEqual(info['video'], "NTSC")
        self.assertEqual(info['active_languages'], ["Japanese (ja)"])

    def test_post_reboot_controller_state_desync_finding(self):
        """EMPIRICAL FINDING: reset_device() reboots camera but leaves controller.authenticated True.

        When reset_device() reboots the device into MASS_STORAGE mode, the camera resets
        its auth_state to 0. However, W300ServiceController does not reset its internal
        self.authenticated flag to False. Consequently, subsequent commands on the same
        controller instance skip switch_to_senser_mode() and fail with ConnectionError.
        """
        controller = W300ServiceController(mock_camera=self.camera)
        controller.run_full_cycle()
        self.assertEqual(self.camera.mode, "MASS_STORAGE")
        self.assertEqual(self.camera.auth_state, 0)
        # Bug demonstration: controller still believes it is authenticated
        self.assertTrue(controller.authenticated)

        # Attempting read_destination_info() fails because controller thinks it is authenticated
        with self.assertRaises(ConnectionError) as ctx:
            controller.read_destination_info()
        self.assertIn("Cannot bulk write: camera not in Senser mode", str(ctx.exception))


# ============================================================================
# Category D: Safety Guardrail Strict Exit Code 2 Enforcement
# ============================================================================

class TestCategoryDSafetyGuardrailExit2(BaseAdversarialTestCase):
    """Verifies that unauthorized destination writes strictly trigger exit code 2."""

    def test_cli_write_cee8_without_unlock_triggers_exit_code_2(self):
        """Running 'write-cee8' CLI directly without prior unlock must exit with code 2."""
        cmd = [sys.executable, str(TOOL_SCRIPT_PATH), "--mock", "write-cee8"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, f"Expected returncode 2, got {result.returncode}. Stderr: {result.stderr}")
        self.assertIn("[ERROR: ACCESS_DENIED]", result.stderr)
        self.assertIn("Service board protection locked", result.stderr)

    def test_controller_write_cee8_without_unlock_raises_permission_error(self):
        """Controller write_cee8_destination() raises PermissionError on locked camera."""
        camera = W300MockUsbCamera(destination="J1")
        controller = W300ServiceController(mock_camera=camera)
        controller.switch_to_senser_mode()
        controller.authenticate_senser()
        self.assertTrue(camera.id1_locked)

        with self.assertRaises(PermissionError) as ctx:
            controller.write_cee8_destination()
        self.assertIn("Service board protection locked", str(ctx.exception))

    def test_main_function_catches_permission_error_and_returns_2(self):
        """Direct call to main() when write is rejected returns integer 2."""
        orig_argv = sys.argv
        try:
            sys.argv = ["w300_service_tool.py", "--mock", "write-cee8"]
            exit_code = main()
            self.assertEqual(exit_code, 2)
        finally:
            sys.argv = orig_argv

    def test_guardrail_protects_all_three_critical_nvram_properties(self):
        """Camera simulator rejects PROP_DESTINATION, PROP_LANG_BASE, and PROP_VIDEO_OUT when locked."""
        camera = W300MockUsbCamera(destination="J1")
        camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        # Authenticate
        camera.bulk_write(SenserWireProtocol.build_auth_packet(cmd=1))
        camera.bulk_read()
        digest = sha1_faulty(camera.auth_challenge[:4])
        camera.bulk_write(SenserWireProtocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest))
        camera.bulk_read()
        camera.bulk_write(SenserWireProtocol.build_auth_packet(cmd=5))
        camera.bulk_read()

        prot = SenserWireProtocol()
        targets = [
            (Cee8Payload.PROP_DESTINATION, b"CEE8"),
            (Cee8Payload.PROP_LANG_BASE, Cee8Payload.LANG_MASK_CEE8),
            (Cee8Payload.PROP_VIDEO_OUT, bytes([0x01])),
        ]

        for prop_id, prop_val in targets:
            with self.subTest(prop_id=hex(prop_id)):
                pkt = prot.build_write_prop(prop_id, prop_val)
                camera.bulk_write(pkt)
                resp = prot.parse_packet(camera.bulk_read())
                self.assertEqual(resp['response'], 5)

    def test_cli_live_usb_failure_returns_exit_code_1(self):
        """Running live USB command without --mock returns exit code 1."""
        cmd = [sys.executable, str(TOOL_SCRIPT_PATH), "detect"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("[ERROR: PROTOCOL]", result.stderr)

    def test_cli_detect_mock_returns_exit_code_0(self):
        """Running --mock detect returns exit code 0."""
        cmd = [sys.executable, str(TOOL_SCRIPT_PATH), "--mock", "detect"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Device detected", result.stdout)

    def test_cli_dry_run_write_cee8_exits_0(self):
        """Running --mock write-cee8 --dry-run returns exit code 0 without triggering guardrail."""
        cmd = [sys.executable, str(TOOL_SCRIPT_PATH), "--mock", "write-cee8", "--dry-run"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Non-destructive dry-run active", result.stdout)


# ============================================================================
# Category E: Fail-Closed --dry-run Non-Volatile Memory Invariance
# ============================================================================

class TestCategoryEDryRunInvariance(BaseAdversarialTestCase):
    """Stress-tests --dry-run guarantee that non-volatile memory is NEVER modified."""

    def test_dry_run_full_cycle_zero_modifications(self):
        """Executing full-cycle under --dry-run must leave flash and staging RAM 100% pristine."""
        camera = W300MockUsbCamera(destination="J1", serial=1458291)
        controller = W300ServiceController(mock_camera=camera, dry_run=True)

        res = controller.run_full_cycle()
        self.assertTrue(res)

        # Invariant checks:
        self.assertEqual(camera.flash_commit_count, 0)
        self.assertEqual(camera.flash_store[Cee8Payload.PROP_DESTINATION], b"J1\x00\x00")
        self.assertEqual(camera.flash_store[Cee8Payload.PROP_VIDEO_OUT], b"\x00")
        self.assertEqual(camera.flash_store[Cee8Payload.PROP_LANG_BASE], Cee8Payload.LANG_MASK_J1)
        self.assertEqual(camera.staging_ram[Cee8Payload.PROP_DESTINATION], b"J1\x00\x00")
        self.assertTrue(camera.id1_locked)
        self.assertEqual(camera.reboot_count, 0)

    def test_dry_run_cli_full_cycle_process(self):
        """CLI execution of full-cycle --dry-run exits 0 without errors."""
        cmd = [sys.executable, str(TOOL_SCRIPT_PATH), "--mock", "full-cycle", "--dry-run"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("DRY-RUN COMPLETE", result.stdout)
        self.assertIn("Zero Mutating Packets Sent", result.stdout)

    def test_dry_run_individual_commands_zero_packet_mutation(self):
        """Individual dry-run invocations of unlock, write-cee8, commit, and reset."""
        camera = W300MockUsbCamera(destination="J1")
        controller = W300ServiceController(mock_camera=camera, dry_run=True)

        # Unlock
        controller.unlock_service_board()
        self.assertTrue(camera.id1_locked)  # Not unlocked on camera

        # Write
        controller.write_cee8_destination()
        self.assertEqual(camera.staging_ram[Cee8Payload.PROP_DESTINATION], b"J1\x00\x00")

        # Commit
        controller.commit_flash()
        self.assertEqual(camera.flash_commit_count, 0)

        # Reset
        controller.reset_device()
        self.assertEqual(camera.reboot_count, 0)

    def test_dry_run_preserves_memory_even_if_error_injected(self):
        """If an exception occurs mid-run during dry-run, NVM remains unaltered."""
        camera = W300MockUsbCamera(destination="J1")
        controller = W300ServiceController(mock_camera=camera, dry_run=True)

        # Sabotage transfer_bulk by setting mock_camera to None
        controller.mock_camera = None
        with self.assertRaises(ConnectionError):
            controller.detect_device()

        # Invariant: original camera instance is still untouched
        self.assertEqual(camera.flash_commit_count, 0)
        self.assertEqual(camera.flash_store[Cee8Payload.PROP_DESTINATION], b"J1\x00\x00")

    def test_dry_run_repeated_100_times_zero_mutation(self):
        """100 sequential full-cycle dry runs guarantee 0 commits and bit-for-bit identical flash."""
        camera = W300MockUsbCamera(destination="J1")
        controller = W300ServiceController(mock_camera=camera, dry_run=True)
        flash_before = dict(camera.flash_store)

        for _ in range(100):
            controller.run_full_cycle()

        self.assertEqual(camera.flash_commit_count, 0)
        self.assertEqual(camera.flash_store, flash_before)


# ============================================================================
# Category F: Cryptographic Fault Invariants & EVR Checksums
# ============================================================================

class TestCategoryFCryptographicAndEvrInvariants(BaseAdversarialTestCase):
    """Stress-tests faulty SHA-1 length truncation and EVR checksum math."""

    def test_faulty_sha1_divergence_from_standard_sha1(self):
        """Verifies that sha1_faulty diverges from standard SHA-1 for payloads >= 32 bytes."""
        msg_32 = b"A" * 32
        std_hash = hashlib.sha1(msg_32).digest()
        faulty_hash = sha1_faulty(msg_32)
        # sha1_faulty truncates length to 32 & 0x1F = 0, so hashes MUST NOT match!
        self.assertNotEqual(std_hash, faulty_hash)

        # For message length 31 bytes, 31 & 0x1F = 31, hashes MUST match!
        msg_31 = b"B" * 31
        std_hash_31 = hashlib.sha1(msg_31).digest()
        faulty_hash_31 = sha1_faulty(msg_31)
        self.assertEqual(std_hash_31, faulty_hash_31)

    def test_evr_checksum_algebraic_identity(self):
        """Formula: (sum(data) + calculate_evr_checksum(data)) & 0xFF == 0."""
        test_vectors = [
            b"",
            b"\x00",
            b"\xFF",
            b"\x01\x02\x03\x04\x05",
            bytes(range(256)),
            b"\x55" * 1024,
            Cee8Payload.LANG_MASK_CEE8,
            Cee8Payload.LANG_MASK_J1,
        ]
        for vec in test_vectors:
            with self.subTest(vec_len=len(vec)):
                chk = Cee8Payload.calculate_evr_checksum(vec)
                full_page = vec + bytes([chk])
                self.assertTrue(Cee8Payload.verify_evr_page(full_page))
                self.assertEqual((sum(vec) + chk) & 0xFF, 0)

    def test_evr_checksum_exhaustive_fuzzing(self):
        """200 pseudorandom payloads with random sizes must all satisfy checksum property."""
        rng = random.Random(0xCEE8)
        for i in range(200):
            length = rng.randint(0, 1024)
            data = bytes([rng.randint(0, 255) for _ in range(length)])
            chk = Cee8Payload.calculate_evr_checksum(data)
            full_page = data + bytes([chk])
            self.assertTrue(Cee8Payload.verify_evr_page(full_page))

    def test_left_rotate_invariants(self):
        """Edge cases for 32-bit left bitwise rotation."""
        self.assertEqual(_left_rotate(0x12345678, 0), 0x12345678)
        self.assertEqual(_left_rotate(0x80000000, 1), 0x00000001)
        self.assertEqual(_left_rotate(0x00000001, 31), 0x80000000)
        self.assertEqual(_left_rotate(0xFFFFFFFF, 16), 0xFFFFFFFF)

    def test_cee8_payload_language_count(self):
        """Table 6-1-2 CEE8 mask must activate exactly 19 languages (including Polish and English)."""
        enabled = Cee8Payload.get_enabled_languages(Cee8Payload.LANG_MASK_CEE8)
        self.assertEqual(len(enabled), 19)
        self.assertIn("English (en)", enabled)
        self.assertIn("Polish (pl)", enabled)
        self.assertNotIn("Japanese (ja)", enabled)

    def test_j1_payload_language_count(self):
        """Table 6-1-2 J1 mask must activate exclusively 1 language (Japanese)."""
        enabled = Cee8Payload.get_enabled_languages(Cee8Payload.LANG_MASK_J1)
        self.assertEqual(len(enabled), 1)
        self.assertEqual(enabled[0], "Japanese (ja)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
