# AGENTS.md: sf-pex-tools for AI assistants

Plain steps for an AI assistant helping someone use sf-pex-tools. Every command here was run once on
sf-pex-tools 0.1.0 before release. The [README](README.md) has the full description.

## 1. What it is for

Two command-line scripts for Starfield and Fallout 4 mod authors:

- `pex_compare.py` compares compiled Papyrus scripts (`.pex`) by meaning. Two builds of the same source never
  match byte for byte (the compiler reorders its output on every run), so a checksum or byte compare is useless.
  It reads scripts from `.pex` files, folders or `.ba2` archives.
- `ba2_extract.py` lists, extracts and compares the files inside `.ba2` archives.

Use them to check whether a rebuilt mod's scripts changed, to pull one file out of an archive, or to see what
changed between two versions of a mod's archive. Don't use them to decompile scripts (use a decompiler such as
Champollion) or to pack archives (use the Creation Kit's Archive2).

## 2. Prerequisites

- Python 3.9 or newer (tested on 3.9, 3.10 and 3.13). Standard library only.
- Optional: `lz4==4.4.5`, only for LZ4-compressed archives (the game's texture archives). The tools say when an
  archive needs it.
- Windows or Linux.

## 3. Install

Download `sf-pex-tools-0.1.0.zip` from https://github.com/taosecurity/sf-pex-tools/releases and check it against
the `.sha256` file:

    certutil -hashfile sf-pex-tools-0.1.0.zip SHA256

On Linux: `sha256sum -c sf-pex-tools-0.1.0.zip.sha256`. Unpack it anywhere, and keep `pex_compare.py` and
`ba2_extract.py` in the same folder. For LZ4 archives only:

    python -m pip install lz4==4.4.5

## 4. Prove the install works

From the unpacked folder:

    python -I pex_compare.py compare tests/fixtures/pex/a1 tests/fixtures/pex/a2

It prints `same: SfPexToolsTest/Alpha.pex` and `same: SfPexToolsTest/Beta.pex` and exits with code 0. The full
test suite is `python -I tests/test_sf_pex_tools.py` (it ends with `OK`; one test is skipped, depending on
whether lz4 is installed).

## 5. Common tasks

- Compare the scripts in two builds of a mod (archives, folders, or one of each):

      python -I pex_compare.py compare "old/MyMod - Main.ba2" "new/MyMod - Main.ba2"

- The same, ignoring line-number changes from moved comments or blank lines:

      python -I pex_compare.py compare "old/MyMod - Main.ba2" "new/MyMod - Main.ba2" --ignore-debug

- The same, as JSON for a script to read:

      python -I pex_compare.py compare tests/fixtures/a1.ba2 tests/fixtures/b.ba2 --json

- Show one script's listing (what gets compared):

      python -I pex_compare.py dump tests/fixtures/pex/a1/SfPexToolsTest/Alpha.pex

- List an archive's files, optionally only paths that contain some text:

      python -I ba2_extract.py list tests/fixtures/a1.ba2 .pex

- Extract matching files into a folder (existing files are skipped unless `--force` is given):

      python -I ba2_extract.py extract tests/fixtures/a1.ba2 out alpha

- What changed between two archives:

      python -I ba2_extract.py diff tests/fixtures/a1.ba2 tests/fixtures/b.ba2

- Find the game's Data folders, and open a game archive by bare name:

      python -I ba2_extract.py where
      python -I ba2_extract.py list "Starfield - Interface.ba2" .swf

  Use `--data <folder>` for an archive somewhere else, for example a Mod Organizer 2 mod folder
  (`<instance>/mods/<mod>/`) or the Vortex staging folder (`%APPDATA%/Vortex/starfield/mods/<mod>/`).

- Troubleshoot: add `--verbose` (log on stderr) or `--log sf-pex-tools.log` (append the log to a file) after the
  command name.

## 6. Inputs, outputs, exit codes, log

- **Input:** `.pex` files, folders (searched below them) and `.ba2` archives (read in memory). An archive can be
  given by bare name, which is looked up in `--data` or in the Steam and Game Pass Data folders.
- **Output:** stdout. `compare` prints one line per script (`same`, `DIFFERENT` with a diff, `ONLY IN first`,
  `ONLY IN second`, `UNREADABLE`, `DUPLICATE` when two files on one side match one name), or JSON with
  `--json`. `extract` writes the files to the output folder you name and prints one line per file
  (`extracted ...` or `skipped (...)` with the reason: already there, unsafe name, name stored twice, or a
  file/folder clash). Without `--force` it never replaces a file; with `--force` it swaps in a new file, so a
  hard link is replaced, never written through. `diff` prints counts and names of new, removed and changed
  files; a file whose stated size changed is listed with `stated sizes` and is not unpacked. Errors go to
  stderr, starting `error:`, and name the file and the fix.
- **Exit codes:** `pex_compare.py`: 0 all equivalent, 1 differences, 2 unreadable, a `DUPLICATE` name, or bad
  arguments.
  `ba2_extract.py`: 0 OK (`diff`: identical), 1 `diff` found differences, 2 unreadable archive (`diff`: also a
  name stored twice, or damage in a file whose size didn't change), or bad arguments. A `diff` line with
  `stated sizes` doesn't prove the file unpacks; use `extract` or `pex_compare.py compare` to check that.
- **Log:** only when asked: `--verbose` to stderr, or `--log FILE`, which adds to the end of FILE.

## 7. Limits

- It never changes the scripts or archives it reads, and never writes into the game folder unless that folder is
  given as the `extract` output folder. Don't do that.
- It makes no network connections and uploads nothing.
- Skyrim (big-endian) scripts and BSA archives aren't supported.
- `compare` takes two files, or two collections (folders or archives). To check one script from an archive,
  extract it first.
- The game's own scripts and archives belong to Bethesda. Never put extracted game files in a repository, a
  release or a message.
