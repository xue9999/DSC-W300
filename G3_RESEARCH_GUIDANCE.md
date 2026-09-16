# Sony Cyber-shot DSC-G3: Firmware Architecture, Wi-Fi Stack, & Laboratory Research Manual

## Executive Summary & Device Profile

The **Sony Cyber-shot DSC-G3** (announced January 2009, FCC ID: `AK8DSCG3`) is an early connected digital camera featuring integrated 802.11b/g Wi-Fi and an embedded web browser. Designed around Sony's BIONZ image processing platform, the device combines a hard real-time operating system for sensor and optical controls with an embedded Linux environment powering its network stack, storage, and user interface.

This document establishes an authoritative technical baseline, verifiable evidence, and a non-destructive laboratory research framework for inspecting, analyzing, and capturing communications from the DSC-G3 using macOS.

---

## 1. System Architecture & Operating System Internals

```
+-----------------------------------------------------------------------------------+
|                           Sony Cyber-shot DSC-G3 SoC                              |
|                                                                                   |
|  +-------------------------------------+   +-----------------------------------+  |
|  |       Real-Time Subsystem           |   |       Application Subsystem       |  |
|  |                                     |   |                                   |  |
|  | - Architecture: ARM / DSP Core      |   | - Architecture: ARM926EJ-S        |  |
|  | - OS: µITRON 4.0 / Sony AV RTOS     |   | - OS: Access Linux Platform (ALP) |  |
|  | - Execution: Direct Execute in SRAM |   | - Kernel: Linux 2.6.11-alp        |  |
|  | - Functions:                        |   | - Userland: BusyBox               |  |
|  |   * CCD Timing & Pixel Readout      |   | - Browser: ACCESS NetFront v3.4   |  |
|  |   * BIONZ ISP Pipeline              |   | - Networking: 802.11b/g, TCP/IP,  |  |
|  |   * Optical SteadyShot (OIS)        |   |               DLNA/UPnP, DHCP     |  |
|  |   * Autofocus & Aperture Motors     |   | - Storage: 4GB Internal Flash,    |  |
|  |   * JPEG/MPEG Encoding Engine       |   |            Memory Stick Duo       |  |
|  +-------------------------------------+   +-----------------------------------+  |
|                     ^                                    ^                        |
|                     |        Shared Memory / IPC         |                        |
|                     +====================================+                        |
+-----------------------------------------------------------------------------------+
       |                                                            |
       v                                                            v
+-----------------------+                                  +------------------------+
| 4GB Internal Flash    |                                  | Wi-Fi Module           |
| (NAND: System + Data) |                                  | (802.11b/g Baseband)   |
+-----------------------+                                  +------------------------+
```

### A. Chipset & Processing Hardware
* **SoC Family:** Sony **BIONZ** imaging engine. Predecessor research (e.g., DSC-G1) and OpenMemories hardware documentation identify this family as utilizing the Sony **CXD4105** ("Arex") or related CXD41xx application-specific integrated circuit (ASIC).
* **CPU Core:** 32-bit **ARM926EJ-S** core (ARMv5TEJ instruction set) operating with Jazelle DBX Java acceleration and DSP extensions.
* **Co-Processor / Real-Time Core:** A dedicated hardware core running **µITRON** (standard Japanese RTOS specification) or an AV real-time executive for timing-critical image sensor and lens motor actuation.

### B. Operating System & Userland Stack
* **Kernel:** **Linux 2.6.11-alp** (internal development name *"Woozy Beaver"*), released with source code by Sony to comply with GPL licensing requirements (`oss.sony.net`).
* **Platform:** **Access Linux Platform (ALP)**, an open-source/commercial embedded Linux platform developed by ACCESS Co., Ltd. after acquiring PalmSource.
* **Userland Tools:** **BusyBox** embedded utility suite, providing standard POSIX command shells, init scripts, and lightweight network clients.
* **Embedded Browser:** **ACCESS NetFront Browser v3.4**, featuring support for HTML 4.01, cHTML, CSS 1/2, JavaScript 1.5, SSL 3.0 / TLS 1.0, and Adobe Flash Lite / Flash 6.

