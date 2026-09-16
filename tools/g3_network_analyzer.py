#!/usr/bin/env python3
"""
tools/g3_network_analyzer.py - Mac-oriented network analysis & mock service harness for Sony DSC-G3.
Parses standard PCAP capture files to extract DSC-G3 DHCP/DNS/SSDP/HTTP signatures,
and runs an isolated local HTTP diagnostic server for NetFront interoperability.
Pure standard library: zero external dependencies.
"""
import argparse
import datetime
import http.server
import json
import socket
import struct
import sys
from pathlib import Path

# PCAP Magic numbers
PCAP_MAGIC_LE = 0xa1b2c3d4
PCAP_MAGIC_BE = 0xd4c3b2a1
PCAP_MAGIC_NS_LE = 0xa1b23c4d
PCAP_MAGIC_NS_BE = 0x4d3cb2a1


class PcapReader:
    """Minimal, self-contained PCAP file parser supporting standard Ethernet/IPv4 captures."""
    def __init__(self, file_path):
        self.path = Path(file_path)
        if not self.path.exists():
            raise FileNotFoundError(f"PCAP file not found: {self.path}")

    def packets(self):
        with open(self.path, 'rb') as f:
            global_header = f.read(24)
            if len(global_header) < 24:
                raise ValueError("Truncated PCAP global header")

            magic = struct.unpack('<I', global_header[:4])[0]
            if magic in (PCAP_MAGIC_LE, PCAP_MAGIC_NS_LE):
                endian = '<'
            elif magic in (PCAP_MAGIC_BE, PCAP_MAGIC_NS_BE):
                endian = '>'
            else:
                raise ValueError(f"Unsupported PCAP magic: {magic:#x}")

            link_type = struct.unpack(endian + 'I', global_header[20:24])[0]
            if link_type != 1:  # LINKTYPE_ETHERNET
                raise ValueError(f"Unsupported link type {link_type} (only Ethernet is supported)")

            pkt_header_fmt = endian + 'IIII'
            pkt_header_size = struct.calcsize(pkt_header_fmt)

            packet_index = 0
            while True:
                hdr_bytes = f.read(pkt_header_size)
                if not hdr_bytes:
                    break
                if len(hdr_bytes) < pkt_header_size:
                    break
                ts_sec, ts_usec, incl_len, orig_len = struct.unpack(pkt_header_fmt, hdr_bytes)
                pkt_data = f.read(incl_len)
                if len(pkt_data) < incl_len:
                    break
                yield {
                    'index': packet_index,
                    'ts': ts_sec + (ts_usec / 1e6),
                    'len': incl_len,
                    'data': pkt_data
                }
                packet_index += 1


def parse_ethernet_ip_udp_tcp(packet_bytes):
    """Parses Ethernet -> IPv4 -> TCP/UDP layers from raw packet bytes."""
    if len(packet_bytes) < 14:
        return None
    eth_type = struct.unpack('>H', packet_bytes[12:14])[0]
    if eth_type != 0x0800:  # IPv4 only
        return None

    ip_bytes = packet_bytes[14:]
    if len(ip_bytes) < 20:
        return None
    version_ihl = ip_bytes[0]
    ihl = (version_ihl & 0x0F) * 4
    protocol = ip_bytes[9]
    src_ip = socket.inet_ntoa(ip_bytes[12:16])
    dst_ip = socket.inet_ntoa(ip_bytes[16:20])

    payload = ip_bytes[ihl:]
    if protocol == 17:  # UDP
        if len(payload) < 8:
            return None
        src_port, dst_port, udp_len = struct.unpack('>HHH', payload[:6])
        return {
            'protocol': 'UDP',
            'src_ip': src_ip,
            'dst_ip': dst_ip,
            'src_port': src_port,
            'dst_port': dst_port,
            'data': payload[8:udp_len]
        }
    elif protocol == 6:  # TCP
        if len(payload) < 20:
            return None
        src_port, dst_port = struct.unpack('>HH', payload[:4])
        data_offset = ((payload[12] >> 4) & 0x0F) * 4
        return {
            'protocol': 'TCP',
            'src_ip': src_ip,
            'dst_ip': dst_ip,
            'src_port': src_port,
            'dst_port': dst_port,
            'data': payload[data_offset:]
        }
    return None


