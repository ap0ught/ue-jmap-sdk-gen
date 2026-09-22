#!/usr/bin/env python3
"""Build fixtures/tiny.jmap — a minimal hand-built jmap for CI.

Exercises the regressions guarded by the generator:
  1. byte-typed enums (uint8_t) vs 4-byte enums (int32_t) vs overflow (uint32_t)
  2. SoftObjectProperty / SoftClassProperty emit as opaque_t<40>
  3. inheriting struct (super emitted) vs unselected/orphan super (flattened pads)
  4. member name colliding with its own type name (trailing '_')
  5. by-value struct dependency ordering (topo A < B < C)
  6. class function RVA comments (func - image base)
Re-run with:  python3 fixtures/build_tiny.py
"""
import json
import os

IMAGE_BASE = "0x140000000"
ENGINE = {"major": 5, "minor": 5}
BUILD = "TinyGame-main-CL-12345"

objs = {}

def mk(path, **kw):
    o = {"type": "Class", "address": "0x0", "vtable": "0x0", "object_flags": "",
         "outer": "", "class": "", "children": [], "property_values": {},
         "properties": [], "properties_size": 0, "min_alignment": 8, "script": "",
         "super_struct": None, "interfaces": [], "class_flags": "", "class_cast_flags": "",
         "class_default_object": ""}
    o.update(kw)
    objs[path] = o
    return o

def prop(name, off, size, typ, **kw):
    p = {"address": "0x0", "name": name, "offset": off, "array_dim": 1,
         "size": size, "type": typ,
         "flags": "CPF_ZeroConstructor | CPF_NoDestructor | CPF_HasGetValueTypeHash | CPF_NativeAccessSpecifierPublic"}
    p.update(kw)
    return p

# ---- modules (Packages) ----
mk("/Script/TinyGame", type="Package", outer="/Script", properties_size=0)
mk("/Script/TinyExtra", type="Package", outer="/Script", properties_size=0)
mk("/Script/CoreUObject", type="Package", outer="/Script", properties_size=0)

# ---- enums ----
# 1a: byte-typed enum (only ever referenced at size 1)
mk("/Script/TinyGame.TinyByte", type="Enum", outer="/Script/TinyGame",
   cpp_type="TinyByte", names=[["Off", 0], ["On", 1]])
# 1b: 4-byte enum (referenced at size 4 -> int32_t)
mk("/Script/TinyGame.TinyLevel", type="Enum", outer="/Script/TinyGame",
   cpp_type="TinyLevel", names=[["Low", 0], ["Mid", 2], ["High", 4]])
# 1c: overflow enum (value > 0x7FFFFFFF in a 4-byte slot -> uint32_t)
mk("/Script/TinyGame.TinyBig", type="Enum", outer="/Script/TinyGame",
   cpp_type="TinyBig", names=[["Zero", 0], ["Max", 4294967295]])

# ---- structs ----
# real UE struct the fixture imports (FVector -> FVector, 3 floats)
mk("/Script/CoreUObject.Vector", type="ScriptStruct", outer="/Script/CoreUObject",
   super_struct=None, properties_size=24,
   properties=[prop("X", 0, 4, "FloatProperty"),
               prop("Y", 4, 4, "FloatProperty"),
               prop("Z", 8, 4, "FloatProperty")])

# 3a: inheriting struct — super IS emitted -> `struct FTinyDerived : public FTinyBase`
mk("/Script/TinyGame.TinyBase", type="ScriptStruct", outer="/Script/TinyGame",
   super_struct=None, properties_size=4,
   properties=[prop("Base", 0, 4, "FloatProperty")])
mk("/Script/TinyGame.TinyDerived", type="ScriptStruct", outer="/Script/TinyGame",
   super_struct="/Script/TinyGame.TinyBase", properties_size=8,
   properties=[prop("Extra", 4, 4, "FloatProperty")])

# 3b: orphan super — super NOT in the dump -> flattened with opaque pads from 0
mk("/Script/TinyGame.TinyOrphan", type="ScriptStruct", outer="/Script/TinyGame",
   super_struct="/Script/NotEmitted.Mystery", properties_size=12,
   properties=[prop("Own", 8, 4, "FloatProperty")])

# 4: member name == own type name -> emitted as FName_ (else it would not compile)
mk("/Script/TinyGame.TinyNames", type="ScriptStruct", outer="/Script/TinyGame",
   super_struct=None, properties_size=16,
   properties=[prop("FName", 0, 8, "NameProperty"),
               prop("Title", 8, 8, "NameProperty")])

