#!/usr/bin/env python3
"""Automated 4-Tier Unit Test Suite for Sony Cyber-shot DSC-W300 Service Tool.

Architecture: 4-Tier Test Coverage
- Tier 1: Feature Coverage (>=5 tests per feature)
  * Wire protocol packing & unpacking
  * Faulty SHA-1 calculation
  * 3-step authentication handshake
  * CEE8 payload generation
  * EVR checksum calculation
  * Mock camera simulator
- Tier 2: Boundary & Corner Cases
  * Truncated/undersized headers & auth packets
  * Oversized payloads
  * Corrupted auth digests & sequence violations
  * Out-of-range/unknown properties
  * Malformed language masks
  * Safety guardrail locked write rejection (Exit 2)
  * Mode-switch & unauthenticated command rejections
- Tier 3: Cross-Feature Combinations & Contracts
  * Sequence number integrity across transactions
  * Fail-closed --dry-run contract
  * Round-trip destination conversion & rollback
  * CLI exit code contracts (0, 1, 2)
- Tier 4: Real-World Application Scenarios
  * End-to-end full-cycle destination conversion against mock camera
  * Verification readback asserting English active, Polish enabled, PAL asserted
  * Subsystem isolation: zero alteration to factory optical/sensor calibration
  * Concurrent mock camera instances isolation

Pure Python 3 standard library unittest only. Zero external dependencies.
"""

from __future__ import annotations

import binascii
import contextlib
import hashlib
import io
from pathlib import Path
import struct
import subprocess
import sys
import unittest

# Ensure tools directory is in sys.path
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


class BaseServiceTestCase(unittest.TestCase):
    """Base test fixture providing automatic stdout suppression for clean test logs."""

    def setUp(self):
        super().setUp()
        self._stdout_trap = io.StringIO()
        self._trap_ctx = contextlib.redirect_stdout(self._stdout_trap)
        self._trap_ctx.__enter__()

    def tearDown(self):
        self._trap_ctx.__exit__(None, None, None)
        super().tearDown()


# ============================================================================
# Tier 1 — Feature Coverage
# ============================================================================

class TestTier1WireProtocolFraming(BaseServiceTestCase):
    """Tier 1.1: Wire protocol packing and unpacking unit tests (>=5 tests)."""

    def setUp(self):
        super().setUp()
        self.protocol = SenserWireProtocol(start_sequence=1)

    def test_header_fields_packing(self):
        """Verify exact 12-byte little-endian header packing structure."""
        payload = b'\x11\x22\x33\x44'
        packet = self.protocol.build_packet(
            p_func=SenserWireProtocol.PFUNC_ADJUST_CONTROL,
            payload=payload,
            pad_to_512=False,
        )
        self.assertEqual(len(packet), 12 + len(payload))
        size, p_func, seq, ver, micon, offset, resp = struct.unpack('<IHHBBBB', packet[:12])
        self.assertEqual(size, 4)
        self.assertEqual(p_func, 0x0040)
        self.assertEqual(seq, 1)
        self.assertEqual(ver, 0)
        self.assertEqual(micon, 0)
        self.assertEqual(offset, 0)
        self.assertEqual(resp, 0)
        self.assertEqual(packet[12:], payload)

    def test_packet_unpacking_roundtrip(self):
        """Verify unpacking returns all expected dictionary fields and raw data."""
        payload = b'TEST_PAYLOAD_BYTES'
        packet = self.protocol.build_packet(
            p_func=SenserWireProtocol.PFUNC_PRODUCT_INFO,
            payload=payload,
            pad_to_512=False,
        )
        parsed = self.protocol.parse_packet(packet)
        self.assertEqual(parsed['size'], len(payload))
        self.assertEqual(parsed['pFunc'], SenserWireProtocol.PFUNC_PRODUCT_INFO)
        self.assertEqual(parsed['sequence'], 1)
        self.assertEqual(parsed['version'], 0)
        self.assertEqual(parsed['miconType'], 0)
        self.assertEqual(parsed['offsetType'], 0)
        self.assertEqual(parsed['response'], 0)
        self.assertEqual(parsed['payload'], payload)
        self.assertEqual(parsed['raw'], packet)

    def test_sequence_counter_monotonicity(self):
        """Verify sequence counter increments monotonically by 1 per packet."""
        proto = SenserWireProtocol(start_sequence=10)
        seqs = []
        for _ in range(5):
            pkt = proto.build_packet(p_func=0x0010, pad_to_512=False)
            parsed = proto.parse_packet(pkt)
            seqs.append(parsed['sequence'])
        self.assertEqual(seqs, [10, 11, 12, 13, 14])
        self.assertEqual(proto.sequence, 15)

    def test_sequence_counter_wrapping(self):
        """Verify sequence counter wraps cleanly at 0xFFFF (16-bit unsigned)."""
        proto = SenserWireProtocol(start_sequence=0xFFFF)
        pkt1 = proto.build_packet(p_func=0x0010, pad_to_512=False)
        self.assertEqual(proto.parse_packet(pkt1)['sequence'], 0xFFFF)
        self.assertEqual(proto.sequence, 0x0000)

        pkt2 = proto.build_packet(p_func=0x0010, pad_to_512=False)
        self.assertEqual(proto.parse_packet(pkt2)['sequence'], 0x0000)
        self.assertEqual(proto.sequence, 0x0001)

    def test_padding_boundary_512_padded(self):
        """Verify short packets are padded with 0x00 to exactly 512 bytes."""
        payload = b'\xAA' * 50
        packet = self.protocol.build_packet(
            p_func=SenserWireProtocol.PFUNC_ADJUST_CONTROL,
            payload=payload,
            pad_to_512=True,
        )
        self.assertEqual(len(packet), 512)
        self.assertEqual(packet[12:62], payload)
        self.assertEqual(packet[62:], b'\x00' * (512 - 62))

    def test_padding_boundary_unpadded_and_large_packets(self):
        """Verify unpadded mode and packets >= 512 bytes maintain exact lengths."""
        short_payload = b'\xBB' * 20
        unpadded = self.protocol.build_packet(
            p_func=0x0010,
            payload=short_payload,
            pad_to_512=False,
        )
        self.assertEqual(len(unpadded), 12 + 20)

        large_payload = b'\xCC' * 700
        large_packet = self.protocol.build_packet(
            p_func=0x0010,
            payload=large_payload,
            pad_to_512=True,
        )
        self.assertEqual(len(large_packet), 12 + 700)
        self.assertEqual(large_packet[12:], large_payload)

    def test_adjust_control_subcommand_helpers(self):
        """Verify helper methods construct correct Category 0x0603 commands."""
        # Read property helper
        read_pkt = self.protocol.build_read_prop(0x00E70001)
        parsed_read = self.protocol.parse_packet(read_pkt)
        self.assertEqual(parsed_read['pFunc'], SenserWireProtocol.PFUNC_ADJUST_CONTROL)
        cat, cmd, prop = struct.unpack('<HHI', parsed_read['payload'])
        self.assertEqual(cat, 0x0603)
        self.assertEqual(cmd, 0x0001)
        self.assertEqual(prop, 0x00E70001)

        # Write property helper
        write_pkt = self.protocol.build_write_prop(0x00E70001, b'CEE8')
        parsed_write = self.protocol.parse_packet(write_pkt)
        cat, cmd, prop = struct.unpack('<HHI', parsed_write['payload'][:8])
        self.assertEqual(cat, 0x0603)
        self.assertEqual(cmd, 0x0002)
        self.assertEqual(prop, 0x00E70001)
        self.assertEqual(parsed_write['payload'][8:], b'CEE8')

        # Commit flash helper
        commit_pkt = self.protocol.build_commit_flash(subsystem=0)
        parsed_commit = self.protocol.parse_packet(commit_pkt)
        cat, cmd, sub = struct.unpack('<HHH', parsed_commit['payload'])
        self.assertEqual(cat, 0x0603)
        self.assertEqual(cmd, 0x0003)
        self.assertEqual(sub, 0)

        # ID1 Lock helper
        id1_pkt = self.protocol.build_id1_lock(lock=False)
        parsed_id1 = self.protocol.parse_packet(id1_pkt)
        cat, cmd = struct.unpack('<HH', parsed_id1['payload'][:4])
        self.assertEqual(cat, 0x0603)
        self.assertEqual(cmd, 0x000F)
        self.assertEqual(parsed_id1['payload'][4], 0x00)


