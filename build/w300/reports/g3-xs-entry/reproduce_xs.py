"""Reproduce bounded XS/native entry evidence, without executing firmware."""
import sys,json,hashlib
sys.dont_write_bytecode=True
from frame_xs import HERE,ROOT,E,parse,branch
from inspect_usb import Elf,cstr
names=['senserModule.xsb','senserCmdTable.xsb','regionInfo.xsb','dsc.xsb']
summary=[]
for name in names:
 r=parse('evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/'+name)
 rows=r['instructions'];bounds={x['offset'] for x in rows}|{r['code_bytes']}
 jumps=[]
 for x in rows:
  if x['opcode'] in (0x28,0x29,0x2a):
   raw=bytes.fromhex(x['raw']);dest=x['offset']+3+int.from_bytes(raw[1:],'big',signed=True)
   assert dest in bounds,(name,x['offset'],dest)
   jumps.append({'source':x['offset'],'target':dest})
 summary.append({k:v for k,v in r.items() if k!='instructions'}|{'framed_instructions':len(rows),'checked_jump_targets':len(jumps)})
 if name=='dsc.xsb':r['instructions']=[x for x in rows if 0x12a800<=x['offset']<=0x12cc80]
 r['output_scope']='Selected ranges for large scripts; full instruction framing and branch alignment checked.'
 (HERE/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
 (HERE/(name+'.txt')).write_text('\n'.join(f"{i['offset']:05x} {i['raw']:24s} {' '.join(i['symbols'])} {i['note']}" for i in r['instructions'])+'\n',encoding='utf-8')
(HERE/'runtime.asm.txt').write_text('\n\n'.join(E.decode(n) for n in ['fxRunLoop','fxRunLoopAccelerator','fxRemapIDs']),encoding='utf-8')
(HERE/'runtime-symbols.json').write_text(json.dumps({'path':E.relative,'sha256':E.sha,'symbols':E.symbols},indent=2))
ranges=['0x91778:0x917c4','0x91e08:0x91e60','0x934a0:0x93604','0x929ac:0x929f4','0x913cc:0x91458','0x91248:0x91274','0x93fa8:0x9401c']
(HERE/'selected-handlers.asm.txt').write_text('\n\n'.join(E.decode('range@'+r) for r in ranges))
p=Elf('evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/PExtSenser.so')
got=0xc624+8+p.word(0xc680)
assert got==0x1b24c
assert p.word(got+0x228)==p.sym('_ZN6Senser9Extension12workerThreadEPv')['value']==0xbf3c
assert cstr(p.data,p.off(got+(p.word(0x112bc)-2**32)))=='senser_normal_mode_start'
assert p.word(0xc3a4)==0xeb0013ae
(HERE/'worker.asm.txt').write_text('\n\n'.join(p.decode(n) for n in ['_ZN6Senser9Extension12workerThreadEPv','_ZN10CoreModule14usb_mode_startER20InitiationDispatcher','_ZN10CoreModule17normal_mode_startER20InitiationDispatcherPFvvE']))
s=Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libsencore.so')
assert s.word(0x6668)==0xe3a02001
(HERE/'normal-start.asm.txt').write_text('\n\n'.join(s.decode(n) for n in ['senser_normal_mode_start','_Z13SenserIfStartR20InitiationDispatcherPFvvE20usb_port_selection_t','_ZN3Usb24initialize_usb_interfaceE20usb_port_selection_t']))
result={'ok':True,'scope':'Static G3 bytecode framing and selected native links only','scripts':summary,'native_inputs':[{'path':e.relative,'sha256':e.sha} for e in [E,p,s]],'w300_qualified':False,'camera_io':False,'firmware_executed':False}
(HERE/'reproduction.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
