# Bounded G3 dispatch decoding: consequence for W300

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

## Result

The newly located service routines were decoded statically to test whether they supply the missing SEUS addressing bridge. They do not establish a W300 Block/Page/Address request or language mapping. They do establish a concrete reason not to probe numbered commands with a zero-filled payload: **one inspected G3 `command0001` takes a write path when its selector byte is zero and a read path when it is one**.

This result concerns retained **G3** binaries. No firmware code was loaded or executed, no camera command was sent, and the portable workbench gained no service operation. All numerical code locations below are offsets/addresses within the hash-identified ELF files, not W300 camera addresses.

## Reproducible scope

- Inputs: `libsencore.so`, `libadj33.so`, `libadj36.so` under `evidence/extracted_g3/archives_unpacked/lib/lib/`. Their SHA-256 values are checked against `retained-service-inventory.json` before decoding.
- Decoder: Capstone 5.0.6, downloaded as the Windows x64 wheel and installed only into `build/w300/re-tools/site/`. The wheel is retained in `re-tools/wheels/`; `reports/capstone-install.json` records its hash. The workbench environment and transfer ZIP dependencies were not changed.
- Reproducer: `build/w300/reports/disassemble_service_dispatch.py`.
- Output: `build/w300/reports/retained-service-dispatch.asm.txt`.
- Selection: the ELF-symbol-sized `Parse`, `AdjustControlFunc`, `libadj33 command0001`, `libadj36 command0001`, plus the exact local helper called at `0xd7c0` immediately before `AdjustControlFunc`.
- Calls through the ARM procedure linkage table are annotated from the actual `.rel.plt`/`.dynsym`/`.dynstr` records. The helper verifies the table size against its 20-byte initial entry and 12-byte stubs, verifies `R_ARM_JUMP_SLOT` types, then decodes each stub and compares the calculated GOT address with that relocation's `r_offset`. All 137, 56 and 18 slots in the three respective libraries matched. It does not infer imported call names from nearby text or rely only on conventional relocation order.

Reproduce from the repository root:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\disassemble_service_dispatch.py'
```

References for the decoder: [official Capstone Python API](https://www.capstone-engine.org/lang_python.html), [pinned 5.0.6 package](https://pypi.org/project/capstone/5.0.6/).

ELF symbol extents can include literal pools after the return instruction. Apparent instructions decoded from such trailing constants are not treated as executable paths. The analysis below follows only the concrete instruction paths leading to calls and returns.

## Concrete findings

### Dispatch is present, but does not identify the old W300 tuple

`libsencore.so` `Parse` reads a halfword at the supplied in-memory packet pointer plus four (`0xcea4`) and compares it with a dispatch-table halfword. This establishes an in-memory dispatch selector. Qualify a raw USB frame or prove that W300 supplies the same packet structure through separate target-model evidence.

`AdjustControlFunc` obtains four bytes via `Serialize` (`0xd82c`). It uses the first byte (`0xd858`) to call a local helper. That helper forwards the byte, constant `0x40` and a module-name argument to `GetPluginModule` (`0xd7ec`). The dispatcher then reads a halfword at local header offset two (`0xd868`) and passes it to `CreatePluginCommand` (`0xd86c`). A failed plugin lookup falls back to a table indexed by the high nibble of the first byte (`0xd878`–`0xd894`).

The inspected path therefore distinguishes a plugin selector and a command selector. It does not identify the manual's Block, Page and Address fields, explain how that interface maps to these selectors, or provide the W300 destination operation. The second serialized header byte is not assigned a W300 meaning by this analysis. Conflating these bytes with the manual's fields would remain a hypothesis.

### A numbered handler contains both writes and reads

`libadj36.so` `command0001` first requires an argument length of ten (`0xcf4`–`0xd08`) and branches on the first payload byte (`0xd10`–`0xd24`).

| Selector and path | Actual calls | Scope |
|---|---|---|
| Byte zero | `Bkup_init`, then `Bkup_pwrite` at `0xd3c` and `0xd54`, then `Bkup_final` | Writes values from payload offsets one and six to two fixed backup identifiers; expected return sizes are five and four |
| Byte one | `Bkup_init`, then `Bkup_pread` at `0xd90` and `0xda8`, then `Bkup_final` | Reads the same fixed identifiers into output space; expected sizes are five and four; records output length nine on success |
| Other value or wrong length | Error path | No evidence that arbitrary fields represent a SEUS tuple |

The fixed identifier constants are loaded from the function's literal pool; this routine is not an arbitrary Block/Page/Address reader. The semantic names of these fixed backup records were not established, so they are not labelled serial, language or calibration data. No persistence or safe restore semantics are inferred merely from calls named `pwrite` or `final`.

The internals of `Bkup_init` and `Bkup_final` were not analysed here. Identifying calls to `pread` does not prove that the entire operation has no state changes. In particular, this result does not qualify even the read branch for execution on W300.

`libadj33.so` `command0001` requires a zero first byte and sends several calls through `Bkup_Sen_ctrl_exeCmd` with changing command arguments. It is not labelled a read-only operation by this analysis. Its generic numeric name cannot qualify a command for W300.

## Effect on the intended tool

This inspection establishes specific behavior in the retained routines from their instructions and control flow. It still supplies neither a W300 implementation nor a justified USB request for the documented W300 calibration anchors. The missing model-specific package, transaction or proprietary firmware layer remains necessary. No `command0001`, selector value, backup identifier, dispatch byte or inferred register tuple from this G3 analysis was inserted into `w300_workbench.py` or the handoff ZIP.
