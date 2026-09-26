"""ARM helper binary generator for Sony DSC-W300 DSP/AV firmware extraction.

Assembles standalone static ARM ELF executables with zero host toolchain dependencies.
Generates:
1. Test payload (verifies ELF execution by writing a canary log file to /usr/test_exec.log)
2. Full extraction payload (mounts /dev/nflasha5 to /tmp/m, dumps av.bin and sa.bin to /usr,
   with raw partition fallback if mount fails, logs progress to /usr/dump.log).
"""

from __future__ import annotations

from pathlib import Path
import struct
from typing import Any, Dict, List, Optional, Tuple, Union

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    import capstone
    HAVE_CAPSTONE = True
except ImportError:
    HAVE_CAPSTONE = False


ELF_MAGIC = b'\x7fELF'
ELF_IDENT_GENERIC = b'\x7fELF\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
ET_EXEC = 2
EM_ARM = 0x28
EV_CURRENT = 1
EF_ARM = 0x206


class ArmHelperAssembler:
    """Two-pass ARMv5 assembler producing position-independent static ELF or patched binary code."""

    def __init__(self, base_va: Optional[int] = None, code_va: Optional[int] = None):
        if code_va is not None:
            self.code_va = code_va
            self.base_va = base_va if base_va is not None else code_va
        elif base_va is not None:
            if base_va == 0x89e0:
                self.code_va = 0x89e0
                self.base_va = 0x89e0
            else:
                self.base_va = base_va
                self.code_va = base_va + 0x80  # 128-byte aligned header
        else:
            # Default to W300 ud_datcnv entry point 0x89e0
            self.code_va = 0x89e0
            self.base_va = 0x89e0
        self.items: List[Tuple[Any, ...]] = []
        self.labels: Dict[str, int] = {}
        self.pool_entries: List[Tuple[str, Union[str, int]]] = []

    def label(self, name: str) -> None:
        self.items.append(('label', name))

    def mov(self, rd: int, imm: int) -> None:
        self.items.append(('mov', rd, imm))

    def mov_reg(self, rd: int, rm: int) -> None:
        self.items.append(('mov_reg', rd, rm))

    def mvn(self, rd: int, imm: int) -> None:
        self.items.append(('mvn', rd, imm))

    def sub(self, rd: int, rn: int, imm: int) -> None:
        self.items.append(('sub', rd, rn, imm))

    def cmp(self, rn: int, imm: int) -> None:
        self.items.append(('cmp', rn, imm))

    def cmp_reg(self, rn: int, rm: int) -> None:
        self.items.append(('cmp_reg', rn, rm))

    def branch(self, cond: int, label: str) -> None:
        self.items.append(('branch', cond, label))

    def b(self, label: str) -> None: self.branch(0xe, label)
    def beq(self, label: str) -> None: self.branch(0x0, label)
    def bne(self, label: str) -> None: self.branch(0x1, label)
    def blt(self, label: str) -> None: self.branch(0xb, label)
    def bge(self, label: str) -> None: self.branch(0xa, label)
    def ble(self, label: str) -> None: self.branch(0xd, label)
    def bgt(self, label: str) -> None: self.branch(0xc, label)

    def ldr_imm(self, rd: int, rn: int, imm: int = 0) -> None:
        self.items.append(('ldr_imm', rd, rn, imm))

    def str_imm(self, rd: int, rn: int, imm: int = 0) -> None:
        self.items.append(('str_imm', rd, rn, imm))

    def svc(self, sysno: int) -> None:
        self.items.append(('svc', sysno))

    def dword(self, val: int) -> None:
        self.items.append(('dword', val))

    def asciiz(self, text: str) -> None:
        data = text.encode('ascii') + b'\x00'
        if len(data) % 4 != 0:
            data += b'\x00' * (4 - len(data) % 4)
        self.items.append(('raw', data))

    def ldr_val(self, rd: int, val_or_label: Union[str, int]) -> None:
        pool_idx = len(self.pool_entries)
        pool_label = f'_pool_{pool_idx}'
        self.pool_entries.append((pool_label, val_or_label))
        self.items.append(('ldr_pool', rd, pool_label))

    def assemble(self) -> bytes:
        # Append literal pool to items
        self.items.append(('align', 4))
        for pool_label, val_or_label in self.pool_entries:
            self.items.append(('label', pool_label))
            self.items.append(('pool_word', val_or_label))

        # Pass 1: compute offsets and label addresses
        curr_va = self.code_va
        for item in self.items:
            op = item[0]
            if op == 'label':
                self.labels[item[1]] = curr_va
            elif op == 'align':
                rem = curr_va % item[1]
                if rem != 0:
                    curr_va += item[1] - rem
            elif op == 'raw':
                curr_va += len(item[1])
            else:
                curr_va += 4

        # Pass 2: emit bytes
        curr_va = self.code_va
        out = bytearray()
        for item in self.items:
            op = item[0]
            if op == 'label':
                pass
            elif op == 'align':
                rem = len(out) % item[1]
                if rem != 0:
                    pad = item[1] - rem
                    out.extend(b'\x00' * pad)
                    curr_va += pad
            elif op == 'raw':
                out.extend(item[1])
                curr_va += len(item[1])
            elif op == 'dword':
                out.extend(struct.pack('<I', item[1]))
                curr_va += 4
            elif op == 'pool_word':
                val = item[1]
                if isinstance(val, str):
                    target_va = self.labels[val]
                else:
                    target_va = int(val)
                out.extend(struct.pack('<I', target_va))
                curr_va += 4
            elif op == 'mov':
                rd, imm = item[1], item[2]
                out.extend(struct.pack('<I', 0xe3a00000 | (rd << 12) | (imm & 0xff)))
                curr_va += 4
            elif op == 'mov_reg':
                rd, rm = item[1], item[2]
                out.extend(struct.pack('<I', 0xe1a00000 | (rd << 12) | (rm & 0xf)))
                curr_va += 4
            elif op == 'mvn':
                rd, imm = item[1], item[2]
                out.extend(struct.pack('<I', 0xe3e00000 | (rd << 12) | (imm & 0xff)))
                curr_va += 4
            elif op == 'sub':
                rd, rn, imm = item[1], item[2], item[3]
                out.extend(struct.pack('<I', 0xe2400000 | (rn << 16) | (rd << 12) | (imm & 0xff)))
                curr_va += 4
            elif op == 'cmp':
                rn, imm = item[1], item[2]
                out.extend(struct.pack('<I', 0xe3500000 | (rn << 16) | (imm & 0xff)))
                curr_va += 4
            elif op == 'cmp_reg':
                rn, rm = item[1], item[2]
                out.extend(struct.pack('<I', 0xe1500000 | (rn << 16) | (rm & 0xf)))
                curr_va += 4
            elif op == 'branch':
                cond, target_label = item[1], item[2]
                target_va = self.labels[target_label]
                rel = target_va - (curr_va + 8)
                field = (rel >> 2) & 0x00ffffff
                out.extend(struct.pack('<I', (cond << 28) | 0x0a000000 | field))
                curr_va += 4
            elif op == 'ldr_pool':
                rd, target_label = item[1], item[2]
                target_va = self.labels[target_label]
                rel = target_va - (curr_va + 8)
                if rel >= 0:
                    insn = 0xe59f0000 | (rd << 12) | (rel & 0xfff)
                else:
                    insn = 0xe51f0000 | (rd << 12) | ((-rel) & 0xfff)
                out.extend(struct.pack('<I', insn))
                curr_va += 4
            elif op == 'ldr_imm':
                rd, rn, imm = item[1], item[2], item[3]
                if imm >= 0:
                    insn = 0xe5900000 | (rn << 16) | (rd << 12) | (imm & 0xfff)
                else:
                    insn = 0xe5100000 | (rn << 16) | (rd << 12) | ((-imm) & 0xfff)
                out.extend(struct.pack('<I', insn))
                curr_va += 4
            elif op == 'str_imm':
                rd, rn, imm = item[1], item[2], item[3]
                if imm >= 0:
                    insn = 0xe5800000 | (rn << 16) | (rd << 12) | (imm & 0xfff)
                else:
                    insn = 0xe5000000 | (rn << 16) | (rd << 12) | ((-imm) & 0xfff)
                out.extend(struct.pack('<I', insn))
                curr_va += 4
            elif op == 'svc':
                sysno = item[1]
                out.extend(struct.pack('<I', 0xef900000 | (sysno & 0xffff)))
                curr_va += 4

        return bytes(out)


