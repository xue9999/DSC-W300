# G3 XS11 callback and service startup evidence

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

This report replaces the earlier symbol-cooccurrence boundary with instruction framing derived from the **actual retained G3 runtime** (`tinyhttp`). No newer Kinoma opcode table, firmware execution or general emulator is used. It closes selected script-to-native edges, not the entire live lifecycle and not W300 compatibility.

## Method and checks

`frame_xs.py` derives operand classes from the ARM branch table in `fxRemapIDs` at 0x94050. Fixed operands, nul-terminated strings, function metadata and counted ID pairs follow the corresponding native handlers. The ID remapper at 0x93FA8 reads big-endian IDs, preserves 0xFFFF and masks the other IDs with 0x7FFF. Unsupported extension-hook opcodes fail closed.

`reproduce_xs.py` validates input hashes against the preserved artifact manifest, full container lengths, all encountered operand boundaries, symbol bounds, final terminators, and alignment of every 0x28/0x29/0x2A relative branch in four selected scripts. All four CODE payloads frame completely. Large outputs retain only relevant ranges; full framing is still checked. This is structural validation, not proof that every function executes or that all opcode semantics have been reconstructed.

The independent `xs-review` analysis checks selected semantics against both `fxRunLoop` and its accelerator. In particular, 0x42 gets a property, 0x2E resolves and calls a method, 0x64 assigns a property, 0x7C calls `fxPutID`, 0x6C swaps stack slots and 0x89 pushes a signed byte integer. The read/assignment distinction matters: symbol names alone did not establish these operations.

## Actual callback route

Offsets below are CODE offsets, unless labeled native VA.

1. `dsc.xsb` 0x12B742–0x12B751 assigns the current target and `senserCallback` to `senserModule`, then calls its `initialize` at 0x12B75B.
2. `senserModule.xsb` 0x134–0x13F passes the module and `readyCallBack` to `Senser.Ready`. The previous native report connects that callback to authentication completion.
3. `readyCallBack` has its function metadata at 0x3E4 and property installation at 0x457. It compares its event with `Senser.status.ACTIVE` and `STOP`, selects `SENSER_ON`/`SENSER_OFF`, then invokes the registered callback's `call` at 0x451 with its stored target. It does **not** directly call `UsbExt.reqStart(13)`.
4. `dsc.senserCallback` at 0x12C3B1–0x12C41C compares its message to `senserModule.SENSER_ON` and calls `cancelUSBConnection(2)` at 0x12C3D6. The latter records the stop reason and routes cancellation according to the current connection state. `cancelUSBCompleted` contains an `enterSENSER()` call at 0x12AB01. The relevant conditional ranges are retained; this report does not claim every asynchronous cancellation completion is proven.
5. `enterSENSER` calls `finalizeUSB` at 0x12C38E and `senserModule.connect` at 0x12C398. In `senserModule`, `connect` calls `registerCallback`; that function loads `senserCmdTable.xsb`, registers command entries and calls `Senser.On` at 0x309.
6. Native `xs_senser_on` calls `Senser::On`. Its actual GOT pointer at 0x1B474 identifies `Extension::workerThread` at 0xBF3C. The worker calls `CoreModule::normal_mode_start` at 0xC3A4. The latter resolves the literal `senser_normal_mode_start`; it does not call the similarly named forced-USB wrapper.
7. `libsencore.so::senser_normal_mode_start` at 0x6638 passes port selection **1** to `SenserIfStart`. The latter opens the USB channel, registers its event handler and invokes `Usb::initialize_usb_interface`. That function calls `senif_init(1,...)` and `usbif_initialize`, invokes the USB API's first slot, and for selection 1 calls slot +0x34 and saves its result at USB object +0x14. The existing G3 descriptor report separately decodes the subsequent event-driven DID13 path.

The ordinary `dsc` function containing `UsbExt.reqStart` at 0x12CB4D chooses among AUTO, STORAGE, PICTBRIDGE and MTP. Its argument is a local variable. It is not evidence for a script call with literal DID13. This narrows the remaining work to the native normal-start lifecycle and event dispatch instead of pursuing the wrong script literal.

## Reproduce

From the repository root:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\g3-xs-entry\reproduce_xs.py'
```

The output `reproduction.json` records input hashes, complete framing sizes/counts and checked branch targets. `runtime.asm.txt`, `selected-handlers.asm.txt`, `worker.asm.txt` and `normal-start.asm.txt` preserve the native derivation. The script only reads firmware as bytes and writes local reports.

Still missing for W300: proprietary native/script equivalence, qualified normal entry/exit, actual language property and persistence operation, original-board eligibility and a recoverable backup. This report does not add a camera command to the workbench.
