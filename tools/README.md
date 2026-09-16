# Tools

Reusable, target-independent utilities live here.

Each tool receives its own directory and README. A tool directory should contain implementation, tests, small distributable fixtures when needed, and licensing notices for adapted third-party code.

Required documentation:

- supported inputs and explicit non-goals;
- runtime and dependency versions;
- command-line or library interface;
- output format and determinism guarantees;
- error behavior and safety constraints;
- verification commands;
- compatibility notes for target repositories.

Target constants, symbols, keys, extracted data, and build-specific wrappers remain in target repositories.
