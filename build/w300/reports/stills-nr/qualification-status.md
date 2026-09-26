# W300 stills NR qualification status

The requested outcome is not achieved. This audit follows the stills requirements
R1–R5 in [ORIGINAL_REQUEST.md](../../../../ORIGINAL_REQUEST.md) and the
[active execution plan](../../../../docs/w300/EXECUTION_PLAN.md).
Offline tests cannot substitute for the requested image-processing result.

Experiment eligibility, NR effect and observed restoration are separate states.
The eligibility gate concerns target identity, transport/plugin selection,
shadow/bounds, entry/exit and implicit-save behavior, original data, backups,
bounded processing risks and recovery. Pixel efficacy and successful normal
shooting/restoration are outcomes needed to certify an operational procedure;
they are not assumed or demanded as prior proof of the first eligible trial.
A transaction probe restored before capture does not supply a changed-state
photograph. A photographic extension must retain the change through normal
capture and preserve access to restoration.

| Requirement | Current evidence | What remains |
|---|---|---|
| R1: shortest practical method | Native RAWNR/CNR gates and AV read/write handler are identified. Actual W300 constructor and AV initialization prove category-6 Asys backing through shared main/spare descriptor inputs. RAM change with exact restoration is the preferred investigation. Raw dual-bank edits and unqualified SA patches are not operational alternatives. | Current numeric descriptor bounds/selection remain unobserved. W300 plugin selection and service-exit behavior need the actual missing libraries or trustworthy runtime evidence. |
| R2: genuine NR bypass | Hash-pinned AV/SA mapping, native zero-gate branches, RAW buffer-promotion protection, engine submission and CNR packed-parameter writers are established. | Mode attribution, pixel-format/side-effect contract and actual NR removal are unverified. Names and one shared address do not prove these properties. |
| R3: tooling | Standard-library verifier and specified offline test harness exist; code and immutable-source checks pass. Acquisition reuses the existing service framework. | Hardware acquisition requires its existing PyUSB/libusb environment. No standard-library-only operational camera NR writer is qualified. Historical file-byte experiments are not an approved application route. |
| R4: restoration/calibration | Acquisition preserves exact sources; simulated candidate restoration checks allowed differences and protects backups. The proposed RAM experiment restores the saved original value before exit. | No current original W300 Asys pair, qualified live inverse, interrupted-operation recovery or post-restoration shooting result is retained. Compiled defaults cannot replace originals. |
| R5: guide | The [guide](../../../../docs/w300/STILLS_NR_DISABLE_GUIDE.md) includes evidence, software, acquisition commands, interpretation, comparison protocol and limitations. | An operational NR application/restoration recipe cannot be certified before R1/R2/R4 close. The guide currently documents the verified investigational result. |

## External evidence needed

Use the prepared receiving-PC environment and the current acquisition script with
`--include-nr-implementation`. Preserve its result, manifest, trace and original
files. The request covers `/usr/lib/libadj11.so`, `/usr/lib/libusb.so`, four
matching baseline libraries and configuration/calibration files. A failed file
read does not prove installation absence. Existing locally retained W300 library
coverage contains only the four baseline libraries, not those two candidates.

The physical result additionally needs repeatable original before/after/restored
photographs and camera-operation checks. No such NR comparison set is retained.
There is no confirmed live receiving-PC process or camera session to poll here.

## Useful static limits

The ARM runner submits SA addresses to an MMIO engine; it does not establish SA
ISA or parse the candidate SA region triples. CNR packed-field writers identify
representation and provenance, not photographic parameter meanings. The event
chain `0x73 -> callback 0x99FB4 -> 0x1009 -> NR sequence selector` is verified
for numeric record type 0/state 1, without a named shooting-mode attribution.
These findings narrow the investigation and must not be promoted to hardware
qualification. Reopen closed traces when a new source, observation, hypothesis or specific
untested producer/consumer can distinguish the remaining hypotheses.

Descriptor constructor `0xB3518` explicitly maps RAW0 and RAW2 to the same
source field and RAW1 to another field. The initial-command path and deferred
descriptor copy are traced. This establishes region mapping for that constructor,
not distinct runtime allocations, pixel layout or applicability to the separate
update constructor. Both initial source tables are now resolved: the first
supplies one shared RAW base, the update supplies three distinct bases. This
does not establish runtime invariance or pixel packing. Event `0x73` is also
proven to reach the object method at +`0xC` through channel 0 of the task linked
to `tsk_capcon_sequence.cpp`. Sender `0x99212` translates resource selector 5
to this event and sends the matching queue envelope. That producer gap is closed;
resource registration does not identify a user shooting mode.

Common owner selector `0xB2FE4` values 6/7 choose the T/S handlers respectively.
The S constructor also runs after encoder stop and in MovieEE error recovery;
the T implementation includes a directly referenced smile-capture diagnostic.
The debug menu and its number-minus-one conversion name selector 6/T StillRec
and selector 7/S MovieRec. Normal message `0x410`/subcommand 1 provides the
pending selector. These findings identify owners without establishing every
pixel-processing path. The alternate AE byte has a different producer: command
`0x17` payload byte 0, delivered through `0x998F0/0x36684/0x299B2`, decoded
and copied into the active snapshot. Its values `0x14/0x18` still lack a verified
mapping to named photographic settings.

The native read-survey map now covers both RAWNR stages and CNR in normal and
alternate banks, plus the four conversion gates that must retain their original
values. This is address evidence, not a qualified request packet. The direct ARM
conversion branches and submission wrappers contain descriptor assembly rather
than pixel processing; the remaining image-format and residual-filter questions
concern SA semantics or controlled photographic results. Do not reopen that
unchanged bounded host trace as though a pixel loop were still missing from it.

The [backing proof](asys-shadow-link.md) closes static category identity,
pointer provenance, main/spare selection logic and row-relative CNR bounds.
Actual BackupCore also defines the expected category-6 logical size as `0x4000`;
this is not an observation of current physical descriptor capacities.
It does not supply current physical descriptor values or a qualified live write.
The AE receive endpoint also has verified local AV senders: `0x1FB50` builds
its envelope. A particular `0x550/0x17` producer and named AE values remain
unresolved; neither the endpoint nor the IPCM label proves an external origin.
