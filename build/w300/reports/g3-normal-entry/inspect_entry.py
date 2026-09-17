"""Bounded read-only G3 normal USB entry inspection. Firmware is never executed."""
from pathlib import Path
import json,re,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'g3-usb-descriptor'))
from inspect_usb import Elf,ROOT
FILES=[
 'evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/USBGMsc.so',
 'evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/PExtSenser.so',
 'evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/usbExt.so',
 'evidence/extracted_g3/archives_unpacked/bin/bin/sen',
]
all_records=[]
for relative in FILES:
 e=Elf(relative)
 strings=[dict(file_offset=hex(m.start()),text=m.group().decode()) for m in re.finditer(rb'[ -~]{6,}',e.data) if re.search(rb'senser|auth|usb|senif|sha1|xsb|/bin/|normal',m.group(),re.I)]
 record=dict(path=relative,sha256=e.sha,elf_type=e.type,symbols=e.symbols,relocations=e.reloc,strings=strings)
 all_records.append(record)
 print('\n'+Path(relative).name)
 print('symbols',len(e.symbols),'relocations',len(e.reloc),'selected strings',len(strings),'sha256',e.sha)
(HERE/'entry-inventory.json').write_text(json.dumps(all_records,indent=2)+'\n',encoding='utf-8')
