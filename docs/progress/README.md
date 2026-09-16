# Progress Tracking

This directory tracks measurable decompilation progress when concrete targets are added to the repository.

## Status Legend

| State | Meaning |
| --- | --- |
| ⚪ Not started | No verified work has begun. |
| 🔵 Analysis | Evidence gathering and structural analysis are in progress. |
| 🟡 Reconstruction | Source, data, or tooling is actively being reconstructed. |
| 🟣 Verification | The reconstructed result is being tested or compared. |
| ✅ Verified | The defined scope has passed its documented verification criteria. |
| ⛔ Blocked | Progress depends on unresolved evidence, tooling, or another task. |

## Target Progress Template

Use a separate Markdown file or subdirectory for each concrete target when target work begins.

```markdown
# Target Name

| Area | State | Evidence / Notes |
| --- | --- | --- |
| Binary layout | ⚪ Not started | |
| Functions | ⚪ Not started | |
| Symbols | ⚪ Not started | |
| Structures | ⚪ Not started | |
| Formats | ⚪ Not started | |
| Source reconstruction | ⚪ Not started | |
| Build | ⚪ Not started | |
| Tests | ⚪ Not started | |
| Comparison | ⚪ Not started | |
| Verification | ⚪ Not started | |
```

Progress should reflect verifiable repository state rather than an estimated percentage whenever possible.
