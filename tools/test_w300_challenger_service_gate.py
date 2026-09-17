#!/usr/bin/env python3
"""Offline hypothetical service-model regression tests.

All calibration, region, transport and recovery scenarios use invented fixtures.
Passing these tests establishes no compatibility or efficacy on W300 hardware.
"""

from __future__ import annotations

import binascii
import contextlib
import copy
import io
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock

# Ensure tools directory is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from w300_service_tool import (
    sha1_faulty,
    SenserWireProtocol,
    Cee8Payload,
    W300MockUsbCamera,
    W300ServiceController,
)



class BaseChallengerTestCase(unittest.TestCase):
    """Base fixture providing stdout capture to keep test output clean."""

    def setUp(self):
        super().setUp()
        self._stdout_trap = io.StringIO()
        self._trap_ctx = contextlib.redirect_stdout(self._stdout_trap)
        self._trap_ctx.__enter__()

    def tearDown(self):
        self._trap_ctx.__exit__(None, None, None)
        super().tearDown()


# ============================================================================
# 1. Roundtrip Reversibility (J1 -> CEE8 -> J1) & Bit-for-Bit Restoration
# ============================================================================

class TestRoundtripReversibility(BaseChallengerTestCase):
    """Empirical verification of full J1 -> CEE8 -> J1 roundtrip reversibility."""

    def setUp(self):
        super().setUp()
        # Initialize the hypothetical J1 camera model
        self.camera = W300MockUsbCamera(destination="J1", serial=1458291)
        # Populate additional persistent camera parameters (arbitrary non-destination NVM entries)
        self.camera.flash_store[0x00E70002] = b'HW_REV_02\x00'
        self.camera.flash_store[0x00E70004] = b'\x10\x20\x30\x40'  # Factory manufacturing date
        self.camera.flash_store[0x01070100] = b'\x05'              # LCD Brightness setting
        self.camera.flash_store[0x01070110] = b'\x02'              # Beep volume setting
        self.camera.flash_store[0x01070120] = b'\x00'              # Power save timeout
        self.camera.staging_ram = copy.deepcopy(self.camera.flash_store)

        # Take bit-for-bit baseline snapshot before any operation
        self.baseline_flash = copy.deepcopy(self.camera.flash_store)
        self.baseline_staging = copy.deepcopy(self.camera.staging_ram)

    def test_full_roundtrip_j1_cee8_j1_bit_for_bit(self):
        """Perform full J1 -> CEE8 conversion, verify CEE8 state, then rollback to J1 and assert bit-for-bit match."""
        # --- PHASE 1: J1 -> CEE8 Conversion ---
        controller = W300ServiceController(mock_camera=self.camera, dry_run=False)
        conversion_ok = controller.run_full_cycle()
        self.assertTrue(conversion_ok, "J1 -> CEE8 lifecycle failed")

        # Assert intermediate CEE8 state
        self.assertEqual(self.camera.flash_commit_count, 1)
        self.assertEqual(self.camera.reboot_count, 1)
        self.assertEqual(self.camera.mode, "MASS_STORAGE")
        self.assertEqual(self.camera.current_pid, W300MockUsbCamera.PID_MASS_STORAGE)
        self.assertEqual(self.camera.flash_store[Cee8Payload.PROP_DESTINATION], b'CEE8')
        self.assertEqual(self.camera.flash_store[Cee8Payload.PROP_VIDEO_OUT], b'\x01')
        self.assertEqual(self.camera.flash_store[Cee8Payload.PROP_LANG_BASE], Cee8Payload.LANG_MASK_CEE8)

        # Verify active languages in CEE8 state
        enabled_cee8 = Cee8Payload.get_enabled_languages(self.camera.flash_store[Cee8Payload.PROP_LANG_BASE])
        self.assertIn("English (en)", enabled_cee8)
        self.assertIn("Polish (pl)", enabled_cee8)
        self.assertNotIn("Japanese (ja)", enabled_cee8)
        self.assertEqual(len(enabled_cee8), 19)

        # Assert non-target properties were NOT altered during CEE8 conversion
        self.assertEqual(self.camera.flash_store[Cee8Payload.PROP_MODEL], b'W300\x00')
        self.assertEqual(self.camera.flash_store[Cee8Payload.PROP_SERIAL], struct.pack('<I', 1458291))
        self.assertEqual(self.camera.flash_store[0x00E70002], b'HW_REV_02\x00')
        self.assertEqual(self.camera.flash_store[0x00E70004], b'\x10\x20\x30\x40')
        self.assertEqual(self.camera.flash_store[0x01070100], b'\x05')

        # --- PHASE 2: CEE8 -> J1 Rollback ---
        # Connect to camera again in service mode
        rollback_controller = W300ServiceController(mock_camera=self.camera, dry_run=False)
        rollback_controller.switch_to_senser_mode()
        rollback_controller.authenticate_senser()
        rollback_controller.unlock_service_board()

        proto = rollback_controller.protocol
        # Restore NTSC video standard (0x00)
        rollback_controller.transfer_bulk(proto.build_write_prop(Cee8Payload.PROP_VIDEO_OUT, b'\x00'))
        # Restore Japanese-only language mask
        rollback_controller.transfer_bulk(proto.build_write_prop(Cee8Payload.PROP_LANG_BASE, Cee8Payload.LANG_MASK_J1))
        # Restore J1 destination code string
        rollback_controller.transfer_bulk(proto.build_write_prop(Cee8Payload.PROP_DESTINATION, b'J1\x00\x00'))
        # Commit to the simulated flash store
        rollback_controller.commit_flash()
        # Clean reboot into retail Mass Storage mode
        rollback_controller.reset_device()

        # --- PHASE 3: Assert Bit-for-Bit Restoration ---
        self.assertEqual(self.camera.flash_commit_count, 2)
        self.assertEqual(self.camera.reboot_count, 2)
        self.assertEqual(self.camera.mode, "MASS_STORAGE")
        self.assertEqual(self.camera.current_pid, W300MockUsbCamera.PID_MASS_STORAGE)
        self.assertTrue(self.camera.id1_locked)

        # Check all keys in flash store
        self.assertEqual(set(self.camera.flash_store.keys()), set(self.baseline_flash.keys()))
        for prop_id, baseline_val in self.baseline_flash.items():
            current_val = self.camera.flash_store[prop_id]
            self.assertEqual(
                current_val, baseline_val,
                f"Bit mismatch at property 0x{prop_id:08X}: expected {baseline_val!r}, got {current_val!r}"
            )

        # Check staging RAM reloaded from flash store
        self.assertEqual(self.camera.staging_ram, self.baseline_staging)

        # Verify active languages in restored J1 state
        enabled_j1 = Cee8Payload.get_enabled_languages(self.camera.flash_store[Cee8Payload.PROP_LANG_BASE])
        self.assertEqual(enabled_j1, ["Japanese (ja)"])

    def test_repeated_multi_cycle_roundtrip_stability(self):
        """Execute 5 consecutive J1 -> CEE8 -> J1 roundtrips to confirm zero parameter drift."""
        for cycle in range(1, 6):
            controller = W300ServiceController(mock_camera=self.camera, dry_run=False)
            # J1 -> CEE8
            self.assertTrue(controller.run_full_cycle())
            self.assertEqual(self.camera.flash_store[Cee8Payload.PROP_DESTINATION], b'CEE8')

            # CEE8 -> J1
            controller.switch_to_senser_mode()
            controller.authenticate_senser()
            controller.unlock_service_board()
            proto = controller.protocol
            controller.transfer_bulk(proto.build_write_prop(Cee8Payload.PROP_VIDEO_OUT, b'\x00'))
            controller.transfer_bulk(proto.build_write_prop(Cee8Payload.PROP_LANG_BASE, Cee8Payload.LANG_MASK_J1))
            controller.transfer_bulk(proto.build_write_prop(Cee8Payload.PROP_DESTINATION, b'J1\x00\x00'))
            controller.commit_flash()
            controller.reset_device()

            # Verify bit-for-bit equality after cycle
            self.assertEqual(self.camera.flash_store, self.baseline_flash)
            self.assertEqual(self.camera.flash_commit_count, cycle * 2)


