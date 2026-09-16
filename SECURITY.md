# Security Policy

Security reports are relevant when repository tools, parsers, build helpers, workflows, or supplied examples could execute untrusted input or affect contributor systems.

Do not publish practical exploit details in a public issue. Use GitHub's private vulnerability reporting feature when it is available for this repository. Ordinary correctness bugs may use a normal issue.

Treat all external binaries, archives, symbols, and metadata as untrusted. Tools should avoid shell interpolation, unsafe archive extraction, uncontrolled path traversal, implicit credential use, and destructive defaults.
