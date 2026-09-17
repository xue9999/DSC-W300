"""Independent bounded reconstruction from raw ext2 metadata; no firmware execution.

Does not import recover_module.py or the repository ext2 parser.
Writes only its own JSON review; never writes the recovered module.
"""
from pathlib import Path
import hashlib,json,struct
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'evidence/artifact_manifest.json').read_text())['artifacts']
pins={i['path']:i for i in manifest}
image_path='evidence/extracted_g3/archives_unpacked/linuxset1/initrd.img'
old_path='evidence/extracted_g3/rootfs/initrd/bin/unified_drv.ko'
def pinned(path):
 data=(ROOT/path).read_bytes();p=pins[path]
 assert len(data)==p['bytes'] and hashlib.sha256(data).hexdigest()==p['sha256']
 return data
image=pinned(image_path);old=pinned(old_path)
def u16(at):return struct.unpack_from('<H',image,at)[0]
def u32(at):return struct.unpack_from('<I',image,at)[0]
assert u16(1024+56)==0xef53
block_size=1024<<u32(1024+24)
blocks_count=u32(1024+4);inodes_count=u32(1024)
first_data=u32(1024+20);inodes_per_group=u32(1024+40)
revision=u32(1024+76);inode_size=u16(1024+88) if revision else 128
assert block_size==1024 and inode_size==128
group_descriptors=(first_data+1)*block_size
def block(number):
 assert 0<number<blocks_count and (number+1)*block_size<=len(image)
 return image[number*block_size:(number+1)*block_size]
def inode(number):
 assert 1<=number<=inodes_count
 group,index=divmod(number-1,inodes_per_group)
 table=u32(group_descriptors+group*32+8)
 at=table*block_size+index*inode_size
 assert at+inode_size<=len(image)
 return {'number':number,'offset':at,'table_block':table,'mode':u16(at),'size':u32(at+4),
         'sectors_512':u32(at+28),'roots':list(struct.unpack_from('<15I',image,at+40))}
def child(parent,name):
 item=inode(parent);assert item['mode']&0o170000==0o040000
 count=(item['size']+block_size-1)//block_size;assert count<=12
 content=b''.join(block(i) for i in item['roots'][:count])[:item['size']]
 entries=[];at=0
 while at<len(content):
  number,length,nlen,kind=struct.unpack_from('<IHBB',content,at)
  assert length>=8 and length%4==0 and at+length<=len(content) and nlen<=length-8
  label=content[at+8:at+8+nlen].decode('ascii')
  if number and label==name:entries.append(number)
  at+=length
 assert len(entries)==1,(name,entries)
 return entries[0]
bin_inode=child(2,'bin');module_inode=child(bin_inode,'unified_drv.ko')
assert module_inode==14
item=inode(module_inode)
assert item['mode']&0o170000==0o100000 and item['size']==303816
roots=item['roots'];per_block=block_size//4
single=list(struct.unpack('<256I',block(roots[12])))
double_roots=list(struct.unpack('<256I',block(roots[13])))
count=(item['size']+block_size-1)//block_size
assert count==297 and count>12+per_block and count<=12+per_block+per_block**2
need=count-12-per_block
assert need==29
double_data=[];used_indirect=[roots[12],roots[13]]
for index in range((need+per_block-1)//per_block):
 ptr=double_roots[index];used_indirect.append(ptr)
 double_data.extend(struct.unpack('<256I',block(ptr)))
data_blocks=roots[:12]+single+double_data[:need]
assert len(data_blocks)==count and all(data_blocks)
assert len(set(data_blocks+used_indirect))==len(data_blocks)+len(used_indirect)
assert item['sectors_512']==(len(data_blocks)+len(used_indirect))*(block_size//512)
raw=b''.join(block(number) for number in data_blocks)
full=raw[:item['size']]
assert len(full)==303816 and len(old)==274432
assert full[:len(old)]==old and full[len(old):]==raw[(12+256)*1024:item['size']]
sha=hashlib.sha256(full).hexdigest()
assert sha=='8d675f7071e49a75a174130ef8525767af07c157fe5f203018eb097e10aa1367'
recovered=(HERE/'unified_drv.complete.ko').read_bytes()
assert full==recovered
# Independent structural ELF check of recovered bytes, without loading the module.
assert full[:6]==b'\x7fELF\x01\x01'
eh=struct.unpack_from('<HHIIIIIHHHHHH',full,16)
assert eh[0]==1 and eh[1]==40 and eh[10]==40
assert eh[5]+eh[10]*eh[11]<=len(full)
sections=[struct.unpack_from('<10I',full,eh[5]+i*eh[10])for i in range(eh[11])]
for s in sections:
 if s[1]!=8:assert s[4]+s[5]<=len(full)
relocations=0
for s in sections:
 if s[1]!=9:continue
 assert s[9]==8 and s[5]%8==0 and s[6]<len(sections) and s[7]<len(sections)
 sym=sections[s[6]];target=sections[s[7]]
 assert sym[1] in (2,11) and sym[9]==16 and sym[5]%16==0
 for at in range(s[4],s[4]+s[5],8):
  destination,info=struct.unpack_from('<II',full,at)
  assert info>>8<sym[5]//16 and destination<target[5]
  relocations+=1
assert relocations==9102
result={'ok':True,'method':'Independent raw ext2 metadata and explicit direct/single/double traversal; no parser import',
 'image':{'path':image_path,'sha256':hashlib.sha256(image).hexdigest()},'bin_inode':bin_inode,'module_inode':item,
 'block_size':block_size,'inode_size':inode_size,'group_descriptors_byte_offset':group_descriptors,
 'data_block_count':count,'single_indirect_block':roots[12],'double_indirect_block':roots[13],
 'double_indirect_second_level_blocks':used_indirect[2:],'double_indirect_data_blocks':data_blocks[268:],
 'metadata_block_count':len(used_indirect),'i_blocks_accounting_matches':True,
 'all_used_blocks_nonzero_and_unique':True,'last_block_used_bytes':item['size']%block_size,
 'omitted_tail_bytes':len(full)-len(old),'preserved_prefix_equal':True,'recovered_file_exactly_equal':True,
 'full_size':len(full),'sha256':sha,'elf_sections':len(sections),'elf_relocations':relocations,
 'all_elf_sections_with_file_contents_in_bounds':True,'all_relocation_symbol_indices_and_targets_in_bounds':True,
 'synthetic_zero_fill_used':False,'firmware_executed':False,'w300_evidence':False}
(HERE/'independent-review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k]for k in ['ok','data_block_count','metadata_block_count','omitted_tail_bytes','full_size','sha256','elf_relocations','synthetic_zero_fill_used']},indent=2))