# ============================================================================
# 2. Calibration Isolation & Parameter Protection
# ============================================================================

class TestCalibrationIsolation(BaseChallengerTestCase):
    """Verify that the model preserves the synthetic calibration parameters."""

    def setUp(self):
        super().setUp()
        self.camera = W300MockUsbCamera(destination="J1", serial=1458291)

        # Populate factory optical, sensor, gyro, and shutter calibration registers
        # across Subsystems 0x02, 0x03, and Block 11 Page 60 & 61 address spaces
        self.calib_store = {
            # Subsystem 0x02: Optical & Hardware Adjustments
            0x02010010: b'\x42\x13\x88\x00\xFF\x01\x23\x45\x67\x89\xAB\xCD',  # Flange back zoom tracking
            0x02020050: bytes((x * 3) & 0xFF for x in range(128)),            # CCD White defect map
            0x020300A0: b'FACTORY_AWB_3200K_HALOGEN_REF_VECTOR_DATA_01234',    # AWB matrix
            0x02040010: b'\xDE\xAD\xBE\xEF\xCA\xFE\xBA\xBE',                  # Gyro Pitch/Yaw sensitivity

            # Subsystem 0x03: Sensor Defect & DAC Maps
            0x03000001: b'\x12\x34\x56\x78',                                  # CCD Black defect compensation
            0x03000040: b'\x99\x88\x77\x66\x55\x44\x33\x22',                  # Mechanical shutter curve
            0x03010080: b'\x01\x02\x03\x04\x05\x06\x07\x08',                  # Iris aperture compensation

            # Block 11 Page 60 (0x0B3Cxxxx): Video & LCD Calibration
            0x0B3C0401: b'\x7F',                                              # LCD V-COM Common Electrode Voltage
            0x0B3C0680: b'\x50\x50\x50',                                      # Component HD_Y/Pb/Pr DAC level
            0x0B3C06B8: b'\x80',                                              # Composite Video output level

            # Block 11 Page 61 (0x0B3Dxxxx): Camera Hardware Adjustments (25 inviolable ranges)
            0x0B3D0000: bytes(range(64)),                                     # CCD Black defect table
            0x0B3D0200: bytes(range(64)),                                     # CCD White defect table
            0x0B3D069C: b'\x11\x22\x33\x44',                                  # Flange back zoom tracking table
            0x0B3D0980: b'\xAA\xBB\xCC\xDD\xEE',                              # Shutter slit width & timing
            0x0B3D0C00: b'AWB_3200K_HALOGEN_STANDARD_CALIBRATION_CURVE_DATA', # AWB 3200K
            0x0B3D0C24: b'AWB_5800K_DAYLIGHT_STANDARD_CALIBRATION_CURVE_DAT', # AWB 5800K
            0x0B3D0E10: b'\x12\x34',                                          # SteadyShot Gyro Dp, Dy
            0x0B3D0F20: b'\x05\x0A\x0F\x14\x19',                              # Flange back stepping motor drive
            0x0B3D0F26: bytes(range(46)),                                     # Flange back focus curve array
        }

        # Inject into camera flash store
        self.camera.flash_store.update(self.calib_store)
        self.camera.staging_ram = copy.deepcopy(self.camera.flash_store)

    def test_calibration_parameters_untouched_during_full_cycle(self):
        """Verify full CEE8 lifecycle leaves 100% of calibration parameters strictly untouched."""
        controller = W300ServiceController(mock_camera=self.camera, dry_run=False)
        success = controller.run_full_cycle()
        self.assertTrue(success)

        # Assert every single calibration parameter in flash_store is bit-for-bit identical
        for prop_id, expected_data in self.calib_store.items():
            self.assertIn(prop_id, self.camera.flash_store, f"Calibration property 0x{prop_id:08X} was deleted!")
            actual_data = self.camera.flash_store[prop_id]
            self.assertEqual(
                actual_data, expected_data,
                f"CORRUPTION DETECTED: Factory calibration 0x{prop_id:08X} altered from {expected_data!r} to {actual_data!r}"
            )

        # Assert staging RAM also preserves exact calibration data
        for prop_id, expected_data in self.calib_store.items():
            self.assertEqual(self.camera.staging_ram[prop_id], expected_data)

    def test_intercept_all_write_packets_targeting_camera(self):
        """Track every packet sent during full lifecycle to prove zero write targets calibration registers."""
        written_prop_ids = []

        # Create a proxy controller that logs property write targets
        original_write_prop = SenserWireProtocol.build_write_prop

        def logged_write_prop(proto_self, prop_id: int, data: bytes):
            written_prop_ids.append(prop_id)
            return original_write_prop(proto_self, prop_id, data)

        with unittest.mock.patch.object(SenserWireProtocol, 'build_write_prop', side_effect=logged_write_prop, autospec=True):
            controller = W300ServiceController(mock_camera=self.camera, dry_run=False)
            controller.run_full_cycle()

        # The only properties written during the entire lifecycle must be:
        # PROP_VIDEO_OUT (0x01070148), PROP_LANG_BASE (0x010D008F), PROP_DESTINATION (0x00E70001)
        expected_allowed_props = {
            Cee8Payload.PROP_VIDEO_OUT,
            Cee8Payload.PROP_LANG_BASE,
            Cee8Payload.PROP_DESTINATION,
        }
        self.assertEqual(set(written_prop_ids), expected_allowed_props)

        # Verify that NO written property ID belongs to Subsystem 0x02, Subsystem 0x03, or Block 11
        for prop_id in written_prop_ids:
            subsystem = (prop_id >> 24) & 0xFF
            self.assertNotIn(
                subsystem, (0x02, 0x03, 0x0B),
                f"Security violation: write targeted protected subsystem 0x{subsystem:02X} (prop 0x{prop_id:08X})"
            )



