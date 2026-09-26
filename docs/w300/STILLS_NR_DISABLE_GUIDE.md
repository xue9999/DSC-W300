# DSC-W300 still-image NR: evidence and qualification

The retained W300 firmware has separate gates for RAW noise reduction, chroma
noise reduction (CNR), and image-format conversion. Its native RAW skip path
preserves input-buffer selection. These findings support a parameter-based
bypass that retains conversion. They do not establish NR-free photographs or
qualify a camera write.

The historical two-byte experiment at Asys `0x3035/0x3036` skips CNR filtering
and the subsequent RGB conversion while leaving RAWNR gates unchanged. It is
not a validated full NR-off method. Live NR writes remain disabled.

## Software and supported evidence

Offline analysis and its tests use Python 3.10+ and the standard library only.
The verified inputs are the exact AV, SA and backup-library hashes below;
other firmware versions require renewed analysis. No firmware version currently
has a qualified operational NR-off procedure in this repository.

The existing camera acquisition framework separately requires PyUSB and
`libusb_package`, plus its retained authentication sources. Use the prepared
receiving-PC environment; the hardware acquisition backend is not standard-library
only. The [environment restoration reference](RELEASE_RESTORE.md) describes the
previously supplied offline runtime, but its historical release instructions do
not replace the current NR scripts or establish current NR qualification.

## Corrected program mapping

Source: `evidence/w300/av.bin`, 2,233,094 bytes, SHA-256
`bfa4df20f5d25daf82419c12ab7efb16ea39420c544a72a3d5037c71ac49bd30`.
The model string is at file `0x1EF548`. Unless marked VA, addresses below are
file offsets; AV code virtual addresses add `0x20100000`.

The name table starts at **`0x16EAF4`** with eight-byte rows in the order
**`name_pointer, program_id`**. Consumer `0x1A378` reads the name at row+0,
returns the ID from row+4 at `0x1A3A2`, and advances eight bytes. Caller
`0x1BB7C` obtains the table through literal `0x1BD00`; its result reaches
getter `0x44340` at `0x1BB8A`. There are 24 entries before the `NULL` sentinel.

| Program | ID | Wrapper | Normal Asys gate | Alternate Asys gate | SA header offset |
|---|---:|---:|---:|---:|---:|
| NR16_RAWNR | 3 | `0xAB34A` | `0x2B01` | `0x32DD` | `0x5438` |
| NR32_RAWNR | 4 | `0xAB370` | `0x3033` | `0x3143` | `0xA014` |
| NR32_CNR_2GCC | 5 | `0xAB396` | `0x3034` | `0x3144` | `0xFB70` |
| NR32_CNR_NR | 6 | `0xAB3BC` | `0x3035` | `0x3145` | `0x13A1C` |
| NR32_CNR_2RGB | 7 | `0xAB3E2` | `0x3036` | `0x3146` | `0x16F98` |

The earlier local v1 report started four bytes late and reversed the fields.
Its fisheye identification for ID 7, proposed ID 5 CNR target and supposed AV/SA
index mismatch were incorrect. Fisheye is ID 8. The corrected interpretation
follows the actual consumer, wrappers and SA headers.

`evidence/w300/sa.bin` is an `SA2U_APP` program container, not merely an audio
image. SHA-256:
`5126c376de296624280ccdc1c8692d98ec674cfaf69bfa8ef6dfa2e367010d44`.
Getter `0x44340` computes
`(base + uint32(base + 0x10 + 4*id) + 0xC) & 0x0FFFFFFF`.
IDs 3–7 yield `NR16_RAW0.07`, `NR32_RAW0.07`, `NR32_GCC0.11`,
`NR32_CNR0.07` and `NR32_RGB0.11`. ID 6 payload begins at `0x13A28`.
Static name/index agreement is verified; runtime container contents and DSP
pixel semantics have not been observed on the camera.

## Processing path and native bypass

Dispatcher `0x2C1D0` is registered for event `0x130` at table entry
`0x20CD38` in `tsk_camc_post`. Incoming stages 5–9 select IDs 3–7.
The old dispatcher claim `0x2CCA0` refers to formatting code; `0x2CD14` is
`add r0,sp,#4`, not a bypass branch.

Records at `0x1D0358`, `0x1D04B4`, `0x1D04D8`, `0x1D04FC` and
`0x1D0520` invoke these stages. Sequence key `0x10` points to `0x1D0448`;
selector `0x2A15E` installs its post pointer. Each record has six halfwords;
the buffer argument is the field at +4, not the full word containing it and flags.

