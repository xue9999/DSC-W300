exec(open(__file__.replace('extract_config.py','inspect_config.py')).read().split('for label,relative')[0])
import struct,hashlib,xml.etree.ElementTree as ET
p=m.Elf('evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/PExtBackup.so')
g=struct.unpack_from('<6I',p.data,p.off(p.sym('PExtBackupGrammar')['value']))
sym=p.data[p.off(g[1]):p.off(g[1])+g[2]]
count=struct.unpack_from('>H',sym)[0];names=sym[2:].split(b'\0');assert len(names)==count+1 and names[-1]==b''
code=p.data[p.off(g[3]):p.off(g[3])+g[4]]
result=dict(scope='G3 static grammar containers and native data table, not W300 addresses',grammar=dict(sha256=p.sha,struct_va=p.sym('PExtBackupGrammar')['value'],symbols_va=g[1],symbols_bytes=g[2],code_va=g[3],code_bytes=g[4]),symbols=[dict(index=i,name=n.decode()) for i,n in enumerate(names[:-1])])
(HERE/'backup-grammar-code.bin').write_bytes(code)
(HERE/'backup-grammar-symbols.bin').write_bytes(sym)
t=m.Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libBackupTable.so')
base=0x2214+8+t.word(0x22a0)+t.word(0x22a4)
result['table_sha256']=t.sha;result['table_base']=base;result['tables']=[]
got=0x2498+8+t.word(0x2508)
count_literals=[0x250c,0x2514,0x2518,0x251c,0x2520,0x2524]
for idx in range(6):
 category=idx//2;variant=idx%2;entry=base+idx*8
 rel=next(r for r in t.reloc if r['offset']==entry)
 assert rel['type']==2 and t.word(entry)==0
 countrel=next(r for r in t.reloc if r['offset']==got+t.word(count_literals[idx]))
 count=t.word(countrel['symbol_value']);array=t.sym(rel['symbol'])
 assert countrel['symbol']==rel['symbol']+'_NUM' and array['size']==count*20
 rows=[]
 for i in range(count):
  row=struct.unpack_from('<5I',t.data,t.off(array['value']+i*20))
  assert row[0]>>24==category
  rows.append(dict(id=row[0],offset=(row[0]>>8)&0xffff,size=row[1],bit_size=row[2],bit_mask=row[3],kind=row[4]))
 result['tables'].append(dict(category=category,variant=variant,descriptor_va=entry,array_symbol=rel['symbol'],array_va=array['value'],count_symbol=countrel['symbol'],rows=rows))
pins={x['path']:x for x in json.loads((ROOT/'evidence/artifact_manifest.json').read_text())['artifacts']}
xmls=[]
for path in sorted((ROOT/'evidence/extracted_g3/archives_unpacked/fskapp1/dsc/app/systemData/RegionInfo').glob('*.xml')):
 relative=path.relative_to(ROOT).as_posix();raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert pins[relative]['sha256']==sha
 doc=ET.fromstring(raw);vals={x.tag.split('}')[-1]:x.text for x in doc.iter() if x.text}
 xmls.append(dict(path=relative,sha256=sha,values=vals))
result['region_xml']=xmls
(HERE/'config-inventory.json').write_text(json.dumps(result,indent=2)+'\n')
print('table base',hex(base),'table sizes',[len(x['rows']) for x in result['tables']]);print('symbols',[(s['index'],s['name']) for s in result['symbols'] if re.search('Lang|region|Destination|signalType',s['name'])])
