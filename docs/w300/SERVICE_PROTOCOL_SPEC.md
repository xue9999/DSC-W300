# Experimental Service Protocol Model: DSC-W300 CEE8 Research

> HARDWARE STATUS: UNVALIDATED. The text below contains simulation assumptions,
> not a qualified W300 procedure. No W300 evidence establishes ASCII CEE8 at
> property 0x00E70001 or a retail-board bypass via ID1. Upstream PMCA calls
> 0x01070148 `palNtscSelector`; treating it as PAL/NTSC output mode is unsupported.
> Upstream authenticates before waiting for service re-enumeration, unlike the
> experimental transport below. Do not execute these sequences on hardware.
> The CLI now makes detect passive, makes dry-run offline, and rejects live
> service operations pending independent model-specific evidence.

**Document Identifier**: `DSC-W300-SVC-SPEC-V1.0`  
**Target Hardware**: Sony Cyber-shot DSC-W300 (Model Code: `0x00E70000`, BIONZ / CXD4108 Architecture)  
**Target Regional Configuration**: `CEE8` (Central/Eastern Europe: Default English, Selectable Polish, PAL Video Format)  
**Baseline Hardware State**: Retail Japanese Domestic Market (`J1` destination, Japanese-only UI, NTSC Video Format, SY-199 Main Board)  
**Applicability**: Software-level service protocol engineering, non-invasive USB communication, zero hardware/board modification  

---

## 1. Architectural Overview & System Taxonomy

The Sony Cyber-shot DSC-W300 relies on a specialized service architecture engineered by Sony EMCS for factory configuration, board replacement adjustments, and calibration. This specification formalizes the physical transport, wire framing, authentication, memory abstractions, regional mapping, and execution sequence required to program the `CEE8` destination on retail hardware.

