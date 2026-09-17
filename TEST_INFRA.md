# Offline verification contracts

Run `python tools/run_checks.py` from the repository. The runner audits immutable artifacts before and after unittest discovery and writes `build/test-results.json`. That report identifies the host, Python version, Git revision, working-tree changes, failures, errors and skips. A report is specific to that run. There is no permanent READY declaration or hard-coded test-count target.

## Required checks

- Known source bytes, section hashes, manifests and retained firmware link targets.
- Parser round trips, malformed/truncated input, archive path boundaries and independent container checks.
- Generation of new G3 experiments in temporary directories, exact allowed differences and refusal of untrusted inputs/output collisions.
- W300 simulations explicitly labelled, no camera access and no unsupported calibration or image-quality verdict.
- Platform-correct temporary-file use, honest optional dependency status and valid active documentation links.

Every required test must run. A missing retained input fails rather than turning a required integration check into a silent skip. Count changes are expected when false or redundant tests are replaced with useful contracts. Hardware effects and numerical image-quality improvements cannot be established by synthetic tests.

## CI and platform claims

The workflow targets Windows, Linux and macOS on Python 3.13, plus Linux on Python 3.10. Windows explicitly uses `core.autocrlf=true`. Optional submodules are not fetched for offline tests. CI stores the JSON report as an artifact.

A workflow file is a configuration, not a completed result. Only actual reports support claims about a platform. Hardware, local HTTP-server operation, native macOS compilation and a QEMU boot are outside these offline checks.

## Manual fresh-checkout validation

Check the final local tree in a separate temporary checkout with Windows line-ending conversion enabled. Run the audit and full suite there, retaining the report outside immutable evidence. This detects dependence on ignored files, untracked fixtures, platform-specific aliases and the original workspace path. Never use a destructive reset of the working repository to perform this check.

Run `python tools/check_fresh_checkout.py` to automate this check of current local changes. It uses an alternate index, does not stage or commit in the original repository, and retains its temporary checkout for inspection. The result is written to `build/fresh-checkout-results.json`.
