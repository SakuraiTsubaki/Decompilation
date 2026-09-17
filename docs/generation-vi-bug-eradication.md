# Generation VI — Shared Bug / Glitch / Error Eradication Pipeline

Targets:

- `SakuraiTsubaki/PocketMonsters-X-Decompilation`
- `SakuraiTsubaki/PocketMonsters-Y-Decompilation`
- `SakuraiTsubaki/PocketMonsters-OmegaRuby-Decompilation`
- `SakuraiTsubaki/PocketMonsters-AlphaSapphire-Decompilation`

## Canonical policy

The objective is to eliminate reproducible unintended behavior across Generation VI without silently changing intended mechanics or erasing legitimate XY/ORAS and version-specific differences.

The ROM binary remains outside Git. All hashes, extracted metadata, manifests, analysis, source, scripts, patches, tests, logs, tables, graphics, and verification outputs that can be stored legally and safely are committed.

## Required target identity

Before binary patching, record for each target:

- title / product identifier
- cartridge or digital distribution form
- region and language
- base revision
- installed update version
- whole-input SHA-256
- NCSD/NCCH/ExeFS/RomFS and executable/module hashes where applicable
- extraction/tool versions

No address-level fix is portable merely because two targets share a game name or engine.

## Official-update baseline

- X/Y: preserve all cumulative behavior through official Ver. 1.5.
- Omega Ruby/Alpha Sapphire: preserve all cumulative behavior through official Ver. 1.4.

Always diff earlier versions against official fixes first. Known Nintendo/Game Freak fixes are evidence for both root cause and intended post-fix behavior.

## Shared analysis outputs

For every supplied target, generate deterministic non-ROM outputs:

- `identity.json`
- `container.json`
- `partitions.json`
- `exefs-files.csv`
- `romfs-files.csv`
- `modules.csv`
- `hashes.csv`
- `update-diff.json`
- `known-bugs.json`
- `reproduction-results.json`
- `regression-results.json`

## Public defect seed manifest

`manifests/generation-vi-known-defects.csv` is the current machine-readable discovery inventory. It contains 55 public defect seeds split across general/system, battle, and overworld families.

A row in this manifest is **not** equivalent to a confirmed ROM defect. Every row must be checked against the exact title, region, base revision, and update version. Community reports are discovery evidence; official Nintendo update notes are stronger evidence for defects Nintendo explicitly fixed.

The public inventory is intentionally only the starting surface. Static and dynamic ROM auditing must also discover defects that have never been publicly catalogued.

## Defect families to audit beyond public glitch lists

- bounds / index / enum validation
- integer wraparound and probability overflow
- stale flags, cache, UI, render, audio, and animation state
- event/script ordering and re-entry
- save/load atomicity and interrupted writes
- transaction rollback, duplication, disconnect, timeout, and retry behavior
- battle state-machine ordering
- form/species/type/ability/item edge cases
- malformed or impossible Pokémon records
- map collision vs rendered geometry mismatches
- resource lifetime / graphics cache invalidation
- text substitution / localization / case conversion tables
- cross-version and cross-language data assumptions
- update-version compatibility
- offline behavior after legacy online-service shutdown
- external integration input hardening (e.g. Bank-originated state)

## Fix acceptance gate

A fix is accepted only when all are true:

1. Trigger is reproducible on a precisely identified original target, or the defect is proven statically with equivalent certainty.
2. Root cause is localized to code/data/script/resource state.
3. Patch changes only the intended root cause.
4. Original expected behavior is documented.
5. Regression test covers the trigger plus neighboring valid cases.
6. No new crash, softlock, save incompatibility, battle-rule drift, event regression, or rendering/data corruption is introduced.
7. Patched artifacts and verification hashes are reproducible.

## Priority order

1. S0 — save corruption / data loss / unsafe invalid-state acceptance
2. S1 — crash / freeze / softlock / progression blocker
3. S2 — battle/state corruption / duplication / transaction failures
4. S3 — incorrect event/data/map/UI/audio/graphics behavior
5. S4 — cosmetic-only defects

## Public seed sources

Use official Nintendo update histories as primary evidence for officially fixed defects. Use community glitch catalogs only as discovery leads; reproduce and verify against the selected ROM/update before treating a report as confirmed.