Getter `0x2A8DC` selects alternate gates when `0x29726` returns `0x14` or
`0x18`. State byte VA `0x203706A7` is identified by diagnostic call
`0x30A08` and string `SET_AE_MODE_DSC` at `0x30D00`. Its user-visible
photographic modes remain unresolved. Camera post-processing reachability is
established; still-only scope and coverage of every shooting mode are not.

RAW parameter blocks have input at word +0 and output at word +4.
`0x6C9B6(3)` selects current buffer state VA `0x203315B4`; argument 4
selects pending state VA `0x203315B8`. Both RAW zero gates set bypass flag
VA `0x2032CCEC` at `0x2C2C2` and post completion through `0x2C4DE`.
Enabled paths clear the flag.

Subsequent event `0x12A` (handler `0x2BF9A`, RAW16) or `0x12B`
(handler `0x2BF3C`, RAW32) checks the flag and skips `0x6C93C(0)` when
bypassed. That helper otherwise promotes pending buffer to current. The native
gate therefore prevents selection of an untouched output buffer while retaining
other host-side descriptor and completion operations.

CNR/RGB descriptors VA `0xA03B2B60` and `0xA03B2BC0` receive the same
word-0 address expression:
`(selected_base + buffer_offset(3)) & 0x0FFFFFF8`.
Their sequence argument 5 does not change buffer state in `0x6C93C`.
CNR zero gate posts event 6 with payload `0xFFFFFFFE` through `0x2C4DE`,
without an explicit image copy or buffer swap in that handler. This removes one
host-side concern; it does not prove RGB accepts the resulting pixel content or
that nominal conversion programs contain no additional filtering.

The GCC stage shares that address expression too: its parameter block is VA
`0xA03B2B00` (getter `0xAB32C`), with image-base stores at `0x2C390/0x2C3A0`.
The corresponding CNR stores are `0x2C3FA/0x2C40C`, and RGB stores are
`0x2C466/0x2C476`. These branches and their direct submission wrappers only
assemble descriptors; they do not load/store image pixels or run a pixel loop.
The CNR skip is an omitted ID-6 submission followed by the existing completion
path, not a substitute image conversion. This is a bounded negative about those
ARM paths, not the entire firmware. SA programs may derive destinations or use
other engine state; neither in-place processing nor absence of filtering in
GCC/RGB follows from their shared parameter word 0.

Investigate native RAWNR and CNR gates while retaining both conversion stages.
This is a research target, not an instruction to write zeros to the camera.

Upstream selector `0x1382E` dispatches incoming event `0x1009` to `0x13948`,
which selects the NR sequences. Producer `0x36578` sends it through `0x363A4`
with a four-byte payload. This identifies a concrete next capture-API trace;
it does not yet map a user-visible mode. The separate debug `cap -- Still Capture`
command sends message type `0x510` with a `0x14`-byte payload starting with
`0x20000`, but its connection to event `0x1009` remains unproved.

The callback consumer narrows that path further: message dispatcher `0x99BAA`
maps event `0x73` to index 3 through table `0x1E2E90`. For record type 0 and
state 1, selector `0x99AD4` chooses matrix slot `0x1E3068`, invoking `0x99FB4`.
That callback calls `0x36578` and sends event `0x1009`. The record type/state
bytes are at +`0x18/+0x19` within records based at object+`0xA0+40*index`.
Their user-visible meaning is still unknown. Function `0x98BBC` records a
timestamp and numeric value; its argument `0x11` must not be called a state
transition without evidence.

The upstream object table at VA `0x203087AC` (file `0x2087AC`) contains
entry `0x98932` and method +`0xC` pointing to `0x99BAA`. Function `0x98932`
passes messages to `0x9847A`, directly or after queue retrieval. For event
`0x73`, its switch at `0x98514` selects `0x985FC`, then `0x98824` calls
method +`0xC`. This establishes dispatch of that numeric event; its original
sender and any user-visible mode remain unresolved.

The receiving task is attributable to `tsk_capcon_sequence`: its queue-read
error path at `0x14762..0x1476C` references source filename
`src\tsk\tsk_capcon_sequence.cpp` at `0x147B0`. Queue getter argument is
`0xC`; read `0x14752` receives an envelope whose first word selects a channel.
Dispatcher `0x37444` passes the remaining message to the registered object.
Initialization `0x37960` registers root member +`0x80` as channel 0; its
constructor installs the table containing `0x98932`. Thus channel 0 with inner
event `0x73` follows the proven NR route.

