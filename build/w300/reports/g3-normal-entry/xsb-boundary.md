# G3 SENSER XSB entry boundary

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

The two requested XSB files were read only as static byte containers. Their size and SHA256 match `evidence/artifact_manifest.json`. The manifest preserves retained bytes; it does not certify camera behavior. No bytecode was executed or decompiled.

| File | Size | Container structure |
|---|---:|---|
| `senserModule.xsb` | 1681 | Top-level big-endian size 1681, magic `XS11`; `SYMB` at file `0x8`, size 466, exactly 48 zero-terminated names after its two-byte count; `CODE` at `0x1da`, size 1207, payload 1199 bytes. |
| `senserCmdTable.xsb` | 84575 | Top-level big-endian size 84575, magic `XS11`; `SYMB` at file `0x8`, size 16688, exactly 1342 names; `CODE` at `0x4138`, size 67879, payload 67871 bytes. |

Both section layouts end exactly at EOF. This check establishes that these containers fit their recorded lengths, not that their bytecode semantics have been recovered.

`senserModule.xsb` has symbol names `FORCE_USB`, `SENSER_ON`, `SENSER_OFF`, `readyCallBack`, `Senser`, `Ready`, `SMode`, `smode`, `registerCallback`, `initialize`, `disconnect`, `finalize`, `connect`, `unregisterCallback`, `extensionManager` and `loadBytecode`. Its CODE payload contains the exact contiguous bytes `senserCmdTable.xsb` at file offset `0x48b`; the preceding byte `0x6a` is not interpreted here as an opcode or a string prefix. The filename is a concrete locator for the second retained file, not proof of when it is loaded.

`senserCmdTable.xsb` contains symbol `reqStart` at file `0x120a`, zero-based symbol index 417, and `usbObject` at `0x1be8`, index 645. These are symbol-table names, not an established caller/callee edge. It also contains `Senser` and `Ready`. Neither inspected file contains the literal native names `xs_senser_on`, `xs_senser_ready`, `xs_senser_activeTrig`, or the symbol `activeTrig`. No adjacent USB XSB file was identified by the filename/symbol references in these two containers; the bounded audit did not search unrelated scripts.

The subsequent [XS framing analysis](../g3-xs-entry/README.md) and [event trace](../g3-entry-events/README.md) develop this inventory into decoded relationships and callback flow. Reuse those completed follow-ups, then qualify the corresponding W300 authentication and mode-transition sequence.

The bounded result is reproducible from the repository root:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\g3-normal-entry\xsb-inspect.py'
```

That command ran successfully. `xsb-inventory.json` records all symbol names and offsets, section boundaries, requested exact byte occurrences, hashes, and pin verification. All outputs are under `build/w300/reports/g3-normal-entry/xsb-*`; immutable sources and evidence were not changed.
