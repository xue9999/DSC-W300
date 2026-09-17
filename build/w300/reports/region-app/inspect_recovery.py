"""Reproduce pinned native file-layout and recovery anchors; no camera access."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE.parent/'g3-usb-descriptor'))
from inspect_usb import Elf


def main():
    sources=[('G3','evidence/extracted_g3/archives_unpacked/lib/lib/libBackupCore.so',None),
             ('T100','build/w300/downloads/related-firmware/t100-extracted/archives_unpacked/lib/lib/libBackupCore.so',
              json.loads((HERE.parent/'t100-language-comparison/extraction.json').read_text())['artifacts'])]
    texts=[]; records=[]; helpers={}
    for model,path,pins in sources:
        pin=next(p for p in pins if p['path']==path) if pins else None
        elf=Elf(path,pin=pin)
        records.append(dict(model=model,path=path,sha256=elf.sha))
        texts.append(model+' '+path+'\nSHA256 '+elf.sha)
        for fragment in ('getHeaderSize','getDataOffset','checkFlushFlg','writeUser','writeSafely'):
            selected=[s for s in elf.symbols if fragment in s['name'] and 'file_offset' in s]
            if not selected: raise ValueError('Missing function '+fragment)
            for symbol in selected:
                texts.append(elf.decode(symbol['name']))
                if fragment in ('getHeaderSize','getDataOffset'):
                    helpers[model,fragment]=elf.data[symbol['file_offset']:symbol['file_offset']+symbol['size']]
    for name in ('getHeaderSize','getDataOffset'):
        if helpers['G3',name]!=helpers['T100',name]: raise ValueError('Layout helper comparison changed')
    (HERE/'recovery-native.txt').write_text('\n\n'.join(texts)+'\n',encoding='utf-8')
    (HERE/'recovery-inputs.json').write_text(json.dumps(dict(inputs=records,layout_helpers_byte_identical=True,
          scope='Static T100/G3 comparison; W300 recovery untested'),indent=2)+'\n',encoding='utf-8')
    print('Reproduced pinned recovery disassembly and helper equality')


if __name__=='__main__': main()
