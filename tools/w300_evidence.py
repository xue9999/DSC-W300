#!/usr/bin/env python3
"""Passive macOS USB inventory and offline file comparison. No camera commands."""
import argparse
import hashlib
import json
import platform
import plistlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def usb_records(tree):
    records = []
    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get('idVendor'), int) and isinstance(node.get('idProduct'), int):
                records.append({
                    'vendor_id': f"{node['idVendor']:04x}",
                    'product_id': f"{node['idProduct']:04x}",
                    'product': node.get('USB Product Name'),
                    'manufacturer': node.get('USB Vendor Name'),
                    'serial': node.get('USB Serial Number'),
                    'location_id': node.get('locationID'),
                })
            for child in node.get('IORegistryEntryChildren', []):
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
    walk(tree)
    return records


def inventory():
    if platform.system() != 'Darwin':
        raise ValueError('inventory uses macOS ioreg; compare works on other hosts')
    try:
        result = subprocess.run(['/usr/sbin/ioreg', '-a', '-c', 'IOUSBHostDevice'],
                                check=True, capture_output=True, timeout=20)
        devices = usb_records(plistlib.loads(result.stdout))
    except Exception:
        devices = []
    if not devices:
        result = subprocess.run(['/usr/sbin/ioreg', '-a', '-p', 'IOUSB'],
                                check=True, capture_output=True, timeout=20)
        devices = usb_records(plistlib.loads(result.stdout))
    sony = [d for d in devices if d['vendor_id'] == '054c']
    return {'captured_at': datetime.now(timezone.utc).isoformat(),
            'host': {'os': platform.system(), 'version': platform.mac_ver()[0],
                     'architecture': platform.machine()},
            'method': 'OS registry only; no device handle or vendor commands',
            'usb_device_count': len(devices), 'sony_devices': sony,
            'camera_identity_verified': False, 'destination': None,
            'camera_write_performed': False,
            'status': 'sony_device_present_identity_unverified' if sony else 'no_sony_usb_device'}


def compare(a, b):
    a, b = Path(a), Path(b)
    lengths = (a.stat().st_size, b.stat().st_size)
    different = 0
    first_offsets = []
    offset = 0
    with a.open('rb') as fa, b.open('rb') as fb:
        while True:
            ba, bb = fa.read(1024 * 1024), fb.read(1024 * 1024)
            if not ba and not bb:
                break
            for i in range(max(len(ba), len(bb))):
                if i >= len(ba) or i >= len(bb) or ba[i] != bb[i]:
                    different += 1
                    if len(first_offsets) < 128:
                        first_offsets.append(offset + i)
            offset += max(len(ba), len(bb))
    return {'files': [{'path': str(p.resolve()), 'size': n, 'sha256': digest(p)}
                      for p, n in zip((a, b), lengths)],
            'identical': different == 0, 'different_byte_positions': different,
            'first_different_offsets': first_offsets,
            'offsets_truncated': different > len(first_offsets),
            'coverage': 'unknown; byte equality does not establish backup coverage or restorability',
            'camera_write_performed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inv = sub.add_parser('inventory')
    inv.add_argument('--output', type=Path)
    cmp = sub.add_parser('compare')
    cmp.add_argument('a', type=Path)
    cmp.add_argument('b', type=Path)
    cmp.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        data = inventory() if args.command == 'inventory' else compare(args.a, args.b)
        rendered = json.dumps(data, indent=2) + '\n'
        if args.output:
            # Exclusive creation preserves previous evidence; never overwrite a backup.
            with args.output.open('x') as f:
                f.write(rendered)
        print(rendered, end='')
    except (OSError, ValueError, subprocess.SubprocessError, plistlib.InvalidFileException) as exc:
        parser.exit(2, f'Error: {exc}\n')
    if args.command == 'compare' and not data['identical']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
