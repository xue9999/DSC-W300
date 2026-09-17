"""Bounded comparative Senser protocol. Transport is injected; no USB imports."""
import struct
import time

HEADER = struct.Struct('<IHHBBBB')
SEGMENT = 0x100000
CHUNK = 0x8000


class ProtocolError(RuntimeError):
    pass


class FileUnavailable(ProtocolError):
    pass


def region_body(signal):
    if type(signal) is not int or signal not in (0, 1):
        raise ValueError('Video standard must be NTSC=0 or PAL=1')
    return setting_body([255, 0x100, 0x8100, signal])


def setting_body(values):
    if len(values) != 4 or any(type(n) is not int or not 0 <= n <= 0xffffffff for n in values):
        raise ValueError('RegionSetting requires four uint32 values')
    return struct.pack('<BBH4I', 0x3f, 0, 0x55, *values)


class Senser:
    """PID0336 file-stream receiver; refuses unverified padding variants."""
    def __init__(self, io, *, deadline=120, clock=time.monotonic):
        self.io = io
        self.sequence = 1
        self.clock = clock
        self.ends = clock() + deadline
        self.failed = False

    def timeout(self):
        remaining = self.ends - self.clock()
        if remaining <= 0:
            raise ProtocolError('Session deadline exceeded')
        return max(1, min(5000, int(remaining * 1000)))

    def exact(self, size):
        result = bytearray()
        while len(result) < size:
            data = self.io.read(size - len(result), self.timeout())
            if not data or len(data) > size - len(result):
                raise ProtocolError('Empty or oversized transfer; stopped')
            result.extend(data)
        return bytes(result)

    def request(self, function, body):
        if self.failed or not 1 <= self.sequence <= 0xffff:
            raise ProtocolError('Session cannot be reused after failure or sequence exhaustion')
        self.io.write(HEADER.pack(len(body), function, self.sequence, 0, 0, 0, 0) + body,
                      self.timeout())

    def header(self, function):
        raw = self.exact(HEADER.size)
        size, func, seq, version, micon, offset, response = HEADER.unpack(raw)
        if (func, seq, version, micon, offset) != (function, self.sequence, 0, 0, 0):
            raise ProtocolError('Response header mismatch')
        return size, response

    def read_file(self, path, limit=16 * 1024 * 1024):
        if not path.startswith('/') or '\0' in path or '..' in path.split('/'):
            raise ValueError('Expected an absolute camera file path')
        encoded = path.encode('ascii')
        if len(encoded) > 240:
            raise ValueError('Camera path too long')
        encoded += bytes(4 - len(encoded) % 4)
        try:
            self.request(0xff01, struct.pack('<HH', 2, len(encoded)) + encoded)
            size, status = self.header(0xff01)
            if status == 0x82 and size == 0:
                self.sequence += 1
                raise FileUnavailable('Camera returned 0x82: file missing or inaccessible')
            if status != 1 or size > limit:
                raise ProtocolError('File response failed or exceeds size limit')
            remaining = size
            output = bytearray()
            while remaining:
                segment = min(remaining, SEGMENT)
                done = 0
                while done < segment:
                    count = min(CHUNK, segment - done)
                    output.extend(self.exact(count))
                    done += count
                    if count % 512 == 0:
                        padding = self.io.read(512, self.timeout())
                        if padding:
                            raise ProtocolError('Expected empty USB terminator; nonempty bytes preserved in trace')
                remaining -= segment
                if remaining:
                    next_size, next_status = self.header(0xff01)
                    if (next_size, next_status) != (remaining, 1):
                        raise ProtocolError('Invalid continuation size or status')
            self.sequence += 1
            return bytes(output)
        except FileUnavailable:
            raise
        except BaseException:
            self.failed = True
            raise

    def change_region(self, signal):
        """Caller must validate a device-specific qualification before invocation."""
        region_body(signal)
        return self.set_region([255, 0x100, 0x8100, signal])

    def set_region(self, values):
        """One native RegionSetting operation; caller owns compatibility/baseline checks."""
        try:
            self.request(0x40, setting_body(values))
            size, status = self.header(0x40)
            if size != 0 or status != 0:
                raise ProtocolError('Unexpected RegionSetting response; do not retry automatically')
            self.sequence += 1
        except BaseException:
            self.failed = True
            raise


def authenticate(io, pid, keys, digest, *, seconds=45, clock=time.monotonic):
    """Seven bounded SHA1 exchanges. No constructors, resets or shell setup."""
    ends = clock() + seconds
    def exchange(command, data=b''):
        remaining = ends - clock()
        if remaining <= 0:
            raise ProtocolError('Authentication deadline exceeded')
        timeout = max(1, min(5000, int(remaining * 1000)))
        io.write(struct.pack('>HH512s', (~command) & 0xffff, 0, data), timeout)
        remaining = ends - clock()
        if remaining <= 0:
            raise ProtocolError('Authentication deadline exceeded')
        response = io.read(516, max(1, min(5000, int(remaining * 1000))))
        if len(response) != 516:
            raise ProtocolError('Authentication record must be exactly 516 bytes')
        cmd, salt, payload = struct.unpack('>HH512s', response)
        if salt:
            raise ProtocolError('Nonzero authentication salt is outside this reviewed profile')
        return (~cmd) & 0xffff, payload
    if len(keys) != 3 or any(len(key) != 512 for key in keys):
        raise ValueError('Invalid pinned authentication keys')
    for key in keys:
        code, challenge = exchange(1)
        if code != 2:
            raise ProtocolError('Expected reviewed SHA1 challenge; no algorithm fallback')
        message = challenge + key if pid == 0x0336 else challenge[:4]
        code, _ = exchange(3, b'\x01' + digest(message))
        if code != 4:
            raise ProtocolError('Authentication digest rejected')
    code, payload = exchange(5)
    if code != 6 or payload[0] != 1:
        raise ProtocolError('Authentication did not complete')
