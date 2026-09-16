# Nintendo DS ROM inventory

`rom_inventory.py` is a dependency-free, read-only identity tool for user-supplied
Nintendo DS ROM images. It streams each input through SHA-256, SHA-1, and MD5,
parses the core 512-byte cartridge header, derives nominal capacity, and verifies
the header CRC-16.

The tool does not extract files, patch the input, copy ROM bytes into the
repository, or establish preservation-database identity by itself.

## Runtime

- Python 3.10 or later
- Python standard library only

## Usage

```console
python tools/nds_rom_inventory/rom_inventory.py /path/to/input.nds
python tools/nds_rom_inventory/rom_inventory.py /path/to/input-directory --output /tmp/inventory.json
python tools/nds_rom_inventory/rom_inventory.py /path/to/input-directory --verify config/target.json
```

Verification compares only identity fields present in the supplied JSON
`roms` entries and exits nonzero for missing, unexpected, or changed inputs.

## Verification

```console
python -m unittest tests.test_nds_rom_inventory -v
python scripts/check_repository.py .
```

Tests use synthetic headers and contain no game data. Output JSON is
deterministic for a fixed set of input bytes and filenames; it does not include
timestamps or machine-specific absolute paths.
