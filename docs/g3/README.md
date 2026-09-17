# DSC-G3: offline firmware analysis and experiments

## Inputs and supported conclusions

The retained `sources/DSCG3V2.exe` is the imported G3 updater. The [artifact manifest](../../evidence/artifact_manifest.json) records its integrity and provenance limits. A known hash identifies these bytes; it is not proof of a new download or manufacturer endorsement.

The parser carves an LHA payload, validates the MsFirm container and its section HMACs, and extracts CramFS, ext2 and TAR content. The [inventory](../../evidence/decrypted_inventory.json) is historical extraction metadata; current commands and tests reproduce the relevant byte-level results.

```sh
python tools/g3_firmware_parser.py --source sources/DSCG3V2.exe --output build/g3/extracted --all
```

Extraction stays in the specified output tree. The retained evidence is not a scratch directory. Genuine filesystem links describe the firmware's own filesystem; they are not host commands.

## Experimental generators

```sh
python tools/g3_text_poc.py --string "G3 POC" --out build/g3/D-G3V2_poc.dat
python tools/g3_stills_nr_patcher.py --out build/g3/D-G3V2_nonr.dat
```

The text experiment changes the `SETUP_VERSION` row in the English resource. Custom text is limited to 1–7 UTF-8 bytes and space-padded to preserve the original member length; control characters and commas are rejected. The AV experiment changes two two-byte instructions at known offsets in the known G3 image. The latter is an instruction patch experiment, not a verified noise-reduction disablement procedure.

Both generators require the pinned original input and verified section data. They stage the output, verify the allowed changes and unchanged content, then publish the result. Existing output requires `--overwrite`; preserved inputs and evidence cannot be used as generator output even with that flag. `--verify-only` checks an existing experiment against the trusted baseline.

Successful verification establishes offline integrity and change isolation. Use these results as the baseline for separate qualification of installation, boot, sensor behavior, image quality and recovery. Establish equivalent evidence for each additional camera model. HMAC verifies container integrity; assess manufacturer authorization separately.

The retained experimental images were regenerated during repository cleanup after the earlier images failed the stricter change-isolation checks. Their manifest records the input, generator command and current verification scope; superseded images remain in Git history. Tests generate new images in temporary directories rather than treating retained files as proof that the generators work.

## Network and emulation work

`g3_network_analyzer.py` parses supplied PCAP files offline. Its separate mock-gateway server is an active local network service; it is not started by the test suite. See `--help` before choosing a mode. QEMU profiles are configuration experiments described in the [emulation guide](../shared/EMULATION_AND_OPENMEMORIES_CI.md).
