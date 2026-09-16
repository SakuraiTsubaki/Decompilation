# Decompilation

`Decompilation` is the shared, target-independent home for decompilation research, reusable analysis, and tooling.

This repository starts from a clean foundation. It does not retain migrated project content or assume a language, platform, build system, or executable format before real work requires one.

## Scope

| Area | Purpose |
| --- | --- |
| [`research/`](research/) | Methods, references, experiments, and open questions that can benefit more than one target. |
| [`analysis/`](analysis/) | Reproducible findings, format notes, comparisons, and verification records. |
| [`tools/`](tools/) | Reusable extraction, inspection, conversion, and verification utilities. |

Target-specific source, assets, symbols, build configuration, and progress belong in the corresponding target repository, such as a `PocketMonsters-*-Decompilation` repository. Shared work should move here only when it is genuinely target-independent.

## Working rules

- Record the origin and licensing terms of references and inputs.
- Separate confirmed findings from probable interpretations and hypotheses.
- Include enough commands, versions, hashes, or fixtures for another person to reproduce a result.
- Keep tools deterministic where practical and document their inputs, outputs, dependencies, and failure modes.
- Do not commit copyrighted game images, firmware, credentials, private keys, or locally extracted proprietary content.
- Add structure only when concrete work needs it; avoid placeholder hierarchies.

## Starting work

Create a focused subdirectory under the appropriate area. Give it a short README that states its purpose, inputs, provenance, procedure, outputs, verification method, and current confidence or status. Add tests beside a tool or analysis when automated verification is practical.
