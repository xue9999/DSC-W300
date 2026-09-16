"""Regression checks for host-only preflight; no hardware access in tests."""
import contextlib
import io
import struct
import unittest
from unittest.mock import patch

import w300_service_tool as svc


class LiveBoundaryTests(unittest.TestCase):
    def test_dry_run_cannot_initialize_usb(self):
        with patch.object(svc, 'SafeLibUsbTransport', side_effect=AssertionError('USB opened')):
            with contextlib.redirect_stdout(io.StringIO()):
                controller = svc.W300ServiceController(dry_run=True)
                self.assertTrue(controller.run_full_cycle())
            self.assertIsNone(controller.transport)
            self.assertEqual(controller.mock_camera.flash_store[svc.Cee8Payload.PROP_DESTINATION], b'J1\0\0')

    def test_every_live_service_cli_command_rejected_before_usb(self):
        for command in ('read', 'unlock', 'write-cee8', 'commit', 'reset', 'full-cycle'):
            with self.subTest(command=command), patch.object(svc, 'SafeLibUsbTransport', side_effect=AssertionError('USB opened')):
                with patch('sys.argv', ['tool', command]), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(svc.main(), 2)

    def test_passive_detection_accepts_observed_descriptor(self):
        observed = {'sony_devices': [{'product': 'DSC-W300', 'product_id': '0341'}]}
        with patch('w300_evidence.inventory', return_value=observed), patch.object(svc, 'SafeLibUsbTransport', side_effect=AssertionError('USB opened')):
            with patch('sys.argv', ['tool', 'detect']), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(svc.main(), 0)

    def test_truncated_payload_is_rejected(self):
        packet = struct.pack('<IHHBBBB', 100, 0x40, 1, 0, 0, 0, 0) + b'X'
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            svc.SenserWireProtocol().parse_packet(packet)


if __name__ == '__main__':
    unittest.main()
