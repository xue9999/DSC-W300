"""Offline codec for ma1co's published legacy A330 transcript, NOT a W300 map.

No USB import, device opening, addresses, write/save commands or live mode.
Source: Sony-PMCA-RE issue 282, attachments 7953397 and 7998362.
This establishes a protocol research lead only. W300 acceptance is unverified.
"""
import hashlib
import struct


def auth_response(challenge: bytes) -> bytes:
    if len(challenge) != 16:
        raise ValueError('The published challenge has exactly 16 bytes')
    return hashlib.md5(bytes(a ^ b for a, b in zip(challenge, b'USBSENSERKEYOPEN'))).digest()


def auth_request(stage: int, challenge: bytes | None = None) -> bytes:
    if stage == 1 and challenge is None:
        payload = b''
    elif stage == 2 and challenge is not None:
        payload = auth_response(challenge)
    else:
        raise ValueError('Only the two published authentication frames are supported')
    return (struct.pack('>IHHIHH', 3 + len(payload) // 4, 1, 0, 0, 0, stage) + payload).ljust(0x120, b'\0')


def parse_auth_reply(data: bytes, stage: int) -> bytes:
    if stage not in (1, 2) or len(data) < 16:
        raise ValueError('Truncated/invalid authentication reply')
    words, command, status, sequence, subcmd, arg = struct.unpack('>IHHIHH', data[:16])
    size = (words + 1) * 4
    if size < 16 or size > 512 or len(data) < size:
        raise ValueError('Invalid or incomplete advertised response size')
    if command != 1 or status != 0x0100 or subcmd != 0 or arg != stage:
        raise ValueError('Unexpected command, status or authentication stage')
    payload = data[16:size]
    if len(payload) != (16 if stage == 1 else 0):
        raise ValueError('Unexpected authentication payload size')
    return payload
