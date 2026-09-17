"""Offline SDM/OneNAND assembly and synthetic emulator-fixture helpers.

Factory profiles below are assumed test layouts, not validated camera calibration
or destination encodings. Outputs are not qualified for physical hardware.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
import struct
from typing import Dict, List, Optional, Tuple, Union

# SDM Partition Table constants
SDM_MAGIC = b"8246"
SDM_VERSION = b"1.00"
SDM_HEADER_SIZE = 32
SDM_ENTRY_SIZE = 16

# Flash Geometry constants
SECTOR_SIZE = 0x200           # 512 bytes
SPARE_SIZE = 0x10             # 16 bytes per sector
SECTORS_PER_BLOCK = 0x100     # 256 sectors per block (128 KB per block)
BLOCK_SIZE = SECTOR_SIZE * SECTORS_PER_BLOCK  # 131,072 bytes (128 KB)
DEFAULT_NAND_SIZE = 0x4000000 # 64 MB (OneNAND default on CXD4108)

# Assumed synthetic fixture offsets, NOT a qualified physical calibration map.
DESTINATION_BYTE_OFFSET = 0x00
TOUCHSCREEN_ENABLE_OFFSET = 0x2A5
LENS_COVER_ENABLE_OFFSET = 0x2A6
TV_STANDARD_OFFSET = 0x400    # In Hreg.bin: 0x02 = NTSC, 0x01 = PAL

# Hypothetical destination labels for test scenarios; bytes are not hardware evidence.
SONY_DESTINATIONS = {
    0x01: "J1 (Japan Domestic - Japanese only)",
    0x02: "UC2 (North America - English/French/Spanish)",
    0x03: "CEE8 (Europe - English/Polish/German/French/etc.)",
    0x04: "CEE9 (Europe East - English/Russian/etc.)",
    0x05: "E32 (Asia/Oceania - English/Traditional Chinese)",
    0x06: "KR2 (Korea - Korean/English)",
    0x07: "CN2 (China Domestic - Simplified Chinese/English)",
}


def dump16le(val: int) -> bytes:
    """Pack 16-bit little-endian integer."""
    return struct.pack("<H", val)


def dump32le(val: int) -> bytes:
    """Pack 32-bit little-endian integer."""
    return struct.pack("<I", val)


def parse32le(data: bytes) -> int:
    """Unpack 32-bit little-endian integer."""
    return struct.unpack("<I", data)[0]


def write_sdm_partition_table(partitions: List[bytes]) -> bytes:
    """Generate raw SDM flash container with partition table header.
    
    Format:
      Offset 0x00: Magic '8246' (4 bytes)
      Offset 0x04: Version '1.00' (4 bytes)
      Offset 0x08: Number of partitions (uint32 LE)
      Offset 0x0C: Padding (20 bytes 0xFF)
      Offset 0x20: Array of partition descriptors (16 bytes each):
                   - Start byte offset (uint32 LE)
                   - Size in bytes (uint32 LE)
                   - Type (uint32 LE, 1 = normal)
                   - Flags (uint32 LE, 0xFFFFFFFF = active)
      Padded to 512-byte sector boundary with 0xFF.
      Partition payloads aligned to 512-byte sector boundaries.
    """
    out = io.BytesIO()
    num_parts = len(partitions)

    # 1. Write Header (32 bytes)
    hdr = io.BytesIO()
    hdr.write(SDM_MAGIC)
    hdr.write(SDM_VERSION)
    hdr.write(dump32le(num_parts))
    hdr.write(b"\xff" * 20)
    out.write(hdr.getvalue())

    # Reserve space for partition descriptor table entries
    entries_size = num_parts * SDM_ENTRY_SIZE
    out.write(b"\x00" * entries_size)

    # Pad header sector to 512 bytes
    if out.tell() % SECTOR_SIZE != 0:
        pad_len = SECTOR_SIZE - (out.tell() % SECTOR_SIZE)
        out.write(b"\xff" * pad_len)

    # 2. Write partition payloads
    descriptors: List[Tuple[int, int]] = []
    for part_data in partitions:
        start_offset = out.tell()
        out.write(part_data)
        # Pad payload to sector boundary
        if out.tell() % SECTOR_SIZE != 0:
            pad_len = SECTOR_SIZE - (out.tell() % SECTOR_SIZE)
            out.write(b"\xff" * pad_len)
        descriptors.append((start_offset, len(part_data)))

    # 3. Seek back and write partition descriptors
    out.seek(SDM_HEADER_SIZE)
    for start_off, size in descriptors:
        out.write(dump32le(start_off))
        out.write(dump32le(size))
        out.write(dump32le(1))          # Type = 1
        out.write(dump32le(0xFFFFFFFF)) # Flags = active

    return out.getvalue()


def read_sdm_partition_table(data: bytes) -> List[Tuple[int, int, bytes]]:
    """Parse SDM partition table and return list of (index, size, payload)."""
    if len(data) < SECTOR_SIZE:
        raise ValueError("Data too short for SDM partition table")
    magic = data[:4]
    if magic != SDM_MAGIC:
        raise ValueError(f"Invalid SDM magic: {magic!r}, expected {SDM_MAGIC!r}")
    version = data[4:8]
    if version != SDM_VERSION:
        raise ValueError(f"Invalid SDM version: {version!r}, expected {SDM_VERSION!r}")

    num_partitions = parse32le(data[8:12])
    partitions = []
    for i in range(num_partitions):
        entry_offset = SDM_HEADER_SIZE + (i * SDM_ENTRY_SIZE)
        entry_data = data[entry_offset : entry_offset + SDM_ENTRY_SIZE]
        start_off, size, p_type, p_flag = struct.unpack("<IIII", entry_data)
        if p_flag & 1:
            payload = data[start_off : start_off + size]
            partitions.append((i + 1, size, payload))
    return partitions


def pack_onenand_image(
    boot: bytes,
    data: bytes,
    size: int = DEFAULT_NAND_SIZE,
    max_free_space: int = 0x100000,
) -> bytes:
    """Format boot partition and flash data into Samsung OneNAND flash image.
    
    Constructs main data sectors (512 bytes) and spare area metadata (16 bytes)
    including block bad markers and bootloader signature tags (0x5555, 0xAAAA).
    """
    num_blocks = size // SECTOR_SIZE // SECTORS_PER_BLOCK
    boot_blocks = (len(boot) + BLOCK_SIZE - 1) // BLOCK_SIZE if boot else 0
    data_blocks = (len(data) + BLOCK_SIZE - 1) // BLOCK_SIZE if data else 0

    if max_free_space >= 0:
        free_blocks = (max_free_space + BLOCK_SIZE - 1) // BLOCK_SIZE
        data_blocks = max(data_blocks, num_blocks - boot_blocks - free_blocks)

    f = io.BytesIO()
    # Write boot payload padded to block boundary
    if boot:
        f.write(boot)
        target_boot_end = boot_blocks * BLOCK_SIZE
        if f.tell() < target_boot_end:
            f.write(b"\xff" * (target_boot_end - f.tell()))

    # Write flash data payload padded to target blocks
    f.write(data)
    target_data_end = (boot_blocks + data_blocks) * BLOCK_SIZE
    if f.tell() < target_data_end:
        f.write(b"\xff" * (target_data_end - f.tell()))

    # Pad remaining flash area
    total_data_bytes = num_blocks * BLOCK_SIZE
    if f.tell() < total_data_bytes:
        f.write(b"\xff" * (total_data_bytes - f.tell()))

    # Append OneNAND spare area framing (16 bytes per sector)
    for i in range(num_blocks):
        for j in range(SECTORS_PER_BLOCK):
            marker = 0xFFFF
            boot_marker = 0xFFFF
            if i == 0 and i < boot_blocks:
                if j == 0:
                    boot_marker = 0x5555
                elif j == 3:
                    boot_marker = 0xAAAA
            elif boot_blocks <= i < boot_blocks + data_blocks:
                if j == 0 or j == 1:
                    marker = 0
                elif j == 2:
                    marker = i - boot_blocks
            spare = b"\xff\xff" + dump16le(marker) + b"\xff" * (SPARE_SIZE - 6) + dump16le(boot_marker)
            f.write(spare)

    return f.getvalue()


def build_mbr_image(partitions: List[bytes]) -> bytes:
    """Build a simple MBR disk image wrapping partitions (e.g. for MMC/SD)."""
    f = io.BytesIO()
    # Reserve MBR sector
    f.write(b"\x00" * SECTOR_SIZE)
    entries: List[Tuple[int, int]] = []
    for p in partitions:
        start_sector = f.tell() // SECTOR_SIZE
        f.write(p)
        if f.tell() % SECTOR_SIZE != 0:
            f.write(b"\x00" * (SECTOR_SIZE - (f.tell() % SECTOR_SIZE)))
        sector_count = (f.tell() // SECTOR_SIZE) - start_sector
        entries.append((start_sector, sector_count))

    # Write MBR partition table entries at offset 0x1BE
    f.seek(0x1BE)
    for i, (start_sec, num_sec) in enumerate(entries[:4]):
        # Bootable (0x80) or non-bootable (0x00), type FAT32 (0x0C)
        entry = struct.pack(
            "<BBBBBBBBII",
            0x80 if i == 0 else 0x00,
            0x00, 0x01, 0x00, # CHS start
            0x0C,             # FAT32 LBA
            0x00, 0x00, 0x00, # CHS end
            start_sec,
            num_sec,
        )
        f.write(entry)
    f.seek(0x1FE)
    f.write(b"\x55\xaa") # MBR signature
    return f.getvalue()


def build_factory_partition2(
    destination_byte: int = 0x01,
    touchscreen_enable: bool = True,
    lens_cover_enable: bool = False,
    ntsc_mode: bool = True,
    base_asys: Optional[bytes] = None,
    base_hsys: Optional[bytes] = None,
) -> Dict[str, bytes]:
    """Generate synthetic partition-2 fixtures, never actual camera calibration.
    
    Returns a dictionary mapping relative filesystem paths to binary contents:
      - /factory/Asys.bin
      - /factory/Areg.bin
      - /factory/Hsys.bin
      - /factory/Hreg.bin
    """
    # Default Asys template: 0x800 bytes
    asys = bytearray(base_asys if base_asys else b"\x00" * 0x800)
    if len(asys) < 0x800:
        asys.extend(b"\x00" * (0x800 - len(asys)))

    # Set destination byte
    asys[DESTINATION_BYTE_OFFSET] = destination_byte & 0xFF

    # Hardware flags
    if len(asys) > TOUCHSCREEN_ENABLE_OFFSET:
        asys[TOUCHSCREEN_ENABLE_OFFSET] = 0x01 if touchscreen_enable else 0x00
    if len(asys) > LENS_COVER_ENABLE_OFFSET:
        asys[LENS_COVER_ENABLE_OFFSET] = 0x01 if lens_cover_enable else 0x00

    # Areg mirrors Asys with destination synchronization
    areg = bytearray(asys)

    # Hsys template: 0x800 bytes
    hsys = bytearray(base_hsys if base_hsys else b"\x00" * 0x800)
    if len(hsys) < 0x800:
        hsys.extend(b"\x00" * (0x800 - len(hsys)))

    # Hreg template: 0x800 bytes with TV standard at 0x400
    hreg = bytearray(hsys)
    if len(hreg) > TV_STANDARD_OFFSET:
        hreg[TV_STANDARD_OFFSET] = 0x02 if ntsc_mode else 0x01

    return {
        "/factory/Asys.bin": bytes(asys),
        "/factory/Areg.bin": bytes(areg),
        "/factory/Hsys.bin": bytes(hsys),
        "/factory/Hreg.bin": bytes(hreg),
    }


class Cxd4108FlashBuilder:
    """Host-only image assembly experiment; no hardware compatibility guarantee."""

    def __init__(self, nand_size: int = DEFAULT_NAND_SIZE):
        self.nand_size = nand_size
        self.partitions: Dict[int, bytes] = {}
        self.boot_partition: bytes = b""
        self.bootrom: bytes = b""

    def set_bootrom(self, data: bytes) -> Cxd4108FlashBuilder:
        self.bootrom = data
        return self

    def set_boot_partition(self, data: bytes) -> Cxd4108FlashBuilder:
        self.boot_partition = data
        return self

    def set_partition(self, index: int, data: bytes) -> Cxd4108FlashBuilder:
        self.partitions[index] = data
        return self

    def build_sdm(self, max_partitions: int = 11) -> bytes:
        """Assemble all configured partitions into an SDM image."""
        part_list: List[bytes] = []
        for i in range(1, max_partitions + 1):
            part_list.append(self.partitions.get(i, b""))
        return write_sdm_partition_table(part_list)

    def build_onenand(self, max_partitions: int = 11) -> bytes:
        """Assemble full OneNAND image with SDM table and spare areas."""
        sdm_data = self.build_sdm(max_partitions=max_partitions)
        return pack_onenand_image(
            boot=self.boot_partition,
            data=sdm_data,
            size=self.nand_size,
        )
