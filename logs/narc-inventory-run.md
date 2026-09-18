# Generation IV NARC inventory run

## Environment

- Tool: `narc_inventory 1.0.0`
- Python: bundled CPython 3.12 runtime
- Inputs: five local ROMs matched against the SHA-256 stored in their structure
  inventories before analysis
- Raw ROM/member bytes committed: no

## Commands

```console
python tools/narc_inventory.py analyze ROM structure.json --output phase3_outputs/GAME
python tools/narc_inventory.py compare phase3_outputs/*/narc-inventory.json --output phase3_outputs/comparison
python -m unittest discover -s tests -v
```

## Result

- 1,129 of 1,129 top-level NARCs parsed successfully.
- 2 nested Platinum NARCs parsed recursively.
- 234,819 total member records generated.
- zero malformed top-level NARCs.
- ordered CSV shards retain every member and comparison row.

