# DSC-G3 Acquisition Evidence & Source Provenance

This document tracks the acquisition status, known locations, file identifiers, and hashes for primary materials relating to the Sony Cyber-shot DSC-G3.

## 1. Firmware Update Package

- **Official Title:** Sony Cyber-shot DSC-G3 Firmware Update Version 2 (2009-03-25)
- **Primary Purpose:** Resolves DNS timeout issues when connecting to wireless networks.
- **Distribution Filename:** `DSCG3V2.exe` (Win32 self-extracting archive)
- **Contained Payload:** `D-G3V2.dat` (Sony binary firmware container)
- **Official Legacy URLs:**
  - Sony Support USA: `https://www.sony.com/electronics/support/compact-cameras-dsc-g-series/dsc-g3/software/00257088` (or legacy `esupport.sony.com`)
  - Sony Support Japan: `https://www.sony.jp/support/cyber-shot/products/DSC-G3/`
- **Acquisition Status:** Not currently present in local workspace.
- **Downstream Processing:**
  - Once acquired, extract `D-G3V2.dat` using 7-Zip, unshield, or running `DSCG3V2.exe` in a Windows VM / Wine.
  - Run `python3 tools/g3_firmware_parser.py extract D-G3V2.dat --output-dir evidence/g3_firmware` to parse and verify chunks.

## 2. Technical Service Documentation

- **Level 2 Service Manual:** `Sony DSC-G3 Level 2 Service Manual` (Sony EMCS). Documents disassembly, block diagrams, board part numbers (`SY-xxx`), and destination setup.
- **Level 3 Service Manual:** `Sony DSC-G3 Level 3 Service Manual`. Documents component-level schematics and IC pinouts.
- **Adjustment Manual:** `Sony DSC-G3 Adjustment Manual Ver. 1.2`. Documents service mode connection (`SeusEX`, `Auto-Adj`), DC coupler power requirements, and NVM calibration data backup (`DSC-G3_ADJBAK_xxxxxxxx_yyyymmdd.dat`).
- **Hosting Repositories:** Elektrotanya, Vinafix, manualslib.

## 3. FCC Certification Records

- **FCC ID:** `AK8DSCG3`
- **Grantee Code:** `AK8` (Sony Corporation)
- **Product Code:** `DSCG3`
- **Grant Date:** 2008-09-04
- **Public Exhibits:**
  - `Internal Photos`: 995701
  - `External Photos`: 995700
  - `Test Report 1`: 995708
  - `Test Report 2`: 995709
  - `User Manual Parts I, II, III`: 1054130, 1054131, 1054132

## 4. Open Source Software (OSS) Packages

- **Source Portal:** Sony Source Code Distribution Service (`oss.sony.net`)
- **Package:** `Linux 2.6.11-alp` ("Woozy Beaver") kernel source and `BusyBox` configuration files published under GNU General Public License (GPL).
- **Embedded Browser:** ACCESS NetFront Browser 3.4 (proprietary engine by ACCESS Co., Ltd.).
