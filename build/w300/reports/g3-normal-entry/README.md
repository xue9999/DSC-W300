# G3 native normal-entry evidence and compiled-script boundary

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

The retained G3 firmware contains a concrete alternative `NinCooperator` that selects a four-byte hash input. This resolves the narrow objection that only the `WorkerThreadManager::getProductId() == 1` branch had been linked to an actual object. It does **not** establish the complete normal-MSC-to-SENSER transition, successful PMCA authentication, or any W300 capability.

This is static inspection of the retained Sony DSC-G3 ELF/XSB artifacts. Every input is checked against its size and SHA256 in `evidence/artifact_manifest.json`. Addresses below are ELF virtual addresses in these G3 files, not W300 addresses. No firmware was loaded or executed and no USB operation was performed. Existing sources and evidence were not modified.

## Concrete product-zero object

`PExtSenser.so` provides an independent object and startup path:

1. Its ELF `.ctors` contains `0xD200`. This function calls initializer `0xCD54` with arguments `1, 0xFFFF`.
2. In the successful initialization branch, `0xCDF4` stores `Extension`'s vtable address plus 8 into the global instance at `0x1C688`. The pointer is obtained through GOT slot `0x1B4D4`, with `R_ARM_RELATIVE` to vtable `0x1C560`. This establishes the actual constructed object's dispatch table, rather than relying on an exported method name.
3. The object's virtual slot `+0x18` resolves through a relocation to `Senser::Extension::getProductId` at `0xBBB4`. Its body sets `r0 = 0` at `0xBBC0` and returns. The separate `WorkerThreadManager` returning 1 remains a different implementation.
4. `Extension::active_event_handler` at `0xB504`, on event value 1, saves the supplied I/O-operations pointer and passes this global object as the cooperator to `CoreModule::nin_start` at `0xB614`. It first requires the authentication thread slot to contain `-1`; the other path prints a diagnostic and aborts.
5. `CoreModule::nin_start` calls `CoreModule::open`, whose resolved filename is `libsencore.so` at `0x12D60`. It looks up the exact string `NinThread` at `0x12D70` and passes the cooperator as the new thread argument. The selected library and symbol are actual referenced data, not loose string matches.

The registration is also concrete up to the USB library boundary. `Senser::Ready` stores the status callback and, when `GetSenserMode() == 0`, calls `Extension::senif_init`. The latter passes type 1 and the callback table at `0x1C540`; both entries relocate to `active_event_handler`. Local `senif_init` chooses `ptbl_senif[1]`, whose `R_ARM_ABS32` references imported `usb_senif_pub`. In retained `libusb.so`, that published structure points to `usb_senif_init` at `0xDC60`, which stores the supplied callbacks at Senif structure offset `+0xC` and allocates its private state. This audit does not bridge the entire upstream USB/kernel event dispatcher to event value 1.

## Four-byte branch and PMCA comparison

In `libsencore.so`, `NinThread` calls the cooperator's virtual slot `+0x18` at `0x79B0`. Value 1 selects `xxstep2`; another value branches to the PLT entry for `xxstep` at `0x79E8`. The linked `Extension` therefore selects `xxstep`.

`xxstep` at `0x11B44` copies the 512-byte challenge payload from packet offset `+4` to a 1024-byte buffer and copies a selected 512-byte key after it. Crucially, its subsequent call is to `shimashima`, not `shimashima2`. `shimashima` at `0x11ABC` passes **length 4** to the hash-input function at `0x11698` (`mov r2, #4` at `0x11AF0`), finalizes at `0x11770`, and copies 20 digest bytes. The appended key lies outside those four input bytes.

This matches the input selection in pinned PMCA revision `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0`: `SonySenserAuthDevice.authenticate` uses `data[:4]` unless the driver's USB PID is `0x0336`. The exact `sony.py` file is pinned by SHA256 and the conditional is checked from its AST. It is a structural match of the selected input bytes and digest size. This report does not execute or independently prove all SHA compression rounds, supply a live authentication transcript, or show the PID present while `Extension` is active.

PMCA's overall `senserShellCommand` has two stages: it starts/authenticates through a normal `SonyMscExtCmdDevice`, waits for service enumeration, then starts/authenticates a `SonySenserDevice`. The earlier [descriptor report](../g3-usb-descriptor/README.md) tied G3's service DID 13 to descriptor `054C:0336`; its 512+512 comparison qualifies that second stage. The four-byte branch here closes a specific first-stage code question, while the full transition remains unproven.

## Where the bounded native trace stops

`Extension::onComplete` at `0xBAA4` clears its active flag and calls the supplied status callback with value 0. `xs_senser_ready` supplies a callback object built from its XS arguments. The native `StatusCallback::onSenserStatusCallback` posts via `FskThreadPostCallback`; its target at `0xB184` converts the status to an XS integer and reaches a helper that invokes `fxCallID` with the property name `call`. Consequently this native completion path returns control to an application-supplied script callback. It does not directly identify the script action, DID, or a completed re-enumeration.

`usbExt.so::xs_reqStart` takes its DID from the first XS argument via `fxToInteger`. In one branch it forwards that integer to USB API slot `+0xC`, the slot relevant to the service start path in the descriptor report. This wrapper does not supply a hard-coded DID 13. This audit has not connected the status callback to an actual `reqStart(13)` call.

The two selected complete XS11 containers, `senserModule.xsb` and `senserCmdTable.xsb`, contain the script-level names `Senser`, `Ready`, callback names, `usbObject` and `reqStart`. Their section boundaries and all symbol offsets are retained in [xsb-inventory.json](xsb-inventory.json). These names are useful locators, not proof of a caller/callee edge. The CODE payload has not been decoded. The exact source or a validated decoder/binding analysis would be needed to establish invocation order, callback target, and the integer supplied to `reqStart`. See [xsb-boundary.md](xsb-boundary.md).

The bounded `USBGMsc.so` inspection found its native extended-command registration wrapper, but did not link an MSC command value to this authentication path. The separately retained `/bin/sen` is also insufficient as an entry recipe: `PowerEventHandler::onPowerOn` calls `usb_mode_start` only when `GetSenserMode()` is already nonzero; mode zero returns immediately. Neither finding is a claim that such a path is absent elsewhere.

## Reproduction and retained checks

Run from the repository root with the prepared Python environment and Capstone under `build/w300/re-tools/site`:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\g3-normal-entry\reproduce.py'
```

This reads immutable artifacts and writes outputs only to this report directory. It calls the retained ELF inventory/decoders, the XSB container inspector, and `verify_entry.py`. The last script asserts constructor/vtable relocations, selected instruction words and branch targets, the dynamic filename/symbol, Senif registration pointers, hash input length, callback and wrapper boundaries, and the pinned PMCA conditional. Its output is [entry-evidence.json](entry-evidence.json), plus three selected native listings. Earlier symbol-size listings include clearly marked trailing literal pools; those data words are not treated as executed instructions.

Each constituent ran successfully. `verify_entry.py` printed `ok: true`, `G3_Extension_product_id: 0`, and `selected_hash_input_bytes: 4`; both full-transition and W300-compatibility results remain false. The aggregation wrapper is provided to replay the checks from the repository root; it was not run again during this analysis. An initial checker attempt selected PMCA's earlier keys ternary instead of the `data` assignment; restricting the AST selector to assignment target `data` corrected that analysis-script error, after which all assertions passed.

The subsequent [XS entry analysis](../g3-xs-entry/README.md) and [event trace](../g3-entry-events/README.md) develop the application/script lifecycle from these native findings. Continue from those results to qualify the corresponding W300 entry, authentication and exit sequence, then its language operation and recovery.