```
+----------------------------------------------------------------------------------------------------+
|                                      DSC-W300 SERVICE ARCHITECTURE                                 |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [USB Stage 1: Mass Storage / Retail Boot]          [USB Stage 2: Service Mode / Senser Boot]       |
|   VID: 0x054C, PID: 0x031B                           VID: 0x054C, PID: 0x02A9                       |
|   USB Mass Storage Class (0x08)                      Vendor-Specific Class (0xFF / 0x00)           |
|   Bulk-Only Transport (BOT)                          Raw Bulk Endpoints (EP1 OUT, EP1 IN)          |
|                  |                                                  |                              |
|                  |  bmRequestType: 0x43 (Vendor Out)                |                              |
|                  |  bRequest:      0x01                             |                              |
|                  |  wValue:        0x37FF                           |                              |
|                  |  wIndex:        0xD7AA                           |                              |
|                  +------------------------------------------------->|                              |
|                     (USB Control Mode-Switch Trigger)               |                              |
|                                                                     v                              |
|                                                     [3-Step Cryptographic Handshake]                |
|                                                      516-byte AuthPacket (Big-Endian)              |
|                                                      SHA-1 BIONZ Faulty Length Bug                 |
|                                                                     |                              |
|                                                                     v                              |
|                                                     [Senser Wire Protocol Framing]                 |
|                                                      12-byte SenserPacketHeader (Little-Endian)    |
|                                                      512-byte Bulk Boundary Padding                |
|                                                                     |                              |
|                                     +-------------------------------+------------------------------+
|                                     |                               |                              |
|                                     v                               v                              |
|                      [pFunc 0x0010: ProductInfo]     [pFunc 0x0040: AdjustControl]                 |
|                       HASP Dongle Query (0x001F)      Category 0x0603 Subcommands:                 |
|                       Terminal Enable   (0x00F1)       - Read Property     (Cmd 0x0001)            |
|                                                        - Write Property RAM (Cmd 0x0002)           |
|                                                        - Commit/Save Flash (Cmd 0x0003)            |
|                                                        - Unlock ID1 Guard  (Cmd 0x000F)            |
|                                                                     |                              |
|                                                                     v                              |
|                                                      [NVM Staging RAM / NOR Flash]                 |
|                                                       Model Code:   0x00E70000                     |
|                                                       PAL/NTSC:     0x01070148                     |
|                                                       Languages:    0x010D008F - 0x010D00B1 (35B)  |
|                                                       EVR Formula:  (0x100 - sum) & 0xFF           |
|                                                                     |                              |
|                  +--------------------------------------------------+                              |
|                  |  bmRequestType: 0x43 (Vendor Out)                                               |
|                  |  bRequest:      0x01                                                            |
|                  |  wValue:        0xC800 (~0x37FF)                                                |
|                  |  wIndex:        0x2855 (~0xD7AA)                                                |
|                  v                                                                                 |
|  [Clean Reboot into Retail Mode with English Default & Selectable Polish]                          |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. USB Transport & Senser Wire Protocol Specification

### 2.1 Two-Stage USB Operational Modes & Vendor Control Requests

The DSC-W300 does not run Linux userspace MTP daemons; its BIONZ RTOS implements a two-stage USB device model:

1. **Standard Retail Mode (PID `0x031B`)**:
   - Enumerates as USB Mass Storage Class (`Class 0x08, SubClass 0x06, Protocol 0x50`).
   - Handles standard SCSI BOT commands (`CBW` / `CSW`).
   - Supports vendor SCSI CDB pass-through (`0x7A` or `0xFD`/`0xFE`).
2. **Service Mode / Senser Protocol (PID `0x02A9`)**:
   - Enumerates as a dedicated Sony Senser Device (`VID 0x054C, PID 0x02A9`).
   - Driven in Sony service environments by `Sony Seus USB Driver` (`seus.inf`).
   - Provides direct memory, EVR, adjustment, and calibration control over raw bulk endpoints (typically EP1 OUT / EP1 IN).

#### Mode-Switch Vendor Control Requests:
- **Enter Senser Service Mode**:
  - `bmRequestType`: `0x43` (Direction: Host-to-Device `0x00`, Type: Vendor `0x40`, Recipient: Other `0x03`)
  - `bRequest`: `0x01`
  - `wValue`: `0x37FF`
  - `wIndex`: `0xD7AA`
  - `wLength`: `0x0000` (No data phase)
  - *Firmware response*: Disconnects from USB, launches `/bin/sen` / `senser_usb_mode_start`, and re-attaches with `PID = 0x02A9`.
- **Exit Senser Service Mode & Reboot**:
  - `bmRequestType`: `0x43`
  - `bRequest`: `0x01`
  - `wValue`: `0xC800` (`~0x37FF & 0xFFFF`)
  - `wIndex`: `0x2855` (`~0xD7AA & 0xFFFF`)
  - `wLength`: `0x0000`
  - *Firmware response*: Tears down Senser session, triggers hardware reset, and boots normally with updated NVM parameters.

---

### 2.2 Senser Bulk Wire Framing: 12-Byte Binary Header

Once in Senser mode (`PID 0x02A9`), all standard command transactions exchange binary packets over bulk endpoints preceded by a 12-byte little-endian header:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      Payload Size (size)                      |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|             pFunc             |            Sequence           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|    Version    |   MiconType   |   OffsetType  |    Response   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                     Command Data Payload                      +
|                     (Length = size bytes)                     |
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

#### Field Definitions:
- **`size`** (`uint32`, Little-Endian, Offset `0x00`): Length of data payload immediately following the 12-byte header.
- **`pFunc`** (`uint16`, Little-Endian, Offset `0x04`): Primary Function Opcode directing the packet to a specific subsystem in firmware.
- **`sequence`** (`uint16`, Little-Endian, Offset `0x06`): Monotonically incrementing transaction counter. Initialized to `1`, incremented by `1` per transaction. The camera echoes the sequence number in its response.
- **`version`** (`uint8`, Offset `0x08`): Protocol revision. Fixed at `0x00`.
- **`miconType`** (`uint8`, Offset `0x09`): Target processor. `0x00` = Host / Main BIONZ CPU, `0x01` = Sub-CPU / Micon.
- **`offsetType`** (`uint8`, Offset `0x0A`): Offset addressing mode. Fixed at `0x00`.
- **`response`** (`uint8`, Offset `0x0B`):
  - Request: `0x00`.
  - Response: Status return code. `0x00` indicates Success for `AdjustControl` (`pFunc 0x0040`); non-zero indicates an execution error.

#### Transport Constraints:
- **512-Byte Alignment (`SenserMinSize`)**: For `PID 0x02A9`, all bulk OUT transfers must be padded with `0x00` to a multiple of 512 bytes (`0x200`). If `12 + size < 512`, the packet is padded to 512 bytes.
- **Chunk Size (`SenserChunkSize`)**: Transfers exceeding 32,768 bytes (`0x8000`) are segmented into 32 KB blocks.
- **Maximum Buffer Size (`SenserMaxSize`)**: Payloads cannot exceed 1,048,576 bytes (1 MB / `0x100000`).

---

### 2.3 Primary Function Opcodes (`pFunc`)

| `pFunc` Code | Symbolic Identifier | Description |
|:---:|---|---|
| **`0x0010`** | `SONY_PFUNC_ProductInfo` | Device identity, HASP key verification (`0x001F`), terminal control (`0x00F1`). |
| **`0x0020`** | `SONY_PFUNC_FirmwareUpdate` | Firmware update staging and flashing. |
| **`0x0030`** | `SONY_PFUNC_MiconAccess` | Direct sub-CPU / lens / power management controller register access. |
| **`0x0040`** | `SONY_PFUNC_AdjustControl` | **Service adjustment engine**: NVM property read/write/save, ID1 lock control. |
| **`0xFF00`** | `SONY_PFUNC_TestMode` | Diagnostic tests, display test patterns, hardware switch sensing. |
| **`0xFF01`** | `SONY_PFUNC_FileControl` | Service filesystem operations (Read=1, Write=2, Delete=3). |
| **`0xFF02`** | `SONY_PFUNC_Sonar` | Protocol ping / heartbeat. |
| **`0xFF03`** | `SONY_PFUNC_MemoryDump` | Direct physical RAM/ROM read and write by base address and length. |

---

### 2.4 Three-Step Challenge-Response Authentication (`AuthPacket` & `sha1_faulty`)

Prior to processing any operational service commands, Senser mode requires a 3-step authentication handshake using a 516-byte frame in big-endian format.

#### `AuthPacket` Format (516 bytes, Big-Endian):
- `cmd` (`uint16`, Big-Endian, Offset `0x00`): Bitwise NOT of the command identifier (`~cmd & 0xFFFF`).
- `salt` (`uint16`, Big-Endian, Offset `0x02`): Set to `0x0000` by the host.
- `data` (512 bytes, Offset `0x04`): Challenge data or computed response digest.

#### Handshake Sequence:
1. **Step 1 (Challenge Request)**:
   - Host sends: `cmd = ~1 & 0xFFFF = 0xFFFE`, `salt = 0`, `data = 512 bytes 0x00`.
   - Camera responds with challenge data. Return code `ret = (~response.cmd & 0xFFFF) - response.salt`.
   - On DSC-W300 (`PID 0x02A9`), `ret == 2`, indicating the SHA-1 algorithm is required.
2. **Step 2 (Cryptographic Response Calculation)**:
   - Input challenge slice: The first 4 bytes of the camera's challenge data: `data = response.data[:4]`.
   - Digest calculation: `digest = sha1_faulty(data)`.
   - Host sends: `cmd = ~3 & 0xFFFF = 0xFFFC`, `salt = 0`, `data = bytes([0x01]) + digest + padding`.
   - Camera verifies the hash and responds with `ret == 4`.
3. **Step 3 (Handshake Finalization)**:
   - Host sends: `cmd = ~5 & 0xFFFF = 0xFFFA`, `salt = 0`.
   - Camera responds with `ret == 6`. The first byte of the returned payload must equal `0x01` (`SUCCESS`).

#### The `sha1_faulty` Algorithm:
In Sony's BIONZ firmware (`libsencore.so`), the SHA-1 implementation contains a length calculation bug where message length in the SHA-1 padding block is bitwise AND-ed with `0x1F`:
$$\text{effective\_length} = \text{len}(\text{message}) \ \& \ 0x1F$$
This exact algorithm must be replicated byte-for-byte in the service tool:
```python
def _left_rotate(n: int, b: int) -> int:
    return ((n << b) | (n >> (32 - b))) & 0xFFFFFFFF

