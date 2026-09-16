# Design Document: Sony Cyber-shot DSC-G3 Custom String Display POC

## 1. Executive Summary & Objective

The objective of this design is to establish an **offline, fail-closed proof-of-concept (POC)** that modifies a visible text string in the Sony Cyber-shot DSC-G3 firmware (`DSCG3V2.exe` / `D-G3V2.dat`) to display a custom string (e.g. `G3 POC`) on the camera's physical display, benchmarked directly against the gold-standard engineering patterns established in **`SONY_NX3_Reversal`** (`nx3_text_poc.py`).

### Non-Destructive Laboratory Principles
1. **100% Offline Execution**: No physical flashing or dangerous writes to hardware. All changes are verified in software through bit-for-bit repacking roundtrips, cryptographic HMAC re-generation, and automated regression test suites.
2. **Fail-Closed Patch Mechanics**: Strict source hash verification, bounded record replacement, refusal of ambiguous or colliding targets, and exact restoration verification.
3. **Preservation of Calibration Data**: NVM, optical calibration, and hardware IDs are never touched.

---

## 2. Target Candidates for Custom String Display

Our architectural excavation of the DSC-G3 firmware identified **three candidate venues** for displaying a custom string on the camera LCD:

```
+-----------------------------------------------------------------------------------+
|                           Target Candidate Landscape                              |
+-----------------------------------------------------------------------------------+
| Venue 1: Main Settings Menu UI (Recommended)                                      |
| File: fskapp1/dsc/app/scripts/language/eng.csv                                    |
| Trigger: HOME > Settings > Main Settings > Page 3/7 > Version                      |
| Display: Renders via FreeType font engine on 3.5" touchscreen                     |
+-----------------------------------------------------------------------------------+
| Venue 2: NetFront Browser Dialog                                                  |
| File: Section 21: omgLng00.csv ([eng.csv] table)                                  |
| Trigger: WLAN button > Browser > Menu > Settings                                  |
| Display: Renders in ACCESS NetFront 3.4 modal dialog                              |
+-----------------------------------------------------------------------------------+
| Venue 3: Updater Splash Screen Framebuffer                                        |
| File: BodyUdtr.img / bin/ass/img/updating                                         |
| Trigger: Memory Stick firmware update boot sequence                               |
| Display: Blitted directly to LCD controller (/dev/fb0) via ud_avldr               |
+-----------------------------------------------------------------------------------+
```

### Primary Target: `SETUP_VERSION` in `eng.csv` (Venue 1)
* **Path**: `fskapp1/dsc/app/scripts/language/eng.csv` (inside Section 10 `10_fskapp1.tar`).
* **Line 1080**: `SETUP_VERSION,Version`
* **Patch**: `SETUP_VERSION,G3 POC ` (padded to 21 bytes or exact substitution).
* **On-Screen Result**: When navigating to the settings screen where "Version" is normally shown, the camera will query `SETUP_VERSION` and render **`G3 POC`**.
* **Rationale**: This is the exact equivalent of the `SONY_NX3_Reversal` target (`MENU -> OTHERS -> LANGUAGE` -> `NX3 POC`).

---

## 3. End-to-End Packaging & Cryptographic Pipeline

To produce a valid firmware image without corrupting the camera's bootloader or update check, the modification must navigate four distinct container layers:

1. **String Substitution**:
   `eng.csv`: Replace `SETUP_VERSION,Version` with `SETUP_VERSION,G3 POC `.
2. **Tar Archive Repack**:
   Repack `fskapp1.tar` with deterministic POSIX permissions and ordering.
3. **Manifest & Checksum Update**:
   Update `cntent.dat` section 10 size, cksum, and `[hdsm]` checksum.
4. **Cryptographic Re-encryption**:
   Generate SHA-1 keystream with `key_cxd4108_ms`, XOR cipher.
5. **Dual HMAC-SHA1 Block Headers**:
   Compute 20-byte data HMAC & 128-byte header HMAC.
6. **LHA Level 2 Container Packaging**:
   Rebuild `D-G3V2_poc.dat` and self-extracting `DSCG3V2_poc.exe`.

---

## 4. Benchmarking Against `SONY_NX3_Reversal`

| Architectural Component | SONY HXR-NX3 Reference (`nx3_text_poc.py`) | Sony Cyber-shot DSC-G3 Implementation |
| :--- | :--- | :--- |
| **Target String** | `share/app/string_english.uxc` (`LANGUAGE` -> `NX3 POC`) | `dsc/app/scripts/language/eng.csv` (`Version` -> `G3 POC`) |
| **File Format** | Binary UXC (2,700 16-bit slots, offset index table) | UTF-8 CSV (1,118 key-value pairs) |
| **Filesystem Level** | Ext2 physical block replacement in LZPT block | POSIX Tarball inside `fskapp1.tar` |
| **Container Encryption** | AES / CXD90014 block cipher | Double HMAC-SHA1 + SHA-1 keystream XOR |
| **Manifest Checksum** | `0701_part_image_sum/part_image.sum` CRC32 | `cntent.dat` header sum + 128-byte HMACs |
| **Safety Invariants** | Refuse size expansion, require exact hash match | Deterministic block alignment, roundtrip decryption test |

---

## 5. Verification & Acceptance Criteria

1. **Self-Consistency Roundtrip**:
   - Running `g3_firmware_parser.py unpack` on `D-G3V2_poc.dat` must succeed with **zero hash errors**.
   - Extracted `eng.csv` must contain `SETUP_VERSION,G3 POC`.
2. **Isolation Guarantee**:
   - All 23 unpatched sections (`defhd.dat`, `partinf.tbl`, `BodyUdtr.img`, `linuxset1.tar`, `vmlinux`, etc.) must remain **100% bit-for-bit identical** to the factory release.
3. **Automated Test Coverage**:
   - Regression test suite `test_g3_text_poc.py` verifying patch application, tamper rejection, invalid length handling, and cryptographic roundtrip.
