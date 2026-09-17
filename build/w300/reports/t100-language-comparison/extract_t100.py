"""Acquire and statically extract the pinned Sony T100 updater; never execute it."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from g3_firmware_parser import G3FirmwareParser, SafeTarExtractor

URL = 'https://di.update.sony.net/DSC/DSCT100V2.exe'
SHA256 = 'e5ecfbeef87a5708536f51b6d2479bffde58394d71c2752337382716d9e72d67'
SIZE = 15978538
DOWNLOADS = ROOT / 'build/w300/downloads/related-firmware'


def record(path):
    data = path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def carve(data):
    if len(data) != SIZE or hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('Input is not the pinned Sony T100 updater')
    header = data.index(b'-lh0-') - 2
    size = struct.unpack_from('<H', data, header)[0]
    packed, unpacked = struct.unpack_from('<II', data, header + 7)
    if (header != 0x6c00 or size != 0x49 or packed != unpacked
            or data[header + 20] != 2
            or b'D-T100V2.dat' not in data[header:header + size]
            or header + size + packed != len(data) - 1 or data[-1] != 0):
        raise ValueError('Unexpected LHA layout')
    payload = data[header + size:header + size + packed]
    # LHA member CRC-16/ARC. HMAC checks below independently cover its contents.
    crc = 0
    table = []
    for value in range(256):
        for _ in range(8):
            value = (value >> 1) ^ (0xa001 if value & 1 else 0)
        table.append(value)
    for value in payload:
        crc = (crc >> 8) ^ table[(crc ^ value) & 255]
    if crc != struct.unpack_from('<H', data, header + 21)[0]:
        raise ValueError('LHA member CRC mismatch')
    return payload, dict(header_offset=header, payload_offset=header + size,
                         payload_bytes=packed, member_crc16=hex(crc))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--acquire', action='store_true', help='Download missing pinned input with TLS verification')
    args = ap.parse_args()
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    source = DOWNLOADS / 'DSCT100V2.exe'
    if not source.exists():
        if not args.acquire:
            raise SystemExit('Missing updater; rerun with --acquire')
        with urllib.request.urlopen(URL, timeout=30) as response:
            data = response.read(SIZE + 1)
        carve(data)  # Verify before retaining the downloaded file.
        source.write_bytes(data)
    payload, lha = carve(source.read_bytes())
    container = DOWNLOADS / 'D-T100V2.dat'
    if container.exists() and container.read_bytes() != payload:
        raise ValueError('Refusing to replace a different carved container')
    container.write_bytes(payload)
    parser = G3FirmwareParser(container)
    header = parser.verify_container_header()
    _, manifest = parser.read_manifest()
    if not manifest['checksum_valid'] or manifest['total_sections'] != 18:
        raise ValueError('Unexpected T100 manifest')
    # Validate paths and bounds before passing section names to the shared parser.
    for i, section in enumerate(manifest['sections']):
        name = section['name']
        if '/' in name or '\\' in name or ':' in name or name in ('.', '..'):
            raise ValueError('Invalid section name')
        if section['offset'] + (i + 2) * 128 + section['size'] > len(payload):
            raise ValueError('Section exceeds the verified container')
    output = DOWNLOADS / 't100-extracted'
    sections = parser.extract_sections(output, dump_container=False)
    archives = []
    for section in sections:
        if section['name'].endswith('.tar'):
            members = SafeTarExtractor.extract(output / 'sections' / section['file_name'],
                                               output / 'archives_unpacked' / section['name'][:-4])
            archives.append(dict(name=section['name'], members=len(members)))
    files = [record(p) for p in sorted((output / 'archives_unpacked').rglob('*')) if p.is_file()]
    result = dict(source_url=URL, source=record(source), container=record(container),
                  lha=lha, container_verification=header, manifest=manifest,
                  sections=sections, archives=archives, artifacts=files,
                  firmware_executed=False, camera_accessed=False, w300_qualified=False)
    (HERE / 'extraction.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(ok=True, sections=len(sections), files=len(files),
                          source_sha256=SHA256, w300_qualified=False)))


if __name__ == '__main__':
    main()
