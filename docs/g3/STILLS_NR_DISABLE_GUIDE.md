# End-to-End Guide: Disabling Stills Noise Reduction on the Sony Cyber-shot DSC-G3

This guide provides step-by-step instructions to eliminate in-camera stills noise reduction on the **Sony Cyber-shot DSC-G3** (Ver 2.00, CXD4108 BIONZ SoC).

By bypassing the Smart Algorithm Chroma Noise Reduction (`NR32_CNR`) and RGB spatial low-pass smoothing (`NR32_RGB`) in the real-time co-processor (`09_av.bin`), the camera preserves **100% of authentic sensor texture, micro-contrast, and sharp detail** without the characteristic "watercolor / plastic skin" smearing.

---

## 1. Prerequisites & Equipment Checklist

Before beginning, ensure you have the following ready:

1. **Hardware**:
   - Sony Cyber-shot DSC-G3 camera (confirmed running **Version 2.00**).
   - Genuine Sony Memory Stick Duo or PRO Duo card (512 MB to 8 GB).
   - Memory Stick USB card reader (for your Mac).
2. **Power Safety**:
   - Fully charged Sony **NP-BD1** or **NP-FD1** battery (at least 3 bars / >= 75% charge).
   - *Optional / Recommended*: Sony AC-LS5 AC adapter with DC coupler.
3. **Software Environment**:
   - Your Mac in this repository (`DSC-W300 and DSC-G3`).
   - Python 3.12 (standard library only; no external pip packages required).

---

## 2. Step 1: Generate the Non-NR Firmware Container (`D-G3V2_nonr.dat`)

In your Mac terminal inside the repository, run the dedicated patcher tool:

```bash
python3 tools/g3_stills_nr_patcher.py --out evidence/extracted_g3/D-G3V2_nonr.dat
```

### What this tool does automatically:
1. **Applies 4-byte surgical bypass** to `sections/09_av.bin`:
   - `0x0ad550` (`run_NR32_CNR`): Patches `10 b5` -> `70 47` (`bx lr`).
   - `0x0ad576` (`run_NR32_RGB`): Patches `10 b5` -> `70 47` (`bx lr`).
2. **Recalculates `cntent.dat` manifest checksum**:
   - Recomputes `[hdsm] chksum = sum(data[0x40:]) & 0xffffffff`.
3. **Cryptographically re-encrypts all 24 sections**:
   - Uses `key_cxd4108_ms` with double SHA-1 HMAC block headers.
4. **Validates the output**:
   - Performs a full decrypt-and-verify pass on the output container.

### Expected Output:
```
Generating DSC-G3 Non-NR Firmware Container -> evidence/extracted_g3/D-G3V2_nonr.dat
[+] Successfully created: evidence/extracted_g3/D-G3V2_nonr.dat (55,898,601 bytes)
Verifying cryptographic and structural integrity...
[+] Verification Result: {'status': 'PASS', 'size': 55898601, 'cnr_bypassed': True, 'rgb_bypassed': True, 'sections_verified': 24}
```

---

## 3. Step 2: Prepare the Memory Stick Duo

1. Insert your Memory Stick Duo into your Mac's card reader.
2. Ensure the card is formatted as **FAT / FAT32** (or format it inside the DSC-G3 camera first via `HOME -> Manage Memory -> Format`).
3. Copy the generated `D-G3V2_nonr.dat` file to the **root directory** of the Memory Stick, renaming it to **`D-G3V2.dat`**:

```bash
# Assuming your Memory Stick is mounted at /Volumes/MEMORYSTICK
cp evidence/extracted_g3/D-G3V2_nonr.dat /Volumes/MEMORYSTICK/D-G3V2.dat

# Flush disk buffers to ensure complete write
sync
```

4. Verify that the file on the Memory Stick is exactly in the root folder:
```bash
ls -lh /Volumes/MEMORYSTICK/D-G3V2.dat
# Expected size: ~55.9 MB (55,898,601 bytes)
```
5. Safely eject the Memory Stick from your Mac:
```bash
diskutil unmount /Volumes/MEMORYSTICK
```

---

## 4. Step 3: Execute In-Camera Firmware Flashing

> [!IMPORTANT]
> **Power Interruption Warning**:
> Never remove the battery or power off the camera while the firmware update screen is active. Flashing takes approximately **60 to 90 seconds**.

1. Ensure camera power is completely **OFF**.
2. Insert the fully charged battery into the camera.
3. Insert the prepared Memory Stick Duo into the camera's card slot.
4. **Initiate the Update**:
   - **Method A (GUI Update Menu)**:
     1. Power on the camera.
     2. Touch `HOME` -> `Settings` -> `Main Settings` (Page 3/7).
     3. Select `Version`.
     4. The camera will detect `D-G3V2.dat` on the Memory Stick and display `Current Version: 2.00` and `New Version: 2.00`.
     5. Touch `OK` / `Update` to confirm.
   - **Method B (IPL Direct Bootloader Sequence)**:
     1. While the camera is powered OFF, press and hold `Playback` + `Zoom T`.
     2. Press the `Power` button while holding the keys.
     3. The Initial Program Loader (IPL) will scan the Memory Stick root and launch the update environment.
5. **Update Execution**:
   - The camera screen will switch to the updater splash screen (`Updating...`).
   - The Memory Stick access LED will flicker as the real-time core (`av.bin`) is flashed into partition `/dev/nflasha5`.
6. **Automatic Reboot**:
   - Once completed, the camera will display `Update Complete` and automatically restart into standard shooting mode.

---

## 5. Step 4: Photographic Verification & Visual Comparison

To verify that noise reduction has been successfully disabled:

1. **Test Setup**:
   - Place a textured subject (e.g. woven fabric, printed fine text, foliage, or portrait skin) in indoor ambient lighting.
   - Set the camera to `Program Auto` (P mode).
   - Set ISO manually to **ISO 400** or **ISO 800** (where stock Sony firmware normally applies the heaviest watercolor smearing).
2. **Capture & Inspection**:
   - Take photos with the camera.
   - Transfer the JPEG files to your Mac and inspect them at **100% zoom (1:1 pixel view)**.
3. **Observable Visual Differences**:

| Image Characteristic | Stock Sony G3 Firmware (Ver 2.00) | Non-NR Patched Firmware |
| :--- | :--- | :--- |
| **Fine Foliage / Fabric** | Blended into flat, waxy watercolor blobs. | Distinct, individual fiber threads and leaf veins preserved. |
| **Skin Micro-texture** | Plastic, mannequin-like smoothing over pores. | Authentic natural skin texture and micro-contrast. |
| **High-ISO Grain** | Splotchy, mottled color blotches. | Crisp, uniform, film-like luminance micro-grain. |
| **Color Edges** | Low-pass chroma bleed along high-contrast boundaries. | Sharp, precise color delineation. |

---

## 6. Step 5: Rollback Protocol (Restoring 100% Stock Firmware)

If you ever wish to return the camera to 100% original factory Sony firmware:

1. Copy the unmodified factory firmware container (`sources/D-G3V2.dat`) to the Memory Stick root:
```bash
cp sources/D-G3V2.dat /Volumes/MEMORYSTICK/D-G3V2.dat
sync
```
2. Eject the Memory Stick, insert it into the camera, and repeat the update procedure described in **Step 3**.
3. The camera will flash the original `av.bin` back into `/dev/nflasha5`, fully restoring factory noise reduction algorithms.
