"""Offline image assembly and QEMU profile experiments.

These helpers do not establish W300 compatibility, boot success or hardware
calibration. Factory layouts are synthetic fixtures.
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
