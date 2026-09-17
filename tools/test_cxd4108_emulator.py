"""Automated Tests for Sony CXD4108 Emulation & Flash Staging Tooling.

Verifies:
  1. SDM Partition Table packing and parsing (header magic '8246', version '1.00').
  2. OneNAND image construction and spare area markers (0x5555, 0xAAAA).
  3. MBR image construction and partition bounds.
  4. Synthetic partition-2 fixture layout (destination byte, touchscreen, TV standard).
  5. QEMU CLI argument synthesis for DSC-G3 and DSC-W90.
  6. High-level Cxd4108FlashBuilder assembly.

100% offline, pure Python standard library.
"""

import os
from pathlib import Path
import struct
import sys
import unittest

# Ensure tools directory is on sys.path
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from cxd4108_emulator import (
    SDM_MAGIC,
    SDM_VERSION,
    SECTOR_SIZE,
    SPARE_SIZE,
    SECTORS_PER_BLOCK,
    DEFAULT_NAND_SIZE,
    write_sdm_partition_table,
    pack_onenand_image,
    build_factory_partition2,
    build_mbr_image,
    Cxd4108FlashBuilder,
    find_qemu_binary,
    build_g3_qemu_args,
    build_w90_qemu_args,
)
from cxd4108_emulator.flash_builder import (
    read_sdm_partition_table,
    DESTINATION_BYTE_OFFSET,
    TOUCHSCREEN_ENABLE_OFFSET,
    LENS_COVER_ENABLE_OFFSET,
    TV_STANDARD_OFFSET,
    SONY_DESTINATIONS,
)


class TestCxd4108FlashBuilder(unittest.TestCase):
    """Test suite for SDM partition table and flash generation."""

    def test_sdm_partition_table_header(self):
        p1 = b"PARTITION_1_DATA" * 32
        p2 = b"PARTITION_2_DATA" * 64
        sdm = write_sdm_partition_table([p1, p2])

        # Verify magic and version
        self.assertEqual(sdm[:4], SDM_MAGIC)
        self.assertEqual(sdm[4:8], SDM_VERSION)

        # Verify partition count (uint32 LE)
        count = struct.unpack("<I", sdm[8:12])[0]
        self.assertEqual(count, 2)

        # Header must be padded to sector boundary (512 bytes)
        self.assertEqual(len(sdm) % SECTOR_SIZE, 0)

        # Roundtrip parsing
        parsed = read_sdm_partition_table(sdm)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0][0], 1)
        self.assertEqual(parsed[0][1], len(p1))
        self.assertEqual(parsed[0][2], p1)
        self.assertEqual(parsed[1][0], 2)
        self.assertEqual(parsed[1][1], len(p2))
        self.assertEqual(parsed[1][2], p2)

    def test_onenand_packaging_and_spare_markers(self):
        boot = b"\x12\x34\x56\x78" * 128
        sdm_data = b"SDM_SAMPLE_PAYLOAD" * 256
        nand_size = 0x80000  # 512 KB (4 blocks of 128 KB)

        nand_image = pack_onenand_image(boot, sdm_data, size=nand_size, max_free_space=0x20000)

        # Total size must equal data blocks + spare area
        num_sectors = nand_size // SECTOR_SIZE
        expected_size = nand_size + (num_sectors * SPARE_SIZE)
        self.assertEqual(len(nand_image), expected_size)

        # Check boot markers in spare area of block 0:
        # Sector 0 spare offset = nand_size + (0 * 16)
        spare_start = nand_size
        sec0_spare = nand_image[spare_start : spare_start + 16]
        # Boot marker is at the end of spare area (last 2 bytes, uint16 LE)
        sec0_boot_marker = struct.unpack("<H", sec0_spare[-2:])[0]
        self.assertEqual(sec0_boot_marker, 0x5555)

        # Sector 3 spare has 0xAAAA
        sec3_spare = nand_image[spare_start + (3 * 16) : spare_start + (4 * 16)]
        sec3_boot_marker = struct.unpack("<H", sec3_spare[-2:])[0]
        self.assertEqual(sec3_boot_marker, 0xAAAA)

    def test_mbr_image_generation(self):
        p1 = b"FAT_FILE_SYSTEM_DATA" * 50
        mbr = build_mbr_image([p1])

        # Must have MBR magic 0x55AA at offset 0x1FE
        self.assertEqual(mbr[0x1FE:0x200], b"\x55\xaa")

        # Must be aligned to sector boundary
        self.assertEqual(len(mbr) % SECTOR_SIZE, 0)
        self.assertTrue(len(mbr) >= SECTOR_SIZE * 2)

    def test_factory_partition2_structure(self):
        # Test CEE8 destination (European English/Polish/German)
        part2 = build_factory_partition2(
            destination_byte=0x03,  # CEE8
            touchscreen_enable=True,
            lens_cover_enable=False,
            ntsc_mode=False,        # PAL
        )

        asys = part2["/factory/Asys.bin"]
        areg = part2["/factory/Areg.bin"]
        hreg = part2["/factory/Hreg.bin"]

        # Destination byte at offset 0
        self.assertEqual(asys[DESTINATION_BYTE_OFFSET], 0x03)
        self.assertEqual(areg[DESTINATION_BYTE_OFFSET], 0x03)

        # Touchscreen enable flag at offset 0x2A5
        self.assertEqual(asys[TOUCHSCREEN_ENABLE_OFFSET], 0x01)

        # Lens cover disable flag at offset 0x2A6
        self.assertEqual(asys[LENS_COVER_ENABLE_OFFSET], 0x00)

        # TV Standard PAL (0x01) at offset 0x400
        self.assertEqual(hreg[TV_STANDARD_OFFSET], 0x01)

    def test_cxd4108_flash_builder_orchestration(self):
        builder = Cxd4108FlashBuilder(nand_size=0x100000)
        builder.set_boot_partition(b"BOOT_PAYLOAD")
        builder.set_partition(1, b"PART_1")
        builder.set_partition(3, b"PART_3_KERNEL")
        builder.set_partition(6, b"PART_6_ROOTFS")

        onenand = builder.build_onenand(max_partitions=6)
        self.assertTrue(len(onenand) > 0x100000)


