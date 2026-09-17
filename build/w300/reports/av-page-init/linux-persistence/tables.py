from pathlib import Path
import struct,json,hashlib
ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
inv=json.loads((ROOT/'build/w300/reports/retained-service-inventory.json').read_text())
lines=[]
for fn in ['libAppBackupApi.so','libBackupCore.so']:
 item=next(x for x in inv if x['path'].endswith('/'+fn)); b=(ROOT/item['path']).read_bytes(); assert hashlib.sha256(b).hexdigest()==item['sha256']
 h=struct.unpack_from('<HHIIIIIHHHHHH',b,16); sec=[struct.unpack_from('<IIIIIIIIII',b,h[5]+i*h[10]) for i in range(h[11])]
 ns=sec[h[12]]; names=b[ns[4]:ns[4]+ns[5]]; named={names[z[0]:].split(b'\0')[0].decode():z for z in sec}
 def off(va): return next((z[4]+va-z[3] for z in sec if z[1]!=8 and z[3]<=va<z[3]+z[5]),None)
 def u(va):
  o=off(va); return struct.unpack_from('<I',b,o)[0] if o is not None else None
 rels={}
 for r in [z for z in sec if z[1]==9]:
  sy=sec[r[6]]; st=sec[sy[6]]; strings=b[st[4]:st[4]+st[5]]
  for at in range(r[4],r[4]+r[5],r[9]):
   va,info=struct.unpack_from('<II',b,at); ss=struct.unpack_from('<IIIBBH',b,sy[4]+(info>>8)*sy[9]); name=strings[ss[0]:].split(b'\0')[0].decode(); rels[va]=(info&255,name,ss[1])
 lines.append(fn+' sha256='+item['sha256'])
 if fn=='libAppBackupApi.so':
  for va,size,label in [(0x51e4,24,'AV command -> BackupEvent'),(0x51b4,24,'AV category -> CommonMethod category')]:
   lines.append(label+' @'+hex(va)); lines.extend('  '+repr(struct.unpack_from('<II',b,off(va)+i)) for i in range(0,size,8))
 else:
  for sym in [s for s in item['symbols'] if s['name'] in ['_ZN12FileAccesser9FILE_NAMEE','_ZN28FileAccesserMeasures2BattOff15SPARE_FILE_NAMEE','_ZTV28FileAccesserMeasures2BattOff','_ZTV30ShadowAccesserMeasures2BattOff','_ZTV11BasicMethod','_ZTV12CommonMethod','_ZTV13CategoryTable','_ZTV11ShadowTable']]:
   va=int(sym['value'],16); lines.append(sym['name']+' @'+hex(va))
   for i in range(0,sym['size'],4):
    value=u(va+i); desc=rels.get(va+i); st=''
    if 'NAME' in sym['name'] and value:
     o=off(value); st=repr(b[o:o+80].split(b'\0')[0]) if o is not None else ''
    lines.append('  +0x%x raw=%s relocation=%s %s'%(i,hex(value) if value is not None else 'BSS',desc,st))
  for va,size in [(0x16458,32),(0x16478,32),(0x16498,32),(0x16908,32)]:
   lines.append('Shadow table @'+hex(va)+' '+repr([(hex(u(va+i)) if u(va+i) is not None else 'BSS', rels.get(va+i)) for i in range(0,size,4)]))
(OUT/'linux-backup-tables.txt').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
