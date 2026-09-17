# Repository Model

## Shared repository

`SakuraiTsubaki/Decompilation` contains target-independent methodology, research, analysis, tooling, templates, policy, and reusable non-ROM artifacts.

## Target repositories

Each repository in the `PocketMonsters-*-Decompilation` or `PokemonLegends-*-Decompilation` series owns one named target and contains its exact target identity, research, analysis, tools, source reconstruction, configuration, tests, progress, and retained non-ROM work products.

## Artifact ownership

Work begins in the narrowest repository that can describe it honestly. Commit every storable non-ROM result there. Promote reusable work to the shared repository without discarding its research history, logs, manifests, patches, visual outputs, or verification material.

## Dependency direction

Target repositories may consume shared guidance and tools. The shared repository must not depend on a target repository for basic operation.

## Versioning and compatibility

Shared tools state compatibility explicitly. Target repositories record the shared tool revision used for each result. Later tool versions must not silently invalidate earlier evidence.
