#!/usr/bin/env python3
"""Offline USB descriptor parser. Live probing is explicitly unsupported."""
import argparse
import json
from pathlib import Path



def parse_config(raw):
    if len(raw) < 9 or raw[1] != 2:
        raise ValueError('Missing configuration descriptor')
    total = int.from_bytes(raw[2:4], 'little')
    if len(raw) != total:
        raise ValueError('Incomplete configuration descriptor')
    interfaces = []
    offset = 0
    while offset < total:
        length, kind = raw[offset:offset + 2]
        if length < 2 or offset + length > total:
            raise ValueError('Invalid USB descriptor length')
        d = raw[offset:offset + length]
        if kind == 4:
            if length < 9:
                raise ValueError('Short interface descriptor')
            interfaces.append(dict(number=d[2], alternate=d[3], usb_class=d[5],
                                   subclass=d[6], protocol=d[7], endpoints=[]))
        elif kind == 5 and interfaces:
            if length < 7:
                raise ValueError('Short endpoint descriptor')
            interfaces[-1]['endpoints'].append(dict(address=f'0x{d[2]:02x}',
                attributes=d[3], max_packet_size=int.from_bytes(d[4:6], 'little')))
        offset += length
    return interfaces


def probe():
    """Live probing is unsupported; retained descriptor parser works offline."""
    raise RuntimeError(
        'Live USB probing is unsupported in this offline research tool. '
        'Use w300_evidence.py inventory for passive macOS OS inventory.'
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = probe()  # Refuse before creating output or touching any device.
    with args.output.open('x') as output:
        rendered = json.dumps(result, indent=2) + '\n'
        output.write(rendered)
        print(rendered, end='')