# 5: by-value dependency chain TinyTopoA < TinyTopoB < TinyTopoC
mk("/Script/TinyGame.TinyTopoA", type="ScriptStruct", outer="/Script/TinyGame",
   super_struct=None, properties_size=4,
   properties=[prop("V", 0, 4, "FloatProperty")])
mk("/Script/TinyGame.TinyTopoB", type="ScriptStruct", outer="/Script/TinyGame",
   super_struct=None, properties_size=4,
   properties=[prop("A", 0, 4, "StructProperty", struct="/Script/TinyGame.TinyTopoA")])
mk("/Script/TinyGame.TinyTopoC", type="ScriptStruct", outer="/Script/TinyGame",
   super_struct=None, properties_size=4,
   properties=[prop("B", 0, 4, "StructProperty", struct="/Script/TinyGame.TinyTopoB")])

# ---- classes ----
TinyActor = "/Script/TinyGame.TinyActor"
mk(TinyActor, outer="/Script/TinyGame", super_struct="/Script/CoreUObject.Object",
   properties_size=24,
   properties=[prop("Name", 0, 8, "NameProperty"),
               prop("Pos", 8, 4, "StructProperty", struct="/Script/TinyGame.TinyTopoA")])

TinyPlayer = "/Script/TinyGame.TinyPlayer"
mk(TinyPlayer, outer="/Script/TinyGame", super_struct="/Script/CoreUObject.Object",
   properties_size=200,
   properties=[
       prop("Health", 0, 4, "IntProperty"),
       prop("Level", 8, 4, "EnumProperty", enum="/Script/TinyGame.TinyLevel",
            container=prop("UnderlyingType", 8, 4, "ByteProperty")),
       prop("Status", 12, 1, "ByteProperty", enum="/Script/TinyGame.TinyByte"),
       prop("Big", 16, 4, "EnumProperty", enum="/Script/TinyGame.TinyBig",
            container=prop("UnderlyingType", 16, 4, "ByteProperty")),
       prop("SoftMesh", 24, 40, "SoftObjectProperty", property_class=TinyActor),
       prop("SoftClass", 64, 40, "SoftClassProperty", meta_class=TinyActor),
       prop("Spawner", 104, 8, "ObjectProperty", property_class=TinyActor),
       prop("Items", 112, 16, "ArrayProperty",
            inner=prop("_Base", 112, 4, "IntProperty")),
       prop("Pos", 128, 24, "StructProperty", struct="/Script/CoreUObject.Vector"),
       prop("Orphan", 152, 12, "StructProperty", struct="/Script/TinyGame.TinyOrphan"),
       prop("TopoC", 164, 4, "StructProperty", struct="/Script/TinyGame.TinyTopoC"),
       prop("Names", 168, 16, "StructProperty", struct="/Script/TinyGame.TinyNames"),
       prop("Derived", 184, 8, "StructProperty", struct="/Script/TinyGame.TinyDerived"),
       prop("Base", 192, 4, "StructProperty", struct="/Script/TinyGame.TinyBase"),
   ],
   children=["%s:Hello" % TinyPlayer, "%s:VerifyFunc" % TinyPlayer])

# 6: functions with RVAs -> emit `// func TinyPlayer:Hello: RVA 0x1234560`
mk("%s:Hello" % TinyPlayer, type="Function", outer=TinyPlayer,
   func="0x141234560", min_alignment=1, function_flags="FUNC_Native",
   properties=[prop("ReturnValue", 0, 4, "IntProperty")])
mk("%s:VerifyFunc" % TinyPlayer, type="Function", outer=TinyPlayer,
   func="0x140aaaaaa", min_alignment=1, function_flags="FUNC_Native",
   properties=[prop("ReturnValue", 0, 1, "BoolProperty")])

# separate module to prove --modules filtering excludes it
Popup = "/Script/TinyExtra.Popup"
mk(Popup, outer="/Script/TinyExtra", super_struct="/Script/CoreUObject.Object",
   properties_size=8, properties=[prop("Text", 0, 8, "NameProperty")])

jmap = {
    "image_base_address": IMAGE_BASE,
    "metadata": {
        "tool": "https://github.com/trumank/jmap",
        "timestamp": "2026-09-22 00:00:00 +00:00:00",
        "source": "TinyGame-Win64-Shipping.exe",
        "engine_version": ENGINE,
        "build_change_list": BUILD,
    },
    "objects": objs,
    "vtables": {},
}

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiny.jmap")
with open(out, "w", encoding="utf-8") as f:
    json.dump(jmap, f, indent=1)
print("wrote %s (%d objects)" % (out, len(objs)))