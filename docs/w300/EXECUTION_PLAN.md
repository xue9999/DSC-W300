# DSC-W300 execution plan — still-image noise reduction

## Objective and completion criteria

Work on stills NR, not menu language. Establish an actual, reversible bypass or
disablement of still-image noise filtering on the original DSC-W300 while
preserving identity, calibration and normal shooting. Byte edits, static analysis,
simulation and readback are separate milestones. Completion requires a qualified
camera operation and a measured image-processing result.

## Finding and selected route

The correct AV table starts at `0x16EAF4` with `(name_pointer, program_id)`
rows. Its names agree with SA. The earlier local v1 report's shifted labels and
supposed AV/SA mismatch were a parser error; they must not guide further work.

| Stage | ID | Normal / alternate Asys gate |
|---|---:|---|
| NR16_RAWNR | 3 | `0x2B01 / 0x32DD` |
| NR32_RAWNR | 4 | `0x3033 / 0x3143` |
| CNR conversion to GCC | 5 | `0x3034 / 0x3144` |
| CNR filter | 6 | `0x3035 / 0x3145` |
| CNR conversion to RGB | 7 | `0x3036 / 0x3146` |

The historical two-byte edit bypasses both CNR filtering and RGB conversion
while leaving RAWNR gates unchanged. Investigate native RAWNR/CNR gates with
conversion retained. RAW skip prevents promotion of an untouched output buffer;
CNR skip has no explicit buffer swap. DSP pixel effects remain unverified.

Use [STILLS_NR_DISABLE_GUIDE.md](STILLS_NR_DISABLE_GUIDE.md) for source anchors,
boundaries and camera verification. The
[standard-library verifier](../../tools/w300_nr_evidence.py) and
[retained evidence](../../build/w300/reports/stills-nr/evidence.json) reproduce
the corrected relationships from pinned W300 AV, SA and backup-library bytes.

## Ordered work

| Question | Next bounded action | Evidence needed to advance |
|---|---|---|
| Can native gates be addressed reversibly? | Use the existing backup tool with `--include-nr-implementation` on the receiving PC to acquire `libadj11.so`, `libusb.so` and matching baseline libraries. Inspect commands 1–3 and teardown callbacks. | Exact selected transport, response checks and scope of implicit persistence; unavailable reads are not absence proof. |
| Which RAM backing will the request modify? | The W300 constructor/AV initialization link is established: both use the same category-6 main/spare descriptor inputs. The expected logical size is `0x4000`; physical capacities remain runtime inputs. Confirm current selected copy and numeric descriptor bounds during device qualification; do not repeat the static identity proof. | Actual pointer/size inputs at `0x200FD898/9C` and `0x200FD8B0/B4`, or attributable runtime evidence of the same scope; compiled defaults and synthetic dumps are insufficient. |
| Does bypass preserve the image pipeline? | The bounded ARM dispatch/wrapper trace is closed: GCC/CNR/RGB receive the same base expression and submit SA programs without processing pixels. Resolve SA pixel semantics from attributable instruction evidence or a qualified controlled image experiment; do not repeat the host trace. | Supported input/output formats, preserved conversion and any residual filtering; no assumed SA ISA or runtime address invariance. |
| Which shooting modes use these gates? | Owner selectors are named: 6/T = StillRec, 7/S = MovieRec. The bounded request-wrapper pass and selected direct-send inventory are closed: the inspected constructors fix non-target types. Continue only with a different untested constructor or indirect reference that can supply type `0x550`, command `0x17`; packet byte +4 reaches the AE adapter as payload byte 0. Do not repeat the closed exclusions. | Mapping of named shooting settings to AE values `0x14/0x18` and actual mode coverage; the internal receive path alone does not prove an external dependency. |
| What is the smallest device experiment? | Qualify a one-gate, one-mode RAM probe and exact restoration before considering persistence. A photographic extension must preserve the active change through normal capture and retain a restoration route. | Verified identity, command route, shadow/bounds, original values, calibration backup, entry/exit and implicit-save behavior, and explicit rollback/recovery. |
| Does NR disappear? | Execute the qualified operation and compare repeated original before/after/restored photos. | Measured photographic result, normal shooting and preserved calibration/identity. |

CNR gates map to page/address `0x51/0x2235` and `0x51/0x2345`.
Operations 2/3 copy to RAM. Operation 4 flushes a whole category; operation 5
erases, not refreshes. The actual backup library always reports its shadow dirty,
but flush has other prerequisites and clears Asys byte `0xD0`.

W300 native fallback framing is established and transaction cleanup does not
flush. Module `libadj11.so` can precede fallback; a missing export in a loaded
module returns an error rather than falling back. Global service-exit callbacks remain
unresolved. Keep hardware writes disabled until those gaps and recovery close.

The camera stage uses the separate receiving PC. Completed static findings
remain valid, but further progress on the current critical routes needs the
specified W300 acquisition/runtime evidence or a concrete new attributable
source. Do not repeat closed traces. Named AE values are not a prerequisite
for acquisition: record the exact tested camera setting and numerical gate
state, without claiming coverage of untested modes. Language engineering and
generic source searches are outside the critical path.

## Execution rules

- Preserve immutable sources and historical reports; correct current conclusions
  when a verified consumer or call chain disproves an earlier interpretation.
- Use two bounded read-only reviewers for independent traces; the main agent
  owns synthesis, implementation and verification.
- Close a bounded attempt when its result is known. Reopen only with a changed
  source, hypothesis, method or access.
- Keep live NR mutations disabled until the bounded experiment is eligible:
  verify identity, command/plugin route, RAM shadow/bounds, entry/exit and
  implicit-save behavior, original values, calibration backup and explicit
  restoration/recovery. Define one tested mode and the smallest change that
  preserves the identified conversion stages. Assess unresolved pixel risks
  without requiring proof of NR removal before the experiment.
- Experiment eligibility does not establish an NR result. Pixel effects,
  residual filtering, normal shooting and observed restoration are outcomes
  required before an operational NR-off procedure can be certified.
- A read/change/read/restore probe restored before shooting yields no NR-off
  photograph. Establish how normal capture occurs with the RAM change active
  and how restoration remains available across that transition before expanding
  the probe into a photographic experiment.
  Keep each of those statuses separate from immediate readback.
  Raw FileControl is not an atomic dual-bank transaction; file readback is not
  a persistence barrier or image-quality measurement.
- Run `python tools/run_checks.py` and `python tools/check_fresh_checkout.py`
  for completed code changes, following [TEST_INFRA.md](../../TEST_INFRA.md).
- Finish useful independent work before a precise hardware handoff. Do not mark
  the goal complete on offline checks alone.
