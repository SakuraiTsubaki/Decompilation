# Contributing

Contributions should make decompilation work more reproducible, reviewable, and reusable.

## Before starting

- Decide whether the work is target-independent. Target-specific work belongs in its matching `PocketMonsters-*-Decompilation` or `PokemonLegends-*-Decompilation` repository.
- Define the question, expected outputs, and verification method.
- Record the exact tools, versions, input identifiers, and legal provenance needed to reproduce the work.
- Never add restricted binaries, extracted proprietary content, credentials, or secrets.

## Research and analysis

Use the templates in `research/template.md` and `analysis/template.md`. Keep observations separate from interpretations and label conclusions as Confirmed, Probable, or Hypothesis. Include negative results when they materially narrow the search space.

## Tools

A tool must document its purpose, supported inputs, outputs, dependencies, deterministic behavior, error handling, and safety constraints. Add automated tests for stable logic and a small distributable fixture when possible. Avoid machine-specific paths and implicit network access.

## Changes

Keep commits and pull requests focused. Explain:

- the problem and scope;
- evidence and provenance;
- repository changes;
- verification commands and results;
- remaining uncertainty or follow-up work.

Run:

```text
python scripts/check_repository.py .
python -m unittest discover -s tests -v
```

before requesting review.
