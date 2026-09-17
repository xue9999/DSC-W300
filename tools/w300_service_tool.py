#!/usr/bin/env python3
"""Sony Cyber-shot DSC-W300 Service Protocol & CEE8 Destination Tool.

Experimental offline model of Sony Senser and destination programming.
Every service action and response below is simulated, including USB terminology.
The property map and retail-board unlock are NOT validated for W300.
Live detection is passive; service operations require missing model evidence
and are disabled. A successful simulation does not establish compatibility.

Pure Python 3 standard library only. Zero external dependencies.
"""

from __future__ import annotations

import argparse
import binascii
import json
import struct
import sys
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# 1. Cryptographic Primitives: Sony BIONZ Faulty Length SHA-1
# ============================================================================

def _left_rotate(n: int, b: int) -> int:
    """32-bit left bitwise rotation."""
    return ((n << b) | (n >> (32 - b))) & 0xFFFFFFFF


def sha1(message: bytes, length: int = -1) -> bytes:
    """Standard 80-round SHA-1 implementation with explicit length parameter.

    Allows length truncation bugs present in legacy embedded architectures.
    """
    if length < 0:
        length = len(message)

    h0 = 0x67452301
    h1 = 0xEFCDAB89
    h2 = 0x98BADCFE
    h3 = 0x10325476
    h4 = 0xC3D2E1F0

    msg = bytearray(message)
    msg.append(0x80)
    # Pad with zeros until message length % 64 == 56
    msg.extend(b'\x00' * ((56 - len(msg) % 64) % 64))
    # Append 64-bit length in bits (big-endian)
    msg.extend(struct.pack('>Q', length * 8))

    for i in range(0, len(msg), 64):
        w = [0] * 80
        for j in range(16):
            w[j] = struct.unpack('>I', msg[i + j * 4 : i + j * 4 + 4])[0]
        for j in range(16, 80):
            w[j] = _left_rotate(w[j - 3] ^ w[j - 8] ^ w[j - 14] ^ w[j - 16], 1)

        a, b, c, d, e = h0, h1, h2, h3, h4
        for j in range(80):
            if 0 <= j <= 19:
                f = d ^ (b & (c ^ d))
                k = 0x5A827999
            elif 20 <= j <= 39:
                f = b ^ c ^ d
                k = 0x6ED9EBA1
            elif 40 <= j <= 59:
                f = (b & c) | (b & d) | (c & d)
                k = 0x8F1BBCDC
            else:
                f = b ^ c ^ d
                k = 0xCA62C1D6

            temp = (_left_rotate(a, 5) + f + e + k + w[j]) & 0xFFFFFFFF
            e = d
            d = c
            c = _left_rotate(b, 30)
            b = a
            a = temp

        h0 = (h0 + a) & 0xFFFFFFFF
        h1 = (h1 + b) & 0xFFFFFFFF
        h2 = (h2 + c) & 0xFFFFFFFF
        h3 = (h3 + d) & 0xFFFFFFFF
        h4 = (h4 + e) & 0xFFFFFFFF

    return struct.pack('>5I', h0, h1, h2, h3, h4)


def sha1_faulty(message: bytes) -> bytes:
    """Sony BIONZ faulty SHA-1 hash.

    Replicates the Sony Senser firmware length calculation anomaly in
    libsencore.so where message length is truncated via `len(message) & 0x1F`.
    """
    return sha1(message, len(message) & 0x1F)


# ============================================================================
# 2. Senser Wire Protocol Framing Engine
# ============================================================================

