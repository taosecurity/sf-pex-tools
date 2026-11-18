# Changelog

## 0.1.0 (not yet released)

First public release. It's based on two scripts that had been used privately since 2026-11-02 to check rebuilt
mods.

- `pex_compare.py dump` and `compare` compare Fallout 4 (PEX 3.9) and Starfield (PEX 3.12) scripts by meaning.
  The string-table order, compile times, the order of sections whose order means nothing, and the numbering of
  temporary variables are ignored. Temporaries are renamed in the order the code first uses them. Struct
  members are sorted, and their declared order is still compared through the debug information. Where and by
  whom a script was built (source folder, user, machine) isn't compared; `dump` shows it on a `# not compared`
  line.
- Two files on one side that match the same script name are reported as `DUPLICATE` (exit 2) instead of one
  hiding the other.
- `compare` reads scripts straight from `.ba2` archives, and from folders, in any mix. `--json` prints a
  machine-readable result.
- `ba2_extract.py list`, `extract`, `diff` and `where` work on general and texture archives (versions 1, 2, 3, 7
  and 8; zlib or LZ4). An archive can be given by bare name and is looked up in `--data` or in the Steam and
  Game Pass Data folders.
- The tools read archives from strangers with care. They check sizes and offsets, stop unpacking at the stated
  size, apply a `--max-size` limit, skip unsafe stored names (including paths through a link that points out of
  the output folder), don't overwrite files without `--force` (which swaps in a new file, so it never writes
  through a hard link or symlink), and show control characters as `\xNN`.
- `diff` lists a file whose stated size changed as changed without unpacking it (marked `stated sizes`). Names an
  archive stores twice (ignoring case) are marked by `list`, skipped by `extract` and stop `diff`.
- `--verbose` and `--log <file>` write a troubleshooting log.
