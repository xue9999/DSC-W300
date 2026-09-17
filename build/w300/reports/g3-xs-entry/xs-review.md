# Independent review of the retained G3 XS11 decoder

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

This review uses the actual ARM `tinyhttp` executable retained in the evidence manifest. It does not borrow opcode numbers from XS6, execute firmware, invoke USB, or qualify any DSC-W300 operation.

## Result

The bounded framing in `frame_xs.py` agrees with the executable's symbol-remapping walk for all instructions in `senserModule.xsb`, `senserCmdTable.xsb`, and `regionInfo.xsb`. An independent cursor walk in `xs-review.py` checked the resulting offsets, raw instruction bytes, file offsets and symbol index bounds. All 1,446 relative branch targets (opcodes 28, 29, 2A) land on decoded instruction boundaries or the code end. See `xs-review-results.json` for exact inputs and counts.

This validates instruction framing and the selected semantics below. It does not constitute a full XS interpreter, execution of the scripts, or proof that all application branches are reachable. The larger `dsc.xsb` output was outside this bounded independent review.

## Selected semantics from native handlers

The normal dispatch table starts at VA 0x907D0 for opcode 0x21. The accelerator table starts at 0x8EA84 with the same base opcode. `fxRunLoop` calls the accelerator before reading its next instruction. Accelerator fallback at 0x9076C saves the current instruction pointer and stack pointer, without consuming the unhandled instruction; the ordinary interpreter subsequently handles it.

| Opcode | Normal handler | Accelerator handler | Supported interpretation |
|---|---:|---:|---|
| 28 | 90CFC | 8F4F8 | Unconditional branch by signed big-endian 16-bit displacement relative to the next instruction. |
| 29 | 90D20 | 8F51C | Branch if the popped condition is false; same displacement base. Normal helper 93EE0 implements truth conversion and pops the condition. |
| 2A | 90D58 | 8F5A0 | Branch if the popped condition is true; same displacement base. |
| 2E | 91778 | 8F9A0 | Resolve named property of the top receiver and call it. Normal handler calls `fxGetProperty`, checks callability, constructs the call frame, and dispatches native or bytecode function. Accelerator has the matching receiver/property lookup and call-frame path. |
| 42 | 91E08 | 8FCF4 | Named property get. It replaces the receiver with the property's value. The ordinary path invokes an accessor when the property's flag 0x20 is set; the accelerator falls back for that case. A getter is therefore not intrinsically free of side effects. |
| 64 | 92570 | 8FEF0 | Named property assignment: resolve the receiver, then store the value below it. Normal path uses `fxPutProperty`; accelerator directly copies the value only for eligible ordinary properties, otherwise falls back. |
| 6A | 92B10 | fallback | Push NUL-terminated string literal; operand width is confirmed by the remapper's `FskStrLen` call at 942A8. |
| 6C | 913CC | 8F860 | Swap the complete two top 16-byte stack slots. No operands. |
| 7C | 934A0 | fallback | Call `fxPutID(machine, id, secondFlagByte, firstFlagByte)` after reading a big-endian 16-bit ID and two flag bytes. This is property installation with flags, not a hardware memory write. |
| 89 | 929AC | 900BC | Push signed 8-bit integer, explicitly sign-extended with ARM `ldrsb`. |

For the reviewed operations, accelerator success paths implement the same relevant stack, operand and control-flow behavior as normal handlers. Unsupported types or accessor/property conditions fall back to the ordinary interpreter. This statement is limited to the inspected handlers, not a proof of equivalence of the entire accelerator.

## Meaning of the `7C ... 10 10` constant-installation sequence

`fxPutID` at VA 0x703F4 takes the ordinary-property arm when flags & 0x60 equals zero. For flags 0x10, it reaches 0x70600, calls `fxPutProperty` at 0x7063C, pops the receiver at 0x70640–0x70648, writes the flags to property-slot byte +6 at 0x70668, and copies the remaining top value's type and payload into the property slot at 0x7066C–0x70688.

Consequently, a script sequence that pushes a string, calls a parse method, swaps the resulting value with its receiver, and executes `7C <ID> 10 10` installs the parse return value as the named property. The literal string's numeric interpretation still depends on the resolved parse implementation. This review establishes the call and property installation; it does not independently establish `__xs__number.parse` hexadecimal-conversion semantics.

## Framing limits

The remapper obtains opcode bytes at 0x9403C and selects handlers from 0x94050. Fixed-width operands, NUL strings, function-header symbol lists and paired symbol lists agree with `frame_xs.py`. The signed count bytes in the latter formats are restricted to nonnegative values by this decoder; the reviewed files satisfy that restriction. Symbol remapping preserves 0xFFFF and otherwise masks 0x8000 before looking up the original symbol table, matching 0x93FA8–0x94018. Framing unsupported/custom opcodes is deliberately rejected. Treat the output as a bounded static decoder, not a general validator for arbitrary XS11 files.

## Reproduction

From the repository root:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\g3-xs-entry\xs-review.py'
```

The command reproduces `xs-review-handlers.asm.txt` and `xs-review-results.json`. Firmware is read as data only. It verifies retained firmware hashes through the existing ELF helper and artifact manifest. `frame_xs.py` outputs for the three reviewed files must already exist.
