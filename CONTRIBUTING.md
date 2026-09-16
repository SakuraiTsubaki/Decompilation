# Contributing to Decompilation

Thank you for helping improve the repository. Contributions should make the decompilation process more reproducible, reviewable, and verifiable.

## Core Principles

1. **Evidence before assumption.** Distinguish confirmed behavior from hypotheses.
2. **Preserve provenance.** Record where names, formats, offsets, structures, and behaviors came from.
3. **Prefer reproducibility.** Scripts, commands, configs, and verification steps should be repeatable by another contributor.
4. **Keep reconstruction incremental.** Small, reviewable changes are preferred over large opaque rewrites.
5. **Verify behavior.** Reconstructed source should be checked against documented reference behavior or outputs whenever possible.

## Where Work Belongs

| Work | Location |
| --- | --- |
| Reconstructed high-level source | `src/code/` |
| Remaining assembly | `src/asm/` |
| Types, declarations, constants | `src/include/` |
| Source-linked data | `src/data/` |
| Binary and function research | `analysis/` |
| Reusable extraction/conversion/build tools | `tools/` |
| Build and symbol configuration | `config/` |
| Methodology and architecture documentation | `docs/` |
| Automated tests | `tests/` |
| Entry-point automation | `scripts/` |

## Analysis Notes

Analysis should clearly separate:

- **Confirmed** — directly supported by reproducible evidence.
- **Probable** — strongly supported but not yet fully verified.
- **Hypothesis** — a working interpretation that still needs evidence.

When practical, include addresses, symbols, signatures, call relationships, file-format fields, or comparison results that support the conclusion.

## Naming

Use descriptive names only when evidence supports them. Temporary names such as `sub_<address>`, `func_<address>`, `data_<address>`, or an equivalent project-specific convention are preferred to invented semantics.

When renaming a symbol, document the reason when it is not obvious from the code itself.

## Source Reconstruction

- Keep generated code clearly distinguishable from hand-reconstructed code when both exist.
- Avoid silently changing known behavior while cleaning up reconstructed source.
- Keep low-level or unresolved behavior in `src/asm/` until a higher-level reconstruction is justified.
- Add comments for decompilation-specific reasoning, not for obvious language syntax.

## Tools and Scripts

New tools should:

- have a clear purpose;
- avoid hard-coded machine-specific paths;
- fail with useful error messages;
- document required inputs and produced outputs;
- be deterministic where practical.

## Tests and Verification

A meaningful reconstruction change should include an appropriate verification path. Depending on the target, that may be a unit test, regression test, binary/data comparison, hash comparison, or documented manual check.

## Repository Safety

Do not commit original, modified, or rebuilt ROM images or installable game packages. The repository CI checks common ROM/package extensions to catch accidental additions.

## Pull Requests

Keep pull requests focused. In the description, explain:

- what was analyzed or reconstructed;
- the evidence used;
- what changed;
- how the result was verified;
- any uncertainty or unresolved follow-up work.

Before submitting, run the available repository checks and make sure new files are placed in the correct part of the tree.
