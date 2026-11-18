# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Richard Bejtlich
"""Tests for pex_compare.py and ba2_extract.py. Standard library only (LZ4 tests skip when lz4 isn't installed).

  python -I tests/test_sf_pex_tools.py -v

The fixtures are our own test scripts (tests/fixtures/src), compiled with the Creation Kit compiler and packed
with Archive2 (tests/fixtures/make_fixtures.py). Nothing from the game is in them.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
FIX = os.path.join(TESTS, "fixtures")
PEX = os.path.join(FIX, "pex")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pc = load("pex_compare", os.path.join(ROOT, "pex_compare.py"))
bx = pc.ba2_extract
writer = load("ba2_writer", os.path.join(TESTS, "ba2_writer.py"))

try:
    import lz4.block  # noqa: F401
    HAVE_LZ4 = True
except ImportError:
    HAVE_LZ4 = False


def run(main, *args):
    """(exit code, stdout, stderr) of a tool's main()."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(args))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


def fixture_pex(set_name, script):
    return os.path.join(PEX, set_name, "SfPexToolsTest", f"{script}.pex")


def read(path):
    with open(path, "rb") as f:
        return f.read()


class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sfpextest-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, data):
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path


class PexCompare(Temp):
    def test_rebuild_of_same_source_is_same_though_bytes_differ(self):
        self.assertNotEqual(read(fixture_pex("a1", "Alpha")), read(fixture_pex("a2", "Alpha")))
        code, out, _ = run(pc.main, "compare", os.path.join(PEX, "a1"), os.path.join(PEX, "a2"))
        self.assertEqual(code, 0, out)
        self.assertIn("same: SfPexToolsTest/Alpha.pex", out)
        self.assertIn("same: SfPexToolsTest/Beta.pex", out)

    def test_changed_constant_is_reported(self):
        code, out, _ = run(pc.main, "compare", os.path.join(PEX, "a1"), os.path.join(PEX, "b"))
        self.assertEqual(code, 1)
        self.assertIn("DIFFERENT: SfPexToolsTest/Alpha.pex", out)
        self.assertIn("+         0 array_getallmatchingstructs ident:Missions, ident:::t1, str:'Reward', int:250", out)

    def test_temporaries_renumbered_by_the_compiler_still_match(self):
        """Swap two ::tempN names in the string table, as another build may number them, for every pair:
        the listing must not change. (Before the 0.1.0 review fix, 71 of Alpha's 100 swaps gave DIFFERENT.)"""
        for script in ("Alpha", "Beta"):
            data = read(fixture_pex("a1", script))
            base = pc.listing(data, "a", False)
            swaps = 0
            for i in range(21):
                for j in range(i + 1, 21):
                    a, b = b"::temp%d" % i, b"::temp%d" % j
                    pa, pb = bytes([len(a), 0]) + a, bytes([len(b), 0]) + b  # length-prefixed table entries
                    if len(a) != len(b) or pa not in data or pb not in data:
                        continue
                    swapped = data.replace(pa, b"\0\0@@").replace(pb, pa).replace(b"\0\0@@", pb)
                    with self.subTest(script=script, swap=(i, j)):
                        self.assertEqual(pc.listing(swapped, "b", False), base)
                    swaps += 1
            self.assertGreater(swaps, 40)

    def test_build_place_user_and_machine_are_not_compared(self):
        data = read(fixture_pex("a1", "Alpha"))
        other = data.replace(b"\x0c\x00<SUPPRESSED>", b"\x0c\x00amy-on-pc-02", 1)
        self.assertNotEqual(data, other)
        self.assertEqual(pc.listing(data, "a", False), pc.listing(other, "b", False))
        path = self.write("other.pex", other)
        code, out, _ = run(pc.main, "dump", path)
        self.assertIn("# not compared: source path 'Alpha.psc', user 'amy-on-pc-02'", out)

    def test_two_files_matching_one_name_are_reported_not_compared(self):
        d = os.path.join(self.tmp, "dup")
        os.makedirs(os.path.join(d, "Scripts", "SfPexToolsTest"))
        os.makedirs(os.path.join(d, "SfPexToolsTest"))
        shutil.copy(fixture_pex("a1", "Alpha"), os.path.join(d, "SfPexToolsTest", "Alpha.pex"))
        shutil.copy(fixture_pex("a2", "Alpha"), os.path.join(d, "Scripts", "SfPexToolsTest", "Alpha.pex"))
        shutil.copy(fixture_pex("a2", "Beta"), os.path.join(d, "SfPexToolsTest", "Beta.pex"))
        code, out, _ = run(pc.main, "compare", d, os.path.join(PEX, "a1"))
        self.assertEqual(code, 2)
        self.assertIn("DUPLICATE: ", out)
        self.assertIn("more than one file matches this name", out)
        self.assertIn("same: SfPexToolsTest/Beta.pex", out)
        code, out, _ = run(pc.main, "compare", d, os.path.join(PEX, "a1"), "--json")
        self.assertEqual(json.loads(out)["counts"], {"duplicate": 1, "same": 1})

    def test_archive_details_reach_the_compare_log(self):
        logf = os.path.join(self.tmp, "c.log")
        run(pc.main, "compare", os.path.join(FIX, "a1.ba2"), os.path.join(PEX, "a2"), "--log", logf)
        with open(logf, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("type GNRL, 2 files, compression zlib", text)
        self.assertIsNone(bx.LOG)

    def test_comment_only_change_needs_ignore_debug(self):
        code, out, _ = run(pc.main, "compare", fixture_pex("a1", "Beta"), fixture_pex("b", "Beta"))
        self.assertEqual(code, 1)
        self.assertIn("debug function", out)
        code, out, _ = run(pc.main, "compare", fixture_pex("a1", "Beta"), fixture_pex("b", "Beta"), "--ignore-debug")
        self.assertEqual(code, 0, out)

    def test_dump_shows_starfield_features(self):
        code, out, _ = run(pc.main, "dump", fixture_pex("a1", "Alpha"))
        self.assertEqual(code, 0)
        for text in ("pex 3.12 game 4", "struct Mission", "guard CountGuard", "lock_guards ident:CountGuard",
                     "try_lock_guards", "array_getallmatchingstructs",
                     "debug structorder SfPexToolsTest:Alpha.Mission ['Name', 'Reward', 'Weight', 'Done']"):
            self.assertIn(text, out)

    def test_dump_of_state_and_property_groups(self):
        code, out, _ = run(pc.main, "dump", fixture_pex("a1", "Beta"))
        self.assertEqual(code, 0)
        self.assertIn("state 'full'", out.lower())
        self.assertIn("debug propertygroup SfPexToolsTest:Beta.'Settings'", out)

    def test_cut_off_file_is_unreadable(self):
        path = self.write("cut.pex", read(fixture_pex("a1", "Alpha"))[:900])
        code, out, _ = run(pc.main, "dump", path)
        self.assertEqual(code, 2)
        self.assertIn("UNREADABLE", out)
        self.assertIn("ends early", out)

    def test_not_a_pex_and_skyrim(self):
        code, out, _ = run(pc.main, "dump", self.write("x.pex", b"hello world, not a script"))
        self.assertEqual(code, 2)
        self.assertIn("not a compiled Papyrus script", out)
        code, out, _ = run(pc.main, "dump", self.write("s.pex", bytes.fromhex("FA57C0DE") + b"\0" * 20))
        self.assertEqual(code, 2)
        self.assertIn("Skyrim", out)

    def test_unreadable_script_inside_compare(self):
        d1 = os.path.join(self.tmp, "one")
        d2 = os.path.join(self.tmp, "two")
        shutil.copytree(os.path.join(PEX, "a1"), d1)
        shutil.copytree(os.path.join(PEX, "a2"), d2)
        with open(os.path.join(d2, "SfPexToolsTest", "Beta.pex"), "r+b") as f:
            f.truncate(100)
        code, out, _ = run(pc.main, "compare", d1, d2)
        self.assertEqual(code, 2)
        self.assertIn("same: SfPexToolsTest/Alpha.pex", out)
        self.assertIn("UNREADABLE: SfPexToolsTest/Beta.pex", out)

    def test_only_in_one_side(self):
        d = os.path.join(self.tmp, "partial", "SfPexToolsTest")
        os.makedirs(d)
        shutil.copy(fixture_pex("a2", "Alpha"), d)
        code, out, _ = run(pc.main, "compare", os.path.join(PEX, "a1"), os.path.join(self.tmp, "partial"))
        self.assertEqual(code, 1)
        self.assertIn("ONLY IN first: SfPexToolsTest/Beta.pex", out)

    def test_file_against_folder_is_refused(self):
        code, _, err = run(pc.main, "compare", fixture_pex("a1", "Alpha"), os.path.join(PEX, "a2"))
        self.assertEqual(code, 2)
        self.assertIn("extract it first", err)

    def test_empty_folders_are_not_a_pass(self):
        os.makedirs(os.path.join(self.tmp, "e1"))
        os.makedirs(os.path.join(self.tmp, "e2"))
        code, _, err = run(pc.main, "compare", os.path.join(self.tmp, "e1"), os.path.join(self.tmp, "e2"))
        self.assertEqual(code, 2)
        self.assertIn("no .pex files", err)

    def test_missing_path(self):
        code, _, err = run(pc.main, "compare", os.path.join(self.tmp, "nope"), os.path.join(PEX, "a1"))
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_ba2_against_ba2_and_folder(self):
        code, out, _ = run(pc.main, "compare", os.path.join(FIX, "a1.ba2"), os.path.join(FIX, "b.ba2"),
                           "--ignore-debug")
        self.assertEqual(code, 1)
        self.assertIn("different: sfpextoolstest/alpha.pex", out.lower())  # Archive2 stores names in lower case
        self.assertIn("same: sfpextoolstest/beta.pex", out.lower())
        code, out, _ = run(pc.main, "compare", os.path.join(FIX, "a1.ba2"), os.path.join(PEX, "a2"))
        self.assertEqual(code, 0, out)

    @unittest.skipUnless(HAVE_LZ4, "lz4 not installed")
    def test_lz4_archive_against_folder(self):
        files = [(f"Scripts\\SfPexToolsTest\\{s}.pex", read(fixture_pex("a2", s))) for s in ("Alpha", "Beta")]
        ba2 = self.write("lz4.ba2", writer.gnrl(files, version=3, method="lz4"))
        code, out, _ = run(pc.main, "compare", ba2, os.path.join(PEX, "a1"))
        self.assertEqual(code, 0, out)

    def test_json_output(self):
        code, out, _ = run(pc.main, "compare", os.path.join(PEX, "a1"), os.path.join(PEX, "b"), "--json")
        self.assertEqual(code, 1)
        doc = json.loads(out)
        self.assertEqual(doc["exit_code"], 1)
        self.assertEqual(doc["counts"], {"different": 2})
        self.assertEqual({s["script"] for s in doc["scripts"]}, {"SfPexToolsTest/Alpha.pex", "SfPexToolsTest/Beta.pex"})

    def test_log_file(self):
        logf = os.path.join(self.tmp, "run.log")
        code, _, _ = run(pc.main, "compare", os.path.join(PEX, "a1"), os.path.join(PEX, "a2"), "--log", logf)
        self.assertEqual(code, 0)
        with open(logf, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("pex 3.12 game 4", text)
        self.assertIn("compared SfPexToolsTest/Alpha.pex: same", text)

    def test_bad_arguments(self):
        self.assertEqual(run(pc.main)[0], 2)
        self.assertEqual(run(pc.main, "compare", "only-one")[0], 2)
        self.assertEqual(run(pc.main, "--version")[0], 0)


class Ba2Extract(Temp):
    def test_list_fixture(self):
        code, out, _ = run(bx.main, "list", os.path.join(FIX, "a1.ba2"))
        self.assertEqual(code, 0)
        self.assertIn("scripts/sfpextoolstest/alpha.pex", out.lower())
        code, out, _ = run(bx.main, "list", os.path.join(FIX, "a1.ba2"), "BETA")
        self.assertNotIn("alpha", out.lower())

    def test_extract_matches_the_packed_scripts_and_refuses_overwrite(self):
        out_dir = os.path.join(self.tmp, "out")
        code, out, _ = run(bx.main, "extract", os.path.join(FIX, "a1.ba2"), out_dir)
        self.assertEqual(code, 0, out)
        self.assertIn("2 file(s) extracted", out)
        found = {}
        for root, _, names in os.walk(out_dir):
            for n in names:
                found[n.lower()] = read(os.path.join(root, n))
        self.assertEqual(found["alpha.pex"], read(fixture_pex("a1", "Alpha")))
        self.assertEqual(found["beta.pex"], read(fixture_pex("a1", "Beta")))
        code, out, _ = run(bx.main, "extract", os.path.join(FIX, "a1.ba2"), out_dir)
        self.assertIn("use --force", out)
        self.assertIn("0 file(s) extracted, 2 skipped", out)
        code, out, _ = run(bx.main, "extract", os.path.join(FIX, "a1.ba2"), out_dir, "--force")
        self.assertIn("2 file(s) extracted", out)

    def test_diff(self):
        a1, b = os.path.join(FIX, "a1.ba2"), os.path.join(FIX, "b.ba2")
        self.assertEqual(run(bx.main, "diff", a1, a1)[0], 0)
        code, out, _ = run(bx.main, "diff", a1, b)
        self.assertEqual(code, 1)
        self.assertIn("changed: 2", out)

    def test_written_kinds_read_back(self):
        files = [("Scripts/a.pex", b"A" * 300), ("Scripts/sub/b.txt", b"hello " * 50)]
        kinds = [(1, "zlib"), (2, "zlib"), (2, "stored"), (8, "zlib")] + ([(3, "lz4")] if HAVE_LZ4 else [])
        for version, method in kinds:
            with self.subTest(version=version, method=method):
                path = self.write(f"k{version}{method}.ba2", writer.gnrl(files, version=version, method=method))
                with bx.Archive(path) as a:
                    self.assertEqual([a.read(e) for e in a.entries], [f[1] for f in files])

    def test_lz4_without_package_names_the_fix(self):
        path = self.write("l.ba2", writer.gnrl([("x.txt", b"x")], version=3, method="stored"))
        with open(path, "r+b") as f:  # say LZ4 and mark the entry packed, so the reader needs lz4
            f.seek(32); f.write((3).to_bytes(4, "little"))
        if HAVE_LZ4:
            self.skipTest("lz4 is installed")
        with bx.Archive(path) as a:
            a.entries[0]["chunks"] = [(a.entries[0]["chunks"][0][0], 1, 1)]
            with self.assertRaisesRegex(bx.BA2Error, "lz4==4.4.5"):
                a.read(a.entries[0])

    def test_texture_gets_dds_header(self):
        path = self.write("t.ba2", writer.dx10("Textures/test.dds", 4, 4, 71, [b"\x11" * 8]))
        out_dir = os.path.join(self.tmp, "tex")
        code, out, _ = run(bx.main, "extract", path, out_dir)
        self.assertEqual(code, 0, out)
        data = read(os.path.join(out_dir, "Textures", "test.dds"))
        self.assertEqual(len(data), 148 + 8)
        self.assertEqual(data[:4], b"DDS ")
        self.assertEqual(data[84:88], b"DX10")

    def test_unsafe_names_are_skipped(self):
        bad = ["../evil.txt", "a/../../evil2.txt", "C:/evil3.txt", "sub/con.txt", "x.txt:stream", "trail. "]
        files = [(n, b"bad") for n in bad] + [("ok/good.txt", b"good")]
        path = self.write("bad.ba2", writer.gnrl(files))
        out_dir = os.path.join(self.tmp, "x", "out")
        code, out, _ = run(bx.main, "extract", path, out_dir)
        self.assertEqual(code, 0)
        self.assertIn("1 file(s) extracted, 6 skipped", out)
        written = [os.path.relpath(os.path.join(r, n), self.tmp) for r, _, ns in os.walk(self.tmp) for n in ns]
        self.assertEqual(sorted(w.replace("\\", "/") for w in written if not w.endswith(".ba2")),
                         ["x/out/ok/good.txt"])

    def test_control_characters_in_names_are_shown_escaped(self):
        path = self.write("esc.ba2", writer.gnrl([("evil\x1b[31mred.txt", b"x")]))
        code, out, _ = run(bx.main, "list", path)
        self.assertEqual(code, 0)
        self.assertNotIn("\x1b", out)
        self.assertIn("evil\\x1b[31mred.txt", out)

    def test_output_folder_at_a_filesystem_root(self):
        root = os.path.realpath(os.path.abspath(os.sep))
        self.assertEqual(bx.safe_target(root, "a/b.txt"), os.path.join(root, "a", "b.txt"))
        self.assertIsNone(bx.safe_target(root, "/"))  # nothing left once empty parts go: never the root itself
        self.assertIsNone(bx.safe_target(root, "../b.txt"))
        self.assertIsNone(bx.safe_target(root, "a/../../b.txt"))

    def test_link_inside_the_output_folder_pointing_outside_is_refused(self):
        base = os.path.realpath(os.path.join(self.tmp, "out"))
        outside = os.path.join(self.tmp, "outside")
        os.makedirs(base)
        os.makedirs(outside)
        link = os.path.join(base, "link")
        try:
            os.symlink(outside, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            try:  # Windows without the symlink right: a directory junction needs none
                import _winapi
                _winapi.CreateJunction(outside, link)
            except (ImportError, AttributeError, OSError):
                self.skipTest("this account can't make symbolic links or junctions")
        self.assertIsNone(bx.safe_target(base, "link/evil.txt"))
        self.assertIsNotNone(bx.safe_target(base, "real/ok.txt"))

    def test_extract_skips_names_stored_twice(self):
        path = self.write("twice.ba2", writer.gnrl([("A.txt", b"1"), ("a.txt", b"2"), ("b.txt", b"3")]))
        code, out, _ = run(bx.main, "extract", path, os.path.join(self.tmp, "o"))
        self.assertEqual(code, 0)
        self.assertIn("1 file(s) extracted, 2 skipped", out)
        code, out, _ = run(bx.main, "list", path)
        self.assertEqual(out.count("(name stored more than once)"), 2)

    def test_diff_finds_damage_when_sizes_match(self):
        good = self.write("g.ba2", writer.gnrl([("x.txt", b"same-size text!!")]))
        data = bytearray(writer.gnrl([("x.txt", b"much longer text")]))
        start = 24 + 8 + 36  # header (version 2) + one record: the packed data starts here
        data[start:start + 4] = b"\xff\xff\xff\xff"
        bad = self.write("d.ba2", bytes(data))
        code, _, err = run(bx.main, "diff", good, bad)
        self.assertEqual(code, 2)
        self.assertIn("won't unpack", err)

    def test_names_the_console_cannot_show(self):
        out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="\n")
        bx.say("scripts/名前.pex", file=out)
        out.flush()
        self.assertEqual(out.buffer.getvalue(), b"scripts/\\u540d\\u524d.pex\n")

    def test_diff_refuses_names_differing_only_in_case(self):
        path = self.write("case.ba2", writer.gnrl([("A.txt", b"1"), ("a.txt", b"2")]))
        code, _, err = run(bx.main, "diff", path, path)
        self.assertEqual(code, 2)
        self.assertIn("ignoring case", err)

    def test_diff_with_different_sizes(self):
        a = self.write("s1.ba2", writer.gnrl([("x.txt", b"short")]))
        b = self.write("s2.ba2", writer.gnrl([("x.txt", b"much longer text")]))
        code, out, _ = run(bx.main, "diff", a, b)
        self.assertEqual(code, 1)
        self.assertIn("x.txt  (5 -> 16 bytes, stated sizes)", out)

    def test_extract_force_replaces_a_hard_link_instead_of_writing_through_it(self):
        outside = self.write("outside.txt", b"keep me")
        out_dir = os.path.join(self.tmp, "o")
        os.makedirs(out_dir)
        try:
            os.link(outside, os.path.join(out_dir, "x.txt"))
        except (OSError, NotImplementedError):
            self.skipTest("this file system can't make hard links")
        path = self.write("h.ba2", writer.gnrl([("x.txt", b"from the archive")]))
        code, out, _ = run(bx.main, "extract", path, out_dir)
        self.assertIn("use --force", out)
        code, out, _ = run(bx.main, "extract", path, out_dir, "--force")
        self.assertEqual(code, 0, out)
        self.assertEqual(read(outside), b"keep me")
        self.assertEqual(read(os.path.join(out_dir, "x.txt")), b"from the archive")
        self.assertEqual([n for n in os.listdir(out_dir) if n.startswith(".ba2x-")], [])

    def test_name_key(self):
        self.assertEqual(bx.name_key("./Textures//a.DDS"), bx.name_key("textures/A.dds"))
        self.assertNotEqual(bx.name_key("textures/straße.dds"), bx.name_key("textures/strasse.dds"))
        self.assertNotEqual(bx.name_key("a/ı.txt"), bx.name_key("a/i.txt"))  # dotless i stays itself
        self.assertEqual(pc._shown("./Scripts//MyMod/X.pex"), "MyMod/X.pex")
        self.assertEqual(pc._key("Scripts//MyMod/X.pex"), pc._key("mymod/x.PEX"))

    def test_extract_skips_a_clash_between_file_and_folder(self):
        path = self.write("clash.ba2", writer.gnrl([("a", b"file"), ("a/b.txt", b"inside"), ("c.txt", b"ok")]))
        code, out, _ = run(bx.main, "extract", path, os.path.join(self.tmp, "o"))
        self.assertEqual(code, 0, out)
        self.assertIn("skipped (a file is in the way of its folder", out)
        self.assertIn("2 file(s) extracted, 1 skipped", out)

    def test_a_failed_write_leaves_no_partial_file(self):
        target = os.path.join(self.tmp, "half.bin")
        with self.assertRaises(TypeError):
            bx._write_exclusive(target, "not bytes")  # write() fails after the file was created
        self.assertFalse(os.path.lexists(target))

    def test_a_failure_when_the_file_closes_leaves_no_partial_file(self):
        """A full disk usually shows up when the buffer is flushed at close, not in write()."""
        import builtins
        target = os.path.join(self.tmp, "full.bin")
        real_open = builtins.open

        class FullDisk(io.BytesIO):
            def close(self):
                super().close()
                raise OSError(28, "No space left on device")

        def fake_open(path, mode="r", *a, **k):
            if path == target:
                real_open(path, mode).close()  # the file is created, as a real open would
                return FullDisk()
            return real_open(path, mode, *a, **k)

        bx.open = fake_open  # module-level name lookup finds this before the builtin
        try:
            with self.assertRaises(OSError):
                bx._write_exclusive(target, b"data")
        finally:
            del bx.open
        self.assertFalse(os.path.lexists(target))

    def test_shown_name_keeps_a_lone_scripts(self):
        self.assertEqual(pc._shown("Scripts"), "Scripts")

    @unittest.skipUnless(os.name == "posix", "file permissions are POSIX only")
    def test_force_keeps_normal_permissions(self):
        path = self.write("p.ba2", writer.gnrl([("x.txt", b"data")]))
        out_dir = os.path.join(self.tmp, "o")
        run(bx.main, "extract", path, out_dir)
        run(bx.main, "extract", path, out_dir, "--force")
        mask = os.umask(0); os.umask(mask)
        self.assertEqual(os.stat(os.path.join(out_dir, "x.txt")).st_mode & 0o777, 0o666 & ~mask)

    def test_names_spelled_differently_count_as_duplicates(self):
        path = self.write("sp.ba2", writer.gnrl([("Textures/a.dds", b"1"), ("textures//A.dds", b"2"),
                                                  ("/other.txt", b"3")]))
        code, out, _ = run(bx.main, "extract", path, os.path.join(self.tmp, "o"))
        self.assertIn("1 file(s) extracted, 2 skipped", out)
        self.assertEqual(run(bx.main, "diff", path, path)[0], 2)

    def test_damaged_archives(self):
        good = writer.gnrl([("a.txt", b"a" * 1000)])
        cases = {
            "cut.ba2": good[:30],
            "magic.ba2": b"NOPE" + good[4:],
            "count.ba2": good[:12] + (10 ** 8).to_bytes(4, "little") + good[16:],
            "past_end.ba2": good[:-40],
        }
        for name, data in cases.items():
            with self.subTest(name):
                code, _, err = run(bx.main, "list", self.write(name, data))
                self.assertEqual(code, 2)
                self.assertIn("error:", err)

    def test_stated_size_smaller_than_content_is_refused(self):
        path = self.write("bomb.ba2", writer.gnrl([("a.txt", b"z" * 100000)], size_override={0: 10}))
        code, _, err = run(bx.main, "extract", path, os.path.join(self.tmp, "o"))
        self.assertEqual(code, 2)
        self.assertIn("more than its stated", err)

    def test_max_size(self):
        path = self.write("big.ba2", writer.gnrl([("a.txt", b"\0" * (2 * 1024 * 1024))]))
        code, _, err = run(bx.main, "extract", path, os.path.join(self.tmp, "o"), "--max-size", "1")
        self.assertEqual(code, 2)
        self.assertIn("--max-size", err)
        code, out, _ = run(bx.main, "extract", path, os.path.join(self.tmp, "o"), "--max-size", "3")
        self.assertEqual(code, 0, out)

    def test_bare_name_with_data(self):
        data = os.path.join(self.tmp, "Data")
        os.makedirs(data)
        shutil.copy(os.path.join(FIX, "a1.ba2"), os.path.join(data, "My Mod - Main.ba2"))
        code, out, _ = run(bx.main, "list", "My Mod - Main.ba2", "--data", data)
        self.assertEqual(code, 0)
        self.assertIn("alpha.pex", out.lower())
        code, _, err = run(bx.main, "list", "Missing.ba2", "--data", data)
        self.assertEqual(code, 2)
        self.assertIn("--data", err)

    def test_where_runs(self):
        code, out, _ = run(bx.main, "where")
        self.assertEqual(code, 0)
        self.assertTrue(out.strip())

    def test_log_file(self):
        logf = os.path.join(self.tmp, "b.log")
        run(bx.main, "list", os.path.join(FIX, "a1.ba2"), "--log", logf)
        with open(logf, encoding="utf-8") as f:
            self.assertIn("type GNRL, 2 files", f.read())

    def test_bad_arguments(self):
        self.assertEqual(run(bx.main)[0], 2)
        self.assertEqual(run(bx.main, "extract", "x.ba2")[0], 2)
        self.assertEqual(run(bx.main, "--version")[0], 0)


class CommandLine(unittest.TestCase):
    def test_isolated_mode_finds_its_sibling(self):
        """python -I leaves the script's folder off sys.path; pex_compare must still load ba2_extract."""
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "pex_compare.py"), "compare",
                            os.path.join(FIX, "a1.ba2"), os.path.join(PEX, "a2")],
                           capture_output=True, text=True, cwd=tempfile.gettempdir())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
