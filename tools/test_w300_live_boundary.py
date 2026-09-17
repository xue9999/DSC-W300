"""Regression checks for host-only preflight; no hardware access in tests."""
import contextlib
import io
import struct
import unittest
from unittest.mock import patch

import w300_service_tool as svc


class LiveBoundaryTests(unittest.TestCase):
    def test_dry_run_cannot_initialize_usb(self):
        with patch('ctypes.CDLL', side_effect=AssertionError('USB opened')):
            with contextlib.redirect_stdout(io.StringIO()):
                controller = svc.W300ServiceController(dry_run=True)
                self.assertTrue(controller.run_full_cycle())
            self.assertFalse(hasattr(controller, "transport"))
            self.assertFalse(hasattr(svc, "SafeLibUsbTransport"))
            self.assertEqual(controller.mock_camera.flash_store[svc.Cee8Payload.PROP_DESTINATION], b'J1\0\0')

    def test_every_live_service_cli_command_rejected_before_usb(self):
        for command in ('read', 'unlock', 'write-cee8', 'commit', 'reset', 'full-cycle'):
            with self.subTest(command=command), patch('ctypes.CDLL', side_effect=AssertionError('USB opened')):
                with patch('sys.argv', ['tool', command]), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(svc.main(), 2)

    def test_passive_detection_accepts_observed_descriptor(self):
        observed = {'sony_devices': [{'product': 'DSC-W300', 'product_id': '0341'}]}
        with patch('w300_evidence.inventory', return_value=observed), patch('ctypes.CDLL', side_effect=AssertionError('USB opened')):
            with patch('sys.argv', ['tool', 'detect']), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(svc.main(), 0)

    def test_direct_unconfigured_controller_refuses_all_operations(self):
        controller = svc.W300ServiceController()
        for operation in ('detect_device', 'switch_to_senser_mode', 'authenticate_senser',
                          'read_destination_info', 'unlock_service_board',
                          'write_cee8_destination', 'commit_flash', 'reset_device', 'run_full_cycle'):
            with self.subTest(operation=operation), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ConnectionError):
                    getattr(controller, operation)()

    def test_mock_metadata_does_not_claim_hardware_validation(self):
        with contextlib.redirect_stdout(io.StringIO()):
            controller = svc.W300ServiceController(mock_camera=svc.W300MockUsbCamera())
            detected = controller.detect_device()
            info = controller.read_destination_info()
        for report in (detected, info):
            self.assertTrue(report['simulation'])
            self.assertFalse(report['hardware_validated'])

    def test_live_probe_refuses_and_descriptor_parser_is_offline(self):
        import w300_usb_probe as probe
        with patch('ctypes.CDLL', side_effect=AssertionError('USB opened')):
            with self.assertRaisesRegex(RuntimeError, 'unsupported'):
                probe.probe()
            self.assertEqual(probe.parse_config(bytes([9, 2, 9, 0, 0, 1, 0, 128, 50])), [])
            with self.assertRaises(ValueError):
                probe.parse_config(b'')

    def test_truncated_payload_is_rejected(self):
        packet = struct.pack('<IHHBBBB', 100, 0x40, 1, 0, 0, 0, 0) + b'X'
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            svc.SenserWireProtocol().parse_packet(packet)


if __name__ == '__main__':
    unittest.main()
