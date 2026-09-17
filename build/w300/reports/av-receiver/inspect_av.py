"""Read-only retained G3 AV inventory; firmware bytes are never executed."""
from pathlib import Path
import hashlib
import json
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'build/w300/re-tools/site'))
from g3_firmware_parser import CXD4108MsCrypter, parse_manifest, MANIFEST_SIZE, BLOCK_HEADER_SIZE, LHA_PAYLOAD_OFFSET, LHA_PAYLOAD_LENGTH
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

exe = (ROOT / 'sources/DSCG3V2.exe').read_bytes()
exe_hash = hashlib.sha256(exe).hexdigest()
assert exe_hash == 'a9698c7b3822f23d71de84ba5389453b847f6de19ab293a55ebe016490fd94d9'
container = exe[LHA_PAYLOAD_OFFSET:LHA_PAYLOAD_OFFSET+LHA_PAYLOAD_LENGTH]
assert container == (ROOT / 'sources/D-G3V2.dat').read_bytes()
crypter = CXD4108MsCrypter()
def block(pos, size):
    hdr = container[pos:pos+BLOCK_HEADER_SIZE]
    data = container[pos+BLOCK_HEADER_SIZE:pos+BLOCK_HEADER_SIZE+size]
    assert len(data) == size and hdr[20:108] == bytes(88)
    assert crypter.check_header_hash(hdr) and crypter.check_data_hash(hdr, data)
    return crypter.cipher(data)
manifest_bytes = block(0, MANIFEST_SIZE)
manifest = parse_manifest(manifest_bytes)
assert manifest['checksum_valid'] and len(manifest['sections']) == 24
recorded = json.loads((ROOT / 'evidence/extracted_g3/manifest.json').read_text())
inventory = {'source':'sources/DSCG3V2.exe', 'sha256':exe_hash,
             'dat_is_exact_exe_slice':True, 'manifest_hmac_and_checksum':True, 'sections':[]}
arm = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
thumb = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
assembly = ['Static decoding of retained G3 AV candidates only. Display addresses are file offsets unless explicitly stated.']
for index in [0, 3, 8, 9, 19, 20]:
    sec = manifest['sections'][index]
    name = f'{index:02d}_{sec["name"]}'
    data = block(sec['offset']+(index+1)*BLOCK_HEADER_SIZE, sec['size'])
    disk = (ROOT / 'evidence/extracted_g3/sections' / name).read_bytes()
    assert data == disk
    digest = hashlib.sha256(data).hexdigest()
    assert digest == recorded['sections'][index]['decrypted_sha256']
    strings = [(m.start(),m.group().decode('ascii')) for m in re.finditer(rb'[ -~]{6,}',data)]
    selected = [{'file_offset':hex(at), 'text':s} for at,s in strings
                if re.search(r'seus|senser|ipcm|avcon|ITRON|HI7700|dispatch|copyright|SA2U_APP',s,re.I)]
    models = {}
    for term in [b'DSC-W300', b'W300', b'DSC-G3', b'G3', b'08210030']:
        for encoding in ['ascii','utf-16le','utf-16be']:
            needle=term.decode().encode(encoding)
            offsets=[m.start() for m in re.finditer(re.escape(needle),data)]
            models[term.decode()+'/'+encoding] = [hex(x) for x in offsets]
    item = {'index':index, 'name':name, 'source_manifest':sec, 'size':len(data), 'sha256':digest,
            'hmac_verified':True, 'equals_preserved_section':True, 'first_64_hex':data[:64].hex(),
            'selected_ascii_strings':selected, 'literal_model_hits':models}
    if index in [3,9]:
        item['vector_pointer_words_le']=[hex(x) for x in struct.unpack_from('<7I',data,0x20)]
        assembly.append('\n'+name+' first 32 bytes ARM vectors, then reset-entry candidate file+0x3C (local inference to inspect).')
        # Stop before the reset literal pool; do not label data as ARM instructions.
        for start,size in [(0,32),(0x3c,(0xf0 if index==3 else 0xf4)-0x3c)]:
            for ins in arm.disasm(data[start:start+size],start):
                assembly.append(f'file+0x{ins.address:08x} {ins.bytes.hex():12s} {ins.mnemonic:9s} {ins.op_str}')
    inventory['sections'].append(item)
(HERE/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n',encoding='utf-8')
(HERE/'vectors-and-reset.asm.txt').write_text('\n'.join(assembly)+'\n',encoding='utf-8')
print(json.dumps({'sections':len(inventory['sections']), 'source_hash':exe_hash, 'output':str(HERE)},indent=2))
