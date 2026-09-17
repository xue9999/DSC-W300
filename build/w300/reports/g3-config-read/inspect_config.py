from pathlib import Path
import sys, json, importlib.util, re
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
spec=importlib.util.spec_from_file_location('elf_static', HERE.parent/'g3-usb-descriptor/inspect_usb.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
for label,relative in [('table','evidence/extracted_g3/archives_unpacked/lib/lib/libBackupTable.so'),('extension','evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/PExtBackup.so')]:
 e=m.Elf(relative)
 (HERE/(label+'-elf.json')).write_text(json.dumps(dict(path=relative,sha256=e.sha,sections=e.sections,symbols=e.symbols,relocations=e.reloc),indent=2)+'\n')
 print(label)
 for s in e.symbols:
  if re.search('get|read|dest|lang|region|table|backup',s['name'],re.I): print(s)
 print('strings',[(hex(x.start()),x.group().decode('ascii')) for x in re.finditer(rb'[ -~]{5,}',e.data) if re.search(b'region|lang|dest|backup|Get',x.group(),re.I)])
