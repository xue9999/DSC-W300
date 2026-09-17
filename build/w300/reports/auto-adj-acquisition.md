# Auto-Adj acquisition and driver inspection

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

Date: 2026-09-16. Scope: public read-only acquisition; no camera connected, no driver installed, no downloaded binary executed. Existing `sources/` and `evidence/` were unchanged.

## Result

The routes below yielded service documentation, package locators and an actual Sony driver ZIP. Find a new source that provides `DSC-W300 Auto-Adj Ver_1.3r04.exe` and compatible SeusEX binaries. Inspect the packages and determine whether they support the original board before selecting the runtime.

One actual dependency candidate was acquired: an old 32-bit Sony Seus USB Driver package. This is a useful static-analysis artifact, **not a validated W300 driver or complete service application**.

## Downloaded driver candidate

- Discovery page: https://www.driveridentifier.com/scan/sony-usb-device-driver/download/641411935/2FEC54AF7D474831A5B799ACFFCF8B1E/USB%5CVID_054C%26PID_0336
- Detail page: https://www.driveridentifier.com/scan/sony-seus-usb-driver/driver-detail/2FEC54AF7D474831A5B799ACFFCF8B1E/719839/13d83993260f266333d3fef3ed0ae4db/641411935/USB-VID_054C%26PID_0336
- Actual direct download (HTTPS succeeded with certificate verification): https://server09.driveridentifier.com/data/jan2012/20120114/Sony%20Seus%20USB%20Driver.zip
- Local archive: `build/w300/downloads/auto-adj/sony-seus-usb-1.0.8.zip`
- Bytes: 96,332.
- SHA-256: `5328FC898ECEF188AF7A848798593B0EADD1AA906FDDA3DB2A248F20B8B79CCC`.
- Expanded for inspection only: `build/w300/downloads/auto-adj/seus-driver-1.0.8-inspection/`.

| Archive entry | Size | Static finding |
| --- | ---: | --- |
| oem21.inf | 35,070 | Provider/Manufacturer Sony Corporation; DriverVer 06/10/2011,1.0.8; WinRT for USB; many Sony VID_054C PIDs; no catalog entry |
| WinRTUSB.sys | 41,984 | PE machine 0x014C (x86), BSQUARE CORPORATION, WinRT for USB Windows XP Driver, 2.102 built by WinDDK, Authenticode NotSigned |
| WinRTUSB.dll | 192,512 | PE machine 0x014C (x86), BSQUARE CORPORATION, WinRT for USB User-Mode DLL Module (cdecl), 2.101, Authenticode NotSigned |
| driveridentifier.txt | 157 | Third-party redistribution record |

Checks are saved in `build/w300/downloads/auto-adj/seus-driver-static-verification.json`. The INF identifies a kernel driver service called WinRTUSB. The binary architecture is direct evidence that this acquired kernel driver is not an x64 driver. Do not install it on the current x64 host or weaken signature checks. The website's generic claims of compatibility through Windows 11 are not reliable evidence, and its explanation confusing Sony Seus with Sony Ericsson Update Service is not relied on. Matching a PID in a broad INF would not establish language-change support.

## Distinct acquisition routes tried

### 1. Archive.org software and technical-disc collections

Queried software metadata for Sony service/repair/adjustment/diagnostic/utility/tools and queried exact SeusEX, SeusCam, AdjustStation, auto-adj variants. Downloaded metadata and file inventories rather than treating item titles as payloads. Reports under `ia-*.json` preserve query responses.

Inspected:
- `sony-tekman-consumer-service-technical-information-sony-technical-information-ma`: March 1999 technical CD, BIN/CUE plus scans; predates W300. Not downloaded as a W300 candidate.
- `sony-das-original`: metadata and ZIP inventory describe CRT monitor Digital Alignment System, not camera SeusEX.
- `sony-utility-disc-compilation-v3` and `sudc4`: actual descriptions identify PlayStation 2/DVD-player utilities, not Cyber-shot tools.
- `ss-010-p-2`: BVM BZI diagnostic software, ZIP files SS010P_1 through SS010P_4; wrong product family.
- `sonypictutil_2007`: consumer camera software ISO, not a claimed service bundle; no service payload obtained.
- `sony-cyber-shot-dsc-f828-service-manual`: file inventory lists four PDFs and generated derivatives, no adjustment executable.

