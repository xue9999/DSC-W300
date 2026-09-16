# Sony Cyber-shot Dual-Platform Research: DSC-W300 and DSC-G3

A unified laboratory repository for offline reverse engineering, firmware analysis, and software modifications across two iconic Sony Cyber-shot digital cameras from the BIONZ era:

1. **Sony Cyber-shot DSC-W300** (13.6 MP CCD, Titanium Chassis, USB Service Adjustment & English Menu Persistence).
2. **Sony Cyber-shot DSC-G3** (10.1 MP CCD, 802.11b/g Wi-Fi, 3.5" Touchscreen, CXD4108 BIONZ Linux/µITRON Architecture).

---

## 1. Workstream Status & Highlights

```
+===================================================================================+
|                              WORKSTREAM DASHBOARD                                 |
+===================================================================================+
| DSC-W300 Workstream:                                                              |
| - Focus: Japanese Domestic (J1) Model English Persistence                         |
| - Status: Service Manual Ver 1.3 analyzed (p. 11 Destination Write boundaries)     |
| - Tooling: tools/w300_evidence.py (passive macOS IOKit USB inventory)             |
| - Guidance: docs/w300/ANALYSIS_LOG.md & make a Japanese DSC-W300 display English.md|
+-----------------------------------------------------------------------------------+
| DSC-G3 Workstream:                                                                |
| - Focus: Firmware Decryption, RootFS Extraction, Custom String POC & Image Tuning |
| - Status: 100% VICTORY CONFIRMED by Independent Victory Auditor                   |
| - Decryption: LHA Level 2 stream (0x744F) + CXD4108 MsFirm (24 sections decrypted)|
| - Filesystems: Pure-Python CramFS userland decompressor (BodyUdtr.img & rootfs.img)|
| - Custom String POC: tools/g3_text_poc.py (SETUP_VERSION -> "G3 POC" in eng.csv)   |
| - Image Pipeline: BIONZ video NR analysis (setNR & Qscale in 09_av.bin)           |
| - Dossiers: docs/g3/DECRYPTED_ARCHITECTURE.md & FIRMWARE_MODIFICATION_POC_DESIGN.md |
+-----------------------------------------------------------------------------------+
| Shared Foundations:                                                               |
| - Architecture: Dual-Core ARM Host + µITRON 4.0 Co-Processor + Memory Stick Bus   |
| - Emulation: CXD4108 QEMU staging, SDM partition builder & launcher tooling       |
| - Test Suite: 94/94 Automated Tests Passing (python3 -m unittest discover)        |
+===================================================================================+
```

---

## 2. Repository Structure

The codebase is structured to allow clean separation between camera-specific assets while enabling maximum reuse of shared reverse-engineering tooling:

```
DSC-W300 and DSC-G3/
├── README.md                              # This document
├── .gitignore                             # Git tracking rules excluding large blobs
│
├── docs/                                  # Structured technical documentation
│   ├── w300/                              # DSC-W300 guides and adjustment procedures
│   │   ├── ANALYSIS_LOG.md                # W300 durable project guidance
│   │   └── make a Japanese DSC-W300...md  # Japanese menu persistence roadmap
│   ├── g3/                                # DSC-G3 reverse engineering dossiers
│   │   ├── G3_RESEARCH_GUIDANCE.md        # Hardware, Wi-Fi & firmware reference
│   │   ├── DECRYPTED_ARCHITECTURE.md      # Canonical architecture dossier (NX3 format)
│   │   └── FIRMWARE_MODIFICATION_POC_DESIGN.md # Custom string POC design
│   └── shared/                            # Shared BIONZ architecture & comparisons
│       ├── CROSS_PLATFORM_ARCHITECTURE.md # Cross-model architecture & reuse matrix
│       └── EMULATION_AND_OPENMEMORIES_CI.md # QEMU CXD4108 & OpenMemories-CI guide
│
├── evidence/                              # Verified empirical logs & extracted artifacts
│   ├── w300/                              # W300 USB captures, service manual page PNGs
│   ├── g3/                                # G3 decrypted inventory JSON & extracted tree
│   │   └── extracted_g3/                  # 24 decrypted sections, rootfs, kernel
│   └── shared/                            # Benchmarking against SONY_NX3_Reversal
│
├── sources/                               # Firmware executables, manuals & upstreams
│   ├── w300/                              # W300 adjustment manuals (PDF/TXT) & handbooks
│   ├── g3/                                # G3 firmware updater (DSCG3V2.exe, D-G3V2.dat)
│   ├── OpenMemories-CI/                   # Upstream firmware CI test suite & runners
│   ├── fwtool.py/                         # Upstream firmware & CramFS archive library
│   ├── qemu/                              # Upstream QEMU fork implementing 'cxd4108'
│   └── shared/                            # Sony-PMCA-RE, OpenMemories-CI, fwtool, qemu
│
└── tools/                                 # Production Python CLI tools & test suites
    ├── cxd4108_emulator/                  # CXD4108 SDM flash builder & QEMU launcher
    ├── w300_evidence.py                   # W300 passive macOS USB inventory parser
    ├── g3_firmware_parser.py              # G3 MsFirm decrypter & pure-Python CramFS engine
    ├── g3_text_poc.py                     # Fail-closed custom string POC tool
    ├── g3_network_analyzer.py             # G3 Wi-Fi PCAP analyzer & mock gateway
    ├── ghidra                             # Headless Ghidra CLI binary (macOS ARM64)
    └── test_*.py                          # 94 automated unit and integration tests
```

---

## 3. Quick Start & Tool Usage

### Running the Test Suite
All 94 tests execute 100% offline within the secure sandbox without external dependencies:
```bash
python3 -m unittest discover -s tools -p "test_*.py" -v
```

### Checking CXD4108 Emulation Status
Verify the availability of QEMU binaries, cloned upstreams, and firmware evidence:
```bash
python3 tools/cxd4108_emulator/qemu_launcher.py status
```

### Unpacking DSC-G3 Firmware
Decrypt and extract all 24 sections, CramFS filesystems, and tarballs:
```bash
python3 tools/g3_firmware_parser.py unpack \
  --exe sources/DSCG3V2.exe \
  --out evidence/extracted_g3
```

### Generating the Custom String Display POC
Generate a verified, cryptographically signed firmware container with a custom display string:
```bash
python3 tools/g3_text_poc.py --string "G3 POC"
```

### Auditing Connected Sony USB Hardware
Passively inspect connected Sony digital cameras via macOS IOKit:
```bash
python3 tools/w300_evidence.py inventory
```

---

## 4. Non-Destructive Laboratory Policy

All research and tooling strictly adhere to non-destructive laboratory rules:
1. **Closed Enclosure**: No physical hardware disassembly, probing, or board modification.
2. **Zero In-Camera Flashing**: No arbitrary code or experimental writes sent to physical cameras.
3. **Fail-Closed Verification**: All modified firmware files must pass end-to-end cryptographic and structural roundtrip tests before acceptance.
