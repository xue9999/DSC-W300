# Sony Cyber-shot DSC-W300: Persistent English Conversion Guide

## Milestone Overview

This guide provides a verified, non-destructive, step-by-step procedure to convert a Japanese-market Sony Cyber-shot DSC-W300 camera (model J1, originally PID `054C:0341`) to persistent English menus using the native Senser service protocol.

### Verified Hardware Results
- **Target Device**: Sony Cyber-shot DSC-W300 (Japanese domestic market J1 edition, hardware serial `D386002E4438`).
- **Original State**: Japanese menu only (Region preset 0, PID `054C:0341`).
- **Conversion Command**: Native Senser `RegionSetting [255, 0x100, 0x8100, 0]` executed over USB Bulk endpoints.
- **New State**: Custom region 255 with default language English (`0x100`) and available languages English + Japanese (`0x8100`).
- **Post-Reboot Verification**: English menus remain active after a cold battery-pull restart. Optical zoom, shutter, autofocus, flash, image capture, video recording, playback, and Memory Stick storage remain 100% functional.
- **Preservation**: Sensor and optical calibration, hardware serial `D386002E4438`, and factory identity blocks were completely preserved.
- **Hardware Re-enumeration**: Following the write, the camera automatically re-enumerates on the USB bus with overseas/custom PID `054C:033F` instead of the Japanese PID `054C:0341`.

---

## Technical Protocol & Architecture Discoveries

### 1. Senser Bulk Framing & Authentication Handshake
Communication with the DSC-W300 service system does not use SCSI vendor pass-through in Mass Storage mode; instead, it uses the Sony Senser protocol over Bulk USB endpoints (`0x02` OUT / `0x81` IN).

1. **Initial Authentication**:
   - The host sends an initial USB vendor control request (`0x40`, request `0x01`).
   - A 3-stage challenge/response handshake is executed against the camera using 516-byte frames (`>HH512s`).
   - The response code algorithm:
     $$\text{code} = \big((\sim\text{cmd} \ \& \ \text{0xFFFF}) - \text{salt}\big) \ \& \ \text{0xFFFF}$$
   - The camera transitions into Service Mode under USB PID `054C:0336`.

2. **Service Mode Authentication**:
   - Re-authenticating in Service Mode unlocks access to Senser bytecode handlers.

### 2. Senser Protocol Request & Response Framing
All Senser packets carry a 12-byte little-endian header:
```
Offset  Length  Type    Description
0x00    4       uint32  Payload size (little-endian)
0x04    2       uint16  Function code (0x0040 for Adjust Control)
0x06    2       uint16  Sequence counter (monotonically incremented)
0x08    2       uint16  Status code (in responses: 0x0001 = Success)
0x0A    2       uint16  Reserved (0x0000)
```

#### Senser Success Response Code Discovery
Unlike Unix exit conventions where `0` indicates success, the Senser protocol returns **`status = 0x01`** to signal successful completion of `RegionSetting`:
```
Header: size=0, func=0x0040, seq=N, status=0x0001
```
A return status of `0x0001` with `size = 0` is the expected success indicator.

### 3. RegionSetting Subcommand Encoding
The `RegionSetting` subcommand is located within `senserCmdTable.xsb` and `regionInfo.xsb` at function `0x40`, Host `0x3F`, Command `0x55`. It accepts four 32-bit little-endian unsigned integers:

$$\text{RegionSetting}(\text{region}, \text{language}, \text{availLang}, \text{videoSignal})$$

For the DSC-W300 English conversion:
- **`region = 255` (`0x000000FF`)**: Custom / Overseas flexible multi-region mode.
- **`language = 0x00000100`**: Initial / active interface language set to English (`0x100`).
- **`availLang = 0x00008100`**: Enabled language bitmask, setting English (`0x100`) + Japanese (`0x8000`).
- **`videoSignal = 0` (`0x00000000`)**: Video standard set to NTSC (preserving original Japanese hardware video encoder configuration).

### 4. Flash and Non-Volatile Storage (NVM) Mechanism
When `RegionSetting` is invoked:
1. The firmware updates Category 0 non-volatile configuration memory:
   - Primary: `/boot/factory/Hreg.bin`
   - Shadow/Backup: `/boot/factory/Hreg2.bak`
   - Active XML: `/boot/dsc/RegionInfo.xml`
