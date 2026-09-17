"""Reproduce pinned T100 standalone service transport anchors; no camera access."""
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE.parent/'g3-usb-descriptor'))
from inspect_usb import Elf
source='build/w300/downloads/related-firmware/t100-extracted/archives_unpacked/bin/bin/sen'
pins=json.loads((HERE.parent/'t100-language-comparison/extraction.json').read_text())['artifacts']
e=Elf(source,pin=next(row for row in pins if row['path']==source))
lines=[f'Source: {source}',f'SHA256: {e.sha}',f'Bytes: {len(e.data)}']
for name in ('SenserThread','AdjustCheckFunc','HostCommunication','FileControl'):
    lines.append(str(e.decode(name)))
for name in ('pFunc_level_A','AdjustCommunication','AdjustCont_Host','AdjustCont_Lib_Host'):
    s=e.sym(name)
    lines.append(f"{name} VA={s['value']:#x} bytes="+e.data[s['file_offset']:s['file_offset']+s['size']].hex())
for address in (0x1B940,0x1B9B4,0x1BA10):
    lines.append(json.dumps([r for r in e.reloc if r['offset']==address]))
(HERE/'t100-transport-native.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(e.sha,len(e.data))
