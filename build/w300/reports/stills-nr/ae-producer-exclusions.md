# Bounded AE producer exclusions

The desired input is type `0x550`, command `0x17`, payload byte 0. Its adapter
updates the AE byte used to select normal versus alternate NR gates. The named
meaning of values `0x14/0x18` remains unresolved. All addresses below are file
offsets in the retained W300 `av.bin`; these are static findings, not camera tests.

The generic local producer `0x1FB50` and endpoint-`0x10` machinery are already
resolved in the [guide](../../../../docs/w300/STILLS_NR_DISABLE_GUIDE.md).
A bounded pass through three caller layers excludes these inspected branches:

| Branch | Discriminating evidence | Result |
|---|---|---|
| `0x97578 -> 0x4E46C -> 0x4E3CE -> 0x1FB50` | `0x97560/0x97562` construct `0x51 << 4`; `0x97570` passes it as type. | Type `0x510`, not the target. |
| `0x4C924 -> 0x1FBBE` | Wrapper forwards input type, packet and length, sets channel `0xB0` at `0x4C92C`. Examined callers explicitly construct `0x210/0x220`, e.g. `0xB4E24..0xB4E2E` and `0x12F148..0x12F152`. | These callers do not supply `0x550`. |
| `0x119A46 -> 0x1FBBE` | `0x119A50..0x119A58` forward input type/packet, length `0x14`, channel `0x30`. Examined immediate callers use other fixed types. | No target constructor found in the bounded caller set. |
| Apparent variable type at `0xB5AA0/0xB5ABC` | Saved `r6` is set at `0xB5A08/0xB5A0E` to `0xFF + 0x21`. | Type `0x120`. |
| Apparent variable type at `0x12FF62` | Saved `r4` is set at `0x12FF24/0x12FF26` to `5 << 10`. | Type `0x1400`. |
| Other `0x1FBBE` branches | `0x1FC2C/0x1FC64`: `0x415`; `0x1FE38`: `0x988`; `0xB444E`: `0xF200`; `0x139FC2`: `0xF360`. | Non-target types. |
| `0x96F92 -> 0x4E492` | Diagnostic string at `0x4E610` is `SendResponse!!! RID : %x`. | Response-labelled forwarding is not proof of the incoming AE producer. |

No direct Thumb BL, inspected nearby Thumb tail-branch or literal Thumb-function
pointer reference to `0x4E3A8` was found. That reference-search result does not
prove the function unreachable or close all indirect calls.

## Direct endpoint send pair

A separate finite pass checked `0xB43D6/0xB43E4`, which bypass `0x1FB50`.
Both send the same 0x28-byte envelope built by `0xB438E` to endpoint `0x10`:

- `0xB43A8/0xB43AA/0xB43AC` construct and store type `0xF200` at envelope+8.
- `0xB43B4` loads literal `0xF305` from `0xB44FC`; `0xB43B6` stores it at +0xE.
- `0xB43B8` stores payload word 0 at +0x10. It is 2 when original `r0` is zero,
  otherwise 0; this is not the target AE input.
- `0xB43D6` calls `0x2E74`, or `0xB43E4` calls `0x2E68`, according to the result
  of `0x3000`. The envelope type and command remain the same on both branches.

The receiver strips eight bytes, yielding type `0xF200`, command `0xF305`.
This pair is conclusively outside the requested `0x550/0x17` route; no caller
expansion is needed to establish that exclusion.

## Remaining direct-send inventory

A finite classification of the remaining selected direct Thumb-BL send sites
also found only fixed non-target types. Addresses are hexadecimal AV file offsets;
type and command are relative to the envelope pointer passed to the sender.

| Send site(s) | Envelope | Type / command | Type construction and command source |
|---|---|---|---|
| `111660 / 11166E` | `sp` | `F350 / 001B` | Type load/store `111632/111636`, literal `11176C`; command `11163C/11163E`. |
| `1128AE` | `sp+4` | `0320 / 8001` | Type `112876..11287C`; command load/store `11287E/112882`, literal `112A1C`. |
| `1131BA` | `sp` | `0320 / 8005` | Type `11317C..113182`; command `113184/113188`, literal `11327C`. |
| `112908` | `sp+4` | `0320 / 8006` | Type `1128D0..1128D6`; command `1128D8/1128DC`, literal `112A28`. |
| `113DB2` | `sp` | `0320 / 8003` | Type `113D74..113D7A`; command `113D7C/113D80`, literal `114080`. |
| `113E36` | `sp+4` | `0320 / 8008` | Type `113E02..113E06`; command `113E08/113E0C`, literal `114098`. |
| `1148E4 / 1148F2` | `sp` | `0220 / 001B` | Type `1148A6..1148AA`; command `1148B2/1148B4`. |
| `1149B8` | `sp+4` | `0220 / 001A` | Type `114980..114986`; command `11498E/114990`. |
| `11535C / 11536A` | `sp` | `F350 / 001B` | Type load/store `11532E/115332`, literal `1154E4`; command `115338/11533A`. |
| `1187BE / 1187CC` | `sp` | `0416 / FF05` | Type `118794/118798`, literal `11899C`; command `1187A2..1187A6` forms low halfword of `~0xFA`. |
| `11A48A` | `sp+10` | `F340 / 0000` | Type `11A45A/11A45E`, literal `11A504`; zero initialization `11A44A..11A458`. |
| `11A552` | `sp+14` | `F340 / 0000` | Type `11A522/11A526`, literal `11A68C`; zero initialization `11A512..11A520`. |
| `11A5AC` | `sp+14` | `F340 / 0000` | Type `11A57C/11A580`, literal `11A68C`; zero initialization `11A56C..11A57A`. |
| `11A604` | `sp+10` | `F340 / 0000` | Type `11A5D4/11A5D8`, literal `11A68C`; zero initialization `11A5C4..11A5D2`. |
| `11A67A` | `sp+10` | `F340 / 0000` | Type `11A64A/11A64E`, literal `11A68C`; zero initialization `11A63A..11A648`. |

For the five F340 constructors, later stores set envelope halfword +0xC and
payload from +0x10; they preserve the zero command at +0xE. Fixed type alone
already excludes the target. No caller expansion was needed for these sites.
This selected inventory is exhausted. It is not an exhaustive proof over ARM
callers, indirect calls or external ingress, and does not prove the target absent
from firmware. Do not reopen the listed sites without changed evidence.

## Reuse and next evidence

Do not repeat these unchanged generic-forwarding, response or fixed-type traces.
A further offline pass must name a different untested constructor or indirect
reference with a plausible target layout. These exclusions do not identify the
sender, prove a Linux origin, or establish a named shooting-mode mapping. The
prepared source acquisition remains the next practical step for service-route
qualification; mode attribution and hardware NR effects remain separate gaps.

One observed edge remains outside this endpoint-constructor inventory:
`0x9B190 -> 0x35CD8` at `0x9B196` forwards a type loaded through `[r5]`,
a packet pointer and length `0x14`. Its type/command eligibility has not been
qualified; no `0x550/0x17` or named AE meaning is established. This supports
one bounded check if mode attribution becomes consequential, not an open-ended
caller search. It does not resolve missing plugin, service-exit or runtime
backing evidence and must not delay the prepared acquisition.