def sha1(message: bytes, length: int = -1) -> bytes:
    if length < 0:
        length = len(message)
    h0, h1, h2, h3, h4 = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0
    msg = bytearray(message)
    msg.append(0x80)
    msg.extend(b'\x00' * ((56 - len(msg) % 64) % 64))
    msg.extend(struct.pack('>Q', length * 8))
    for i in range(0, len(msg), 64):
        w = [0] * 80
        for j in range(16):
            w[j] = struct.unpack('>I', msg[i + j*4:i + j*4 + 4])[0]
        for j in range(16, 80):
            w[j] = _left_rotate(w[j-3] ^ w[j-8] ^ w[j-14] ^ w[j-16], 1)
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
            a, b, c, d, e = (_left_rotate(a, 5) + f + e + k + w[j]) & 0xFFFFFFFF, a, _left_rotate(b, 30), c, d
        h0 = (h0 + a) & 0xFFFFFFFF
        h1 = (h1 + b) & 0xFFFFFFFF
        h2 = (h2 + c) & 0xFFFFFFFF
        h3 = (h3 + d) & 0xFFFFFFFF
        h4 = (h4 + e) & 0xFFFFFFFF
    return struct.pack('>5I', h0, h1, h2, h3, h4)

def sha1_faulty(message: bytes) -> bytes:
    return sha1(message, len(message) & 0x1F)
