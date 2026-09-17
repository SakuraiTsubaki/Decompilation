# Non-ROM Artifact Preservation Policy

## Core rule

GitHub stores every storable work product except ROM binaries.

Excluded files are original ROMs, modified ROMs, rebuilt ROMs, and equivalent complete game-image or installable-package binaries. The repository validator blocks their common extensions.

## Required repository material

Commit all non-ROM results created, collected, normalized, converted, or organized during the work, including:

- research material, notes, reports, documentation, and README files;
- scripts, source code, tools, configuration, and build descriptions;
- logs, manifests, inventories, hashes, checklists, and progress records;
- comparison tables and CSV, JSON, YAML, TOML, XML, TSV, and other structured data;
- graphics, sprites, images, palettes, fonts, icons, tiles, atlases, and converted visual data;
- patches, diffs, symbol maps, address maps, validation reports, and test results;
- intermediate non-ROM outputs when they preserve provenance or make the process reproducible.

Do not discard a useful non-ROM result merely because it is generated, collected, intermediate, binary, large, or machine-readable. Organize it, document its provenance, and commit it.

## Graphics and sprite rule

Graphics-related work must include viewable PNG results.

Raw tile data, palettes, sprite metadata, font data, icons, conversion tables, or manifests are not sufficient by themselves. Commit one or more PNG sheets, previews, renders, or comparisons that let a reviewer inspect the actual visual result.

A graphics artifact directory should normally contain:

- a README explaining the source and conversion;
- the raw or converted non-ROM data;
- palette and metadata files;
- the conversion script and command;
- a manifest or hashes;
- one or more PNG outputs;
- validation or comparison results.

## Placement

Use `research/` and `analysis/` for topic-specific evidence, `tools/` for implementations, `artifacts/` for retained outputs, `manifests/` for indexes and hashes, `logs/` for execution records, and `patches/` for patch material.

Secrets, access tokens, credentials, and private keys are not work products and must not be committed.
