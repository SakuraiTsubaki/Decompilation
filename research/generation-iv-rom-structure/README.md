# Generation IV ROM structure comparison

## Scope

Path-based and content-hash comparisons of the five selected ROM inventories. ROM bytes are not included. Counts are **Confirmed** outputs of the same analyzer version and input hashes recorded in each inventory.

## Structure summary

| ROM | Code | ROM / used bytes | Files | Directories | ARM9 / ARM7 overlays | NARC | Banner |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Pokémon Diamond Version (USA, ADAE, header ROM version 5) | `ADAE` | `67108864` / `61169344` | `356` | `69` | `87` / `0` | `149` | `1` |
| Pokémon Pearl Version (USA, APAE, header ROM version 5) | `APAE` | `67108864` / `61169344` | `356` | `70` | `87` / `0` | `149` | `1` |
| 포켓몬스터Pt 기라티나 (Korea, CPUK, header ROM version 0) | `CPUK` | `134217728` / `102630460` | `461` | `105` | `122` / `0` | `215` | `3` |
| 포켓몬스터 하트골드 (Korea, IPKK, header ROM version 0) | `IPKK` | `134217728` / `124639804` | `511` | `46` | `129` / `0` | `308` | `3` |
| 포켓몬스터 소울실버 (Korea, IPGK, header ROM version 0) | `IPGK` | `134217728` / `124639804` | `511` | `46` | `129` / `0` | `308` | `3` |

## Pairwise file comparison

| Left | Right | Shared paths | Identical | Changed | Left-only | Right-only | Shared hashes at any path |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Pokémon Diamond Version (USA, ADAE, header ROM version 5) | Pokémon Pearl Version (USA, APAE, header ROM version 5) | 355 | 337 | 18 | 1 | 1 | 332 |
| Pokémon Diamond Version (USA, ADAE, header ROM version 5) | 포켓몬스터Pt 기라티나 (Korea, CPUK, header ROM version 0) | 326 | 169 | 157 | 30 | 135 | 174 |
| Pokémon Diamond Version (USA, ADAE, header ROM version 5) | 포켓몬스터 하트골드 (Korea, IPKK, header ROM version 0) | 161 | 64 | 97 | 195 | 350 | 109 |
| Pokémon Diamond Version (USA, ADAE, header ROM version 5) | 포켓몬스터 소울실버 (Korea, IPGK, header ROM version 0) | 161 | 64 | 97 | 195 | 350 | 109 |
| Pokémon Pearl Version (USA, APAE, header ROM version 5) | 포켓몬스터Pt 기라티나 (Korea, CPUK, header ROM version 0) | 325 | 168 | 157 | 31 | 136 | 173 |
| Pokémon Pearl Version (USA, APAE, header ROM version 5) | 포켓몬스터 하트골드 (Korea, IPKK, header ROM version 0) | 161 | 64 | 97 | 195 | 350 | 108 |
| Pokémon Pearl Version (USA, APAE, header ROM version 5) | 포켓몬스터 소울실버 (Korea, IPGK, header ROM version 0) | 161 | 64 | 97 | 195 | 350 | 108 |
| 포켓몬스터Pt 기라티나 (Korea, CPUK, header ROM version 0) | 포켓몬스터 하트골드 (Korea, IPKK, header ROM version 0) | 198 | 66 | 132 | 263 | 313 | 138 |
| 포켓몬스터Pt 기라티나 (Korea, CPUK, header ROM version 0) | 포켓몬스터 소울실버 (Korea, IPGK, header ROM version 0) | 198 | 66 | 132 | 263 | 313 | 138 |
| 포켓몬스터 하트골드 (Korea, IPKK, header ROM version 0) | 포켓몬스터 소울실버 (Korea, IPGK, header ROM version 0) | 511 | 390 | 121 | 0 | 0 | 355 |

## Interpretation limits

An identical SHA-256 proves byte identity for the compared file payloads. A changed hash proves a byte difference but not its semantic cause. A path missing from one FNT can still have related data elsewhere or in an overlay. `file-comparison.csv` and `structure-comparison.json` retain the complete path-level evidence.