A broader query for camera-service software returned Minolta adjustment/ROM packages and a Casio QV-10 repair tool; none is for the target camera. A filename-field scrape query returned zero, but this does not exhaust archive interiors and is not proof that no archived binary exists.

Finding and follow-up: wrong-package/wrong-device results and no exact publicly indexed package, **not an environment or dependency installation failure**. Safe next avenue was to separate acquisition of the driver dependency from acquisition of the complete application; that yielded the actual ZIP above.

### 2. eServiceInfo archive search and contents

Fetched the site's own DSC-W300 search results to `eservice-w300-search.html`. Search returned Sony Ericsson W300 phone documents and other DSC model manuals/archives, without a W300 service executable result. Examined displayed decompressed-file contents for neighboring Auto-Adj archive hits, including:
- https://www.eserviceinfo.com/downloadsm/42954/SONY_DSC-HX1.html : one PDF, 36 KB archive, no executable.
- https://www.eserviceinfo.com/downloadsm/60971/Sony_DSC-W120%20W125.html : two PDF documents in a 2,584 KB archive.

Finding and follow-up: misleading archive/model keyword matches and manuals without tool payloads. These are not missing-library errors. Do not infer an executable from an Auto-Adj PDF/archive title.

### 3. Regional and exact-name software searches

Used English, Russian, Japanese, and Chinese query variants, including literal `SeusEX.exe`, `DSC-W300 AutoAdj`, `SeusEX_x64_128200.zip`, and the exact Auto-Adj version. Results remained manuals, catalog entries, and service-portal references. No public executable or complete installation bundle was recovered.

A Russian W270 repair thread discusses old Aladdin versus later SafeNet driver generations and reports a later SeusEX working under Windows 7. Use this version lead to acquire the actual package and inspect W300 support: https://forum-monitor.net.ru/threads/585578/ . It points to a partial `/IBISS_Files/DSC/Software/` path without a publicly accessible complete download link. No credentials, service portal login, or correspondence was used.

An indexed Sony ASC portal introduction displays the newer filename `SeusEX_x64_128200.zip` in a screenshot; a screenshot is not an accessible installer or proof of W300 compatibility. No bearer tokens or portal credentials were used.

### 4. Driver-specific public catalogs, followed to actual payload

DriverMax's nominal driver link invokes its own downloader flow. DriverScape's current Download button points to `DriverToolkitInstaller.exe`. Neither third-party utility was downloaded or executed. The DriverIdentifier detail HTML contained a direct static driver ZIP URL; HTTPS download succeeded, and the archive was statically inspected as above.

Outcome: an actual dependency candidate was acquired and identified as an unsigned x86 driver redistributed by a third party. Use this architecture finding to select the next compatible driver candidate while pursuing exact Auto-Adj and SeusEX packages separately.

### 5. Public source-code index

grep.app API requests for exact SeusEX/Auto-Adj strings returned HTTP 429. This is an external access/rate-limit failure, not evidence of absence. No authentication workaround was attempted. Local PMCA source analysis remains the practical independent route and is owned by the main task.

## Reproduction

From the repository root in PowerShell:

```powershell
Invoke-WebRequest -Uri 'https://server09.driveridentifier.com/data/jan2012/20120114/Sony%20Seus%20USB%20Driver.zip' -OutFile 'build/w300/downloads/auto-adj/sony-seus-usb-1.0.8.zip'
Get-FileHash -LiteralPath 'build/w300/downloads/auto-adj/sony-seus-usb-1.0.8.zip' -Algorithm SHA256
```

Archive inspection uses .NET `System.IO.Compression.ZipFile.OpenRead`, then reads INF text, PE machine words and file-version metadata; `Get-AuthenticodeSignature` provides signature status. No executable is loaded to inspect these values.

## Next acquisition and implementation task

Acquire the exact W300 Auto-Adj executable with usable SeusEX and documented HASP requirements. Inspect its destination routine, original-board eligibility and affected data before implementing the smallest required adapter. If the package source cannot supply bytes, continue W300 firmware/trace acquisition and prepare the alternative [file-read route](g3-file-read/README.md), coordinated by the [execution plan](../../../docs/w300/EXECUTION_PLAN.md). Preserve the identification helper and simulator as distinct tools while qualifying the hardware operation. Verify backup/restoration and persistence before the separately authorized write stage.