# ============================================================================
# 3. Sequence Number Monotonicity & Wrapping at 0xFFFF
# ============================================================================

class TestSequenceNumberMonotonicityAndWrapping(BaseChallengerTestCase):
    """Empirical verification of packet sequence number monotonicity and 0xFFFF wrapping."""

    def test_sequence_monotonicity_linear(self):
        """Verify sequential packets increment sequence by exactly +1."""
        proto = SenserWireProtocol(start_sequence=500)
        for expected in range(500, 600):
            pkt = proto.build_packet(p_func=SenserWireProtocol.PFUNC_PRODUCT_INFO, pad_to_512=False)
            parsed = proto.parse_packet(pkt)
            self.assertEqual(parsed['sequence'], expected)
        self.assertEqual(proto.sequence, 600)

    def test_sequence_wrapping_at_0xffff_boundary(self):
        """Verify exact rollover from 0xFFFE -> 0xFFFF -> 0x0000 -> 0x0001."""
        proto = SenserWireProtocol(start_sequence=0xFFFD)

        # Packet 1: 0xFFFD
        p1 = proto.build_packet(p_func=0x0010, pad_to_512=False)
        self.assertEqual(proto.parse_packet(p1)['sequence'], 0xFFFD)
        self.assertEqual(proto.sequence, 0xFFFE)

        # Packet 2: 0xFFFE
        p2 = proto.build_packet(p_func=0x0010, pad_to_512=False)
        self.assertEqual(proto.parse_packet(p2)['sequence'], 0xFFFE)
        self.assertEqual(proto.sequence, 0xFFFF)

        # Packet 3: 0xFFFF (max 16-bit value)
        p3 = proto.build_packet(p_func=0x0010, pad_to_512=False)
        self.assertEqual(proto.parse_packet(p3)['sequence'], 0xFFFF)
        # Next sequence must wrap to 0x0000
        self.assertEqual(proto.sequence, 0x0000)

        # Packet 4: 0x0000 (first value after wrap)
        p4 = proto.build_packet(p_func=0x0010, pad_to_512=False)
        self.assertEqual(proto.parse_packet(p4)['sequence'], 0x0000)
        self.assertEqual(proto.sequence, 0x0001)

        # Packet 5: 0x0001
        p5 = proto.build_packet(p_func=0x0010, pad_to_512=False)
        self.assertEqual(proto.parse_packet(p5)['sequence'], 0x0001)
        self.assertEqual(proto.sequence, 0x0002)

    def test_camera_acknowledgement_sequence_echo_across_wrap(self):
        """Verify W300MockUsbCamera correctly echoes wrapped sequence numbers in responses."""
        camera = W300MockUsbCamera()
        camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        controller = W300ServiceController(mock_camera=camera)
        controller.authenticate_senser()

        # Set protocol sequence right before wrap boundary
        controller.protocol.sequence = 0xFFFE

        # Transaction 1: Sequence 0xFFFE
        pkt1 = controller.protocol.build_read_prop(Cee8Payload.PROP_MODEL)
        resp1 = controller.transfer_bulk(pkt1)
        parsed1 = controller.protocol.parse_packet(resp1)
        self.assertEqual(parsed1['sequence'], 0xFFFE)

        # Transaction 2: Sequence 0xFFFF
        pkt2 = controller.protocol.build_read_prop(Cee8Payload.PROP_MODEL)
        resp2 = controller.transfer_bulk(pkt2)
        parsed2 = controller.protocol.parse_packet(resp2)
        self.assertEqual(parsed2['sequence'], 0xFFFF)

        # Transaction 3: Sequence 0x0000 (Wrapped)
        pkt3 = controller.protocol.build_read_prop(Cee8Payload.PROP_MODEL)
        resp3 = controller.transfer_bulk(pkt3)
        parsed3 = controller.protocol.parse_packet(resp3)
        self.assertEqual(parsed3['sequence'], 0x0000)

        # Transaction 4: Sequence 0x0001
        pkt4 = controller.protocol.build_read_prop(Cee8Payload.PROP_MODEL)
        resp4 = controller.transfer_bulk(pkt4)
        parsed4 = controller.protocol.parse_packet(resp4)
        self.assertEqual(parsed4['sequence'], 0x0001)

    def test_full_cycle_executes_seamlessly_across_wrap_boundary(self):
        """Start full lifecycle right before 0xFFFF to verify seamless execution during wrap."""
        camera = W300MockUsbCamera(destination="J1", serial=1458291)
        controller = W300ServiceController(mock_camera=camera, dry_run=False)
        # Position sequence counter 4 packets before 0xFFFF
        controller.protocol.sequence = 0xFFFC

        success = controller.run_full_cycle()
        self.assertTrue(success)

        # Verify that sequence counter has wrapped into low numbers
        self.assertLess(controller.protocol.sequence, 0x0020)
        self.assertGreater(controller.protocol.sequence, 0x0005)

        # Verify camera successfully transitioned to CEE8
        self.assertEqual(camera.flash_store[Cee8Payload.PROP_DESTINATION], b'CEE8')
        self.assertEqual(camera.flash_commit_count, 1)

    def test_70000_packet_stress_wrap(self):
        """Stress test: execute 70,000 packet builds across multiple wrap-arounds."""
        proto = SenserWireProtocol(start_sequence=0)
        expected_seq = 0
        for _ in range(70000):
            pkt = proto.build_packet(p_func=0x0010, pad_to_512=False)
            size, pfunc, seq, _, _, _, _ = struct.unpack('<IHHBBBB', pkt[:12])
            self.assertEqual(seq, expected_seq)
            expected_seq = (expected_seq + 1) & 0xFFFF
        self.assertEqual(proto.sequence, expected_seq)


