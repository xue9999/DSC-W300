"""Verified, offline-only DSC-G3 firmware inputs and atomic output publication."""
from pathlib import Path
import os
import tempfile
from g3_firmware_parser import (CXD4108MsCrypter, MANIFEST_SIZE, BLOCK_HEADER_SIZE,
    LHA_PAYLOAD_OFFSET, LHA_PAYLOAD_LENGTH, calculate_sha256, parse_manifest)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'sources/DSCG3V2.exe'
SOURCE_SHA256 = 'a9698c7b3822f23d71de84ba5389453b847f6de19ab293a55ebe016490fd94d9'
EXTRACTED = ROOT / 'evidence/extracted_g3'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def decode_container(data, original=False):
    crypter = CXD4108MsCrypter()
    def block(pos, size):
        hdr = data[pos:pos + BLOCK_HEADER_SIZE]
        payload = data[pos + BLOCK_HEADER_SIZE:pos + BLOCK_HEADER_SIZE + size]
        require(len(hdr) == BLOCK_HEADER_SIZE and len(payload) == size, 'Truncated block')
        require(hdr[20:108] == bytes(88), 'Invalid header padding')
        require(crypter.check_header_hash(hdr), 'Header HMAC mismatch')
        require(crypter.check_data_hash(hdr, payload), 'Payload HMAC mismatch')
        return crypter.cipher(payload)
    manifest = block(0, MANIFEST_SIZE)
    meta = parse_manifest(manifest)
    require(meta['checksum_valid'] and meta['datasize'] == MANIFEST_SIZE - 64, 'Invalid manifest checksum/size')
    sections = meta['sections']
    require(len(sections) == 24, 'Expected 24 sections')
    names = [s['name'] for s in sections]
    require(len(set(names)) == 24, 'Duplicate section names')
    payloads = []
    previous_end = BLOCK_HEADER_SIZE + MANIFEST_SIZE
    for i, sec in enumerate(sections):
        require(int(sec['fnum'], 16) == i, 'Unexpected section order')
        pos = sec['offset'] + (i + 1) * BLOCK_HEADER_SIZE
        require(pos >= previous_end and sec['size'] > 0, 'Overlapping or invalid section')
        require(original or not any(data[previous_end:pos]), 'Unexpected inter-section bytes')
        payloads.append(block(pos, sec['size']))
        previous_end = pos + BLOCK_HEADER_SIZE + sec['size']
    require(original or previous_end == len(data), 'Unexpected trailing bytes')
    return manifest, sections, payloads


class FirmwareBaseline(tuple):
    """Decoded trusted source plus original container framing for exact preservation."""
    def __new__(cls, decoded, container):
        instance = super().__new__(cls, decoded)
        instance.container = container
        return instance


def trusted_source(source=SOURCE):
    raw = Path(source).read_bytes()
    require(calculate_sha256(raw) == SOURCE_SHA256, 'Untrusted DSC-G3 source SHA-256')
    container = raw[LHA_PAYLOAD_OFFSET:LHA_PAYLOAD_OFFSET + LHA_PAYLOAD_LENGTH]
    return FirmwareBaseline(decode_container(container, original=True), container)


def verified_extracted(sections_dir, manifest_path, baseline):
    manifest, sections, payloads = baseline
    require(Path(manifest_path).read_bytes() == manifest, 'Extracted manifest differs from trusted source')
    actual = sorted(p.name for p in Path(sections_dir).iterdir() if p.is_file() and p.name[:2].isdigit())
    expected = [f'{i:02d}_{s["name"]}' for i, s in enumerate(sections)]
    require(actual == expected, 'Extracted section names/order differ from trusted source')
    for name, payload in zip(expected, payloads):
        require((Path(sections_dir) / name).read_bytes() == payload, f'Untrusted extracted section: {name}')


def assemble(manifest, payloads, template=None):
    crypter = CXD4108MsCrypter()
    sections = parse_manifest(manifest)['sections']
    out = bytearray(template or b'')
    end = 0
    for i, payload in enumerate([manifest, *payloads]):
        pos = 0 if i == 0 else sections[i - 1]['offset'] + i * BLOCK_HEADER_SIZE
        require(pos >= end, 'Overlapping output sections')
        if pos > len(out):
            out.extend(bytes(pos - len(out)))
        enc = crypter.cipher(payload)
        hdr = crypter._calc_hash(enc) + bytes(108)
        block = hdr[:-20] + crypter._calc_hash(hdr) + enc
        out[pos:pos + len(block)] = block
        end = pos + len(block)
    return bytes(out)


def check_output(path, source=SOURCE, overwrite=False):
    path = Path(path).resolve()
    require(path != Path(source).resolve(), 'Output must not overwrite source')
    require(not path.is_relative_to((ROOT / 'evidence').resolve()) and not path.is_relative_to((ROOT / 'sources').resolve()),
            'Output must not overwrite preserved source or evidence trees')
    require(overwrite or not path.exists(), 'Output exists; use --overwrite explicitly')
    return path


def publish(data, path, verifier, source=SOURCE, overwrite=False):
    path = check_output(path, source, overwrite)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.g3-', suffix='.dat', dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        verifier(temporary)
        if overwrite:
            os.replace(temporary, path)
        else:
            # Hard-link publication refuses a concurrently created destination.
            os.link(temporary, path)
        return path
    finally:
        temporary.unlink(missing_ok=True)


def verify_expected(path, baseline, expected_manifest, expected_payloads):
    data = Path(path).read_bytes()
    manifest, sections, payloads = decode_container(data, original=True)
    require(manifest == expected_manifest, 'Unexpected manifest changes')
    require([s['name'] for s in sections] == [s['name'] for s in baseline[1]], 'Unexpected section identities')
    for i, (actual, expected) in enumerate(zip(payloads, expected_payloads)):
        require(actual == expected, f'Unexpected payload changes in section {i}')
    # Preserve all bytes outside authenticated blocks, including original padding.
    require(len(data) == len(baseline.container), 'Unexpected container size')
    end = BLOCK_HEADER_SIZE + MANIFEST_SIZE
    for i, section in enumerate(sections):
        pos = section['offset'] + (i + 1) * BLOCK_HEADER_SIZE
        require(data[end:pos] == baseline.container[end:pos], 'Unexpected container padding changes')
        end = pos + BLOCK_HEADER_SIZE + section['size']
    require(data[end:] == baseline.container[end:], 'Unexpected container trailer changes')
    return {'status': 'OFFLINE_INTEGRITY_VERIFIED', 'offline_only': True, 'hardware_validation': 'not_performed',
            'sections_verified': len(sections), 'sha256': calculate_sha256(path),
            'size': Path(path).stat().st_size}
