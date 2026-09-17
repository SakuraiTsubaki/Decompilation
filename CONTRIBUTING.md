# Contributing

Contributions should make decompilation work reproducible, reviewable, reusable, and durably preserved.

## Before starting

- Decide whether the work is target-independent. Target-specific work belongs in its matching `PocketMonsters-*-Decompilation` or `PokemonLegends-*-Decompilation` repository.
- Define the question, expected outputs, and verification method.
- Record exact tools, versions, input identifiers, provenance, and commands.
- Keep original, modified, and rebuilt ROM binaries outside Git.
- Commit every storable non-ROM work product created or collected during the work.

## Required retained outputs

Retain analysis, research material, reports, documents, README files, scripts, source, tools, configuration, logs, manifests, checklists, comparison tables, CSV/JSON/YAML and other structured data, graphics, sprites, images, palettes, fonts, icons, tiles, converted data, patches, and verification material.

When work produces graphics, sprites, icons, fonts, palettes, or tiles, include actual PNG output that reviewers can inspect. Metadata-only graphics submissions are incomplete.

## Research and analysis

Use the templates in `research/template.md` and `analysis/template.md`. Keep observations separate from interpretations, label confidence, and commit the complete non-ROM evidence trail, including negative results.

## Tools

Document supported inputs, outputs, dependencies, deterministic behavior, error handling, and safety constraints. Commit tool source, fixtures, generated non-ROM examples, manifests, logs, and verification results.

## Changes

A pull request must explain scope, evidence, changes, retained artifacts, verification results, and remaining uncertainty.

Run:

```text
python scripts/check_repository.py .
python -m unittest discover -s tests -v
```