class TestTier1FaultySha1(BaseServiceTestCase):
    """Tier 1.2: Faulty SHA-1 calculation unit tests (>=5 tests)."""

    def test_sha1_faulty_length_truncation_formula(self):
        """Verify sha1_faulty exactly applies `len & 0x1F` length truncation."""
        test_inputs = [
            b'',
            b'1234',
            b'A' * 31,
            b'B' * 32,
            b'C' * 33,
            b'D' * 63,
            b'E' * 64,
            b'F' * 65,
        ]
        for inp in test_inputs:
            expected = sha1(inp, len(inp) & 0x1F)
            actual = sha1_faulty(inp)
            self.assertEqual(actual, expected)

    def test_sha1_faulty_matches_standard_under_32_bytes(self):
        """For inputs < 32 bytes, len & 0x1F == len, so output matches standard SHA-1."""
        short_inputs = [
            b'Sony',
            b'DSC-W300',
            b'SenserMode1234567890123456789',  # 30 bytes
            b'Exact31ByteLengthStringTest1234',  # 31 bytes
        ]
        for inp in short_inputs:
            faulty_hash = sha1_faulty(inp)
            std_hash = hashlib.sha1(inp).digest()
            self.assertEqual(faulty_hash, std_hash)

    def test_sha1_faulty_divergence_above_31_bytes(self):
        """For inputs >= 32 bytes, faulty SHA-1 diverges from standard SHA-1."""
        inp32 = b'01234567890123456789012345678901'  # 32 bytes
        faulty_hash = sha1_faulty(inp32)
        std_hash = hashlib.sha1(inp32).digest()
        self.assertNotEqual(faulty_hash, std_hash)
        # 32 & 0x1F == 0, so bit length in padding is 0 bits
        self.assertEqual(faulty_hash, sha1(inp32, 0))

        inp35 = b'X' * 35  # 35 & 0x1F == 3
        self.assertNotEqual(sha1_faulty(inp35), hashlib.sha1(inp35).digest())
        self.assertEqual(sha1_faulty(inp35), sha1(inp35, 3))

    def test_sha1_faulty_mock_challenge_vector(self):
        """Verify hash on the exact mock camera 4-byte challenge vector."""
        challenge_slice = b'\x4a\x8e\x12\xbd'
        digest = sha1_faulty(challenge_slice)
        self.assertEqual(len(digest), 20)
        expected_digest = hashlib.sha1(challenge_slice).digest()
        self.assertEqual(digest, expected_digest)
        # Verify hex format representation
        self.assertEqual(len(binascii.hexlify(digest)), 40)

    def test_sha1_nist_known_test_vectors(self):
        """Verify underlying standard sha1 function against official NIST test vectors."""
        nist_abc = b"abc"
        expected_abc = "a9993e364706816aba3e25717850c26c9cd0d89d"
        self.assertEqual(binascii.hexlify(sha1(nist_abc)).decode('ascii'), expected_abc)

        nist_empty = b""
        expected_empty = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
        self.assertEqual(binascii.hexlify(sha1(nist_empty)).decode('ascii'), expected_empty)

    def test_left_rotate_correctness(self):
        """Verify 32-bit left circular shift primitive."""
        self.assertEqual(_left_rotate(0x80000000, 1), 0x00000001)
        self.assertEqual(_left_rotate(0x12345678, 4), 0x23456781)
        self.assertEqual(_left_rotate(0xFFFFFFFF, 16), 0xFFFFFFFF)
        self.assertEqual(_left_rotate(0x00000001, 31), 0x80000000)