def build_elf(code: bytes, bss_size: int = 0x10000, base_va: int = 0x10000) -> bytes:
    """Wraps ARM bytecode into a standard 32-bit ELF executable."""
    file_size = 0x80 + len(code)
    mem_size = file_size + bss_size

    ehdr = struct.pack('<16sHHIIIIIHHH',
        ELF_IDENT_GENERIC,
        ET_EXEC,
        EM_ARM,
        EV_CURRENT,
        base_va + 0x80,  # e_entry
        52,              # e_phoff
        0,               # e_shoff
        EF_ARM,          # e_flags (0x206)
        52,              # e_ehsize
        32,              # e_phentsize
        1,               # e_phnum
    )

    phdr = struct.pack('<IIIIIIII',
        1,               # PT_LOAD
        0,               # p_offset
        base_va,         # p_vaddr
        base_va,         # p_paddr
        file_size,       # p_filesz
        mem_size,        # p_memsz
        7,               # p_flags (PF_R | PF_W | PF_X)
        0x10000,         # p_align
    )

    header = (ehdr + phdr).ljust(0x80, b'\x00')
    return header + code


def patch_ud_datcnv(code: bytes, orig_binary: Optional[Union[bytes, Path, str]] = None) -> bytes:
    """Patches original ud_datcnv executable with custom ARM code at entry point _start."""
    if orig_binary is None:
        p = BASE_DIR / 'build/w300/ud_datcnv.original'
        if p.is_file():
            orig_bytes = p.read_bytes()
        else:
            return build_elf(code, base_va=0x8000)
    elif isinstance(orig_binary, (str, Path)):
        orig_bytes = Path(orig_binary).read_bytes()
    else:
        orig_bytes = bytes(orig_binary)

    if len(orig_bytes) != 18028:
        if len(orig_bytes) == 0:
            return build_elf(code)
        raise ValueError(f"Expected 18028-byte ud_datcnv binary, got {len(orig_bytes)}")

    ENTRY_OFFSET = 0x9e0   # _start offset in file (vaddr 0x89e0 - 0x8000)
    MAX_TEXT_SIZE = 0xc44  # 3140 bytes available in .text

    if len(code) > MAX_TEXT_SIZE:
        raise ValueError(f"Assembled code size {len(code)} exceeds available .text capacity {MAX_TEXT_SIZE}")

    patched = bytearray(orig_bytes)
    patched[ENTRY_OFFSET : ENTRY_OFFSET + len(code)] = code
    return bytes(patched)


