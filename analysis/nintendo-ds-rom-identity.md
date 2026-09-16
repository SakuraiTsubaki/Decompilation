# Analysis: Nintendo DS ROM identity baseline

## Target and applicability

This method applies to ordinary Nintendo DS cartridge images with a complete
512-byte header. It records identity metadata without extracting or committing
restricted content. DSi-enhanced validation, secure-area authentication, and
preservation-database matching are outside this first unit.

## Claim

A complete-file cryptographic hash, selected cartridge-header fields, nominal
capacity, and recalculated header CRC provide a reproducible local identity
baseline. A valid header CRC is an internal consistency check; it does not prove
that an image is a known-good retail dump.

## Evidence

The Nintendo DS header stores the game title at `0x0000..0x000B`, game code at
`0x000C..0x000F`, maker code at `0x0010..0x0011`, unit code at `0x0012`,
device-capacity exponent at `0x0014`, ROM version at `0x001E`, and header
CRC-16 at `0x015E..0x015F`. The CRC covers `0x0000..0x015D` and is calculated
with initial value `0xFFFF` and reflected polynomial `0xA001`.

## Method

Run:

```console
python tools/nds_rom_inventory/rom_inventory.py /path/to/input.nds
```

The implementation reads the file in 1 MiB chunks, calculates SHA-256, SHA-1,
and MD5 over the complete byte stream, retains only the first 512 bytes for
header parsing, and compares stored and calculated header CRC values.

## Findings

- Nominal capacity is `128 KiB << device_capacity_exponent`.
- The raw ROM-version byte must be reported separately from any inferred
  commercial revision label.
- Full-file hash agreement with a separately documented build target is stronger
  evidence than filename, title, game-code, or header-only agreement.
- Header CRC agreement detects many header changes but says nothing about
  non-header bytes.

## Confidence

**Confirmed** for the parsing and CRC procedure, covered by synthetic known-vector
and malformed-identity tests. Any target-specific preservation claim remains the
responsibility of the corresponding target repository.

## Verification

```console
python -m unittest tests.test_nds_rom_inventory -v
python scripts/check_repository.py .
```

Expected result: all synthetic tests pass and repository policy reports no
restricted binary.

## Unknowns

Secure-area checks, filesystem bounds, FNT/FAT integrity, overlay tables,
banner integrity, padding, and independently curated hash catalogs require
separate analysis units.
