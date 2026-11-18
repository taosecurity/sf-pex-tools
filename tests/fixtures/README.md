# Test fixtures

Everything here was made for the tests. Nothing comes from the game.

- `src/v1` and `src/v2` hold two small test scripts written for sf-pex-tools (MIT). `Alpha` uses a struct, a guard
  (`LockGuard`, `TryLockGuard`) and `GetAllMatchingStructs`. `Beta` uses property groups, a full property and a
  state. `v2` changes one number in Alpha (`100` to `250`) and adds a comment to Beta.
- `pex/a1` and `pex/a2` are two compilations of `src/v1`. They are the same code, but their bytes differ.
  `pex/b` is `src/v2`.
- `a1.ba2` and `b.ba2` are `pex/a1` and `pex/b` packed with Archive2 (general archive, version 2).

They were made on 2026-11-18 with the Steam Creation Kit's `PapyrusCompiler.exe` (no `-release`, no `-optimize`)
and `Archive2.exe`, using `make_fixtures.py`:

```
python -I tests/fixtures/make_fixtures.py --tools "<Starfield>\Tools" --imports "<Bethesda's Scripts\Source>"
```

The compiler needs Bethesda's script sources as imports (from `Tools\ContentResources.zip`). They're used only
while compiling and aren't copied here. Rebuilding gives different `.pex` bytes every time (that's what the tool
is for), so the checksums below change if you rebuild.

```
fd67426d88afc48a00f7cf2114086c9f9b398e0cee036ff32c02e408763fb493  a1.ba2
22dd420f75f87fbefef7e7abec4fbd4649a7731dfeeb6aef7031b29e7e91e433  b.ba2
593000b5b3016a7fcee3320703f728724154dfdd192dd894b4e7d6178886bf67  pex/a1/SfPexToolsTest/Alpha.pex
8a69720f6439e1c7ea370040ce71bb1dd692d30fea4f868895f62892d71e9b4c  pex/a1/SfPexToolsTest/Beta.pex
672986cd63727b71bbd5a471e17712feeccda82ae85080009e438450b5ba7335  pex/a2/SfPexToolsTest/Alpha.pex
42e8c6131b5e88aa7360cefeae01605e4eb7a86b3550bf85fc0444bbd4ffecec  pex/a2/SfPexToolsTest/Beta.pex
10c3af28f218ee0da292e2918ffabc7b91707709f08ed0368cf516bb1c1f71f6  pex/b/SfPexToolsTest/Alpha.pex
547b66bb2754b80d720b06d81fe395eaae1bd50f3df27ba8a50dd0b9f2b2ebd1  pex/b/SfPexToolsTest/Beta.pex
```

Other archive kinds (LZ4, stored, version 1 and 8, textures, damaged archives) are built during the tests by
`tests/ba2_writer.py`.
