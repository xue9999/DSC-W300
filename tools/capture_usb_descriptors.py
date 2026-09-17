"""Capture enumerated USB descriptors without claiming interfaces or sending vendor commands."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import usb.core
import usb.util
import libusb_package


def fields(obj, names):
    return {name: getattr(obj, name) for name in names.split()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to overwrite capture')
    devices = list(usb.core.find(find_all=True, idVendor=0x054c, idProduct=0x0341,
                                backend=libusb_package.get_libusb1_backend()))
    if len(devices) != 1:
        raise SystemExit('Expected exactly one 054c:0341; no device opened')
    dev = devices[0]
    result = {'captured_at_utc': datetime.now(timezone.utc).isoformat(),
              'method': 'libusb Windows enumeration descriptors and standard string reads; no claim/reset/configuration/vendor command',
              'identity_scope': 'VID/PID and bus/port; compare Windows PnP serial separately if string read fails',
              'device': fields(dev, 'bLength bDescriptorType bcdUSB bDeviceClass bDeviceSubClass bDeviceProtocol bMaxPacketSize0 idVendor idProduct bcdDevice iManufacturer iProduct iSerialNumber bNumConfigurations bus address port_numbers speed'),
              'configurations': [], 'strings': {}}
    for cfg in dev:
        c = fields(cfg, 'bLength bDescriptorType wTotalLength bNumInterfaces bConfigurationValue iConfiguration bmAttributes bMaxPower')
        c['extra_descriptors_hex'] = bytes(cfg.extra_descriptors).hex()
        c['interfaces'] = []
        for interface in cfg:
            i = fields(interface, 'bLength bDescriptorType bInterfaceNumber bAlternateSetting bNumEndpoints bInterfaceClass bInterfaceSubClass bInterfaceProtocol iInterface')
            i['extra_descriptors_hex'] = bytes(interface.extra_descriptors).hex()
            i['endpoints'] = []
            for ep in interface:
                e = fields(ep, 'bLength bDescriptorType bEndpointAddress bmAttributes wMaxPacketSize bInterval')
                e['extra_descriptors_hex'] = bytes(ep.extra_descriptors).hex()
                i['endpoints'].append(e)
            c['interfaces'].append(i)
        result['configurations'].append(c)
    for name in ('iManufacturer', 'iProduct', 'iSerialNumber'):
        try:
            result['strings'][name] = {'ok': True, 'value': usb.util.get_string(dev, getattr(dev, name))}
        except Exception as exc:
            result['strings'][name] = {'ok': False, 'error_type': type(exc).__name__, 'error': str(exc)}
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
