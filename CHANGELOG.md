# Changelog

## 0.1.0 (2026-11-18)

### What's new

This is the first public release. sf-pex-tools tells Starfield (and Fallout 4) mod authors whether a rebuild of their mod changed its scripts, and lets them look inside `.ba2` archives. `pex_compare.py` compares compiled Papyrus scripts by meaning, so two builds of the same source count as the same even though their bytes differ. `ba2_extract.py` lists, extracts and compares the files inside `.ba2` archives. Both are based on two scripts that had been used privately since 2026-11-02 to check rebuilt mods.

### Example

The release zip holds two builds of the same made-up scripts (`a1`, `a2`) and a third (`b`) with one changed number:

    > python pex_compare.py compare tests/fixtures/pex/a1 tests/fixtures/pex/a2
    same: SfPexToolsTest/Alpha.pex
    same: SfPexToolsTest/Beta.pex

    > python pex_compare.py compare tests/fixtures/a1.ba2 tests/fixtures/b.ba2 --ignore-debug
    DIFFERENT: sfpextoolstest/alpha.pex
       --- first
       +++ second
       @@ -65,5 +65,5 @@
              returns sfpextoolstest:alpha#mission[]  doc ''  userflags 0x0  flags 0x0
              local ::t1 : sfpextoolstest:alpha#mission[]
       -         0 array_getallmatchingstructs ident:Missions, ident:::t1, str:'Reward', int:100, int:0, int:-1
       +         0 array_getallmatchingstructs ident:Missions, ident:::t1, str:'Reward', int:250, int:0, int:-1
                 1 return ident:::t1
            function Score
    same: sfpextoolstest/beta.pex

### pex_compare.py

- `dump` and `compare` compare Fallout 4 (PEX 3.9) and Starfield (PEX 3.12) scripts by meaning. The string-table order, compile times, the order of sections whose order means nothing, and the numbering of temporary variables are ignored.
- Temporaries are renamed in the order the code first uses them. Struct members are sorted, and their declared order is still compared through the debug information.
- Where and by whom a script was built (source folder, user, machine) isn't compared; `dump` shows it on a `# not compared` line.
- Two files on one side that match the same script name are reported as `DUPLICATE` (exit 2) instead of one hiding the other.
- `compare` reads scripts straight from `.ba2` archives and from folders, in any mix. `--json` prints a machine-readable result.

### ba2_extract.py

- `list`, `extract`, `diff` and `where` work on general and texture archives (versions 1, 2, 3, 7 and 8; zlib or LZ4). An archive can be given by bare name and is looked up in `--data` or in the Steam and Game Pass Data folders.
- `diff` lists a file whose stated size changed as changed without unpacking it (marked `stated sizes`). Names an archive stores twice (ignoring case) are marked by `list`, skipped by `extract` and stop `diff`.

### Safety and troubleshooting

- The tools read archives from strangers with care. They check sizes and offsets, stop unpacking at the stated size, apply a `--max-size` limit, and skip unsafe stored names (including paths through a link that points out of the output folder).
- `extract` doesn't overwrite files without `--force`, which swaps in a new file, so it never writes through a hard link. Control characters in names are shown as `\xNN`.
- `--verbose` and `--log <file>` write a troubleshooting log.

### Download

Download `sf-pex-tools-0.1.0.zip` and its `.sha256` file below, unzip it anywhere and follow the Install steps in the README. It needs Python 3.9 or newer and nothing else; LZ4 archives also need `python -m pip install lz4==4.4.5`.