### C. Flash Storage & Memory Partitioning
* **Internal Storage:** 4 GB onboard NAND flash partitioned into:
  1. Bootloader / IPL (Initial Program Loader).
  2. Kernel partition (raw zImage).
  3. System Root filesystem (read-only compressed image, CramFS or SquashFS).
  4. Configuration / NVM calibration storage (read-write, JFFS2/YAFFS2).
  5. User Media Storage (FAT32 filesystem mounted as mass storage for photos/videos).
* **Removable Storage:** Memory Stick Duo / Memory Stick PRO Duo slot.

---

## 2. Firmware Container Structure & Update Process

Sony firmware updates for this model were distributed as `DSCG3V2.exe`, which unpacks to **`D-G3V2.dat`**.

### A. Container Format Specification (`.dat`)
Upstream reverse engineering from `Sony-PMCA-RE` demonstrates that Sony camera `.dat` containers use an 8-byte magic header followed by tagged chunk headers:

```
00000000: 89 55 46 55 0D 0A 1A 0A                               .UFU....
00000008: [4-byte Size: Big-Endian] [4-byte Tag: ASCII] [Payload...]
```

1. **Magic Header (8 bytes):** `\x89\x55\x46\x55\x0d\x0a\x1a\x0a` (ASCII `\x89UFU\r\n\x1a\n`).
2. **Chunk Header (8 bytes):**
   * `Size` (`uint32_be`): Byte length of the chunk payload.
   * `Type` (`4-byte char`): Chunk type identifier.
3. **Chunk Types:**
   * `FDAT`: Firmware Data chunk containing the kernel, initrd, and flash partition images.
   * `FPRM`: Firmware Parameters (model ID, hardware version constraints).
   * `FSIG`: Cryptographic signature / integrity guard.

### B. Official Update Channels
1. **Memory Stick Method (Consumer Path):**
   * The user copies `D-G3V2.dat` to the root directory of a formatted Memory Stick Duo.
   * Power on camera with external power or full battery.
   * The bootloader validates the `FPRM`/`FSIG` chunk and flashes the `FDAT` image.
   * **Cautionary Notice:** Official Sony documentation states that updating firmware **erases the entire 4GB internal memory**, reformatting the user storage partition.
2. **USB Service Method (SEUS Path):**
   * Uses the proprietary Sony Multi-terminal USB cable with `SeusEX` and model-specific `Auto-Adj.exe`.
   * Negotiates commands over USB SCSI vendor commands (`CMD_INIT 0x01`, `CMD_CHK_GUARD 0x10`, `CMD_SWITCH_MODE 0x30`, `CMD_WRITE_FIRM 0x40`).

---

## 3. Wi-Fi Stack, Protocols, & Services

### A. Wireless Physical & Data Link Layers
* **Standard:** IEEE 802.11b/g (2.4 GHz, Channels 1–11 US / 1–13 JP/EU).
* **Security Modes:** Open, WEP (64/128-bit), WPA-PSK (TKIP/AES), WPA2-PSK (AES-CCMP).
* **Power Management:** Radio remains unpowered during normal shooting; activates only when WLAN button, Easy Upload, or DLNA mode is engaged.

### B. Application Protocols
1. **DHCP Client:** Requests IPv4 parameters with standard Option 55 parameter request list and Option 60 Vendor Class Identifier.
2. **DNS Resolver:** Queries configured DNS server for outbound photo sharing domains.
3. **Embedded Browser (Outbound Client):**
   * Launches NetFront 3.4 when the WLAN button is pressed.
   * Originally pointed to the Sony "Easy Upload" portal (`http://...sony...`) to route uploads to YouTube, Picasa, Photobucket, Shutterfly, and Dailymotion. *(Service sunset December 10, 2014).*
   * Provides captive portal authentication on public hotspots (e.g., AT&T / Wayport).
