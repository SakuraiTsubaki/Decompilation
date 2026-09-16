# Decompilation

A shared, target-independent foundation for reproducible decompilation research, analysis, and tooling.

This repository owns methods and utilities that apply across targets. Game- or build-specific source, symbols, assets, configurations, and conclusions belong in the corresponding target repository, including the `PocketMonsters-*-Decompilation` and `PokemonLegends-*-Decompilation` series.

## Repository responsibilities

| Area | Responsibility |
| --- | --- |
| [`research/`](research/) | Cross-target experiments, literature and reference studies, open questions, and reusable research methods. |
| [`analysis/`](analysis/) | Verified format, algorithm, comparison, and validation findings that generalize across targets. |
| [`tools/`](tools/) | Reusable extraction, inspection, conversion, comparison, and verification utilities. |
| [`docs/`](docs/) | Shared methodology, repository boundaries, evidence standards, and operating guidance. |
| [`scripts/`](scripts/) | Repository maintenance and validation entry points. |
| [`tests/`](tests/) | Automated checks for shared tooling and repository policy. |

## Operating model

1. Identify the exact target and inputs before drawing conclusions.
2. Capture provenance, versions, hashes, commands, and environment details.
3. Record experiments under `research/`.
4. Promote repeatable findings to `analysis/` with an explicit confidence level.
5. Implement repeatable operations under `tools/`, with tests and documented interfaces.
6. Keep target-specific work in its target repository; promote only genuinely reusable work here.
7. Verify repository policy with `python scripts/check_repository.py .`.

See [the methodology](docs/methodology.md) and [the repository model](docs/repository-model.md) before starting substantial work.

## Evidence standard

Conclusions use three levels:

- **Confirmed** — reproduced or directly supported by inspectable evidence.
- **Probable** — supported by multiple observations but not fully verified.
- **Hypothesis** — a working interpretation awaiting stronger evidence.

A useful record identifies inputs without redistributing restricted material, gives exact reproduction steps, separates observation from interpretation, and states how the result was checked.

## Safety and distribution

Do not commit copyrighted game images, firmware, credentials, private keys, or locally extracted proprietary content. Prefer hashes, manifests, small independently distributable fixtures, patches where lawful, and scripts that operate on user-supplied inputs.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md). New work should begin from the templates in `research/` or `analysis/`, remain narrowly scoped, and include an appropriate verification path.
