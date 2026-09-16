# Decompilation Methodology

## 1. Identify

Record the target name, release, region, revision, platform, executable or image hashes, and relevant tool versions. A repository name alone is not a sufficient build identifier.

## 2. Preserve provenance

For each input or reference, record where it came from, when it was obtained, its license or distribution constraints, and a stable identifier such as a cryptographic hash or public URL. Do not upload restricted source material.

## 3. Research

State a narrow question and design a repeatable experiment. Capture commands, environment, observations, failed approaches, and limitations. Keep raw local artifacts outside Git.

## 4. Analyze

Turn observations into a structured claim. Separate facts from interpretation, assign a confidence level, connect the claim to supporting evidence, and define a falsification or verification route.

## 5. Implement tooling

Automate stable, repeated operations. Define inputs and outputs, reject malformed data safely, avoid hidden state, and include tests with independently distributable fixtures.

## 6. Reconstruct

Target repositories may reconstruct source or data only after the relevant target build and evidence are fixed. Preserve unresolved behavior explicitly instead of inventing semantics.

## 7. Verify

Use the strongest practical method: byte comparison, structured diff, unit or regression tests, trace comparison, deterministic rebuild, or a documented manual procedure. Record both expected and observed results.

## 8. Promote shared work

Move a method or tool into this repository only after target-specific assumptions have been removed or made explicit. Keep adapters and build-specific configuration in target repositories.
