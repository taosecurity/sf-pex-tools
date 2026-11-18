# Privacy

sf-pex-tools runs on your own computer, offline. It collects no data and sends nothing anywhere.

## What it does not do

- It makes no network connections.
- It has no telemetry, analytics, crash reporting or update checks.
- It starts no other programs. (The maintainers' fixture builder, `tests/fixtures/make_fixtures.py`, runs the
  Creation Kit's compiler and Archive2. It isn't part of the tools, and the tests don't run it.)

## What it reads

- the scripts, folders and archives you name on the command line;
- to find the game's Data folder when you give an archive by bare name without `--data`: Steam's location from the
  Windows registry (`SteamPath`, `InstallPath`), Steam's `libraryfolders.vdf`, and whether
  `<drive>:\XboxGames\Starfield\Content\Data` exists on each drive.

## What it writes

- `extract` writes the files you ask for into the output folder you name.
- `--log <file>` adds a troubleshooting log to the end of that file.

Nothing else.

## What the output contains

The output shows the paths of the files you named, the paths stored in archives, and the names and text in the
scripts. A log also shows the Data folders it found, which include your Steam library paths. Read a log before you
post it.

## Downloading it

Downloading sf-pex-tools from GitHub is covered by GitHub's own
[privacy statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement). Its
author receives only the public download counts GitHub shows.

## Questions

Open an issue at https://github.com/taosecurity/sf-pex-tools/issues.
