# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Richard Bejtlich
"""List, extract and compare the files inside Starfield and Fallout 4 BA2 archives.

Bethesda's Archive2 can only unpack a whole archive. This pulls out just the files you name, and tells you
what changed between two archives.

  python -I ba2_extract.py list    <archive.ba2> [text]            list stored paths that contain the text
  python -I ba2_extract.py extract <archive.ba2> <out dir> [text]  extract the matching files
  python -I ba2_extract.py diff    <a.ba2> <b.ba2> [text]          files that are new, removed or changed
  python -I ba2_extract.py where                                   show the game Data folders it can find

<archive.ba2> is a path, or just a file name ("Starfield - Interface.ba2"), which is looked up in --data or,
without it, in the Steam and Game Pass Data folders that `where` shows.

Options: --data <folder>, --verbose (log to stderr), --log <file> (log to a file), --force (extract over
existing files), --max-size <MB> (largest single file it will unpack; default 1024).
Matching is case-insensitive on the stored path; leaving the text out matches everything.
General (GNRL) and texture (DX10) archives, versions 1, 2, 3, 7 and 8; zlib, or LZ4 when a version-3
archive says so (LZ4 needs `python -m pip install lz4==4.4.5`). Textures come out as .dds files with a
rebuilt DX10 header. diff compares the unpacked content, so the same file stored with different compression
counts as the same.
Exit codes: 0 OK (diff: identical), 1 diff found differences, 2 bad arguments or an unreadable archive.
It only reads archives. It writes only into the output folder you give `extract`.
"""
import argparse
import os
import re
import struct
import sys
import zlib

VERSION = "0.1.0"
DEFAULT_MAX_MB = 1024
LOG = None  # a file object when --verbose or --log is on
_MAX_SIZE = DEFAULT_MAX_MB * 1024 * 1024


def clean(text):
    """Text from archives and scripts can hold control characters (terminal escape codes): show them as \\xNN."""
    return "".join(c if c == "\n" or c.isprintable() else f"\\x{ord(c):02x}" for c in str(text))


def say(text, file=None):
    """Print cleaned text. Characters the console's encoding can't show (a redirected cp1252 stdout on
    Windows) come out as \\uNNNN instead of stopping the run."""
    out = file or sys.stdout
    text = clean(text)
    try:
        print(text, file=out)
    except UnicodeEncodeError:
        enc = getattr(out, "encoding", None) or "ascii"
        print(text.encode(enc, "backslashreplace").decode(enc), file=out)


def log(msg):
    if LOG:
        print(clean(msg), file=LOG, flush=True)


class BA2Error(Exception):
    pass