The sender is now established: `0x99212` maps selector 5 to event `0x73`
through its switch at `0x9922C/0x99246`. It calls `0x97CDA`, which writes
channel 0, event, handle and argument at envelope +0/+4/+8/+`0xC`, then sends
`0x28` bytes to queue `0xC` through `0x98DF2`. Queue lookup and send occur at
`0x98E04/0x98E10`. This matches the receiver above.

Selector 5 is registered by `0x37B08/0x37B0C` through `0x98E80`: object
root+`0x2514` retains it at byte +`0xC`, with underlying object root+`0x2268`.
Callers `0x98F44/0x98F9A/0x98FE2` read that byte and send the translated
event when the underlying method +8 returns a nonnegative result; a negative
result queues the handle instead. The diagnostic filename `ResourceMain.cpp`
at `0x99014` is directly referenced by this implementation. Thus the selector
belongs to resource registration, not an established user shooting-mode enum.
This identifies capture-sequence infrastructure; it does not exclude video.

## ARM-to-engine boundary

Runner `0xAB45C` calls `0x19E44`, forwarding to `0x19F92`. The latter submits
a four-byte-aligned SA program address to hardware register `0x79500008`,
three parameter words to `0x79500040/44/48`, and zero to `0x7950004C`.
It starts the engine through bit 0 of `0x79500004`. In synchronous mode it
reads status at `0x79500010` and results at `0x79500060/64/68`.
This bounded ARM path does not dereference the SA program contents.

The ID-6 wrapper explicitly initializes input word 0 with the low-28-bit address
of the dispatcher's parameter block. It does not explicitly initialize the
other two input words; do not label them pixel-buffer addresses. The previously
described current/pending image addresses reside inside the parameter blocks,
not directly in these generic engine-input registers.

SA table boundaries give payload sizes `0x4BD0`, `0x5B50`, `0x3EA0`, `0x3570`
and `0x6100` for IDs 3–7. RAW32/CNR share their first `0x40` payload bytes;
GCC/RGB share their first `0x34`. Structured triples inside the payloads suggest
segmented regions, but their code/data/address meaning and the execution ISA
remain unverified. Do not treat the entire member as a flat ARM instruction
stream. Follow parameter-block producers and engine behavior before attempting
algorithm patches or claiming that conversion contains no further filtering.

The CNR parameter-block getter `0xAB336` is called by initializers `0x77E84`
and `0x7BBC4`; reader `0xE236E` exports selected fields. The first initializer
packs 14-bit bank values from `0x3508..0x350E` into block+`0x28/+0x2C`, uses
selectors `0x2F6F4(0..5)` for +`0x30..+0x38`, and writes computed values from
`0x74C3C` starting at +`0x3C`. Those fields are not established image dimensions,
stride or filter strength. Fixed values `0x3FFE/0x3FFF` do not supply such labels.
`0xAB414` installs an execution callback; it is not the CNR-block initializer.
One supplied address does not by itself prove in-place pixel processing.

The selected image base has a separate provenance. Getter `0x35F94` reads
shared state VA `0x203729C0` at +8; getter `0x35F8E` reads +`0x10`.
Diagnostics in `0x35F9A` explicitly name these fields `RAW0` and `RAW1`
(strings `0x36258/0x36264`). The normal capture record receives the first
base through `0x13CEC..0x13CFE` and setter `0x2A47C`. Those names identify
firmware regions, not pixel packing, stride or an in-place filtering contract.

Function `0x35F9A` imports a caller's `0xA8`-byte descriptor; it does not
allocate the regions. Command `0x415`, subcommands 2/4, forwards body+`0x10`
to this importer. The inspected local builder `0x148E0` initializes only
words +0/+4 of its zero-initialized descriptor VA `0x203489D4`. It therefore
does not establish normal RAW0/RAW1 allocation.

The other local route reaches a concrete descriptor builder, `0xB3518`.
With `S = *(VA 0x20336784 + 8)`, it writes:

| Imported region | Base expression | Paired word |
|---|---|---|
| RAW0, descriptor +8 | `S.word38 \| 0x80000000` | `S.word3C` at +`0xC` |
| RAW1, descriptor +`0x10` | `S.word40 \| 0x80000000` | `S.word44` at +`0x14` |
| RAW2, descriptor +`0x18` | Same expression as RAW0 | Same paired word as RAW0 |

