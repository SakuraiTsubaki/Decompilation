# Milestones: Decompilation common foundation

This roadmap governs target-independent research methods, schemas, tooling, validation, and retained non-ROM artifacts shared by the Decompilation repository family.

## Ground rules

- This common repository is completed ahead of dependent target rollouts for every shared capability.
- Milestones are evidence gates, not dates, percentages, or claims of total decompilation.
- Target identities and title-specific interpretations remain in their target repositories.
- Original, modified, and rebuilt ROM or complete game-package binaries are never committed.
- Every other storable work product is retained, including research, reports, source, scripts, tools, logs, manifests, structured data, patches, validation material, and generated outputs.
- Graphics and sprite pipelines always preserve viewable PNG results with their data and metadata.
- Normal diagnostics and safe error handling remain part of the tools; there is no separate bug-eradication track.

## Dependency chain

`C0 → C1 → C2 → C3 → C4 → C5 → C6`

A target repository may consume a common milestone only after the relevant common exit criteria are met by a passing commit.

## C0 — Governance, policy, and green baseline

**Goal:** make repository boundaries, evidence rules, artifact retention, and validation unambiguous.

**Required outputs**

- Versioned repository model, methodology, contribution guide, artifact policy, and templates.
- A machine-checkable policy that rejects ROM/game-package binaries, credentials, keys, and caches while preserving lawful non-ROM outputs.
- PNG-companion enforcement for graphics and sprite workflows.
- Passing repository checks and unit tests on a clean runner.
- A documented compatibility and deprecation policy for shared schemas and tools.

**Exit criteria**

- CI is green from a clean checkout.
- Policy tests cover allowed artifacts, prohibited binaries, visual companions, and malformed metadata.
- Target repositories can reference stable policy documents without copying ambiguous rules.

## C1 — Identity and provenance contracts

**Goal:** define one honest, extensible way to describe targets and authorized local inputs.

**Required outputs**

- Versioned schemas for target identity, release/region/revision/edition/update metadata, hashes, provenance, and multi-variant matrices.
- Validators, synthetic fixtures, examples for GBA, Nintendo DS, Nintendo 3DS, Nintendo Switch, and unclassified targets.
- Rules for unknown and unselected values that prevent invented identities.
- Command/environment/log manifests for reproducible runs.

**Exit criteria**

- Every target repository can validate its identity file without ROM bytes.
- Schema migrations are documented and tested.
- Unknown fields remain explicitly unknown instead of being inferred from names.

## C2 — Platform inventory adapters

**Goal:** provide reusable, deterministic structural inventories without embedding title-specific assumptions.

**Required outputs**

- GBA header, checksum, address, ARM/Thumb, pointer, and compression primitives.
- Nintendo DS header, ARM9/ARM7, overlay, FNT/FAT, filesystem, NARC, banner, and compression primitives.
- Nintendo 3DS container-metadata, ExHeader, ExeFS, RomFS, executable/module, and update-context adapters.
- Nintendo Switch edition/version, ExeFS, RomFS, NSO/module, relocation, update, and downloadable-content metadata adapters.
- Stable CSV/JSON schemas, synthetic fixtures, unit tests, and deterministic comparison reports.

**Exit criteria**

- Each adapter is proven by committed non-ROM fixtures and at least one target integration.
- Repeated runs produce byte-identical manifests.
- Unsupported structures fail explicitly and safely.

## C3 — Normalized code-analysis model

**Goal:** give all targets a common representation for executable regions and evidence-backed symbols.

**Required outputs**

- Schemas for sections, load addresses, functions, blocks, edges, relocations, references, symbols, compiler fingerprints, and confidence.
- Import/export adapters for supported analysis tools using open, documented intermediate forms.
- Address-space and variant-comparison rules.
- Small architecture-specific fixtures for ARM, Thumb, ARM11, and AArch64 where supported.
- Deterministic reports suitable for both humans and automation.

**Exit criteria**

- At least one bounded code slice per supported architecture round-trips through the normalized model.
- Every record retains provenance and source coordinates.
- Target adapters can extend the model without silently changing shared semantics.

## C4 — Normalized resource and visual pipelines

**Goal:** standardize how target repositories describe, convert, compare, and review non-code resources.

**Required outputs**

- Schemas and helpers for archives, text, scripts, maps, graphics, sprites, tiles, palettes, fonts, icons, models, textures, audio, and localization tables.
- Converter contracts with lossless round-trip or documented semantic-equivalence validation.
- PNG preview, sheet, and comparison generation with metadata linkage.
- Format-detection confidence and unresolved-field conventions.
- Fixture packs and cross-platform comparison tools.

**Exit criteria**

- Every supported visual workflow produces data, metadata, and an inspectable PNG.
- Converted assets retain hashes, coordinates, tool versions, and commands.
- Target repositories can reuse pipelines without moving target-specific assets into the common repository.

## C5 — Reconstruction and verification framework

**Goal:** support bounded source/data reconstruction with auditable equivalence checks.

**Required outputs**

- Source-to-evidence mapping and component manifest schemas.
- Reproducible build orchestration that accepts local protected inputs only when necessary.
- Byte, layout, decoded-data, control-flow, state, and behavior comparison helpers.
- Coverage and gap-report generators.
- Example end-to-end slices that do not distribute a complete game image.

**Exit criteria**

- A clean environment can reproduce every example and its validation report.
- Generated differences are classified and retained.
- The framework does not equate a passing narrow test with whole-title completion.

## C6 — Series integration and versioned releases

**Goal:** make common capabilities dependable across the full Decompilation series.

**Required outputs**

- A compatibility matrix linking shared tool/schema versions to every target repository.
- Automated target-consumer checks or fixture-based contract tests.
- Versioned releases with changelogs, migration notes, supported capabilities, known unknowns, and exact commits.
- Cross-target indexes for research, tools, schemas, and reusable findings.
- Long-term archival manifests for all retained non-ROM release artifacts.

**Exit criteria**

- Every active target can pin a compatible shared release.
- Breaking changes include tested migration guidance.
- Release statements report measured support and coverage without invented completeness.

## Status recording

Use `planned`, `in-progress`, `blocked`, or `evidence-complete`. Every status change must cite a commit, tests, commands, outputs, and remaining limitations. This file assigns no milestone completion status until those records exist.