# ============================================================================
# 4. Large Multi-Chunk Payload Handling & Boundary Dynamics
# ============================================================================

class TestLargeMultiChunkPayloadHandling(BaseChallengerTestCase):
    """Empirical verification of large payload transfers, chunking, and buffer boundaries."""

    def setUp(self):
        super().setUp()
        self.protocol = SenserWireProtocol()
        self.camera = W300MockUsbCamera()

    def test_large_payload_framing_1kb_to_1mb(self):
        """Verify SenserWireProtocol frames and parses payloads from 1 KB up to 1 MB."""
        sizes = [1024, 4096, 16384, 65536, 1048576]
        for sz in sizes:
            payload = bytes((i & 0xFF) for i in range(sz))
            packet = self.protocol.build_packet(
                p_func=SenserWireProtocol.PFUNC_MEMORY_DUMP,
                payload=payload,
                pad_to_512=False,
            )
            self.assertEqual(len(packet), 12 + sz)

            parsed = self.protocol.parse_packet(packet)
            self.assertEqual(parsed['size'], sz)
            self.assertEqual(parsed['pFunc'], SenserWireProtocol.PFUNC_MEMORY_DUMP)
            self.assertEqual(parsed['payload'], payload)

    def test_exact_512_byte_packet_boundaries(self):
        """Verify packets at 511, 512, and 513 bytes (512-byte USB bulk boundary)."""
        # 12-byte header + 499-byte payload = 511 bytes -> padded to 512
        p511 = self.protocol.build_packet(p_func=0x0010, payload=b'A' * 499, pad_to_512=True)
        self.assertEqual(len(p511), 512)
        self.assertEqual(self.protocol.parse_packet(p511)['size'], 499)

        # 12-byte header + 500-byte payload = 512 bytes -> exactly 512
        p512 = self.protocol.build_packet(p_func=0x0010, payload=b'B' * 500, pad_to_512=True)
        self.assertEqual(len(p512), 512)
        self.assertEqual(self.protocol.parse_packet(p512)['size'], 500)

        # 12-byte header + 501-byte payload = 513 bytes -> not padded, length 513
        p513 = self.protocol.build_packet(p_func=0x0010, payload=b'C' * 501, pad_to_512=True)
        self.assertEqual(len(p513), 513)
        self.assertEqual(self.protocol.parse_packet(p513)['size'], 501)

    def test_mock_camera_large_property_write_and_readback(self):
        """Verify writing and reading a 4096-byte calibration/dump property through mock camera."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        controller = W300ServiceController(mock_camera=self.camera)
        controller.authenticate_senser()
        controller.unlock_service_board()

        LARGE_PROP_ID = 0x02500000
        large_data = bytes((x * 7) & 0xFF for x in range(4096))

        # Write 4096-byte property
        write_pkt = controller.protocol.build_write_prop(LARGE_PROP_ID, large_data)
        # Note: write_pkt has 12 (hdr) + 4 (cat/cmd) + 4 (prop) + 4096 = 4116 bytes
        self.camera.bulk_write(write_pkt)
        resp_write = self.camera.bulk_read()
        parsed_write = controller.protocol.parse_packet(resp_write)
        self.assertEqual(parsed_write['response'], 0)

        # Verify stored in staging RAM
        self.assertEqual(self.camera.staging_ram[LARGE_PROP_ID], large_data)

        # Commit to flash and verify flash store
        commit_pkt = controller.protocol.build_commit_flash(subsystem=0)
        self.camera.bulk_write(commit_pkt)
        self.camera.bulk_read()
        self.assertEqual(self.camera.flash_store[LARGE_PROP_ID], large_data)

        # Read back property
        read_pkt = controller.protocol.build_read_prop(LARGE_PROP_ID)
        self.camera.bulk_write(read_pkt)
        # Read with buffer size 8192 to encompass full 4096-byte response + 12-byte header
        resp_read = self.camera.bulk_read(length=8192)
        parsed_read = controller.protocol.parse_packet(resp_read)
        self.assertEqual(parsed_read['response'], 0)
        self.assertEqual(parsed_read['size'], 4096)
        self.assertEqual(parsed_read['payload'], large_data)

    def test_chunked_streaming_read_simulation(self):
        """Simulate physical USB transport streaming chunks of 512 bytes for a 2048-byte payload."""
        payload_data = bytes((x * 13) & 0xFF for x in range(2048))
        full_packet = self.protocol.build_packet(
            p_func=SenserWireProtocol.PFUNC_MEMORY_DUMP,
            payload=payload_data,
            pad_to_512=False,
        )
        total_len = len(full_packet)  # 12 + 2048 = 2060 bytes

        # Simulate USB transfer in 512-byte MTU chunks
        CHUNK_SIZE = 512
        chunks = [full_packet[i:i + CHUNK_SIZE] for i in range(0, total_len, CHUNK_SIZE)]
        self.assertEqual(len(chunks), 5)  # 512*4 = 2048 + 12 = 2060 (5 chunks)

        # Streaming receiver reassembly
        stream_buffer = bytearray()
        for chunk in chunks:
            stream_buffer.extend(chunk)

        # Parse assembled stream
        parsed = self.protocol.parse_packet(bytes(stream_buffer))
        self.assertEqual(parsed['size'], 2048)
        self.assertEqual(parsed['payload'], payload_data)

    def test_undersized_buffer_truncation_behavior(self):
        """Document and verify behavior when transfer_bulk buffer (4096) is smaller than packet (4108)."""
        self.camera.control_request(0x43, 0x01, 0x37FF, 0xD7AA)
        controller = W300ServiceController(mock_camera=self.camera)
        controller.authenticate_senser()
        controller.unlock_service_board()

        LARGE_PROP_ID = 0x02500001
        large_data = bytes((x * 11) & 0xFF for x in range(4096))
        self.camera.staging_ram[LARGE_PROP_ID] = large_data

        # Request property using standard transfer_bulk with default read_length=4096
        read_pkt = controller.protocol.build_read_prop(LARGE_PROP_ID)
        in_data = controller.transfer_bulk(read_pkt, read_length=4096)

        # in_data is capped at 4096 bytes, but total packet is 4096 + 12 = 4108 bytes
        self.assertEqual(len(in_data), 4096)
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            controller.protocol.parse_packet(in_data)

        # Remaining 12 bytes stayed in camera tx_buffer
        leftover = self.camera.bulk_read()
        self.assertEqual(len(leftover), 12)
        # Combined payload equals original data
        parsed = controller.protocol.parse_packet(in_data + leftover)
        self.assertEqual(parsed['payload'], large_data)

    def test_zero_payload_packet_handling(self):
        """Verify building and parsing packets with zero-length payload."""
        pkt = self.protocol.build_packet(p_func=0x0010, payload=b'', pad_to_512=False)
        self.assertEqual(len(pkt), 12)
        parsed = self.protocol.parse_packet(pkt)
        self.assertEqual(parsed['size'], 0)
        self.assertEqual(parsed['payload'], b'')

    def test_64kb_plus_32bit_payload_framing(self):
        """Verify handling of payloads exceeding 16-bit unsigned integer (65,536 bytes)."""
        payload_70k = b'Z' * 70000
        pkt = self.protocol.build_packet(p_func=0xFF03, payload=payload_70k, pad_to_512=False)
        self.assertEqual(len(pkt), 12 + 70000)
        # Verify size unpacks as 32-bit integer
        size = struct.unpack('<I', pkt[:4])[0]
        self.assertEqual(size, 70000)
        parsed = self.protocol.parse_packet(pkt)
        self.assertEqual(parsed['size'], 70000)
        self.assertEqual(len(parsed['payload']), 70000)


if __name__ == "__main__":
    unittest.main()
