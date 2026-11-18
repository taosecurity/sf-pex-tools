# Changelog

## 0.1.0 (not yet released)

First public release. It's based on two scripts that had been used privately since 2026-11-02 to check rebuilt
mods.

- `pex_compare.py dump` and `compare` compare Fallout 4 (PEX 3.9) and Starfield (PEX 3.12) scripts by meaning.
  The string-table order, compile times, the order of sections whose order means nothing, and the numbering of
  temporary variables are ignored. Struct members are sorted, and their declared order is still compared through
  the debug information.
- `compare` reads scripts straight from `.ba2` archives, and from folders, in any mix. `--json` prints a
  machine-readable result.
- `ba2_extract.py list`, `extract`, `diff` and `where` work on general and texture archives (versions 1, 2, 3, 7
  and 8; zlib or LZ4). An archive can be given by bare name and is looked up in `--data` or in the Steam and
  Game Pass Data folders.
- The tools read archives from strangers with care. They check sizes and offsets, stop unpacking at the stated
  size, apply a `--max-size` limit, skip unsafe stored names, don't overwrite files without `--force`, and show
  control characters as `\xNN`.
- `--verbose` and `--log <file>` write a troubleshooting log.