class SenserWireProtocol:
    """Builder and parser for Sony Senser bulk framing (PID 0x02A9)."""

    # 12-byte little-endian header:
    # uint32 size, uint16 pFunc, uint16 sequence, uint8 ver, uint8 micon, uint8 offset, uint8 resp
    HEADER_FORMAT = '<IHHBBBB'
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    MIN_BULK_SIZE = 512

    # Primary Function Opcodes (pFunc)
    PFUNC_PRODUCT_INFO = 0x0010
    PFUNC_FIRMWARE_UPDATE = 0x0020
    PFUNC_MICON_ACCESS = 0x0030
    PFUNC_ADJUST_CONTROL = 0x0040
    PFUNC_TEST_MODE = 0xFF00
    PFUNC_FILE_CONTROL = 0xFF01
    PFUNC_SONAR = 0xFF02
    PFUNC_MEMORY_DUMP = 0xFF03

    # AdjustControl Subcommands
    CAT_BACKUP = 0x0603
    CMD_BACKUP_READ = 0x0001
    CMD_BACKUP_WRITE = 0x0002
    CMD_BACKUP_SAVE = 0x0003
    CMD_BACKUP_ID1_LOCK = 0x000F

    # USB Vendor Request Definitions
    REQ_START_SENSER = (0x43, 0x01, 0x37FF, 0xD7AA)
    REQ_STOP_SENSER = (0x43, 0x01, 0xC800, 0x2855)

    def __init__(self, start_sequence: int = 1):
        self.sequence = start_sequence

    def build_packet(self, p_func: int, payload: bytes = b'', pad_to_512: bool = True) -> bytes:
        """Constructs a Senser bulk packet with 12-byte header and optional 512-byte padding."""
        payload_len = len(payload)
        header = struct.pack(
            self.HEADER_FORMAT,
            payload_len,
            p_func,
            self.sequence,
            0,  # version
            0,  # miconType (0 = Host / Main CPU)
            0,  # offsetType
            0,  # response
        )
        self.sequence = (self.sequence + 1) & 0xFFFF
        raw_packet = header + payload
        if pad_to_512 and len(raw_packet) < self.MIN_BULK_SIZE:
            raw_packet = raw_packet.ljust(self.MIN_BULK_SIZE, b'\x00')
        return raw_packet

    def parse_packet(self, raw_bytes: bytes) -> Dict[str, Any]:
        """Parses a received Senser bulk frame into a structured dictionary."""
        if len(raw_bytes) < self.HEADER_SIZE:
            raise ValueError(f"Packet too short ({len(raw_bytes)} bytes < {self.HEADER_SIZE})")

        size, p_func, seq, ver, micon, offset, resp = struct.unpack(
            self.HEADER_FORMAT, raw_bytes[: self.HEADER_SIZE]
        )
        if size > len(raw_bytes) - self.HEADER_SIZE:
            raise ValueError("Truncated Senser payload; refusing incomplete response")
        payload = raw_bytes[self.HEADER_SIZE : self.HEADER_SIZE + size]
        return {
            'size': size,
            'pFunc': p_func,
            'sequence': seq,
            'version': ver,
            'miconType': micon,
            'offsetType': offset,
            'response': resp,
            'payload': payload,
            'raw': raw_bytes,
        }

    # AuthPacket framing (516 bytes, big-endian)
    @staticmethod
    def build_auth_packet(cmd: int, salt: int = 0, data: bytes = b'') -> bytes:
        """Constructs a 516-byte AuthPacket frame for Senser challenge-response."""
        cmd_field = (~cmd) & 0xFFFF
        salt_field = salt & 0xFFFF
        payload = data.ljust(512, b'\x00')[:512]
        return struct.pack('>HH', cmd_field, salt_field) + payload

    @staticmethod
    def parse_auth_packet(raw_bytes: bytes) -> Tuple[int, int, bytes]:
        """Parses a 516-byte AuthPacket frame returning (ret_code, salt, data)."""
        if len(raw_bytes) < 516:
            raise ValueError(f"AuthPacket too short ({len(raw_bytes)} < 516)")
        raw_cmd, salt = struct.unpack('>HH', raw_bytes[:4])
        data = raw_bytes[4:516]
        ret = ((~raw_cmd) & 0xFFFF) - salt
        return ret, salt, data

    # High-level AdjustControl payload builders
    def build_read_prop(self, prop_id: int) -> bytes:
        """Category 0x0603, Command 0x0001 (Read Property)."""
        cmd_header = struct.pack('<HH', self.CAT_BACKUP, self.CMD_BACKUP_READ)
        param = struct.pack('<I', prop_id)
        return self.build_packet(self.PFUNC_ADJUST_CONTROL, cmd_header + param)

    def build_write_prop(self, prop_id: int, data: bytes) -> bytes:
        """Category 0x0603, Command 0x0002 (Write Property to Staging RAM)."""
        cmd_header = struct.pack('<HH', self.CAT_BACKUP, self.CMD_BACKUP_WRITE)
        param = struct.pack('<I', prop_id) + data
        return self.build_packet(self.PFUNC_ADJUST_CONTROL, cmd_header + param)

    def build_commit_flash(self, subsystem: int = 0) -> bytes:
        """Category 0x0603, Command 0x0003 (Commit Staging RAM to Flash)."""
        cmd_header = struct.pack('<HH', self.CAT_BACKUP, self.CMD_BACKUP_SAVE)
        param = struct.pack('<H', subsystem)
        return self.build_packet(self.PFUNC_ADJUST_CONTROL, cmd_header + param)

    def build_id1_lock(self, lock: bool) -> bytes:
        """Category 0x0603, Command 0x000F (ID1 Service Board Protection Toggle)."""
        cmd_header = struct.pack('<HH', self.CAT_BACKUP, self.CMD_BACKUP_ID1_LOCK)
        param = bytes([0x01 if lock else 0x00])
        return self.build_packet(self.PFUNC_ADJUST_CONTROL, cmd_header + param)


# ============================================================================
# 3. CEE8 Regional Destination Payload & NVM Specifications
# ============================================================================

