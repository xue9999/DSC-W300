# Stills NR acquisition handoff

The local Windows x64 package contains the current acquisition command and its
portable USB runtime. It is an evidence-acquisition artifact, not an NR writer.
It has not been published or run against a physical camera.

Artifact relative to the repository root:

```text
build/w300/portable-region/stills-nr-acquisition-20260926-r2/W300-Stills-NR-Acquisition-Windows-x64.zip
```

Size: 12,174,133 bytes. SHA-256:
`e19ef7f440a7d0407266732b3b2f2374f34bc3fa7c88b99ebf37e48164e87c40`.
The adjacent `.zip.sha256` sidecar identifies the same archive. Its internal
manifest checks 105 files, including the executable, runtime, authentication
sources, licenses, source copy and acquisition launcher.

## Receiving-PC operation

Extract the entire ZIP into a new local directory and read its `README.md`.
With the existing W300 service USB setup and serial `D386002E4438`, run
`START_NR_CAPTURE.cmd`, or invoke:

```powershell
.\W300Region.exe backup-calibration --serial D386002E4438 --experimental-service --include-nr-implementation
```

No Python installation is required. The launcher requests configuration,
calibration and six exact library candidates, with repeated reads. It does not
request an NR parameter write or a backup-category flush. The general executable
contains other framework commands; this handoff concerns only the command above.

Preserve the whole new `sessions` directory entry, including failed results,
`result.json`, `manifest.json`, `transactions.jsonl` and `files`. Missing library
replies are not proof of installation absence. The
[NR guide](../../../../docs/w300/STILLS_NR_DISABLE_GUIDE.md) defines the evidence
needed before any parameter experiment.

## Verified scope and limitations

- The existing builder verified pinned authentication sources and passed its
  frozen selftest. The handoff adds acquisition-specific instructions and launcher
  in a new directory; earlier archives remain unchanged.
- Archive extraction and all 105 manifest hashes passed. The extracted executable
  passed selftest and mock acquisition in another path containing spaces and `ą`.
- Synthetic fixtures existed only in the validation copy. Five synthetic libraries
  were read twice, the sixth was reported unavailable, and every NR qualification
  flag remained false. The resulting synthetic dump passed `verify_dump.py`.
- Reusing the output directory was refused. Archive inspection confirmed that no
  validation fixtures, backups or test sessions entered the ZIP.
- The first candidate exposed a legacy-console encoding failure for a Unicode
  session path. The display-only fix preserves the actual filesystem path and
  uses escaped characters only when required by the output encoding. The existing
  CLI test now exercises CP1252 output and a real Unicode destination.
- An earlier attempt to run an extracted executable from Windows Temp returned
  `WinError 5: Access is denied`; the cause was not established. No security
  setting was changed. The successful relocation test used a new local build
  directory, so this report does not promise execution under every host policy.
- A standalone mock without complete fixtures correctly refused acquisition for
  missing `initreg.bin`. Complete synthetic fixtures were supplied for the positive
  packaging test; that result is not an original W300 backup.

The detailed local validation result is retained alongside the ZIP as
`acquisition-validation.json`. Hardware entry/exit behavior, actual library
availability, calibration preservation and NR effects remain unverified by this
package test. Source `region_app.py` SHA-256 at packaging:
`b6c9d1ae5bbc0a19ee12ce1f960c509038f3fb46350e42d1f95f25fb72a2e098`.
