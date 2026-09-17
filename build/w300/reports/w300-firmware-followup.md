# W300 firmware and transaction evidence: additional bounded acquisition

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

## Result

The additional sources and queries below produced references for further acquisition. Pursue a new DSC-W300 firmware/flash or service-transaction payload and establish its provenance, internal model identity and structure before implementation.

A useful false positive was resolved: an accepted answer to a W300 Japanese-menu question links to the **DSC-WX300** guide. Use the exact model in the linked primary guide to classify the result and pursue W300-specific evidence next.

All work was offline with respect to the camera. No device connection, login, purchase, correspondence, downloaded executable execution, driver installation, or camera write was performed. New acquisition records are confined to `build/w300/downloads/w300-firmware-followup/`.

## Prior coverage used to avoid repeating acquisition

Reviewed `build/w300/downloads/w300-firmware-candidates/ACQUISITION_REPORT.md`, `reports/auto-adj-acquisition.md`, `reports/w300-gpl-audit.md`, and `ANALYSIS_LOG.md`. Prior work already inspected native Elektrotanya search pages, native Remont-aud W300 searches, EletronicaBR's W300 schematic listing, all ten returned Archive.org W300 item inventories, current regional Sony download listings, exact GPL packages, and global GitHub issue results. Those materials were not downloaded again as new firmware candidates. Initial web reconnaissance did reproduce some of those known irrelevant listings; those repeats are not counted as new evidence.

## New specific sources followed to their actual content