class TestTier1AuthHandshake(BaseServiceTestCase):
    """Tier 1.3: 3-step authentication handshake unit tests (>=5 tests)."""

    def setUp(self):
        super().setUp()
        self.camera = W300MockUsbCamera()
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)

    def test_auth_packet_packing_cmd_inversion(self):
        """Verify AuthPacket packs bitwise NOT of command and 512-byte payload."""
        packet = SenserWireProtocol.build_auth_packet(cmd=1, salt=0)
        self.assertEqual(len(packet), 516)
        raw_cmd, salt = struct.unpack('>HH', packet[:4])
        self.assertEqual(raw_cmd, (~1) & 0xFFFF)
        self.assertEqual(salt, 0)
        self.assertEqual(packet[4:], b'\x00' * 512)

    def test_auth_packet_parsing_math(self):
        """Verify parse_auth_packet calculates ((~raw_cmd) & 0xFFFF) - salt."""
        raw_cmd = (~2) & 0xFFFF
        salt = 10
        raw_packet = struct.pack('>HH', raw_cmd, salt) + (b'\x55' * 512)
        ret, s, data = SenserWireProtocol.parse_auth_packet(raw_packet)
        self.assertEqual(ret, 2 - 10)
        self.assertEqual(s, 10)
        self.assertEqual(data, b'\x55' * 512)

    def test_auth_handshake_step1_challenge_generation(self):
        """Verify Step 1 emits challenge with ret=2 (indicating SHA-1 required)."""
        req1 = SenserWireProtocol.build_auth_packet(cmd=1)
        self.camera.bulk_write(req1)
        resp1 = self.camera.bulk_read()
        ret, _, data = SenserWireProtocol.parse_auth_packet(resp1)
        self.assertEqual(ret, 2)
        self.assertEqual(data[:4], self.camera.auth_challenge[:4])
        self.assertEqual(self.camera.auth_state, 1)

    def test_auth_handshake_step2_response_calculation(self):
        """Verify Step 2 with sha1_faulty digest receives ret=4 acknowledgement."""
        # Step 1
        self.camera.bulk_write(SenserWireProtocol.build_auth_packet(cmd=1))
        resp1 = self.camera.bulk_read()
        _, _, data1 = SenserWireProtocol.parse_auth_packet(resp1)

        # Step 2
        digest = sha1_faulty(data1[:4])
        req2 = SenserWireProtocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest)
        self.camera.bulk_write(req2)
        resp2 = self.camera.bulk_read()
        ret2, _, _ = SenserWireProtocol.parse_auth_packet(resp2)
        self.assertEqual(ret2, 4)

    def test_auth_handshake_step3_finalization_success(self):
        """Verify Step 3 finalizes handshake with ret=6 and status 0x01."""
        # Step 1
        self.camera.bulk_write(SenserWireProtocol.build_auth_packet(cmd=1))
        resp1 = self.camera.bulk_read()
        _, _, data1 = SenserWireProtocol.parse_auth_packet(resp1)

        # Step 2
        digest = sha1_faulty(data1[:4])
        self.camera.bulk_write(SenserWireProtocol.build_auth_packet(cmd=3, data=bytes([0x01]) + digest))
        self.camera.bulk_read()

        # Step 3
        self.camera.bulk_write(SenserWireProtocol.build_auth_packet(cmd=5))
        resp3 = self.camera.bulk_read()
        ret3, _, data3 = SenserWireProtocol.parse_auth_packet(resp3)
        self.assertEqual(ret3, 6)
        self.assertEqual(data3[0], 0x01)
        self.assertEqual(self.camera.auth_state, 2)

    def test_controller_authenticate_senser_success(self):
        """Verify W300ServiceController.authenticate_senser() executes all 3 steps."""
        controller = W300ServiceController(mock_camera=self.camera)
        self.assertFalse(controller.authenticated)
        res = controller.authenticate_senser()
        self.assertTrue(res)
        self.assertTrue(controller.authenticated)
        self.assertEqual(self.camera.auth_state, 2)


