"""QEMU Launcher and Command Generator for Sony CXD4108 Emulation.

Handles discovery of the custom QEMU binary (ma1co/qemu), device configuration
for DSC-G3 (touchscreen/PMIC) and DSC-W90/T100 (buttons/MB89083), and argument
generation for both headless CI testing and interactive debugging.

Zero external dependencies - 100% standard library.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


def check_machine_cxd4108(qemu_bin: Path) -> bool:
    """Verify if the QEMU binary supports the Sony cxd4108 machine."""
    try:
        res = subprocess.run(
            [str(qemu_bin), "-machine", "help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "cxd4108" in res.stdout
    except Exception:
        return False


def find_qemu_binary(custom_path: Optional[str] = None) -> Optional[Path]:
    """Locate the qemu-system-arm executable with cxd4108 support.
    
    Search order:
      1. Explicit user-provided path
      2. Local compiled binary in sources/qemu/arm-softmmu/qemu-system-arm
      3. System PATH (only if cxd4108 supported)
    """
    if custom_path:
        p = Path(custom_path)
        if p.is_file() and os.access(p, os.X_OK):
            return p.resolve()

    # Check local repository sources/qemu build tree
    local_build = Path("sources/qemu/arm-softmmu/qemu-system-arm")
    if local_build.is_file() and os.access(local_build, os.X_OK):
        return local_build.resolve()

    # Check system PATH
    system_bin = shutil.which("qemu-system-arm")
    if system_bin:
        p = Path(system_bin).resolve()
        if check_machine_cxd4108(p):
            return p

    return None


def build_g3_qemu_args(
    bootrom_path: Optional[str] = None,
    nand_path: Optional[str] = None,
    mmc_path: Optional[str] = None,
    kernel_path: Optional[str] = None,
    initrd_path: Optional[str] = None,
    headless: bool = True,
    qmp_stdio: bool = True,
    serial_port_base: int = 4321,
) -> List[str]:
    """Generate complete qemu-system-arm CLI arguments for Sony DSC-G3."""
    args = [
        "-machine", "cxd4108",
        "-icount", "shift=4",
    ]

    if bootrom_path:
        args += ["-bios", str(bootrom_path)]
    if kernel_path:
        args += ["-kernel", str(kernel_path)]
    if initrd_path:
        args += ["-initrd", str(initrd_path)]
    if nand_path:
        args += ["-drive", f"file={nand_path},if=mtd,format=raw"]
    if mmc_path:
        args += ["-drive", f"file={mmc_path},if=mtd,format=raw"]

    # DSC-G3 Specific Hardware Peripherals:
    # 1. Power IC (Renesas SC901572 on SIO0)
    args += [
        "-device", "bionz_sc901572,id=sc901572,bus=/sio0",
        "-connect-gpio", "odev=gpio1,onum=1,idev=sc901572,iname=ssi-gpio-cs",
    ]
    # 2. Battery Authenticator (NEC uPD79F on SIO1)
    args += [
        "-device", "bionz_upd79f,id=upd79f,bus=/sio1",
        "-connect-gpio", "odev=gpios,onum=4,idev=upd79f,iname=ssi-gpio-cs",
    ]
    # 3. Battery Voltage ADC sensor
    args += [
        "-device", "analog_voltage,id=batt_sens,bus=/adc0,channel=5,value=128",
    ]
    # 4. Buttons (Tele/Wide zoom + Playback button on ADC0)
    args += [
        "-device", "bionz_buttons,id=buttons,bus=/adc0,keys0=tw,keys=p",
        "-connect-gpio", "odev=buttons,idev=sc901572,iname=play",
    ]
    # 5. Resistive Touch Panel Controller on ADC0 / GPIO3
    args += [
        "-device", "bionz_touch_panel,id=touch_panel,bus=/adc0",
        "-connect-gpio", "odev=gpio3,onum=5,idev=touch_panel,inum=0",
        "-connect-gpio", "odev=gpio3,onum=6,idev=touch_panel,inum=1",
    ]

    if headless:
        args += ["-display", "none"]
        if qmp_stdio:
            args += ["-qmp", "stdio"]
        args += ["-serial", f"tcp::{serial_port_base},server,mux"]

    return args


def build_w90_qemu_args(
    bootrom_path: Optional[str] = None,
    nand_path: Optional[str] = None,
    kernel_path: Optional[str] = None,
    initrd_path: Optional[str] = None,
    headless: bool = True,
    qmp_stdio: bool = True,
    serial_port_base: int = 4321,
) -> List[str]:
    """Generate complete qemu-system-arm CLI arguments for Sony DSC-W90 / DSC-T100."""
    args = [
        "-machine", "cxd4108",
        "-icount", "shift=4",
    ]

    if bootrom_path:
        args += ["-bios", str(bootrom_path)]
    if kernel_path:
        args += ["-kernel", str(kernel_path)]
    if initrd_path:
        args += ["-initrd", str(initrd_path)]
    if nand_path:
        args += ["-drive", f"file={nand_path},if=mtd,format=raw"]

    # DSC-W90/T100 Hardware Peripherals:
    # 1. Power IC (Fujitsu MB89083 on SIO0)
    args += [
        "-device", "bionz_mb89083,id=mb89083,bus=/sio0",
        "-connect-gpio", "odev=gpio1,onum=1,idev=mb89083,iname=ssi-gpio-cs",
    ]
    # 2. Battery Authenticator (NEC uPD79F on SIO1)
    args += [
        "-device", "bionz_upd79f,id=upd79f,bus=/sio1",
        "-connect-gpio", "odev=gpios,onum=4,idev=upd79f,iname=ssi-gpio-cs",
    ]
    # 3. D-Pad & Control Buttons
    args += [
        "-device", "bionz_buttons,id=buttons,bus=/adc0,keys0=druls,keys1=wtmh,keys=p",
        "-connect-gpio", "odev=buttons,idev=mb89083,iname=play",
    ]

    if headless:
        args += ["-display", "none"]
        if qmp_stdio:
            args += ["-qmp", "stdio"]
        args += ["-serial", f"tcp::{serial_port_base},server,mux"]

    return args


class Cxd4108QemuLauncher:
    """CLI orchestrator for Sony CXD4108 emulation."""

    def __init__(self, qemu_bin: Optional[str] = None):
        self.qemu_bin = find_qemu_binary(qemu_bin)

    def is_available(self) -> bool:
        return self.qemu_bin is not None

    def get_status(self) -> Dict[str, Union[bool, str]]:
        openmemories_dir = Path("sources/OpenMemories-CI")
        qemu_dir = Path("sources/qemu")
        fwtool_dir = Path("sources/fwtool.py")
        extracted_g3 = Path("evidence/extracted_g3")

        return {
            "qemu_available": self.is_available(),
            "qemu_binary": str(self.qemu_bin) if self.qemu_bin else "Not found",
            "openmemories_ci_cloned": openmemories_dir.is_dir(),
            "qemu_source_cloned": qemu_dir.is_dir(),
            "fwtool_cloned": fwtool_dir.is_dir(),
            "g3_extracted_evidence": extracted_g3.is_dir(),
        }


def main():
    parser = argparse.ArgumentParser(description="CXD4108 QEMU Emulator Launcher & Stager")
    subparsers = parser.add_subparsers(dest="command")

    # Command: status
    subparsers.add_parser("status", help="Check status of QEMU binary and cloned upstreams")

    # Command: print-args
    cmd_args = subparsers.add_parser("print-args", help="Generate and print QEMU CLI arguments")
    cmd_args.add_argument("--model", choices=["g3", "w90", "t100"], default="g3", help="Camera model target")
    cmd_args.add_argument("--nand", help="Path to nand.dat")
    cmd_args.add_argument("--mmc", help="Path to mmc.dat")
    cmd_args.add_argument("--bootrom", help="Path to rom.dat / bootrom")
    cmd_args.add_argument("--interactive", action="store_true", help="Launch in interactive graphical mode")

    args = parser.parse_args()

    launcher = Cxd4108QemuLauncher()

    if args.command == "status" or not args.command:
        status = launcher.get_status()
        print("CXD4108 Emulation Subsystem Status:")
        for k, v in status.items():
            print(f"  {k:25}: {v}")
        if not status["qemu_available"]:
            print("\nNote: To compile the CXD4108 QEMU binary:")
            print("  cd sources/qemu")
            print("  ./configure --target-list=arm-softmmu --disable-docs --disable-tools --disable-user")
            print("  make -j$(sysctl -n hw.ncpu)")
        return 0

    elif args.command == "print-args":
        headless = not args.interactive
        if args.model == "g3":
            qargs = build_g3_qemu_args(
                bootrom_path=args.bootrom,
                nand_path=args.nand,
                mmc_path=args.mmc,
                headless=headless,
            )
        else:
            qargs = build_w90_qemu_args(
                bootrom_path=args.bootrom,
                nand_path=args.nand,
                headless=headless,
            )
        bin_name = str(launcher.qemu_bin) if launcher.qemu_bin else "qemu-system-arm"
        cmd_str = f"{bin_name} " + " ".join(f"'{a}'" if " " in a or "," in a else a for a in qargs)
        print("Generated QEMU invocation command:\n")
        print(cmd_str)
        return 0


if __name__ == "__main__":
    sys.exit(main())
