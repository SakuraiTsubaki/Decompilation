# Repository Model

## Shared repository

`SakuraiTsubaki/Decompilation` contains target-independent methodology, research, analysis, tooling, templates, and policy.

## Target repositories

Each `PocketMonsters-*-Decompilation` repository owns one named target and contains its exact target identity, target-specific research, analysis, tools, source reconstruction, configuration, tests, and progress records.

## Promotion rule

Work begins in the narrowest repository that can describe it honestly. Promote work to the shared repository only when:

- target-specific constants and paths are removed or isolated;
- supported inputs and limitations are documented;
- tests cover the reusable behavior;
- provenance and licensing permit reuse.

## Dependency direction

Target repositories may consume shared guidance and tools. The shared repository must not depend on a target repository for its basic operation.

## Versioning and compatibility

Shared tools should state compatibility explicitly. Target repositories should pin or record the shared tool revision used for a verified result. A later tool version must not silently invalidate earlier evidence.
