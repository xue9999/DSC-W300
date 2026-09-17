# Model-specific qualification and reusable tooling

| Component | Evidence scope | Next qualification for reuse |
|---|---|---|
| G3 container parser | Retained updater and section integrity | Verify the target model input format and section checks. |
| G3 AV instruction experiment | Known AV binary and isolated changed bytes | Confirm equivalent W300 operations and measure photographic effects separately. |
| W300 service simulation | Assumed in-memory packet/state model | Derive physical addresses, original-board eligibility and persistence from W300 evidence. |
| W300 adjustment manual | Model-specific service documentation | Map its operations to exact application code or captured transactions. |
| QEMU profiles and synthetic factory data | Host-side assembly/configuration tests | Qualify machine model and boot sequence; keep synthetic fixtures within the emulator. |

Reuse byte-comparison, parsing and test utilities across models. Qualify firmware layouts, calibration structures, keys and service transactions against evidence for each target model; use generation labels such as BIONZ to guide research.

The [G3 guide](../g3/README.md) and [W300 guide](../w300/README.md) identify current findings and next steps. Native camera probes, a network server and a local emulator are distinct active operations, separated from default offline tests.
