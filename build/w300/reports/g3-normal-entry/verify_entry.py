"""Verify selected G3 native entry links; static bytes only, no firmware/USB imports."""
from pathlib import Path
import ast, hashlib, json, struct, sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'g3-usb-descriptor'))
from inspect_usb import Elf, ROOT, cstr

pext = Elf('evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/PExtSenser.so')
core = Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libsencore.so')
usb = Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libusb.so')
sen = Elf('evidence/extracted_g3/archives_unpacked/bin/bin/sen')
usbx = Elf('evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/usbExt.so')

def word(e, va, expected):
    assert e.word(va) == expected, (e.relative, hex(va), hex(e.word(va)), hex(expected))

def reloc(e, va, kind, name=None):
    found = [r for r in e.reloc if r['offset'] == va and r['type'] == kind and (name is None or r['symbol'] == name)]
    assert len(found) == 1, (e.relative, hex(va), kind, name)
    return found[0]

def relative_pointer(e, va, expected):
    word(e, va, expected)
    reloc(e, va, 23)

def branch(e, va, expected, link=True):
    w = e.word(va)
    assert (w >> 24) & 15 == (11 if link else 10), (hex(va), hex(w))
    delta = w & 0xffffff
    if delta & 0x800000: delta -= 0x1000000
    assert va + 8 + delta * 4 == expected, (hex(va), hex(expected))

# ELF constructor table -> initializer -> actual global Extension vptr.
ctors = next(s for s in pext.sections if s['name'] == '.ctors')
assert struct.unpack_from('<4I', pext.data, ctors['off']) == (0xffffffff, 0x9098, 0xd200, 0)
reloc(pext, ctors['va'] + 8, 23)
branch(pext, 0xd218, 0xcd54)
base = (0xcd70 + pext.word(0xcfac)) & 0xffffffff
assert base == 0x1b24c
instance = base + pext.word(0xcfbc)
assert instance == 0x1c688
vtable_got = base + pext.word(0xcfc4)
relative_pointer(pext, vtable_got, 0x1c560)
for va, value in [(0xcdec, 0xe79a3003), (0xcdf0, 0xe2833008), (0xcdf4, 0xe78a3002)]: word(pext, va, value)
vptr = pext.word(vtable_got) + 8
assert vptr == 0x1c568
relative_pointer(pext, vptr + 0x18, 0xbbb4)
assert pext.sym('_ZNK6Senser9Extension12getProductIdEv')['value'] == 0xbbb4
word(pext, 0xbbc0, 0xe3a00000)
relative_pointer(pext, vptr + 0x14, 0xbaa4)

# Ready(mode == 0) sets up the USB Senif callback table, not an MSC opcode claim.
relative_pointer(pext, base + 0x274, 0xd2cc)
relative_pointer(pext, base + 0x210, 0x1c540)
for va in [0x1c540, 0x1c544]: relative_pointer(pext, va, 0xb504)
word(pext, 0xd2e0, 0xe3a00001)
branch(pext, 0xd2f4, 0xec74)
relative_pointer(pext, base + 0x348, 0x1c5f4)
reloc(pext, 0x1c5f8, 2, 'usb_senif_pub')
pub = usb.sym('usb_senif_pub')['value']
assert pub == 0x18bf8
assert reloc(usb, pub, 2, 'usb_senif_init')['symbol_value'] == 0xdc60
word(usb, 0xdc78, 0xe581200c)  # save supplied callbacks at Senif + 0xc

# Event 1 uses the initialized global object as NinCooperator.
assert (0xb520 + pext.word(0xb72c)) & 0xffffffff == base
assert base + pext.word(0xb740) == instance
word(pext, 0xb564, 0xe3530001)
branch(pext, 0xb568, 0xb578, False)
word(pext, 0xb604, 0xe2820050)
word(pext, 0xb610, 0xe51b1070)
branch(pext, 0xb614, 0x111a0)
assert (0x111c0 + pext.word(0x11204)) & 0xffffffff == base
library_va = (base + pext.word(0x11188)) & 0xffffffff
thread_va = (base + pext.word(0x11208)) & 0xffffffff
assert cstr(pext.data, pext.off(library_va)) == 'libsencore.so'
assert cstr(pext.data, pext.off(thread_va)) == 'NinThread'
branch(pext, 0x111c8, 0x1115c)
branch(pext, 0x111e0, 0xeff0)
word(pext, 0x111c4, 0xe1a05001)
word(pext, 0x111f0, 0xe1a02005)
branch(pext, 0x111f8, 0xed50)

# The product selector uses virtual +0x18 and selects xxstep for value != 1.
word(core, 0x79b0, 0xe593c018)
word(core, 0x79c0, 0xe3500001)
branch(core, 0x79c4, 0x79dc, False)
assert core.plt[0x6224] == 'xxstep'
branch(core, 0x79e8, 0x6224)
assert core.plt[0x6218] == 'shimashima'
branch(core, 0x11c00, 0x6218)
# shimashima sends four bytes to the same input routine used by shimashima2.
word(core, 0x11af0, 0xe3a02004)
branch(core, 0x11af4, 0x11698)
branch(core, 0x11b0c, 0x11770)
word(core, 0x11b30, 0xe3500013)  # copy 20 digest bytes, indexes 0..19

