# Comparative language-code acquisition targets

The immediate research target is proprietary W300 code or a qualified transaction, not a transplanted G3 setting. Sony's official [W150/W170](https://oss.sony.net/Products/Linux/DI/DSC-W150.html), [T300](https://oss.sony.net/Products/Linux/DI/DSC-T300.html) and [H50](https://oss.sony.net/Products/Linux/DI/DSC-H50.html) GPL pages link the same five package URLs as the [W300 page](https://oss.sony.net/Products/Linux/DI/DSC-W300.html). Reuse those downloaded GPL bytes rather than treating another model-page download as new implementation evidence. Shared GPL inputs do not establish equivalent proprietary code or language mappings.

`verify_g3_targets.py` preserves source-pinned comparison anchors in G3 `regionInfo.xsb` and `senserCmdTable.xsb`. It uses the existing XS instruction framer derived from the actual retained G3 runtime, checks branch boundaries, and validates selected opcode/symbol pairs. `g3-targets.json` contains the selected instructions. No code is executed and no camera is accessed.

The relevant region script calls `read` and builds region information as described in `../g3-config-read/`. The additionally selected save area has four `write` call sites at CODE offsets `0x631`, `0x63F`, `0x64D`, `0x65B`, followed by `flush` at `0x66C` and installation of `saveRegionInfoData` at `0x672`. Adjacent property loads reference the region, language, available-language and signal-type backup IDs and the host-regulation category. The command-table area references `makeRegionInfoFile`, `saveRegionInfoData`, `reset` and `initialize`.

These are useful targets when an actual W300 or close-model payload is acquired. They are not a full stack/data-flow analysis, an identified remote language command, or proof of W300 field values, original-board eligibility or persistence. The four writes also show why a region operation must not be assumed to change only the menu language.

Reproduce from the repository root:

```powershell
.\build\w300\venv\Scripts\python.exe -B build/w300/reports/comparative-language-acquisition/verify_g3_targets.py
```

The separate `../g3-file-read/` report establishes a possible route to acquiring proprietary libraries from the owner's camera later, after model-specific qualification. No such acquisition has occurred.