4. **DLNA / UPnP AV (Inbound/Outbound Media Server):**
   * **SSDP (UDP 1900):** Sends `NOTIFY` multicasts and responds to `M-SEARCH` requests on multicast address `239.255.255.250:1900`.
   * **HTTP Media Server:** Runs an embedded HTTP server on an ephemeral high port (e.g., TCP 8080 or dynamic port) serving XML device descriptors (`device.xml`) and thumbnail/image streams.

### C. Public Vulnerability & Reverse-Engineering Corpus
* **Sony-PMCA-RE Project:** Reverse-engineered the BIONZ USB updater protocol, `.dat` file structures, and NVM backup formats (`BK2`/`BK4`).
* **OpenMemories:** Documented the CXD41xx architecture, ARM926EJ-S cores, and QEMU-based emulation for BIONZ processors.
* **GPL Distributions:** Confirms the 2.6.11-alp kernel tree, BusyBox integration, and network device drivers.

---

## 4. Mac-Native Laboratory Capture & Analysis Plan

Because all testing will run from the Mac workstation, the laboratory harness uses macOS's built-in networking utilities (`networksetup`, `tcpdump`, Internet Sharing) and Python scripts.

```
                              ISOLATED MAC LAB HARNESS
+-------------------+        802.11b/g          +--------------------------------------+
|                   |  ~~~~~~~~~~~~~~~~~~~~~~>  |       macOS Workstation              |
|  Sony DSC-G3      |                           | - Wi-Fi AP via Internet Sharing OR   |
|  (Camera)         |  <~~~~~~~~~~~~~~~~~~~~~~  |   Ad-Hoc / Dedicated USB Wi-Fi AP    |
|                   |  <~~~~~~~~~~~~~~~~~~~~~~  | - tcpdump packet capture on en0/en1  |
+-------------------+                           | - Python Mock HTTP & UPnP Analyzer   |
                                                +--------------------------------------+
```

### Step 1: Setting Up the Isolated Wi-Fi Network on Mac
To observe the camera without exposing it to the live internet:
1. **Dedicated Wi-Fi Interface:** If using Mac's built-in Wi-Fi (`en0`):
   * Create a local computer-to-computer (ad-hoc) network or enable **System Settings > General > Sharing > Internet Sharing** (sharing from a disconnected/dummy interface or local loopback to Wi-Fi).
   * Alternatively, use a supported USB 802.11b/g Wi-Fi adapter configured with an isolated SSID: `Lab_G3_Research`.
2. **Network Parameters:**
   * Subnet: `192.168.2.0/24` (Mac IP: `192.168.2.1`).
   * Security: WPA2-PSK (AES) with a simple alphanumeric key (avoid special characters that legacy NetFront input methods might mishandle).

### Step 2: Capturing Network Traffic with `tcpdump`
Open Terminal on macOS and execute a packet capture bound to the wireless interface:

```bash
# Identify your Wi-Fi interface (typically en0 or en1)
networksetup -listallhardwareports

# Start passive capture with full packet payloads
sudo tcpdump -i en0 -s 0 -n -w dsc_g3_baseline.pcap
```

### Step 3: Triggering Camera Communications
1. Turn on the camera.
2. Verify Wi-Fi network selection: navigate to **HOME > Settings > Network Settings > Access Point Settings**. Select `Lab_G3_Research`.
3. Press the physical **WLAN** button.
4. Observe the capture file in Wireshark or via `tools/g3_network_analyzer.py`.

### Step 4: Local Server Interoperability & Mock Services
Run the mock diagnostic server (`tools/g3_network_analyzer.py mock-server --port 8080`) to inspect NetFront's HTTP requests:
* Inspect `User-Agent` string, `Accept` headers, and cookies.
* Serve a mock diagnostic HTML form to observe how NetFront handles file uploads and local links.

---

## 5. Offline Firmware Extraction Workflow

When the firmware update file (`D-G3V2.dat` / `DSCG3V2.exe`) is acquired:
1. **Extract Container:** Run `python3 tools/g3_firmware_parser.py extract D-G3V2.dat --output-dir evidence/g3_firmware`.
2. **Inspect Hashes:** Verify the SHA-256 digests generated in `manifest.json`.
3. **Carve File Systems:**
   ```bash
   binwalk -Me evidence/g3_firmware/chunk_0_FDAT.bin
   ```
