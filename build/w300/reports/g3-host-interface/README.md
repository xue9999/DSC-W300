# G3 host interface: actual correspondence with current PMCA

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

## Result and decision

The retained G3 implementation contains the **12-byte Senser packet header and 516-byte authentication exchange used by the pinned modern PMCA source**. Its concrete worker selects the three 512-byte SHA1 key blocks that match PMCA byte-for-byte. Its hash finalizer also contains the length truncation reproduced by PMCA's `sha1_faulty` helper. The matching 1024-byte hash-input branch in PMCA is conditional on USB PID **`0x0336`**; other PIDs use only the first four challenge bytes. The subsequent [USB-descriptor analysis](../g3-usb-descriptor/README.md) resolves the selected G3 descriptor and PMCA PID branch; compare live enumeration with that static result during session qualification. This is substantially stronger than a similar function name or camera age, but the conditional branch must be retained in the qualification.

This corrects the research priority: the A330 legacy protocol is no longer the sole preferred lead. Modern Senser framing with a missing page/address helper is a concrete candidate to investigate for the W300 generation. Neither this G3 comparison nor a common SoC qualifies W300 service entry, authentication, the language property, persistence, original-board eligibility or recovery. No camera API was added to the workbench and no camera command was sent.

## Inputs and preservation

`inspect_host.py` checks four retained ELF inputs against `evidence/artifact_manifest.json`: `libsencore.so`, `libusb.so`, and the two `unified_drv*.ko` modules. They are read as bytes, never loaded or executed. The G3 source/container provenance limitations remain those in `evidence/g3_acquisition.md`.

`libsencore.so` SHA-256 is `401bc78bc84bd175968513a387b8951626ceb48a345eed134b998d3630103270`. The kernel modules declare ARMv5 vermagic `2.6.11-alp20080305 preempt ARMv5 gcc-3.4`. This is G3 module metadata, distinct from the ARMv6 examples in the public Sony/libmtp email. The wider USB symbol inventory identifies storage/extension functions but does not prove the mode-switch vendor request.

PMCA revision is `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0`. `compare_pmca.py` compares actual local `pmca/usb/sony.py`, `constants.py` and `crypto.py` bytes with their Git blobs at that exact revision before reading their constants. Constants are parsed with Python AST literal evaluation; the PMCA USB module and raw A330 scripts are not imported.

## Observed G3 authentication path

All addresses here are ELF addresses in the retained G3 library, not W300 camera addresses.

1. `WorkerThreadManager::start_authentication` resolves GOT slot `0x1B628` to `NinThread` (`0x7888`). The latter receives exactly `0x204` bytes at `0x7934–0x7938`, decodes commands, and branches on 1, 3 and 5. The paired helpers emit 2, 4 and 6. These are the same command stages and frame size used by `SonySenserAuthDevice`.
2. `CmdDecode` at `0x1137C` reads the command as big-endian, complements it, subtracts the low salt byte and retains the low result byte. `CmdEncode` at `0x111F8` stores the complemented command-plus-salt and salt as two big-endian halfwords. This is compatible with the normal command values and zero-salt requests in the pinned PMCA code; it is not a claim that the two decoders behave identically for arbitrary malformed frames.
3. The concrete manager vtable slot `0x1B6D0` resolves to `getProductId`, whose body at `0x80B4` returns 1. `NinThread` selects `xxstep2` when that virtual method returns 1; the alternate `xxstep` branch must not be substituted.
4. `xxstep2` copies the received 512-byte challenge and a selected 512-byte constant into a 1024-byte buffer. Its selected key literals resolve through the actual ELF section mapping to file offsets `0x13F11`, `0x13D11`, `0x13B11`. All three equal `senserKeysSha1[0..2]` from the pinned PMCA source. In `sony.py:925`, PMCA constructs this same input only if `driver.getId()[1] == 0x0336`; for other PIDs it hashes `data[:4]`. `compare_pmca.py` asserts the actual pinned AST condition and both expressions. The G3 worker's method named `getProductId` returning 1 must not be confused with a USB product descriptor. The alternate `xxstep` has a different first constant and a different hash-input length; an early exploratory comparison of that alternate branch was not treated as a protocol mismatch.
5. `shimashima2` at `0x11930` passes `0x400` input bytes to the local hash input routine and returns a 20-byte digest. The initialization constants are the five standard SHA1 initial words. At `0x11888/0x1188C`, the finalizer masks each bit-count word to its low byte before shifting it into the final block. For the observed 1024-byte input, the serialized length is zero instead of 8192 bits; PMCA's `sha1_faulty(message)` uses `len(message) & 0x1F`, which yields the same result. Bounded offline arithmetic checks cover additional lengths below the high-word boundary.

The SHA1 compression round function was not newly audited in full, no firmware hash routine was emulated, and no real camera challenge was collected. Therefore the result is byte-level/key/protocol-structure correspondence, not an executed G3 or W300 authentication session or proof of complete equivalence for every possible input.

Follow-up: [the separate USB descriptor audit](../g3-usb-descriptor/README.md) resolves the static G3 PID condition through the actual descriptor selection and its consumer. It also matches the start/stop request patterns. This qualifies the G3 configuration for PMCA's second, Senser-stage authentication; the first normal-mass-storage authentication uses a different input branch. No live enumeration or W300 session is established by either report.

## Header and page/address relationship

The input prefix of `SenserThread` calls `Serialize` with 12 bytes (`0x6F68–0x6F70`). It then reads the first word as length, bounds the fragment at `0x100000`, and reads sequence at offset 6. `Parse` consumes the function halfword at offset 4, as documented in the preceding retained-dispatch analysis. The code receives these bytes directly into an in-memory structure and uses little-endian ARM loads; the inspected prefix contains no byte-swapping stage. This corresponds to modern PMCA's size/pFunc/sequence layout, rather than A330's 16-byte big-endian legacy frame.

The already established G3 path routes pFunc `0x40` through the adjustment dispatcher and forwards the body to AV. The actual page8/address16 handler is documented in `../av-receiver/README.md`; the wire header and AV body are different layers. A match in framing does not make PMCA's modern BK2/BK4 property IDs the W300 language map. The pinned `SonySenserCamera` exposes modern property and flat-memory helpers, but no implementation of the W300 manual's independent Block/Page/Address tuple.

This result keeps **modern PMCA as a serious transport candidate**. It does not justify running `serviceshell` indiscriminately, assuming its terminal/backup operations are read-only, or sending an inferred page read to W300. The exact mode-entry request and complete session/exit behavior remain unqualified for W300.

## Reproduction and checks

From the repository root:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\g3-host-interface\inspect_host.py'
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\g3-host-interface\decode_host.py'
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\g3-host-interface\compare_pmca.py'
```

All three ran successfully. `decode_host.py` reuses the existing ELF/PLT decoder and verifies all 137 PLT-to-GOT relocation targets. Its 16 named/bounded ranges end before literal pools; the Senser input range is explicitly only a function prefix. `host-interface.asm.txt` preserves the instructions and resolved calls. `pmca-comparison.json` records source pins, actual key matches, the mandatory PMCA PID branch, vtable/GOT resolutions, asserted instruction words and limited padding arithmetic checks. `inventory.json` records all four inspected input hashes and the selected symbols/strings. An independent review verified the selected instruction paths and identified the PID condition; it is now explicitly represented in the report and reproduction.

No kernel build, driver installation, emulator, camera command, calibration access, language write, or claim of W300 support is part of these checks.
