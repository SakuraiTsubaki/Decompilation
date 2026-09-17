# NDS ROM analyzer

## Scope

`nds_rom_analyzer` inventories Nintendo DS cartridge structure without extracting
or committing payload bytes. It consumes a user-supplied ROM and produces JSON,
CSV, and Markdown containing offsets, sizes, addresses, hashes, table entries,
recognized leading signatures, validation results, and unreferenced physical
ranges.

Implemented coverage:

- all standard 512-byte NDS header fields and reserved-range hashes;
- ARM9 and ARM7 ROM, entry, load, RAM-end, size, and SHA-256 information;
- complete FNT directory traversal and FAT entry validation;
- every NitroFS/FAT file path, offset, size, SHA-256, extension, and signature;
- complete ARM9 and ARM7 overlay tables and RAM placement;
- banner versions 1–3, localized titles, icon/palette hashes, and applicable CRCs;
- secure-area raw-byte identity with decrypted CRC validation explicitly deferred;
- referenced-region coverage, physical gaps, trailing padding, alignment, and
  byte-distribution summaries;
- NARC, SDAT, Nitro graphics/model/audio formats, BMG, and Nintendo compression
  signatures;
- path-based and content-hash comparison of multiple inventories.

## Technical references

- Nintendo DS Game Card Manual, “NITRO_Card_Manual-1_01-20051109,” for the
  cartridge header and generated region definitions:
  <https://twlsdk.randommeaninglesscharacters.com/download/CardManual/NITRO_Card_Manual-1_01-20051109.pdf>
- GBATEK Nintendo DS cartridge header, secure area, FNT/FAT, overlay, and banner
  descriptions: <https://doc.kodewerx.org/documents/gbatek.html>
- devkitPro `ndstool` banner implementation, used to cross-check the version-1
  banner CRC coverage: <https://github.com/devkitPro/ndstool/blob/master/source/banner.cpp>
- Ekona cartridge-header field map, used as an additional independent field-layout
  comparison: <https://scenegate.github.io/Ekona/docs/specs/cartridge/header.html>

Where references disagree or use historical terminology, the output preserves raw
values and avoids inventing semantic names. In particular, the final overlay-table
word is retained as a 24-bit size field plus an 8-bit flags field, and the tool does
not claim successful secure-area CRC validation without decrypting the secure area.

## Commands

Analyze one input:

```console
python tools/nds_rom_analyzer/analyzer.py input.nds --output analysis/generated/rom-structure --label "target label"
```

Compare inventories:

```console
python tools/nds_rom_analyzer/analyzer.py compare \
  target-a/structure.json target-b/structure.json \
  --output research/comparison
```

Run automated tests:

```console
python -m unittest tests.test_nds_rom_analyzer -v
python scripts/check_repository.py .
```

## Evidence language

- **Confirmed**: raw fields, table entries, offsets, hashes, calculated CRCs, and
  deterministic comparisons produced directly from the identified inputs.
- **Probable**: format classification based on a recognized leading magic when the
  complete semantic format has not yet been parsed.
- **Hypothesis**: none is emitted automatically. Unknown formats remain unknown.

“Unreferenced” means no parsed header region, executable, table, banner, or FAT file
covers the physical range. It does not prove the bytes are unused by custom runtime
code. Likewise, a changed file hash proves a byte difference but does not explain
its semantic cause.
