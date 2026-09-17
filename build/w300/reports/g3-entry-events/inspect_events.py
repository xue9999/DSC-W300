"""Bounded retained G3 event-path inspection; firmware is data only."""
from pathlib import Path
import json,struct,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.dont_write_bytecode=True
sys.path.insert(0,str(HERE.parent/'g3-usb-descriptor'))
from inspect_usb import Elf
e=Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libusb.so')
lines=['Static G3 libusb.so '+e.sha]
if len(sys.argv)==1:
 for key in ['usb_senif_user_ops','usb_senif_pub']:
  s=e.sym(key);lines.append(repr(s))
  for va in range(s['value'],s['value']+s['size'],4):
   lines.append('%x=%x %s'%(va,e.word(va),[r for r in e.reloc if r['offset']==va]))
 for s in e.symbols:
  if any(x in s['name'] for x in ['CUsbGadgetSen','usb_event','senif']):lines.append(repr(s))
elif sys.argv[1]=='--data':
 for arg in sys.argv[2:]:
  lo,hi=(int(v,16)for v in arg.split(':'))
  for va in range(lo,hi,4):lines.append('%x=%x %s'%(va,e.word(va),[r for r in e.reloc if r['offset']==va]))
else:
 for arg in sys.argv[1:]:lines.append(e.decode(arg))
print('\n'.join(lines))
