# Security Policy

## Scope

This repository contains decompilation research, reconstructed source, tools, scripts, tests, configuration, and documentation. Security reports are most relevant when they concern repository tooling, automation, parsers, build scripts, or other code that could affect contributors' systems or CI environments.

## Reporting

Please do not publish sensitive exploit details in a public issue when a report could create a practical risk for users or contributors.

For ordinary bugs that do not involve a security risk, use the normal GitHub issue templates instead.

## Supported State

The repository is currently in an early foundation stage. Security-relevant fixes should target the current `main` branch.

## Tooling Expectations

Contributed tools should avoid unsafe defaults, untrusted command execution, hard-coded credentials, and machine-specific secrets. Inputs derived from external binaries or assets should be treated as untrusted unless the tool explicitly documents otherwise.
