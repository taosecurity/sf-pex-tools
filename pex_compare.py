# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Richard Bejtlich
"""Compare compiled Papyrus scripts (.pex) by meaning, not by bytes.

Two builds of the same Starfield script never match byte for byte: the compiler stores every name in a
string table in a different order each time, and Starfield's PapyrusAssembler.exe also shuffles user flags,
variables, properties, functions and locals on every run. This tool reads each .pex, replaces every
string-table number with the text it stands for, puts the sections whose order means nothing in a fixed
order, and writes a plain listing. Two scripts are equivalent when their listings match.

  python -I pex_compare.py dump    <file.pex>                  print the listing
  python -I pex_compare.py compare <A> <B>                     compare two scripts, or every script in two places

<A> and <B> are two .pex files, or two collections of scripts in any mix: a folder (searched below it) or a
.ba2 archive (read in memory, nothing is extracted). Scripts are matched by their path under "Scripts/".

Options (after the command): --ignore-debug (leave out line-number debug info, which changes when only
comments or blank lines move), --json (compare: machine-readable result), --verbose (log to stderr),
--log <file> (log to a file).

Fallout 4 (PEX 3.9) and Starfield (PEX 3.12) scripts. Skyrim's big-endian PEX is not supported.
Never compared: the compile time, the source file's modification time, the string-table order, and where
and by whom it was built (the source file's folder, the user name and the machine name; `dump` shows them on
a "# not compared" line). Instruction order inside a function is always compared as written.
Two files that match one script name (Scripts/X.pex and X.pex, or names differing only in case) are
reported as DUPLICATE and not compared; the other scripts still are.
Exit codes: 0 all equivalent, 1 differences found, 2 a file could not be read, a DUPLICATE name, or bad
arguments.
It only reads files; it never writes them.
"""
import argparse
import difflib
import importlib.util
import json
import os
import struct
import sys


