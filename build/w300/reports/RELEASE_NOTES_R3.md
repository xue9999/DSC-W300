# W300 research handoff — revision 3

The repository now presents completed analyses, concrete findings and the next model-specific qualification steps in English. Code, documentation, research reports and manifests are versioned at their existing paths. Prior source bytes, captured results, historical manifests, submodule pins and camera safeguards are preserved.

Two independently checksummed packages complete the handoff:

- **W300-Workbench-Windows-x64.zip**: portable identification workbench, private Python/libraries, Microsoft PowerShell 7.4.18, pinned source, licenses and revised instructions. Its 1318 manifest entries passed relocation checks; selftest and OS inventory both exited zero with external Python/Git/pwsh removed from PATH.
- **W300-Research-Offline-r3.zip**: 2894 files containing acquired materials, offline dependency wheels, Capstone, matching Python 3.12 x64, pinned PMCA Git history and the historical editorial baseline. The archive was restored into a fresh checkout and every file hash checked. Offline environment reconstruction and the actual workbench selftest passed; all 13 protocol-analysis jobs reproduced their outputs byte-for-byte.

Validation: 253 repository tests passed locally and in a fresh Windows-style checkout; five workbench tests passed; the integrity audit covers 821 preserved artifacts. A Windows-specific repeated-EXE-write issue was resolved by assembling tampered fixtures before writing them and retaining identical regular files during repeated archive extraction. Corruption checks and extraction boundaries remain active.

Start with `docs/w300/RELEASE_RESTORE.md` for complete reconstruction, or extract the workbench ZIP and run `W300Workbench.exe selftest`. The executable provides selftest, OS inventory and bounded standard INQUIRY. Continue the W300 language-operation, original-board eligibility and recovery qualification in `docs/w300/EXECUTION_PLAN.md`; hardware verification flags retain their recorded values and the camera write stage remains separately authorized.
