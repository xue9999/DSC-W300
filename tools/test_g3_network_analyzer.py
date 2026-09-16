#!/usr/bin/env python3
"""
tools/test_g3_network_analyzer.py - Offline unit tests for g3_network_analyzer.py.
Validates PCAP parsing and mock gateway helpers using synthetic in-memory packets.
"""
import json
import socket
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Allow importing when run from repository root or tools/ directory
sys.path.insert(0, str(Path(__file__).parent))

from g3_network_analyzer import (
    analyze_pcap,
    parse_dhcp_options,
    parse_dns_query,
    parse_ethernet_ip_udp_tcp,
    PcapReader
)


def create_synthetic_pcap(packets):
    """
    Constructs a valid binary PCAP file from a list of raw packet byte strings.
    """
    # PCAP Global Header: magic (4), v_major (2), v_minor (2), thiszone (4), sigfigs (4), snaplen (4), network (4)
    global_hdr = struct.pack('<IHHiIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)  # LinkType 1 = Ethernet
    body = bytearray(global_hdr)

    for ts_sec, pkt_bytes in packets:
        pkt_hdr = struct.pack('<IIII', ts_sec, 0, len(pkt_bytes), len(pkt_bytes))
        body.extend(pkt_hdr)
        body.extend(pkt_bytes)

    return bytes(body)


def build_ethernet_ipv4_udp(src_ip, dst_ip, src_port, dst_port, udp_payload):
    eth_hdr = b'\x00\x11\x22\x33\x44\x55' + b'\x66\x77\x88\x99\xaa\xbb' + struct.pack('>H', 0x0800)
    total_ip_len = 20 + 8 + len(udp_payload)
    ip_hdr = struct.pack(
        '>BBHHHBBH4s4s',
        0x45, 0, total_ip_len, 1234, 0, 64, 17, 0,
        socket.inet_aton(src_ip), socket.inet_aton(dst_ip)
    )
    udp_hdr = struct.pack('>HHH', src_port, dst_port, 8 + len(udp_payload)) + b'\x00\x00'
    return eth_hdr + ip_hdr + udp_hdr + udp_payload


def build_ethernet_ipv4_tcp(src_ip, dst_ip, src_port, dst_port, tcp_payload):
    eth_hdr = b'\x00\x11\x22\x33\x44\x55' + b'\x66\x77\x88\x99\xaa\xbb' + struct.pack('>H', 0x0800)
    total_ip_len = 20 + 20 + len(tcp_payload)
    ip_hdr = struct.pack(
        '>BBHHHBBH4s4s',
        0x45, 0, total_ip_len, 5678, 0, 64, 6, 0,
        socket.inet_aton(src_ip), socket.inet_aton(dst_ip)
    )
    # TCP header with 20 bytes (data offset = 5)
    tcp_hdr = struct.pack('>HHIIBBHHH', src_port, dst_port, 100, 0, 0x50, 0x18, 65535, 0, 0)
    return eth_hdr + ip_hdr + tcp_hdr + tcp_payload


class NetworkAnalyzerTests(unittest.TestCase):
    def test_parse_dns_query(self):
        # Query for 'g3.sony.net'
        dns_payload = (
            b'\x12\x34'  # ID
            b'\x01\x00'  # Standard query
            b'\x00\x01'  # QDCOUNT = 1
            b'\x00\x00\x00\x00\x00\x00'
            b'\x02g3\x04sony\x03net\x00'  # 2g3 4sony 3net 0
            b'\x00\x01\x00\x01'           # Type A, Class IN
        )
        domains = parse_dns_query(dns_payload)
        self.assertEqual(domains, ['g3.sony.net'])

    def test_parse_dhcp_options(self):
        dhcp_payload = bytearray(240)
        dhcp_payload[0] = 1  # BootRequest
        dhcp_payload[28:34] = b'\x00\x13\xe8\x11\x22\x33'  # Sony MAC
        dhcp_payload[236:240] = b'\x63\x82\x53\x63'         # Magic cookie

        # Add Option 53 (Message Type = 1 Discover)
        dhcp_payload.extend(b'\x35\x01\x01')
        # Add Option 12 (Host Name = 'DSC-G3')
        dhcp_payload.extend(b'\x0c\x06DSC-G3')
        # Add Option 60 (Vendor Class = 'Sony Camera')
        dhcp_payload.extend(b'\x3c\x0bSony Camera')
        # End option
        dhcp_payload.append(255)

        opts = parse_dhcp_options(bytes(dhcp_payload))
        self.assertIsNotNone(opts)
        self.assertEqual(opts['mac'], '00:13:e8:11:22:33')
        self.assertEqual(opts['hostname'], 'DSC-G3')
        self.assertEqual(opts['vendor_class'], 'Sony Camera')
        self.assertEqual(opts['message_type'], 'DISCOVER')

    def test_analyze_pcap_end_to_end(self):
        # 1. DNS Query packet
        dns_payload = b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x06upload\x04sony\x03com\x00\x00\x01\x00\x01'
        pkt1 = build_ethernet_ipv4_udp('192.168.2.15', '192.168.2.1', 45678, 53, dns_payload)

        # 2. SSDP packet
        ssdp_payload = (
            b'M-SEARCH * HTTP/1.1\r\n'
            b'HOST: 239.255.255.250:1900\r\n'
            b'MAN: "ssdp:discover"\r\n'
            b'ST: urn:schemas-upnp-org:device:MediaServer:1\r\n\r\n'
        )
        pkt2 = build_ethernet_ipv4_udp('192.168.2.15', '239.255.255.250', 1900, 1900, ssdp_payload)

        # 3. HTTP GET request packet from NetFront 3.4
        http_payload = (
            b'GET /easyupload HTTP/1.1\r\n'
            b'Host: upload.sony.com\r\n'
            b'User-Agent: Mozilla/4.0 (compatible; NetFront/3.4; Sony Cyber-shot DSC-G3)\r\n\r\n'
        )
        pkt3 = build_ethernet_ipv4_tcp('192.168.2.15', '192.168.2.1', 49152, 80, http_payload)

        pcap_data = create_synthetic_pcap([
            (1700000000, pkt1),
            (1700000001, pkt2),
            (1700000002, pkt3),
        ])

        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tf:
            tf.write(pcap_data)
            tf_path = Path(tf.name)

        try:
            res = analyze_pcap(tf_path)
            self.assertIn('upload.sony.com', res['dns_queried_domains'])
            self.assertEqual(res['ssdp_messages_count'], 1)
            self.assertEqual(res['ssdp_messages'][0]['st'], 'urn:schemas-upnp-org:device:MediaServer:1')

            self.assertEqual(res['http_requests_count'], 1)
            self.assertEqual(res['http_requests'][0]['host'], 'upload.sony.com')
            self.assertIn('NetFront/3.4', res['http_requests'][0]['user_agent'])
        finally:
            tf_path.unlink()

    def test_cli_mac_help_and_parse(self):
        script = Path(__file__).parent / "g3_network_analyzer.py"

        # Test mac-help command
        res_help = subprocess.run([sys.executable, str(script), 'mac-help'], capture_output=True, text=True)
        self.assertEqual(res_help.returncode, 0)
        self.assertIn("macOS Packet Capture Guide", res_help.stdout)

        # Test parse command with synthetic pcap
        with tempfile.TemporaryDirectory() as td:
            pcap_path = Path(td) / "test.pcap"
            pcap_path.write_bytes(create_synthetic_pcap([]))
            out_json = Path(td) / "out.json"

            cmd_parse = [sys.executable, str(script), 'parse', str(pcap_path), '--output', str(out_json)]
            res_parse = subprocess.run(cmd_parse, capture_output=True, text=True)
            self.assertEqual(res_parse.returncode, 0)
            self.assertTrue(out_json.exists())

            data = json.loads(out_json.read_text())
            self.assertEqual(data['dns_queried_domains'], [])


if __name__ == '__main__':
    unittest.main()
