"""Static ELF32/ASCII inventory of the eleven retained G3 service libraries.

Reads data as bytes; never loads the libraries or calls firmware functions.
"""
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[3]
LIB = ROOT / 'evidence/extracted_g3/archives_unpacked/lib/lib'
NAMES = ['libsencore.so', 'libsenupdate.so', 'libadj30.so', 'libadj31.so',
         'libadj32.so', 'libadj33.so', 'libadj36.so', 'libadj3E.so',
         'libBackupCore.so', 'libBackupTable.so', 'libAppBackupApi.so']
MATCH = re.compile(r'seus|senser|backup|block|page|address|dest|lang|model|read|command|auth', re.I)

def cstr(buf, offset):
    end = buf.find(b'\0', offset)
    if end < 0:
        raise ValueError('unterminated string')
    return buf[offset:end].decode('ascii', errors='replace')

out = []
for name in NAMES:
    p = LIB / name
    data = p.read_bytes()
    assert data[:6] == b'\x7fELF\x01\x01', (name, 'expected little-endian ELF32')
    hdr = struct.unpack_from('<HHIIIIIHHHHHH', data, 16)
    _, machine, _, _, _, shoff, _, _, _, _, shsize, shnum, shstrndx = hdr
    assert shsize == 40 and shoff + shsize * shnum <= len(data)
    sections = [struct.unpack_from('<IIIIIIIIII', data, shoff + i * shsize) for i in range(shnum)]
    st = sections[shstrndx]
    snames = data[st[4]:st[4]+st[5]]
    symbols = []
    for sec in sections:
        if sec[1] not in (2, 11):
            continue
        assert sec[9] == 16 and sec[4] + sec[5] <= len(data)
        strs = sections[sec[6]]
        buf = data[strs[4]:strs[4]+strs[5]]
        for at in range(sec[4], sec[4]+sec[5], sec[9]):
            n, value, size, info, other, ndx = struct.unpack_from('<IIIBBH', data, at)
            if not n:
                continue
            sym = {'name': cstr(buf, n), 'value': hex(value), 'size': size,
                   'type': info & 15, 'section_index': ndx}
            if 0 < ndx < len(sections):
                s = sections[ndx]
                sym['section'] = cstr(snames, s[0])
                if s[1] != 8:
                    address = value & ~1 if (info & 15) == 2 else value
                    sym['file_offset'] = hex(s[4] + address - s[3])
            symbols.append(sym)
    strings = [{'file_offset': hex(m.start()), 'text': m.group().decode('ascii')}
               for m in re.finditer(rb'[\x20-\x7e]{5,}', data) if MATCH.search(m.group().decode('ascii'))]
    literals = {}
    for term in ('W300', 'DSC-W300', 'USBSENSERKEYOPEN'):
        for encoding in ('ascii', 'utf-16le', 'utf-16be'):
            needle = term.encode(encoding)
            literals[term + ':' + encoding] = [hex(m.start()) for m in re.finditer(re.escape(needle), data)]
    item = {'path': p.relative_to(ROOT).as_posix(), 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'elf_machine': machine, 'literals': literals, 'symbols': symbols, 'relevant_strings': strings}
    out.append(item)
    print(name, 'machine', machine, 'symbols', len(symbols), 'literal_hits', {k:v for k,v in literals.items() if v})
    for s in symbols:
        if MATCH.search(s['name']):
            print(' ', s.get('file_offset', 'undefined'), s['size'], s['name'])
    for s in strings:
        if ' ' in s['text'] or '/' in s['text']:
            print(' STRING', s['file_offset'], s['text'])
dest = Path(__file__).with_name('retained-service-inventory.json')
dest.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
