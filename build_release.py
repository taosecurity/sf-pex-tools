# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Richard Bejtlich
"""Build the release zip and its SHA-256 checksum file.

  python -I build_release.py                 build dist/sf-pex-tools-<version>.zip (+ .sha256)
  python -I build_release.py --tag v0.1.0    the same, but first check that the tag matches both scripts'
                                             VERSION and that CHANGELOG.md has a dated entry for it

Also writes build/release-notes.md (the CHANGELOG entry), used as the GitHub release text.
The zip holds one folder, sf-pex-tools-<version>/, with every committed file except the GitHub workflow and git
settings. It uses fixed file times, the same "made on" system (Unix) for every entry, mode 0644, and no
compression (stored), so the same commit gives the same zip on any system. The files come from the commit
(git show HEAD:<file>), so uncommitted edits never reach a zip. A working tree with changes is refused
(--allow-dirty builds from the files on disk instead, for trying things out). CI builds the zip on Windows and
Linux and checks that the two checksums match.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
LEAVE_OUT = (".github/", ".gitignore", ".gitattributes")
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def git(*args):
    return subprocess.run(["git", "-C", HERE, *args], capture_output=True, check=True).stdout


def shipped_files():
    names = git("ls-files", "-z").decode("utf-8").split("\0")
    return sorted(n for n in names if n and not n.startswith(LEAVE_OUT))


def dirty_files():
    out = git("status", "--porcelain").decode("utf-8", "replace")
    return [line[3:] for line in out.splitlines() if line.strip()]


def script_version(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        m = re.search(r'^VERSION = "([^"]+)"', f.read(), re.M)
    if not m:
        raise SystemExit(f"VERSION not found in {name}")
    return m.group(1)


def changelog_entry(version):
    """(heading, body) of the CHANGELOG entry for this version."""
    with open(os.path.join(HERE, "CHANGELOG.md"), encoding="utf-8") as f:
        text = f.read()
    m = re.search(rf"^## {re.escape(version)}(?=[ \t]|$)([^\n]*)\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        raise SystemExit(f"CHANGELOG.md has no entry for {version}")
    return m.group(1).strip(), m.group(2).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", help="the git tag being released, e.g. v0.1.0")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="build from the files on disk, uncommitted changes included (never for a release)")
    args = ap.parse_args()
    if args.allow_dirty and args.tag:
        raise SystemExit("--allow-dirty can't be used with --tag: a release is built from the commit")
    if not args.allow_dirty:
        dirty = dirty_files()
        if dirty:
            raise SystemExit("these files have uncommitted changes: " + ", ".join(dirty) +
                             ". Commit them first (or use --allow-dirty to try a build).")

    version = script_version("pex_compare.py")
    if script_version("ba2_extract.py") != version:
        raise SystemExit("pex_compare.py and ba2_extract.py have different VERSIONs; make them match")
    heading, notes = changelog_entry(version)
    if args.tag is not None:
        if args.tag != "v" + version:
            raise SystemExit(f"tag {args.tag} doesn't match VERSION {version} (expected v{version})")
        if "not yet released" in heading.lower() or not re.search(r"\d{4}-\d\d-\d\d", heading):
            raise SystemExit(f"CHANGELOG.md entry for {version} needs a release date, e.g. '## {version} (2026-11-20)'")

    dist = os.path.join(HERE, "dist")
    build = os.path.join(HERE, "build")
    os.makedirs(dist, exist_ok=True)
    os.makedirs(build, exist_ok=True)
    top = f"sf-pex-tools-{version}"
    zpath = os.path.join(dist, top + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for rel in shipped_files():
            if args.allow_dirty:
                with open(os.path.join(HERE, rel), "rb") as f:
                    data = f.read()
            else:
                data = git("show", f"HEAD:{rel}")
            info = zipfile.ZipInfo(f"{top}/{rel}", FIXED_TIME)
            info.create_system = 3   # Unix, on every OS (Python sets 0 on Windows, which changes the zip's bytes)
            info.compress_type = zipfile.ZIP_STORED   # no zlib: its output can differ between systems
            info.external_attr = 0o100644 << 16       # a regular file, rw-r--r--
            z.writestr(info, data)
    with open(zpath, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    with open(zpath + ".sha256", "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{digest}  {os.path.basename(zpath)}\n")
    with open(os.path.join(build, "release-notes.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(notes + "\n\n" + f"SHA-256 of `{os.path.basename(zpath)}`: `{digest}`\n")

    print(zpath)
    print(f"SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
