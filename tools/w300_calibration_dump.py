#!/usr/bin/env python3
"""Sony Cyber-shot DSC-W300 Full Calibration & Configuration Safety Dump Tool.

Performs a bit-for-bit double-read SHA-256 verified safety dump of all
critical non-volatile configuration files and unique factory CCD/optical
calibration data over USB Senser service protocol.

Targets:
  - CCD & Optical Calibration: /boot/factory/Areg.bin & Areg2.bak (Category 5)
  - Regional & Language Configuration: /boot/factory/Hreg.bin & Hreg2.bak (Category 0)
  - Golden Mirror & Anti-tamper NVRAM: /boot/factory/Preg.bin
  - Flash Memory Partition Table & Register Map: /boot/factory/initreg.bin
  - AV Subsystem Parameters: /boot/factory/Asys.bin & Asys2.bak (Category 6)
  - Host Subsystem Parameters: /boot/factory/Hsys.bin & Hsys2.bak (Category 1)
  - User Backup Banks: /boot/backup/Ausr.bin, Ausr2.bak, Husr.bin, Husr2.bak
  - Runtime Brew Config: /boot/factory/brew_cnf.bin
  - Kinoma UI Settings: /boot/dsc/RegionInfo.xml, UserInfo.xml, UserInfo.bak
  - System Firmware Version: /version.txt
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

# Ensure build/w300 is importable
BASE_DIR = Path(__file__).resolve().parent.parent
BUILD_W300 = BASE_DIR / 'build/w300'
if str(BUILD_W300) not in sys.path:
    sys.path.insert(0, str(BUILD_W300))

import region_app as app


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DSC-W300 Full Calibration & Configuration Safety Dump Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--serial', default=None,
                        help='Camera USB serial number (default: auto-detect from connected USB device)')
    parser.add_argument('--experimental-service', action='store_true', required=True,
                        help='Acknowledge experimental Senser service mode operation')
    parser.add_argument('--output', type=Path, default=None,
                        help='Custom directory to store dumped calibration files (default: build/w300/backups/calibration_<serial>)')
    parser.add_argument('--resume-session', type=Path, default=None,
                        help='Prior failed session to resume from')
    parser.add_argument('--mock', action='store_true',
                        help='Run in offline mock mode using reference fixtures')
    parser.add_argument('--include-implementation', action='store_true',
                        help='Also dump proprietary firmware binaries and libraries')
    parser.add_argument('--include-nr-implementation', action='store_true',
                        help='Also read the six stills NR investigation libraries; does not change NR')

    args = parser.parse_args()

    serial = args.serial
    if not args.mock and serial is None:
        try:
            core, util, backend = app.usb_modules()
            dev = app.find_one(core, backend, app.NORMAL_PIDS)
            _, dev_serial = app.device_identity(dev)
            util.dispose_resources(dev)
            serial = dev_serial
        except Exception:
            pass

    effective_serial = serial or 'D386002E4438'
    default_output = args.output
    if default_output is None:
        suffix = ('_nr_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
                  if args.include_nr_implementation else '')
        default_output = BUILD_W300 / 'backups' / f"calibration_{effective_serial}{suffix}"

    sys_argv_backup = sys.argv
    try:
        cmd = [
            'region_app.py',
            'backup-calibration',
            '--experimental-service',
            '--output', str(default_output),
        ]
        if serial:
            cmd.extend(['--serial', serial])
        if args.resume_session:
            cmd.extend(['--resume-session', str(args.resume_session)])
        if args.mock:
            cmd.append('--mock')
        if args.include_implementation:
            cmd.append('--include-implementation')
        if args.include_nr_implementation:
            cmd.append('--include-nr-implementation')

        sys.argv = cmd
        return app.main()
    finally:
        sys.argv = sys_argv_backup


if __name__ == '__main__':
    raise SystemExit(main())