2. Offsets `0x400–0x40F` within Category 0 `Hreg.bin` store the regional settings and language masks.
3. User preferences (`/boot/dsc/UserInfo.xml` and `UserInfo.bak`) are reset to defaults, ensuring clean startup with the new language.
4. Calibration data (sensor blemish, optical distortion, AF calibration) is stored in Category 5 (`Areg.bin` / `Areg2.bak`) and separate EEPROM blocks, which are completely untouched by Category 0 region changes.
5. The camera automatically re-enumerates into normal Mass Storage mode with USB PID `054C:033F`.

---

## Required Hardware & Software

### Hardware
- Sony Cyber-shot DSC-W300 camera with fully charged battery (Sony NP-BG1 / FG1).
- Sony multi-connector USB cable (VMC-MD1).
- Direct USB port on a Windows 10/11 x64 PC (avoid unpowered USB hubs).

### Software
- **Zadig** (driver management utility): [https://zadig.akeo.ie/](https://zadig.akeo.ie/)
- **W300Region Console Application** or the local repository tools (`build/w300/region_app.py`).
- Git for Windows.

---

## Step-by-Step Conversion Procedure

### Step 1: USB Connection & Normal Mode Driver
1. Turn on the DSC-W300 and verify it operates normally.
2. In camera Setup (Setup Menu), ensure **USB Connect** is set to **Mass Storage**.
3. Connect the camera to your Windows PC via the USB cable.
4. Launch **Zadig**:
   - Go to **Options** -> Check **List All Devices**.
   - In the dropdown, locate **Sony DSC** or device with VID `054C` and PID `0341`.
   - In the target driver box, select **WinUSB**.
   - Click **Replace Driver** (or **Install Driver**).
   - Once completed, the camera's Mass Storage mode will be accessible to `libusb` / `W300Region`.

### Step 2: Environment Self-Test
Open an elevated PowerShell or Command Prompt in the repository directory:
```powershell
python build/w300/region_app.py selftest
python build/w300/region_app.py doctor
```
Ensure that all dependency checks pass and `libusb-1.0.dll` is correctly located.

### Step 3: Capture Camera Baseline Backup
Before making any changes to the camera, capture a complete, double-read backup of all critical NVM and firmware configuration components:

```powershell
python build/w300/region_app.py capture --serial D386002E4438 --experimental-service
```
*(Replace `D386002E4438` with your camera's serial number if different. You can also supply `--output <directory>` to save directly to a custom destination instead of the default `build/w300/sessions/<timestamp>-capture`).*

> **Note on Service Mode Driver Binding**:
> During this step, the camera will switch from Mass Storage mode (PID `0341`) to Service Mode (PID `0336`).
> If Windows prompts for a driver or the script indicates a mode transition wait, check Zadig:
> 1. Select the device with VID `054C` and PID `0336`.
> 2. Install **WinUSB** for this PID as well.
> 3. Resume capture:
>    ```powershell
>    python build/w300/region_app.py capture --serial D386002E4438 --experimental-service --resume-session build/w300/sessions/<session-directory>
>    ```

The captured files are saved and double-read bit-for-bit. A complete baseline contains 20 archived files (including all 11 `ESSENTIAL` reference components evaluated during assessment):
- Category-0 NVM state: `/boot/factory/Hreg.bin`, `Hreg2.bak`, `/boot/dsc/RegionInfo.xml`, `/boot/dsc/UserInfo.xml`, `UserInfo.bak`
- Bytecode & handlers: `/usr/dsc/fsk/regionInfo.xsb`, `senserCmdTable.xsb`, `senserModule.xsb`, `dsc.xsb`
- Extensions & libraries: `/usr/dsc/fsk/PExtBackup.so`, `PExtSenser.so`, `/usr/lib/libsencore.so`, `libAppBackupApi.so`, `libBackupCore.so`, `libBackupTable.so`
- Daemon & configs: `/usr/dsc/fsk/tinyhttp`, `/usr/bin/sen`, `/usr/dsc/fsk/kconfig.xml`, `/usr/dsc/app/scripts/kconfig.xml`
- Firmware banner: `/version.txt`

### Step 4: Verify Baseline Assessment
Run the offline assessment tool against the archived baseline (or your freshly captured session directory) to ensure byte-level compatibility with reviewed components:
```powershell
python build/w300/region_app.py assess --baseline evidence/w300/baseline_files
```
The assessment will verify that:
- Senser command table matches the reviewed function `0x40` / command `0x55` structure.
- Bytecode offset `0x856` in `regionInfo.xsb` matches the `RegionSetting` four-argument signature.
- Hreg size is exactly 2048 bytes with valid category-0 header markers.
- All 11 `ESSENTIAL` reference components match (`"can_attempt_experimental_write": true` and `"reasons": []`).

### Step 5: Execute Region Change to English
Execute the verified region change command:
```powershell
python build/w300/region_app.py change --serial D386002E4438 --experimental-service --baseline evidence/w300/baseline_files
```

What happens during execution:
1. The tool verifies camera identity and establishes an authenticated Senser session.
2. An intent record is saved to disk before transmission.
3. The host transmits `RegionSetting [255, 0x100, 0x8100, 0]`.
4. The camera returns `size=0, func=0x40, status=0x01` (success).
5. The camera exits Service Mode, commits changes to NVM, and resets user preferences.
6. The camera automatically re-enumerates on the USB bus under PID `054C:033F` (Overseas/Custom DSC-W300).

### Step 6: Physical Verification & Cold Restart
1. Safely unplug the USB cable from the camera.
2. Turn off the camera.
3. Remove the battery for 10 seconds to execute a true cold power cycle (discharging residual rail capacitance).
4. Re-insert the battery and turn the camera on.
5. **Observe the LCD Screen**:
   - The initial setup prompts (Clock / Date Set) will appear in **English**.
   - Press the **MENU** button: all menu items, settings, scene selections, and tooltips are now in **English**.
6. **Verify Camera Functions**:
   - Optical zoom (in / out): Smooth and responsive.
   - Shutter button & Auto-focus: Focus lock green indicator functions normally.
   - Test photo & flash: Image captured cleanly and stored on Memory Stick / internal memory.
   - Playback mode: Captured photos display with English metadata and EXIF tags.
   - Video recording: Captures and saves audio/video properly.
7. **Optional Software Verification**:
   You can also verify that the camera reports English region configuration over USB:
   ```powershell
   python build/w300/region_app.py verify-region --serial D386002E4438 --experimental-service --baseline evidence/w300/baseline_files --expect english
   ```

### Step 7: Restoring Standard USB Mass Storage Driver
After the conversion is complete and verified, you can restore standard Windows file explorer access:
1. Connect the camera in Mass Storage mode (now VID `054C`, PID `033F`).
2. Open Windows **Device Manager**.
3. Under **Universal Serial Bus devices**, right-click the Sony device and select **Uninstall device**.
4. Check **Attempt to remove the driver for this device** and click **Uninstall**.
5. Unplug and reconnect the camera: Windows will automatically bind the default Microsoft `USBSTOR` driver, allowing the camera to appear as a removable drive in File Explorer.

---

## Safety Guarantees & Restoration (Rollback)

### Why This Method Is Safe
1. **Calibration Integrity**: Optical alignment, sensor blemish compensation tables, white balance matrix, and AF calibration data reside in separate EEPROM categories (Category 5 and hardware DSP registers). The `RegionSetting` command only writes Category 0 (`Hreg.bin`), leaving optical calibration 100% unaltered.
2. **Serial Number Preservation**: The camera hardware serial (e.g. `D386002E4438`) is stored in immutable hardware security blocks and is unaffected by region configuration.
3. **No Firmware Flashing Required**: The camera's Linux kernel and application binaries in flash ROM (`/usr/dsc/fsk/tinyhttp`, etc.) are not modified. English language strings are already present in the factory firmware; `RegionSetting` simply unlocks them in the UI.

### Factory Rollback Procedure
If you ever want to return the camera to its original Japanese factory state, provide the original baseline and the session directory recorded during the change:
```powershell
python build/w300/region_app.py restore-region --serial D386002E4438 --experimental-service --baseline evidence/w300/baseline_files --change-session build/w300/sessions/<timestamp>-change
```
The `--change-session` argument ensures transactional safety by validating that the serial number, baseline SHA-256 digest, and recorded change intent match the camera state before executing the restore command. This reapplies the original Japanese preset arguments `[0, 0x8000, 0x8000, 0]` and restores the original `/boot/factory/Hreg.bin` configuration.
