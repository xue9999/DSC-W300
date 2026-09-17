# W300 service-board and recovery audit

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

## Result and scope

Read-only source audit performed on 2026-09-16. No USB command was issued and no source or retained evidence file was changed. The precise Sony program has a documented destination-write function for the DSC-W300, but the documented workflow explicitly excludes boards other than service boards. A normal original production board cannot be called eligible on the evidence reviewed here. This is not proof that changing an original board is technically impossible: the gate implementation and a validated alternative remain unknown.

The strongest additional evidence is Sony's W300 Level 2 service note, section 1-1, which ties destination writing to replacement of the **SY-199** board and separately says that a new service board lacks the original factory USB identity. Consequently, “service board” is a category of replacement board, not a synonym for any camera connected in Adjustment Mode. An exact binary, W300-specific protocol trace, or equivalent implementation evidence is needed to establish whether the restriction is in Auto-Adj, camera firmware, stored board metadata, or hardware. Entering service mode alone does not discharge this requirement.

## Sources inspected

- Local Sony-authored primary source: `sources/sony_dsc-w300_adjustment_ver1.3.pdf`, Sony document **9-852-287-54**, 37 PDF pages, paired with `sources/sony_dsc-w300_adjustment_ver1.3.txt`.
- Relevant existing page renders visually inspected: `evidence/adj-page-11.png` and `evidence/adj-page-36.png`. These confirm both the tabular language details and wording contained only in the p.11 dialog image.
- Sony-authored DSC-W300 Level 2 service manual reproduced at [section 1-1, PDF page 5 / printed 1-1](https://www.manualslib.com/manual/767486/Sony-Dsc-W300.html?page=5) and [section 1-5, PDF page 8 / printed 1-4](https://www.manualslib.com/manual/767486/Sony-Dsc-W300.html?page=8). The host is a third-party manual mirror; the technical content is Sony's source material.
- Repository context: `ANALYSIS_LOG.md`, `docs/w300/README.md`, `sources/manifest.json`, `evidence/acquisition.md`, and `evidence/usb-investigation.md`. These are prior research context rather than independent model-support proof.
- Current Sony public W300 support pages still list PlayMemories Home as their software download; that software is not Auto-Adj: [Sony India W300 support](https://www.sony.co.in/electronics/support/compact-cameras-dscw-series/dsc-w300).

## Exact supported operation

The model-specific program is **DSC-W300 Auto-Adj Ver_1.3r04.exe**. Sony ADJ PDF p.9 / printed 6-8 describes it as driving adjustments through SeusEX. The revision history (PDF p.37) matters: 1.2r03 corrected Destination Data Write, while 1.3r04 corrected entry into Adjustment Mode. An earlier executable is not interchangeable without review.

For a qualified service board, the actual documented operation is Main Menu > **DESTINATION DATA WRITE** > choose destination > **Data Write**. Opening this screen reads and displays the current destination; clicking the Destination Check area refreshes that read (PDF p.11 / printed 6-10; text lines 566-594).

The p.11 dialog image states that the write completes first, that changes take effect after reset, and that pressing **OK automatically resets the camera**. Its opening status text is `Destination Data Write Completed.` Do not mistake this OK button for a read-only acknowledgement before the write. The final step is a fresh Destination Check.

The table offers several English-initial destinations. **U2** is English-initial and **NTSC**, like the Japanese **J1** video default. **CEE8** is English-initial but **PAL**. CEE8 is therefore not automatically the minimum-scope target for a Japanese original when English is the only goal. The table does not reveal whether changing destination also changes other undisclosed fields, and it does not supply the destination's encoding, memory address, checksum, or USB request. No raw values should be inferred from list order.

## Environment and connection supported by the manual

- ADJ p.3 / printed 6-2 specifies Windows **2000 / XP Home / XP Pro**, at least 256 MB RAM recommended, USB 2.0 recommended with 1.1 compatible, and **two USB connectors** for camera and HASP. This is a historical supported configuration, not proof that current Windows cannot run the eventual program. Binary/driver inspection remains necessary before selecting a VM.
- SeusEX must be installed and started before Auto-Adj. Legacy SEUS and SeusCam must not be running simultaneously (ADJ p.9).
- ADJ p.30 / printed 6-29 requires a **HASP key** and directs the operator to start SeusEX and click **Connect**, with expected status `connected`. Exact SeusEX/HASP-driver versions are not specified in this manual. Verify the matching HASP entitlement/key alongside the actual service package.
- The documented power arrangement is **AC-LS5**, part **1-479-284-51**, through the USB/A/V/DC multi-use cable **1-830-848-21** (ADJ pp.3-4). A USB data cable by itself is not the documented external power arrangement. The supplied cable's DC capability and availability of this power source need physical confirmation before relying on that method.
- Auto-Adj **CONNECT** actively changes camera mode; it is not passive identification. The corrected p.10 sequence instructs connection and power-on, CONNECT, camera power-off on the prompt, complete removal of DC input or multi-connector, reconnection and power-on, then OK. Qualify whether every mode transition is volatile through separate target-model evidence.
- **END** releases Adjustment Mode. The manual then requires a power cycle and confirmation of the normal USB screen (ADJ p.10). SeusEX disconnects when the camera resets or powers off, so reconnection may be needed (p.30).
- The W300 Level 2 internal-memory procedure explicitly names **Sony Seus USB Driver**, but does not give a version. It uses camera USB mode **Mass Storage**. This corroborates a service-driver dependency; it does not fully specify the Auto-Adj driver-install sequence.

## Initial state and backup boundaries

| Data | Documented read/backup | Documented restore | Proven limitation |
|---|---|---|---|
| Current destination | Open Destination Data Write; refresh Destination Check | Select a destination and use Data Write, for a qualified service board | No destination backup file, encoding, or original-board restore guarantee is documented. |
| Original USB identity | USB SERIAL No. INPUT > Check Serial; Read and Save | Load and Write using the original saved serial file | Separate identity backup, not a calibration or firmware backup. Do not use Write Manually or generate a service identity for the user's original board. |
| Adjustment data | DATA BACKUP > Data Read and Save | Data Load and Write using the saved ADJBAK file | Documented coverage: Video, LCD and Camera System Adjustments. Establish separate coverage and restoration evidence for destination data, firmware, remaining flash partitions and recovery after interrupted operation. |
| Photographs in internal storage | Ordinary file transfer or the camera's Copy function | A separate, temporary internal-memory write-enable workflow is described by Level 2 | User photographs are not camera firmware or a calibration backup. |

ADJ p.12 / printed 6-11 gives the identity filename `DSC-W300_SERIAL_xxxxxxxx_yyyymmdd.dat` and says factory identity and newly generated service identity differ. ADJ p.36 / printed 6-35E gives `DSC-W300_ADJBAK_xxxxxxxx_yyyymmdd.dat`. Its language is narrower than “full camera backup.” A reproducible real workflow must obtain the original identity and adjustment backups separately and establish recovery coverage for the exact field(s) it changes.

SeusEX exposes distinct operations (ADJ p.30): **Set** changes working data without a nonvolatile write; **Write** writes EEPROM; **Set then Save** writes flash; **Read** explicitly refreshes values, because displayed data are otherwise stale. The manual does not give the destination's block/page/address. Generic access controls do not provide a W300 destination implementation.

The separate **WriteEnableTool.exe** in Level 2 section 1-5 temporarily permits PC writes to the camera's user-accessible internal image memory. Power-off resets that permission. Its source context is restoration of user data after board replacement. It is not evidence of a destination-write unlock, firmware-flash facility, or service-board flag conversion, and should not be substituted for the missing language operation.

## Error behavior material to a future procedure

ADJ pp.28-29 / printed 6-27 to 6-28 distinguishes communication errors from data-save errors. It warns that an interrupted adjustment can leave working adjustment values active, causing abnormal camera behavior. A red **Release Data Setting** button cancels such working settings; some flash-save failures require the exact page/address/data instructions supplied by that error dialog. This is not a justification for guessing corrective writes. Capture the full dialog before any recovery action. The procedure must avoid camera/video/LCD calibration routines entirely.

## Search result and the concrete missing evidence

Web queries covered exact W300 destination/service-board/SeusEX/Auto-Adj combinations, W300 language conversion, and English/Russian/Japanese variants. Results included the W300 Level 2 primary service content above, consumer support, neighbouring-model manuals, and unrelated commerce pages. No W300-specific retail-board destination encoding, reproducible conversion trace, or documented override was obtained in this bounded audit. Search absence is not proof that none exists.

The smallest technically justified next research object is the **exact W300 Auto-Adj executable and its payload**, plus its SeusEX API surface. Static analysis could identify the destination-read path, service-board eligibility check, destination-data bounds, and any checksums without touching the camera. That analysis must precede writing an adapter. If only the generic SeusEX tool becomes available, arbitrary address reads/writes still lack a W300 specification. If PMCA independently produces a real W300 backup through a qualified read path, its actual format and properties could provide an alternative, but this audit supplies no such qualification.

This report does not select a safe executable procedure for the original board and does not claim the user's completion criteria are met.
