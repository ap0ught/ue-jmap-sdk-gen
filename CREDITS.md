# Credits

This template inherits method, structure, and format lineage from the
following open-source projects. Please keep this file, and the README footer
referencing it, intact when forking the template.

## KN4CK3R — original Unreal Engine SDK Generator

The class/struct reflection-SDK emission approach (offset-accurate C++
headers derived from a live/world UObject reflection dump) is the original
work of **KN4CK3R** (the classic "Unreal Engine 4 SDK Generator",
oldschoolhack.me). The `U`/`F`/`E` naming, `TObjectPtr`/`FName`/`FString`
basic types, and per-member offset layout style in `generator/jmap2sdk.py`
follow that lineage.

## Kronos / satisfactorymodding/SatisfactorySDKGenerator

**Kronos**'s maintenance of KN4CK3R's generator for Satisfactory —
`https://github.com/satisfactorymodding/SatisfactorySDKGenerator` — is the
working reference this pipeline was adapted from. Kronos contributed the
Engine update flows and pattern resolution that informed how we structure
re-generation when a game patches.

## trumank/jmap — the reflection format & dumper

The `.jmap` dump format and the `jmap_dumper` tool that produce the input to
this generator are **Truman Kilen**'s **trumank/jmap** project:
`https://github.com/trumank/jmap` (MIT). The JSON layout — objects keyed by
`/Path.Name`, `properties`, `properties_size`, `super_struct`, `func` RVAs,
`metadata`/`engine_version`/`build_change_list` — is defined there, and the
generator's output is a superset-compatible interpretation of it.

- jmap License: MIT — Copyright (c) 2025 Truman Kilen. See LICENSE.md note.
- The `metadata.tool` field in every dump already records the upstream
  `https://github.com/trumank/jmap`.

## Example content

`fixtures/tiny.jmap` is a hand-built synthetic dump for CI; it is *not* taken
from any shipped game. Ground-truth golden values in a real fork are derived
from that game's own dump and verified against its process (as documented in
`docs/skill.md`).