Stores `0xB3524..0xB353C` establish these relationships. RAW0 and RAW2 alias
in this builder. RAW1 uses a different source field; its runtime value need not
be distinct. These expressions still do not establish pixel layout or lengths.

Callers at `0xB364C`, `0xB3C02` and `0xB40D8` submit the built descriptor
through `0x203B4`. Message builder `0x20372` places it at message+`0xC`,
with command `0x415`, subcommand `0x200` and operation 1. Dispatchers
`0x202FC/0x1FF86` pass it through `0x1FD1A` and `0x4E6B4` to the importer.
A deferred path copies all `0xA8` descriptor bytes to VA `0x203495E0` before
queuing the message, preserving its lifetime.

Both initial source pointers are present in the firmware image. Scatter record
`0x20AE24` copies VA `0x2030B02C` to `0x2032B02C`, length `0x160B0`.
It maps state word `0x2033678C` to file `0x21678C`, containing `0x202E6400`.
Hence initial `S` is file `0x1E6400`; its +`0x38/+0x40` both contain
`0x24D4D200`, with paired values `0x00D3E000`.

The separate update constructor `0x1184D2`, submitting at `0x11867E`, uses
`T = *(VA 0x20340914 + 0xC)`. Its initial pointer comes from file `0x220920`
and equals `0x202FC324`, identifying table file `0x1FC324`. It maps T fields
+0/+8/+`0x10` to RAW0/RAW1/RAW2 and adds alias bit `0x80000000`.

| Descriptor family | Initial RAW0 base | Initial RAW1 base | Initial RAW2 base |
|---|---|---|---|
| `0xB3518` | `0xA4D4D200` | `0xA4D4D200` | `0xA4D4D200` |
| Update ending at `0x11867E` | `0xA1BEF700` | `0xA292D700` | `0xA366B700` |

All six associated words are initially `0x00D3E000`; the three update bases
are separated by that value. These are initial firmware tables, not observed
runtime addresses. A bounded reference scan did not find a direct replacement
of S's state pointer, but does not exclude indirect writes. Do not generalize
aliasing across the two families or equate region spacing with verified pixel
packing. The remaining issue is which family a shooting operation installs and
what GCC/CNR/RGB consume within the selected regions.

The two descriptor families belong to different state-handler implementations:
tables at file `0x207FA0` and `0x207FC0` contain corresponding entries
`0xB408A` and `0x1184D2`. Both read shared active byte VA `0x2033677C`
through `0xB32FA`, construct their descriptor when it is zero, then set it
through `0xB32F4`. This proves handler activation, not camera boot.

The S-based constructor also runs after a successful encoder-stop indication
(message halfword +6 = `0x8301`, word +8 = 0). The path to `0xB3646` directly
prints `ENC STOPPED`; error-recovery path `0xB3BF2` logs
`Error HANDLE! Switch Camera To MovieEE`. Preserve the proprietary `MovieEE`
label rather than assigning an unsupported user-visible mode. The T-based
handler explicitly accepts message `0x988`/subcommand 2 while active and
clears the shared active byte for `0x989`/subcommand 1. Therefore the maps are
installed through activation and transition handling, and the S map can be
reinstated during recovery. Buffer addresses alone cannot distinguish still
capture from preview or movie operation.

The owners are now concrete: the S handler is singleton VA `0x203B4788`
(object ID `0x0C`), and the T handler is singleton VA `0x2034092C`
(object ID `0x0D`). Constructors `0xB331E/0x116E50` install their tables.
Common selector `0xB2FE4` uses its incoming `r1`: switch value 7 chooses S
via `0xB3016`, while value 6 chooses T via `0xB300A`; both store the selected
owner at state+8. These mode-selection values are separate from resource
selector 5 in the event route above.

The T implementation contains a directly referenced smile-capture diagnostic:
`0x116EC6` uses the string `[SMILE CAPTURE] Smile Caputre Start!` at
`0x117088` (original spelling). This locates a smile-capture operation within
that implementation, without proving all T operations are still-only or naming
the entire owner `StillEE`.

The firmware debug menu supplies authoritative names for these owners:
strings `0x57868/0x57884` are `7)StillRec Mode` and `8)MovieRec Mode`
(spacing normalized here). At `0x57958` the selected menu number is reduced
by one, then `0x5795E` calls `0x119910`, which forwards the result to
`0xB2FE4` at `0x11991C`. Thus selector 6/T is **StillRec**, and selector 7/S
is **MovieRec**. These are firmware operation names, not a mapping of every
user-facing shooting setting.

