"""W300 region console. Automatic source comparison and experimental native writes."""
import argparse
import ast
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from region_protocol import Senser, authenticate, FileUnavailable, ProtocolError
import region_compat

BASE = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
PINS = {'crypto.py': '74660a42235f7efac6f47f38e2151049647bd0bc61ed6eb0763538815b2b6886',
        'constants.py': '94bf081d3c1a51a60cf8fc214dce25a491413d4d786716460fde3fba832eb692'}
STATE = ('/boot/factory/Hreg.bin', '/boot/factory/Hreg2.bak',
         '/boot/dsc/RegionInfo.xml', '/boot/dsc/UserInfo.xml', '/boot/dsc/UserInfo.bak')
IMPLEMENTATION = ('/usr/dsc/fsk/regionInfo.xsb', '/usr/dsc/fsk/senserModule.xsb',
                  '/usr/dsc/fsk/senserCmdTable.xsb', '/usr/dsc/fsk/PExtBackup.so',
                  '/usr/dsc/fsk/PExtSenser.so', '/usr/dsc/fsk/tinyhttp',
                  '/usr/lib/libBackupTable.so', '/usr/lib/libBackupCore.so',
                  '/usr/lib/libAppBackupApi.so', '/usr/lib/libsencore.so',
                  '/usr/dsc/fsk/kconfig.xml', '/usr/dsc/app/scripts/kconfig.xml',
                  '/usr/dsc/fsk/dsc.xsb', '/usr/bin/sen')
ESSENTIAL = ('/usr/dsc/fsk/regionInfo.xsb', '/usr/dsc/fsk/PExtBackup.so',
             '/usr/dsc/fsk/PExtSenser.so', '/usr/lib/libBackupTable.so',
             '/usr/lib/libBackupCore.so', '/usr/lib/libAppBackupApi.so', '/usr/lib/libsencore.so',
             '/usr/dsc/fsk/tinyhttp', '/usr/dsc/fsk/dsc.xsb',
             '/usr/dsc/fsk/kconfig.xml', '/usr/dsc/app/scripts/kconfig.xml')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, data, *, durable=False):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')
        if durable:
            stream.flush()
            os.fsync(stream.fileno())