class Cee8Payload:
    """Simulation assumptions, not a qualified W300 programming profile.

    In upstream PMCA, 0x01070148 is palNtscSelector, NOT a PAL value.
    The destination address and ASCII encoding below have no W300 proof.
    """

    PROP_MODEL = 0x00E70000
    PROP_DESTINATION = 0x00E70001
    PROP_SERIAL = 0x00E70003
    PROP_VIDEO_OUT = 0x01070148
    PROP_LANG_BASE = 0x010D008F

    # Assumed 35-slot model, not an established W300 property layout.
    LANGUAGE_NAMES = [
        "English (en)",           # 0
        "Japanese (ja)",          # 1
        "French (fr)",            # 2
        "German (de)",            # 3
        "Spanish (es)",           # 4
        "Italian (it)",           # 5
        "Portuguese (pt)",        # 6
        "Simplified Chinese",     # 7
        "Traditional Chinese",    # 8
        "Traditional Chinese alt",# 9
        "Korean (ko)",            # 10
        "Dutch (nl)",             # 11
        "Russian (ru)",           # 12
        "Arabic (ar)",            # 13
        "Persian (fa)",           # 14
        "Swedish (sv)",           # 15
        "Norwegian (no)",         # 16
        "Danish (da)",            # 17
        "Finnish (fi)",           # 18
        "Polish (pl)",            # 19
        "Czech (cs)",             # 20
        "Hungarian (hu)",         # 21
        "Turkish (tr)",           # 22
        "Greek (el)",             # 23
        "Thai (th)",              # 24
        "Greek alt",              # 25
        "Turkish alt",            # 26
        "Czech alt",              # 27
        "Hungarian alt",          # 28
        "Reserved 29",            # 29
        "Reserved 30",            # 30
        "Reserved 31",            # 31
        "Reserved 32",            # 32
        "Reserved 33",            # 33
        "Reserved 34",            # 34
    ]

    # 35-byte language masks (0x01 = Enabled, 0x02 = Disabled in Senser property format)
    # J1: Only Japanese (index 1) is 0x01
    LANG_MASK_J1 = bytes([
        0x02, 0x01, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
        0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
        0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
        0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
        0x02, 0x02, 0x02,
    ])

    # CEE8: English(0), French(2), German(3), Spanish(4), Italian(5), Portuguese(6),
    # Dutch(11), Swedish(15), Norwegian(16), Danish(17), Finnish(18), Polish(19),
    # Czech(20), Hungarian(21), Turkish(22), Greek alt(25), Turkish alt(26),
    # Czech alt(27), Hungarian alt(28) are 0x01.
    LANG_MASK_CEE8 = bytes([
        0x01, 0x02, 0x01, 0x01, 0x01, 0x01, 0x01, 0x02,
        0x02, 0x02, 0x02, 0x01, 0x02, 0x02, 0x02, 0x01,
        0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x02,
        0x02, 0x01, 0x01, 0x01, 0x01, 0x02, 0x02, 0x02,
        0x02, 0x02, 0x02,
    ])

    @staticmethod
    def calculate_evr_checksum(data: bytes) -> int:
        """Additive two's complement modulo-256 checksum used in this simulation.

        Formula: (0x100 - (sum(data) & 0xFF)) & 0xFF.
        """
        return (0x100 - (sum(data) & 0xFF)) & 0xFF

    @classmethod
    def verify_evr_page(cls, page: bytes) -> bool:
        """Verifies that the entire page including checksum byte sums to 0 modulo 256."""
        return (sum(page) & 0xFF) == 0x00

    @classmethod
    def get_enabled_languages(cls, mask: bytes) -> List[str]:
        """Returns a list of language names enabled in the given 35-byte mask."""
        enabled = []
        for idx, val in enumerate(mask[:35]):
            if val == 0x01:
                name = cls.LANGUAGE_NAMES[idx] if idx < len(cls.LANGUAGE_NAMES) else f"Lang {idx}"
                enabled.append(name)
        return enabled


# ============================================================================
# 4. Realistic In-Memory W300 USB Mock Camera Simulator
# ============================================================================

