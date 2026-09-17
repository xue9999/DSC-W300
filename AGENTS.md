# Research execution

## Outcome and ownership

Drive the requested outcome to completion. For W300 language work, the target is persistent English on the original Japanese camera, with identity, calibration and normal operation preserved. The analyst owns acquisition, analysis, implementation and verification within the authorized stage. Use the [current execution plan](docs/w300/EXECUTION_PLAN.md) to select work and [ANALYSIS_LOG.md](ANALYSIS_LOG.md) for reusable technical knowledge.

## Continue through obstacles

- Treat an unsuccessful route as evidence for selecting the next route. A missing artifact limits the operation that needs it; continue acquisition, offline analysis and useful tooling that can advance independently.
- For each material gap, state the affected operation, evidence needed, next action you will execute, expected result and alternative route. Execute the available next action rather than waiting for the artifact to appear or asking the user to repeat the request.
- Close a specific attempt when its result is established. Reopen it when the source, hypothesis, method or access changes. Repeating unchanged searches, checks or summaries is not progress.
- If one branch depends on hardware or external access, finish useful independent work and prepare a precise handoff for that dependency. End the whole task as externally blocked only after checking the remaining justified routes and explaining why none currently permits a useful action. State the smallest external input that would enable the next step.
- Choose bounded investigations with a concrete question and an observable result. Compare alternative sources and methods; Auto-Adj is one acquisition route, not the sole entry to W300 research.

## Evidence and operating boundaries

Keep source observations, static analysis, simulation and hardware results distinct. Preserve unsuccessful attempts, exact coverage, raw evidence and measured flags. A research hypothesis guides a test; it does not qualify a camera operation. Continue offline work on the preparation computer; camera writes belong to the separately authorized stage in the execution plan. Maintain identity checks, affected-data backup, recovery and persistence verification.

## Documentation and delivery

Write maintained documentation in English: finding, relevance to the goal, next action, verification. Give limitations their precise scope and a route to resolve them. Historical reports record their original result; the current execution plan governs continuation. Keep ANALYSIS_LOG.md compact and durable, without session chronology or copied diagnostics.

Before changing a file, inspect existing changes and applicable tools. Preserve unrelated work and source bytes. Use 2–4 subagents for independent, bounded, read-heavy reviews when they materially improve coverage; the main agent owns synthesis and verification. Run the checks in [TEST_INFRA.md](TEST_INFRA.md), update only explicitly intended manifest entries, and verify publication when requested. Report actual outcomes and any material remaining uncertainty.