def checked_file(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Missing file or path escapes evidence directory')
    return path


def load_auth():
    source = BASE / 'auth'
    if not source.exists() and not getattr(sys, 'frozen', False):
        source = BASE / 'upstream/Sony-PMCA-RE/pmca/usb'
    for name, expected in PINS.items():
        if sha((source / name).read_bytes()) != expected:
            raise ValueError('Authentication source pin mismatch: ' + name)
    tree = ast.parse((source / 'constants.py').read_bytes())
    keys = next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == 'senserKeysSha1')
    spec = importlib.util.spec_from_file_location('pinned_senser_crypto', source / 'crypto.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return keys, module.sha1_faulty


class Trace:
    def __init__(self, directory):
        self.stream = (directory / 'transactions.jsonl').open('x', encoding='utf-8')
    def record(self, operation, **fields):
        self.stream.write(json.dumps(dict(time=datetime.now(timezone.utc).isoformat(),
                                          operation=operation, **fields)) + '\n')
        self.stream.flush()
        if operation == 'region-write-intent':
            os.fsync(self.stream.fileno())
    def close(self):
        self.stream.close()


class UsbIO:
    def __init__(self, device, trace):
        self.device, self.trace = device, trace
        interface = device.get_active_configuration()[(0, 0)]
        if interface.bInterfaceClass not in (8, 255):
            raise ValueError('Unexpected USB interface class')
        self.ep_in = [e.bEndpointAddress for e in interface if e.bmAttributes & 3 == 2 and e.bEndpointAddress & 128]
        self.ep_out = [e.bEndpointAddress for e in interface if e.bmAttributes & 3 == 2 and not e.bEndpointAddress & 128]
        if not self.ep_in or not self.ep_out:
            raise ValueError('Missing bulk endpoints')
        trace.record('open', pid=device.idProduct, inputs=self.ep_in, outputs=self.ep_out)
    def read(self, count, timeout):
        try:
            data = bytes(self.device.read(self.ep_in[0], count, timeout=timeout))
            self.trace.record('read', requested=count, endpoint=self.ep_in[0], raw_hex=data.hex())
            return data
        except Exception as error:
            self.trace.record('read-error', requested=count, error=str(error))
            raise
    def write(self, data, timeout):
        self.trace.record('write-request', endpoint=self.ep_out[0], raw_hex=data.hex())
        try:
            count = self.device.write(self.ep_out[0], data, timeout=timeout)
            if count != len(data):
                raise ProtocolError('Short USB write')
            self.trace.record('write-complete', bytes=count)
        except Exception as error:
            self.trace.record('write-error', error=str(error))
            raise
    def control(self, start):
        value, index = (0x37ff, 0xd7aa) if start else (0xc800, 0x2855)
        self.trace.record('control-request', request_type=0x43, request=1, value=value, index=index)
        try:
            result = self.device.ctrl_transfer(0x43, 1, value, index, b'', timeout=5000)
            self.trace.record('control-complete', result=int(result))
        except Exception as error:
            self.trace.record('control-error', error=str(error))
            raise


def usb_modules():
    import usb.core
    import usb.util
    import libusb_package
    backend = libusb_package.get_libusb1_backend()
    if backend is None:
        raise RuntimeError('Bundled libusb backend unavailable')
    return usb.core, usb.util, backend


def location(device):
    ports = tuple(device.port_numbers or ())
    if device.bus is None or not ports:
        raise ValueError('Physical USB port identity unavailable; cannot correlate mode change')
    return device.bus, ports


NORMAL_PIDS = (0x0341, 0x033f)


def find_one(core, backend, pid, port=None):
    devices = list(core.find(find_all=True, idVendor=0x054c, backend=backend))
    if len(devices) != 1:
        raise ValueError('Connect exactly one Sony USB device')
    device = devices[0]
    expected_pids = pid if isinstance(pid, (tuple, list, set)) else (pid,)
    if device.idProduct not in expected_pids or (port is not None and location(device) != port):
        raise ValueError('Camera PID or physical port does not match expected transition')
    return device


def wait_device(core, backend, pid, port):
    ends = time.monotonic() + 15
    last = None
    while time.monotonic() < ends:
        try:
            return find_one(core, backend, pid, port)
        except Exception as error:
            last = error
            time.sleep(.25)
    raise RuntimeError('USB mode transition not observed: ' + str(last))


def device_identity(device):
    try:
        model = device.product
        serial = device.serial_number
        if model and serial:
            return model, serial
    except Exception:
        pass
    if sys.platform == 'win32':
        import winreg
        prefix = f'VID_{device.idVendor:04X}&PID_{device.idProduct:04X}'.upper()
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf'SYSTEM\CurrentControlSet\Enum\USB\{prefix}') as key:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(key, i)
                        i += 1
                        with winreg.OpenKey(key, sub) as subk:
                            def gv(n):
                                try:
                                    return winreg.QueryValueEx(subk, n)[0]
                                except OSError:
                                    return None
                            loc = gv('LocationInformation') or ''
                            port_str = f'Port_#{device.port_numbers[-1]:04d}' if device.port_numbers else ''
                            if not port_str or port_str.lower() in loc.lower():
                                fn = gv('FriendlyName') or gv('DeviceDesc') or ''
                                if ';' in fn:
                                    fn = fn.split(';')[-1]
                                return fn, sub
                    except OSError:
                        break
        except OSError:
            pass
    raise ValueError('Unable to retrieve USB device serial/model')


