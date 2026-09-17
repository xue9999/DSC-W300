# T100 standalone transport reference

T100 packages its native service transport as `bin/bin/sen`, rather than G3's separate `libsencore.so`. The extraction-manifest-pinned executable is 141,345 bytes, SHA-256 `1b030a4bf459e6cabec773251bb4a02f85dd9a08c5e1a8faad25b89ac18f8d9b`.

Run `inspect_t100_transport.py` to verify the source pin and reproduce `t100-transport-native.txt`. It inspects ARM code as data and never executes the firmware.

| Mechanism | T100 virtual address | Finding |
|---|---|---|
| Packet header | C2F0–C2F8 | Receives 12 bytes; function at +4 (C550), sequence at +6 (C320), status at +B (C498). |
| Function dispatch | 1BB24 | 0040 dispatches to AdjustCheckFunc D1CC; FF01 to FileControl D210. |
| Block dispatch | D1CC, 1BB98 | Block high nibble selects index 3, HostCommunication F854. |
| Host command routing | F868–F888, F8D4–F8F4 | Explicit block 3F handling and command-prefix lookup. |
| Application IPC | F964–FAAC | Command 3F/0055 is absent from local tables; packet routes through queue keys 09010001/09010000 to the application. |
| File read | D25C, D28C, D4F4 | Command 2, padded filename length and name at packet +10. |
| Read status | D524–D530, D5A4–D5A8 | Missing/inaccessible returns 82; success returns 1 with total size. |
| Raw write hazard | D310–D318 | Command 1 opens with 1241, including truncation. |

The existing service-method report anchors T100 senserModule.xsb CODE 12406–12427 registration of ADJUST_CNTL/HOST/55 and argument decoding at 12128–12172. This supplies a continuous comparative route from native dispatch to the application registration.

This finding does not establish W300 equivalence, USB authentication, successful service entry, or persistence. A separate T100 transport profile would need its runtime path, complete transfer behavior and coherent component set; substituting the executable into a G3 profile would be invalid. The current app therefore retains its existing write qualification boundary.

The runtime path is confirmed by T100 rootfs.img /sbin/init: the NUL-terminated `/usr/bin/sen` literal begins at decompressed offset 0x2064. The rootfs input is 946,176 bytes, SHA-256 `89c26f514389f5a0a5956b645898595195b138ce1c477514c97f5ebe14444709`, pinned by extraction.json. The console captures this path as an optional implementation artifact; presence does not grant write eligibility.
