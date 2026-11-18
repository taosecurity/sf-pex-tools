# sf-pex-tools

Two small command-line tools for Starfield (and Fallout 4) mod authors:

- **pex_compare.py** tells you whether two compiled Papyrus scripts (`.pex`) do the same thing, even when
  their bytes differ. Use it to check that a rebuild of your mod changed only what you meant to change.
- **ba2_extract.py** lists, extracts and compares the files inside `.ba2` archives. You can take out one
  file instead of unpacking a whole archive, and see what changed between two versions of a mod.

`pex_compare.py` also reads scripts straight out of `.ba2` archives, so one command can compare the scripts in
two builds of a mod.

- They need Python 3.9 or newer and nothing else. (LZ4-compressed archives also need the `lz4` package; see
  [Install](#install).)
- They work on Windows and Linux.
- They only read your files. `extract` writes into the folder you name, and nothing else is written anywhere.
- They're released under the MIT license.

This tool was built with [Claude Code](https://claude.com/claude-code).

**For AI assistants:** [AGENTS.md](AGENTS.md) has step-by-step instructions: what the tools are for, the commands,
the exit codes and the limits.

## Quick start

Download the release zip, unpack it, and try it on the bundled test scripts:

```
python pex_compare.py compare tests/fixtures/pex/a1 tests/fixtures/pex/a2
```

```
same: SfPexToolsTest/Alpha.pex
same: SfPexToolsTest/Beta.pex
```

`a1` and `a2` are two builds of the same source, and their bytes differ. `pex_compare` reports them as the same.
Now compare the same build with `b`, which has one changed number in Alpha and one added comment in Beta:

```
python pex_compare.py compare tests/fixtures/pex/a1 tests/fixtures/pex/b
```

It prints `DIFFERENT` for both scripts, with a diff that shows `int:100` becoming `int:250`. Beta differs only in
its line-number debug information. Add `--ignore-debug` and Beta shows as `same`.

## Why a byte comparison doesn't work

Build the same `.psc` twice with the Creation Kit's compiler and you get two different `.pex` files. The compiler
keeps every name in a string table and refers to names by their position in it. Starfield's
`PapyrusAssembler.exe` also writes the string table, the variables, properties, functions and locals in a different
order on every run, and the compile time is stored in the file. A byte-for-byte check or a checksum always says
"changed".

`pex_compare.py` reads both scripts, swaps every table number for the name it stands for, puts the sections whose
order means nothing in a fixed order, renames the compiler's temporary variables by first use, and compares what's
left. The order of instructions inside a function is always compared as written.

## Common tasks

**Did my rebuild change anything?** Compare the archive you tested with the new one:

```
python pex_compare.py compare "old\MyMod - Main.ba2" "new\MyMod - Main.ba2"
```

Either side can be a `.ba2`, a folder (it searches every folder below it) or, for one script, a `.pex` file.
Scripts are matched by their path below `Scripts/`, so a `.ba2` can be compared with your `Data\Scripts` folder or
your build's output folder.

**Show one script's listing** (the text that gets compared):

```
python pex_compare.py dump Scripts\MyMod\QuestScript.pex
```

**List what's in an archive**, optionally only paths that contain some text (not case-sensitive):

```
python ba2_extract.py list "MyMod - Main.ba2"
python ba2_extract.py list "MyMod - Main.ba2" .pex
```

**Take out one file or a few:**

```
python ba2_extract.py extract "MyMod - Main.ba2" out QuestScript
```

Files keep their stored paths below `out`. Files that are already there are skipped unless you add `--force`.

**What changed between two versions of an archive?**

```
python ba2_extract.py diff "MyMod 1.0 - Main.ba2" "MyMod 1.1 - Main.ba2"
```

It lists files that are new, removed and changed, comparing their unpacked content. A rebuilt script always shows
as changed, so use `pex_compare.py` on the archives to see whether its code changed.

**Machine-readable results:** `pex_compare.py compare ... --json` prints the result as JSON (each script's status
and diff, counts, and the exit code).

## Where your files are

You can give an archive as a full path, or as a bare file name, which is looked up in the game's `Data` folder:

```
python ba2_extract.py list "Starfield - Interface.ba2" .swf
python ba2_extract.py where
```

`where` shows the Data folders it found. Without `--data`, the tools look in:

- **Steam:** `steamapps\common\Starfield\Data` in every Steam library (read from Steam's `libraryfolders.vdf`;
  the default is `C:\Program Files (x86)\Steam`). On Linux they look in `~/.steam/steam`,
  `~/.local/share/Steam` and the Flatpak Steam folder.
- **Game Pass / Xbox app:** `<drive>:\XboxGames\Starfield\Content\Data` on every drive.

Use `--data <folder>` to look somewhere else. Where mod managers keep a mod's own archives:

- **Mod Organizer 2:** each mod has its own folder, `<MO2 instance>\mods\<mod name>\`. The default instance is
  `%LOCALAPPDATA%\ModOrganizer\Starfield`; a portable install keeps `mods\` next to `ModOrganizer.exe`. The game's
  own archives stay in the game's Data folder.
- **Vortex:** the staging folder, by default `%APPDATA%\Vortex\starfield\mods\<mod name>\`, or the deployed copy
  in the game's Data folder.

For example, `python ba2_extract.py list "MyMod - Main.ba2" --data "%APPDATA%\Vortex\starfield\mods\MyMod-1.0"`.

The tools never write into any of these folders unless you name one as the `extract` output folder. Please don't.

## Install

1. Install Python 3.9 or newer from https://www.python.org (on Windows, tick "Add python.exe to PATH").
2. Download `sf-pex-tools-<version>.zip` from the [releases page](https://github.com/taosecurity/sf-pex-tools/releases)
   and check it against the `.sha256` file next to it:

   ```
   certutil -hashfile sf-pex-tools-0.1.0.zip SHA256
   ```

   On Linux: `sha256sum -c sf-pex-tools-0.1.0.zip.sha256`.
3. Unpack it anywhere. Keep `pex_compare.py` and `ba2_extract.py` in the same folder, because `pex_compare.py`
   uses `ba2_extract.py` to read archives.
4. Only if you'll read LZ4-compressed archives (the game's texture archives use LZ4; archives made by the
   Creation Kit's Archive2 for scripts use zlib): `python -m pip install lz4==4.4.5`. The tools tell you
   when an archive needs it.

Check the install with the tests: `python -I tests/test_sf_pex_tools.py`.

## Options

Options go after the command name.

| Option | Commands | What it does |
|---|---|---|
| `--ignore-debug` | `compare`, `dump` | Leave out line-number debug info, which changes when only comments or blank lines move |
| `--json` | `compare` | Print the result as JSON |
| `--data <folder>` | `list`, `extract`, `diff`, `where` | Where to look up an archive given by bare name |
| `--force` | `extract` | Replace files that are already in the output folder |
| `--max-size <MB>` | `extract`, `diff` | Largest single file to unpack (default 1024 MB) |
| `--verbose` | all | Write a troubleshooting log to stderr |
| `--log <file>` | all | Append the same log to a file |
| `--version` | (before the command) | Print the version |

## Exit codes

| Code | pex_compare.py | ba2_extract.py |
|---|---|---|
| 0 | every script is equivalent (`dump`: it read the script) | it worked (`diff`: the archives hold the same files) |
| 1 | at least one script differs, or is only on one side | `diff` found new, removed or changed files |
| 2 | a script or archive couldn't be read, or bad arguments | an archive couldn't be read, or bad arguments |

## Logging

When something goes wrong, run the same command again with `--verbose` (the log goes to the screen, on stderr) or
`--log sf-pex-tools.log` (the log is added to the end of that file). The log records what was read (each archive's
version, type, file count and compression, and each script's PEX version, string count, objects and functions),
what was decided for each file, and the full error if a run stopped. Errors name the file and say what to do.
Attach the log when you report a problem.

## What it reads

- **Scripts:** Fallout 4 (PEX 3.9) and Starfield (PEX 3.12) compiled scripts, including Starfield's guards
  (`LockGuard`, `TryLockGuard`) and `GetAllMatchingStructs`. Skyrim scripts are stored big-endian and aren't supported.
- **Archives:** general (GNRL) and texture (DX10) BA2 archives, versions 1, 2 and 3 (Starfield uses 2 and 3) and
  Fallout 4's 7 and 8; zlib or LZ4. Textures come out as `.dds` files with a DX10 header rebuilt from the
  archive's record. BSA archives from older games aren't supported.

Archives and scripts from other people are read with care: sizes and offsets are checked against the file,
unpacking stops at the size the archive states, a file over `--max-size` is refused, stored names that would
leave the output folder (`..`, drive letters, `:` streams, Windows device names) are skipped, and control
characters in names are shown as `\xNN`.

## Limits

- It compares compiled code, not source. To read a script's source again, use a decompiler such as
  [Champollion](https://github.com/Orvid/Champollion).
- `pex_compare` compares one script with another script, or two collections of scripts. To check a single
  script from an archive, extract it first.
- It doesn't pack archives. Use the Creation Kit's Archive2, or [BSArch](https://github.com/sableeyed/BSArch).
- The game's own scripts and archives belong to Bethesda. Look inside them on your own PC, but don't share what
  you extract.
- It makes no network connections and uploads nothing ([PRIVACY.md](PRIVACY.md)).

## Tests

`python -I tests/test_sf_pex_tools.py -v` runs the tests. They use only test scripts written for this project
(`tests/fixtures/src`), compiled with the Creation Kit's compiler and packed with Archive2
(`tests/fixtures/make_fixtures.py`), plus archives the tests build themselves. Nothing from the game is included.

## License

MIT. See [LICENSE](LICENSE). Questions and bug reports: https://github.com/taosecurity/sf-pex-tools/issues.
