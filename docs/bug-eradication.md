# Exhaustive Bug Eradication Workflow

This document defines the common defect-removal policy used by target repositories.

## Goal

Remove every reproducible unintended defect from the reconstructed target while preserving the original intended game design and retaining historical evidence of defects that existed in released builds.

A defect is never removed from the historical record merely because a later official update fixed it.

## Scope

The audit covers, without exception:

- crashes, fatal errors, assertions, heap corruption, memory/resource leaks
- hangs, input locks, softlocks, progression blockers, unwinnable states
- save corruption, invalid persistence, stale flags, migration/version incompatibilities
- battle-calculation, targeting, turn-order, status, move, Ability, item and form logic errors
- raid/event scripting, reward tables, encounter data and event-distribution errors
- online/local communication desync, lobby errors, invalid state replication and timer errors
- spawn, despawn, collision, clipping, out-of-bounds and navigation errors
- map, quest, NPC, trigger, schedule, weather, time and progression-state errors
- graphics, model, texture, animation, camera, lighting, UI and HUD errors
- music, sound-effect, voice and playback-state errors
- text, localization, description, icon and metadata mismatches
- performance regressions, runaway allocation, pathological frame-time behavior and platform-specific faults
- DLC, update, event-data, Pokémon HOME and hardware-edition integration faults
- invalid/unreachable data, missing logic, overflow/underflow, truncation and boundary-condition defects
- duplication, cloning and other exploit paths caused by unintended state handling
- any additional reproducible behavior that contradicts verified intended behavior

## Preserve vs. fix

Each finding must be classified before modification:

1. `BUG` — unintended behavior; must be fixed.
2. `GLITCH` — unintended state/visual/system behavior; must be fixed.
3. `EXPLOIT` — player-usable consequence of unintended behavior; root cause must be fixed.
4. `DATA_ERROR` — invalid/missing/mismatched data; must be corrected.
5. `PERFORMANCE_DEFECT` — pathological performance/resource behavior; must be corrected.
6. `INTENDED_QUIRK` — verified intentional behavior; preserve and document.
7. `UNKNOWN` — insufficient evidence; do not silently change until reproduced or verified.

The project goal is zero known `BUG`, `GLITCH`, `EXPLOIT`, `DATA_ERROR`, or `PERFORMANCE_DEFECT` entries in a verified target build.

## Required target identity

No fix may be claimed against an unidentified ROM/game package. Before binary-derived conclusions, record:

- title and edition
- region/language where relevant
- base version
- update version
- DLC/version combination
- platform edition/hardware where behavior differs
- cryptographic hashes of the user-supplied local input and relevant extracted executable/data files

Original or modified complete ROM/package binaries must not be committed to GitHub. Hashes, manifests, extracted non-ROM work products, patches, scripts, tests, reports and verification outputs are retained.

## Registry states

Every finding progresses through these states:

`REPORTED -> REPRODUCTION_NEEDED -> REPRODUCED -> ROOT_CAUSED -> PATCHED -> REGRESSION_TESTED -> CLOSED`

Historical upstream fixes use `UPSTREAM_FIXED_VERIFY` until the target build and reconstructed implementation are both checked.

A finding is not `CLOSED` merely because an official patch note says it was fixed.

## Evidence required per finding

Record at minimum:

- stable bug ID
- title/category
- affected game/version/platform
- exact reproduction steps or automated reproducer
- expected behavior
- observed behavior
- save/event/network prerequisites
- source/evidence links
- relevant files/functions/data records once known
- root cause
- patch/change identifier
- regression test identifier
- verification build/hash

## Audit order

1. Identify exact target build(s).
2. Import official patch-note history so previously shipped defects remain in scope.
3. Import current public glitch/bug research as leads, never as unquestioned truth.
4. Run static data validation and structural checks against extracted game data.
5. Reproduce every known applicable finding on the target build.
6. Add newly discovered findings from fuzzing, boundary tests, long-session tests and differential comparison.
7. Root-cause and patch each confirmed defect.
8. Add a regression test before closing a finding.
9. Run full-suite verification across base game, updates, DLC, online/event data and supported hardware variants.
10. Re-run from a clean extraction/build to prove reproducibility.

## Mandatory test families

- clean boot / save creation / save load / migration
- story and quest progression state machines
- map transitions, collision and out-of-bounds sweeps
- encounter/spawn/despawn and form-state validation
- battle mechanics boundary values and long-battle counters
- raid/event state, timers, rewards and failure recovery
- inventory, crafting, shops, auctions and item-capacity boundaries
- Box/party/storage transformations and serialization
- HOME/import/export compatibility data
- local/online multiplayer state replication
- DLC installed/not installed and version-mismatch cases
- long-session memory/resource stability
- Switch and Switch 2 specific behavior where applicable
- UI/model/texture/audio reference checks

## Completion gate

A target is considered bug-eradicated only when:

- every registry entry is either `CLOSED` or explicitly proven `INTENDED_QUIRK`;
- no `UNKNOWN`, `REPRODUCTION_NEEDED`, or unverified upstream-fix entries remain;
- static validators report no unexplained structural/data errors;
- all regression tests pass on a clean reproducible build;
- version/platform/DLC matrices have been exercised;
- the final report lists target hashes and test evidence.

"Could not reproduce" is not equivalent to "fixed" unless the tested build, prerequisites, procedure and repeated verification are recorded.
