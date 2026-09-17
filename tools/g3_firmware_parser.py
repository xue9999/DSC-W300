#!/usr/bin/env python3
"""
tools/g3_firmware_parser.py - Container carving & cryptographic extraction pipeline for Sony Cyber-shot DSC-G3 firmware.
Safe offline parser, container carver, and CXD4108 MsFirm decryption engine.
Zero external C dependencies (pure Python standard library).
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import struct
import sys
import tarfile
import zlib
from pathlib import Path

# Static 64-byte key for Sony CXD4108 MsFirm container
KEY_CXD4108_MS = (
    b'\xF0\x68\x8F\x00\x00\x00\x68\xE0\x2C\x42\x00\x6A\x02\x8B\x55\xF0'
    b'\x52\xE8\x1A\xBD\xFF\xFF\x83\xC4\x10\x89\x45\xF4\x83\x7D\xF4\x00'
    b'\x75\x0E\x8B\x45\xE8\x50\xFF\x15\xA4\xF1\x68\x00\x33\xC0\xEB\x25'
    b'\x8B\x4D\xF0\x51\x8B\x55\xE8\x52\x8B\x45\xF4\x50\xE8\xFF\x58\x00'
)
key_cxd4108_ms = KEY_CXD4108_MS  # Export alias

LHA_HEADER_OFFSET = 0x7400
LHA_PAYLOAD_OFFSET = 0x744F
LHA_PAYLOAD_LENGTH = 55898688  # 0x0354F240
BLOCK_HEADER_SIZE = 128
MANIFEST_OFFSET = 0
MANIFEST_SIZE = 0x5000  # 20,480 bytes
EXPECTED_CHKSUM = 0x000c0eed
EXPECTED_SECTION_COUNT = 24

CRAMFS_MAGIC_LE = b'\x45\x3d\xcd\x28'
CRAMFS_SIGNATURE = b'Compressed ROMFS'
EXT2_SUPER_OFFSET = 1080
EXT2_SUPER_MAGIC = 0xEF53
INTERNAL_TAR_ARCHIVES = [
    'backup.tar', 'bin.tar', 'factory.tar', 'lib.tar',
    'fskapp1.tar', 'fskapp_1.tar', 'fskapp_2.tar', 'fskapp_3.tar',
    'fskfnt.tar', 'fskrel1.tar', 'fskrel2.tar', 'linuxset1.tar'
]
KERNEL_VERSION_EXPECTED = "Linux version 2.6.11-alp20080305 (jp06294@monet03) (gcc version 3.4.4) #1 Tue Feb 10 14:03:21 JST 2009"



def calculate_sha256(path_or_bytes):
    """Computes SHA-256 hex digest for a file path or bytes."""
    h = hashlib.sha256()
    if isinstance(path_or_bytes, (str, Path)):
        with open(path_or_bytes, 'rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
    else:
        h.update(path_or_bytes)
    return h.hexdigest()


def calculate_sha1(path_or_bytes):
    """Computes SHA-1 hex digest for a file path or bytes."""
    h = hashlib.sha1()
    if isinstance(path_or_bytes, (str, Path)):
        with open(path_or_bytes, 'rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
    else:
        h.update(path_or_bytes)
    return h.hexdigest()


class CXD4108MsCrypter:
    """
    Cryptographic engine for Sony CXD4108 MsFirm containers.
    Implements RFC 2104 double SHA-1 HMAC and SHA-1 PRNG keystream XOR cipher.
    """
    def __init__(self, key: bytes = KEY_CXD4108_MS):
        if len(key) != 64:
            raise ValueError(f"CXD4108 key must be exactly 64 bytes, got {len(key)}")
        self.key = bytes(key)
        self.name = "CXD4108_ms"
        self.ipad = bytes(b ^ 0x36 for b in self.key)
        self.opad = bytes(b ^ 0x5C for b in self.key)

    def _calc_hash(self, data: bytes) -> bytes:
        """
        RFC 2104 double SHA-1 HMAC over data using key ^ 0x36 and key ^ 0x5c.
        """
        inner = hashlib.sha1(self.ipad + data).digest()
        return hashlib.sha1(self.opad + inner).digest()

    calc_hash = _calc_hash
    _calcHash = _calc_hash

    def check_header_hash(self, hdr: bytes) -> bool:
        """
        Validates 128-byte block header signature.
        _calc_hash(hdr[:-20] + b'\\0'*20) == hdr[-20:]
        """
        if len(hdr) < BLOCK_HEADER_SIZE:
            return False
        computed = self._calc_hash(hdr[:-20] + b'\0' * 20)
        return computed == hdr[-20:]

    checkHeaderHash = check_header_hash

    def check_data_hash(self, hdr: bytes, data: bytes) -> bool:
        """
        Validates payload against header's first 20 bytes.
        _calc_hash(data) == hdr[:20]
        """
        if len(hdr) < 20:
            return False
        computed = self._calc_hash(data)
        return computed == hdr[:20]

    checkDataHash = check_data_hash

    def cipher(self, data: bytes) -> bytes:
        """
        Stream cipher: SHA-1 PRNG keystream generation.
        digest = key[:20], loop: digest = sha1(digest + key[20:40]).digest(), XOR with data.
        """
        if not data:
            return b''
        data_len = len(data)
        keystream_chunks = []
        generated = 0
        digest = self.key[:20]
        seed = self.key[20:40]
        while generated < data_len:
            digest = hashlib.sha1(digest + seed).digest()
            keystream_chunks.append(digest)
            generated += 20
        ks = b''.join(keystream_chunks)[:data_len]
        return (int.from_bytes(data, 'big') ^ int.from_bytes(ks, 'big')).to_bytes(data_len, 'big')

    decrypt = cipher

    def _decrypt(self, part, offset: int, size: int) -> bytes:
        """Compatibility helper for file-like stream parts."""
        part.seek(offset + BLOCK_HEADER_SIZE)
        enc_data = part.read(size)
        return self.cipher(enc_data)


class LhaStreamCarver:
    """
    Carves uncompressed LHA Level 2 stream (-lh0-) from PE32 executable or container file.
    """
    def __init__(self, file_path_or_obj):
        self.file_path_or_obj = file_path_or_obj

    def locate_stream(self) -> tuple[int, int]:
        """
        Locates LHA stream offset and length.
        Returns (stream_offset, stream_length).
        """
        if isinstance(self.file_path_or_obj, (str, Path)):
            with open(self.file_path_or_obj, 'rb') as f:
                return self._locate_from_stream(f)
        else:
            return self._locate_from_stream(self.file_path_or_obj)

    def _locate_from_stream(self, f) -> tuple[int, int]:
        f.seek(0)
        magic = f.read(2)
        if magic == b'MZ':
            # Windows PE executable - inspect LHA Level 2 header at 0x7400
            f.seek(LHA_HEADER_OFFSET)
            hdr_raw = f.read(2)
            if len(hdr_raw) < 2:
                raise ValueError(f"File truncated before LHA header at {LHA_HEADER_OFFSET:#x}")
            hdr_size = struct.unpack('<H', hdr_raw)[0]
            method = f.read(5)
            if method != b'-lh0-':
                raise ValueError(f"Expected uncompressed LHA method -lh0-, found {method!r}")
            comp_size, uncomp_size = struct.unpack('<II', f.read(8))
            stream_offset = LHA_HEADER_OFFSET + hdr_size
            return stream_offset, comp_size

        # Check if already a carved container (starts with 128-byte header)
        f.seek(0)
        hdr = f.read(BLOCK_HEADER_SIZE)
        if len(hdr) == BLOCK_HEADER_SIZE and hdr[20:-20] == b'\0' * 88:
            f.seek(0, os.SEEK_END)
            total_size = f.tell()
            return 0, total_size

        raise ValueError(f"Unrecognized container or executable format: magic={magic!r}")

    def extract_stream(self, output_path: Path | str = None) -> bytes:
        """
        Extracts the full uncompressed payload stream.
        """
        offset, length = self.locate_stream()
        if isinstance(self.file_path_or_obj, (str, Path)):
            with open(self.file_path_or_obj, 'rb') as f:
                f.seek(offset)
                data = f.read(length)
        else:
            self.file_path_or_obj.seek(offset)
            data = self.file_path_or_obj.read(length)

        if len(data) != length:
            raise ValueError(f"Expected {length} bytes for stream, read {len(data)} bytes")

        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_bytes(data)

        return data


def parse_manifest(manifest_bytes: bytes) -> dict:
    """
    Parses decrypted cntent.dat manifest and validates arithmetic checksum.
    Returns structured manifest dictionary with 24 section records.
    """
    if len(manifest_bytes) < 0x40:
        raise ValueError(f"Manifest too short ({len(manifest_bytes)} bytes, expected >= 64)")

    # Arithmetic checksum verification: sum(cntent[0x40:]) == int(chksum, 16)
    chksum_calc = sum(manifest_bytes[0x40:])
    text = manifest_bytes.decode('latin1')

    # Parse header properties
    fw_ver = ""
    sys_ver = ""
    datasize = 0
    expected_chksum = 0
    total_num = 0

    m = re.search(r'FV\s+([0-9a-zA-Z]+)', text)
    if m:
        fw_ver = m.group(1)
    m = re.search(r'SV\s+([0-9a-zA-Z]+)', text)
    if m:
        sys_ver = m.group(1)
    m = re.search(r'datasize=([0-9a-fA-F]+)', text)
    if m:
        datasize = int(m.group(1), 16)
    m = re.search(r'chksum=([0-9a-fA-F]+)', text)
    if m:
        expected_chksum = int(m.group(1), 16)
    m = re.search(r'total_num=([0-9a-fA-F]+)', text)
    if m:
        total_num = int(m.group(1), 16)

    if expected_chksum and chksum_calc != expected_chksum:
        raise ValueError(
            f"Manifest checksum mismatch: computed {chksum_calc:#010x}, expected {expected_chksum:#010x}"
        )

    sections = []
    current_sec = None
    section_index = 0

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            tag = line[1:-1]
            if tag in ('header', 'program data'):
                current_sec = {
                    'index': section_index,
                    'tag': tag
                }
                sections.append(current_sec)
                section_index += 1
        elif '=' in line and current_sec is not None:
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip()
            if k in ('offset', 'size'):
                current_sec[k] = int(v, 16)
                current_sec[f"{k}_hex"] = v
            elif k == 'encrypt':
                current_sec['encrypt'] = (v.lower() == 'yes')
                current_sec['encrypt_raw'] = v
            else:
                current_sec[k] = v

    if total_num and len(sections) != total_num:
        raise ValueError(
            f"Declared section count ({total_num}) does not match parsed section count ({len(sections)})"
        )

    return {
        'firmware_version': fw_ver,
        'system_version': sys_ver,
        'datasize': datasize,
        'checksum': chksum_calc,
        'checksum_expected': expected_chksum,
        'checksum_valid': (chksum_calc == expected_chksum),
        'total_sections': len(sections),
        'sections': sections
    }


def _parseContents(text_or_bytes):
    """Compatibility alias matching fwtool.sony.msfirm._parseContents."""
    if isinstance(text_or_bytes, bytes):
        raw_bytes = text_or_bytes
    else:
        raw_bytes = text_or_bytes.encode('latin1')
    manifest = parse_manifest(raw_bytes)
    # fwtool returns 3 dummy header dicts followed by sections
    out = [
        {'datasize': hex(manifest['datasize'])},
        {'chksum': hex(manifest['checksum'])},
        {'total_num': hex(manifest['total_sections'])}
    ]
    for s in manifest['sections']:
        out.append({
            'fnum': s.get('fnum', ''),
            'name': s['name'],
            'offset': hex(s['offset'])[2:],
            'size': hex(s['size'])[2:],
            'cksum': s.get('cksum', ''),
            'progress': s.get('progress', ''),
            'encrypt': s.get('encrypt_raw', 'yes')
        })
    return out


def _findDecrypter(part):
    """Compatibility decrypter probe matching fwtool.sony.msfirm._findDecrypter."""
    part.seek(0)
    hdr = part.read(BLOCK_HEADER_SIZE)
    crypter = CXD4108MsCrypter()
    if crypter.check_header_hash(hdr):
        return crypter
    raise ValueError("No matching decrypter found for container header")


class CramFSUnpacker:
    """
    Pure-Python userland CramFS decompression engine.
    Decompresses CramFS filesystem images in userland using standard struct and zlib.
    Zero external C dependencies, zero kernel mount requirements.
    Validates magic 0x28cd3d45 (LE: \\x45\\x3d\\xcd\\x28) and signature b'Compressed ROMFS'.
    Preserves directory tree, file permissions (mode & 0o777), and resolves symlinks.
    """
    def __init__(self, data: bytes):
        if len(data) < 64:
            raise ValueError(f"Buffer too small for CramFS superblock ({len(data)} bytes, expected >= 64)")
        self.data = data
        (
            self.magic, self.size, self.flags, self.future, self.signature,
            self.fsid_crc, self.fsid_edition, self.fsid_blocks, self.fsid_files, self.name
        ) = struct.unpack('<4sIII16sIIII16s', data[:64])
        if self.magic != CRAMFS_MAGIC_LE:
            raise ValueError(f"Invalid CramFS magic: {self.magic.hex()} (expected {CRAMFS_MAGIC_LE.hex()})")
        if self.signature.strip(b'\x00') != CRAMFS_SIGNATURE:
            raise ValueError(f"Invalid CramFS signature: {self.signature}")

    def _parse_inode(self, offset: int) -> tuple[int, int, int, int, int, int]:
        raw = struct.unpack('<HHII', self.data[offset:offset + 12])
        mode = raw[0]
        uid = raw[1]
        sz = raw[2] & 0xFFFFFF
        gid = (raw[2] >> 24) & 0xFF
        namelen = (raw[3] & 0x3F) << 2
        data_offset = (raw[3] >> 6) << 2
        return mode, uid, sz, gid, namelen, data_offset

    def unpack(self, dest_dir: Path | str) -> list[tuple[str, str, int]]:
        dest_dir = Path(dest_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        extracted = []

        def _extract_node(offset: int, node_size: int, mode: int, target_path: Path):
            name = target_path.name
            norm_target = Path(os.path.normpath(str(target_path)))
            try:
                if not norm_target.is_relative_to(dest_dir):
                    raise ValueError(f"Path traversal detected in CramFS: {name}")
            except AttributeError:
                if not str(norm_target).startswith(str(dest_dir)):
                    raise ValueError(f"Path traversal detected in CramFS: {name}")

            file_type = mode & 0o170000
            if file_type == 0o040000:  # Directory
                target_path.mkdir(parents=True, exist_ok=True)
                extracted.append((str(target_path), 'dir', 0))
                cur = offset
                end = offset + node_size
                while cur < end:
                    child_mode, uid, child_size, gid, namelen, child_offset = self._parse_inode(cur)
                    raw_name = self.data[cur + 12:cur + 12 + namelen]
                    child_name = raw_name.split(b'\0')[0].decode('ascii', errors='replace')
                    if child_name in ('.', '..') or any(part == '..' for part in Path(child_name).parts) or child_name.startswith(('/', '\\')):
                        raise ValueError(f"Path traversal detected in CramFS: {child_name}")
                    child_target = target_path / child_name
                    norm_child = Path(os.path.normpath(str(child_target)))
                    try:
                        if not norm_child.is_relative_to(dest_dir):
                            raise ValueError(f"Path traversal detected in CramFS: {child_name}")
                    except AttributeError:
                        if not str(norm_child).startswith(str(dest_dir)):
                            raise ValueError(f"Path traversal detected in CramFS: {child_name}")
                    _extract_node(child_offset, child_size, child_mode, child_target)
                    cur += 12 + namelen
            elif file_type == 0o100000:  # Regular file
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if target_path.is_symlink() or target_path.exists():
                    try:
                        os.chmod(target_path, 0o777)
                    except OSError:
                        pass
                    try:
                        target_path.unlink()
                    except OSError:
                        pass
                content = bytearray()
                if node_size > 0:
                    num_blocks = (node_size + 4095) // 4096
                    ptrs = struct.unpack(f'<{num_blocks}I', self.data[offset:offset + num_blocks * 4])
                    start_pos = offset + num_blocks * 4
                    for blk_end in ptrs:
                        blk_data = self.data[start_pos:blk_end]
                        if blk_data:
                            content.extend(zlib.decompress(blk_data))
                        start_pos = blk_end
                target_path.write_bytes(content[:node_size])
                try:
                    os.chmod(target_path, mode & 0o777)
                except OSError:
                    pass
                extracted.append((str(target_path), 'file', len(content[:node_size])))
            elif file_type == 0o120000:  # Symlink
                target_path.parent.mkdir(parents=True, exist_ok=True)
                content = bytearray()
                if node_size > 0:
                    num_blocks = (node_size + 4095) // 4096
                    ptrs = struct.unpack(f'<{num_blocks}I', self.data[offset:offset + num_blocks * 4])
                    start_pos = offset + num_blocks * 4
                    for blk_end in ptrs:
                        blk_data = self.data[start_pos:blk_end]
                        if blk_data:
                            content.extend(zlib.decompress(blk_data))
                        start_pos = blk_end
                sym_target = content[:node_size].decode('ascii', errors='replace')
                if any(part == '..' for part in Path(sym_target).parts) or sym_target.startswith(('/', '\\')):
                    norm_link = Path(os.path.normpath(str(target_path.parent / sym_target)))
                    try:
                        is_rel = norm_link.is_relative_to(dest_dir)
                    except AttributeError:
                        is_rel = str(norm_link).startswith(str(dest_dir))
                    if not is_rel and sym_target not in ('/dev/null', '/proc/kcore', '/proc/self/fd'):
                        raise ValueError(f"Path traversal detected in CramFS: {name}")
                    if sym_target.startswith(('/', '\\')) and sym_target not in ('/dev/null', '/proc/kcore', '/proc/self/fd'):
                        raise ValueError(f"Path traversal detected in CramFS: {name}")
                try:
                    if target_path.is_symlink() or target_path.exists():
                        try:
                            os.chmod(target_path, 0o777)
                        except OSError:
                            pass
                        target_path.unlink()
                    target_path.symlink_to(sym_target)
                except OSError:
                    target_path.write_text(sym_target)
                extracted.append((str(target_path), 'symlink', node_size))

        root_mode, root_uid, root_size, root_gid, root_namelen, root_offset = self._parse_inode(64)
        _extract_node(root_offset, root_size, root_mode, dest_dir)
        return extracted


def unpack_cramfs(cramfs_data: bytes, dest_dir: Path | str) -> list[tuple[str, str, int]]:
    unpacker = CramFSUnpacker(cramfs_data)
    return unpacker.unpack(dest_dir)


class SafeTarExtractor:
    """
    Secure tar archive extraction engine with strict path-traversal guardrails.
    Rejects directory escapes (..), absolute paths, character/block devices, and escaping symlinks.
    Supports Python 3.12+ data_filter.
    """
    @staticmethod
    def extract(tar_path_or_bytes, dest_dir: Path | str) -> list[str]:
        dest_dir = Path(dest_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)

        if isinstance(tar_path_or_bytes, (str, Path)):
            tf = tarfile.open(tar_path_or_bytes)
        elif isinstance(tar_path_or_bytes, (bytes, bytearray)):
            tf = tarfile.open(fileobj=io.BytesIO(tar_path_or_bytes))
        else:
            tf = tarfile.open(fileobj=tar_path_or_bytes)

        with tf:
            extracted_names = []
            for member in tf.getmembers():
                if member.isdev() or member.ischr() or member.isblk() or member.isfifo():
                    raise ValueError(f"Special device file rejected: {member.name}")

                name = member.name
                if os.path.isabs(name) or name.startswith('/') or name.startswith('\\'):
                    raise ValueError(f"Absolute path in tar archive rejected: {name}")

                parts = Path(name).parts
                if any(part == '..' for part in parts):
                    raise ValueError(f"Parent traversal '..' in tar archive rejected: {name}")

                target_path = (dest_dir / name).resolve()
                try:
                    if not target_path.is_relative_to(dest_dir):
                        raise ValueError(f"Target path escapes destination: {name} -> {target_path}")
                except AttributeError:
                    if not str(target_path).startswith(str(dest_dir)):
                        raise ValueError(f"Target path escapes destination: {name} -> {target_path}")

                if member.issym() or member.islnk():
                    link_target = (target_path.parent / member.linkname).resolve()
                    try:
                        if not link_target.is_relative_to(dest_dir):
                            raise ValueError(f"Symlink traversal detected: {name} -> {member.linkname}")
                    except AttributeError:
                        if not str(link_target).startswith(str(dest_dir)):
                            raise ValueError(f"Symlink traversal detected: {name} -> {member.linkname}")

                extracted_names.append(member.name)

            # Preserve identical regular files on repeat extraction. Reopening
            # PE files for mutation can be denied by Windows; byte equality lets
            # an idempotent run retain them without changing any source bytes.
            pending = []
            for member in tf.getmembers():
                target = dest_dir / member.name
                if member.isfile() and target.is_file() and not target.is_symlink():
                    with tf.extractfile(member) as source:
                        if target.read_bytes() == source.read():
                            continue
                pending.append(member)
            if hasattr(tarfile, 'data_filter'):
                tf.extractall(dest_dir, members=pending, filter='data')
            else:
                tf.extractall(dest_dir, members=pending)

            return extracted_names


def safe_extract_tar(tar_path_or_bytes, dest_dir: Path | str) -> list[str]:
    return SafeTarExtractor.extract(tar_path_or_bytes, dest_dir)


class Ext2Unpacker:
    """
    Pure-Python ext2 filesystem unpacker for initrd.img.
    Zero external C-dependencies, zero root required.
    """
    def __init__(self, data: bytes):
        if len(data) < 1024 + 1024:
            raise ValueError(f"Buffer too small for ext2 image ({len(data)} bytes)")
        self.data = data
        magic = struct.unpack('<H', data[EXT2_SUPER_OFFSET:EXT2_SUPER_OFFSET + 2])[0]
        if magic != EXT2_SUPER_MAGIC:
            raise ValueError(f"Invalid ext2 superblock magic: {hex(magic)} (expected {hex(EXT2_SUPER_MAGIC)})")
        self.block_size = 1024 << struct.unpack('<I', data[1024 + 24:1024 + 28])[0]
        self.blocks_count = struct.unpack('<I', data[1024 + 4:1024 + 8])[0]
        self.blocks_per_group = struct.unpack('<I', data[1024 + 32:1024 + 36])[0]
        self.inodes_per_group = struct.unpack('<I', data[1024 + 40:1024 + 44])[0]
        self.inode_size = struct.unpack('<H', data[1024 + 88:1024 + 90])[0]

        bgd_offset = max(self.block_size, 2048)
        num_groups = (self.blocks_count - 1) // self.blocks_per_group + 1
        self.inode_tables = []
        for g in range(num_groups):
            bgd = data[bgd_offset + g * 32:bgd_offset + (g + 1) * 32]
            inode_table_block = struct.unpack('<I', bgd[8:12])[0]
            self.inode_tables.append(inode_table_block)

    def _get_inode(self, num: int) -> tuple[int, int, int, bytes]:
        grp = (num - 1) // self.inodes_per_group
        idx = (num - 1) % self.inodes_per_group
        off = self.inode_tables[grp] * self.block_size + idx * self.inode_size
        raw = self.data[off:off + self.inode_size]
        mode, uid, size = struct.unpack('<HHI', raw[:8])
        blocks = raw[40:100]
        return mode, uid, size, blocks

    def _read_inode_data(self, mode: int, size: int, blocks_raw: bytes) -> bytes:
        if (mode & 0o170000) == 0o120000 and size <= 60:
            return blocks_raw[:size]
        ptrs = list(struct.unpack('<12I', blocks_raw[:48]))
        ind1 = struct.unpack('<I', blocks_raw[48:52])[0]
        if ind1 != 0:
            ind_data = self.data[ind1 * self.block_size:(ind1 + 1) * self.block_size]
            ptrs.extend(struct.unpack(f'<{self.block_size // 4}I', ind_data))
        out = bytearray()
        rem = size
        for p in ptrs:
            if rem <= 0:
                break
            take = min(rem, self.block_size)
            if p == 0:
                out.extend(b'\0' * take)
            else:
                out.extend(self.data[p * self.block_size:p * self.block_size + take])
            rem -= take
        return bytes(out)

    def _walk_dir(self, inode_num: int, path: str = '') -> list[tuple[int, str, int]]:
        mode, uid, size, blocks_raw = self._get_inode(inode_num)
        content = self._read_inode_data(mode, size, blocks_raw)
        off = 0
        entries = []
        while off < len(content):
            if off + 8 > len(content):
                break
            child_inode, rec_len, name_len, file_type = struct.unpack('<IHBB', content[off:off + 8])
            if rec_len == 0:
                break
            name = content[off + 8:off + 8 + name_len].decode('ascii', errors='replace')
            if name not in ('.', '..'):
                entries.append((child_inode, path + '/' + name if path else name, file_type))
            off += rec_len
        return entries

    def unpack(self, dest_dir: Path | str) -> list[tuple[str, str, int]]:
        dest_dir = Path(dest_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        extracted = []
        queue = [(2, '')]  # Root dir is inode 2
        while queue:
            inum, p = queue.pop(0)
            for c_inum, c_path, ftype in self._walk_dir(inum, p):
                if any(part == '..' for part in Path(c_path).parts) or c_path.startswith(('/', '\\')):
                    raise ValueError(f"Path traversal detected in Ext2: {c_path}")
                norm_target = Path(os.path.normpath(str(dest_dir / c_path)))
                try:
                    if not norm_target.is_relative_to(dest_dir):
                        raise ValueError(f"Path traversal detected in Ext2: {c_path}")
                except AttributeError:
                    if not str(norm_target).startswith(str(dest_dir)):
                        raise ValueError(f"Path traversal detected in Ext2: {c_path}")

                cmode, cuid, csize, cblocks = self._get_inode(c_inum)
                target = dest_dir / c_path
                ft = cmode & 0o170000
                if ft == 0o040000:  # Directory
                    target.mkdir(parents=True, exist_ok=True)
                    queue.append((c_inum, c_path))
                    extracted.append((c_path, 'dir', 0))
                elif ft == 0o100000:  # Regular file
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.is_symlink() or target.exists():
                        try:
                            os.chmod(target, 0o777)
                        except OSError:
                            pass
                        try:
                            target.unlink()
                        except OSError:
                            pass
                    cdata = self._read_inode_data(cmode, csize, cblocks)
                    target.write_bytes(cdata)
                    try:
                        os.chmod(target, cmode & 0o777)
                    except OSError:
                        pass
                    extracted.append((c_path, 'file', len(cdata)))
                elif ft == 0o120000:  # Symlink
                    target.parent.mkdir(parents=True, exist_ok=True)
                    sym_target = self._read_inode_data(cmode, csize, cblocks).decode('ascii', errors='replace')
                    if any(part == '..' for part in Path(sym_target).parts) or sym_target.startswith(('/', '\\')):
                        norm_link = Path(os.path.normpath(str(target.parent / sym_target)))
                        try:
                            is_rel = norm_link.is_relative_to(dest_dir)
                        except AttributeError:
                            is_rel = str(norm_link).startswith(str(dest_dir))
                        if not is_rel and sym_target not in ('/dev/null', '/proc/kcore', '/proc/self/fd'):
                            raise ValueError(f"Path traversal detected in Ext2: {c_path} -> {sym_target}")
                        if sym_target.startswith(('/', '\\')) and sym_target not in ('/dev/null', '/proc/kcore', '/proc/self/fd'):
                            raise ValueError(f"Path traversal detected in Ext2: {c_path} -> {sym_target}")
                    try:
                        if target.is_symlink() or target.exists():
                            try:
                                os.chmod(target, 0o777)
                            except OSError:
                                pass
                            target.unlink()
                        target.symlink_to(sym_target)
                    except OSError:
                        target.write_text(sym_target)
                    extracted.append((c_path, 'symlink', len(sym_target)))
        return extracted


def unpack_ext2(ext2_data: bytes, dest_dir: Path | str) -> list[tuple[str, str, int]]:
    unpacker = Ext2Unpacker(ext2_data)
    return unpacker.unpack(dest_dir)


def parse_partition_table(tbl_text_or_path) -> list[dict]:
    """
    Parses partinf.tbl into structured partition table entries.
    Identifies all 12 OneNAND flash partitions (/dev/nflasha1 through /dev/nflasha12).
    """
    if isinstance(tbl_text_or_path, (str, Path)) and os.path.exists(str(tbl_text_or_path)):
        with open(tbl_text_or_path, 'r', encoding='ascii', errors='replace') as f:
            tbl_text = f.read()
    elif isinstance(tbl_text_or_path, bytes):
        tbl_text = tbl_text_or_path.decode('ascii', errors='replace')
    else:
        tbl_text = str(tbl_text_or_path)

    partitions = []
    lines = tbl_text.splitlines()
    current_device = None
    current_desc = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('#') and '/dev/nflasha' in stripped:
            parts = stripped[1:].strip().split(maxsplit=2)
            if len(parts) >= 1:
                current_device = parts[0]
            current_desc = parts[2] if len(parts) >= 3 else ""
            if current_desc.startswith('(') and current_desc.endswith(')'):
                current_desc = current_desc[1:-1]
        elif stripped.startswith('0x'):
            tokens = [t.strip() for t in stripped.split(',')]
            if len(tokens) == 4:
                size_int = int(tokens[1], 16)
                size_mb = size_int / (1024 * 1024)
                partitions.append({
                    'device': current_device or f"/dev/nflasha{len(partitions) + 1}",
                    'description': current_desc or "",
                    'start': tokens[0],
                    'size': tokens[1],
                    'size_mb': size_mb,
                    'type': tokens[2],
                    'valid': tokens[3],
                })
                current_device = None
                current_desc = None

    return partitions


def extract_kernel_version(vmlinux_path_or_bytes) -> str:
    """
    Extracts Linux kernel banner string from vmlinux binary.
    """
    if isinstance(vmlinux_path_or_bytes, (str, Path)):
        with open(vmlinux_path_or_bytes, 'rb') as f:
            data = f.read()
    else:
        data = bytes(vmlinux_path_or_bytes)

    idx = data.find(b'Linux version ')
    if idx == -1:
        return ""
    end_null = data.find(b'\0', idx)
    end_nl = data.find(b'\n', idx)
    ends = [e for e in (end_null, end_nl) if e != -1]
    end = min(ends) if ends else idx + 256
    return data[idx:end].decode('ascii', errors='replace').strip()


def count_elf_files(root_dir: Path | str) -> int:
    """
    Recursively scans regular files under root_dir and counts those with \\x7fELF magic.
    """
    root_path = Path(root_dir)
    count = 0
    if not root_path.exists():
        return 0
    for p in root_path.rglob('*'):
        if p.is_file() and not p.is_symlink():
            try:
                with open(p, 'rb') as f:
                    if f.read(4) == b'\x7fELF':
                        count += 1
            except (OSError, PermissionError):
                pass
    return count


def generate_architecture_markdown(inventory: dict, md_path: Path | str) -> None:
    """Render bounded offline findings without inferring hardware qualification."""
    platform = inventory['platform']
    artifacts = inventory['artifacts']
    partitions = inventory['partition_table']
    lines = [
        '# DSC-G3 offline extraction summary', '',
        '## Decryption Status',
        'This report describes a reproducible offline extraction. Hashes and container HMACs establish recorded integrity checks; provenance and hardware behavior have separate qualification steps.',
        '',
        '## Platform Facts',
        'Model/architecture/browser labels in the imported profile are research descriptions. Counts, extracted strings and byte hashes are separately reproducible; descriptive labels are not hardware measurements.',
        f"- Model profile: `{platform['camera_model']}`",
        f"- Extracted kernel string: `{platform['kernel_version_string']}`",
        f"- Observed ELF files: {platform['elf_file_count']}",
        f"- Declared payload section count: {artifacts['manifest_cntent']['section_count']}",
        '', '## Storage Layout',
        f"Parsed table entries: {partitions['entry_count']}. A table entry can be unused; it is not necessarily an active partition.",
        '', '| Device | Offset | Size | Valid field |', '| --- | --- | --- | --- |',
    ]
    for item in partitions.get('entries', []):
        lines.append(f"| `{item['device']}` | `{item['start']}` | `{item['size']}` | `{item['valid']}` |")
    lines += ['', '## Subsystem Analysis',
              'The retained payload contains updater/runtime filesystems and application archives for static inspection. Use G3 findings as comparative material and qualify equivalent W300 firmware and calibration operations against W300 evidence.',
              'AV instruction edits and text-resource edits are offline experiments. Next qualification: verify installation, boot, recovery and image-quality effects on the target camera.',
              '', '## Key Evidence Paths']
    for name, item in artifacts.items():
        if isinstance(item, dict) and 'path' in item:
            lines.append(f"- {name}: `{item['path']}`; SHA-256: `{item.get('sha256', 'not recorded')}`")
    lines += ['', 'Paths in this generated report refer to the extraction run. Historical copies can contain historical paths. See the active repository guides and artifact manifest for canonical retained locations.']
    Path(md_path).write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


class G3FirmwareParser:
    """
    Main parser and extractor for Sony Cyber-shot DSC-G3 firmware containers.
    """
    def __init__(self, source_path: Path | str = "sources/DSCG3V2.exe", crypter: CXD4108MsCrypter = None):
        self.source_path = Path(source_path)
        if not self.source_path.exists():
            raise FileNotFoundError(f"Firmware source not found: {self.source_path}")
        self.crypter = crypter or CXD4108MsCrypter()
        self.carver = LhaStreamCarver(self.source_path)
        self.stream_offset, self.stream_length = self.carver.locate_stream()

    def verify_container_header(self) -> dict:
        """
        Validates the 128-byte container header at the beginning of the MsFirm stream.
        """
        with open(self.source_path, 'rb') as f:
            f.seek(self.stream_offset)
            hdr = f.read(BLOCK_HEADER_SIZE)
            if len(hdr) < BLOCK_HEADER_SIZE:
                raise ValueError("Truncated container header")

            padding_ok = (hdr[20:-20] == b'\0' * 88)
            hdr_hmac_ok = self.crypter.check_header_hash(hdr)

            # Check cntent.dat payload HMAC
            f.seek(self.stream_offset + BLOCK_HEADER_SIZE)
            enc_cntent = f.read(MANIFEST_SIZE)
            data_hmac_ok = self.crypter.check_data_hash(hdr, enc_cntent)

            if not padding_ok or not hdr_hmac_ok or not data_hmac_ok:
                raise ValueError(
                    f"Container header verification failed: padding={padding_ok}, "
                    f"header_hmac={hdr_hmac_ok}, data_hmac={data_hmac_ok}"
                )

            return {
                'stream_offset': self.stream_offset,
                'stream_length': self.stream_length,
                'padding_valid': padding_ok,
                'header_hmac_valid': hdr_hmac_ok,
                'data_hmac_valid': data_hmac_ok,
                'header_hmac': hdr[-20:].hex(),
                'data_hmac': hdr[:20].hex()
            }

    def read_manifest(self) -> tuple[bytes, dict]:
        """
        Decrypts cntent.dat (offset 0, size 0x5000) and parses all 24 section records.
        """
        with open(self.source_path, 'rb') as f:
            f.seek(self.stream_offset + BLOCK_HEADER_SIZE)
            enc_cntent = f.read(MANIFEST_SIZE)
            if len(enc_cntent) != MANIFEST_SIZE:
                raise ValueError(f"Expected {MANIFEST_SIZE} bytes for manifest, got {len(enc_cntent)}")

            dec_cntent = self.crypter.cipher(enc_cntent)
            manifest = parse_manifest(dec_cntent)
            return dec_cntent, manifest

    def extract_sections(self, output_dir: Path | str, dump_container: bool = True) -> list[dict]:
        """
        Extracts, decrypts, and cryptographically verifies all 24 sections declared in cntent.dat.
        Saves decrypted sections to output_dir/sections/ and cntent.dat to output_dir/.
        """
        out_path = Path(output_dir)
        sections_path = out_path / 'sections'
        sections_path.mkdir(parents=True, exist_ok=True)

        # 1. Verify container header
        container_info = self.verify_container_header()

        # 2. Decrypt manifest
        raw_cntent, manifest = self.read_manifest()
        cntent_file = out_path / 'cntent.dat'
        cntent_file.write_bytes(raw_cntent)

        # Also place cntent.dat in sections_path for convenience
        (sections_path / 'cntent.dat').write_bytes(raw_cntent)

        # Optional: Save carved uncompressed container stream to output
        if dump_container:
            carved_container_file = out_path / 'D-G3V2.dat'
            if not carved_container_file.exists() or carved_container_file.stat().st_size != self.stream_length:
                self.carver.extract_stream(carved_container_file)

        extracted_sections = []

        with open(self.source_path, 'rb') as f:
            for i, sec in enumerate(manifest['sections']):
                # Physical offset formula: stream_offset + offset_i + (i + 1) * 128
                phys_hdr_offset = self.stream_offset + sec['offset'] + (i + 1) * BLOCK_HEADER_SIZE
                phys_data_offset = phys_hdr_offset + BLOCK_HEADER_SIZE

                f.seek(phys_hdr_offset)
                hdr = f.read(BLOCK_HEADER_SIZE)
                if len(hdr) != BLOCK_HEADER_SIZE:
                    raise ValueError(f"Truncated block header for section {i} ({sec['name']}) at {phys_hdr_offset:#x}")

                # Cryptographic checks
                hdr_hmac_ok = self.crypter.check_header_hash(hdr)
                if not hdr_hmac_ok:
                    raise ValueError(
                        f"Header HMAC check failed for section {i} ({sec['name']}) at {phys_hdr_offset:#x}"
                    )

                f.seek(phys_data_offset)
                enc_payload = f.read(sec['size'])
                if len(enc_payload) != sec['size']:
                    raise ValueError(
                        f"Truncated payload for section {i} ({sec['name']}): read {len(enc_payload)}, expected {sec['size']}"
                    )

                data_hmac_ok = self.crypter.check_data_hash(hdr, enc_payload)
                if not data_hmac_ok:
                    raise ValueError(
                        f"Data HMAC check failed for section {i} ({sec['name']}) at {phys_data_offset:#x}"
                    )

                # Decrypt payload
                dec_payload = self.crypter.cipher(enc_payload)

                # Compute digests of decrypted payload
                dec_sha1 = hashlib.sha1(dec_payload).hexdigest()
                dec_sha256 = hashlib.sha256(dec_payload).hexdigest()

                # Numbered section files are canonical; no organizational aliases.
                prefix_name = f"{i:02d}_{sec['name']}"
                out_file = sections_path / prefix_name
                out_file.write_bytes(dec_payload)

                sec_info = {
                    'index': i,
                    'fnum': sec.get('fnum', f"{i:02x}"),
                    'name': sec['name'],
                    'file_name': prefix_name,
                    'offset': sec['offset'],
                    'size': sec['size'],
                    'phys_hdr_offset': phys_hdr_offset,
                    'phys_data_offset': phys_data_offset,
                    'header_hmac': hdr[-20:].hex(),
                    'data_hmac': hdr[:20].hex(),
                    'decrypted_sha1': dec_sha1,
                    'decrypted_sha256': dec_sha256,
                    'verified': True
                }
                extracted_sections.append(sec_info)

        # Write manifest metadata
        manifest_meta = {
            'source_path': str(self.source_path.resolve()),
            'source_sha256': calculate_sha256(self.source_path),
            'stream_offset': self.stream_offset,
            'stream_length': self.stream_length,
            'container_verification': container_info,
            'manifest_header': {
                'firmware_version': manifest['firmware_version'],
                'system_version': manifest['system_version'],
                'datasize': manifest['datasize'],
                'checksum': f"{manifest['checksum']:#010x}",
                'checksum_valid': manifest['checksum_valid'],
                'total_sections': manifest['total_sections']
            },
            'sections': extracted_sections
        }

        with open(out_path / 'manifest.json', 'w', encoding='utf-8') as f_out:
            json.dump(manifest_meta, f_out, indent=2)

        return extracted_sections

    def unpack_rootfs(self, output_dir: Path | str) -> dict:
        """
        Milestone 2: Decompresses CramFS root filesystems:
        1. BodyUdtr.img into <output_dir>/rootfs/BodyUdtr/
        2. rootfs.img from linuxset1.tar into <output_dir>/rootfs/system_rootfs/
        3. Also extracts kernel/vmlinux, kernel/initrd.img, kernel/rootfs.img,
           and unpacks initrd.img into <output_dir>/rootfs/initrd/.
        """
        out_path = Path(output_dir)
        sections_dir = out_path / 'sections'

        # Ensure sections are extracted
        if not (sections_dir / '02_BodyUdtr.img').exists() and not (sections_dir / 'BodyUdtr.img').exists():
            self.extract_sections(out_path)

        # Locate BodyUdtr.img
        body_udtr_path = sections_dir / '02_BodyUdtr.img'
        if not body_udtr_path.exists():
            body_udtr_path = sections_dir / 'BodyUdtr.img'

        # Locate linuxset1.tar
        linuxset_path = sections_dir / '17_linuxset1.tar'
        if not linuxset_path.exists():
            linuxset_path = sections_dir / 'linuxset1.tar'

        # 1. Unpack BodyUdtr.img
        body_dest = out_path / 'rootfs' / 'BodyUdtr'
        body_nodes = unpack_cramfs(body_udtr_path.read_bytes(), body_dest)

        # 2. Extract linuxset1.tar members into kernel/
        kernel_dir = out_path / 'kernel'
        kernel_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(linuxset_path) as tf:
            for member in tf.getmembers():
                if member.name in ('vmlinux', 'initrd.img', 'rootfs.img'):
                    f = tf.extractfile(member)
                    if f:
                        (kernel_dir / member.name).write_bytes(f.read())

        # Verify vmlinux intact
        vmlinux_path = kernel_dir / 'vmlinux'
        if not vmlinux_path.exists() or vmlinux_path.stat().st_size == 0:
            raise ValueError(f"vmlinux missing or empty in {kernel_dir}")

        # 3. Unpack rootfs.img into system_rootfs/
        rootfs_img_path = kernel_dir / 'rootfs.img'
        sys_rootfs_dest = out_path / 'rootfs' / 'system_rootfs'
        sys_nodes = unpack_cramfs(rootfs_img_path.read_bytes(), sys_rootfs_dest)

        # 4. Unpack initrd.img into rootfs/initrd/
        initrd_img_path = kernel_dir / 'initrd.img'
        initrd_dest = out_path / 'rootfs' / 'initrd'
        initrd_nodes = unpack_ext2(initrd_img_path.read_bytes(), initrd_dest)

        return {
            'body_udtr_nodes': len(body_nodes),
            'system_rootfs_nodes': len(sys_nodes),
            'initrd_nodes': len(initrd_nodes),
            'vmlinux_size': vmlinux_path.stat().st_size
        }

    def unpack_archives(self, output_dir: Path | str) -> dict:
        """
        Milestone 2: Safely extracts all 12 internal .tar archives into
        <output_dir>/archives_unpacked/<archive_name>/.
        Enforces path-traversal guardrails.
        """
        out_path = Path(output_dir)
        sections_dir = out_path / 'sections'
        archives_dir = out_path / 'archives_unpacked'
        archives_dir.mkdir(parents=True, exist_ok=True)

        if not sections_dir.exists() or not any(sections_dir.glob('*.tar')):
            self.extract_sections(out_path)

        unpacked_counts = {}
        for tar_name in INTERNAL_TAR_ARCHIVES:
            folder_name = tar_name[:-4] if tar_name.endswith('.tar') else tar_name
            candidates = list(sections_dir.glob(f"*_{tar_name}"))
            if not candidates:
                raw_path = sections_dir / tar_name
                if raw_path.exists():
                    candidates = [raw_path]

            if not candidates:
                continue

            tar_file = candidates[0]
            target_dest = archives_dir / folder_name
            members = safe_extract_tar(tar_file, target_dest)
            unpacked_counts[folder_name] = len(members)

        return unpacked_counts

    def generate_inventory(
        self,
        output_dir: Path | str,
        inventory_json_path: Path | str = None,
        architecture_md_path: Path | str = None
    ) -> dict:
        """
        Milestone 3: Generates structured decrypted_inventory.json and DECRYPTED_ARCHITECTURE.md
        benchmarked against SONY_NX3_Reversal schema.
        """
        out_path = Path(output_dir)
        sections_dir = out_path / 'sections'

        # Ensure prerequisites exist
        if not (sections_dir / '01_partinf.tbl').exists() and not (sections_dir / 'partinf.tbl').exists():
            self.extract_sections(out_path)
        if not (out_path / 'kernel' / 'vmlinux').exists():
            self.unpack_rootfs(out_path)
        if not (out_path / 'archives_unpacked').exists():
            self.unpack_archives(out_path)

        # Parse partition table
        partinf_path = sections_dir / '01_partinf.tbl'
        if not partinf_path.exists():
            partinf_path = sections_dir / 'partinf.tbl'
        partitions = parse_partition_table(partinf_path)

        # Extract kernel version
        vmlinux_path = out_path / 'kernel' / 'vmlinux'
        kver = extract_kernel_version(vmlinux_path)
        if not kver:
            raise ValueError("Kernel version string not found in vmlinux")

        # Count ELFs across output_dir
        total_elfs = count_elf_files(out_path)

        # Breakdown by archive
        elf_breakdown = {
            "BodyUdtr.img": count_elf_files(out_path / 'rootfs' / 'BodyUdtr'),
            "bin.tar": count_elf_files(out_path / 'archives_unpacked' / 'bin'),
            "lib.tar": count_elf_files(out_path / 'archives_unpacked' / 'lib'),
            "fskrel1.tar": count_elf_files(out_path / 'archives_unpacked' / 'fskrel1'),
            "fskrel2.tar": count_elf_files(out_path / 'archives_unpacked' / 'fskrel2'),
            "linuxset1.tar/rootfs.img": count_elf_files(out_path / 'rootfs' / 'system_rootfs'),
            "linuxset1.tar/initrd.img": count_elf_files(out_path / 'rootfs' / 'initrd')
        }

        # Locate section files for artifacts
        carved_dat = out_path / 'D-G3V2.dat'
        cntent_dat = out_path / 'cntent.dat'
        body_img = sections_dir / '02_BodyUdtr.img' if (sections_dir / '02_BodyUdtr.img').exists() else sections_dir / 'BodyUdtr.img'
        linuxset_tar = sections_dir / '17_linuxset1.tar' if (sections_dir / '17_linuxset1.tar').exists() else sections_dir / 'linuxset1.tar'
        av_bin = sections_dir / '09_av.bin' if (sections_dir / '09_av.bin').exists() else sections_dir / 'av.bin'

        inventory = {
            "artifacts": {
                "source_executable": {
                    "path": str(self.source_path),
                    "size": self.source_path.stat().st_size if self.source_path.exists() else 0,
                    "sha256": calculate_sha256(self.source_path) if self.source_path.exists() else "",
                    "lha_stream_offset": self.stream_offset,
                    "lha_stream_length": self.stream_length
                },
                "msfirm_container": {
                    "path": str(carved_dat),
                    "size": carved_dat.stat().st_size if carved_dat.exists() else 0,
                    "sha256": calculate_sha256(carved_dat) if carved_dat.exists() else ""
                },
                "manifest_cntent": {
                    "path": str(cntent_dat),
                    "size": cntent_dat.stat().st_size if cntent_dat.exists() else 0,
                    "sha256": calculate_sha256(cntent_dat) if cntent_dat.exists() else "",
                    "section_count": EXPECTED_SECTION_COUNT
                },
                "updater_body_img": {
                    "path": str(body_img),
                    "size": body_img.stat().st_size if (body_img and body_img.exists()) else 0,
                    "sha256": calculate_sha256(body_img) if (body_img and body_img.exists()) else ""
                },
                "linux_set_archive": {
                    "path": str(linuxset_tar),
                    "size": linuxset_tar.stat().st_size if (linuxset_tar and linuxset_tar.exists()) else 0,
                    "sha256": calculate_sha256(linuxset_tar) if (linuxset_tar and linuxset_tar.exists()) else ""
                },
                "av_rtos_image": {
                    "path": str(av_bin),
                    "size": av_bin.stat().st_size if (av_bin and av_bin.exists()) else 0,
                    "sha256": calculate_sha256(av_bin) if (av_bin and av_bin.exists()) else ""
                }
            },
            "platform": {
                "camera_model": "Sony Cyber-shot DSC-G3",
                "model_id": "0x08210030",
                "region_id": "0x00000000",
                "firmware_version": "2.00",
                "soc_architecture": "Sony CXD4108 BIONZ (ARM926EJ-S + µITRON Core)",
                "kernel_version_string": kver,
                "vmlinux_file_type": "Linux kernel ARM boot executable zImage (little-endian)",
                "vmlinux_size": vmlinux_path.stat().st_size if vmlinux_path.exists() else 0,
                "rootfs_file_type": "Compressed ROMFS (CramFS, big-endian magic 0x28cd3d45)",
                "rootfs_size": (out_path / 'kernel' / 'rootfs.img').stat().st_size if (out_path / 'kernel' / 'rootfs.img').exists() else 0,
                "initrd_file_type": "Linux rev 1.0 ext2 filesystem data (magic 0xef53)",
                "initrd_size": (out_path / 'kernel' / 'initrd.img').stat().st_size if (out_path / 'kernel' / 'initrd.img').exists() else 0,
                "body_udtr_file_type": "Compressed ROMFS (CramFS, big-endian magic 0x28cd3d45)",
                "body_udtr_size": body_img.stat().st_size if (body_img and body_img.exists()) else 0,
                "av_rtos_file_type": "ARM bare-metal executable / µITRON vector image",
                "av_rtos_size": av_bin.stat().st_size if (av_bin and av_bin.exists()) else 0,
                "elf_file_count": total_elfs,
                "elf_count_breakdown": elf_breakdown,
                "browser_version": "ACCESS NetFront Browser v3.4 (Flash Lite 6)",
                "app_framework": "Kinoma Platform / Fsk on Access Linux Platform"
            },
            "partition_table": {
                "source_file": str(partinf_path),
                "storage_technology": "OneNAND Flash",
                "entry_count": len(partitions),
                "entries": partitions
            },
            "sections_inventory": [
                {
                    'index': i,
                    'name': s.name,
                    'size': s.stat().st_size,
                    'sha1': calculate_sha1(s),
                    'sha256': calculate_sha256(s)
                }
                for i, s in enumerate(sorted(sections_dir.glob("[0-9][0-9]_*")))
            ]
        }

        # Write JSON output
        inv_targets = []
        if inventory_json_path:
            inv_targets.append(Path(inventory_json_path))
        else:
            inv_targets.append(out_path / 'decrypted_inventory.json')

        for tgt in inv_targets:
            tgt.parent.mkdir(parents=True, exist_ok=True)
            with open(tgt, 'w', encoding='utf-8') as f_json:
                json.dump(inventory, f_json, indent=2)

        # Write Markdown output
        md_targets = []
        if architecture_md_path:
            md_targets.append(Path(architecture_md_path))
        else:
            md_targets.append(out_path / 'DECRYPTED_ARCHITECTURE.md')

        for md_tgt in md_targets:
            md_tgt.parent.mkdir(parents=True, exist_ok=True)
            generate_architecture_markdown(inventory, md_tgt)

        return inventory


def main():
    parser = argparse.ArgumentParser(
        description="Sony Cyber-shot DSC-G3 Firmware Parser & Cryptographic Extractor"
    )
    parser.add_argument(
        '--source',
        type=Path,
        default=Path("sources/DSCG3V2.exe"),
        help="Path to source firmware executable (default: sources/DSCG3V2.exe)"
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path("build/g3/extracted"),
        help="Output base directory (default: build/g3/extracted)"
    )
    parser.add_argument(
        '--dump-sections',
        action='store_true',
        help="Decrypt and write all 24 section files into <output>/sections/"
    )
    parser.add_argument(
        '--dump-container',
        action='store_true',
        help="Carve uncompressed container stream to <output>/D-G3V2.dat"
    )
    parser.add_argument(
        '--info',
        action='store_true',
        help="Print container header information and manifest sections table"
    )
    parser.add_argument(
        '--unpack-rootfs',
        action='store_true',
        help="Unpack CramFS root filesystems (Milestone 2 hook)"
    )
    parser.add_argument(
        '--unpack-archives',
        action='store_true',
        help="Safely extract embedded tar archives (Milestone 2 hook)"
    )
    parser.add_argument(
        '--generate-inventory',
        action='store_true',
        help="Generate decrypted_inventory.json and DECRYPTED_ARCHITECTURE.md (Milestone 3 hook)"
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help="Execute complete end-to-end extraction pipeline"
    )

    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    for protected in (repository / 'sources', repository / 'evidence'):
        if args.output.resolve().is_relative_to(protected.resolve()):
            parser.error('Extraction output cannot overwrite preserved sources or evidence; use build/ or a temporary directory')

    # If no specific action specified, default to --dump-sections
    if not (args.dump_sections or args.dump_container or args.info or args.all or args.unpack_rootfs or args.unpack_archives or args.generate_inventory):
        args.dump_sections = True

    try:
        print(f"[*] Initializing G3 firmware parser for source: {args.source}")
        g3_parser = G3FirmwareParser(args.source)
        print(f"[+] LHA Stream located: offset {g3_parser.stream_offset:#06x}, size {g3_parser.stream_length:,} bytes")

        container_info = g3_parser.verify_container_header()
        print(f"[+] Container Header HMAC: {container_info['header_hmac']} [VALID]")
        print(f"[+] Container Data HMAC:   {container_info['data_hmac']} [VALID]")

        _, manifest = g3_parser.read_manifest()
        print(
            f"[+] Decrypted cntent.dat: Checksum {manifest['checksum']:#010x} "
            f"({'VALID' if manifest['checksum_valid'] else 'INVALID'}), "
            f"declared {manifest['total_sections']} sections"
        )

        if args.info:
            print("\n--- Manifest Section Table ---")
            print(f"{'Idx':<4} {'fnum':<6} {'Name':<16} {'Offset (hex)':<14} {'Size':<12} {'Tag'}")
            print("-" * 65)
            for s in manifest['sections']:
                print(
                    f"{s['index']:<4} {s.get('fnum', ''):<6} {s['name']:<16} "
                    f"{s['offset']:#010x}     {s['size']:<12} {s['tag']}"
                )

        if args.dump_sections or args.all:
            print(f"\n[*] Carving and decrypting {manifest['total_sections']} sections to: {args.output / 'sections'}")
            sections = g3_parser.extract_sections(args.output, dump_container=True)

            print(f"\n{'Idx':<4} {'Section Name':<16} {'Size (Bytes)':<14} {'Header HMAC':<12} {'Data HMAC':<12} {'Status'}")
            print("-" * 72)
            for s in sections:
                print(
                    f"{s['index']:<4} {s['name']:<16} {s['size']:<14,} "
                    f"{s['header_hmac'][:8]}...   {s['data_hmac'][:8]}...   [OK - VERIFIED]"
                )

            print(f"\n[SUCCESS] All {len(sections)} sections successfully decrypted and verified!")
            print(f"[+] Manifest written to: {args.output / 'cntent.dat'}")
            print(f"[+] Section payloads written to: {args.output / 'sections'}/")
            print(f"[+] Section metadata written to: {args.output / 'manifest.json'}")

        if args.unpack_rootfs or args.all:
            print(f"\n[*] Unpacking CramFS root filesystems to: {args.output / 'rootfs'}")
            rootfs_res = g3_parser.unpack_rootfs(args.output)
            print(f"[+] BodyUdtr.img unpacked: {rootfs_res['body_udtr_nodes']} filesystem nodes")
            print(f"[+] system_rootfs unpacked: {rootfs_res['system_rootfs_nodes']} filesystem nodes")
            print(f"[+] initrd.img unpacked: {rootfs_res['initrd_nodes']} filesystem nodes")
            print(f"[+] Kernel vmlinux extracted: {rootfs_res['vmlinux_size']:,} bytes")

        if args.unpack_archives or args.all:
            print(f"\n[*] Safely extracting internal tar archives to: {args.output / 'archives_unpacked'}")
            archives_res = g3_parser.unpack_archives(args.output)
            for name, count in archives_res.items():
                print(f"  [+] {name}.tar: {count} members safely extracted")

        if args.generate_inventory or args.all:
            print(f"\n[*] Generating architectural inventory & documentation...")
            inv = g3_parser.generate_inventory(args.output)
            print(f"[+] Inventory JSON generated: {args.output / 'decrypted_inventory.json'}")
            print(f"[+] Architecture Markdown generated: {args.output / 'DECRYPTED_ARCHITECTURE.md'}")
            print(f"[+] Verified ELF count: {inv['platform']['elf_file_count']}")
            print(f"[+] Verified Partitions: {inv['partition_table']['entry_count']}")
            print(f"[+] Kernel Version: {inv['platform']['kernel_version_string']}")

    except Exception as e:
        print(f"[-] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

