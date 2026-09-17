"""Offline comparative RegionSetting packet encoder. No device or transport access."""
import json
import struct


def custom_packet(sequence, language=0x100, available=0x8100, signal=0):
    """Encode the T100/G3 semantic candidate in verified G3 Senser framing.

    W300 support is unverified. Availability here is a mask, never a group ID.
    Restrict this research helper to the independently checked ENG/JPN masks.
    """
    values = (sequence, language, available, signal)
    if any(type(value) is not int for value in values):
        raise ValueError('All inputs must be integers')
    if not 0 <= sequence <= 0xffff:
        raise ValueError('Sequence must fit a 16-bit field')
    if language not in (0x100, 0x8000):
        raise ValueError('Only verified English/Japanese masks are supported')
    if available not in (0x100, 0x8000, 0x8100) or not available & language:
        raise ValueError('Availability must include the initial language')
    if signal not in (0, 1):
        raise ValueError('Signal must be NTSC=0 or PAL=1')
    return struct.pack('<IHHBBBBBBH4I', 20, 0x40, sequence, 0, 0, 0, 0,
                       0x3f, 0, 0x55, 0xff, language, available, signal)


if __name__ == '__main__':
    print(json.dumps(dict(scope='Offline comparative test vector; W300 unverified',
                         camera_command_sent=False,
                         sequence_zero_hex=custom_packet(0).hex()), indent=2))