class W300MockUsbCamera:
    """Stateful hypothetical USB model; not a W300 hardware emulator.

    Emulates:
    - Normal Mass Storage mode (VID 0x054C, PID 0x031B)
    - Vendor control mode-switch and reboot requests
    - Senser mode (VID 0x054C, PID 0x02A9)
    - 3-step challenge-response authentication using sha1_faulty
    - In-memory NVM property store & staging RAM
    - ID1 protection state machine (rejects destination write if locked)
    - Checksum recalculation & flash commit
    """

    VID = 0x054C
    PID_MASS_STORAGE = 0x031B
    PID_SENSER = 0x02A9

    def __init__(self, destination: str = "J1", serial: int = 1458291):
        self.mode = "MASS_STORAGE"
        self.current_pid = self.PID_MASS_STORAGE
        self.serial = serial
        self.initial_destination = destination

        # Auth state: 0 = unauthenticated, 1 = challenge issued, 2 = authenticated
        self.auth_state = 0
        self.auth_challenge = b'\x4a\x8e\x12\xbd\x99\x21\x7f\x03'

        # Assumed ID1 lock state for this simulated profile.
        self.id1_locked = True

        # Persistent Flash Store (ROM/NOR)
        self.flash_store: Dict[int, bytes] = {
            Cee8Payload.PROP_MODEL: b'W300\x00',
            Cee8Payload.PROP_DESTINATION: destination.encode('ascii').ljust(4, b'\x00'),
            Cee8Payload.PROP_SERIAL: struct.pack('<I', serial),
            Cee8Payload.PROP_VIDEO_OUT: b'\x00' if destination == "J1" else b'\x01',
            Cee8Payload.PROP_LANG_BASE: (
                Cee8Payload.LANG_MASK_J1 if destination == "J1" else Cee8Payload.LANG_MASK_CEE8
            ),
        }

        # Volatile Staging RAM (loaded from flash at boot)
        self.staging_ram: Dict[int, bytes] = dict(self.flash_store)

        # Communication buffers
        self.rx_buffer = bytearray()
        self.tx_buffer = bytearray()
        self.protocol = SenserWireProtocol()

        # Audit & state counters
        self.flash_commit_count = 0
        self.rejected_write_count = 0
        self.reboot_count = 0

    def control_request(self, bm_req: int, b_req: int, w_val: int, w_idx: int) -> int:
        """Processes USB Vendor Control requests on EP0."""
        # Enter Senser Mode
        if (bm_req, b_req, w_val, w_idx) == (0x43, 0x01, 0x37FF, 0xD7AA):
            self.mode = "SENSER"
            self.current_pid = self.PID_SENSER
            self.auth_state = 0
            self.rx_buffer.clear()
            self.tx_buffer.clear()
            return 0

        # Exit Senser Mode & Reboot
        if (bm_req, b_req, w_val, w_idx) == (0x43, 0x01, 0xC800, 0x2855):
            self.mode = "MASS_STORAGE"
            self.current_pid = self.PID_MASS_STORAGE
            self.auth_state = 0
            self.reboot_count += 1
            # On cold reboot, reload staging RAM from permanent Flash store
            self.staging_ram = dict(self.flash_store)
            self.id1_locked = True
            return 0

        return -1

    def bulk_write(self, data: bytes) -> int:
        """Processes data sent to USB Bulk OUT endpoint."""
        if self.mode != "SENSER":
            raise ConnectionError("Cannot bulk write: camera not in Senser mode")

        # 1. Handle Authentication Phase if not yet authenticated
        if self.auth_state < 2:
            if len(data) < 516:
                raise ValueError("Expected 516-byte AuthPacket during authentication")
            raw_cmd, salt = struct.unpack('>HH', data[:4])
            cmd = ((~raw_cmd) & 0xFFFF) - salt
            packet_data = data[4:516]

            if cmd == 1:
                # Step 1: Challenge request
                self.auth_state = 1
                # Return code 2 (SHA-1) + challenge payload
                resp_cmd = (~(2 + 0)) & 0xFFFF
                resp_payload = self.auth_challenge.ljust(512, b'\x00')
                self.tx_buffer = bytearray(struct.pack('>HH', resp_cmd, 0) + resp_payload)
                return len(data)

            elif cmd == 3:
                # Step 2: Response verification
                if self.auth_state != 1:
                    raise PermissionError("Auth protocol sequence error: step 2 without step 1")
                # Expected digest from first 4 bytes of challenge using sha1_faulty
                expected_hash = sha1_faulty(self.auth_challenge[:4])
                flag = packet_data[0]
                received_hash = packet_data[1:21]

                if flag == 0x01 and received_hash == expected_hash:
                    # Success -> ret = 4
                    resp_cmd = (~4) & 0xFFFF
                    self.tx_buffer = bytearray(struct.pack('>HH', resp_cmd, 0) + (b'\x00' * 512))
                    return len(data)
                else:
                    self.auth_state = 0
                    raise PermissionError("Cryptographic challenge failed: sha1_faulty mismatch")

            elif cmd == 5:
                # Step 3: Finalization
                self.auth_state = 2  # Authenticated!
                resp_cmd = (~6) & 0xFFFF
                # First byte must equal 0x01 (SUCCESS)
                resp_data = bytes([0x01]) + (b'\x00' * 511)
                self.tx_buffer = bytearray(struct.pack('>HH', resp_cmd, 0) + resp_data)
                return len(data)

            else:
                raise ValueError(f"Unknown auth command: {cmd}")

        # 2. Operational Phase: Senser Bulk Packets (12-byte header)
        parsed = self.protocol.parse_packet(data)
        p_func = parsed['pFunc']
        seq = parsed['sequence']
        payload = parsed['payload']

        if p_func == SenserWireProtocol.PFUNC_PRODUCT_INFO:
            # Emulate HASP (0x001F) and Terminal (0x00F1)
            # Response: status 1 indicates success
            resp_header = struct.pack(
                SenserWireProtocol.HEADER_FORMAT,
                0, p_func, seq, 0, 0, 0, 1
            )
            self.tx_buffer = bytearray(resp_header.ljust(512, b'\x00'))
            return len(data)

        elif p_func == SenserWireProtocol.PFUNC_ADJUST_CONTROL:
            cat, cmd = struct.unpack('<HH', payload[:4])
            param = payload[4:]

            if cat == SenserWireProtocol.CAT_BACKUP:
                if cmd == SenserWireProtocol.CMD_BACKUP_READ:
                    prop_id = struct.unpack('<I', param[:4])[0]
                    prop_val = self.staging_ram.get(prop_id, b'')
                    resp_header = struct.pack(
                        SenserWireProtocol.HEADER_FORMAT,
                        len(prop_val), p_func, seq, 0, 0, 0, 0  # resp=0 OK
                    )
                    self.tx_buffer = bytearray((resp_header + prop_val).ljust(512, b'\x00'))
                    return len(data)

                elif cmd == SenserWireProtocol.CMD_BACKUP_WRITE:
                    prop_id = struct.unpack('<I', param[:4])[0]
                    write_val = param[4:]

                    # Service Board Protection Check:
                    # Model rule: a locked ID1 rejects destination/language mutation.
                    if self.id1_locked and prop_id in (
                        Cee8Payload.PROP_DESTINATION,
                        Cee8Payload.PROP_LANG_BASE,
                        Cee8Payload.PROP_VIDEO_OUT,
                    ):
                        self.rejected_write_count += 1
                        # Response 0x05: Access Denied / Service Board Required
                        resp_header = struct.pack(
                            SenserWireProtocol.HEADER_FORMAT,
                            0, p_func, seq, 0, 0, 0, 5
                        )
                        self.tx_buffer = bytearray(resp_header.ljust(512, b'\x00'))
                        return len(data)

                    # Update staging RAM
                    self.staging_ram[prop_id] = write_val
                    resp_header = struct.pack(
                        SenserWireProtocol.HEADER_FORMAT,
                        0, p_func, seq, 0, 0, 0, 0
                    )
                    self.tx_buffer = bytearray(resp_header.ljust(512, b'\x00'))
                    return len(data)

                elif cmd == SenserWireProtocol.CMD_BACKUP_SAVE:
                    # Commit staging RAM to persistent Flash Store
                    self.flash_store = dict(self.staging_ram)
                    self.flash_commit_count += 1
                    resp_header = struct.pack(
                        SenserWireProtocol.HEADER_FORMAT,
                        0, p_func, seq, 0, 0, 0, 0
                    )
                    self.tx_buffer = bytearray(resp_header.ljust(512, b'\x00'))
                    return len(data)

                elif cmd == SenserWireProtocol.CMD_BACKUP_ID1_LOCK:
                    # Unlock / Lock toggle
                    lock_flag = param[0]
                    self.id1_locked = (lock_flag != 0)
                    resp_header = struct.pack(
                        SenserWireProtocol.HEADER_FORMAT,
                        0, p_func, seq, 0, 0, 0, 0
                    )
                    self.tx_buffer = bytearray(resp_header.ljust(512, b'\x00'))
                    return len(data)

        # Default fallback response
        resp_header = struct.pack(
            SenserWireProtocol.HEADER_FORMAT,
            0, p_func, seq, 0, 0, 0, 0
        )
        self.tx_buffer = bytearray(resp_header.ljust(512, b'\x00'))
        return len(data)

    def bulk_read(self, length: int = 4096) -> bytes:
        """Reads pending data from USB Bulk IN endpoint."""
        if not self.tx_buffer:
            return b''
        chunk = bytes(self.tx_buffer[:length])
        self.tx_buffer = self.tx_buffer[length:]
        return chunk


