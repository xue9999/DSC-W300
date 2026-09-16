#!/usr/bin/env python3
"""Bounded USB transport probe: descriptors and interface claim, no vendor commands.

Does not detach drivers, reset, switch modes, send bulk traffic or write NVM.
Uses the observed OS identity and requires exactly one Sony DSC-W300.
"""
import argparse
import ctypes
import json
from pathlib import Path

from w300_evidence import inventory
from w300_service_tool import SafeLibUsbTransport


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
    report = inventory()
    report['method'] = 'OS identity, libusb standard descriptor reads and bounded interface claim'
    report['vendor_commands_sent'] = False
    report['bulk_commands_sent'] = False
    report['driver_detach_attempted'] = False
    sony = report['sony_devices']
    if len(sony) != 1 or sony[0]['product'] != 'DSC-W300':
        raise RuntimeError('Exactly one OS-identified Sony DSC-W300 required')
    transport = SafeLibUsbTransport()
    claimed = False
    try:
        if not transport.is_available():
            raise RuntimeError('libusb unavailable')
        lib = transport.lib
        lib.libusb_error_name.argtypes = [ctypes.c_int]
        lib.libusb_error_name.restype = ctypes.c_char_p
        if not transport.open_device(0x054c, int(sony[0]['product_id'], 16)):
            report['transport_status'] = 'open_failed'
            return report
        report['handle_opened'] = True

        def descriptor(kind, size):
            buf = (ctypes.c_ubyte * size)()
            count = lib.libusb_control_transfer(transport.handle, 0x80, 6, kind << 8,
                                                0, buf, size, 1500)
            if count < 0:
                raise RuntimeError('GET_DESCRIPTOR: ' + lib.libusb_error_name(count).decode())
            return bytes(buf[:count])

        header = descriptor(2, 9)
        if len(header) != 9:
            raise RuntimeError('Short configuration header')
        size = int.from_bytes(header[2:4], 'little')
        if not 9 <= size <= 4096:
            raise RuntimeError('Configuration exceeds bounded size')
        raw = descriptor(2, size)
        report['configuration_hex'] = raw.hex()
        report['interfaces'] = parse_config(raw)
        if len(report['interfaces']) != 1 or report['interfaces'][0]['number'] != 0:
            raise RuntimeError('Unexpected interface layout; no claim attempted')
        status = lib.libusb_claim_interface(transport.handle, 0)
        claimed = status == 0
        report['claim_result'] = status
        report['claim_result_name'] = lib.libusb_error_name(status).decode()
        report['transport_status'] = 'interface_claimed' if claimed else 'interface_claim_failed'
    except Exception as exc:
        report['transport_status'] = 'probe_error'
        report['error'] = str(exc)
    finally:
        if transport.handle:
            if claimed:
                transport.lib.libusb_release_interface(transport.handle, 0)
            transport.lib.libusb_close(transport.handle)
            transport.handle = ctypes.c_void_p()
        transport.close()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Reserve output before interacting with USB, preserving earlier captures.
    with args.output.open('x') as output:
        result = probe()
        rendered = json.dumps(result, indent=2) + '\n'
        output.write(rendered)
        print(rendered, end='')