4. **Static Audit in Ghidra:**
   * Architecture: `ARM:LE:32:v5TE` (ARM926EJ-S).
   * Search for:
     * Inbound daemons (`telnetd`, `httpd`, `inetd`).
     * Hardcoded URLs or URLs matching `http://` in the NetFront binary.
     * Environment variables or command injection points in startup scripts (`/etc/init.d/*`).

---

## 6. Diagnostic, Maintenance, & Safety Precautions

### A. Non-Destructive Firmware Policy
* **Zero Arbitrary Flashing:** Never write arbitrary code or altered `.dat` files to the physical camera.
* **Emulation-First Verification:** Any code or shell testing must first be proven in `qemu-system-arm` before physical testing is even considered.

### B. Physical Diagnostic Inspection (UART)
* If the camera chassis is opened in future research:
  * Locate the `SY-xxx` main board test pads.
  * Baud rate: 115,200 bps, 8-N-1, 3.3V CMOS logic.
  * **Critical Safety Rule:** Connect **only the RX pin** of your 3.3V FTDI / serial adapter to the camera's TX pad (along with GND). Leave the adapter's TX line floating/disconnected. This guarantees 100% passive listening with zero electrical risk of driving voltage into the BIONZ SoC.

### C. Built-in Firmware Version Verification
To read the current installed ROM version directly on the physical camera without tools:
1. Power off the camera and open the lens cover.
2. Hold down the **"T" (Zoom)** button and simultaneously press the **Playback** button to power on.
3. Tap **HOME > Settings > Main Settings > Page 3/7**.
4. Read the active ROM version string (e.g., `Ver 1.00` or `Ver 2.00`).

### D. Emergency Recovery Precautions
* **Regulated External Power:** Any camera maintenance, backup, or diagnostic procedure must use the **Sony AC-LS5 AC adapter and DC coupler**, never a depleted lithium battery.
* **Preserving Calibration Tables:** The factory NVM stores optical alignment, autofocus tables, and dead-pixel maps. Never perform blind EEPROM/NAND erasures, as factory calibration cannot be recreated without Sony optical jig hardware.

---

## 7. Verified Facts vs. Working Hypotheses

| Category | Verified Technical Fact | Working Hypothesis / Unverified Lead | Primary Evidence |
| :--- | :--- | :--- | :--- |
| **SoC / CPU** | ARM926EJ-S core running Linux alongside real-time co-processor. | Exact SoC ASIC part number is likely CXD41xx (similar to DSC-G1's CXD4105). | Sony Open Source Distribution; OpenMemories Docs (`Hardware.md`). |
| **OS & Kernel** | Linux 2.6.11-alp ("Woozy Beaver"), BusyBox, Access Linux Platform (ALP). | Exact custom kernel driver names for BIONZ IPC shared memory pipes. | *Linux Magazine* (2009); Sony OSS repository (`oss.sony.net`). |
| **Browser** | ACCESS NetFront Browser 3.4 with Flash Lite 6. | Whether custom URI schemes (e.g. `file://`, `camera://`) are reachable from web pages. | Impress Watch (Jan 2009); Sony DSC-G3 User Handbook. |
| **Firmware Container** | Structured `.dat` file with `\x89UFU\r\n\x1a\n` header and `FDAT` chunk. | Exact filesystem compression on carved `FDAT` partitions (CramFS vs. SquashFS). | `pmca/firmware/__init__.py`; `pmca/commands/usb.py`. |
| **Network Flashing** | No official OTA update protocol exists; updates require Memory Stick or USB SEUS. | Whether bootloader has dormant TFTP/DHCP boot features accessible via network. | Sony Level 2 Service Manual; Sony Support Update Advisory. |
| **Open Ports** | DLNA/UPnP SSDP (UDP 1900) and UPnP HTTP media server are active. | Whether BusyBox `telnetd` or a service shell can be activated via network parameters. | FCC ID `AK8DSCG3`; Sony G3 Specifications. |