def make_test_payload(orig_binary: Optional[Union[bytes, Path, str]] = None) -> bytes:
    """Builds a canary binary by patching ud_datcnv to write /usr/test_exec.log and exit 0."""
    asm = ArmHelperAssembler(code_va=0x89e0)

    # sys_open("/usr/test_exec.log", 0x241, 0666)
    asm.ldr_val(0, 'path_test_log')
    asm.ldr_val(1, 0x241)  # O_WRONLY | O_CREAT | O_TRUNC
    asm.ldr_val(2, 0x1b6)  # 0666
    asm.svc(5)             # sys_open
    asm.mov_reg(8, 0)      # r8 = fd

    # sys_write(fd, "W300_EXEC_TEST_OK\n", 18)
    asm.mov_reg(0, 8)
    asm.ldr_val(1, 'msg_canary')
    asm.mov(2, 18)
    asm.svc(4)             # sys_write

    # sys_close(fd)
    asm.mov_reg(0, 8)
    asm.svc(6)             # sys_close

    # sys_sync()
    asm.svc(36)            # sys_sync (0x24)

    # sys_exit(0)
    asm.mov(0, 0)
    asm.svc(1)             # sys_exit

    # Data section
    asm.label('path_test_log')
    asm.asciiz('/usr/test_exec.log')
    asm.label('msg_canary')
    asm.asciiz('W300_EXEC_TEST_OK\n')

    code = asm.assemble()
    return patch_ud_datcnv(code, orig_binary)