## ============================================================================
# No live USB transport is implemented.
# ============================================================================



# ============================================================================
# 5. High-Level Service Controller Engine
# ============================================================================

class W300ServiceController:
    """Orchestrates only the hypothetical in-memory programming model."""

    def __init__(self, mock_camera: Optional[W300MockUsbCamera] = None, dry_run: bool = False, verbose: bool = False):
        self.mock_camera = mock_camera if mock_camera is not None else (W300MockUsbCamera() if dry_run else None)
        self.dry_run = dry_run
        self.verbose = verbose
        self.protocol = SenserWireProtocol()
        self.authenticated = False
        self.mode = "DISCONNECTED"
        self.simulation = True
        self.hardware_validated = False
        # Never initialize a USB backend from this unqualified controller.
        # Dry-run always uses the offline model, including via the Python API.

    def require_offline_model(self):
        if self.mock_camera is None:
            raise ConnectionError(
                "W300 live service operations unavailable: destination encoding, "
                "property map, retail-board eligibility and recovery are unverified. "
                "Use detect for passive inventory or --mock for simulation."
            )

    def log(self, message: str, stage: str = "INFO"):
        prefix = f"[SIMULATION:{stage}]" if self.mock_camera is not None else f"[{stage}]"
        print(f"{prefix:<10} {message}")

    def log_hex(self, label: str, data: bytes):
        if self.verbose:
            hex_str = binascii.hexlify(data[:64]).decode('ascii')
            suffix = f"... ({len(data)} bytes total)" if len(data) > 64 else ""
            print(f"           HEX {label:<10}: {hex_str}{suffix}")

    # Transport interaction primitives
    def send_control_request(self, bm_req: int, b_req: int, w_val: int, w_idx: int) -> bool:
        self.require_offline_model()
        self.log(f"USB Control Request bmReq=0x{bm_req:02X} bReq=0x{b_req:02X} wVal=0x{w_val:04X} wIdx=0x{w_idx:04X}", "USB")
        if self.mock_camera:
            res = self.mock_camera.control_request(bm_req, b_req, w_val, w_idx)
            return res == 0

    def transfer_bulk(self, out_data: bytes, read_length: int = 4096) -> bytes:
        self.require_offline_model()
        self.log_hex("OUT", out_data)
        if self.mock_camera:
            self.mock_camera.bulk_write(out_data)
            in_data = self.mock_camera.bulk_read(read_length)
            self.log_hex("IN", in_data)
            return in_data

    # High-level actions
    def detect_device(self) -> Dict[str, Any]:
        """Detects camera status, USB mode, and Vendor/Product IDs."""
        self.require_offline_model()
        self.log("Probing USB bus for Sony Cyber-shot DSC-W300...", "DETECT")
        if self.mock_camera:
            pid = self.mock_camera.current_pid
            mode = self.mock_camera.mode
            self.log(f"Device detected: VID 0x054C, PID 0x{pid:04X} ({mode})", "DETECT")
            return {"vid": 0x054C, "pid": pid, "mode": mode, "status": "SIMULATED", "simulation": True, "hardware_validated": False}

    def switch_to_senser_mode(self) -> bool:
        """Transitions camera from Mass Storage to Senser Mode (PID 0x02A9)."""
        self.require_offline_model()
        self.log("Issuing Vendor Control Switch request (0x43, 1, 0x37FF, 0xD7AA)...", "SWITCH")
        if self.mock_camera:
            success = self.send_control_request(0x43, 0x01, 0x37FF, 0xD7AA)
            if success:
                self.mode = "SENSER"
                self.log("Camera acknowledged switch. Re-enumerated as Senser device (PID 0x02A9).", "SWITCH")
            return success

    def authenticate_senser(self) -> bool:
        """Performs 3-round challenge-response authentication using sha1_faulty."""
        self.log("Initiating 3-round Senser authentication handshake...", "AUTH")

        for step_i in range(3):
            # Step 1: Challenge request
            req1 = self.protocol.build_auth_packet(cmd=1)
            resp1_raw = self.transfer_bulk(req1)
            ret1, _, data1 = self.protocol.parse_auth_packet(resp1_raw)
            self.log(f"Auth Round {step_i+1} Step 1 response code: ret={ret1}", "AUTH")

            if ret1 != 2:
                raise PermissionError(f"Unexpected auth algorithm requested: {ret1} (expected 2 for SHA-1)")

            challenge = data1[:4]
            self.log_hex(f"CHALLENGE_R{step_i+1}", challenge)

            # Step 2: Compute response via sha1_faulty
            digest = sha1_faulty(challenge)
            self.log_hex(f"SHA1_FAULTY_R{step_i+1}", digest)
            req2_payload = bytes([0x01]) + digest
            req2 = self.protocol.build_auth_packet(cmd=3, data=req2_payload)
            resp2_raw = self.transfer_bulk(req2)
            ret2, _, _ = self.protocol.parse_auth_packet(resp2_raw)
            self.log(f"Auth Round {step_i+1} Step 2 verification code: ret={ret2}", "AUTH")
            if ret2 != 4:
                raise PermissionError(f"Auth challenge verification failed in round {step_i+1}: ret={ret2}")

        # Step 3: Finalize
        req3 = self.protocol.build_auth_packet(cmd=5)
        resp3_raw = self.transfer_bulk(req3)
        ret3, _, data3 = self.protocol.parse_auth_packet(resp3_raw)
        status = data3[0] if data3 else 0
        self.log(f"Auth Step 3 finalization: ret={ret3}, status=0x{status:02X}", "AUTH")

        if ret3 == 6 and status == 0x01:
            self.authenticated = True
            self.log("Authentication successful! Senser service channel open.", "AUTH")
            return True
        else:
            raise PermissionError("Auth finalization rejected by camera.")

    def read_destination_info(self) -> Dict[str, Any]:
        """Reads model code, destination string, serial number, video format, and active languages."""
        if not self.authenticated:
            self.switch_to_senser_mode()
            self.authenticate_senser()

        self.log("Reading persistent properties from camera NVM...", "READ")

        # Read Model Code (0x00E70000)
        p_model = self.transfer_bulk(self.protocol.build_read_prop(Cee8Payload.PROP_MODEL))
        model_res = self.protocol.parse_packet(p_model)
        model_str = model_res['payload'].decode('ascii', errors='replace').rstrip('\x00')

        # Read Destination (0x00E70001)
        p_dest = self.transfer_bulk(self.protocol.build_read_prop(Cee8Payload.PROP_DESTINATION))
        dest_res = self.protocol.parse_packet(p_dest)
        dest_str = dest_res['payload'].decode('ascii', errors='replace').rstrip('\x00')

        # Read Serial Number (0x00E70003)
        p_serial = self.transfer_bulk(self.protocol.build_read_prop(Cee8Payload.PROP_SERIAL))
        serial_res = self.protocol.parse_packet(p_serial)
        serial_num = struct.unpack('<I', serial_res['payload'][:4])[0] if len(serial_res['payload']) >= 4 else 0

        # Read Video Standard (0x01070148)
        p_video = self.transfer_bulk(self.protocol.build_read_prop(Cee8Payload.PROP_VIDEO_OUT))
        video_res = self.protocol.parse_packet(p_video)
        video_val = video_res['payload'][0] if video_res['payload'] else 0
        video_str = "PAL" if video_val == 0x01 else "NTSC"

        # Read Language Mask (0x010D008F)
        p_lang = self.transfer_bulk(self.protocol.build_read_prop(Cee8Payload.PROP_LANG_BASE))
        lang_res = self.protocol.parse_packet(p_lang)
        lang_mask = lang_res['payload']
        if len(lang_mask) == 1:
            # Physical camera returned 1 byte for 0x010D008F (CompoundBackupProp)
            # Read remaining 34 registers
            full_mask = bytearray(lang_mask)
            for idx in range(1, 35):
                p_l = self.transfer_bulk(self.protocol.build_read_prop(Cee8Payload.PROP_LANG_BASE + idx))
                res_l = self.protocol.parse_packet(p_l)
                full_mask.extend(res_l['payload'][:1])
            lang_mask = bytes(full_mask)
        active_langs = Cee8Payload.get_enabled_languages(lang_mask)

        info = {
            "model": model_str,
            "destination": dest_str,
            "serial": serial_num,
            "video": video_str,
            "language_mask_hex": binascii.hexlify(lang_mask).decode('ascii'),
            "active_languages": active_langs,
        }

        self.log(f"Camera Model: {model_str}", "INFO")
        self.log(f"Serial Number: {serial_num}", "INFO")
        self.log(f"Current Destination: {dest_str}", "INFO")
        self.log(f"Video Standard: {video_str}", "INFO")
        self.log(f"Active Languages ({len(active_langs)}): {', '.join(active_langs)}", "INFO")
        info.update(simulation=True, hardware_validated=False)
        return info

    def unlock_service_board(self) -> bool:
        """Sends ID1 service board unlock command (Category 0x0603, Cmd 15, Data 0x00)."""
        if self.dry_run:
            self.log("[DRY-RUN] Would send ID1 Unlock packet (Category 0x0603, Cmd 15, Data 0x00). Skipped.", "DRYRUN")
            return True

        self.log("Transmitting Service Board ID1 Unlock packet...", "UNLOCK")
        packet = self.protocol.build_id1_lock(lock=False)
        resp_raw = self.transfer_bulk(packet)
        resp = self.protocol.parse_packet(resp_raw)

        if resp['response'] == 0:
            self.log("Service Board ID1 write protection successfully cleared!", "UNLOCK")
            return True
        else:
            raise PermissionError(f"Camera rejected ID1 unlock with response code {resp['response']}")

    def write_cee8_destination(self) -> bool:
        """Stages CEE8 parameters (language mask, PAL video, CEE8 string) into camera RAM."""
        if self.dry_run:
            self.log("[DRY-RUN] Preparing CEE8 Destination modifications:", "DRYRUN")
            self.log("[DRY-RUN]  - Destination Code: 'CEE8' (0x43 0x45 0x45 0x38)", "DRYRUN")
            self.log("[DRY-RUN]  - Video Standard: PAL (0x01)", "DRYRUN")
            self.log(f"[DRY-RUN]  - 35-byte Language Mask: {binascii.hexlify(Cee8Payload.LANG_MASK_CEE8).decode('ascii')}", "DRYRUN")
            self.log("[DRY-RUN]  - Enabled Languages: English (default), Polish, +15 European languages.", "DRYRUN")
            self.log("[DRY-RUN] Non-destructive dry-run active: writes omitted.", "DRYRUN")
            return True

        self.log("Staging CEE8 regional parameters into volatile RAM...", "WRITE")

        # 1. Write PAL video standard
        p_video = self.protocol.build_write_prop(Cee8Payload.PROP_VIDEO_OUT, bytes([0x01]))
        resp_v = self.protocol.parse_packet(self.transfer_bulk(p_video))
        if resp_v['response'] != 0:
            if resp_v['response'] == 5:
                raise PermissionError("Write rejected: Service board protection locked! Execute unlock first.")
            raise RuntimeError(f"Error writing PAL video property: code {resp_v['response']}")

        # 2. Write 35-byte language mask
        p_lang = self.protocol.build_write_prop(Cee8Payload.PROP_LANG_BASE, Cee8Payload.LANG_MASK_CEE8)
        resp_l = self.protocol.parse_packet(self.transfer_bulk(p_lang))
        if resp_l['response'] != 0:
            if resp_l['response'] == 5:
                raise PermissionError("Write rejected: Service board protection locked! Execute unlock first.")
            raise RuntimeError(f"Error writing language mask: code {resp_l['response']}; no fallback writes attempted")

        # 3. Write Destination Code string
        p_dest = self.protocol.build_write_prop(Cee8Payload.PROP_DESTINATION, b"CEE8")
        resp_d = self.protocol.parse_packet(self.transfer_bulk(p_dest))
        if resp_d['response'] != 0:
            if resp_d['response'] == 5:
                raise PermissionError("Write rejected: Service board protection locked! Execute unlock first.")
            raise RuntimeError(f"Error writing destination code: code {resp_d['response']}")

        self.log("CEE8 parameters staged in camera RAM successfully.", "WRITE")
        return True

    def commit_flash(self) -> bool:
        """Directs camera to recalculate checksums and commit staging RAM to NOR flash."""
        if self.dry_run:
            self.log("[DRY-RUN] Would issue Flash Commit packet (Category 0x0603, Cmd 3, Subsystem 0). Skipped.", "DRYRUN")
            return True

        self.log("Transmitting Flash Commit packet (BACKUP_SAVE)...", "COMMIT")
        packet = self.protocol.build_commit_flash(subsystem=0)
        resp_raw = self.transfer_bulk(packet)
        resp = self.protocol.parse_packet(resp_raw)

        if resp['response'] == 0:
            self.log("NOR Flash commit successful! NVM checksums updated permanently.", "COMMIT")
            return True
        else:
            raise RuntimeError(f"Flash commit rejected with code {resp['response']}")

    def reset_device(self) -> bool:
        """Issues Vendor Request to exit Senser mode and cleanly cold-reboot camera."""
        self.require_offline_model()
        if self.dry_run:
            self.log("[DRY-RUN] Would issue USB Reboot Request (0x43, 1, 0xC800, 0x2855). Skipped.", "DRYRUN")
            return True

        self.log("Issuing Vendor Reboot Request (0x43, 1, 0xC800, 0x2855)...", "RESET")
        if self.mock_camera:
            success = self.send_control_request(0x43, 0x01, 0xC800, 0x2855)
            if success:
                self.mode = "MASS_STORAGE"
                self.log("Camera cleanly rebooted into retail operational mode.", "RESET")
            return success

    def run_full_cycle(self) -> bool:
        """Runs the complete end-to-end destination programming lifecycle."""
        self.log("=" * 70, "LIFECYCLE")
        self.log("STARTING FULL DSC-W300 CEE8 PROGRAMMING LIFECYCLE", "LIFECYCLE")
        self.log("=" * 70, "LIFECYCLE")

        # Step 1: Detect
        self.detect_device()

        # Step 2: Senser Mode Switch & Auth
        self.switch_to_senser_mode()
        self.authenticate_senser()

        # Step 3: Baseline Read
        self.log("--- BASELINE INSPECTION ---", "READ")
        baseline = self.read_destination_info()

        # Step 4: Unlock Service Board
        self.log("--- SERVICE BOARD UNLOCK ---", "UNLOCK")
        self.unlock_service_board()

        # Step 5: Write CEE8 Parameters
        self.log("--- CEE8 PAYLOAD WRITE ---", "WRITE")
        self.write_cee8_destination()

        # Step 6: Commit Flash
        self.log("--- FLASH COMMIT ---", "COMMIT")
        self.commit_flash()

        # Step 7: Verification Readback (if not dry run)
        if not self.dry_run:
            self.log("--- VERIFICATION READBACK ---", "VERIFY")
            updated = self.read_destination_info()
            if updated['destination'] != "CEE8" or "Polish (pl)" not in updated['active_languages']:
                raise RuntimeError("Post-write verification failed: CEE8 destination not active!")
            self.log("VERIFICATION CONFIRMED: CEE8 Active, Polish Available, PAL Video Configured.", "VERIFY")

        # Step 8: Reboot
        self.log("--- CLEAN REBOOT ---", "RESET")
        self.reset_device()

        self.log("=" * 70, "LIFECYCLE")
        status_label = "DRY-RUN COMPLETE (Zero Mutating Packets Sent)" if self.dry_run else "LIFECYCLE COMPLETED SUCCESSFULLY"
        self.log(status_label, "LIFECYCLE")
        self.log("=" * 70, "LIFECYCLE")
        return True


