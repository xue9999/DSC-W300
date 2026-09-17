exec(open(__file__.replace('inspect_grammar.py','inspect_config.py')).read().split('for label,relative')[0])
import struct
p=m.Elf('evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/PExtBackup.so')
for s in p.sections: print(s)
print('grammar',p.data[p.off(55772):p.off(55772)+24].hex(' '))
for va in struct.unpack_from('<6I',p.data,p.off(55772)):
 try: print(hex(va),p.data[p.off(va):p.off(va)+96].hex(' '))
 except:pass
print('magic positions',[(v,p.data.find(v)) for v in [b'XS11',b'SYMB',b'CODE']])
t=m.Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libBackupTable.so')
(HERE/'table-internal.asm.txt').write_text(t.decode('range@0x21f0:0x22a8')+'\n')