# Native completion goes to a supplied status callback, then an XS call.
word(pext, 0xbb20, 0xe5923008)
word(pext, 0xbb28, 0xe5933008)
word(pext, 0xbb3c, 0xe3a01000)
assert pext.plt[0x74e8] == 'FskThreadPostCallback'
branch(pext, 0xb170, 0x74e8)
relative_pointer(pext, base + 0x2e8, 0xb184)
relative_pointer(pext, base + 0x1d0, 0xb208)
assert cstr(pext.data, pext.off((base + pext.word(0xb2f4)) & 0xffffffff)) == 'call'
assert pext.plt[0x76ec] == 'fxCallID'
branch(pext, 0xb2c8, 0x76ec)

# Named USB wrapper takes its DID from XS argument 0, not a hard-coded service DID.
assert usbx.plt[0x139c] == 'fxToInteger'
branch(usbx, 0x2988, 0x139c)
word(usbx, 0x29f0, 0xe1a01002)
word(usbx, 0x29fc, 0xe593c00c)
# Standalone /bin/sen only enters usb_mode_start when GetSenserMode != 0.
branch(sen, 0x9dbc, 0xc13c)
word(sen, 0x9dc0, 0xe3500000)
word(sen, 0x9dc4, 0x089dac10)
branch(sen, 0x9dd4, 0xce14)

pmca = ROOT / 'build/w300/upstream/Sony-PMCA-RE/pmca/usb/sony.py'
pmca_sha = hashlib.sha256(pmca.read_bytes()).hexdigest()
assert pmca_sha == '53ffb4d9d49cb5146623fda2b66ecb137681a6fc9ab0c98d23a51e75128af97e'
tree = ast.parse(pmca.read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SonySenserAuthDevice')
auth = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'authenticate')
selection = next(n.value for n in ast.walk(auth) if isinstance(n, ast.Assign) and isinstance(n.value, ast.IfExp) and any(isinstance(t, ast.Name) and t.id == 'data' for t in n.targets))
assert isinstance(selection.test, ast.Compare) and selection.test.comparators[0].value == 0x0336
assert isinstance(selection.orelse, ast.Subscript) and isinstance(selection.orelse.slice, ast.Slice)
assert selection.orelse.value.id == 'data' and selection.orelse.slice.lower is None and selection.orelse.slice.upper.value == 4

# Selected additional ranges, retaining code and literal-pool caveat explicitly.
groups = {
    'native-links.asm.txt': (pext, [
        'range@0xd200:0xd220', 'range@0xcd54:0xcff0',
        '_ZN14StatusCallback22onSenserStatusCallbackEN6Senser6status4typeE',
        '_ZN14StatusCallback8CallbackEPvS0_S0_S0_', 'range@0xb208:0xb2f8',
        'range@0xb9b4:0xba44', 'senif_init']),
    'core-normal-auth.asm.txt': (core, ['range@0x7888:0x7b70', 'xxstep', 'shimashima']),
    'usb-registration.asm.txt': (usb, ['usb_senif_init']),
}
for filename, (e, selections) in groups.items():
    text = ['Static retained G3 ARM only; symbol/range listings may include trailing literal pools, which are not claimed executed.', e.relative, e.sha]
    text.extend(e.decode(name) for name in selections)
    (HERE / filename).write_text('\n\n'.join(text) + '\n', encoding='utf-8')

out = {
    'scope': 'Static retained G3 native cooperator and first-stage hash-length evidence; no complete normal-MSC entry or W300 proof',
    'input_manifest_pins_verified': {e.relative: e.sha for e in [pext, core, usb, sen, usbx]},
    'pmca_commit': 'a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0',
    'pmca_sony_py_sha256': pmca_sha,
    'extension': {'constructor': '0xd200', 'initializer': '0xcd54', 'instance_va': hex(instance),
                  'vptr_va': hex(vptr), 'get_product_vslot': '0x18', 'get_product_function': '0xbbb4', 'get_product_value': 0,
                  'event_handler': '0xb504', 'start_event': 1, 'nin_start_call': '0xb614'},
    'dynamic_thread': {'library': 'libsencore.so', 'library_string_va': hex(library_va), 'symbol': 'NinThread', 'symbol_string_va': hex(thread_va), 'cooperator_passed_as_thread_argument': True},
    'registration': {'senif_type_argument': 1, 'callback_table': '0x1c540', 'senif_pub_import': 'usb_senif_pub', 'usb_senif_init': '0xdc60', 'upstream_kernel_event_to_callback_full_path_traced': False},
    'hash_branch': {'nin_thread_product_id_condition': 'value != 1', 'step': 'xxstep', 'hash_wrapper': 'shimashima', 'input_bytes': 4, 'digest_bytes': 20, 'same_length_as_pmca_non_0336_branch': True, 'sha_compression_executed_or_fully_proven_here': False},
    'completion_boundary': {'callback': 'StatusCallback::onSenserStatusCallback', 'posting_api': 'FskThreadPostCallback', 'xs_call_api': 'fxCallID', 'xs_property_name': 'call', 'script_target_and_order_resolved': False},
    'normal_msc_to_senser_transition_proven': False,
    'live_authentication_tested': False, 'firmware_executed': False, 'usb_commands_sent': False, 'w300_compatibility_proven': False,
}
(HERE / 'entry-evidence.json').write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'ok': True, 'G3_Extension_product_id': 0, 'selected_hash_input_bytes': 4, 'full_entry_transition_proven': False, 'W300_compatibility_proven': False}))