The normal transition path accepts message `0x410`, subcommand 1. When the
current handler is inactive, `0xB3078/0xB307A` saves message byte +8 as the
pending selector. When handler processing returns 2, `0xB3106..0xB310C`
promotes that selector and installs the new owner. An active handler instead
reports an attempted mode transfer during command execution. This establishes
how the named descriptor owners are selected, without proving their relation
to each AE mode or the contents consumed by the SA programs.

The AE gate selector has a separate input route: command `0x17` in dispatcher
`0x299B2` sends its payload to bulk decoder `0x291BC` at `0x29B9A`.
Payload byte 0 is stored at VA `0x20370721`. Snapshot copier `0x290AC`
copies `0x7A` bytes from `0x203706FA` to `0x20370680`, placing that byte at
`0x203706A7`, where getter `0x29726` reads it. Wrapper `0x36684` receives
the command and payload through caller `0x998F0`. The named setting that
produces payload value `0x14` or `0x18` remains unresolved; neither StillRec
nor MovieRec selection alone supplies that mapping.

The upstream adapter is `0x99920`, referenced by callback pointer at file
`0x207C1C`. For message type `0x550` in halfword +`0x18`, it takes command
from halfword +`0x1C` and payload from message+8, then enters `0x9988E`.
For command `0x17`, that wrapper preserves payload byte 0 while inspecting
other fields before calling `0x36684`. Thus the unresolved named-setting input
is message+8 for type `0x550`/command `0x17`, rather than the already decoded
AE snapshot copy. The callback's transport consumer and sender must establish
source ownership before assuming an external artifact is required.

The callback is registered as channel 1 of the local queue-`0xC` dispatcher,
on root member +`0x50`. Envelope builder `0x35CD8` writes that channel and
copies its incoming type, command and payload into the adapter's layout.
For type `0x550`/command `0x17`, the reviewed compatible caller chain is
`0x11A732 -> 0x4E918 -> 0x35CD8`. Other inspected `0x4E918` call sites
handle commands 3/9 or values below 7 and do not supply this AE command.

Function `0xB2CBC` receives a message by value and passes it to `0x11A732`
at `0xB2D30`. Its direct adapter `0x4C000` copies a 32-byte input into those
arguments. Callers in `0x1F9F8` receive through `0x2E9C`, with endpoint
argument `0x10`, into VA `0x203493E0`, then dispatch the body at +8. This
narrows the next source question to the producer of that received message.
It does not yet identify a Linux sender or name AE values `0x14/0x18`.

The endpoint itself is local AV message-buffer machinery. Receive wrapper
`0x2E9C -> 0xAD80` and send wrappers `0x2E68/0x2E74/0x2E7E -> 0x28A0`
share tables VA `0x2034134C/0x20343734`. Sending either copies directly to a
waiting receiver (`0x297C..0x2988`) or uses the paired ring helpers
`0xBCF4/0xBD70`. The generic producer `0x1FB50` constructs a 0x28-byte
envelope: argument 2 becomes type at +8, packet halfwords +0/+2 become
fields +0xC/+0xE, and packet bytes +4..+0x13 become payload +0x10..+0x1F.
It sends to endpoint `0x10` through `0x2E7E` at `0x1FBA6`.

After stripping the first eight bytes, this gives the expected type,
command-at-+6 and payload-at-+8 layout. It does not itself choose `0x550/0x17`.
A bounded request-wrapper pass through `0x4E3A8/0x4E3CE/0x1FBBE` did not
identify the target producer. Examined concrete callers supplied other types.
The separate direct send pair `0xB43D6/0xB43E4` also uses fixed type `0xF200`
and command `0xF305`. These [producer exclusions](../../build/w300/reports/stills-nr/ae-producer-exclusions.md)
are closed; another pass must identify a different untested constructor or
indirect reference. The target packet byte +4 remains unattributed. The separate branch `0x96F92 -> 0x4E492` is
explicitly labelled `SendResponse!!!`; it is not proof of the desired incoming
AE producer. The generic IPCM error label does not establish a Linux origin.

The remaining selected direct-send inventory is also exhausted: each inspected
constructor fixes a type other than `0x550`. This closes those concrete sites,
not every indirect or external ingress. The exclusion report records the fields
and scope; another arbitrary caller expansion is not a demonstrated route.

