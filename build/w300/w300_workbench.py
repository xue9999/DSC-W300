"""Windows first-contact preparation. No service, memory or settings writes.

inventory: OS PnP properties. inquiry: ONLY standard SCSI INQUIRY, bounded
to a currently identified DSC-W300 and explicit current USB serial. selftest:
offline dependency/codec checks, not camera compatibility validation.
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
from datetime import datetime, timezone

FROZEN = bool(getattr(sys, 'frozen', False))
BASE = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
UPSTREAM = BASE / 'upstream' / 'Sony-PMCA-RE'
PIN = 'a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0'


def inventory() -> dict:
    portable_engine = BASE / 'runtime' / 'powershell' / 'pwsh.exe'
    bundled_engine = Path(sys.base_prefix).parent / 'native' / 'powershell' / 'pwsh.exe'
    engine = (str(portable_engine) if portable_engine.is_file() else
              str(bundled_engine) if bundled_engine.is_file() and not FROZEN else
              shutil.which('pwsh.exe') if not FROZEN else None)
    if not engine:
        raise RuntimeError('PowerShell 7 used by this prepared environment is missing')
    # Restore normal Windows DLL search while launching the independent shell.
    # A frozen application otherwise exposes its private Python DLL directory.
    saved_dll_directory = ctypes.create_unicode_buffer(32768)
    if FROZEN:
        ctypes.windll.kernel32.GetDllDirectoryW(len(saved_dll_directory), saved_dll_directory)
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    try:
        result = subprocess.run([engine, '-NoLogo', '-NoProfile', '-NonInteractive', '-File',
                                 str(BASE / 'inventory.ps1'), '-JsonOnly'], capture_output=True)
    finally:
        if FROZEN:
            ctypes.windll.kernel32.SetDllDirectoryW(saved_dll_directory.value or None)
    if result.returncode:
        raise RuntimeError('PnP inventory failed: ' + result.stderr.decode('utf-8-sig', errors='replace'))
    data = json.loads(result.stdout.decode('utf-8-sig'))
    data['powershell_executable'] = engine
    return data


def select_w300(data: dict, serial: str) -> dict:
    devices = [d for d in data['sony_devices'] if '&MI_' not in d['instance_id'].upper()]
    if len(devices) != 1:
        raise ValueError('Exactly one current Sony USB device is required; disconnect other Sony devices')
    device = devices[0]
    expected = 'USB\\VID_054C&PID_0341\\' + serial
    if device['instance_id'].upper() != expected.upper() or not serial:
        raise ValueError('Current VID/PID/serial does not match the selected W300; no command sent')
    if device.get('status') != 'OK':
        raise ValueError('PnP device is not OK; no command sent')
    if device.get('description') != 'DSC-W300' and device.get('friendly_name') != 'DSC-W300':
        raise ValueError('OS product descriptor does not identify DSC-W300; no command sent')
    return device


def parse_inquiry(data: bytes) -> dict:
    if len(data) < 36 or 5 + data[4] > len(data):
        raise ValueError('INQUIRY response incomplete')
    if data[0] & 0x1f not in (0, 5):
        raise ValueError('Unexpected peripheral type')
    return {'manufacturer': data[8:16].decode('ascii').strip(),
            'product': data[16:32].decode('ascii').strip(),
            'revision': data[32:36].decode('ascii').strip(),
            'raw_hex': data.hex()}


def inquiry(serial: str, trace: dict) -> dict:
    current = inventory()
    selected = select_w300(current, serial)
    sys.path.insert(0, str(UPSTREAM))
    from pmca.usb.driver.windows.msc import MscContext, SCSI_PASS_THROUGH_DIRECT, SCSI_PASS_THROUGH_DIRECT_WITH_BUFFER
    from win32file import CreateFile, CloseHandle, DeviceIoControl, GENERIC_READ, GENERIC_WRITE, FILE_SHARE_READ, FILE_SHARE_WRITE, OPEN_EXISTING
    candidates = [d for d in MscContext().listDevices(0x054c) if d.idProduct == 0x0341]
    if len(candidates) != 1:
        raise ValueError('Exactly one W300 mass-storage volume is required; keep Microsoft USBSTOR driver for this step')
    device_path = str(candidates[0].handle)
    # Upstream enumeration returns a complete \\.\X: path. Never prepend twice.
    if len(device_path) != 6 or not device_path.startswith('\\\\.\\') or not device_path[4].isalpha() or device_path[5] != ':':
        raise ValueError('Unexpected native volume path; no camera command sent')
    # Recheck identity immediately before opening the selected volume.
    if select_w300(inventory(), serial)['instance_id'] != selected['instance_id']:
        raise ValueError('Device identity changed during selection')
    transactions = trace.setdefault('transactions', [])
    trace.update(selected_pnp_device=selected, volume=device_path)
    def read_standard_inquiry(size: int, handle) -> bytes:
        if not 5 <= size <= 255:
            raise ValueError('INQUIRY size out of bounds')
        buffer = (ctypes.c_ubyte * size)()
        cdb = bytes((0x12, 0, 0, 0, size, 0))
        transaction = {'cdb_hex': cdb.hex(), 'direction': 'IN', 'requested': size, 'state': 'prepared'}
        transactions.append(transaction)
        packet = SCSI_PASS_THROUGH_DIRECT_WITH_BUFFER(sptd=SCSI_PASS_THROUGH_DIRECT(
            Length=ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT), CdbLength=6, DataIn=1,
            DataTransferLength=size, DataBuffer=ctypes.cast(buffer, ctypes.c_void_p),
            TimeOutValue=5, SenseInfoLength=32,
            SenseInfoOffset=SCSI_PASS_THROUGH_DIRECT_WITH_BUFFER.ucSenseBuf.offset,
            Cdb=(ctypes.c_ubyte * 16).from_buffer_copy(cdb.ljust(16, b'\0'))))
        try:
            transaction['state'] = 'submitted'
            response = DeviceIoControl(handle, 0x4d014, packet, ctypes.sizeof(packet))
        except Exception as exc:
            transaction.update(state='failed', error=str(exc))
            raise
        returned = SCSI_PASS_THROUGH_DIRECT_WITH_BUFFER.from_buffer_copy(response)
        actual = returned.sptd.DataTransferLength
        transaction.update(state='returned', returned=actual, scsi_status=returned.sptd.ScsiStatus,
                           sense_hex=bytes(returned.ucSenseBuf).hex(), response_hex=bytes(buffer)[:min(actual,size)].hex())
        if returned.sptd.ScsiStatus != 0 or not 0 < actual <= size:
            raise ValueError('INQUIRY failed; status=%d sense=%s; no retry or fallback' % (returned.sptd.ScsiStatus, bytes(returned.ucSenseBuf).hex()))
        value = bytes(buffer)[:actual]
        return value
    handle = CreateFile(device_path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    try:
        first = read_standard_inquiry(5, handle)
        if len(first) != 5 or not 31 <= first[4] <= 250:
            raise ValueError('Invalid INQUIRY length; stopped')
        info = parse_inquiry(read_standard_inquiry(5 + first[4], handle))
    finally:
        CloseHandle(handle)
    if info['manufacturer'].upper() != 'SONY':
        raise ValueError('INQUIRY manufacturer mismatch; stopped')
    return {'selected_pnp_device': selected, 'volume': device_path, 'inquiry': info,
            'transactions': transactions, 'scope': 'Standard identification only; no service entry or vendor commands',
            'w300_language_function_verified': False, 'camera_setting_write_performed': False}


def selftest() -> dict:
    import libusb_package
    from legacy_codec import auth_response, auth_request, parse_auth_reply
    sys.path.insert(0, str(UPSTREAM))
    from pmca.usb.driver.windows.msc import MscContext
    from pmca.usb.driver.windows.wpd import MtpContext
    from pmca.usb.driver.windows.driverless import VendorSpecificContext
    backend = libusb_package.get_libusb1_backend()
    if backend is None:
        raise RuntimeError('Bundled libusb DLL failed to load')
    challenge = bytes.fromhex('7ef0f51f86e7bca5309b826db1b7bc8f')
    expected = '172f1588efa2c0435e493fb5f7d0b052'
    if auth_response(challenge).hex() != expected:
        raise RuntimeError('Published A330 authentication transcript does not reproduce')
    reply = bytes.fromhex('0000000700010100ffffffff00000001') + challenge
    if parse_auth_reply(reply, 1) != challenge or auth_request(2, challenge)[16:32].hex() != expected:
        raise RuntimeError('Legacy authentication frame check failed')
    if FROZEN:
        packaged_pins = json.loads((BASE / 'source-pins.json').read_text(encoding='utf-8'))
        revision = packaged_pins['pmca_commit']
        pinned_files = packaged_pins['reviewed_files']
        source_check = 'Packaged reviewed source hashes and recorded build revision; no Git dependency'
    else:
        revision = subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
        source_manifest = json.loads((BASE.parents[1] / 'sources' / 'manifest.json').read_text(encoding='utf-8'))
        pinned_files = next(a for a in source_manifest['artifacts'] if a['path'] == 'sources/Sony-PMCA-RE')['reviewed_files']
        source_check = 'Live Git revision and original reviewed source hashes'
    if revision != PIN:
        raise RuntimeError('PMCA source revision changed')
    if not all(hashlib.sha256((UPSTREAM / f['path']).read_bytes()).hexdigest() == f['sha256'] for f in pinned_files):
        raise RuntimeError('PMCA reviewed source bytes do not match the preserved source pins')
    return {'python': sys.version, 'platform': platform.platform(), 'pmca_commit': revision,
            'frozen_portable_executable': FROZEN, 'source_revision_check': source_check,
            'native_driver_imports': [MscContext.__name__, MtpContext.__name__, VendorSpecificContext.__name__],
            'libusb_dll_loaded': str(libusb_package.get_library_path()),
            'dependencies': {n: importlib.metadata.version(n) for n in ['pyusb','pywin32','comtypes','libusb-package']},
            'published_a330_authentication_replay': 'PASS', 'pmca_source_pin': 'PASS',
            'pmca_reviewed_source_hashes': 'PASS',
            'camera_communication_tested': False, 'w300_language_function_verified': False,
            'camera_setting_write_performed': False,
            'scope': 'Host runtime and offline transcript verification; no camera calls'}


def main() -> int:
    # A redirected Windows console can default to a code page which cannot
    # represent the user's extraction path. JSON and report paths use UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('selftest')
    commands.add_parser('inventory')
    p = commands.add_parser('inquiry', help='Standard INQUIRY only; requires live OS identification and current serial')
    p.add_argument('--serial', required=True)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    result = {'captured_at': datetime.now(timezone.utc).isoformat(), 'operation': args.command}
    try:
        result['result'] = selftest() if args.command == 'selftest' else inventory() if args.command == 'inventory' else inquiry(args.serial, result)
        result['ok'] = True
    except Exception as exc:
        result.update(ok=False, error_type=type(exc).__name__, error=str(exc), scope='No language-changing operation implemented')
    report = BASE / 'reports' / (args.command + '-' + stamp + '.json')
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=True))
    print('Report:', report)
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
