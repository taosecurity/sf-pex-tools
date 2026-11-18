# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Richard Bejtlich
"""Rebuild the test fixtures from the test scripts in src/ (maintainers only; the tests use the committed files).

  python -I tests/fixtures/make_fixtures.py --tools "<Starfield>\\Tools" --imports "<folder with Bethesda's .psc>"

--tools is the Starfield Creation Kit's Tools folder (it holds "Papyrus Compiler" and "Archive2").
--imports is a folder with Bethesda's script sources (Scripts\\Source from Tools\\ContentResources.zip),
needed only as compiler imports. Nothing from it is copied into the fixtures.

It compiles src/v1 twice (pex/a1 and pex/a2: the same source, so the scripts are equivalent but the bytes
differ) and src/v2 once (pex/b: one changed constant in Alpha, one added comment in Beta), without -release,
then packs pex/a1 into a1.ba2 and pex/b into b.ba2 with Archive2, and prints the SHA-256 of every file.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = ("Alpha", "Beta")


def compile_set(tools, imports, src, out):
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    flags = os.path.join(imports, "Starfield_Papyrus_Flags.flg")
    for name in SCRIPTS:
        cmd = [os.path.join(tools, "Papyrus Compiler", "PapyrusCompiler.exe"), f"SfPexToolsTest\\{name}.psc",
               f"-i={src};{imports}", f"-f={flags}", f"-o={out}"]
        r = subprocess.run(cmd, cwd=src, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        target = os.path.join(out, "SfPexToolsTest", f"{name}.pex")
        if not os.path.isfile(target):
            sys.exit(f"compile failed: {name}\n{r.stdout}\n{r.stderr}")
        print(f"compiled {target}")


def pack(tools, pex_dir, ba2):
    """Archive2 stores paths relative to -r, so stage the scripts under <stage>/Scripts/."""
    stage = os.path.join(HERE, "_stage")
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(pex_dir, os.path.join(stage, "Scripts"))
    if os.path.exists(ba2):
        os.remove(ba2)
    subprocess.run([os.path.join(tools, "Archive2", "Archive2.exe"), os.path.join(stage, "Scripts"),
                    f"-c={ba2}", f"-r={stage}", "-q"], check=True, stdin=subprocess.DEVNULL)
    shutil.rmtree(stage)
    print(f"packed {ba2}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tools", required=True)
    p.add_argument("--imports", required=True)
    a = p.parse_args()
    pex = os.path.join(HERE, "pex")
    compile_set(a.tools, a.imports, os.path.join(HERE, "src", "v1"), os.path.join(pex, "a1"))
    compile_set(a.tools, a.imports, os.path.join(HERE, "src", "v1"), os.path.join(pex, "a2"))
    compile_set(a.tools, a.imports, os.path.join(HERE, "src", "v2"), os.path.join(pex, "b"))
    pack(a.tools, os.path.join(pex, "a1"), os.path.join(HERE, "a1.ba2"))
    pack(a.tools, os.path.join(pex, "b"), os.path.join(HERE, "b.ba2"))
    for root, _, names in os.walk(HERE):
        for n in sorted(names):
            if n.endswith((".pex", ".ba2")):
                f = os.path.join(root, n)
                print(hashlib.sha256(open(f, "rb").read()).hexdigest(), os.path.relpath(f, HERE).replace("\\", "/"))


if __name__ == "__main__":
    main()
