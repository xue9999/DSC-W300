"""Hash-pinned static G3 ELF inspection; never imports or executes firmware."""
from pathlib import Path
import argparse, hashlib, json, re, struct, sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'build/w300/re-tools/site'))
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_REG_PC

def cstr(data, at):
    return data[at:].split(b'\0', 1)[0].decode('ascii', errors='replace')

class Elf:
    def __init__(self, relative, *, pin=None):
        self.relative = relative
        self.data = (ROOT / relative).read_bytes()
        if pin is None:
            pin = next(r for r in json.loads((ROOT/'evidence/artifact_manifest.json').read_text())['artifacts'] if r['path']==relative)
        assert pin['path'] == relative
        self.sha = hashlib.sha256(self.data).hexdigest()
        assert self.sha == pin['sha256'] and len(self.data)==pin['bytes']
        assert self.data[:6] == b'\x7fELF\x01\x01'
        h = struct.unpack_from('<HHIIIIIHHHHHH', self.data, 16)
        assert h[1]==40
        self.type = h[0]
        raw=[struct.unpack_from('<10I', self.data, h[5]+i*h[10]) for i in range(h[11])]
        ns=raw[h[12]]
        names=self.data[ns[4]:ns[4]+ns[5]]
        self.sections=[dict(index=i,name=cstr(names,s[0]),type=s[1],flags=s[2],va=s[3],off=s[4],size=s[5],link=s[6],info=s[7],entsize=s[9]) for i,s in enumerate(raw)]
        self.symbols=[]
        tables={}
        for s in self.sections:
            if s['type'] not in (2,11): continue
            strings=self.sections[s['link']]
            strings=self.data[strings['off']:strings['off']+strings['size']]
            table=[]
            for at in range(s['off'],s['off']+s['size'],s['entsize']):
                n,v,z,info,other,index=struct.unpack_from('<IIIBBH',self.data,at)
                item=dict(name=cstr(strings,n),value=v,size=z,type=info&15,section_index=index)
                if 0<index<len(self.sections):
                    t=self.sections[index]
                    item['section']=t['name']
                    if t['type']!=8: item['file_offset']=t['off']+v-(t['va'] if self.type!=1 else 0)
                table.append(item)
                if n and item not in self.symbols:self.symbols.append(item)
            tables[s['index']]=table
        self.reloc=[]
        for s in self.sections:
            if s['type']!=9: continue
            for at in range(s['off'],s['off']+s['size'],s['entsize']):
                off,inf=struct.unpack_from('<II',self.data,at)
                sym=tables[s['link']][inf>>8]
                self.reloc.append(dict(relocation_section=s['name'],target_section=self.sections[s['info']]['name'] if s['info'] else None,offset=off,type=inf&255,symbol=sym['name'],symbol_value=sym['value'],symbol_section=sym.get('section')))
        self.plt={}
        ps=next((s for s in self.sections if s['name']=='.plt'),None)
        rel=[r for r in self.reloc if r['relocation_section']=='.rel.plt']
        if ps:
            assert ps['size']==20+len(rel)*12
            for i,r in enumerate(rel):
                va=ps['va']+20+i*12
                words=struct.unpack_from('<III',self.data,ps['off']+20+i*12)
                adds=[]
                for word,reg in zip(words[:2],[15,12]):
                    assert word&(1<<25) and (word>>21)&15==4 and (word>>16)&15==reg
                    imm,rot=word&255,((word>>8)&15)*2
                    adds.append(((imm>>rot)|(imm<<(32-rot)))&0xffffffff if rot else imm)
                third=words[2]
                displacement=third&0xfff
                if not third&(1<<23):displacement=-displacement
                assert ((va+8+sum(adds)+displacement)&0xffffffff)==r['offset'] and r['type']==22
                self.plt[va]=r['symbol']
    def sym(self,name): return next(s for s in self.symbols if s['name']==name and 'file_offset' in s)
    def off(self,va):
        assert self.type!=1
        s=next(s for s in self.sections if s['type']!=8 and s['va']<=va<s['va']+s['size'])
        return s['off']+va-s['va']
    def word(self,va): return struct.unpack_from('<I',self.data,self.off(va))[0]
    def decode(self,name):
        if name.startswith('range@'):
            lo,hi=(int(v,0) for v in name[6:].split(':'))
            assert self.type!=1 and hi>lo
            s=dict(value=lo,file_offset=self.off(lo),size=hi-lo,section='.text')
        else:s=self.sym(name)
        va=s['value']; at=s['file_offset']
        md=Cs(CS_ARCH_ARM,CS_MODE_ARM|CS_MODE_LITTLE_ENDIAN);md.detail=True
        lines=[f"{name} section={s['section']} value={va:#x} file={at:#x} symbol_size={s['size']}"]
        for i in md.disasm(self.data[at:at+s['size']],va):
            note=[]
            if i.mnemonic in ('b','bl','blx') and i.op_str.startswith('#0x'):
                target=int(i.op_str[1:],16)
                if target in self.plt:note.append('PLT:'+self.plt[target])
                else:note.extend(t['name'] for t in self.symbols if t['value']==target and t.get('section')==s['section'])
            if i.mnemonic=='ldr' and len(i.operands)==2 and i.operands[1].type==3 and i.operands[1].mem.base==ARM_REG_PC:
                literal=i.address+8+i.operands[1].mem.disp
                try:note.append(f'literal[{literal:#x}]={self.word(literal):#x}')
                except (StopIteration,AssertionError,struct.error):pass
            note.extend(f"RELOC {r['type']} {r['symbol']} value={r['symbol_value']:#x} section={r['symbol_section']}" for r in self.reloc if r['offset']==i.address and (self.type!=1 or r['target_section']==s['section']))
            lines.append(f'{i.address:#010x} {i.bytes.hex():12s} {i.mnemonic:8s} {i.op_str}'+(' ; '+' | '.join(dict.fromkeys(note)) if note else ''))
        return '\n'.join(lines)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',default='evidence/extracted_g3/archives_unpacked/lib/lib/libusb.so')
    ap.add_argument('--select',action='append',default=[])
    ap.add_argument('--prefix',default='libusb')
    args=ap.parse_args()
    e=Elf(args.input)
    if args.select:
        (HERE/(args.prefix+'.asm.txt')).write_text('Static ARM decoding only. Symbol sizes may include trailing literal pools; annotated words are not claimed executed.\n\n'+'\n\n'.join(e.decode(n) for n in args.select)+'\n',encoding='utf-8')
        print(json.dumps(dict(decoded=args.select,output=args.prefix+'.asm.txt')))
    else:
        (HERE/(args.prefix+'-elf.json')).write_text(json.dumps(dict(path=e.relative,sha256=e.sha,elf_type=e.type,sections=e.sections,symbols=e.symbols,relocations=e.reloc),indent=2)+'\n',encoding='utf-8')
        for s in e.symbols:
            if re.search(r'desc|vendor|product|sen|switch|setup|mode|usbif_get|usbid',s['name'],re.I):print(s)
        print('verified_plt',len(e.plt))

if __name__=='__main__':main()