# ---------------------------------------------------------------- finding the game's Data folder
def _steam_roots():
    roots = []
    if sys.platform == "win32":
        try:
            import winreg
            for hive, key, value in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                     (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        roots.append(winreg.QueryValueEx(k, value)[0])
                except OSError:
                    pass
        except ImportError:
            pass
        roots.append(r"C:\Program Files (x86)\Steam")
    else:
        home = os.path.expanduser("~")
        roots += [os.path.join(home, ".steam", "steam"), os.path.join(home, ".local", "share", "Steam"),
                  os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam")]
    return roots


def _steam_libraries(root):
    libs = [root]
    vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
    try:
        with open(vdf, encoding="utf-8", errors="replace") as f:
            for m in re.finditer(r'"path"\s+"([^"]+)"', f.read()):
                libs.append(m.group(1).replace("\\\\", "\\"))
        log(f"read Steam library list {vdf}")
    except OSError:
        pass
    return libs


def find_data_folders():
    """Starfield Data folders in a Steam library or a Game Pass install, in that order, without repeats."""
    seen, found = set(), []
    for root in _steam_roots():
        for lib in _steam_libraries(os.path.normpath(root)):
            found.append(os.path.join(lib, "steamapps", "common", "Starfield", "Data"))
    if sys.platform == "win32":
        for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            found.append(rf"{drive}:\XboxGames\Starfield\Content\Data")
    out = []
    for d in found:
        key = os.path.normcase(os.path.normpath(d))
        if key in seen:
            continue
        seen.add(key)
        if os.path.isdir(d):
            out.append(d)
            log(f"found Data folder {d}")
    return out


def resolve_archive(arg, data):
    """A path that exists is used as is. A bare file name is looked up in --data, or the Data folders found."""
    if os.path.exists(arg) or os.path.dirname(arg):
        return arg
    places = [data] if data else find_data_folders()
    for d in places:
        p = os.path.join(d, arg)
        if os.path.isfile(p):
            log(f"{arg} found in {d}")
            return p
    where = ", ".join(places) if places else "no Starfield Data folder was found"
    raise BA2Error(f"{arg}: no such file here or in the Data folder ({where}). "
                   f"Give the full path, or name the folder with --data <folder>.")


# ---------------------------------------------------------------- reading
class Archive:
    """An open BA2. entries: dicts with name, size (unpacked), chunks [(offset, packed, size)], dx10 fields."""

    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        try:
            self.length = os.fstat(self.f.fileno()).st_size
            self._read()
        except Exception:
            self.f.close()
            raise

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _need(self, n, what):
        raw = self.f.read(n)
        if len(raw) != n:
            raise BA2Error(f"{self.path}: the file ends inside the {what} (damaged or not a whole BA2)")
        return raw

    def _read(self):
        magic, version, kind, count, names_at = struct.unpack("<4sI4sIQ", self._need(24, "header"))
        if magic != b"BTDX":
            raise BA2Error(f"{self.path}: not a BA2 archive (it starts with {magic!r}, not BTDX)")
        if version not in (1, 2, 3, 7, 8):
            raise BA2Error(f"{self.path}: BA2 version {version} is not supported (1, 2, 3, 7 and 8 are)")
        self.method = 0
        if version in (2, 3):
            self._need(8, "header")
            if version == 3:
                (self.method,) = struct.unpack("<I", self._need(4, "header"))
        self.kind = kind.decode("ascii", "replace")
        record = {b"GNRL": 36, b"DX10": 24}.get(kind)
        if record is None:
            raise BA2Error(f"{self.path}: archive type {self.kind!r} is not supported (GNRL and DX10 are)")
        if count * record > self.length or names_at > self.length:
            raise BA2Error(f"{self.path}: the header says {count} files, more than the file can hold (damaged)")
        log(f"{self.path}: version {version}, type {self.kind}, {count} files, "
            f"compression {'LZ4' if self.method == 3 else 'zlib'}, names at {names_at}")
        self.entries = []
        for _ in range(count):
            if kind == b"GNRL":
                _h, _ext, _d, _fl, off, packed, size, _a = struct.unpack("<I4sIIQIII", self._need(36, "file table"))
                self.entries.append({"chunks": [(off, packed, size)], "size": size, "dx10": False})
            else:
                (_h, _ext, _d, _u, n_chunks, chunk_hdr, height, width, mips, fmt, cube,
                 _tile) = struct.unpack("<I4sIBBHHHBBBB", self._need(24, "texture table"))
                if chunk_hdr < 24:
                    raise BA2Error(f"{self.path}: texture chunk record of {chunk_hdr} bytes (24 expected; damaged)")
                chunks = []
                for _ in range(n_chunks):
                    off, packed, size, _s, _e, _a = struct.unpack_from("<QIIHHI", self._need(chunk_hdr, "texture table"))
                    chunks.append((off, packed, size))
                self.entries.append({"chunks": chunks, "size": 148 + sum(c[2] for c in chunks), "dx10": True,
                                     "w": width, "h": height, "mips": mips, "fmt": fmt, "cube": cube & 1})
        self.f.seek(names_at)
        for e in self.entries:
            (n,) = struct.unpack("<H", self._need(2, "name table"))
            e["name"] = self._need(n, "name table").decode("utf-8", "replace").replace("\\", "/")
        # The game looks names up without regard to case, so two entries whose names differ only in case
        # are ambiguous: list shows them, extract skips them, diff stops.
        seen = set()
        self.duplicates = set()
        for e in self.entries:
            k = e["name"].lower()
            (self.duplicates if k in seen else seen).add(k)
        if self.duplicates:
            log(f"{self.path}: {len(self.duplicates)} name(s) stored more than once (ignoring case)")
        for e in self.entries:
            for off, packed, size in e["chunks"]:
                if off + (packed or size) > self.length:
                    raise BA2Error(f"{self.path}: {e['name']} points past the end of the archive (damaged)")

    def _unpack(self, raw, packed, size, name):
        if not packed:
            return raw
        if self.method == 3:
            try:
                import lz4.block
            except ImportError:
                raise BA2Error(f"{self.path} uses LZ4 compression. Install it with:  "
                               f"python -m pip install lz4==4.4.5")
            try:
                out = lz4.block.decompress(raw, uncompressed_size=size)
            except Exception as e:  # lz4 raises its own LZ4BlockError
                raise BA2Error(f"{self.path}: {name} won't unpack (LZ4: {e}; damaged)")
        else:
            d = zlib.decompressobj()
            try:
                out = d.decompress(raw, size)
            except zlib.error as e:
                raise BA2Error(f"{self.path}: {name} won't unpack (zlib: {e}; damaged)")
            if d.unconsumed_tail:
                raise BA2Error(f"{self.path}: {name} unpacks to more than its stated {size} bytes (damaged)")
        if len(out) != size:
            raise BA2Error(f"{self.path}: {name} unpacked to {len(out)} bytes, not the stated {size} (damaged)")
        return out

    def read(self, e):
        """The file's full unpacked bytes (a texture as a complete .dds)."""
        if e["size"] > _MAX_SIZE:
            raise BA2Error(f"{self.path}: {e['name']} is {e['size'] // 1048576} MB unpacked, over the "
                           f"--max-size limit of {_MAX_SIZE // 1048576} MB. Raise it with --max-size <MB>.")
        parts = [dds_header(e)] if e["dx10"] else []
        for off, packed, size in e["chunks"]:
            self.f.seek(off)
            parts.append(self._unpack(self.f.read(packed or size), packed, size, e["name"]))
        return b"".join(parts)


# DXGI block-compressed formats -> bytes per 4x4 block (BC1/BC4 8, others 16)
_BLOCK = {70: 8, 71: 8, 72: 8, 79: 8, 80: 8, 81: 8, 73: 16, 74: 16, 75: 16, 76: 16, 77: 16, 78: 16,
          82: 16, 83: 16, 84: 16, 94: 16, 95: 16, 96: 16, 97: 16, 98: 16, 99: 16}


def dds_header(e):
    """128-byte DDS header + 20-byte DX10 extension for a texture record."""
    w, h, fmt = e["w"], e["h"], e["fmt"]
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000            # caps, height, width, pixelformat, mipcount
    if fmt in _BLOCK:
        flags |= 0x80000                                  # linear size
        pitch = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * _BLOCK[fmt]
    else:
        flags |= 0x8                                      # pitch (assumes 32 bits per pixel)
        pitch = w * 4
    caps = 0x1000 | 0x8 | 0x400000                        # texture, complex, mipmap
    caps2 = 0xFE00 if e["cube"] else 0                    # cubemap with all six faces
    return (struct.pack("<4sIIIIIII44x", b"DDS ", 124, flags, h, w, pitch, 0, e["mips"])
            + struct.pack("<II4s20x", 32, 0x4, b"DX10")
            + struct.pack("<IIIII", caps, caps2, 0, 0, 0)
            + struct.pack("<IIIII", fmt, 3, 0x4 if e["cube"] else 0, 1, 0))


# ---------------------------------------------------------------- extracting safely
_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}


def safe_target(base, name):
    """Where a stored name goes under base, or None when it would leave base or isn't a plain file name."""
    parts = [p for p in name.split("/") if p]
    if not parts:
        return None
    for p in parts:
        if p in (".", "..") or ":" in p or p.split(".")[0].lower() in _RESERVED or p != p.rstrip(" ."):
            return None
    try:
        path = os.path.realpath(os.path.join(base, *parts))
    except (OSError, ValueError):  # e.g. Windows refuses to follow an untrusted junction (error 448)
        return None
    try:  # commonpath also handles a base that is a drive or filesystem root (D:\ or /)
        inside = path != base and os.path.commonpath([base, path]) == base
    except ValueError:  # different drives
        inside = False
    return path if inside else None


# ---------------------------------------------------------------- commands
def cmd_list(archive, needle):
    with Archive(archive) as a:
        for e in a.entries:
            if needle in e["name"].lower():
                extra = f"  {e['w']}x{e['h']} fmt {e['fmt']}" if e["dx10"] else ""
                if e["name"].lower() in a.duplicates:
                    extra += "  (name stored more than once)"
                say(f"{e['size']:>10}  {e['name']}{extra}")
    return 0


def cmd_extract(archive, out_dir, needle, force):
    base = os.path.realpath(out_dir)
    n = skipped = 0
    with Archive(archive) as a:
        for e in a.entries:
            if needle not in e["name"].lower():
                continue
            if e["name"].lower() in a.duplicates:
                say(f"skipped (the archive stores this name more than once, ignoring case): {e['name']!r}")
                skipped += 1
                continue
            path = safe_target(base, e["name"])
            if path is None:
                say(f"skipped (not a safe file name inside the output folder): {e['name']!r}")
                log(f"refused unsafe path {e['name']!r}")
                skipped += 1
                continue
            data = a.read(e)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                with open(path, "wb" if force else "xb") as out:
                    out.write(data)
            except FileExistsError:
                say(f"skipped (already there; use --force to replace it): {path}")
                skipped += 1
                continue
            log(f"wrote {path} ({len(data)} bytes, {len(e['chunks'])} chunk(s))")
            say(f"extracted {e['name']} ({len(data)} bytes)")
            n += 1
    say(f"{n} file(s) extracted" + (f", {skipped} skipped" if skipped else ""))
    return 0


def _by_name(archive, needle):
    """Matching entries by lower-case name; a name stored twice (ignoring case) stops the run."""
    out = {}
    for e in archive.entries:
        k = e["name"].lower()
        if needle not in k:
            continue
        if k in archive.duplicates:
            raise BA2Error(f"{archive.path}: two stored files have the name {e['name']!r} (ignoring case); "
                           f"the game loads only one of them")
        out[k] = e
    return out


def cmd_diff(a_path, b_path, needle):
    with Archive(a_path) as fa, Archive(b_path) as fb:
        if fa.kind != fb.kind:
            say(f"note: archive types differ ({fa.kind} vs {fb.kind}); texture and general files never match")
        a, b = _by_name(fa, needle), _by_name(fb, needle)
        new = sorted(b[k]["name"] for k in b.keys() - a.keys())
        removed = sorted(a[k]["name"] for k in a.keys() - b.keys())
        changed, same = [], 0
        for k in sorted(a.keys() & b.keys()):
            # Both are always unpacked, even when the stated sizes differ, so damage is still found.
            da, db = fa.read(a[k]), fb.read(b[k])
            is_same = da == db
            if is_same:
                same += 1
            else:
                changed.append(f"{b[k]['name']}  ({len(da)} -> {len(db)} bytes)")
            log(f"compared {k}: {'same' if is_same else 'changed'}")
    for label, items in (("new in B", new), ("removed (only in A)", removed), ("changed", changed)):
        say(f"{label}: {len(items)}")
        for x in items:
            say(f"  {x}")
    say(f"same: {same}")
    return 1 if new or removed or changed else 0


def cmd_where():
    found = find_data_folders()
    for d in found:
        say(d)
    if not found:
        say("No Starfield Data folder found in the usual Steam or Game Pass places. Use --data <folder>.")
    return 0


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # bad arguments: usage and exit code 2 (argparse's default too, made explicit)
        self.print_usage(sys.stderr)
        say(f"error: {message}", file=sys.stderr)
        sys.exit(2)


def open_log(args):
    global LOG
    if args.log:
        LOG = open(args.log, "a", encoding="utf-8")
    elif args.verbose:
        LOG = sys.stderr


def close_log():
    global LOG
    if LOG and LOG is not sys.stderr:
        LOG.close()
    LOG = None


def main(argv=None):
    global _MAX_SIZE
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--verbose", action="store_true", help="log what was read and decided to stderr")
    common.add_argument("--log", metavar="FILE", help="append the same log to FILE")
    common.add_argument("--data", metavar="FOLDER",
                        help="where to look up a bare archive name (default: the Steam and Game Pass Data folders)")
    common.add_argument("--max-size", type=int, default=DEFAULT_MAX_MB, metavar="MB",
                        help=f"largest single file to unpack, in MB (default {DEFAULT_MAX_MB})")
    p = _Parser(prog="ba2_extract.py", description="List, extract and compare files in BA2 archives. "
                "Options go after the command name.",
                epilog="Exit codes: 0 OK (diff: identical), 1 diff found differences, 2 error.")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = p.add_subparsers(dest="cmd", metavar="command", parser_class=_Parser)
    s = sub.add_parser("list", parents=[common], help="list stored paths that contain the text")
    s.add_argument("archive"); s.add_argument("text", nargs="?", default="")
    s = sub.add_parser("extract", parents=[common], help="extract the matching files into a folder")
    s.add_argument("archive"); s.add_argument("out_dir"); s.add_argument("text", nargs="?", default="")
    s.add_argument("--force", action="store_true", help="replace files that are already there")
    s = sub.add_parser("diff", parents=[common], help="files that are new, removed or changed between two archives")
    s.add_argument("a"); s.add_argument("b"); s.add_argument("text", nargs="?", default="")
    sub.add_parser("where", parents=[common], help="show the Starfield Data folders found")
    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 2
    _MAX_SIZE = max(1, args.max_size) * 1024 * 1024
    try:
        open_log(args)
        log(f"ba2_extract {VERSION}: {args.cmd}")
        if args.cmd == "where":
            return cmd_where()
        if args.cmd == "list":
            return cmd_list(resolve_archive(args.archive, args.data), args.text.lower())
        if args.cmd == "extract":
            return cmd_extract(resolve_archive(args.archive, args.data), args.out_dir, args.text.lower(), args.force)
        return cmd_diff(resolve_archive(args.a, args.data), resolve_archive(args.b, args.data), args.text.lower())
    except (BA2Error, OSError) as e:
        say(f"error: {e}", file=sys.stderr)
        log(f"failed: {e!r}")
        return 2
    finally:
        close_log()


if __name__ == "__main__":
    sys.exit(main())
