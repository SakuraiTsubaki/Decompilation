# Decompilation

A shared, target-independent foundation for reproducible decompilation research, analysis, tooling, and retained non-ROM work products.

This repository owns methods and utilities that apply across targets. Game- or build-specific work belongs in the corresponding target repository, including the `PocketMonsters-*-Decompilation` and `PokemonLegends-*-Decompilation` series.

## Repository responsibilities

| Area | Responsibility |
| --- | --- |
| [`research/`](research/) | Cross-target experiments, collected research, open questions, and reusable methods. |
| [`analysis/`](analysis/) | Verified format, algorithm, comparison, and validation findings. |
| [`tools/`](tools/) | Reusable extraction, inspection, conversion, comparison, and verification utilities. |
| [`artifacts/`](artifacts/) | Generated or collected non-ROM outputs, including graphics and converted data. |
| [`manifests/`](manifests/) | Hashes, inventories, file maps, build records, and machine-readable indexes. |
| [`logs/`](logs/) | Reproducible command, extraction, build, comparison, and validation logs. |
| [`patches/`](patches/) | Patch files and the evidence needed to generate and verify them. |
| [`docs/`](docs/) | Shared methodology, repository boundaries, evidence standards, and operating guidance. |
| [`scripts/`](scripts/) | Repository maintenance and validation entry points. |
| [`tests/`](tests/) | Automated checks for shared tooling and repository policy. |

## Operating model

1. Identify the exact target and inputs before drawing conclusions.
2. Capture provenance, versions, hashes, commands, environment details, and collected research.
3. Record experiments under `research/`.
4. Promote repeatable findings to `analysis/` with an explicit confidence level.
5. Implement repeatable operations under `tools/`, with tests and documented interfaces.
6. Preserve every storable non-ROM output: reports, source, scripts, logs, tables, structured data, manifests, patches, validation material, and visual results.
7. Keep target-specific work in its target repository; promote genuinely reusable work here.
8. Verify repository policy with `python scripts/check_repository.py .`.

See [the methodology](docs/methodology.md), [the repository model](docs/repository-model.md), and [the artifact policy](ARTIFACT_POLICY.md).

## Evidence standard

Conclusions use three levels:

- **Confirmed** — reproduced or directly supported by inspectable evidence.
- **Probable** — supported by multiple observations but not fully verified.
- **Hypothesis** — a working interpretation awaiting stronger evidence.

A useful record includes its non-ROM evidence and outputs directly in Git whenever they can be stored. Use hashes and manifests to identify the excluded ROM binary.

## Storage policy

Only original, modified, or rebuilt ROM binaries—and equivalent full game-image/package binaries—are excluded from GitHub. All other storable work products are repository material.

Graphics and sprite work must include viewable PNG output in addition to raw data, palettes, metadata, tile data, or conversion descriptions. See [ARTIFACT_POLICY.md](ARTIFACT_POLICY.md).

Secrets, credentials, and private keys are not work products and must never be committed.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md). New work should preserve its complete non-ROM research trail and verification evidence.
