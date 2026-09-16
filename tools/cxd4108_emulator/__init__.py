"""Sony CXD4108 BIONZ Emulation & Flash Staging Tooling.

This package bridges decrypted Sony Cyber-shot DSC-G3 and DSC-W90/W300 firmware
artifacts with the OpenMemories QEMU hardware emulation platform.
"""

from .flash_builder import (
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
)
from .qemu_launcher import (
    Cxd4108QemuLauncher,
    find_qemu_binary,
    build_g3_qemu_args,
    build_w90_qemu_args,
)

__all__ = [
    "SDM_MAGIC",
    "SDM_VERSION",
    "SECTOR_SIZE",
    "SPARE_SIZE",
    "SECTORS_PER_BLOCK",
    "DEFAULT_NAND_SIZE",
    "write_sdm_partition_table",
    "pack_onenand_image",
    "build_factory_partition2",
    "build_mbr_image",
    "Cxd4108FlashBuilder",
    "Cxd4108QemuLauncher",
    "find_qemu_binary",
    "build_g3_qemu_args",
    "build_w90_qemu_args",
]