```

---

### 2.5 AdjustControl Category 0x0603 Subcommands

All NVM parameter reads, destination writes, checksum updates, and flash commits execute under `pFunc = 0x0040` (`AdjustControl`). The payload begins with a 4-byte header:
```
Category (uint16 LE) | Command (uint16 LE) | Parameters ...
```

| Category | Command | Symbolic Identifier | Parameters / Payload | Description |
|:---:|:---:|---|---|---|
| `0x0603` | `0x0001` | `SONY_ADJUST_BACKUP_READ` | `property_id` (`uint32` LE) | Read property from NVM staging RAM / Flash. Returns raw property value. |
| `0x0603` | `0x0002` | `SONY_ADJUST_BACKUP_WRITE` | `property_id` (`uint32` LE) + `data` | Write property into volatile staging RAM. |
| `0x0603` | `0x0003` | `SONY_ADJUST_BACKUP_SAVE` | `subsystem` (`uint16` LE, `0x0000` = All) | Recalculate block checksums and commit staging RAM to NOR flash. |
| `0x0603` | `0x000F` | `SONY_ADJUST_BACKUP_ID1` | `lock_state` (`uint8`: `0x00` = Unlock, `0x01` = Lock) | **Service Board Write Protection Toggle**. Unlocks destination modification on retail boards. |

---

## 3. "Service Board" Restriction Analysis & Retail Unlock

### 3.1 Root Cause Analysis: Hardware vs. Software

In the official Sony Service Adjustment Manual (`sony_dsc-w300_adjustment_ver1.3.txt`, Section 1-3, lines 567–568; Sony document 9-852-287-54), the following note appears:
> **"Note: The DESTINATION DATA WRITE cannot be set with other than the Service board."**

#### Technical Findings:
1. **Physical Motherboard Identity**:
   - Sony parts catalog lists only one replacement motherboard for all 18 worldwide regions: `SY-199 BOARD, COMPLETE` (Sony Part No. A-1512-321-A).
   - Retail production cameras and spare-parts boards use identical silicon: CXD4108 BIONZ SoC, identical NOR flash, and identical EEPROM.
   - There are **no one-time programmable (OTP) fuses**, hardware write-protect jumpers, or blown silicon locks on the `SY-199` board.
2. **The "Service Board" Differentiator**:
   - A replacement "Service board" is shipped blank from Kohda TEC / EMCS spare parts depots (destination register uninitialized, `0xFF` or `0x00`).
   - A retail production board has had its regional code (`J1`) and serial number written during factory assembly line finalization.
3. **Primary Host Application Enforcement**:
   - In `DSC-W300 Auto-Adj Ver_1.3r04.exe`, when the `DESTINATION DATA WRITE` dialog (`Fig. 6-1-12`) is launched, the PC software queries the current destination.
   - If the camera returns an already programmed code (`J1`), the GUI recognizes that the unit is not a blank replacement board and disables (`EnableWindow = FALSE`) the `[Data Write]` button.
   - Sony Service Bulletin DI08-225 confirms this: a destination write issue was resolved solely by updating the PC application from `Ver_1.1r02` to `Ver_1.2r03` without any camera firmware modification.
4. **Firmware ID1 Write Guard**:
   - The camera RTOS maintains an ID1 protection state flag (governing persistent configuration blocks at backup offset `0x28`).
   - When ID1 lock is asserted (`id1 = 1`), high-level destination write commands return an authorization rejection.
   - When unlocked via the service subcommand `BACKUP_ID1` (`Category 0x0603, Command 0x000F, Data 0x00`), the firmware clears the write-protection lock in staging memory, allowing direct destination and language updates.

### 3.2 Unlock Routes

1. **Direct Protocol Unlock (`BACKUP_ID1 = 0`)** [RECOMMENDED]:
   - Send `pFunc 0x0040, Category 0x0603, Command 0x000F, Data 0x00`.
   - Immediately clears write protection in staging RAM.
   - Write destination and language properties via `BACKUP_WRITE` (`0x0002`).
   - Commit changes via `BACKUP_SAVE` (`0x0003`).
2. **Direct NVM / EVR Register Write**:
   - Low-level EVR register writes (`SeusEX Direct Register Access`, Block `0x00`, Page `0x60`) bypass the high-level semantic destination guard.
3. **Re-Virginizing (0xFF Reset)**:
   - Writing `0xFF` to the destination register resets the board to a virgin state. The camera firmware then natively accepts `DESTINATION DATA WRITE` without restriction.

---

## 4. Complete CEE8 Destination Specification

### 4.1 Master Destination Matrix (Table 6-1-2)

From Section 1-3, Table 6-1-2 of the Sony Service Manual, the complete 18-destination by 25-language matrix is defined:

- `z`: Initial language loaded on cold boot / factory reset.
- `a`: Selectable language available in `HOME` > `Settings` > `Language`.
- `-`: Language disabled.

| Destination | Area | JA | EN | FR | DE | ES | IT | PT | ZH-S | ZH-T | NL | RU | KO | FA | AR | TH | MS | SV | NO | DA | FI | PL | CS | HU | TR | EL | Video Out |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **J1** | J | **z** | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | **NTSC** |
| **JE3** | JE | - | **z** | a | - | - | - | a | a | a | - | - | a | a | a | a | a | - | - | - | - | - | - | - | - | - | **PAL** |
| **U2** | US | - | **z** | a | - | a | - | a | a | a | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | **NTSC** |
| **CA2** | CND | - | **z** | a | - | a | - | a | a | a | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | **NTSC** |
| **CEE2** | AEP | - | a | a | a | a | a | a | - | - | a | **z** | - | - | - | - | - | a | a | a | a | a | a | a | a | a | **PAL** |
| **CEE8** | AEP | - | **z** | a | a | a | a | a | - | - | a | - | - | - | - | - | - | a | a | a | a | a | a | a | a | a | **PAL** |
| **CEE9** | AEP | - | **z** | a | a | a | a | a | - | - | a | a | - | - | - | - | - | a | a | a | a | a | a | a | a | a | **PAL** |
| **CEH** | UK | - | **z** | a | a | a | a | a | - | - | a | - | - | - | - | - | - | a | a | a | a | a | a | a | a | a | **PAL** |
| **E15** | E | - | **z** | a | - | - | - | a | a | a | - | - | a | a | a | a | a | - | - | - | - | - | - | - | - | - | **PAL** |
| **E32** | E | - | **z** | a | - | - | - | a | a | a | - | - | a | a | a | a | a | - | - | - | - | - | - | - | - | - | **PAL** |
| **E33** | E | - | a | **z** | - | - | - | a | a | a | - | - | a | a | a | a | a | - | - | - | - | - | - | - | - | - | **NTSC** |
| **TH6** | Thai | - | a | a | - | - | - | a | a | a | - | - | a | a | a | **z** | a | - | - | - | - | - | - | - | - | - | **PAL** |
| **AU2** | AUS | - | **z** | a | - | a | - | a | a | a | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | **PAL** |
| **HK1** | HK | - | **z** | a | - | - | - | a | a | a | - | - | a | a | a | a | a | - | - | - | - | - | - | - | - | - | **PAL** |
| **CN2** | CH | - | a | a | - | - | - | a | **z** | a | - | - | a | a | a | a | a | - | - | - | - | - | - | - | - | - | **PAL** |
| **KR2** | KR | - | a | a | - | - | - | a | a | a | - | - | **z** | a | a | a | a | - | - | - | - | - | - | - | - | - | **NTSC** |
| **AR2** | AR | - | a | - | - | **z** | - | a | a | a | - | - | a | a | a | a | a | - | - | - | - | - | - | - | - | - | **NTSC** |
| **BR1** | BR | - | a | a | - | - | - | **z** | a | a | - | - | a | a | a | a | a | - | - | - | - | - | - | - | - | - | **NTSC** |

### 4.2 CEE8 Profile Attributes
- **Target Area**: `AEP` (Central/Eastern Europe).
- **Default Initial Language**: English (`en`).
- **Selectable Languages (16 total)**: English, French, German, Spanish, Italian, Portuguese, Dutch, Swedish, Norwegian, Danish, Finnish, **Polish (`pl`)**, Czech, Hungarian, Turkish, Greek.
- **Russian**: Excluded in `CEE8` (included in `CEE2` and `CEE9`).
- **Default Video Standard**: `PAL` (625/50).
- **Destination Code**: ASCII `"CEE8"` (`0x43 0x45 0x45 0x38`).

### 4.3 35-Byte Language Mask Hex Specifications

Sony cameras address language properties sequentially from `0x010D008F` (Index 0) to `0x010D00B1` (Index 34).
- In Senser property format: `0x01` = Enabled, `0x02` = Disabled.
- In raw bitmask format: `0x01` = Enabled, `0x00` = Disabled.

#### CEE8 Configuration:
- **Senser Property Array (35 bytes)**:
  ```hex
  01 02 01 01 01 01 01 02 02 02 02 01 02 02 02 01 01 01 01 01 01 01 01 02 02 01 01 01 01 02 02 02 02 02 02
  ```
  Continuous hex:
  `0102010101010102020202010202020101010101010101020201010101020202020202`

#### J1 Baseline Configuration:
- **Senser Property Array (35 bytes)**:
  ```hex
  02 01 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02 02
  ```
  Continuous hex:
  `0201020202020202020202020202020202020202020202020202020202020202020202`

### 4.4 Persistent NVM Property IDs

| Property Name | Property ID (Hex) | Type / Size | Description |
|---|:---:|:---:|---|
| `modelCode` | `0x00E70000` | 5 bytes | Hardware model identifier (`0x00E70000`). |
| `destinationCode` | `0x00E70001` | 4 bytes ASCII | Destination string (`"J1\0\0"` vs `"CEE8"`). |
| `serialNumber` | `0x00E70003` | 4 bytes uint32 | 7-digit camera serial number. |
| `palNtscSelector` | `0x01070148` | 1 byte uint8 | Video format standard: `0x00` = NTSC, `0x01` = PAL. |
| `languageTable` | `0x010D008F` – `0x010D00B1` | 35 bytes | Compound array of 35 single-byte language flags. |
| `id1Protection` | `0x0603` / Cmd `0x000F` | 1 byte uint8 | Service board lock state (`0x01` = Locked, `0x00` = Unlocked). |

### 4.5 EVR Checksum Formula

For direct EVR memory pages, Sony firmware enforces an additive two's complement modulo-256 checksum:
$$\text{checksum} = (0x100 - (\sum_{i=0}^{N-1} \text{data}[i] \ \& \ 0xFF)) \ \& \ 0xFF$$
When the checksum byte is appended to the data stream, the full block sums to zero:
$$\sum_{i=0}^{N} \text{page}[i] \pmod{256} == 0x00$$

---

## 5. Complete Packet Sequence Trace (Full Lifecycle)

```
HOST PC (CLI Service Tool)                             SONY DSC-W300 (Camera)
      |                                                            |
      |=================== 1. USB MODE SWITCH =====================|
      |                                                            |
      |--- USB Control Transfer: bmReq=0x43, bReq=1, --------------->
      |    wVal=0x37FF, wIdx=0xD7AA, wLen=0                        |
      |    [Camera detaches from Mass Storage PID 0x031B]          |
      |    [Camera re-attaches as Senser Device PID 0x02A9]        |
      |                                                            |
      |================= 2. CRYPTOGRAPHIC AUTH ===================|
      |                                                            |
      |--- AuthPacket 1: cmd=0xFFFE, salt=0, data=512x0x00 ------->|
      |<-- AuthPacket 1 Resp: cmd=0xFFFC, ret=2, challenge data ---|
      |    [Host calculates hash = sha1_faulty(challenge[:4])]     |
      |--- AuthPacket 2: cmd=0xFFFC, salt=0, data=[0x01]+hash ---->|
      |<-- AuthPacket 2 Resp: ret=4 -------------------------------|
      |--- AuthPacket 3: cmd=0xFFFA, salt=0, data=512x0x00 ------->|
      |<-- AuthPacket 3 Resp: ret=6, payload[0]=0x01 (SUCCESS) ----|
      |                                                            |
      |============== 3. SERVICE ENVIRONMENT QUERY ===============|
      |                                                            |
      |--- SenserPacket(pFunc=0x10, Cat=0, Cmd=0x001F, data=0) --->| (Read HASP)
      |<-- SenserPacket(resp=1, OK) -------------------------------|
      |--- SenserPacket(pFunc=0x10, Cat=0, Cmd=0x00F1, data=1) --->| (Term Enable)
      |<-- SenserPacket(resp=1, OK) -------------------------------|
      |                                                            |
      |=============== 4. READ CURRENT DESTINATION ===============|
      |                                                            |
      |--- SenserPacket(pFunc=0x40, Cat=0x0603, Cmd=1, ----------->| (Read Model/Dest)
      |                 Prop=0x00E70001)                           |
      |<-- SenserPacket(resp=0, data=b"J1\x00\x00") ---------------|
      |--- SenserPacket(pFunc=0x40, Cat=0x0603, Cmd=1, ----------->| (Read Lang Table)
      |                 Prop=0x010D008F)                           |
      |<-- SenserPacket(resp=0, data=35 bytes J1 mask) ------------|
      |--- SenserPacket(pFunc=0x40, Cat=0x0603, Cmd=1, ----------->| (Read Video Std)
      |                 Prop=0x01070148)                           |
      |<-- SenserPacket(resp=0, data=b"\x00" [NTSC]) --------------|
      |                                                            |
      |================= 5. SERVICE BOARD UNLOCK ==================|
      |                                                            |
      |--- SenserPacket(pFunc=0x40, Cat=0x0603, Cmd=15, ---------->| (Disable ID1 Lock)
      |                 data=b"\x00")                              |
      |<-- SenserPacket(resp=0, ID1 Protection Cleared) -----------|
      |                                                            |
      |================ 6. WRITE CEE8 DESTINATION ================|
      |                                                            |
      |--- SenserPacket(pFunc=0x40, Cat=0x0603, Cmd=2, ----------->| (Write PAL)
      |                 Prop=0x01070148, data=b"\x01")             |
      |<-- SenserPacket(resp=0, RAM Staged OK) --------------------|
      |--- SenserPacket(pFunc=0x40, Cat=0x0603, Cmd=2, ----------->| (Write Lang Table)
      |                 Prop=0x010D008F, data=35 bytes CEE8 mask)  |
      |<-- SenserPacket(resp=0, RAM Staged OK) --------------------|
      |--- SenserPacket(pFunc=0x40, Cat=0x0603, Cmd=2, ----------->| (Write Dest String)
      |                 Prop=0x00E70001, data=b"CEE8")             |
      |<-- SenserPacket(resp=0, RAM Staged OK) --------------------|
      |                                                            |
      |================== 7. COMMIT / FLASH SAVE ==================|
      |                                                            |
      |--- SenserPacket(pFunc=0x40, Cat=0x0603, Cmd=3, ----------->| (Commit Flash)
      |                 Subsystem=0x0000)                          |
      |    [Camera recalculates NVM block checksums]               |
      |    [Camera flushes RAM buffer to physical NOR flash]       |
      |<-- SenserPacket(resp=0, Flash Commit Successful) ----------|
      |                                                            |
      |================ 8. VERIFICATION READBACK =================|
      |                                                            |
      |--- SenserPacket(pFunc=0x40, Cat=0x0603, Cmd=1, ----------->| (Readback Dest)
      |                 Prop=0x00E70001)                           |
      |<-- SenserPacket(resp=0, data=b"CEE8") ---------------------|
      |--- SenserPacket(pFunc=0x40, Cat=0x0603, Cmd=1, ----------->| (Readback English)
      |                 Prop=0x010D008F)                           |
      |<-- SenserPacket(resp=0, data=b"\x01" [Enabled]) -----------|
      |--- SenserPacket(pFunc=0x40, Cat=0x0603, Cmd=1, ----------->| (Readback Video)
      |                 Prop=0x01070148)                           |
      |<-- SenserPacket(resp=0, data=b"\x01" [PAL]) ---------------|
      |                                                            |
      |=================== 9. REBOOT / RELEASE ===================|
      |                                                            |
      |--- USB Control Transfer: bmReq=0x43, bReq=1, --------------->
      |    wVal=0xC800, wIdx=0x2855, wLen=0                        |
      |    [Camera unregisters PID 0x02A9, triggers cold reset]     |
      |    [Camera boots with English UI, Polish selectable, PAL]  |
      |    [Camera enumerates in retail mode as PID 0x031B]        |
      v                                                            v
