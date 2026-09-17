# W300 manual: external package locator audit

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

## Result

The supplied Sony W300 adjustment PDF contains **no actionable external program or payload locator** in its object graph. This check goes beyond text extraction and the earlier finding that there is no embedded executable. It does not change the next acquisition step: the exact Auto-Adj/SeusEX software or an independent W300 protocol implementation is still needed.

Source: `sources/sony_dsc-w300_adjustment_ver1.3.pdf`, 37 pages, SHA-256 `1cc830d94ac4cf4afad4db4b0634d8e922615118f2f570d604e950a2fbc45185`. The source was read only. Derived evidence: `build/w300/reports/w300-package-locators.json`.

## Object-level inspection

The bundled runtime's pypdf inspected **all 512 indirect objects** from the PDF cross-reference tables, recursively inspecting direct dictionaries, arrays and string values. It separately decoded non-image streams for filename/URL strings. No object parse errors occurred. The scan checked file specifications, file fields, remote navigation, embedded-file dictionaries, launch actions, URI actions and JavaScript. It did not execute PDF actions or scripts.

- There are **46 internal `/GoTo` actions** and no external `/GoToR`, `/GoToE`, `/Launch`, `/URI`, `/JavaScript`, `/SubmitForm` or `/ImportData` action.
- No `/Filespec`, `/FileSpec`, `/EmbeddedFiles`, `/EF`, `/JS` or external file field was found.
- The catalog's `/OpenAction` is internal navigation; no software-download action is hidden there.
- A numerical `/S` field in object 512 is part of a compressed structural stream, not an action. The derived JSON records it separately as `non_action_s_fields`.
- Decoded-stream URLs are XMP namespace identifiers and an IEC color-profile reference. They are not Sony software endpoints. Metadata identifies Sony Corporation, Adobe PageMaker/Distiller and document UUIDs; it contains no package source.
- Package-like strings in content streams are the documented **output backup filenames**: SERIAL, DpDyDT and ADJBAK data files. They are not input payloads. PDF text construction fragments the displayed executable name; the complete name remains independently confirmed by the extracted text and visual/manual review.

The first stream-string scan was stopped because a broad regular expression behaved poorly on binary stream data. It was replaced with bounded string matching and omission of image pixels; the full object-level dictionary inspection remained complete. Images can show labels but cannot themselves define PDF FileSpec, Launch, URI or JavaScript actions.

## Version and filename boundary

Revision history on PDF p.37 / printed final revision page supplies these documentary identifiers:

| Manual revision | Auto-Adj version | Reference | Documented change |
|---|---|---|---|
| 1.0, March 2008 | 1.0r01 | Original manual `9-852-287-51` | Initial release |
| 1.1, May 2008 | 1.1r02 | `A1 DI08-068`; replaces -51 | Thai model added |
| 1.2, June 2008 | 1.2r03 | `A2 DI08-113`; replaces -52 | Destination Data Write corrected |
| 1.3, August 2008 | 1.3r04 | `A3 DI08-225`; replaces -53 | Setting of Adjustment Mode corrected |

The final printed `985228754.pdf` is this manual's document filename. The DI08 identifiers are revision/service-document references, **not recovered executable URLs or package paths**. The PDF does not encode a downloadable location behind them. It supplies no alternate Auto-Adj archive name, DLL name, VBS/VBE payload, manifest or SeusEX version.

## Documented reads and their limits

No source instruction gives a block/page/address for firmware version, production-versus-service-board eligibility, destination data, or a language-enable field.

The PDF does document real W300 calibration addresses. In particular, p.24 / printed 6-23 instructs reading block `11`, page `61`, addresses `0E10` and `0E11`, naming them Dp and Dy. They are **angular-velocity sensor sensitivity calibration**, not board identity, firmware or destination. The text explicitly separates recording these existing values from later adjustment. This establishes the semantic meaning of those two W300 addresses; it does not supply the USB transaction or prove that A330's differently shaped page/offset request can read them.

Other address tables concern video levels (p.13), camera calibration (p.17) and LCD adjustment (p.26). Treating them as board eligibility or language flags would contradict their documented purpose.

The model-specific application's **Destination Check** and **Check Serial** are documented reads, while **Record Data** displays lifetime counters. Their underlying protocol and memory locations are undisclosed. A screenshot or displayed model/application version cannot be substituted for a camera firmware identity read. No reason was found to issue an experimental USB read or reuse another model's bytes.

All outputs from this bounded check are in `build/w300/reports/`. No additional manual was downloaded and no device operation was performed.

## Reproduce the object audit

The successful inline audit is retained as `build/w300/reports/pdf_locator_audit.py`. It consolidates the already performed separation of numerical `/S` fields from actual actions. The retained helper was not rerun merely to repeat the passed check. From the repository root, this invocation reads the original PDF and regenerates only the derived JSON report:

```powershell
& 'C:\Users\apara01\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'build/w300/reports/pdf_locator_audit.py' --source 'sources/sony_dsc-w300_adjustment_ver1.3.pdf' --output 'build/w300/reports/w300-package-locators.json'
```

The expected recorded result is 37 pages, 512 inspected indirect objects, 46 `/GoTo` actions, an empty external-reference list and no parse errors. The script does not execute PDF actions or open a USB device.
