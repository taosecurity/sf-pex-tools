# sf-pex-tools

sf-pex-tools tells Starfield (and Fallout 4) mod authors whether a rebuild of their mod changed its scripts, and
lets them look inside `.ba2` archives. It has two small command-line tools:

- **pex_compare.py** tells you whether two compiled Papyrus scripts (`.pex`) do the same thing, even when
  their bytes differ. Use it to check that a rebuild of your mod changed only what you meant to change.
- **ba2_extract.py** lists, extracts and compares the files inside `.ba2` archives. You can take out one
  file instead of unpacking a whole archive, and see what changed between two versions of a mod.

Download the latest zip from [Releases](https://github.com/taosecurity/sf-pex-tools/releases), unzip it, open a
Command Prompt in the folder (see [Install](#install)) and try it on the bundled test scripts:

```
python pex_compare.py compare tests/fixtures/pex/a1 tests/fixtures/pex/a2
```

For AI assistants: step-by-step instructions are in [AGENTS.md](AGENTS.md).

## Example

The release zip holds two builds of the same made-up scripts (`a1` and `a2`) and a third build (`b`) with one
changed number in Alpha and one added comment in Beta. This is a real run on them:

```
> python pex_compare.py compare tests/fixtures/pex/a1 tests/fixtures/pex/a2
same: SfPexToolsTest/Alpha.pex
same: SfPexToolsTest/Beta.pex
```

The bytes of `a1` and `a2` differ, but `pex_compare` reports them as the same, because the code is the same. Now
compare `a1` with `b`:

```
> python pex_compare.py compare tests/fixtures/pex/a1 tests/fixtures/pex/b
DIFFERENT: SfPexToolsTest/Alpha.pex
   --- first
   +++ second
   @@ -65,5 +65,5 @@
          returns sfpextoolstest:alpha#mission[]  doc ''  userflags 0x0  flags 0x0
          local ::t1 : sfpextoolstest:alpha#mission[]
   -         0 array_getallmatchingstructs ident:Missions, ident:::t1, str:'Reward', int:100, int:0, int:-1
   +         0 array_getallmatchingstructs ident:Missions, ident:::t1, str:'Reward', int:250, int:0, int:-1
             1 return ident:::t1
        function Score
DIFFERENT: SfPexToolsTest/Beta.pex
   --- first
   +++ second
   @@ -72,9 +72,9 @@
             0 strcat ident:::t1, str:'[SfPexToolsTest] full, ignored ', ident:asName
             1 callstatic ident:debug, ident:Trace, ident:::nonevar, ident:::t1, int:0
   -debug function SfPexToolsTest:Beta..Describe type 0 lines [36, 36, 36, 36, 36, 36, 36, 36]
   +debug function SfPexToolsTest:Beta..Describe type 0 lines [38, 38, 38, 38, 38, 38, 38, 38]
...
```

Alpha's diff shows the number `100` becoming `250`. Beta differs only in its line-number debug information,
because the added comment moved the lines down. Add `--ignore-debug`, and Beta shows as `same` while Alpha stays
`DIFFERENT` (exit code 1).

What the tools promise:

- They need Python 3.9 or newer and nothing else. (LZ4-compressed archives also need the `lz4` package; see
  [Install](#install).)
- They work on Windows and Linux.
- They only read your files. `extract` writes into the folder you name, and nothing else is written anywhere.

This tool was built with [Claude Code](https://claude.com/claude-code).

## Install

1. Install Python 3.11 or newer from [python.org](https://www.python.org/downloads/). On the first screen of the
   installer, tick **Add python.exe to PATH**. To check that it worked, open a new Command Prompt and type
   `python --version`. It should print a version number. (The tools themselves need only Python 3.9 or newer.)
2. Download `sf-pex-tools-0.1.0.zip` from the [releases page](https://github.com/taosecurity/sf-pex-tools/releases).
   If you want to check the download, run `certutil -hashfile sf-pex-tools-0.1.0.zip SHA256` (on Linux,
   `sha256sum -c sf-pex-tools-0.1.0.zip.sha256`) and compare the result with the `.sha256` file next to it.
3. Unzip it anywhere. Keep `pex_compare.py` and `ba2_extract.py` in the same folder, because `pex_compare.py`
   uses `ba2_extract.py` to read archives.
4. Open the unzipped folder in File Explorer, click the address bar at the top, type `cmd` and press Enter. A
   Command Prompt window opens in that folder, ready for the commands in this README.
5. Run `python pex_compare.py --version`. It should print `pex_compare.py 0.1.0`.
6. Only if you'll read LZ4-compressed archives (the game's texture archives use LZ4; archives made by the
   Creation Kit's Archive2 for scripts use zlib): `python -m pip install lz4==4.4.5`. The tools tell you
   when an archive needs it.

To check the install fully, run the tests: `python -I tests/test_sf_pex_tools.py`. They end with `OK`.

## Words used here

- **Papyrus:** Starfield's scripting language. Scripts are written as `.psc` source files and compiled into `.pex`
  files that the game runs.
- **Compiler:** the program that turns a `.psc` file into a `.pex` file. It comes with the Creation Kit.
- **BA2:** Bethesda's archive format. Mods pack their scripts, models and textures into `.ba2` files.
- **Creation Kit (CK):** Bethesda's official editor for making Starfield mods. Its Archive2 tool packs `.ba2`
  files.
- **Plugin:** a mod's data file (`.esm`, `.esp` or `.esl`). A plugin's archives are named after it, such as
  `MyMod - Main.ba2`.

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

### Did my rebuild change anything?

Compare the archive you tested with the new one:

```
python pex_compare.py compare "old\MyMod - Main.ba2" "new\MyMod - Main.ba2"
```

With the bundled test archives, and `--ignore-debug` to leave out line-number changes:

```
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
```

Either side can be a `.ba2`, a folder (it searches every folder below it) or, for one script, a `.pex` file.
Scripts are matched by their path below `Scripts/`, so a `.ba2` can be compared with your `Data\Scripts` folder or
your build's output folder.

If two files on one side match the same name (say `Scripts\MyMod\X.pex` and a loose `MyMod\X.pex`, or names that
differ only in case), that name is reported as `DUPLICATE` and not compared, and the run ends with exit code 2. The
other scripts are still compared.

Where and by whom a script was built isn't compared: the folder of its source file, and the user and machine names
the compiler can store (Starfield's compiler writes `<SUPPRESSED>`). `dump` shows them on a `# not compared` line.

### Show one script's listing

`dump` prints the text that gets compared:

```
> python pex_compare.py dump tests/fixtures/pex/a1/SfPexToolsTest/Alpha.pex
# not compared: source path 'Alpha.psc', user '<SUPPRESSED>', machine '<SUPPRESSED>'
pex 3.12 game 4
source Alpha.psc
...
object SfPexToolsTest:Alpha extends 'ScriptObject'
  doc ''  const 0  userflags 0x0  autostate ''
  struct Mission
    member Done : Bool  flags 0x0 = bool:False  const 0  doc ''
    member Name : String  flags 0x0 = str:'Survey'  const 0  doc ''
    member Reward : Int  flags 0x0 = int:100  const 0  doc ''
...
```

### List what's in an archive

Add some text after the archive to list only the paths that contain it (not case-sensitive):

```
> python ba2_extract.py list tests/fixtures/a1.ba2 .pex
      1776  scripts/sfpextoolstest/alpha.pex
      1195  scripts/sfpextoolstest/beta.pex
```

The first column is each file's size in bytes. For your own mod, run `python ba2_extract.py list "MyMod - Main.ba2"`.

### Take out one file or a few

```
> python ba2_extract.py extract tests/fixtures/a1.ba2 out alpha
extracted scripts/sfpextoolstest/alpha.pex (1776 bytes)
1 file(s) extracted
```

Files keep their stored paths below `out`. Files that are already there are skipped unless you add `--force`,
which replaces them. A hard link already in the folder is replaced, never written through, and a symbolic link
or junction that points out of the folder is skipped.

### What changed between two versions of an archive?

```
> python ba2_extract.py diff tests/fixtures/a1.ba2 tests/fixtures/b.ba2
new in B: 0
removed (only in A): 0
changed: 2
  scripts/sfpextoolstest/alpha.pex  (1776 -> 1776 bytes)
  scripts/sfpextoolstest/beta.pex  (1195 -> 1195 bytes)
same: 0
```

It lists files that are new, removed and changed, comparing their unpacked content. A file whose size (as the
archive states it) changed is listed as changed without being unpacked, which keeps big archives fast; those lines
say `stated sizes`. A rebuilt script always shows as changed, as both scripts do here, so use `pex_compare.py` on
the archives to see whether its code changed.

### Machine-readable results

`pex_compare.py compare ... --json` prints the result as JSON: each script's status and diff, the counts, and the
exit code.

## Where your files are

You can give an archive as a full path, or as a bare file name, which is looked up in the game's `Data` folder.
`where` shows the Data folders it found:

```
> python ba2_extract.py where
C:\Program Files (x86)\Steam\steamapps\common\Starfield\Data
C:\XboxGames\Starfield\Content\Data
```

Then, for example, `python ba2_extract.py list "Starfield - Interface.ba2" .swf` lists the game's own interface
files. Without `--data`, the tools look in:

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

The tools never write into any of these folders unless you name one as the `extract` output folder. Don't do that:
extract into a folder of your own, so that nothing you take out ends up loaded by the game or your mod manager.

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
| 2 | a script or archive couldn't be read, a `DUPLICATE` name, or bad arguments | an archive couldn't be read (`extract`: some entries couldn't be unpacked and were skipped, the rest were extracted; `diff`: also a name stored twice), or bad arguments |

## Logging

When something goes wrong, run the same command again with `--verbose` (the log goes to the screen, on stderr) or
`--log sf-pex-tools.log` (the log is added to the end of that file). The log records what was read: each archive's
version, type, file count and compression, and each script's PEX version, string count, objects and functions. It
also records what was decided for each file, and the full error if a run stopped. Errors name the file and say what
to do. Attach the log when you report a problem.

## What it reads

- **Scripts:** Fallout 4 (PEX 3.9) and Starfield (PEX 3.12) compiled scripts, including Starfield's guards
  (`LockGuard`, `TryLockGuard`) and `GetAllMatchingStructs`. Skyrim scripts are stored big-endian and aren't supported.
- **Archives:** general (GNRL) and texture (DX10) BA2 archives, versions 1, 2 and 3 (Starfield uses 2 and 3) and
  Fallout 4's 7 and 8; zlib or LZ4. Textures come out as `.dds` files with a DX10 header rebuilt from the
  archive's record. BSA archives from older games aren't supported.

Archives and scripts from other people are read with care:

- Sizes and offsets are checked against the file, unpacking stops at the size the archive states, and a file over
  `--max-size` is refused.
- Stored names that would leave the output folder (`..`, drive letters, `:` streams, Windows device names, links
  inside the output folder that point elsewhere) are skipped, and control characters in names are shown as `\xNN`.
- The game looks names up without regard to the case of A to Z, so names an archive stores twice (ignoring that
  case, and empty or `.` parts such as `a//b` or `./a`) are marked by `list`, skipped by `extract` and stop `diff`.

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

## Found a mistake?

Open an issue: https://github.com/taosecurity/sf-pex-tools/issues. Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Credits and license

sf-pex-tools was made by Richard Bejtlich. It uses only Python's standard library, plus the optional
[lz4](https://pypi.org/project/lz4/) package for LZ4-compressed archives. The PEX and BA2 formats are Bethesda's;
the tools ship no game files.

sf-pex-tools is released under the MIT license (see [LICENSE](LICENSE)).
