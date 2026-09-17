"""Frame only retained G3 backup grammar; does not execute it or connect to USB."""
from pathlib import Path
import importlib.util,json,sys
sys.dont_write_bytecode=True
h=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('frame_xs',h.parent/'g3-xs-entry/frame_xs.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
syms=(h/'backup-grammar-symbols.bin').read_bytes()[2:].split(b'\0')[:-1]
r=m.frame((h/'backup-grammar-code.bin').read_bytes(),syms,0)
(h/'backup-grammar-framed.json').write_text(json.dumps(r,indent=2)+'\n')
(h/'backup-grammar-framed.txt').write_text('\n'.join(f"{i['offset']:05x} {i['raw']:24s} {' '.join(i['symbols'])} {i['note']}" for i in r)+'\n')
print('framed',len(r),'instructions',sum(len(bytes.fromhex(i['raw'])) for i in r),'bytes')