def parse_dns_query(data):
    """Extracts queried domain names from a DNS request payload."""
    if len(data) < 12:
        return None
    flags = struct.unpack('>H', data[2:4])[0]
    is_response = bool(flags & 0x8000)
    qdcount = struct.unpack('>H', data[4:6])[0]
    if is_response or qdcount == 0:
        return None

    idx = 12
    domains = []
    for _ in range(qdcount):
        labels = []
        while idx < len(data):
            length = data[idx]
            if length == 0:
                idx += 1
                break
            if length >= 192:  # DNS compression pointer
                idx += 2
                break
            idx += 1
            if idx + length > len(data):
                break
            labels.append(data[idx:idx+length].decode('ascii', errors='replace'))
            idx += length
        if labels:
            domains.append(".".join(labels))
        idx += 4  # skip QTYPE and QCLASS
    return domains if domains else None


def parse_dhcp_options(data):
    """Extracts DHCP Option 12 (Hostname) and Option 60 (Vendor Class) from BOOTP/DHCP."""
    if len(data) < 240:
        return None
    op = data[0]
    if op != 1:  # BootRequest
        return None

    chaddr = data[28:34]
    mac_str = ":".join(f"{b:02x}" for b in chaddr)
    magic_cookie = data[236:240]
    if magic_cookie != b'\x63\x82\x53\x63':
        return None

    options = {'mac': mac_str}
    idx = 240
    while idx < len(data):
        opt = data[idx]
        if opt == 255:  # End
            break
        if opt == 0:    # Pad
            idx += 1
            continue
        if idx + 1 >= len(data):
            break
        opt_len = data[idx + 1]
        opt_val = data[idx + 2 : idx + 2 + opt_len]
        idx += 2 + opt_len

        if opt == 12:  # Hostname
            options['hostname'] = opt_val.decode('utf-8', errors='replace')
        elif opt == 60:  # Vendor Class Identifier
            options['vendor_class'] = opt_val.decode('utf-8', errors='replace')
        elif opt == 53 and opt_len == 1:  # DHCP Message Type
            msg_types = {1: 'DISCOVER', 2: 'OFFER', 3: 'REQUEST', 8: 'INFORM'}
            options['message_type'] = msg_types.get(opt_val[0], f"TYPE_{opt_val[0]}")
    return options


def analyze_pcap(pcap_path):
    """Scans a PCAP file and produces a structured inventory of observed Sony camera traffic."""
    reader = PcapReader(pcap_path)
    dns_queries = set()
    dhcp_records = []
    ssdp_messages = []
    http_requests = []

    for pkt in reader.packets():
        parsed = parse_ethernet_ip_udp_tcp(pkt['data'])
        if not parsed:
            continue

        # DHCP
        if parsed['protocol'] == 'UDP' and (parsed['src_port'] == 68 or parsed['dst_port'] == 67):
            dhcp = parse_dhcp_options(parsed['data'])
            if dhcp and dhcp not in dhcp_records:
                dhcp_records.append(dhcp)

        # DNS
        elif parsed['protocol'] == 'UDP' and parsed['dst_port'] == 53:
            domains = parse_dns_query(parsed['data'])
            if domains:
                dns_queries.update(domains)

        # SSDP / UPnP
        elif parsed['protocol'] == 'UDP' and (parsed['dst_port'] == 1900 or parsed['src_port'] == 1900):
            try:
                text = parsed['data'].decode('utf-8', errors='ignore')
                first_line = text.split('\r\n')[0] if '\r\n' in text else text[:60]
                if 'M-SEARCH' in first_line or 'NOTIFY' in first_line or '200 OK' in first_line:
                    headers = dict(line.split(':', 1) for line in text.split('\r\n') if ':' in line)
                    ssdp_messages.append({
                        'ts': pkt['ts'],
                        'src': f"{parsed['src_ip']}:{parsed['src_port']}",
                        'line': first_line.strip(),
                        'st': headers.get('ST', '').strip(),
                        'location': headers.get('LOCATION', '').strip(),
                        'server': headers.get('SERVER', '').strip()
                    })
            except Exception:
                pass

        # HTTP
        elif parsed['protocol'] == 'TCP' and parsed['dst_port'] in (80, 8080, 50000, 52235):
            try:
                text = parsed['data'].decode('utf-8', errors='ignore')
                if text.startswith(('GET ', 'POST ', 'HEAD ')):
                    lines = text.split('\r\n')
                    req_line = lines[0]
                    headers = dict(l.split(':', 1) for l in lines[1:] if ':' in l)
                    http_requests.append({
                        'ts': pkt['ts'],
                        'src_ip': parsed['src_ip'],
                        'dst_ip': parsed['dst_ip'],
                        'dst_port': parsed['dst_port'],
                        'request': req_line,
                        'host': headers.get('Host', '').strip(),
                        'user_agent': headers.get('User-Agent', '').strip()
                    })
            except Exception:
                pass

    return {
        'pcap_file': str(Path(pcap_path).resolve()),
        'analyzed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'dhcp_records': dhcp_records,
        'dns_queried_domains': sorted(list(dns_queries)),
        'ssdp_messages_count': len(ssdp_messages),
        'ssdp_messages': ssdp_messages[:50],  # Bounded to prevent overwhelming outputs
        'http_requests_count': len(http_requests),
        'http_requests': http_requests
    }