## Native parameter route and persistence

W300 AV dispatcher `0x21E38` calls page handler `0x2220C`.
Runtime table VA `0x2032B9A0` contains row `0x20BD60`, mapping page
`0x51`, segment `0x22` to bank+`0x3000`, and row `0x20BD74`,
mapping segment `0x23` to bank+`0x3100`. Both lengths are `0x100`.
CNR gates map to page/address `0x51/0x2235` and `0x51/0x2345`.
Compiled defaults are 1; they are not this camera's original backup.

The same table also maps both RAWNR gates. Row `0x20BCFC` maps segment
`0x1D` to bank+`0x2B00` (default pointer `0x202E01E8`); row `0x20BD88`
maps segment `0x24` to bank+`0x3200` (default pointer `0x202E04F4`). Both
have page `0x51`, type 3 and length `0x100`. Their respective defaults resolve
to file `0x1E00E8` and `0x1E03F4`.

| Stage | Normal page/address | Alternate page/address | Investigational treatment |
|---|---|---|---|
| NR16_RAWNR | `0x51/0x1D01` | `0x51/0x24DD` | Candidate filter gate |
| NR32_RAWNR | `0x51/0x2233` | `0x51/0x2343` | Candidate filter gate |
| GCC conversion | `0x51/0x2234` | `0x51/0x2344` | Preserve exact original value |
| CNR filter | `0x51/0x2235` | `0x51/0x2345` | Candidate filter gate |
| RGB conversion | `0x51/0x2236` | `0x51/0x2346` | Preserve exact original value |

These ten addresses define a bounded future read survey, not an approved write
packet. Save actual values before choosing one active filter gate for a reversible
experiment. Never replace a conversion value with a compiled default or change
all six candidate filter bytes simply because they appear in this table.

These fields describe the **AV shared-memory body**, not a complete USB packet:

| Field | Body offset | Width |
|---|---:|---:|
| Operation | `+2` | 16 bits |
| Flush category | `+4` | 8 bits |
| Length | `+6` | 16 bits |
| Page | `+9` | 8 bits |
| Segmented address | `+0xA` | 16 bits |
| Write payload | `+0xC` | Length bytes |

Operation 1 reads. Operations 2/3 take the same RAM-copy path via `memcpy`
at `0x2231A`, then set a local notification flag. Helper `0x95D88` copies
notification fields to VA `0x20335F06`.

Operation 4 sends IPCM `0x1002`, subcommand 1 (flush). AV category 2 maps
to Linux Asys category 6. Operation 5 sends subcommand 3 (**erase**), not undo.
Linux supports subcommand 2 (refresh), but an AV adjustment opcode exposing it
has not been established.

Actual W300 `libBackupCore.so` is byte-identical to the library decoded in the
[backup report](../../build/w300/reports/av-page-init/linux-persistence/FINDINGS.md).
SHA-256:
`56aa2595c4747b6aadc1c0c3bb7a438b15086951121024a8649254cdec61fd4b`.
Both shadow-accessor vtables use constant-return dirty methods: `markDirty`
and `eraseDirty` return 0; `isDirty` at ELF VA `0x7AC4` returns 1.
The verifier checks the stubs and relocations. Explicit dirty marking is not
required for this implementation's flush.

Flush still validates arguments, obtains and locks the shadow and writes a
whole category. Category-6 flush also clears shadow byte `0xD0`. It is not a
one-byte persistence transaction. Linux refresh can read storage into shadow,
but that supplies no proven service reload command. Current shadow selection,
numeric runtime bounds, service-exit effects and interrupted-save recovery still
require qualification.

The [W300 shadow-link proof](../../build/w300/reports/stills-nr/asys-shadow-link.md)
now establishes backing identity. Actual `libBackupCore.so` constructor `0x6CCC`
loads physical descriptor pointer words `0x200FD898/0x200FD8B0` into its
category-6 main/spare arrays. AV initialization loads the same words, selects
main if its marker at +`0xE0` equals `0xAAAAAAAA`, otherwise selects spare,
and stores the aliased pointer at VA `0x2032B584`. Page `0x51` row initialization
then supplies that pointer plus `0x3000/0x3100` to segments `0x22/0x23`.
Both CNR gates therefore address the selected Asys shadow. Actual W300
`CategoryTable::getCategorySize` also specifies the expected category-6 logical
size as `0x4000` (16 KiB); this supports file consistency checks but does not
observe current physical descriptor capacity. Descriptor size inputs
are `0x200FD89C/0x200FD8B4`; their current numeric values are not in the retained
library. The spare selection branch does not prove a second marker check.