class TestCxd4108QemuLauncher(unittest.TestCase):
    """Test suite for QEMU argument builder and platform profiles."""

    def test_g3_argument_synthesis(self):
        args = build_g3_qemu_args(
            bootrom_path="/path/to/rom.dat",
            nand_path="/path/to/nand.dat",
            mmc_path="/path/to/mmc.dat",
            headless=True,
            serial_port_base=5000,
        )

        self.assertIn("-machine", args)
        self.assertIn("cxd4108", args)
        self.assertIn("-bios", args)
        self.assertIn("/path/to/rom.dat", args)
        self.assertIn("file=/path/to/nand.dat,if=mtd,format=raw", args)
        self.assertIn("file=/path/to/mmc.dat,if=mtd,format=raw", args)

        # Peripherals verification
        self.assertIn("bionz_sc901572,id=sc901572,bus=/sio0", args)
        self.assertIn("bionz_upd79f,id=upd79f,bus=/sio1", args)
        self.assertIn("bionz_touch_panel,id=touch_panel,bus=/adc0", args)
        self.assertIn("-serial", args)
        self.assertIn("tcp::5000,server,mux", args)

    def test_w90_argument_synthesis(self):
        args = build_w90_qemu_args(
            bootrom_path="/path/to/rom.dat",
            nand_path="/path/to/nand.dat",
            headless=True,
        )

        self.assertIn("-machine", args)
        self.assertIn("cxd4108", args)
        self.assertIn("bionz_mb89083,id=mb89083,bus=/sio0", args)
        self.assertIn("bionz_buttons,id=buttons,bus=/adc0,keys0=druls,keys1=wtmh,keys=p", args)
        # G3 touchscreen should NOT be in W90 args
        self.assertNotIn("bionz_touch_panel,id=touch_panel,bus=/adc0", args)


if __name__ == "__main__":
    unittest.main()