```

---

## 6. Safety Guardrails and Reversibility

1. **Power Supply Requirement**:
   - Firmware flash commit (`BACKUP_SAVE`) alters non-volatile sectors. Destination write operations must **only** be conducted with external regulated DC power (Sony AC-LS5 or laboratory power supply connected via the multi-terminal cable). Battery power alone is strictly prohibited.
2. **Preservation of Calibration Sectors**:
   - Optical lens centering, CCD defect maps, exposure calibration, and white balance matrices reside in distinct NVM subsystems (`Subsystem 0x02`+). The service tool strictly constrains its writes to the Destination, Language, and Video properties (`0x00E70001`, `0x010D008F`–`0x010D00B1`, `0x01070148`), ensuring zero impact on factory calibration.
3. **Dry-Run Enforcement**:
   - Any service tool implementing this specification must support a mandatory `--dry-run` flag. In dry-run mode, the tool must execute all handshake and frame generation logic, but terminate before dispatching state-modifying or flash-committing commands (`BACKUP_WRITE`, `BACKUP_SAVE`, `BACKUP_ID1`).
4. **Emergency Rollback Procedure**:
   - An exact binary snapshot of original NVM properties is captured before any write. Restoring the camera to original Japanese `J1` state is achieved by writing back the baseline 35-byte mask (`02010202...`), setting video to NTSC (`0x00`), and executing `BACKUP_SAVE`.
