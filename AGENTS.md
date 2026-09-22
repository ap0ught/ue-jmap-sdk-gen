# AGENTS.md — guidance for agentic tools, forks, and automation

This repository is a **GitHub template** for building C++ reflection SDKs for
any Unreal Engine game from a [trumank/jmap](https://github.com/trumank/jmap)
dump. It is intended to be used both by humans and by autonomous coding agents
(CI, Copilot, Claude/GPT-based tools). If you are an agent working in this
repo or in a fork of it, follow these conventions.

## What this is / isn't

- **Is:** a Python-orchestrated pipeline: `jmap` → generated headers → compile
  check → golden-layout probe → optional re-run on game patches.
- **Is not:** a runtime library, a DLL injector, or an SDK for a specific game.
  A fork of this template *becomes* the specific game's SDK repo by editing
  `game.yaml` and committing the generated `sdk/` output.

## The pipeline (three commands)

```
python3 sdkgen.py generate --jmap path/to/Game.jmap    # writes sdk/ + version.json
python3 sdkgen.py verify  --sdk sdk --config game.yaml # gate: compile + layout probe
python3 sdkgen.py update  --jmap path/to/newer.jmap    # re-generate, diff, verify
```

Rules agents must respect:

1. **Never edit generated code.** Everything under `sdk/` is output. Change
   `game.yaml`, the fixture, or `generator/jmap2sdk.py` instead, then
   regenerate. Generated headers are committed (they are the SDK), but hand
   edits to them will be lost on the next `generate`/`update`.
2. **Never hand-patch `generator/jmap2sdk.py` layout rules** without re-running
   the fixture CI (`fixtures/build_tiny.py` + `sdkgen.py verify`). The six
   fixture cases (byte/4-byte/overflow enums, SoftObject/SoftClass `opaque_t<40>`,
   super-struct inheritance vs orphan flattening, member-name collisions, topo
   ordering, function RVA comments) are the regression contract.
3. **`game.yaml` is the single per-game customization point.** `verify.*`
   holds *golden* sizes/offsets — concrete numbers, not guesses. Missing
   symbols are skipped automatically so module-filtered SDKs still verify.
4. **Keep `sdk/version.json` in sync with the dump.** It records
   `engine`, `build`, `source`, `image_base`. `verify --jmap <dump>` pins it.
5. **Large dumps are not committed.** Add your `.jmap` to `.gitignore` (or keep
   it outside the repo) and reference it by path. `fixtures/tiny.jmap` is the
   small stand-in used for CI.
6. **CI workflows are part of the contract.** `verify.yml` (on push/PR) and
   `update-sdk.yml` (manual dispatch) must stay green. When you change the
   generator or fixture, re-run both locally before pushing.
7. **Credits stay intact.** `CREDITS.md` and the README footer credit KN4CK3R,
   Kronos/SatisfactorySDKGenerator, and trumank/jmap. Do not strip them when
   forking the template.

## How a fork differs from this template

A fork that targets one game changes only:

- `game.yaml` (game name, `modules`, `verify` goldens for that game)
- `.gitignore` (usually adds `<Game>.jmap`)
- the committed `sdk/` output and `sdk/version.json`

Everything else (generator, verifier, workflows, fixture) should stay generic
unless you are improving the pipeline itself — in which case CI will re-check
your change against the fixture.

## Environment

- Python 3.9+ (stdlib only for `sdkgen.py`; `PyYAML` and `ijson` are preferred
  but `sdkgen.py` detects their absence and degrades).
- A C++17 compiler (`g++`) for `verify`.
- `jmap` dumps come from `trumank/jmap`'s `jmap_dumper` (Rust). See
  `docs/skill.md` for the full end-to-end skill, including the Windows
  minidump + PATTERNSLEUTH workflow.

## Layout reference

```
generator/jmap2sdk.py   the (unchanged) generator; emit engine + layout logic
sdkgen.py               orchestration CLI (generate/verify/update)
verify/probe.cpp.tmpl   C++ probe scaffold (static_asserts on goldens)
fixtures/build_tiny.py  generates the CI fixture; edit, then re-run it
fixtures/tiny.jmap      committed miniature dump (19 objects, 6 tricky cases)
game.yaml               per-game config; edit me in a fork
sdk/                    generated output (committed); never hand-edit
.github/workflows/      verify.yml + update-sdk.yml
docs/skill.md           the full "make an SDK for any UE game" skill
```