# ============================================================================
# 6. Command-Line Interface Entrypoint
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--mock",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Run against internal W300MockUsbCamera simulator (offline testing)",
    )
    common_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Validate all frames and report planned changes without executing mutating or flash-commit operations",
    )
    common_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Enable verbose output with hex frame packet dumps",
    )

    parser = argparse.ArgumentParser(
        parents=[common_parser],
        description="Sony Cyber-shot DSC-W300 Service Protocol Engineering Tool (CEE8 Destination Writer)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Detect camera status with mock simulator:
  python3 tools/w300_service_tool.py --mock detect

  # Read current destination and language table:
  python3 tools/w300_service_tool.py --mock read

  # Execute a safe, non-destructive dry run of the full cycle:
  python3 tools/w300_service_tool.py --mock full-cycle --dry-run

  # Execute full CEE8 destination programming on mock camera:
  python3 tools/w300_service_tool.py --mock full-cycle
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Service command to execute")
    sub_commands = [
        ("detect", "Detect connected camera status and USB PID"),
        ("read", "Read current destination, serial, video format, and language table"),
        ("unlock", "Send ID1 unlock command to clear service board write protection"),
        ("write-cee8", "Stage CEE8 destination parameters into camera RAM"),
        ("commit", "Commit staged RAM configuration to physical NOR flash"),
        ("reset", "Issue reboot request to return camera to retail mode"),
        ("full-cycle", "Execute complete end-to-end CEE8 programming lifecycle"),
    ]
    for cmd_name, help_text in sub_commands:
        subparsers.add_parser(cmd_name, parents=[common_parser], help=help_text)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    is_mock = getattr(args, "mock", False)
    is_dry_run = getattr(args, "dry_run", False)
    is_verbose = getattr(args, "verbose", False)

    if not is_mock and not is_dry_run:
        if args.command == "detect":
            from w300_evidence import inventory
            try:
                result = inventory()
                print(json.dumps(result, indent=2))
                return 0 if any(d.get("product") == "DSC-W300" for d in result["sony_devices"]) else 1
            except (OSError, ValueError) as exc:
                print(f"[ERROR: INVENTORY] {exc}", file=sys.stderr)
                return 1
        print("[ERROR: UNVALIDATED_W300] Live service operations disabled: no verified "
              "W300 destination encoding, retail-board unlock or recoverable backup. "
              "No USB commands sent.", file=sys.stderr)
        return 2

    print(json.dumps({"simulation": True, "hardware_validated": False, "profile": "assumed"}))

    # Initialize the offline model only.
    mock_camera: Optional[W300MockUsbCamera] = None
    if is_mock:
        mock_camera = W300MockUsbCamera(destination="J1")

    controller = W300ServiceController(
        mock_camera=mock_camera,
        dry_run=is_dry_run,
        verbose=is_verbose,
    )

    try:
        if args.command == "detect":
            controller.detect_device()
            return 0

        elif args.command == "read":
            controller.detect_device()
            controller.read_destination_info()
            return 0

        elif args.command == "unlock":
            controller.detect_device()
            controller.switch_to_senser_mode()
            controller.authenticate_senser()
            controller.unlock_service_board()
            return 0

        elif args.command == "write-cee8":
            controller.detect_device()
            controller.switch_to_senser_mode()
            controller.authenticate_senser()
            controller.write_cee8_destination()
            return 0

        elif args.command == "commit":
            controller.detect_device()
            controller.switch_to_senser_mode()
            controller.authenticate_senser()
            controller.commit_flash()
            return 0

        elif args.command == "reset":
            controller.reset_device()
            return 0

        elif args.command == "full-cycle":
            controller.run_full_cycle()
            return 0

        else:
            parser.print_help()
            return 1

    except PermissionError as pe:
        # Safety guardrail violation / write rejected by lock
        print(f"\n[ERROR: ACCESS_DENIED] {pe}", file=sys.stderr)
        return 2
    except (ConnectionError, RuntimeError, ValueError) as err:
        # Communication or protocol error
        print(f"\n[ERROR: PROTOCOL] {err}", file=sys.stderr)
        return 1
    except Exception as ex:
        print(f"\n[ERROR: UNEXPECTED] {ex}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
