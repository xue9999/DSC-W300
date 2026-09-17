"""Reproduce only static, hash-pinned G3 configuration findings."""
from pathlib import Path
import subprocess,sys,json,hashlib
sys.dont_write_bytecode=True
h=Path(__file__).resolve().parent
root=h.parents[3]
for name in ['inspect_config.py','decode_config.py','extract_config.py','frame_grammar.py']:
 p=subprocess.run([sys.executable,'-B',str(h/name)],cwd=root,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stdout+p.stderr)
facts=json.loads((h/'config-inventory.json').read_text());frames=json.loads((h/'backup-grammar-framed.json').read_text())
expected=[(69,0x10400),(78,0x40000),(79,0x40400),(80,0x40800),(81,0x40c00)]
selected=[]
for sym,id in expected:
 matches=[(j,i) for j,i in enumerate(frames) if i['opcode']==0x7c and i['symbols'][0].startswith(str(sym)+':')]
 assert len(matches)==1
 j,i=matches[0];seq=frames[j-6:j+1]
 assert [x['opcode'] for x in seq]==[0x6a,0x89,0x6d,0x42,0x2e,0x6c,0x7c]
 text=bytes.fromhex(seq[0]['raw'])[1:-1].decode();assert int(text,0)==id
 assert seq[3]['symbols']==['43:__xs__number'] and seq[4]['symbols']==['44:parse']
 tbl,row=next((t,r) for t in facts['tables'] for r in t['rows'] if r['id']==id)
 selected.append(dict(symbol=i['symbols'][0],id_hex=hex(id),literal_code_offset=seq[0]['offset'],property_code_offset=i['offset'],array=tbl['array_symbol'],row=row))
sys.path.insert(0,str(h.parent/'g3-usb-descriptor'));from inspect_usb import Elf,cstr
e=Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libBackupCore.so')
paths=[]
for n in ['_ZN12FileAccesser9FILE_NAMEE','_ZN28FileAccesserMeasures2BattOff15SPARE_FILE_NAMEE']:
 va=e.sym(n)['value'];assert next(r for r in e.reloc if r['offset']==va)['type']==23
 paths.append(cstr(e.data,e.off(e.word(va))))
assert paths==['/boot/factory/Hreg.bin','/boot/factory/Hreg2.bak']
result=dict(ok=True,scope='Static native getter and XS framing; property semantic qualification recorded separately',selected=selected,category=0,category_files=paths,no_usb=True,no_firmware_execution=True,w300_qualified=False)
(h/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(ok=True,configuration_rows=len(selected),native_category=0,source_model='DSC-G3',w300_qualified=False)))