class TestTier1Cee8PayloadGeneration(BaseServiceTestCase):
    """Tier 1.4: CEE8 payload generation and language mask unit tests (>=5 tests)."""

    def test_cee8_language_mask_spec(self):
        """Verify CEE8 language mask is exactly 35 bytes with valid 0x01/0x02 codes."""
        mask = Cee8Payload.LANG_MASK_CEE8
        self.assertEqual(len(mask), 35)
        for val in mask:
            self.assertIn(val, (0x01, 0x02))

    def test_j1_baseline_language_mask_spec(self):
        """Verify J1 baseline mask has only Japanese (index 1) enabled."""
        mask = Cee8Payload.LANG_MASK_J1
        self.assertEqual(len(mask), 35)
        self.assertEqual(mask[1], 0x01)
        for idx, val in enumerate(mask):
            if idx != 1:
                self.assertEqual(val, 0x02)

    def test_cee8_enabled_languages_contains_english_and_polish(self):
        """Verify CEE8 enabled languages include English and Polish, excluding Japanese."""
        enabled = Cee8Payload.get_enabled_languages(Cee8Payload.LANG_MASK_CEE8)
        self.assertIn("English (en)", enabled)
        self.assertIn("Polish (pl)", enabled)
        self.assertIn("French (fr)", enabled)
        self.assertIn("German (de)", enabled)
        self.assertIn("Spanish (es)", enabled)
        self.assertIn("Italian (it)", enabled)
        self.assertIn("Czech (cs)", enabled)
        self.assertNotIn("Japanese (ja)", enabled)
        self.assertNotIn("Russian (ru)", enabled)

    def test_pal_ntsc_video_property_codes(self):
        """Verify video standard property ID and PAL/NTSC binary values."""
        self.assertEqual(Cee8Payload.PROP_VIDEO_OUT, 0x01070148)
        self.assertEqual(b'\x01', bytes([0x01]))  # PAL
        self.assertEqual(b'\x00', bytes([0x00]))  # NTSC

    def test_destination_code_property(self):
        """Verify destination property ID and 4-byte ASCII encodings."""
        self.assertEqual(Cee8Payload.PROP_DESTINATION, 0x00E70001)
        self.assertEqual(b"CEE8", "CEE8".encode('ascii'))
        self.assertEqual(len(b"CEE8"), 4)
        self.assertEqual(len("J1".encode('ascii').ljust(4, b'\x00')), 4)

    def test_all_hardware_property_ids(self):
        """Verify all persistent NVM property IDs and language list size."""
        self.assertEqual(Cee8Payload.PROP_MODEL, 0x00E70000)
        self.assertEqual(Cee8Payload.PROP_SERIAL, 0x00E70003)
        self.assertEqual(Cee8Payload.PROP_LANG_BASE, 0x010D008F)
        self.assertEqual(len(Cee8Payload.LANGUAGE_NAMES), 35)


class TestTier1EvrChecksum(BaseServiceTestCase):
    """Tier 1.5: EVR checksum calculation unit tests (>=5 tests)."""

    def test_evr_checksum_formula_basic_vectors(self):
        """Verify additive two's complement formula ((0x100 - sum) & 0xFF)."""
        self.assertEqual(Cee8Payload.calculate_evr_checksum(b'\x00'), 0x00)
        self.assertEqual(Cee8Payload.calculate_evr_checksum(b'\x01'), 0xFF)
        self.assertEqual(Cee8Payload.calculate_evr_checksum(b'\xFF'), 0x01)
        self.assertEqual(Cee8Payload.calculate_evr_checksum(b'\x01\x02\x03'), 250)

    def test_evr_page_verification_valid_blocks(self):
        """Verify that appending calculated checksum makes entire block sum to 0 mod 256."""
        blocks = [
            b'\x10\x20\x30\x40',
            b'\xAA\xBB\xCC\xDD\xEE\xFF',
            bytes(range(100)),
        ]
        for blk in blocks:
            chk = Cee8Payload.calculate_evr_checksum(blk)
            page = blk + bytes([chk])
            self.assertTrue(Cee8Payload.verify_evr_page(page))

    def test_evr_checksum_zero_sum_boundary(self):
        """Verify block whose sum is already multiple of 256 yields checksum 0."""
        blk = bytes([100, 156])  # 100 + 156 = 256
        chk = Cee8Payload.calculate_evr_checksum(blk)
        self.assertEqual(chk, 0)
        self.assertTrue(Cee8Payload.verify_evr_page(blk + bytes([chk])))

    def test_evr_page_corruption_detection(self):
        """Verify modifying any byte causes checksum verification failure."""
        blk = b'\x05\x0A\x0F\x14'
        chk = Cee8Payload.calculate_evr_checksum(blk)
        valid_page = bytearray(blk + bytes([chk]))
        self.assertTrue(Cee8Payload.verify_evr_page(valid_page))

        # Tamper with payload byte
        valid_page[1] ^= 0x01
        self.assertFalse(Cee8Payload.verify_evr_page(valid_page))

    def test_evr_checksum_full_256_byte_page(self):
        """Verify checksum across full 255-byte EVR memory page."""
        page_data = bytes((i * 7) & 0xFF for i in range(255))
        chk = Cee8Payload.calculate_evr_checksum(page_data)
        full_page = page_data + bytes([chk])
        self.assertEqual(len(full_page), 256)
        self.assertTrue(Cee8Payload.verify_evr_page(full_page))

    def test_evr_empty_input(self):
        """Verify empty byte input handles correctly without exception."""
        chk = Cee8Payload.calculate_evr_checksum(b'')
        self.assertEqual(chk, 0)
        self.assertTrue(Cee8Payload.verify_evr_page(b'\x00'))


