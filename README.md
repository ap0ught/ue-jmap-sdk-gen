# ue-jmap-sdk-gen — generic Unreal SDK generator (GitHub template)

A Python-orchestrated pipeline that turns a [trumank/jmap](https://github.com/trumank/jmap)
reflection dump of **any Unreal Engine 4/5 game** into a pinned, compile-checked
C++ SDK — then regenerates and re-verifies it whenever the game patches.

```
   Game.jmap ──► generator/jmap2sdk.py ──► sdk/ (5 committed headers)
        ▲                                        │
        │ sdkgen.py update (new patch)           ▼ sdkgen.py verify
        └────────── version.json ◄──────── g++ compile + layout probe
```

## Quickstart

```sh
# 1. fork this repo ("Use this template" → your game's SDK repo), then:
python3 -m pip install pyyaml            # optional; sdkgen degrades without it
python3 sdkgen.py generate --jmap /path/to/MyGame.jmap
python3 sdkgen.py verify  --sdk sdk --config game.yaml
git add sdk game.yaml && git commit      # SDK output is committed, not ignored
```

Edit `game.yaml` for your game: `game`, `engine`, `modules` (e.g.
`["P9Playable"]` to scope to one gameplay module, empty = everything), and the
`verify` goldens (sizes/offsets that must hold — add the types you actually
mod; missing symbols are skipped automatically).

## On a game patch

```sh
python3 sdkgen.py update --jmap /path/to/Newer.jmap     # re-generate + verify + report
```

The update compares `metadata.build_change_list` / `engine_version` against
`sdk/version.json`, regenerates, and re-runs the layout probe — the same step
CI runs via **Actions → update-sdk → Run workflow**, which commits the new SDK
back to the repo.

## What's in the box

| Path | Purpose |
|---|---|
| `generator/jmap2sdk.py` | the verified layout-exact generator (single file, untouched) |
| `sdkgen.py` | orchestration CLI: `generate` / `verify` / `update` |
| `game.yaml` | the per-game customization point (modules + verify goldens) |
| `verify/probe.cpp.tmpl` | C++ layout probe (static_assert golden sizes/offsets) |
| `fixtures/build_tiny.py` + `fixtures/tiny.jmap` | CI fixture exercising the 6 regression cases |
| `.github/workflows/verify.yml` | on push/PR: generate from fixture + compile + probe |
| `.github/workflows/update-sdk.yml` | manual dispatch: regenerate + verify + commit `sdk/` |
| `docs/skill.md` | the full end-to-end skill (jmap route + in-process fallback) |
| `AGENTS.md` | conventions for automated/agentic users of this template |
| `CREDITS.md`, `LICENSE` | must-stay-intact attribution (see footer) |

### The six fixture regression cases
1. byte-typed enum → `uint8_t`; 4-byte enum → `int32_t`; overflow → `uint32_t`
2. `SoftObjectProperty`/`SoftClassProperty` → `opaque_t<40>`
3. inheriting struct vs orphan-super struct (flattened pads)
4. member name colliding with its type → trailing `_`
5. by-value struct dependency topo-ordering
6. function RVA comments (`// func TinyPlayer:Hello: RVA 0x1234560`)

## Verified on real input

Full The Alters dump (`TheAlters.jmap`, image base `0x140000000`, UE 5.5):
**6413 classes / 2068 structs / 1320 enums**, ~46 s generate, clean C++17
compile, layout spot-checks match the dump. Module-filtered
(`--modules P9Playable`) builds also compile. See `docs/skill.md` for numbers.

## Requirements

- Python 3.9+ (stdlib; PyYAML preferred for `game.yaml`)
- `g++` (or any C++17 compiler) for `verify`
- a `.jmap` dump of the target game (from `jmap_dumper`, see `docs/skill.md`)

---

*This template is derived from the work of **KN4CK3R** (original UE4 SDK
Generator), **Kronos** (SatisfactorySDKGenerator), and **trumank/jmap** (the
reflection format + dumper). Keeping `CREDITS.md` and these attributions is
part of the fork contract — read [`CREDITS.md`](CREDITS.md).*