def make_extractor_payload(orig_binary: Optional[Union[bytes, Path, str]] = None) -> bytes:
    """Builds the full AV / BIONZ firmware extraction binary by patching ud_datcnv."""
    asm = ArmHelperAssembler(code_va=0x89e0)

    # 1. Allocate 16KB buffer on stack
    # 0xe24dd901 encodes "sub sp, sp, #0x4000" (16384 bytes)
    asm.items.append(('raw', struct.pack('<I', 0xe24dd901)))
    asm.mov_reg(11, 13)    # r11 = sp (buffer pointer)

    # 2. Open log file /usr/dump.log
    asm.label('entry')
    asm.ldr_val(0, 'path_log')
    asm.ldr_val(1, 0x241)  # O_WRONLY | O_CREAT | O_TRUNC
    asm.ldr_val(2, 0x1b6)  # 0666
    asm.svc(5)             # sys_open
    asm.mov_reg(8, 0)      # r8 = log_fd

    # Log START
    asm.mov_reg(0, 8)
    asm.ldr_val(1, 'msg_start')
    asm.mov(2, 6)
    asm.svc(4)             # sys_write

    # 3. mkdir("/tmp/m", 0777)
    asm.ldr_val(0, 'path_tmp_m')
    asm.ldr_val(1, 0x1ff)  # 0777
    asm.svc(39)            # sys_mkdir (0x27)

    # 4. Mount /dev/nflasha5 to /tmp/m
    # Try 1: mount("/dev/nflasha5", "/tmp/m", "vfat", 0, "posix_attr")
    asm.ldr_val(0, 'path_dev_nflasha5')
    asm.ldr_val(1, 'path_tmp_m')
    asm.ldr_val(2, 'str_vfat')
    asm.mov(3, 0)
    asm.ldr_val(4, 'str_posix_attr')
    asm.svc(21)            # sys_mount (0x15)
    asm.cmp(0, 0)
    asm.bge('mount_ok')

    # Try 2: mount("/dev/nflasha5", "/tmp/m", "vfat", 0, 0)
    asm.ldr_val(0, 'path_dev_nflasha5')
    asm.ldr_val(1, 'path_tmp_m')
    asm.ldr_val(2, 'str_vfat')
    asm.mov(3, 0)
    asm.mov(4, 0)
    asm.svc(21)            # sys_mount
    asm.cmp(0, 0)
    asm.blt('mount_failed')

    asm.label('mount_ok')
    asm.mov_reg(0, 8)
    asm.ldr_val(1, 'msg_mount_ok')
    asm.mov(2, 9)
    asm.svc(4)             # sys_write

    # 5. Copy av.bin from /tmp/m/av.bin (or /tmp/m/AV.BIN) -> /usr/av.bin
    asm.ldr_val(0, 'path_mnt_av_bin')
    asm.mov(1, 0)          # O_RDONLY
    asm.mov(2, 0)
    asm.svc(5)             # sys_open
    asm.cmp(0, 0)
    asm.bge('av_open_ok')

    # Try uppercase AV.BIN
    asm.ldr_val(0, 'path_mnt_av_bin_upper')
    asm.mov(1, 0)
    asm.mov(2, 0)
    asm.svc(5)             # sys_open
    asm.cmp(0, 0)
    asm.blt('av_open_failed')

    asm.label('av_open_ok')
    asm.mov_reg(9, 0)      # r9 = av_in_fd

    # Open destination /usr/av.bin
    asm.ldr_val(0, 'path_usr_av_bin')
    asm.ldr_val(1, 0x241)
    asm.ldr_val(2, 0x1b6)
    asm.svc(5)             # sys_open
    asm.cmp(0, 0)
    asm.blt('av_dest_failed')
    asm.mov_reg(10, 0)     # r10 = av_out_fd

    # av.bin copy loop
    asm.label('av_copy_loop')
    asm.mov_reg(0, 9)
    asm.mov_reg(1, 11)     # r1 = buffer on stack
    asm.ldr_val(2, 16384)
    asm.svc(3)             # sys_read
    asm.cmp(0, 0)
    asm.ble('av_copy_done')

    asm.mov_reg(2, 0)      # r2 = bytes read
    asm.mov_reg(0, 10)     # r0 = out_fd
    asm.mov_reg(1, 11)     # r1 = buffer on stack
    asm.svc(4)             # sys_write
    asm.b('av_copy_loop')

    asm.label('av_copy_done')
    asm.mov_reg(0, 10)
    asm.svc(6)             # sys_close out_fd
    asm.mov_reg(0, 9)
    asm.svc(6)             # sys_close in_fd

    asm.mov_reg(0, 8)
    asm.ldr_val(1, 'msg_av_ok')
    asm.mov(2, 6)
    asm.svc(4)             # sys_write
    asm.b('try_sa')

    asm.label('av_dest_failed')
    asm.mov_reg(0, 9)
    asm.svc(6)             # sys_close in_fd
    asm.label('av_open_failed')
    asm.mov_reg(0, 8)
    asm.ldr_val(1, 'msg_av_fail')
    asm.mov(2, 8)
    asm.svc(4)             # sys_write
    # If av.bin failed on mounted filesystem, fallback to raw partition dump
    asm.b('do_raw_dump')

    # 6. Copy sa.bin from /tmp/m/sa.bin -> /usr/sa.bin
    asm.label('try_sa')
    asm.ldr_val(0, 'path_mnt_sa_bin')
    asm.mov(1, 0)
    asm.mov(2, 0)
    asm.svc(5)             # sys_open
    asm.cmp(0, 0)
    asm.bge('sa_open_ok')

    asm.ldr_val(0, 'path_mnt_sa_bin_upper')
    asm.mov(1, 0)
    asm.mov(2, 0)
    asm.svc(5)             # sys_open
    asm.cmp(0, 0)
    asm.blt('sa_done')

    asm.label('sa_open_ok')
    asm.mov_reg(9, 0)      # r9 = sa_in_fd

    asm.ldr_val(0, 'path_usr_sa_bin')
    asm.ldr_val(1, 0x241)
    asm.ldr_val(2, 0x1b6)
    asm.svc(5)
    asm.cmp(0, 0)
    asm.blt('sa_dest_failed')
    asm.mov_reg(10, 0)     # r10 = sa_out_fd

    asm.label('sa_copy_loop')
    asm.mov_reg(0, 9)
    asm.mov_reg(1, 11)     # r1 = buffer on stack
    asm.ldr_val(2, 16384)
    asm.svc(3)
    asm.cmp(0, 0)
    asm.ble('sa_copy_done')

    asm.mov_reg(2, 0)
    asm.mov_reg(0, 10)
    asm.mov_reg(1, 11)     # r1 = buffer on stack
    asm.svc(4)
    asm.b('sa_copy_loop')

    asm.label('sa_copy_done')
    asm.mov_reg(0, 10)
    asm.svc(6)
    asm.mov_reg(0, 9)
    asm.svc(6)

    asm.mov_reg(0, 8)
    asm.ldr_val(1, 'msg_sa_ok')
    asm.mov(2, 6)
    asm.svc(4)
    asm.b('umount_fs')

    asm.label('sa_dest_failed')
    asm.mov_reg(0, 9)
    asm.svc(6)
    asm.label('sa_done')

    # 7. Unmount /tmp/m
    asm.label('umount_fs')
    asm.ldr_val(0, 'path_tmp_m')
    asm.svc(22)            # sys_umount (0x16)

    asm.mov_reg(0, 8)
    asm.ldr_val(1, 'msg_umount')
    asm.mov(2, 7)
    asm.svc(4)
    asm.b('finish')

    # Mount failed branch
    asm.label('mount_failed')
    asm.mov_reg(0, 8)
    asm.ldr_val(1, 'msg_mount_fail')
    asm.mov(2, 11)
    asm.svc(4)

    # 8. Fallback: dump raw /dev/nflasha5 to /usr/nflasha5.raw
    asm.label('do_raw_dump')
    asm.ldr_val(0, 'path_dev_nflasha5')
    asm.mov(1, 0)
    asm.mov(2, 0)
    asm.svc(5)             # sys_open
    asm.cmp(0, 0)
    asm.blt('raw_open_failed')
    asm.mov_reg(9, 0)      # in_fd

    asm.ldr_val(0, 'path_usr_nflasha5_raw')
    asm.ldr_val(1, 0x241)
    asm.ldr_val(2, 0x1b6)
    asm.svc(5)
    asm.cmp(0, 0)
    asm.blt('raw_dest_failed')
    asm.mov_reg(10, 0)     # out_fd

    # Loop 224 blocks of 16384 = 3,670,016 bytes (3.5 MB)
    asm.ldr_val(7, 224)

    asm.label('raw_copy_loop')
    asm.mov_reg(0, 9)
    asm.mov_reg(1, 11)     # r1 = buffer on stack
    asm.ldr_val(2, 16384)
    asm.svc(3)
    asm.cmp(0, 0)
    asm.ble('raw_copy_done')

    asm.mov_reg(2, 0)
    asm.mov_reg(0, 10)
    asm.mov_reg(1, 11)     # r1 = buffer on stack
    asm.svc(4)

    asm.sub(7, 7, 1)
    asm.cmp(7, 0)
    asm.bgt('raw_copy_loop')

    asm.label('raw_copy_done')
    asm.mov_reg(0, 10)
    asm.svc(6)
    asm.mov_reg(0, 9)
    asm.svc(6)

    asm.mov_reg(0, 8)
    asm.ldr_val(1, 'msg_raw_ok')
    asm.mov(2, 7)
    asm.svc(4)
    asm.b('finish')

    asm.label('raw_dest_failed')
    asm.mov_reg(0, 9)
    asm.svc(6)
    asm.label('raw_open_failed')
    asm.mov_reg(0, 8)
    asm.ldr_val(1, 'msg_raw_fail')
    asm.mov(2, 9)
    asm.svc(4)

    # 9. Finish: sync and exit
    asm.label('finish')
    asm.svc(36)            # sys_sync

    asm.mov_reg(0, 8)
    asm.ldr_val(1, 'msg_done')
    asm.mov(2, 5)
    asm.svc(4)

    asm.mov_reg(0, 8)
    asm.svc(6)             # sys_close log_fd

    asm.mov(0, 0)
    asm.svc(1)             # sys_exit(0)

    # Constant string data
    asm.label('path_log')
    asm.asciiz('/usr/dump.log')
    asm.label('path_tmp_m')
    asm.asciiz('/tmp/m')
    asm.label('path_dev_nflasha5')
    asm.asciiz('/dev/nflasha5')
    asm.label('str_vfat')
    asm.asciiz('vfat')
    asm.label('str_posix_attr')
    asm.asciiz('posix_attr')
    asm.label('path_mnt_av_bin')
    asm.asciiz('/tmp/m/av.bin')
    asm.label('path_mnt_av_bin_upper')
    asm.asciiz('/tmp/m/AV.BIN')
    asm.label('path_usr_av_bin')
    asm.asciiz('/usr/av.bin')
    asm.label('path_mnt_sa_bin')
    asm.asciiz('/tmp/m/sa.bin')
    asm.label('path_mnt_sa_bin_upper')
    asm.asciiz('/tmp/m/SA.BIN')
    asm.label('path_usr_sa_bin')
    asm.asciiz('/usr/sa.bin')
    asm.label('path_usr_nflasha5_raw')
    asm.asciiz('/usr/nflasha5.raw')

    asm.label('msg_start')
    asm.asciiz('START\n')
    asm.label('msg_mount_ok')
    asm.asciiz('MOUNT_OK\n')
    asm.label('msg_mount_fail')
    asm.asciiz('MOUNT_FAIL\n')
    asm.label('msg_av_ok')
    asm.asciiz('AV_OK\n')
    asm.label('msg_av_fail')
    asm.asciiz('AV_FAIL\n')
    asm.label('msg_sa_ok')
    asm.asciiz('SA_OK\n')
    asm.label('msg_umount')
    asm.asciiz('UMOUNT\n')
    asm.label('msg_raw_ok')
    asm.asciiz('RAW_OK\n')
    asm.label('msg_raw_fail')
    asm.asciiz('RAW_FAIL\n')
    asm.label('msg_done')
    asm.asciiz('DONE\n')

    code = asm.assemble()
    return patch_ud_datcnv(code, orig_binary)


def disassemble_elf(elf_bytes: bytes) -> str:
    """Disassembles text section of an ELF or patched ud_datcnv binary using Capstone."""
    if not HAVE_CAPSTONE:
        return "[Capstone not available for disassembly]"
    if len(elf_bytes) == 18028:
        entry = 0x89e0
        code = elf_bytes[0x9e0:0x9e0 + 0xc44]
    else:
        entry = struct.unpack('<I', elf_bytes[24:28])[0]
        code = elf_bytes[0x80:]
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    lines = []
    for insn in md.disasm(code, entry):
        lines.append(f"0x{insn.address:05x}: {insn.mnemonic:<8} {insn.op_str}")
    return "\n".join(lines)


if __name__ == '__main__':
    test_elf = make_test_payload()
    print(f"Test ELF payload size: {len(test_elf)} bytes")
    print(disassemble_elf(test_elf[:120]))
    print("---")
    ext_elf = make_extractor_payload()
    print(f"Extractor ELF payload size: {len(ext_elf)} bytes")
    print("Disassembly of first 40 instructions:")
    print("\n".join(disassemble_elf(ext_elf).splitlines()[:40]))
