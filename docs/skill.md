# UE4/UE5 SDK Generation — the skill, packaged

> **One pipeline, two routes.** Route 1 is this template's native workflow: an
> **offline jmap→SDK generator** (`generator/jmap2sdk.py`, orchestrated by
> `sdkgen.py`) that consumes a `.jmap` reflection dump and emits layout-exact C++
> headers with **no game process access**. Route 2 is the legacy in-process
> KN4CK3R/SatisfactorySDKGenerator DLL-injection lineage — use it only when no
> `.jmap` exists for the game.

## Route 1 — offline jmap → SDK (preferred)

Input: a `.jmap` JSON reflection dump produced by
[trumank/jmap](https://github.com/trumank/jmap)'s `jmap_dumper` (a Rust CLI that
reads a running process or a full-memory Windows minidump). The dump holds every
class/struct/enum, property offsets, sizes, and native function addresses. The
generator does **not** touch the game — it reads the JSON and emits five headers:

```
BasicTypes.hpp   UE primitives: FName(8) FString(16) FText(16) FVector, TArray(16),
                 TObjectPtr, opaque_t<N>, base UObject layout (0x28)
Fwd.hpp          forward decls: every enum/struct/class + every class ref reachable
                 from structs+classes (so module-filtered builds still compile)
Enums.hpp        enum class E<Name> : underlying (per-enum from how it's REFERENCED:
                 int32_t in a 4-byte slot, uint8_t in a 1-byte slot)
Structs.hpp      struct F<Name> + static_assert(sizeof >= properties_size); parent
                 inherited only when it is itself emitted (else flattened pads);
                 topo-ordered so by-value struct deps are defined first
Classes.hpp      struct U<Name> : <nearest emitted ancestor>; per-class
                 // func <name>: RVA 0x… comments; members at exact offsets
                 with opaque gap fills + static_assert on total size
```

### Using the CLI

```sh
python3 sdkgen.py generate --jmap /path/to/Game.jmap            # writes sdk/ + version.json
python3 sdkgen.py verify  --sdk sdk --config game.yaml          # g++ compile + layout probe
python3 sdkgen.py update  --jmap /path/to/Newer.jmap            # re-gen, diff, verify (patches)
```

`game.yaml` holds the per-game specifics (modules filter, verify goldens). The
`verify` step is the regression gate: it compiles `Classes.hpp` and static-asserts
golden sizes/offsets via `verify/probe.cpp.tmpl`.

### Layout-authoring rules encoded in the generator
(re-derive for other dumps if they differ)

- Unknown/container slots become `opaque_t<N>` fills; same-offset properties
  (bitfield bools) collapse to comments on the main member.
- Enum underlying type comes from the **referencing property slot size** (jmap
  `size`: 4 for EnumProperty pools, 1 for ByteProperty pools), *not* the max
  value — UE enums are int32 unless `:uint8`. Values `> 0x7FFFFFFF` in a 4-byte
  slot → `uint32_t`.
- By-value struct fields without a definition in the emitted set become
  `opaque_t<size>`; struct inheritance only when the parent is itself emitted.
- Member names that shadow their own type get a trailing `_`; the root
  `CoreUObject.Object` class is skipped (UObject lives in BasicTypes.hpp).
- Function RVAs are comments only (native exec minus image base); usable after
  adding a runtime binding layer (`SetBaseAddress(gamemodule) + Addr(rva)`).

Validated on a UE 5.5 dump (image base 0x140000000):
6413 classes / 2068 structs / 1320 enums in ~46 s, clean compile, spot checks
(`FVector`=24, `FString`=16, `FName`=8, `FRigModuleReference`=368,
`FConstraintInstance`=648, `UGameInstance` RVA `0x14389b5d0`→`0x389b5d0`) all
match. Should run on any game with a jmap dump.

### Getting a jmap for a game

1. On Windows: launch the game to the main menu, create a full-memory minidump
   (Task Manager → right-click game → "Create dump file").
2. `jmap_dumper --minidump Game.DMP output.jmap` (or `--pid <pid>` live).
3. If the dumper reports `PATTERNSLEUTH_RES_EngineVersion` / `_FNamePool`
   resolution errors, set the documented env vars and retry.

## Route 2 — in-process generator (KN4CK3R lineage, fallback)

A Windows x64 DLL injected into the running game. It signature-scans the module
for `GObjects`/`GNames`/`GWorld`, walks the arrays, and writes `SDK.hpp`.
Reference repo: `https://github.com/satisfactorymodding/SatisfactorySDKGenerator`
(archived, read-only; fork of KN4CK3R's generator + Kronos's Satisfactory target).
Use as a **template** for any UE game when no jmap exists.

Key files: `Engine/` (game-agnostic), `Target/<Game>/` (the ONLY game-specific
unit: GObjects/GNames signatures, Generator.cpp knobs, EngineClasses.hpp).
Port steps: copy a Target, replace signatures, adjust engine offsets per UE
version, build (VS, x64 Release), inject (`Syringe`/`Xenos`/`x64dbg`), collect
`SDK.hpp` under `<Output>/<ShortName>/`.

### Update / re-signature playbook after a game patch

Never guess masks. Re-derive GObjects/GNames/GWorld against the current binary;
update BOTH `Target/<Game>/*Store.cpp` AND the generated `InitSDK()` block
(details in the generator lineage `_Basic.hpp`). If core offsets moved, refresh
`EngineClasses.hpp` + `predefinedMembers`. Bump `GetGameVersion()`, rebuild,
re-inject, verify that a known class renders with ascending offsets and the
`SDK.hpp` compiles + does `SDK::InitSDK()` object lookups.

## Verification checklist (either route)

- Offline: `sdkgen.py verify` → "VERIFY PASS" with non-empty goldens; diff old vs
  new `sdk/` after a patch; check `version.json` build vs the dump's
  `metadata.build_change_list`.
- In-process: `Generator.log` ends "Finished"; `ObjectsDump.txt` dense; known
  class renders in the right `_classes.hpp` with ascending offsets; generated
  `SDK.hpp` compiles and resolves objects at runtime.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `verify` → compile FAIL | Gap-fill math vs `properties_size`; adjust generator or re-dump. |
| probe → `sizeof == N` fails | Golden in `game.yaml` stale after a patch — update from the new dump. |
| `update` reports changed `build` | New patch detected: commit the regenerated `sdk/`. |
| classifier skips a whole module | `--modules` filter excludes it; empty `modules` = everything. |
| Enum width wrong | Slots: enum used in a 1-byte ByteProperty → uint8; 4-byte EnumProperty → int32/uint32. |
| In-process: "ObjectsStore::Initialize failed" | GObjects pattern wrong for this build; re-scan. |
| In-process: huge `MISSING.hpp` | Layout drift: refresh `EngineClasses.hpp` + predefinedMembers. |

## Gotchas

- jmap patterns/dump format are version-locked to trumank/jmap — re-dump when
  the game updates, never reuse an old dump for a new patch.
- Function RVAs are addresses, not callable code, until you add a binding layer.
- If the user mentions anti-cheat or a live online session, stop and confirm scope
  before any injected/in-process work.