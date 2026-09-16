# Decompilation

Research and reconstruction of compiled software into readable, buildable source code through decompilation, analysis, documentation, tooling, testing, and verification.

## Purpose

This repository provides a reusable workspace for systematic decompilation work. The workflow is organized around analysis, reconstruction, tooling, testing, and verification.

## Repository Structure

```text
Decompilation/
├─ README.md
├─ LICENSE
├─ .gitignore
├─ .gitattributes
├─ src/
│  ├─ code/
│  ├─ asm/
│  ├─ include/
│  └─ data/
├─ assets/
│  ├─ graphics/
│  ├─ audio/
│  ├─ text/
│  ├─ maps/
│  └─ metadata/
├─ analysis/
│  ├─ binaries/
│  ├─ functions/
│  ├─ symbols/
│  ├─ structures/
│  ├─ formats/
│  └─ comparisons/
├─ tools/
│  ├─ extraction/
│  ├─ conversion/
│  ├─ analysis/
│  ├─ build/
│  └─ verification/
├─ config/
│  ├─ symbols/
│  ├─ mappings/
│  └─ build/
├─ docs/
│  ├─ architecture/
│  ├─ decompilation/
│  ├─ formats/
│  ├─ progress/
│  └─ references/
├─ tests/
│  ├─ unit/
│  ├─ regression/
│  └─ comparison/
├─ scripts/
│  ├─ setup/
│  ├─ build/
│  └─ verify/
└─ .github/
   └─ workflows/
```

## Directory Roles

- `src/code/`: reconstructed C/C++ and other high-level source code.
- `src/asm/`: assembly that has not yet been reconstructed into higher-level source.
- `src/include/`: headers, types, structures, constants, and declarations.
- `src/data/`: data definitions directly tied to reconstructed code.
- `assets/`: graphics, audio, text, maps, and reusable asset metadata.
- `analysis/`: binary structures, functions, symbols, structures, formats, and comparison research.
- `tools/`: extraction, conversion, analysis, build, and verification utilities.
- `config/`: symbols, mappings, and build configuration.
- `docs/`: architecture, decompilation methodology, formats, progress, and references.
- `tests/`: unit, regression, and comparison tests.
- `scripts/`: setup, build, and verification entry points.
- `.github/workflows/`: CI and automated validation workflows.

## Workflow

1. Collect and document publicly available reference material.
2. Analyze binary structures, functions, symbols, formats, and data relationships.
3. Reconstruct source code and supporting data incrementally.
4. Build reusable tools and scripts for repeatable processing.
5. Test reconstructed components and compare behavior or outputs against documented references.
6. Record verification results and progress alongside the corresponding work.

## Repository Policy

Publicly distributable source code, analysis, documentation, manifests, metadata, scripts, tools, tests, and generated non-ROM artifacts may be tracked here. Original, modified, or rebuilt ROM binaries are not stored in this repository.

Empty working directories are retained with `.gitkeep` until real files replace them.

## Status

Initial repository structure established. Decompilation targets, tooling, analyses, reconstructed sources, and verification materials will be added incrementally.
