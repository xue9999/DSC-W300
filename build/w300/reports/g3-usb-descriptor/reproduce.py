"""Offline reproduction of bounded G3 USB descriptor analysis. No device APIs."""
from pathlib import Path
import json, subprocess, sys
from inspect_usb import Elf, HERE

groups = {
    'libusb-chain.asm.txt': (
        'evidence/extracted_g3/archives_unpacked/lib/lib/libusb.so',
        [('usbif_initialize',0x5b70,0x5e44),('USB API start wrapper',0x6314,0x648c),
         ('CUsbSvc::start',0x9554,0x95f8),('CUsbSvc::createGadget',0x9f94,0xa360),
         ('usbproduct_conv_did',0xfe38,0xfec0),('CUsbGadgetSen::on_create',0xcd70,0xce60),
         ('CUsbGadgetSen::proc_kevent',0xcec0,0xcf30)]),
    'libsencore-chain.asm.txt': (
        'evidence/extracted_g3/archives_unpacked/lib/lib/libsencore.so',
        [('Usb::handle_input',0x83bc,0x86b0),
         ('Usb::initialize_usb_interface',0x8978,0x8b04)]),
}
for filename,(relative,ranges) in groups.items():
    e=Elf(relative)
    lines=['Static G3 ARM ELF decoding only; no firmware execution. Bounded code ends before trailing literal pools.',
           f'Input {relative}; SHA256 {e.sha}; verified PLT stubs {len(e.plt)}']
    for label,lo,hi in ranges:
        lines.append('\n'+label+'\n'+e.decode(f'range@{lo:#x}:{hi:#x}'))
    (HERE/filename).write_text('\n'.join(lines)+'\n',encoding='utf-8')
for script in ['kernel-inspect.py','kernel-decode.py','verify_descriptor.py']:
    subprocess.run([sys.executable,str(HERE/script)],check=True)
print(json.dumps(dict(ok=True,scope='G3 descriptor/request chain, offline static only',decoded_library_ranges=sum(len(r[1]) for r in groups.values()))))