| Source | Inspected content | Consequence |
| --- | --- | --- |
| [HelpOwl question 356526](https://www.helpowl.com/q/Sony/DSCW300/Troubleshooting/firmware-dscw300/356526), posted 2013-06-13 | The actual owner question asks where to obtain W300 firmware; the answers section is empty. Related manual excerpts are generated below it. | No owner dump, updater, transaction log or acquisition locator. |
| [HelpOwl question 160000](https://www.helpowl.com/q/Sony/DSCW300/Technical-Support/change-language-settings/160000), posted 2012-04-06 | Language-settings question; empty answers section. | No implementation or communication evidence. |
| [HelpOwl question 1066945](https://www.helpowl.com/q/Sony/DSCW300/Technical-Support/english-menu-japanese-model-dscw-300-change-english/1066945), posted 2021-06-15 | The page marks an answer accepted, but that answer offers general settings advice and one Sony guide URL. Following the URL identifies DSC-WX300. | Wrong-model reference; no W300 before/after observation or service trace. |
| [Sony guide actually linked by the accepted answer](https://helpguide.sony.net/gbmig/44559301/v1/eng/contents/07/02/03/03.html) | Downloaded HTML declares `Applicable model` = `DSC-WX300` at line 11 and includes DSC-WX300 in its title at line 13. | Direct primary-source verification of the mismatch; do not cite the accepted answer as W300 conversion success. |
| [DriverOwl W300 download listing 773](https://www.driverowl.com/p/Sony/DSC-W300/Driver/773) | Generic driver/firmware page says it points to the Sony site and requires a robot check to show that link. It does not identify a firmware filename/version, binary size, or owner dump. | Not an acquired payload. No check bypass or installer download attempted. |
| [VLab Sony service-manual thread, page 2](https://vlab.su/viewtopic.php?f=163&hilit=%2AW350%2A&start=30&t=333) | The W300 post by `swansic`, dated 2011-04-06, labels its attachment **Service Manual Sony DSC-W300 Level 3**. Attachment viewing requires an account and either participation or paid access. | A declared manual, not a claimed firmware dump; attachment bytes were not available for inspection. No login/purchase attempted. A separate investigation was obtaining the known public Level 3 manual to identify components. |
| [GSMHosting DBSS announcement](https://forum.gsmhosting.com/vbb/f360/dbss-v3-6-dreambox-firmware-v1-13-a-559384/) | The actual announcement's W300/full-flash support refers explicitly to Sony Ericsson DB2012 phones, alongside K310/K320/K510/Z530, and DCU-60 phone tooling. | Wrong product family. Its firmware capabilities are not Cyber-shot evidence. |

The regional search response and source-page text retrieved through the web tool are preserved in `regional-search-response.json` and `owner-reference-and-vlab-response.json`. The successful Sony HTML download is `sony-guide-wx300-not-w300.html`.

Direct PowerShell HTTP acquisition of the two selected HelpOwl pages and DriverOwl returned HTTP 403; those failures are recorded in `page-acquisition.json`. Their readable web-tool text was sufficient to evaluate the visible claims, but the failed requests did not produce local HTML or firmware. This is an access restriction, not evidence that a binary was examined or that no hidden attachment exists.

## Additional indexed scope

New targeted searches combined the exact `DSC-W300` name or `SY-199`/`SY199` board aliases with firmware, dump, EEPROM, ROM, BIN, Russian `дамп`/`прошивка`, Chinese `固件`, and trace terms `usbmon`, `pcap`, `USBsnoop`, and `gphoto`. Regional/developer-domain checks included `forum-monitor.net.ru`, `monitor.espec.ws`, `badcaps.net`, `repair-info.com`, `4pda.to`, `vlab.su`, `chinafix.com`, `repara-tu-mismo.webcindario.com`, and `forum.gsmhosting.com`. No W300 binary or trace candidate appeared in the returned results; the positive VLab and GSMHosting results were examined as above.

These are search-index observations, not an inspection of every site's archive. Existing normal USB descriptors are already retained in `evidence/w300/usb-transport-probe-20260916.json`; no generic descriptor utility was introduced or relabeled as a service trace.

## Follow-through from the acquired Level 3 manual

The separate investigation acquired the 34-page W300 Level 3 version 1.1 manual from [Manuallib's actual PDF](https://www.manuallib.com/download/pdf4/SONY-DSC-W300-MANUAL.PDF), retained at `build/w300/downloads/w300-l3-reference/sony-w300-l3-v1.1.pdf` and `.txt`. Its schematic identifies IC203 as `PRX765105A`. This is a source-qualified component designation; this check does **not** establish that PRX765105A is a separately accessible flash IC or establish its storage capacity.

New queries for `"PRX765105A"`, `"PRX765105" firmware dump`, `"PRX765105A" datasheet`, and `"PRX765105A" прошивка` returned an explicit empty result set. Follow-up family queries `"PRX765" Sony` and `"765105A" Sony` did not expose a component specification or payload. Results are retained in `prx765105a-search-response.json` and `prx-family-and-watermark-search-response.json`. This closes the exact-marking search attempted here; it is not a statement about unindexed repair archives.

The manual's extracted text also repeats a Chinese archive watermark directing readers to `http://bbs.520101.com` (for example lines 797–798 and 1309–1310). A targeted `"DSC-W300" site:520101.com` query returned no indexed W300 item. Opening the watermark URL through the web tool failed with a non-retryable URL-access error; a single direct public HTTP request then failed name resolution with `The requested name is valid, but no data of the requested type was found. (bbs.520101.com:80)`. These are access failures, not a native archive search or evidence that the archive lacks a dump. The web result is retained in `watermark-site-access-response.json`; the direct request result is retained in `watermark-site-direct-request.json`.

## Remaining concrete lead and qualification requirement

The source-linked regional archive is the historical `bbs.520101.com` forum. This check identified that lead without acquiring a binary. The subsequent [watermark archive audit](w300-watermark-archive/README.md) recovered its archived W300 manual listing and recorded the inspected thread/attachment coverage. Reuse that result, then seek a distinct binary-bearing thread or mirror instead of restarting from the failed live address. If no distinct source is found, continue the alternative routes in the [execution plan](../../../docs/w300/EXECUTION_PLAN.md).

Any future hit still needs its original uploader/model context and actual binary inspection: full length versus established storage capacity, spare/ECC layout if applicable, container/filesystem signatures and internal model evidence. A matching component alone does not make a dump W300-specific. A different unit's calibration/identity must never be written wholesale to the user's original camera. Continue from the recorded source coverage to a binary-bearing firmware or service-trace lead and verify its provenance.
