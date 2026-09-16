# Cross-Platform Architecture: Sony Cyber-shot DSC-W300 & DSC-G3

## 1. Dual-Platform Overview

This repository houses the research, reverse engineering, and tooling for two landmark Sony Cyber-shot digital cameras from the BIONZ era:

1. **Sony Cyber-shot DSC-W300 (2008)**:
   - High-end compact titanium digital still camera.
   - Sensor: 1/1.7" Super HAD CCD (13.6 MP).
   - Core Focus: Destination code & language persistence (enabling persistent English menus on Japanese domestic J1 hardware without board transplantation).
   - Interface: Wired multi-terminal USB using Sony SEUS / Service Adjustment protocols.

2. **Sony Cyber-shot DSC-G3 (2008/2009)**:
   - Connected digital camera with 802.11b/g Wi-Fi and 3.5" touchscreen.
   - Sensor: 1/2.3" Super HAD CCD (10.1 MP).
   - Core Focus: Complete firmware decryption (CXD4108 MsFirm), CramFS rootfs extraction, custom string display POC, and image pipeline / video noise reduction tuning.
   - Interface: Dual-stack (Wi-Fi 802.11b/g NetFront 3.4 + wired USB + Memory Stick Duo firmware bootloader).

---

## 2. Shared Architectural Foundations & Artifact Reuse

Despite differing form factors and connectivity, both cameras belong to the same Sony engineering generation and share key architectural layers:

```
+-----------------------------------------------------------------------------------+
|                        SHARED SONY BIONZ FOUNDATIONS                              |
+-----------------------------------------------------------------------------------+
| 1. Asymmetric Dual-Core Architecture:                                              |
|    - Host CPU: ARM core (ARM926EJ-S in G3) executing OS and high-level UI.         |
|    - Real-Time DSP: ARM / µITRON 4.0 co-processor handling sensor timing, 3A,      |
|      BIONZ hardware ISP line-buffer coring, and JPEG/MPEG compression.            |
|    - Inter-Processor Communication (IPC): ARM PrimeCell PL320 mailbox interface.  |
+-----------------------------------------------------------------------------------+
| 2. Storage & Memory Stick Subsystem:                                              |
|    - Removable Media: Memory Stick Duo / PRO Duo parallel 4-bit bus.              |
|    - Internal Storage: OneNAND flash partition tables (/dev/nflasha1..nflasha12).  |
|    - Firmware Update Packaging: Sony MsFirm Memory Stick container format.        |
+-----------------------------------------------------------------------------------+
| 3. Service & Calibration Infrastructure:                                          |
|    - Service Mode Handshake: Senser communication protocol (sen / libsencore.so). |
|    - Destination & Language Tables: Destination bitmasks and localized CSVs.     |
|    - NVM & Calibration: Optical/shutter adjustment data preserved via backup.     |
+-----------------------------------------------------------------------------------+
```

### Artifact & Tooling Reusability Matrix

| Component / Artifact | DSC-W300 Applicability | DSC-G3 Applicability | Reusability Scope |
| :--- | :--- | :--- | :--- |
| **`CXD4108MsCrypter`** (`tools/g3_firmware_parser.py`) | Reference for older BIONZ MS container encryption (`key_cxd4108_ms`). | Production decrypter for `D-G3V2.dat`. | **Direct Tooling**: Can decrypt any CXD4105/CXD4108 Memory Stick firmware. |
| **Ghidra CLI Bridge** (`tools/ghidra`) | Static disassembly of adjustment tools and USB payloads. | Static analysis of 96 ARM ELF binaries and `09_av.bin`. | **Universal Tool**: Shared headless reverse-engineering platform on macOS ARM64. |
| **USB Protocol Sniffer** (`tools/w300_evidence.py`) | Passive macOS IOKit inventory & USB descriptor parsing. | USB Mass Storage & PTP mode verification. | **Direct Tooling**: Audits all Sony USB vendor descriptors without hardware risk. |
| **Language Persistence Mechanics** | Destination code rewrite (EEPROM / Service Adjustment p.11). | String replacement in `fskapp1/dsc/app/scripts/language/eng.csv`. | **Cross-Pollination**: Both cameras load localized strings dynamically from flash. |
| **Image Pipeline Architecture** | Sensor 3A, CCD timing, and dark-frame subtraction in µITRON. | BIONZ ISP line-buffer coring, `setNR`, and MPEG quantization in `09_av.bin`. | **Architectural Insight**: Reveals how BIONZ DSP separates still vs video processing. |

---

## 3. Directory Layout & Organization

The repository is cleanly partitioned into dedicated camera domains while retaining shared libraries and tools:

```
DSC-W300 and DSC-G3/
├── README.md                      # Master repository documentation
├── .gitignore                     # Git tracking rules excluding large binaries
│
├── docs/                          # Comprehensive technical documentation
│   ├── w300/                      # DSC-W300 guidance & Japanese language persistence
│   ├── g3/                        # DSC-G3 architecture & firmware modification POC
│   └── shared/                    # Cross-platform BIONZ architecture dossier
│
├── evidence/                      # Verified empirical logs & extracted artifacts
│   ├── w300/                      # W300 USB captures, service manual pages, archive scans
│   ├── g3/                        # G3 decrypted inventory, architecture MD, extracted tree
│   └── shared/                    # Benchmarking against SONY_NX3_Reversal
│
├── sources/                       # Firmware archives, service manuals, upstream repos
│   ├── w300/                      # W300 adjustment manuals & handbooks
│   ├── g3/                        # G3 firmware updater EXE & DAT files
│   └── shared/                    # Sony-PMCA-RE upstream reference snapshot
│
└── tools/                         # Automated Python test suites and CLI utilities
    ├── w300_evidence.py           # W300 hardware inventory and comparison tool
    ├── g3_firmware_parser.py      # G3 MsFirm decrypter & pure-Python CramFS unpacker
    ├── g3_text_poc.py             # Fail-closed custom string POC tool
    ├── g3_network_analyzer.py     # G3 Wi-Fi PCAP analyzer & mock gateway
    ├── ghidra                     # Headless Ghidra CLI binary
    └── test_*.py                  # 87 automated unit and regression tests
```
