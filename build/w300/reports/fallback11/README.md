# G3 AdjustCommunication fallback for selector 0x11

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

## Result and limit

The fallback is a concrete **AV/interprocessor forwarding path** in the retained **DSC-G3** `libsencore.so`. It is not a recovered W300 Block/Page/Address implementation. The inspected routines copy selected packet/header fields into an internal 20-byte request, exchange that request through `/dev/ipcm`, and map a returned memory region through `/dev/kmem`. They do not disclose how the receiving processor interprets a SEUS block, page, or 16-bit address.

This does not prove that the path is unrelated to service register access; it locates the unresolved interpretation beyond the forwarding routine. The equal number `0x11` is not evidence that the W300 manual's Block 11 selects this path, nor that W300 runs these G3 routines. No W300 read or write primitive has been established.

## Reproduction and boundaries

Only `evidence/extracted_g3/archives_unpacked/lib/lib/libsencore.so` was read as bytes. Its recorded SHA-256 is `401bc78bc84bd175968513a387b8951626ceb48a345eed134b998d3630103270`. The isolated, previously installed Capstone 5.0.6 decoder was reused. No firmware code, downloaded script or device command was executed; no binary was imported or loaded as a native library. The original shared disassembler was not modified.

From the repository root:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\fallback11\inspect_fallback11.py'
```

Outputs are `fallback11.asm.txt` and `fallback11-evidence.json`. The script checks the source hash, the actual GOT relocation for the dispatch table, the chosen table-entry relocation, and all 137 PLT stub GOT targets against ELF relocation offsets before annotating external calls. Decoding was limited to three routines: wrapper `0xE894` (124 bytes), its direct target `0xE104` (1676 bytes through its last return), and the target's direct IPC helper `0xDD84` (360 bytes through its last return). Literal pools are not presented as executable instructions in those ranges. Addresses in this report are G3 ELF virtual addresses, never proposed W300 addresses.

## Verified dispatch and data movement

1. Existing `AdjustControlFunc` at `0xD878–0xD894` takes the high nibble of the first byte of its four-byte serialized header after plugin-command creation returns null. For a hypothetical local header byte `0x11`, the table index is 1.
2. Its position-independent base is `0x1B2D4`. The table pointer is obtained through GOT slot `0x1B5D4`, whose `R_ARM_GLOB_DAT` relocation names `AdjustCommunication`. That symbol is a 64-byte table at VA `0x1BA04` / file offset `0x13A04`.
3. Table entry 1 at VA `0x1BA08` has `R_ARM_RELATIVE` relocation and local target `0xE894`. This is a verified pointer resolution; reading the unrelocated GOT word alone yields zero and is insufficient.
4. Wrapper `0xE894–0xE90C` clears 20 bytes, sets internal request byte 0 to 1, then copies packet byte at `+0xB`, halfwords at `+6` and `+4`, packet word at `+0`, the header's first byte, and its halfword at `+2` into that request. These are observed local structure fields, not identified host-wire Block/Page/Address fields. It calls `0xE104` at `0xE904`.
5. `0xE104` opens `/dev/ipcm` at `0xE31C`, issues ioctl `0x400C4901` at `0xE340`, and calls helper `0xDD84` at `0xE3D4`. The primary embedded error text names `IPCMIOC_CONNECT` and `AV con result failed`. It subsequently opens `/dev/kmem` at `0xE47C`, maps a region at `0xE4A8`, and copies data at `0xE52C`. This is evidence of forwarding and shared-memory transport; the memory-mapping address is supplied from the IPC response, not a decoded W300 address.
6. `0xDD84` sends exactly 20 bytes via `DeviceIo::write` at `0xDDC4`, polls, then requires a 20-byte `DeviceIo::read` at `0xDE78`. It returns status `0x82` for a short transfer and `0x83` for the unsuccessful poll branch; these are observed G3 helper paths, not expected responses from a W300 host command.

Literal locations reproduced in the JSON include `/dev/ipcm` at `0x12B54`, `IPCMIOC_CONNECT Failed` at `0x12B60`, `TransactionStart` at `0x1298C`, the AV-result format string at `0x12B04`, and `/dev/kmem` at `0x12BA4`. Byte searches of this library found zero exact ASCII occurrences of `SEUS`, `Seus`, or `seus`; the prior symbol inventory supplied no matching exported SEUS handler. Use this bounded string/symbol inventory to target code paths and payload dispatch when searching for an unlabeled implementation.

## Exact missing evidence

The receiving AV firmware or its service-command dispatcher would be needed to interpret the forwarded request and payload. Following the Linux-side wrapper alone cannot provide the semantics of Block 11, Page 61, Address 0E10/0E11 in the W300 service manual. Even a complete G3 receiver would still need independent W300 qualification: matching W300 implementation or a W300-specific service transaction showing entry/authentication, serialization and response. The W300 destination/language mapping, persistence operation, backup/restore method and original-board eligibility remain separate unresolved requirements.

The bounded inspection stops here. It does not produce a device adapter, request payload, read command, or authorization to substitute G3 behavior for W300.
