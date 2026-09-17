# Evidence index

This directory preserves historical observations and reproducible offline firmware artifacts. Use dated records to understand completed work, then follow active guides for the next model-specific qualification.

- [Artifact manifest](artifact_manifest.json): current integrity contract, link targets and provenance/derivative roles.
- [W300 preflight review](w300/CEE8_PREFLIGHT_REVIEW_20260916.md): historical review of the earlier implementation, before the documented repair.
- [W300 procedure repair](w300/CEE8_PROCEDURE_REPAIR_20260916.md): historical host-side repair, followed by the current simulation-only implementation; use the active W300 preparation guide for the next hardware qualification.
- [USB investigation](usb-investigation.md): historical observations and limits; not a request to rerun active probes.
- [Acquisition notes](acquisition.md): historical W300 searches and supplied sources.
- [G3 provenance](g3_acquisition.md): retained input and limits of acquisition attribution.
- [G3 inventory](decrypted_inventory.json): imported extraction metadata. Byte counts, hashes and extracted strings can be checked against the retained data; architecture labels are research interpretations, not hardware measurements.
- [G3 architecture summary](DECRYPTED_ARCHITECTURE.md): bounded interpretation of the retained extraction.

Raw JSON/TXT captures and source documents are preserved byte-for-byte where recorded. Their timestamps, serial identifiers, historical paths and unsupported claims are source content, not current instructions. Superseded operational guides and generated success narratives have been removed from the active tree, with history retained in Git.

## From historical evidence to the next action

Use the [current W300 execution plan](../docs/w300/EXECUTION_PLAN.md) as operating guidance. Historical statements such as an unavailable package, an untested driver or a completed review describe their dated scope. The analyst owns the next acquisition or qualification task: develop another source, derive a specific comparison from retained firmware, or prepare bounded file acquisition. Preserve original observations while recording new results separately.
