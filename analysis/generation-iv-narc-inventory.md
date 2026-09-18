# Generation IV NARC/member inventory

## Scope and provenance

The five verified structure inventories were used as the authoritative list of
top-level NARC files. Diamond and Pearl are the selected USA English inputs;
Platinum, HeartGold, and SoulSilver are the selected Korean inputs. Cross-family
differences therefore combine title, region, and language variables and are not
assigned a semantic cause without later data-specific analysis.

## Confirmed totals

| Input | Top-level NARCs | Nested NARCs | Members | Confirmed LZ10/LZ11 | Unknown members |
| --- | ---: | ---: | ---: | ---: | ---: |
| Diamond USA | 149 | 0 | 33,953 | 1,885 | 23,233 |
| Pearl USA | 149 | 0 | 33,953 | 1,885 | 23,233 |
| Platinum Korea | 215 | 2 | 53,565 | 2,490 | 35,025 |
| HeartGold Korea | 308 | 0 | 56,674 | 4,618 | 32,414 |
| SoulSilver Korea | 308 | 0 | 56,674 | 4,618 | 32,414 |
| **Total** | **1,129** | **2** | **234,819** | **15,496** | **146,319** |

All 1,129 top-level archives have valid bounds, declared sizes, and ordered
BTAF/BTNF/GMIF blocks. No malformed top-level archive was omitted. Every archive
uses the anonymous BTNF form in these inputs, so member names are not present in
the containers themselves. Member indices and complete container chains are
retained instead.

Platinum contains two nested NARCs at members 0 and 1 of
`/graphic/library_tv.narc`. No other direct or safely LZ-decoded nested NARC was
found.

## Format evidence

Common Nitro headers were structurally checked before raising their evidence
status to Confirmed. Compression-like leading bytes are reported separately:
LZ10/LZ11 streams are Confirmed only when bounded decompression succeeds, while
Huffman/RLE markers remain Probable pending codec validation.

Graphics were detected and their Nitro headers validated, but pixel, tile,
palette, cell, animation, and texture semantics were not decoded in this phase.
Consequently no misleading PNG previews are emitted. The member container chain,
index, hash, format, compression state, and transformation provenance needed for
the subsequent graphics decoder are preserved.

## Comparison interpretation

The shared comparison directory records every container path and every member
hash-sequence operation. `equal`, `replace`, `delete`, and `insert` describe byte
sequence alignment only; they do not by themselves prove localization changes,
version-exclusive content, or game-design intent.

