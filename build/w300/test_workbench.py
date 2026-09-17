"""Host-only boundary tests. No USB calls and no claims of W300 compatibility."""
import copy
import unittest
from legacy_codec import auth_request, auth_response, parse_auth_reply
from w300_workbench import select_w300, parse_inquiry


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {'sony_devices': [{'instance_id': 'USB\\VID_054C&PID_0341\\TESTONLY',
            'description': 'DSC-W300', 'status': 'OK'}]}

    def test_identity_selection(self):
        self.assertEqual(select_w300(self.fixture, 'TESTONLY')['description'], 'DSC-W300')

    def test_identity_refuses_missing_multiple_wrong_serial_and_model(self):
        cases = [({'sony_devices': []}, 'TESTONLY'),
                 ({'sony_devices': self.fixture['sony_devices'] * 2}, 'TESTONLY'),
                 (self.fixture, 'ANOTHER'), (self.fixture, '')]
        for field, value in [('description','DSC-G3'),('status','Error'),('instance_id','USB\\VID_054C&PID_03A8\\TESTONLY')]:
            altered = copy.deepcopy(self.fixture)
            altered['sony_devices'][0][field] = value
            cases.append((altered, 'TESTONLY'))
        for fixture, serial in cases:
            with self.subTest(fixture=fixture,serial=serial), self.assertRaises(ValueError):
                select_w300(fixture, serial)

    def test_real_a330_auth_transcript(self):
        challenge=bytes.fromhex('7ef0f51f86e7bca5309b826db1b7bc8f')
        digest=bytes.fromhex('172f1588efa2c0435e493fb5f7d0b052')
        self.assertEqual(auth_response(challenge),digest)
        reply=bytes.fromhex('0000000700010100ffffffff00000001')+challenge
        self.assertEqual(parse_auth_reply(reply,1),challenge)
        self.assertEqual(auth_request(1)[:16].hex(),'00000003000100000000000000000001')
        self.assertEqual(auth_request(2,challenge)[:32],bytes.fromhex('00000007000100000000000000000002')+digest)
        self.assertEqual(len(auth_request(1)),0x120)

    def test_auth_rejects_malformed_replies(self):
        for data in [b'',bytes(15),bytes(32),bytes.fromhex('ffffffff00010100ffffffff00000001'),
                     bytes.fromhex('0000000700010100ffffffff00000001')+bytes(15),
                     bytes.fromhex('0000000700010af0ffffffff00000001')+bytes(16)]:
            with self.subTest(data=data.hex()),self.assertRaises(ValueError):
                parse_auth_reply(data,1)
        with self.assertRaises(ValueError): auth_response(bytes(15))
        with self.assertRaises(ValueError): auth_request(3)

    def test_inquiry_parser_rejects_short_data(self):
        # Published A330 INQUIRY transcript tests a standard parser only.
        raw=bytes.fromhex('008000011f000000536f6e792020202044534c522d413333302020202020202020312e3030')
        self.assertEqual(parse_inquiry(raw)['product'],'DSLR-A330')
        for length in (0,4,35):
            with self.assertRaises(ValueError): parse_inquiry(raw[:length])
        with self.assertRaises(ValueError): parse_inquiry(raw[:4]+bytes([255])+raw[5:])


if __name__ == '__main__':
    unittest.main()
