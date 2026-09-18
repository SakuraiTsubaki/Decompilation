# NARC and member inventory workflow

`tools/narc_inventory.py` builds on the ROM file table emitted by
`tools/nds_rom_analyzer/analyzer.py`. It validates every file already identified
as a NARC instead of scanning arbitrary byte patterns.

## Coverage

- common NARC header, BOM, version, declared size, header size, and block count;
- ordered BTAF, BTNF, and GMIF block magic, size, and bounds;
- every BTAF member range relative to GMIF and to its parent container;
- optional BTNF filename trees, including the canonical anonymous table;
- member size, SHA-256, leading signature, extension, and probable format;
- common Nitro-format header validation for NCGR, NCLR, NSCR, NANR, NCER,
  NFTR, NSBMD, NSBTX, and related animation and sound formats;
- safe LZ10/LZ11 decompression with declared-size and back-reference bounds;
- recursive analysis of direct and safely decompressed nested NARCs;
- hash-sequence comparisons that distinguish equal, replace, delete, and insert
  operations without claiming a semantic cause.

No ROM or raw member payload is written. Complete member metadata is sharded
into ordered CSV files so every record remains reviewable and below practical
repository transport limits.

## Commands

```console
python tools/narc_inventory.py analyze input.nds analysis/generated/rom-structure/structure.json --output analysis/generated/narc-inventory
python tools/narc_inventory.py compare game-a/narc-inventory.json game-b/narc-inventory.json --output research/generation-iv-narc-members
python -m unittest tests.test_narc_inventory -v
```

## Evidence terms

- **Confirmed**: parsed offsets, sizes, hashes, valid NARC block structure,
  structurally valid common Nitro headers, and successfully bounded LZ decode.
- **Probable**: a known leading magic or compression marker whose complete
  internal format was not decoded.
- **Hypothesis**: not emitted automatically.

A byte beginning with `0x10` or `0x11` is not counted as confirmed compression
unless the entire declared LZ stream decodes with valid back-references. Huffman
and RLE markers remain Probable in this phase.

## Public implementation comparisons

- ndspy NARC parser and serializer:
  <https://github.com/RoadrunnerWMC/ndspy/blob/master/ndspy/narc.py>
- FEAT LZ10 implementation and format commentary:
  <https://github.com/SciresM/FEAT/blob/master/FEAT/DSDecmp/Formats/Nitro/LZ10.cs>
- FEAT LZ11 implementation:
  <https://github.com/SciresM/FEAT/blob/master/FEAT/DSDecmp/Formats/Nitro/LZ11.cs>
- devkitPro libnds BIOS decompression interface:
  <https://github.com/devkitPro/libnds/blob/master/include/nds/bios.h>

These sources were used as independent layout and codec comparisons. The
committed results come from direct parsing of the five identified local inputs.

