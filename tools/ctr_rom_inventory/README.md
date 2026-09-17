# CTR ROM Inventory

Read-only Nintendo 3DS NCSD/NCCH inventory utility for Generation VI and other CTR targets.

## Purpose

This tool fingerprints a supplied `.3ds` / `.cci` / `.cxi` / raw NCCH-style image before any binary-level research or patching. It does not decrypt, extract, rewrite, or redistribute ROM data.

The tool records:

- whole-input SHA-256 and byte size;
- NCSD or NCCH magic;
- NCSD declared media size, media ID, card title version/revision and partition table;
- per-partition type, crypto type, range validation and optional SHA-256;
- nested NCCH partition/program IDs and product code;
- NCCH ExHeader size/hash and flags;
- Plain/Logo/ExeFS/RomFS declared offsets and sizes;
- ExeFS/RomFS superblock hashes from the header.

## Usage

```bash
python3 tools/ctr_rom_inventory/inventory.py /path/to/input.3ds \
  --output artifacts/identity.json
```

For raw per-partition hashes:

```bash
python3 tools/ctr_rom_inventory/inventory.py /path/to/input.3ds \
  --deep-hash \
  --output artifacts/identity.deep.json
```

ROM images must remain outside Git. Commit only the generated non-ROM JSON/log/manifests and subsequent reproducible analysis artifacts.

## Determinism

For identical input bytes and tool revision, the JSON values are deterministic. The output includes the source filename; use a stable basename when byte-for-byte JSON comparison is required.

## Format references

The parser follows the documented CTR media-unit size (`0x200` bytes), NCSD partition table, and NCCH header offsets described by 3dbrew:

- https://3dbrew.org/wiki/NCSD
- https://3dbrew.org/wiki/NCCH

The current tool intentionally stops at header/inventory metadata. ExeFS/RomFS file enumeration, decryption-aware handling, update-title comparison, executable/CRO mapping, and patch generation belong to later verified stages.