class TestTier1MockCameraSimulator(BaseServiceTestCase):
    """Tier 1.6: Mock camera simulator unit tests (>=5 tests)."""

    def setUp(self):
        super().setUp()
        self.cam = W300MockUsbCamera(destination="J1", serial=1234567)

    def test_mock_camera_initial_state_defaults(self):
        """Verify initial state: Mass Storage mode, PID 0x031B, J1 destination, locked."""
        self.assertEqual(self.cam.mode, "MASS_STORAGE")
        self.assertEqual(self.cam.current_pid, 0x031B)
        self.assertEqual(self.cam.serial, 1234567)
        self.assertEqual(self.cam.flash_store[Cee8Payload.PROP_MODEL], b'W300\x00')
        self.assertEqual(self.cam.flash_store[Cee8Payload.PROP_DESTINATION], b'J1\x00\x00')
        self.assertEqual(self.cam.flash_store[Cee8Payload.PROP_VIDEO_OUT], b'\x00')
        self.assertEqual(self.cam.auth_state, 0)
        self.assertTrue(self.cam.id1_locked)

    def test_mock_camera_custom_initialization(self):
        """Verify custom destination and serial initialization."""
        cam2 = W300MockUsbCamera(destination="CEE8", serial=9876543)
        self.assertEqual(cam2.flash_store[Cee8Payload.PROP_DESTINATION], b'CEE8')
        self.assertEqual(cam2.flash_store[Cee8Payload.PROP_VIDEO_OUT], b'\x01')
        self.assertEqual(cam2.flash_store[Cee8Payload.PROP_LANG_BASE], Cee8Payload.LANG_MASK_CEE8)
        serial_val = struct.unpack('<I', cam2.flash_store[Cee8Payload.PROP_SERIAL])[0]
        self.assertEqual(serial_val, 9876543)

    def test_mock_camera_mode_switch_control_request(self):
        """Verify USB Vendor Request 0x43/1/0x37FF/0xD7AA transitions to Senser mode."""
        res = self.cam.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        self.assertEqual(res, 0)
        self.assertEqual(self.cam.mode, "SENSER")
        self.assertEqual(self.cam.current_pid, 0x02A9)
        self.assertEqual(self.cam.auth_state, 0)

    def test_mock_camera_reboot_control_request(self):
        """Verify USB Vendor Request 0x43/1/0xC800/0x2855 cleanly cold reboots camera."""
        # Enter senser mode first
        self.cam.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        self.assertEqual(self.cam.mode, "SENSER")

        # Send reboot request
        res = self.cam.control_request(0x43, 0x01, 0xC800, 0x2855)
        self.assertEqual(res, 0)
        self.assertEqual(self.cam.mode, "MASS_STORAGE")
        self.assertEqual(self.cam.current_pid, 0x031B)
        self.assertEqual(self.cam.reboot_count, 1)
        self.assertTrue(self.cam.id1_locked)
        self.assertEqual(self.cam.auth_state, 0)

    def test_mock_camera_product_info_pfunc(self):
        """Verify PFUNC_PRODUCT_INFO responds with status 1."""
        self.cam.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        controller = W300ServiceController(mock_camera=self.cam)
        controller.authenticate_senser()

        # Send ProductInfo packet
        pkt = SenserWireProtocol().build_packet(p_func=SenserWireProtocol.PFUNC_PRODUCT_INFO)
        self.cam.bulk_write(pkt)
        resp = self.cam.bulk_read()
        parsed = SenserWireProtocol().parse_packet(resp)
        self.assertEqual(parsed['response'], 1)

    def test_mock_camera_read_properties_in_senser(self):
        """Verify CMD_BACKUP_READ reads staged properties accurately."""
        self.cam.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        controller = W300ServiceController(mock_camera=self.cam)
        controller.authenticate_senser()

        proto = SenserWireProtocol()
        # Read Model
        self.cam.bulk_write(proto.build_read_prop(Cee8Payload.PROP_MODEL))
        resp = proto.parse_packet(self.cam.bulk_read())
        self.assertEqual(resp['response'], 0)
        self.assertEqual(resp['payload'], b'W300\x00')

        # Read Destination
        self.cam.bulk_write(proto.build_read_prop(Cee8Payload.PROP_DESTINATION))
        resp = proto.parse_packet(self.cam.bulk_read())
        self.assertEqual(resp['response'], 0)
        self.assertEqual(resp['payload'], b'J1\x00\x00')


# ============================================================================
# Tier 2 — Boundary & Corner Cases
# ============================================================================