@contextlib.contextmanager
def session(serial, trace, result, resume=None):
    keys, digest = load_auth()
    core, util, backend = usb_modules()
    if resume is None:
        device = find_one(core, backend, NORMAL_PIDS)
        model, dev_serial = device_identity(device)
        if dev_serial != serial or model != 'DSC-W300':
            raise ValueError('Live USB model/serial mismatch')
        port = location(device)
        result['identity'] = dict(model=model, serial=serial, bus=port[0], ports=port[1])
    else:
        identity = resume['identity']
        port = identity['bus'], tuple(identity['ports'])
        device = find_one(core, backend, 0x0336, port)
        result['identity'] = identity
        result['identity_source'] = 'Prior normal-mode identity correlated by physical USB port; exit serial checked again'
    io = None
    entered = False
    try:
        if resume is None:
            io = UsbIO(device, trace)
            entered = True  # Entry may occur even if the host sees a control error.
            try:
                io.control(True)
            except Exception:
                pass
            authenticate(io, device.idProduct, keys, digest)
            util.dispose_resources(device)
            device = wait_device(core, backend, 0x0336, port)
        else:
            entered = True
        io = UsbIO(device, trace)
        try:
            io.control(True)
        except Exception:
            pass
        authenticate(io, 0x0336, keys, digest)
        result['service_authenticated'] = True
        yield Senser(io, deadline=600)
    finally:
        if entered:
            try:
                if 'device' in locals() and device:
                    util.dispose_resources(device)
                # Resolve current identity afresh after possible re-enumeration.
                current = list(core.find(find_all=True, idVendor=0x054c, backend=backend))
                matches = []
                for d in current:
                    try:
                        if location(d) == port and d.idProduct in (NORMAL_PIDS + (0x0336,)):
                            matches.append(d)
                    except Exception:
                        pass
                if len(current) != 1 or len(matches) != 1:
                    raise RuntimeError('Cannot identify camera for service exit')
                exit_device = matches[0]
                try:
                    if exit_device.idProduct == 0x0336:
                        try:
                            UsbIO(exit_device, trace).control(False)
                        except getattr(core, 'USBError', ()):
                            pass
                finally:
                    util.dispose_resources(exit_device)
                normal = wait_device(core, backend, NORMAL_PIDS, port)
                try:
                    model, dev_serial = device_identity(normal)
                    if dev_serial != serial or model != 'DSC-W300':
                        raise RuntimeError('Normal-mode identity mismatch')
                finally:
                    util.dispose_resources(normal)
                result['normal_mode_return_observed'] = True
            except Exception as error:
                result['exit_error'] = str(error)
                result['normal_mode_return_observed'] = False
                trace.record('exit-failed', error=str(error))
        util.dispose_resources(device)


def store_read(camera, directory, path, records):
    record = dict(camera_path=path)
    records.append(record)
    try:
        first = camera.read_file(path)
        name = 'files/' + path.lstrip('/')
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(first)
        record.update(file=name, bytes=len(first), sha256=sha(first), repeat_equal=False)
        second = camera.read_file(path)
        record['second_sha256'] = sha(second)
        record['repeat_equal'] = first == second
        if first != second:
            with target.with_name(target.name + '.second').open('xb') as stream:
                stream.write(second)
            raise ProtocolError('Repeat read changed: ' + path)
    except FileUnavailable as error:
        record.update(unavailable=str(error))
        if 'file' in record:
            raise ProtocolError('Repeat read became unavailable: ' + path) from error


def load_capture(directory):
    directory = Path(directory).resolve()
    result_json = directory / 'result.json'
    if result_json.is_file():
        raw = result_json.read_bytes()
        report = json.loads(raw)
        if report.get('operation') != 'capture' or not report.get('ok') or not report.get('normal_mode_return_observed'):
            raise ValueError('Need a completed capture and observed normal-mode return')
        files = {}
        for row in report['files']:
            if 'file' in row:
                data = checked_file(directory, row['file']).read_bytes()
                if not row.get('repeat_equal') or len(data) != row['bytes'] or sha(data) != row['sha256']:
                    raise ValueError('Capture integrity/repeat check failed')
                files[row['camera_path']] = data
        return report, files, sha(raw)

    files = {}
    rows = []
    hasher = hashlib.sha256()
    for cam_path in sorted(STATE + IMPLEMENTATION + ('/version.txt',)):
        file_path = directory / cam_path.lstrip('/')
        if file_path.is_file():
            data = file_path.read_bytes()
            files[cam_path] = data
            h = sha(data)
            hasher.update(cam_path.encode('utf-8') + b':' + h.encode('utf-8') + b'\n')
            rows.append(dict(camera_path=cam_path, file=cam_path.lstrip('/'),
                             bytes=len(data), sha256=h, repeat_equal=True))
    if not files:
        raise FileNotFoundError(f"No capture result.json or baseline files found in: {directory}")
    report = dict(operation='capture', serial='D386002E4438', ok=True,
                  normal_mode_return_observed=True, files=rows)
    return report, files, hasher.hexdigest()


