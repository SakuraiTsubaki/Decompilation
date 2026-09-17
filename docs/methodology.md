# Decompilation Methodology

## 1. Identify

Record the target name, release, region, revision, platform, executable or image hashes, and relevant tool versions. A repository name alone is not a sufficient build identifier.

## 2. Preserve provenance and outputs

For each input or reference, record where it came from, when it was obtained, its terms, and a stable identifier. Keep the ROM binary outside Git, but commit all storable non-ROM collected material, manifests, notes, converted data, logs, and intermediate results.

## 3. Research

State a narrow question and design a repeatable experiment. Commit commands, environment records, observations, failed approaches, limitations, logs, and all non-ROM outputs.

## 4. Analyze

Turn observations into a structured claim. Separate facts from interpretation, assign a confidence level, connect the claim to committed evidence, and define a falsification or verification route.

## 5. Implement tooling

Automate stable operations. Define inputs and outputs, reject malformed data safely, avoid hidden state, and commit source, tests, fixtures, manifests, logs, and generated non-ROM examples.

## 6. Reconstruct

Target repositories may reconstruct source or data after the relevant build and evidence are fixed. Preserve unresolved behavior explicitly. Commit reconstructed source and every supporting non-ROM artifact.

## 7. Verify

Use the strongest practical method: byte comparison, structured diff, tests, trace comparison, deterministic rebuild, or documented manual procedure. Commit expected and observed results, logs, tables, reports, and patches.

Graphics and sprite verification must include actual PNG output alongside palettes, metadata, tile data, or conversion records.

## 8. Promote shared work

Move a method or tool here after target-specific assumptions are removed or isolated. Preserve the complete non-ROM evidence and artifact trail during promotion.