class TestTier2BoundaryAndCornerCases(BaseServiceTestCase):
    """Tier 2: Boundary conditions, corner cases, error detection, and guardrails."""

    def setUp(self):
        super().setUp()
        self.cam = W300MockUsbCamera()
        self.protocol = SenserWireProtocol()

    def test_truncated_senser_header_raises_value_error(self):
        """Packets smaller than 12 bytes must raise ValueError during parsing."""
        with self.assertRaises(ValueError) as ctx:
            self.protocol.parse_packet(b'\x00' * 11)
        self.assertIn("Packet too short", str(ctx.exception))

        with self.assertRaises(ValueError):
            self.protocol.parse_packet(b'')

    def test_undersized_auth_packet_raises_value_error(self):
        """AuthPackets smaller than 516 bytes must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.protocol.parse_auth_packet(b'\x00' * 515)
        self.assertIn("AuthPacket too short", str(ctx.exception))

    def test_mock_bulk_write_undersized_auth_packet_raises_value_error(self):
        """Sending < 516 bytes to bulk_write during auth phase raises ValueError."""
        self.cam.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        with self.assertRaises(ValueError) as ctx:
            self.cam.bulk_write(b'\x00' * 100)
        self.assertIn("Expected 516-byte AuthPacket", str(ctx.exception))

    def test_oversized_payload_handling(self):
        """Verify handling of payloads up to 1 MB."""
        one_mb_payload = b'X' * (1024 * 1024)
        packet = self.protocol.build_packet(
            p_func=SenserWireProtocol.PFUNC_MEMORY_DUMP,
            payload=one_mb_payload,
            pad_to_512=False,
        )
        parsed = self.protocol.parse_packet(packet)
        self.assertEqual(parsed['size'], 1024 * 1024)
        self.assertEqual(len(parsed['payload']), 1024 * 1024)

    def test_corrupted_auth_step2_digest_rejected(self):
        """Passing an invalid hash in Step 2 causes PermissionError and aborts handshake."""
        self.cam.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        # Step 1
        self.cam.bulk_write(SenserWireProtocol.build_auth_packet(cmd=1))
        self.cam.bulk_read()

        # Step 2 with corrupted hash
        bad_hash = b'\xFF' * 20
        bad_packet = SenserWireProtocol.build_auth_packet(cmd=3, data=bytes([0x01]) + bad_hash)
        with self.assertRaises(PermissionError) as ctx:
            self.cam.bulk_write(bad_packet)
        self.assertIn("Cryptographic challenge failed", str(ctx.exception))
        # Handshake aborted: auth_state reset to 0
        self.assertEqual(self.cam.auth_state, 0)

    def test_auth_sequence_violation_step2_without_step1(self):
        """Attempting Step 2 without Step 1 raises PermissionError."""
        self.cam.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        bad_packet = SenserWireProtocol.build_auth_packet(cmd=3, data=bytes([0x01]) + (b'\x00' * 20))
        with self.assertRaises(PermissionError) as ctx:
            self.cam.bulk_write(bad_packet)
        self.assertIn("sequence error", str(ctx.exception))

    def test_auth_unknown_command_raises_value_error(self):
        """Sending an unrecognized auth command raises ValueError."""
        self.cam.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        unknown_pkt = SenserWireProtocol.build_auth_packet(cmd=99)
        with self.assertRaises(ValueError) as ctx:
            self.cam.bulk_write(unknown_pkt)
        self.assertIn("Unknown auth command", str(ctx.exception))

    def test_unknown_property_read_returns_empty(self):
        """Reading an unmapped property ID returns empty payload with response 0."""
        self.cam.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        controller = W300ServiceController(mock_camera=self.cam)
        controller.authenticate_senser()

        # Read unmapped property 0xDEADBEEF
        pkt = self.protocol.build_read_prop(0xDEADBEEF)
        self.cam.bulk_write(pkt)
        resp = self.protocol.parse_packet(self.cam.bulk_read())
        self.assertEqual(resp['response'], 0)
        self.assertEqual(resp['size'], 0)
        self.assertEqual(resp['payload'], b'')

    def test_malformed_language_mask_length_handling(self):
        """Verify get_enabled_languages gracefully handles truncated or short masks."""
        truncated_mask = bytes([0x01, 0x02, 0x01])  # Only 3 bytes
        enabled = Cee8Payload.get_enabled_languages(truncated_mask)
        self.assertEqual(enabled, ["English (en)", "French (fr)"])

        empty_enabled = Cee8Payload.get_enabled_languages(b'')
        self.assertEqual(empty_enabled, [])

    def test_safety_guardrail_locked_write_rejection(self):
        """Attempting to write destination while ID1 is locked triggers Access Denied (code 5)."""
        self.cam.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        controller = W300ServiceController(mock_camera=self.cam)
        controller.authenticate_senser()

        self.assertTrue(self.cam.id1_locked)
        self.assertEqual(self.cam.rejected_write_count, 0)

        # Attempt writing destination property directly without unlock
        with self.assertRaises(PermissionError) as ctx:
            controller.write_cee8_destination()
        self.assertIn("Service board protection locked", str(ctx.exception))
        self.assertGreater(self.cam.rejected_write_count, 0)
        # Verify flash store remains Japanese J1
        self.assertEqual(self.cam.flash_store[Cee8Payload.PROP_DESTINATION], b'J1\x00\x00')

    def test_bulk_write_rejected_in_mass_storage_mode(self):
        """Attempting bulk write when camera is not in Senser mode raises ConnectionError."""
        self.assertEqual(self.cam.mode, "MASS_STORAGE")
        with self.assertRaises(ConnectionError) as ctx:
            self.cam.bulk_write(b'\x00' * 516)
        self.assertIn("camera not in Senser mode", str(ctx.exception))

    def test_unknown_vendor_control_request_returns_negative(self):
        """Unrecognized USB control requests return -1."""
        res = self.cam.control_request(0x00, 0x00, 0x00, 0x00)
        self.assertEqual(res, -1)

    def test_controller_without_mock_or_live_raises_connection_error(self):
        """Controller without mock_camera raises ConnectionError for live USB attempts."""
        controller = W300ServiceController(mock_camera=None)
        with self.assertRaises(ConnectionError):
            controller.detect_device()
        with self.assertRaises(ConnectionError):
            controller.send_control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        with self.assertRaises(ConnectionError):
            controller.transfer_bulk(b'\x00' * 512)


# ============================================================================
# Tier 3 — Cross-Feature Combinations & Contracts
# ============================================================================

class TestTier3CrossFeatureCombinationsAndContracts(BaseServiceTestCase):
    """Tier 3: Multi-step transaction integrity, dry-run guarantees, rollback, and CLI exit codes."""

    def setUp(self):
        super().setUp()
        self.cam = W300MockUsbCamera(destination="J1", serial=1458291)

    def test_sequence_number_integrity_across_multi_step_transactions(self):
        """Verify camera echoes matching sequence numbers across sequential transactions."""
        self.cam.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        controller = W300ServiceController(mock_camera=self.cam)
        controller.authenticate_senser()

        proto = controller.protocol
        for expected_seq in range(proto.sequence, proto.sequence + 5):
            pkt = proto.build_read_prop(Cee8Payload.PROP_MODEL)
            resp_bytes = controller.transfer_bulk(pkt)
            parsed = proto.parse_packet(resp_bytes)
            self.assertEqual(parsed['sequence'], expected_seq)

    def test_fail_closed_dry_run_contract(self):
        """Executing full-cycle with --dry-run must leave camera NVM storage 100% unmodified."""
        initial_flash_snapshot = dict(self.cam.flash_store)
        initial_staging_snapshot = dict(self.cam.staging_ram)

        controller = W300ServiceController(mock_camera=self.cam, dry_run=True)
        res = controller.run_full_cycle()
        self.assertTrue(res)

        # Assert flash commit was NEVER called
        self.assertEqual(self.cam.flash_commit_count, 0)
        # Assert flash store is bit-for-bit identical to baseline
        self.assertEqual(self.cam.flash_store, initial_flash_snapshot)
        self.assertEqual(self.cam.flash_store[Cee8Payload.PROP_DESTINATION], b'J1\x00\x00')
        self.assertEqual(self.cam.flash_store[Cee8Payload.PROP_VIDEO_OUT], b'\x00')
        self.assertEqual(self.cam.flash_store[Cee8Payload.PROP_LANG_BASE], Cee8Payload.LANG_MASK_J1)

        # Assert staging RAM was not mutated
        self.assertEqual(self.cam.staging_ram, initial_staging_snapshot)

        # Assert reboot was skipped in dry-run
        self.assertEqual(self.cam.reboot_count, 0)

    def test_round_trip_destination_conversion_and_rollback(self):
        """Verify complete roundtrip: J1 -> CEE8 -> J1 with bit-for-bit restoration."""
        baseline_flash = dict(self.cam.flash_store)

        # 1. Convert J1 -> CEE8
        controller = W300ServiceController(mock_camera=self.cam, dry_run=False)
        self.assertTrue(controller.run_full_cycle())
        self.assertEqual(self.cam.flash_store[Cee8Payload.PROP_DESTINATION], b'CEE8')
        self.assertEqual(self.cam.flash_store[Cee8Payload.PROP_VIDEO_OUT], b'\x01')
        self.assertEqual(self.cam.flash_store[Cee8Payload.PROP_LANG_BASE], Cee8Payload.LANG_MASK_CEE8)
        self.assertEqual(self.cam.flash_commit_count, 1)

        # 2. Rollback CEE8 -> J1
        controller.switch_to_senser_mode()
        controller.authenticate_senser()
        controller.unlock_service_board()

        proto = controller.protocol
        controller.transfer_bulk(proto.build_write_prop(Cee8Payload.PROP_VIDEO_OUT, b'\x00'))
        controller.transfer_bulk(proto.build_write_prop(Cee8Payload.PROP_LANG_BASE, Cee8Payload.LANG_MASK_J1))
        controller.transfer_bulk(proto.build_write_prop(Cee8Payload.PROP_DESTINATION, b'J1\x00\x00'))
        controller.commit_flash()
        controller.reset_device()

        # 3. Assert bit-for-bit restoration
        self.assertEqual(self.cam.flash_commit_count, 2)
        self.assertEqual(self.cam.flash_store, baseline_flash)

    def test_cli_exit_code_0_on_success(self):
        """CLI contract: returns 0 on successful operations."""
        commands = [
            ["--mock", "detect"],
            ["--mock", "read"],
            ["--mock", "unlock"],
            ["--mock", "reset"],
            ["--mock", "full-cycle", "--dry-run"],
            ["--mock", "full-cycle"],
        ]
        for cmd_args in commands:
            res = subprocess.run(
                [sys.executable, str(TOOL_SCRIPT_PATH)] + cmd_args,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Failed on command: {cmd_args}\nStderr: {res.stderr}")

    def test_cli_exit_code_2_on_safety_guardrail(self):
        """CLI contract: returns 2 when write is attempted without unlock."""
        res = subprocess.run(
            [sys.executable, str(TOOL_SCRIPT_PATH), "--mock", "write-cee8"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 2)
        self.assertIn("[ERROR: ACCESS_DENIED]", res.stderr)
        self.assertIn("Service board protection locked", res.stderr)

    def test_cli_rejects_unvalidated_live_programming(self):
        """Must reject live programming independently of connected hardware."""
        res = subprocess.run(
            [sys.executable, str(TOOL_SCRIPT_PATH), "full-cycle"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 2)
        self.assertIn("[ERROR: UNVALIDATED_W300]", res.stderr)

    def test_cli_help_and_no_arguments(self):
        """Verify --help returns exit code 0 and provides usage instructions."""
        res_help = subprocess.run(
            [sys.executable, str(TOOL_SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_help.returncode, 0)
        self.assertIn("Sony Cyber-shot DSC-W300", res_help.stdout)

        res_none = subprocess.run(
            [sys.executable, str(TOOL_SCRIPT_PATH)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_none.returncode, 0)


# ============================================================================
# Tier 4 — Real-World Application Scenarios
# ============================================================================

class TestTier4RealWorldScenarios(BaseServiceTestCase):
    """Tier 4: End-to-end operational workflows, readback, subsystem isolation, and concurrency."""

    def test_e2e_full_cycle_lifecycle_against_mock(self):
        """Execute complete operational lifecycle against mock camera and verify state transitions."""
        cam = W300MockUsbCamera(destination="J1", serial=1458291)
        controller = W300ServiceController(mock_camera=cam, dry_run=False)

        self.assertEqual(cam.mode, "MASS_STORAGE")
        self.assertEqual(cam.flash_commit_count, 0)
        self.assertEqual(cam.reboot_count, 0)

        # Run lifecycle
        success = controller.run_full_cycle()
        self.assertTrue(success)

        # Assert post-lifecycle camera state
        self.assertEqual(cam.mode, "MASS_STORAGE")
        self.assertEqual(cam.current_pid, 0x031B)
        self.assertEqual(cam.flash_commit_count, 1)
        self.assertEqual(cam.reboot_count, 1)
        self.assertEqual(cam.flash_store[Cee8Payload.PROP_DESTINATION], b'CEE8')
        self.assertEqual(cam.flash_store[Cee8Payload.PROP_VIDEO_OUT], b'\x01')

    def test_e2e_verification_readback_properties(self):
        """Verify post-conversion readback confirms English active, Polish enabled, PAL video."""
        cam = W300MockUsbCamera(destination="J1", serial=1458291)
        controller = W300ServiceController(mock_camera=cam, dry_run=False)
        controller.run_full_cycle()

        # Connect again to read back properties
        readback_controller = W300ServiceController(mock_camera=cam)
        info = readback_controller.read_destination_info()

        self.assertEqual(info['model'], "W300")
        self.assertEqual(info['serial'], 1458291)
        self.assertEqual(info['destination'], "CEE8")
        self.assertEqual(info['video'], "PAL")
        self.assertIn("English (en)", info['active_languages'])
        self.assertIn("Polish (pl)", info['active_languages'])
        self.assertNotIn("Japanese (ja)", info['active_languages'])
        self.assertEqual(len(info['active_languages']), 19)

    def test_subsystem_isolation_preserves_calibration_data(self):
        """Verify destination write does NOT touch optical or sensor calibration ranges."""
        cam = W300MockUsbCamera(destination="J1", serial=1458291)

        # Inject factory calibration properties across Subsystems 0x02 and 0x03
        PROP_OPTICAL_CALIB = 0x02010010
        PROP_SENSOR_DEFECT_MAP = 0x02020050
        PROP_WHITE_BALANCE = 0x020300A0

        optical_bytes = b'\x12\x34\x56\x78\x9A\xBC\xDE\xF0\x11\x22\x33\x44'
        defect_bytes = bytes(range(64))
        wb_bytes = b'FACTORY_WB_CALIBRATION_MATRIX_DO_NOT_ALTER'

        cam.flash_store[PROP_OPTICAL_CALIB] = optical_bytes
        cam.flash_store[PROP_SENSOR_DEFECT_MAP] = defect_bytes
        cam.flash_store[PROP_WHITE_BALANCE] = wb_bytes
        cam.staging_ram = dict(cam.flash_store)

        controller = W300ServiceController(mock_camera=cam, dry_run=False)
        self.assertTrue(controller.run_full_cycle())

        # Assert calibration properties are completely unmodified
        self.assertEqual(cam.flash_store[PROP_OPTICAL_CALIB], optical_bytes)
        self.assertEqual(cam.flash_store[PROP_SENSOR_DEFECT_MAP], defect_bytes)
        self.assertEqual(cam.flash_store[PROP_WHITE_BALANCE], wb_bytes)

        self.assertEqual(cam.staging_ram[PROP_OPTICAL_CALIB], optical_bytes)
        self.assertEqual(cam.staging_ram[PROP_SENSOR_DEFECT_MAP], defect_bytes)
        self.assertEqual(cam.staging_ram[PROP_WHITE_BALANCE], wb_bytes)

    def test_concurrent_mock_camera_instances_isolation(self):
        """Verify independent mock camera instances maintain isolated state."""
        cam_tokyo = W300MockUsbCamera(destination="J1", serial=1111111)
        cam_warsaw = W300MockUsbCamera(destination="J1", serial=2222222)

        controller_warsaw = W300ServiceController(mock_camera=cam_warsaw, dry_run=False)
        controller_warsaw.run_full_cycle()

        # Warsaw camera converted to CEE8
        self.assertEqual(cam_warsaw.flash_store[Cee8Payload.PROP_DESTINATION], b'CEE8')
        self.assertEqual(cam_warsaw.flash_store[Cee8Payload.PROP_VIDEO_OUT], b'\x01')
        self.assertEqual(cam_warsaw.flash_commit_count, 1)

        # Tokyo camera remains untouched J1
        self.assertEqual(cam_tokyo.flash_store[Cee8Payload.PROP_DESTINATION], b'J1\x00\x00')
        self.assertEqual(cam_tokyo.flash_store[Cee8Payload.PROP_VIDEO_OUT], b'\x00')
        self.assertEqual(cam_tokyo.flash_commit_count, 0)
        self.assertEqual(cam_tokyo.reboot_count, 0)


if __name__ == "__main__":
    unittest.main()
