# Tools

This directory holds target-independent utilities for extraction, inspection, conversion, comparison, and verification.

Give each tool its own directory once implementation begins. Document:

- purpose and supported inputs;
- runtime and dependency requirements;
- usage and produced outputs;
- safety constraints and failure behavior;
- tests or another repeatable verification method;
- the license for bundled or adapted third-party code.

Target-specific wrappers and build scripts belong in the corresponding target repository unless they become genuinely reusable.