class DiagnosticHTTPHandler(http.server.BaseHTTPRequestHandler):
    """Mock HTTP service simulating an endpoint for NetFront browser inspection."""
    def log_message(self, format, *args):
        # Override to format cleanly to stdout
        sys.stdout.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {self.client_address[0]} - {format % args}\n")

    def do_GET(self):
        print(f"[+] HTTP GET: {self.path}")
        print(f"    User-Agent: {self.headers.get('User-Agent', 'None')}")
        print(f"    Accept: {self.headers.get('Accept', 'None')}")

        html = """<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <title>Sony DSC-G3 Lab Interop Gateway</title>
</head>
<body bgcolor="#FFFFFF" text="#000000">
  <table width="100%" border="0" cellpadding="4">
    <tr bgcolor="#003366">
      <td><font color="#FFFFFF" size="+1"><b>Sony DSC-G3 Laboratory Interoperability Gateway</b></font></td>
    </tr>
  </table>
  <p><b>Status:</b> Local Mock Gateway Active (Preservation / Interop Mode)</p>
  <hr>
  <p><b>Detected Client Parameters:</b></p>
  <ul>
    <li><b>Remote IP:</b> """ + self.client_address[0] + """</li>
    <li><b>User-Agent:</b> """ + (self.headers.get('User-Agent') or 'Unknown') + """</li>
  </ul>
  <hr>
  <form action="/test-upload" method="post" enctype="multipart/form-data">
    <p><b>File Upload Test:</b></p>
    <input type="file" name="upload_file"><br><br>
    <input type="submit" value="Upload to Local Lab">
  </form>
</body>
</html>"""
        encoded = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_len) if content_len > 0 else b''
        print(f"[+] HTTP POST: {self.path} ({len(post_data)} bytes received)")

        resp = b"OK - Received by Local Lab Gateway\n"
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(resp)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(resp)


def run_mock_server(host, port):
    server = http.server.HTTPServer((host, port), DiagnosticHTTPHandler)
    print(f"[+] DSC-G3 Lab Mock Gateway listening on http://{host}:{port}/")
    print("[+] Press Ctrl+C to terminate server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[+] Server terminated cleanly.")
    finally:
        server.server_close()


def print_mac_capture_help():
    print("""
=== macOS Packet Capture Guide for Sony Cyber-shot DSC-G3 ===

1. List available network interfaces:
   $ networksetup -listallhardwareports

   (Typically 'en0' is built-in Wi-Fi on MacBooks, or 'en1'/'en2' on desktop Macs/adapters).

2. Capture all traffic to a PCAP file:
   $ sudo tcpdump -i en0 -s 0 -n -w dsc_g3_traffic.pcap

3. Filter specifically for camera IP (once assigned, e.g. 192.168.2.15):
   $ sudo tcpdump -i en0 -s 0 -n host 192.168.2.15 -w dsc_g3_filtered.pcap

4. Inspect the capture using this tool:
   $ python3 tools/g3_network_analyzer.py parse dsc_g3_traffic.pcap --output evidence/network-summary.json
""")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    # Help command
    sub.add_parser('mac-help', help='Show macOS Wi-Fi capture commands and guide')

    # Parse command
    parse_parser = sub.add_parser('parse', help='Analyze PCAP capture file for camera activity')
    parse_parser.add_argument('pcap', type=Path, help='Path to .pcap capture file')
    parse_parser.add_argument('--output', type=Path, help='Optional JSON output path')

    # Mock server command
    server_parser = sub.add_parser('mock-server', help='Run mock diagnostic HTTP server')
    server_parser.add_argument('--host', default='0.0.0.0', help='Host to bind (default: 0.0.0.0)')
    server_parser.add_argument('--port', type=int, default=8080, help='Port to bind (default: 8080)')

    args = parser.parse_args()

    if args.command == 'mac-help':
        print_mac_capture_help()
    elif args.command == 'parse':
        try:
            result = analyze_pcap(args.pcap)
            rendered = json.dumps(result, indent=2)
            if args.output:
                if args.output.exists():
                    raise FileExistsError(f"Output file {args.output} already exists.")
                args.output.write_text(rendered + '\n', encoding='utf-8')
                print(f"[+] Analysis saved to {args.output}")
            else:
                print(rendered)
        except Exception as e:
            print(f"[-] Error: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.command == 'mock-server':
        run_mock_server(args.host, args.port)


if __name__ == '__main__':
    main()