def _load_ba2():
    """ba2_extract.py from this script's folder (python -I leaves that folder off the import path)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ba2_extract.py")
    spec = importlib.util.spec_from_file_location("ba2_extract", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ba2_extract = _load_ba2()
say = ba2_extract.say
log = ba2_extract.log  # one log for both tools, so archive details reach it too

VERSION = "0.1.0"
IDENT = "ident:"


# opcode: (name, fixed argument count, variadic). Variadic ops are followed by an int count and that many args.
OPCODES = {
    0x00: ("nop", 0, False), 0x01: ("iadd", 3, False), 0x02: ("fadd", 3, False), 0x03: ("isub", 3, False),
    0x04: ("fsub", 3, False), 0x05: ("imul", 3, False), 0x06: ("fmul", 3, False), 0x07: ("idiv", 3, False),
    0x08: ("fdiv", 3, False), 0x09: ("imod", 3, False), 0x0A: ("not", 2, False), 0x0B: ("ineg", 2, False),
    0x0C: ("fneg", 2, False), 0x0D: ("assign", 2, False), 0x0E: ("cast", 2, False), 0x0F: ("cmp_eq", 3, False),
    0x10: ("cmp_lt", 3, False), 0x11: ("cmp_le", 3, False), 0x12: ("cmp_gt", 3, False), 0x13: ("cmp_ge", 3, False),
    0x14: ("jmp", 1, False), 0x15: ("jmpt", 2, False), 0x16: ("jmpf", 2, False), 0x17: ("callmethod", 3, True),
    0x18: ("callparent", 2, True), 0x19: ("callstatic", 3, True), 0x1A: ("return", 1, False),
    0x1B: ("strcat", 3, False), 0x1C: ("propget", 3, False), 0x1D: ("propset", 3, False),
    0x1E: ("array_create", 2, False), 0x1F: ("array_length", 2, False), 0x20: ("array_getelement", 3, False),
    0x21: ("array_setelement", 3, False), 0x22: ("array_findelement", 4, False),
    0x23: ("array_rfindelement", 4, False), 0x24: ("is", 3, False), 0x25: ("struct_create", 1, False),
    0x26: ("struct_get", 3, False), 0x27: ("struct_set", 3, False), 0x28: ("array_findstruct", 5, False),
    0x29: ("array_rfindstruct", 5, False), 0x2A: ("array_add", 3, False), 0x2B: ("array_insert", 3, False),
    0x2C: ("array_removelast", 1, False), 0x2D: ("array_remove", 3, False), 0x2E: ("array_clear", 1, False),
    # Starfield (PEX 3.12) additions
    0x2F: ("array_getallmatchingstructs", 6, False), 0x30: ("lock_guards", 0, True),
    0x31: ("unlock_guards", 0, True), 0x32: ("try_lock_guards", 1, True),
}


class PexError(Exception):
    pass


class Reader:
    def __init__(self, data, name):
        self.b, self.p, self.name = data, 0, name
        self.strings = []
        self.temps = 0

    def need(self, n):
        if self.p + n > len(self.b):
            raise PexError(f"{self.name}: the file ends early at byte {self.p} (wanted {n} more; damaged or cut off)")

    def u8(self):
        self.need(1); v = self.b[self.p]; self.p += 1; return v

    def u16(self):
        self.need(2); v = struct.unpack_from("<H", self.b, self.p)[0]; self.p += 2; return v

    def u32(self):
        self.need(4); v = struct.unpack_from("<I", self.b, self.p)[0]; self.p += 4; return v

    def s32(self):
        self.need(4); v = struct.unpack_from("<i", self.b, self.p)[0]; self.p += 4; return v

    def u64(self):
        self.need(8); v = struct.unpack_from("<Q", self.b, self.p)[0]; self.p += 8; return v

    def f32(self):
        self.need(4); v = struct.unpack_from("<f", self.b, self.p)[0]; self.p += 4; return v

    def wstr(self):
        n = self.u16(); self.need(n)
        s = self.b[self.p:self.p + n].decode("utf-8", "replace"); self.p += n; return s

    def sref(self):
        i = self.u16()
        if i >= len(self.strings):
            raise PexError(f"{self.name}: string number {i} is past the end of the string table at byte {self.p - 2}")
        return self.strings[i]

    def value(self):
        t = self.u8()
        if t == 0:
            return "None"
        if t == 1:
            return "ident:" + self.sref()
        if t == 2:
            return "str:" + repr(self.sref())
        if t == 3:
            return "int:" + str(self.s32())
        if t == 4:
            return "float:" + repr(self.f32())
        if t == 5:
            return "bool:" + ("True" if self.u8() else "False")
        raise PexError(f"{self.name}: unknown value type {t} at byte {self.p - 1}")


def read_function(r, indent):
    """One function as listing lines. Temporary variables (::tempN) are renamed ::t1, ::t2 ... in the order the
    code first uses them, because the compiler numbers them per script in a build-dependent order."""
    head = f"{indent}returns {r.sref()}  doc {r.sref()!r}  userflags {r.u32():#x}  flags {r.u8():#x}"
    params = [f"{indent}param {r.sref()} : {r.sref()}" for _ in range(r.u16())]
    local_list = [(r.sref(), r.sref()) for _ in range(r.u16())]
    code = []
    for _ in range(r.u16()):
        op = r.u8()
        if op not in OPCODES:
            raise PexError(f"{r.name}: unknown opcode {op:#x} at byte {r.p - 1}")
        name, fixed, variadic = OPCODES[op]
        args = [r.value() for _ in range(fixed)]
        if variadic:
            count = r.value()
            if not count.startswith("int:"):
                raise PexError(f"{r.name}: variadic count is {count} at byte {r.p}")
            n = int(count[4:])
            if n < 0:
                raise PexError(f"{r.name}: variadic count {n} is negative at byte {r.p} (damaged)")
            args += [r.value() for _ in range(n)]
        code.append((name, args))
    rename = {}
    for _, args in code:
        for a in args:
            if a.startswith(IDENT + "::temp"):
                temp = a[len(IDENT):]
                if temp not in rename:
                    rename[temp] = f"::t{len(rename) + 1}"
    for lname, _ in sorted(local_list, key=lambda x: (x[1], x[0])):  # temps the code never uses
        if lname.startswith("::temp") and lname not in rename:
            rename[lname] = f"::t{len(rename) + 1}"
    r.temps += len(rename)
    lines = [head] + params
    lines += sorted(f"{indent}local {rename.get(n, n)} : {ty}" for n, ty in local_list)
    for i, (name, args) in enumerate(code):
        args = [IDENT + rename.get(a[len(IDENT):], a[len(IDENT):]) if a.startswith(IDENT) else a for a in args]
        lines.append(f"{indent}{i:4d} {name} " + ", ".join(args))
    return lines


def read_pex_bytes(data, name):
    """(listing lines, debug lines, header info not compared) for one script's bytes.
    On PexError, e.partial holds what was read."""
    out = []
    try:
        return _read_into(data, name, out)
    except PexError as e:
        e.partial = out
        raise


def _read_into(data, name, out):
    """Fills `out` with the listing. Sections whose order has no meaning (user flags, variables, properties,
    functions, locals, debug entries, struct members) are sorted, because the compiler writes them in a
    build-dependent order."""
    r = Reader(data, name)
    magic = r.u32()
    if magic == 0xDEC057FA:
        raise PexError(f"{name}: a Skyrim (big-endian) script, which isn't supported (Fallout 4 and Starfield only)")
    if magic != 0xFA57C0DE:
        raise PexError(f"{name}: not a compiled Papyrus script (it doesn't start with the PEX signature)")
    major, minor, game = r.u8(), r.u8(), r.u16()
    if (major, minor) not in ((3, 9), (3, 12)):
        raise PexError(f"{name}: PEX version {major}.{minor} isn't supported (3.9 Fallout 4, 3.12 Starfield)")
    starfield = (major, minor) >= (3, 12)
    r.u64()  # compile time: never compared
    out.append(f"pex {major}.{minor} game {game}")
    # Where and by whom it was built isn't part of the code: only the source file's name is compared.
    source, user, machine = r.wstr(), r.wstr(), r.wstr()
    out.append(f"source {source.replace(chr(92), '/').rsplit('/', 1)[-1]}")
    info = [f"# not compared: source path {source!r}, user {user!r}, machine {machine!r}"]
    r.strings = [r.wstr() for _ in range(r.u16())]

    debug = []
    if r.u8():
        r.u64()  # source modification time: never compared
        for _ in range(r.u16()):
            obj, state, fn, ftype = r.sref(), r.sref(), r.sref(), r.u8()
            lines = [r.u16() for _ in range(r.u16())]
            debug.append(f"debug function {obj}.{state}.{fn} type {ftype} lines {lines}")
        for _ in range(r.u16()):
            obj, grp, doc, flags = r.sref(), r.sref(), r.sref(), r.u32()
            names = sorted(r.sref() for _ in range(r.u16()))
            debug.append(f"debug propertygroup {obj}.{grp!r} doc {doc!r} flags {flags:#x} {names}")
        for _ in range(r.u16()):
            obj, order = r.sref(), r.sref()
            names = [r.sref() for _ in range(r.u16())]  # declared (source) member order: kept as written
            debug.append(f"debug structorder {obj}.{order} {names}")
    debug.sort()

    out += sorted(f"userflag {r.sref()} = bit {r.u8()}" for _ in range(r.u16()))

    n_objects = n_functions = 0
    for _ in range(r.u16()):
        n_objects += 1
        oname = r.sref()
        size = r.u32()
        start = r.p
        out.append(f"object {oname} extends {r.sref()!r}")
        out.append(f"  doc {r.sref()!r}  const {r.u8()}  userflags {r.u32():#x}  autostate {r.sref()!r}")
        structs = []
        for _ in range(r.u16()):
            block = [f"  struct {r.sref()}"]
            for _ in range(r.u16()):
                mname, mtype, mflags = r.sref(), r.sref(), r.u32()
                mval, mconst, mdoc = r.value(), r.u8(), r.sref()
                block.append(f"    member {mname} : {mtype}  flags {mflags:#x} = {mval}  const {mconst}  doc {mdoc!r}")
            # Struct members are used by name, and their table order changes between builds of the same
            # source; the declared order is compared through the "debug structorder" line instead.
            structs.append(block[:1] + sorted(block[1:]))
        variables = []
        for _ in range(r.u16()):
            vname, vtype, vflags = r.sref(), r.sref(), r.u32()
            vval, vconst = r.value(), r.u8()
            variables.append(f"  variable {vname} : {vtype}  flags {vflags:#x} = {vval}  const {vconst}")
        guards = [f"  guard {r.sref()}" for _ in range(r.u16())] if starfield else []
        properties = []
        for _ in range(r.u16()):
            pname, ptype, pdoc, pflags, pfl = r.sref(), r.sref(), r.sref(), r.u32(), r.u8()
            block = [f"  property {pname} : {ptype}  doc {pdoc!r}  userflags {pflags:#x}  flags {pfl:#x}"]
            if pfl & 4:
                block.append(f"    autovar {r.sref()}")
            else:
                if pfl & 1:
                    block += ["    get"] + read_function(r, "      ")
                    n_functions += 1
                if pfl & 2:
                    block += ["    set"] + read_function(r, "      ")
                    n_functions += 1
            properties.append(block)
        states = []
        for _ in range(r.u16()):
            block = [f"  state {r.sref()!r}"]
            funcs = []
            for _ in range(r.u16()):
                funcs.append([f"    function {r.sref()}"] + read_function(r, "      "))
                n_functions += 1
            for f in sorted(funcs):
                block += f
            states.append(block)
        for block in sorted(structs):
            out += block
        out += sorted(variables) + sorted(guards)
        for block in sorted(properties) + sorted(states):
            out += block
        if r.p - start != size - 4 and r.p - start != size:
            raise PexError(f"{name}: object {oname} read {r.p - start} bytes but its size field says {size}")
    if r.p != len(data):
        raise PexError(f"{name}: {len(data) - r.p} unread bytes at the end (a format this tool doesn't understand)")
    log(f"read {name}: pex {major}.{minor} game {game}, {len(r.strings)} strings, {n_objects} object(s), "
        f"{n_functions} function(s), {len(debug)} debug entries, {r.temps} temporary variable(s) renamed")
    return out, debug, info


def listing(data, name, ignore_debug, with_info=False):
    out, debug, info = read_pex_bytes(data, name)
    return (info if with_info else []) + out + ([] if ignore_debug else debug)


# ---------------------------------------------------------------- where the scripts come from
def _key(rel):
    """Match key: the path in lower case with / separators and any leading 'scripts/' removed."""
    return _shown(rel).lower()


def _shown(rel):
    """The same path as shown in results: original spelling, / separators, no leading 'scripts/'."""
    k = rel.replace("\\", "/").lstrip("/")
    return k[8:] if k.lower().startswith("scripts/") else k


class Source:
    """A .pex file, a folder of them, or a .ba2 archive. scripts: key -> (label, loader returning bytes)."""

    def __init__(self, path):
        self.path, self.archive, self.single = path, None, False
        self.scripts = {}
        self.duplicates = {}  # key -> labels of every file matching that script name
        if os.path.isfile(path) and path.lower().endswith(".ba2"):
            self.archive = ba2_extract.Archive(path)
            try:
                for e in self.archive.entries:
                    if e["name"].lower().endswith(".pex"):
                        self._add(_key(e["name"]), f"{path}:{e['name']}", lambda e=e: self.archive.read(e),
                                  _shown(e["name"]))
            except BaseException:
                self.archive.close()
                raise
            log(f"{path}: archive with {len(self.scripts)} script(s) out of {len(self.archive.entries)} files")
        elif os.path.isfile(path):
            self.single = True
            self._add(_key(os.path.basename(path)), path, lambda: _read_file(path), os.path.basename(path))
        elif os.path.isdir(path):
            for root, dirs, names in os.walk(path):
                dirs.sort()
                for n in sorted(names):
                    if n.lower().endswith(".pex"):
                        full = os.path.join(root, n)
                        rel = os.path.relpath(full, path)
                        self._add(_key(rel), full, lambda full=full: _read_file(full), _shown(rel))
            log(f"{path}: folder with {len(self.scripts)} script(s)")
        else:
            raise OSError(f"{path}: no such file or folder")

    def _add(self, key, label, loader, shown):
        """Two scripts that match the same name (Scripts/X.pex and X.pex, or names differing only in case)
        would hide one another, so that name is reported as a duplicate instead of compared."""
        if key in self.scripts:
            self.duplicates.setdefault(key, [self.scripts[key][0]]).append(label)
            return
        self.scripts[key] = (label, loader, shown)

    def close(self):
        if self.archive:
            self.archive.close()


def _read_file(path):
    with open(path, "rb") as f:
        return f.read()


def compare(a_path, b_path, ignore_debug, as_json):
    a = Source(a_path)
    try:
        b = Source(b_path)
    except BaseException:
        a.close()
        raise
    try:
        if a.single != b.single:
            raise ValueError("compare one file with one file, or a folder or .ba2 with a folder or .ba2 "
                             "(to check one script from an archive, extract it first with ba2_extract.py)")
        if a.single:
            fa, fb = {"script": list(a.scripts.values())[0]}, {"script": list(b.scripts.values())[0]}
        else:
            fa, fb = a.scripts, b.scripts
        if not fa and not fb:
            raise ValueError(f"no .pex files found in {a_path} or {b_path}")
        results, status = [], 0
        for key in sorted(set(fa) | set(fb)):
            shown = (fa.get(key) or fb.get(key))[2]
            dups = a.duplicates.get(key, []) + b.duplicates.get(key, [])
            if dups:
                results.append({"script": shown, "status": "duplicate",
                                "error": "more than one file matches this name: " + ", ".join(dups)})
                log(f"duplicate {shown}: {dups}")
                status = 2
                continue
            if key not in fa or key not in fb:
                results.append({"script": shown, "status": "only-in-second" if key not in fa else "only-in-first"})
                status = max(status, 1)
                continue
            try:
                la = listing(fa[key][1](), fa[key][0], ignore_debug)
                lb = listing(fb[key][1](), fb[key][0], ignore_debug)
            except (PexError, ba2_extract.BA2Error, OSError) as e:
                results.append({"script": shown, "status": "unreadable", "error": str(e)})
                log(f"unreadable {shown}: {e!r}")
                status = 2
                continue
            if la == lb:
                results.append({"script": shown, "status": "same"})
            else:
                status = max(status, 1)
                diff = list(difflib.unified_diff(la, lb, "first", "second", lineterm="", n=2))
                results.append({"script": shown, "status": "different", "diff": diff})
            log(f"compared {shown}: {results[-1]['status']}")
    finally:
        a.close()
        b.close()
    if as_json:
        counts = {}
        for r in results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        print(json.dumps({"tool": "sf-pex-tools pex_compare", "version": VERSION, "first": a_path,
                          "second": b_path, "ignore_debug": ignore_debug, "exit_code": status,
                          "counts": counts, "scripts": results}, indent=2))
    else:
        labels = {"same": "same", "different": "DIFFERENT", "only-in-first": "ONLY IN first",
                  "only-in-second": "ONLY IN second", "unreadable": "UNREADABLE", "duplicate": "DUPLICATE"}
        for r in results:
            say(f"{labels[r['status']]}: {r['script']}" + (f"  ({r['error']})" if "error" in r else ""))
            for line in r.get("diff", []):
                say("   " + line)
    return status


_Parser = ba2_extract._Parser


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--ignore-debug", action="store_true",
                        help="leave out line-number debug info (it changes when only comments or blank lines move)")
    common.add_argument("--verbose", action="store_true", help="log what was read and decided to stderr")
    common.add_argument("--log", metavar="FILE", help="append the same log to FILE")
    p = _Parser(prog="pex_compare.py", description="Compare compiled Papyrus scripts by meaning, not by bytes. "
                "Options go after the command name.",
                epilog="Exit codes: 0 all equivalent, 1 differences found, 2 unreadable file, DUPLICATE name or bad arguments.")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = p.add_subparsers(dest="cmd", metavar="command", parser_class=_Parser)
    s = sub.add_parser("dump", parents=[common], help="print one script's listing")
    s.add_argument("file")
    s = sub.add_parser("compare", parents=[common], help="compare two scripts, folders or .ba2 archives")
    s.add_argument("a"); s.add_argument("b")
    s.add_argument("--json", action="store_true", help="print the result as JSON")
    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 2
    try:
        ba2_extract.open_log(args)
        log(f"pex_compare {VERSION}: {args.cmd}")
        if args.cmd == "dump":
            try:
                say("\n".join(listing(_read_file(args.file), args.file, args.ignore_debug, with_info=True)))
                return 0
            except PexError as e:
                say("\n".join(getattr(e, "partial", [])[-40:]))
                say(f"UNREADABLE: {e}")
                log(f"failed: {e!r}")
                return 2
        return compare(args.a, args.b, args.ignore_debug, args.json)
    except (OSError, ValueError, ba2_extract.BA2Error) as e:
        say(f"error: {e}", file=sys.stderr)
        log(f"failed: {e!r}")
        return 2
    finally:
        ba2_extract.close_log()


if __name__ == "__main__":
    sys.exit(main())