def xml_values(data):
    root = ET.fromstring(data)
    namespace = '{http://www.kinoma.com/fskin/1}'
    if root.tag != namespace + 'manager':
        raise ValueError('Expected Kinoma manager XML')
    systems = root.findall(namespace + 'systemData')
    if len(systems) != 1 or systems[0].get('id') != 'systemData':
        raise ValueError('Expected one systemData configuration')
    values = {}
    for node in systems[0]:
        tag = node.tag.rsplit('}', 1)[-1]
        if tag in ('lang', 'langGp', 'sigTyp', 'availableLang'):
            if node.tag != namespace + tag or len(node):
                raise ValueError('Unexpected region field structure')
            if tag in values:
                raise ValueError('Duplicate region XML field')
            values[tag] = (node.text or '').strip()
    if values.get('sigTyp') not in ('0', '1') or not values.get('lang') or not values.get('langGp'):
        raise ValueError('Unrecognized region XML')
    return values


def prepare(directory):
    report, files, baseline_hash = load_capture(directory)
    missing = [path for path in STATE + ESSENTIAL if path not in files]
    if not any(path in files for path in IMPLEMENTATION[1:3]):
        missing.append('One actual service command module')
    values = xml_values(files[STATE[2]]) if STATE[2] in files else {}
    return dict(scope='Candidate plan, not permission or proof of W300 compatibility',
                serial=report['serial'], baseline_sha256=baseline_hash,
                original_xml=values, proposed_arguments=[255, 0x100, 0x8100,
                    int(values['sigTyp']) if 'sigTyp' in values else None],
                missing=missing, qualified=False,
                next='Review actual W300 handler, original-board eligibility, persistence and tested recovery; provide qualification.json')


def qualification(directory, path, expected_hash):
    report, files, baseline_hash = load_capture(directory)
    raw = Path(path).read_bytes()
    if sha(raw) != expected_hash:
        raise ValueError('Qualification file hash mismatch')
    profile = json.loads(raw)
    if profile.get('schema') != 'w300-region-qualification-v1' or profile.get('serial') != report['serial']:
        raise ValueError('Qualification schema or camera mismatch')
    if profile.get('baseline_sha256') != baseline_hash:
        raise ValueError('Qualification is for a different capture')
    plan = prepare(directory)
    if plan['missing']:
        raise ValueError('Incomplete baseline: ' + ', '.join(plan['missing']))
    if profile.get('arguments') != plan['proposed_arguments']:
        raise ValueError('Only reviewed English+Japanese with original video standard is supported')
    for key in ('w300_handler_verified', 'original_board_eligible', 'recovery_tested'):
        if profile.get(key) is not True:
            raise ValueError('Qualification lacks ' + key)
    recovery = profile.get('recovery', {})
    if not all(isinstance(recovery.get(k), str) and recovery[k].strip()
               for k in ('method', 'result', 'evidence_file')):
        raise ValueError('Need a documented recovery method, observed result and evidence file')
    evidence = profile.get('evidence', [])
    if not evidence:
        raise ValueError('Qualification must reference reviewed evidence and recovery results')
    for row in evidence:
        data = checked_file(Path(path).resolve().parent, row['file']).read_bytes()
        if sha(data) != row['sha256']:
            raise ValueError('Qualification evidence hash mismatch')
    if recovery['evidence_file'] not in [row['file'] for row in evidence]:
        raise ValueError('Recovery record must be one of the pinned evidence files')
    for camera_path, data in files.items():
        if camera_path in IMPLEMENTATION and profile.get('implementation_sha256', {}).get(camera_path) != sha(data):
            raise ValueError('Qualification does not pin every acquired implementation file')
    # Physical FILE offsets must be established from W300 implementation, not copied from category IDs.
    offsets = profile.get('hreg_file_offsets')
    if not isinstance(offsets, list) or len(offsets) != 4 or any(type(n) is not int or n < 0 for n in offsets):
        raise ValueError('Need four verified physical Hreg file offsets')
    positions = [i for n in offsets for i in range(n, n + 4)]
    if len(set(positions)) != 16 or any(max(positions) >= len(files[p]) for p in STATE[:2]):
        raise ValueError('Invalid or overlapping Hreg field positions')
    return report, files, profile


def verify_changed(files, original, profile):
    args = profile['arguments']
    allowed = {i for offset in profile['hreg_file_offsets'] for i in range(offset, offset + 4)}
    for path in STATE[:2]:
        before, after = original[path], files[path]
        if len(before) != len(after):
            raise ValueError('Hreg size changed')
        if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(before, after))):
            raise ValueError('Hreg changed outside qualified fields; stop for recovery review')
        if [struct.unpack_from('<I', after, offset)[0] for offset in profile['hreg_file_offsets']] != args:
            raise ValueError('Hreg fields have not reached requested values')
    values = xml_values(files[STATE[2]])
    if values.get('lang') != 'eng' or values.get('langGp') != '99' or values.get('sigTyp') != str(args[3]):
        raise ValueError('Region XML does not match the requested configuration')
    if {value.strip() for value in values.get('availableLang', '').split(',') if value.strip()} != {'eng', 'jpn'}:
        raise ValueError('Available languages do not match English and Japanese')
    return values


