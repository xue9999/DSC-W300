"""Read hash-pinned G3 USB/Senser ELF metadata as data, never load firmware."""
from pathlib import Path
import hashlib, json, re, struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FILES = [
    'evidence/extracted_g3/archives_unpacked/lib/lib/libsencore.so',
    'evidence/extracted_g3/archives_unpacked/lib/lib/libusb.so',
    'evidence/extracted_g3/rootfs/initrd/bin/unified_drv.ko',
    'evidence/extracted_g3/rootfs/initrd/bin/unified_drv2.ko',
]
pins = {r['path']: r for r in json.loads((ROOT/'evidence/artifact_manifest.json').read_text())['artifacts']}
pattern = re.compile(r'usbif|senif|senser|auth|sha1|sha256|vermagic|vendor|extcmd|storage|stillimage', re.I)


def cstr(data, offset):
    end = data.find(b'\0', offset)
    assert end >= 0
    return data[offset:end].decode('ascii', errors='replace')


out = []
for relative in FILES:
    data = (ROOT/relative).read_bytes()
    assert len(data) == pins[relative]['bytes']
    digest = hashlib.sha256(data).hexdigest()
    assert digest == pins[relative]['sha256']
    assert data[:6] == b'\x7fELF\x01\x01'
    h = struct.unpack_from('<HHIIIIIHHHHHH', data, 16)
    assert h[1] == 40 and h[10] == 40
    sections = [struct.unpack_from('<10I', data, h[5]+i*h[10]) for i in range(h[11])]
    ns = sections[h[12]]
    names = data[ns[4]:ns[4]+ns[5]]
    symbols = []
    for s in sections:
        if s[1] not in (2, 11):
            continue
        assert s[9] == 16
        strings = sections[s[6]]
        strs = data[strings[4]:strings[4]+strings[5]]
        for at in range(s[4], s[4]+s[5], s[9]):
            n, value, size, info, other, index = struct.unpack_from('<IIIBBH', data, at)
            if not n:
                continue
            name = cstr(strs, n)
            if not pattern.search(name):
                continue
            item = dict(name=name, value=hex(value), size=size, type=info&15, section_index=index)
            if 0 < index < len(sections):
                target = sections[index]
                item['section'] = cstr(names, target[0])
                if target[1] != 8:
                    address = value & ~1 if info&15 == 2 else value
                    item['file_offset'] = hex(target[4]+address-target[3])
            symbols.append(item)
    strings = [dict(file_offset=hex(m.start()), text=m.group().decode('ascii'))
               for m in re.finditer(rb'[ -~]{6,}', data) if pattern.search(m.group().decode('ascii'))]
    out.append(dict(path=relative, bytes=len(data), sha256=digest, elf_type=h[0],
                    machine=h[1], symbols=symbols, strings=strings))
    print(Path(relative).name, 'ELF type', h[0], 'selected symbols', len(symbols))
    for s in symbols:
        if re.search(r'auth|senif|extcmd', s['name'], re.I):
            print(' ', s.get('file_offset','undefined'), s['size'], s['name'])
    for s in strings:
        if s['text'].startswith('vermagic='):
            print(' ', s['text'])
(HERE/'inventory.json').write_text(json.dumps(out, indent=2)+'\n', encoding='utf-8')