## W300 transport findings

Actual `libsencore.so` has SHA-256
`579cee5f0c9af3009a650ab4b4c907e58a0c62f8e4d075f8415213301686f9d4`.
Only bytes `0x13A1C–0x13A1D` differ from the retained G3 library: dispatch
entry 6 points to W300 `0xDD70` instead of G3 `0xDF10`. Entry 1 and the
reviewed framing, relocations and response code are identical.

`AdjustControlFunc` at ELF VA `0xD7F8` serializes a four-byte prefix and
tries plugin lookup using prefix byte 0 and operation at +2. If module loading
fails, prefix `0x11` selects table entry 1 (`0xE894`), then helper
`0xE104`, using IPC registration `(0,1,0x1001)`. The body consists of the
prefix plus subsequently received bytes; the 20-byte IPC structure is separate.
In W300 AV, `tsk_senser` starts at `0xE2B2`; category `0x40` routes
through `0xE3F6` to `0x21E38`.

The exact module candidate is `/usr/lib/libadj11.so`: helper `0xD7C0` uses
the full selector byte in `libadj%02X.so`, while only the later fallback uses
its high nibble. Factory `0xC018` looks up `command0001`, `command0002` or
`command0003`. A missing module permits fallback; a loaded module missing the
command instead returns an error object with status `0x80`. Optional plugin
`open`, `close` and `memory` exports can also affect the request lifecycle.
The retained W300 baseline contains only four libraries and does not establish
whether this plugin is installed. Acquire this exact file, or authoritative
evidence of its absence; do not infer absence from the partial capture.

The normal read/write path has not established meanings or required values for
body bytes +1, +4..+5 and +8. Keep them unresolved rather than inventing reserved
values for a hardware packet. For operation 4, +4 is the flush category.

Response handling copies AV status to outer byte `+0xB` and constructs data
from returned pointer/length. Page-handler success is 1, missing target is
`0x80`, bounds failure is `0x81`. IPC short transfer is `0x82`, failed
polling `0x83`; special status `0x88` must not be treated as ordinary
success. A future probe must check status, exact length and readback.

Transaction destructor `0xF434` sends pending IPC operation `0x10`.
W300 AV `0xE42E–0xE460` releases the transaction slot and acknowledges;
that bounded path contains no backup flush. Global service exit remains a
separate gap: USB teardown makes indirect external-interface calls at
`0x8848` and `0x88DC`, and calls `senif_destroy` at `0x88F8`.
Their downstream effects must be resolved before claiming a session is RAM-only.

The W300 ELF explicitly depends on `libusb.so`. Initialization calls imported
`usbif_initialize` at `0x8A14`, which supplies that callback object. Interface
index 1 selects imported `usb_senif_pub` through relocation at VA `0x1BB0C`;
local `senif_destroy` ultimately invokes its function at +4. Thus the next
specific artifact is W300 `/usr/lib/libusb.so`, absent from the partial baseline.
Comparative G3 callbacks reach USB stop/close, ioctls and asynchronous deletion;
they do not qualify W300 or exclude later application-driven persistence.

The prospective experiment is read → save exact original value → one-byte RAM
write → readback → restore original value → readback, without operations 4/5.
It remains a proposed procedure until entry/exit behavior and rollback are qualified.

Separate eligibility for that bounded transaction from proof of NR removal.
Eligibility requires verified identity, selected command/plugin route, exact RAM
shadow and bounds, entry/exit and implicit-save behavior, current original values,
calibration backup and an explicit restoration/recovery procedure. Use one known
mode and the smallest filter-gate change, retaining the identified conversion
stages. The present evidence does not yet satisfy these prerequisites, so live
NR writes remain disabled.

The transaction restored before shooting cannot produce an NR-off photograph.
A photographic experiment additionally needs a verified route to normal capture
while the RAM change remains active, with restoration still available afterward.
Assess the bounded processing risks before that trial; demonstrate actual pixel
effects, residual filtering, normal shooting and successful restoration as its
outcomes. Do not require proven NR removal as a prerequisite for testing NR
removal, and do not report transaction readback as a photographic result.

## Reproduce offline

From the repository root, Python 3.10 or later:

```powershell
python tools/w300_stills_nr.py analyze-av
python -m unittest discover -s tools -p test_w300_stills_nr.py
python -m unittest discover -s tools -p test_w300_nr_nvram.py
```

These commands use the standard library and retained sources; they do not
initialize USB. The [verifier](../../tools/w300_nr_evidence.py) checks source
hashes, table consumer, SA headers, gates, RAW completion protection, CNR host
buffer contract, AV body fields and backup dirty stubs.
[Retained evidence](../../build/w300/reports/stills-nr/evidence.json) uses schema
v2 and reports `live_write_qualified: false`, `nr_disable_verified: false`.
Transport findings above remain a separate static trace pending integration.

`w300_nr_nvram.py` retains the old two-byte edit for offline reproduction.
`OFFSET_RGB` denotes RGB conversion. Reports use `candidate_bytes_zero`,
never `nr_disabled`; dry-run current and planned states are separate.
Live patch/restore refuse even with `--experimental-service`. Simulated restore
rejects unrelated differences and incompatible banks before mutation, and never
replaces an existing backup directory. These checks do not establish flash
atomicity or persistence.

## Remaining qualification and camera result

The existing acquisition tool now supports `--include-nr-implementation`.
It reads configuration/calibration files and these exact library candidates:
`libsencore.so`, `libBackupCore.so`, `libBackupTable.so`, `libAppBackupApi.so`,
`libadj11.so` and `libusb.so`, all under `/usr/lib/`. Keeping the four previously
captured libraries in the same session permits comparison with the analyzed
version. No NR parameter change or flush is requested by this option.

Offline exercise, from the repository root:

```powershell
python tools/w300_calibration_dump.py --mock --experimental-service --include-nr-implementation
```

On the receiving PC, the [portable acquisition handoff](../../build/w300/reports/stills-nr/acquisition-package.md)
also packages the current executable and USB dependencies. It needs no Python
installation; use its acquisition launcher and retain the complete returned session.
The source-checkout equivalent is:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\tools\w300_calibration_dump.py' --serial D386002E4438 --experimental-service --include-nr-implementation
```

The second command enters the existing service session and reads the camera;
it has not been run on the preparation PC. This is source acquisition, not the
NR experiment. Use the current repository scripts; an older packaged executable
does not automatically contain this new option. The default output has a unique
`_nr_` timestamp suffix. An explicitly supplied `--output` must not exist.

Each acquired library is saved unchanged and read twice. A failed repeated read
aborts and preserves the differing bytes. Inspect `result.json` and
`manifest.json`: `nr_implementation.verified_paths` lists completed reads,
while `unavailable_or_inaccessible_paths` preserves unsuccessful candidates.
An unavailable reply never proves that `libadj11.so` is absent. Acquisition
success never sets `live_nr_write_qualified` or `nr_disable_verified` true.
The report separately records whether both Asys files were acquired twice.
Validate the returned directory with `python tools/verify_dump.py <capture_directory>`
and retain it unchanged. A successful file verifier proves capture integrity,
not NR efficacy or a safe write. If the hardware command reports a missing USB
module, use the prepared environment above; do not interpret that import error
as an unavailable camera or plugin. If either library cannot be read, retain
the exact acquisition result instead of substituting a library from another model.

1. Resolve `/usr/lib/libadj11.so` and acquire W300 `/usr/lib/libusb.so` to finish
   the specified service teardown callbacks, including downstream application effects.
   Confirm current shadow selection and bounds, then qualify a bounded reversible
   RAM operation using the established category-6 backing link.
2. Identify shooting-mode coverage and DSP input/output contracts for bypassing
   RAWNR/CNR while preserving conversion; identify any residual filtering.
3. On the receiving PC, preserve a current double-read configuration/calibration
   backup and identity before a qualified experiment. Keep original gate values;
   never substitute compiled defaults or a foreign dump.
4. Verify readback, normal shooting and restoration. Qualify persistence and
   interrupted-save recovery separately if required.
5. Retain original JPEGs from repeated before/after/restored captures with
   matching exposure, fixed ISO, focus, white balance and sharpening. Compare
   texture, chroma noise and edges. One sharper image does not prove NR removal;
   record tested modes and separate image results from byte readback.

No actual NR-off photo set, post-restart NR capture or complete original W300
Asys pair is retained in this checkout. That limits device qualification, not
independent offline work. If an earlier experiment was applied, preserve its
session and original Asys pair; compare those exact originals with current bytes
before choosing a restoration operation.