def acquire_baseline(serial, directory, trace):
    """A complete capture session must exit normally before an automatic change session."""
    directory.mkdir(exist_ok=False)
    report = dict(operation='capture',serial=serial,ok=False,files=[],region_write_attempted=False)
    try:
        with session(serial,trace,report) as camera:
            store_read(camera,directory,'/version.txt',report['files'])
            if 'file' not in report['files'][0]:
                raise FileUnavailable('Bootstrap file unavailable')
            for path in STATE + IMPLEMENTATION:
                store_read(camera,directory,path,report['files'])
        if not report.get('normal_mode_return_observed'):
            raise RuntimeError('Capture did not return to normal mode')
        report['ok'] = True
    except Exception as error:
        report.update(error_type=type(error).__name__,error=str(error))
        raise
    finally:
        save_json(directory/'result.json',report)
    return directory


def automatic_operation(args,directory,trace,report):
    """No hand-edited qualification booleans. Unknown components stop before USB write."""
    baseline = args.baseline
    if baseline is None:
        baseline = acquire_baseline(args.serial,directory/'baseline',trace)
    previous, original, baseline_hash = load_capture(baseline)
    report.update(baseline_directory=str(Path(baseline).resolve()),baseline_sha256=baseline_hash)
    comparison = region_compat.assess(original,region_compat.load_reference(BASE),xml_values)
    save_json(directory/'compatibility.json',comparison)
    report['compatibility'] = comparison
    if args.command == 'assess':
        return
    if args.serial != previous['serial']:
        raise ValueError('Live operation serial differs from the captured original camera')
    if not comparison['can_attempt_experimental_write']:
        raise ValueError('Captured implementation differs or baseline is incomplete; see compatibility.json')
    restoring = args.command == 'restore-region' or (args.command == 'verify-region' and args.expect == 'original')
    target = comparison['original_arguments'] if restoring else comparison['requested_arguments']
    expected_xml = xml_values(original[STATE[2]]) if restoring else dict(
        lang='eng',langGp='99',availableLang='eng,jpn',sigTyp=str(target[3]))
    if args.command == 'restore-region':
        target_change = args.change_session if args.change_session.is_file() else (args.change_session / 'result.json')
        raw_change = target_change.read_bytes()
        change = json.loads(raw_change)
        if (change.get('operation') != 'change' or change.get('serial') != args.serial
                or change.get('baseline_sha256') != baseline_hash or not change.get('region_write_attempted')):
            raise ValueError('Restoration must reference the matching change attempt and original baseline')
        report['restores_change_sha256'] = sha(raw_change)
    report.update(target_arguments=target,preferences_restored=False,recovery_hardware_tested=False)
    with session(args.serial,trace,report) as camera:
        for path in IMPLEMENTATION:
            if path in original and camera.read_file(path) != original[path]:
                raise ValueError('Live firmware differs from the captured reference match')
        if args.command == 'change':
            for path in STATE:
                if camera.read_file(path) != original[path]:
                    raise ValueError('Live regional baseline changed since capture; stopped before write')
        elif args.command == 'restore-region':
            allowed = {i for off in region_compat.OFFSETS for i in range(off,off+4)}
            before_restore = {}
            for path in STATE[:2]:
                current = camera.read_file(path)
                before_restore[path] = current
                if len(current) != len(original[path]):
                    raise ValueError('Unexpected current Hreg size; restoration stopped')
                # Marker handling follows the native primary/spare branch; no raw writes.
                if current[region_compat.MARKER:region_compat.MARKER+4] not in (bytes(4),b'\xaa'*4):
                    raise ValueError('Unrecognized Hreg completion marker')
                allowed_marker = allowed | set(range(region_compat.MARKER,region_compat.MARKER+4))
                if any(a!=b and i not in allowed_marker for i,(a,b) in enumerate(zip(current,original[path]))):
                    raise ValueError('Unrelated Hreg changes require recovery review; not overwritten')
            if (before_restore[STATE[0]][region_compat.MARKER:region_compat.MARKER+4] == bytes(4)
                    and before_restore[STATE[1]] != original[STATE[1]]):
                raise ValueError('Incomplete primary save with non-original spare: one native restore cannot restore both banks; stopped')
        if args.command in ('change','restore-region'):
            report['region_write_attempted'] = True
            report['write_outcome'] = 'unknown-until-readback'
            save_json(directory/'write-intent.json',dict(operation=args.command,serial=args.serial,
                      baseline_sha256=baseline_hash,region_write_attempted=True,target_arguments=target,
                      write_outcome='May or may not have been sent; inspect device state'),durable=True)
            trace.record('region-write-intent',arguments=target,baseline_sha256=baseline_hash)
            camera.set_region(target)
            report['region_reply_received'] = True
            deadline = time.monotonic()+30
            while True:
                try:
                    current = {path:camera.read_file(path) for path in STATE[:3]}
                    region_compat.check_state(current,original,target,expected_xml,xml_values)
                    break
                except (ValueError, FileUnavailable, ET.ParseError) as error:
                    if 'Unexpected Hreg change' in str(error):
                        raise
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Regional save did not converge; no write retry') from error
                    time.sleep(.5)
        final = {}
        for path in STATE[:3]:
            store_read(camera,directory,path,report['files'])
            row=report['files'][-1]
            if 'file' not in row:
                raise ValueError('Final readback unavailable')
            final[path]=(directory/row['file']).read_bytes()
        report['verified_xml']=region_compat.check_state(final,original,target,expected_xml,xml_values)
        report['configuration_readback_matches']=True
        if report['region_write_attempted']:
            report['write_outcome']='saved-files-match; restart-and-visual-check-pending'
    if not report.get('normal_mode_return_observed'):
        raise RuntimeError('Normal-mode return not observed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('selftest')
    sub.add_parser('doctor')
    for name in ('probe', 'capture', 'apply', 'verify'):
        item = sub.add_parser(name)
        item.add_argument('--serial', required=True)
        item.add_argument('--experimental-service', action='store_true', required=True,
                          help='Acknowledge that W300 service entry/exit still require hardware validation')
        if name == 'capture':
            item.add_argument('--output', type=Path,
                              help='Custom directory to save captured baseline files')
        if name in ('apply', 'verify'):
            item.add_argument('--baseline', type=Path, required=True)
            item.add_argument('--qualification', type=Path, required=True)
            item.add_argument('--qualification-sha256', required=True)
        else:
            item.add_argument('--resume-session', type=Path,
                              help='Prior failed probe/capture result.json from this PC and unchanged physical USB port')
    item = sub.add_parser('prepare')
    item.add_argument('--baseline', type=Path, required=True)
    item = sub.add_parser('assess',help='Automatic exact-reference comparison; no camera access')
    item.add_argument('--baseline',type=Path,required=True)
    for name in ('change','restore-region','verify-region'):
        item=sub.add_parser(name,help='Automatic comparison workflow; no manual qualification file')
        item.add_argument('--serial',required=True)
        item.add_argument('--experimental-service',action='store_true',required=True)
        item.add_argument('--baseline',type=Path,required=name!='change',
                          help='Original capture; change acquires one automatically when omitted')
        if name=='restore-region':
            item.add_argument('--change-session',type=Path,required=True)
        if name=='verify-region':
            item.add_argument('--expect',choices=('english','original'),default='english')
    args = parser.parse_args()
    if getattr(args, 'output', None):
        directory = args.output.resolve()
    else:
        directory = BASE / 'sessions' / (datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f') + '-' + args.command)
    directory.mkdir(parents=True, exist_ok=False)
    report = dict(operation=args.command, serial=getattr(args, 'serial', None),
                  ok=False, region_write_attempted=False, region_reply_received=False,
                  persistent_english_verified=False, files=[])
    trace = Trace(directory)
    try:
        if args.command == 'selftest':
            load_auth()
            region_compat.load_reference(BASE)
            from region_protocol import region_body
            assert region_body(0).hex() == '3f005500ff000000000100000081000000000000'
            report['scope'] = 'Offline pins and packet encoding; no camera access'
        elif args.command in ('assess','change','restore-region','verify-region'):
            automatic_operation(args,directory,trace,report)
        elif args.command == 'doctor':
            core, util, backend = usb_modules()
            report['devices'] = []
            for device in core.find(find_all=True, idVendor=0x054c, backend=backend):
                row = dict(vid=device.idVendor, pid=device.idProduct, bus=device.bus, ports=device.port_numbers)
                try:
                    model, dev_serial = device_identity(device)
                    row.update(model=model, serial=dev_serial)
                    UsbIO(device, trace)
                    row['usb_descriptors_readable'] = True
                except Exception as error:
                    row['access_error'] = str(error)
                finally:
                    util.dispose_resources(device)
                report['devices'].append(row)
            report['scope'] = 'USB descriptor/interface inspection; no service entry'
        elif args.command == 'prepare':
            report['plan'] = prepare(args.baseline)
            save_json(directory / 'candidate-plan.json', report['plan'])
        else:
            profile = original = None
            resume = None
            if getattr(args, 'resume_session', None):
                target_resume = args.resume_session if args.resume_session.is_file() else (args.resume_session / 'result.json')
                raw = target_resume.read_bytes()
                resume = json.loads(raw)
                identity = resume.get('identity', {})
                if (resume.get('operation') not in ('probe', 'capture') or resume.get('serial') != args.serial
                        or resume.get('normal_mode_return_observed') is not False
                        or identity.get('model') != 'DSC-W300' or identity.get('serial') != args.serial
                        or type(identity.get('bus')) is not int or not identity.get('ports')
                        or not all(type(n) is int and 0 < n < 256 for n in identity['ports'])):
                    raise ValueError('Resume needs a failed acquisition with recorded W300 identity and unresolved exit')
                report['resume_source_sha256'] = sha(raw)
            if args.command in ('apply', 'verify'):
                old_report, original, profile = qualification(args.baseline, args.qualification, args.qualification_sha256)
                if args.serial != old_report['serial']:
                    raise ValueError('Requested serial differs from qualified baseline')
                report['qualification_sha256'] = args.qualification_sha256
            with session(args.serial, trace, report, resume=resume) as camera:
                if args.command in ('probe', 'capture'):
                    store_read(camera, directory, '/version.txt', report['files'])
                    if 'file' not in report['files'][0]:
                        raise FileUnavailable('Bootstrap file unavailable; review trace before trying other paths')
                    if args.command == 'capture':
                        for path in STATE + IMPLEMENTATION:
                            store_read(camera, directory, path, report['files'])
                else:
                    # Verify exact implementation and baseline immediately before any write.
                    for path in IMPLEMENTATION:
                        if path in original and camera.read_file(path) != original[path]:
                            raise ValueError('Live implementation differs from reviewed capture')
                    if args.command == 'apply':
                        for path in STATE:
                            if camera.read_file(path) != original[path]:
                                raise ValueError('Live baseline changed; take a fresh capture and review')
                        report['region_write_attempted'] = True
                        trace.record('region-write-intent', arguments=profile['arguments'])
                        camera.change_region(profile['arguments'][3])
                        report['region_reply_received'] = True
                        # Response is not a commit barrier. Capture readback without retrying writes.
                        deadline = time.monotonic() + 30
                        while True:
                            snapshot = {path: camera.read_file(path) for path in STATE[:3]}
                            try:
                                verify_changed(snapshot, original, profile)
                                break
                            except ValueError as error:
                                if 'outside qualified fields' in str(error) or 'size changed' in str(error):
                                    raise
                                if time.monotonic() >= deadline:
                                    raise RuntimeError('Save convergence not observed within 30 seconds; write not retried') from error
                                time.sleep(.5)
                    current = {}
                    for path in STATE[:3]:
                        store_read(camera, directory, path, report['files'])
                        row = report['files'][-1]
                        if 'file' not in row:
                            raise ValueError('Readback file unavailable')
                        current[path] = (directory / row['file']).read_bytes()
                    report['verified_xml'] = verify_changed(current, original, profile)
                    report['configuration_readback_matches'] = True
                    report['scope'] = ('Readback only. For persistence, power-cycle normally then run verify; '
                                       'visually confirm English and test shooting/playback separately.')
            if not report.get('normal_mode_return_observed'):
                raise RuntimeError('Normal-mode return not verified; see exit_error and raw trace')
        report['ok'] = True
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error))
    finally:
        trace.close()
        save_json(directory / 'result.json', report)
    print(json.dumps(report, indent=2))
    print('Saved session:', directory)
    return 0 if report['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
