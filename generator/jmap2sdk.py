#!/usr/bin/env python3
"""jmap2sdk.py — generate a C++ layout SDK from a trumank jmap reflection dump.

Usage:
  python3 jmap2sdk.py --jmap TheAlters.jmap --out sdk --modules P9Playable
  python3 jmp2sdk.py --jmap TheAlters.jmap --out sdk            # all classes

Emits: BasicTypes.hpp, Enums.hpp, Structs.hpp, Classes.hpp
All offsets/sizes come from the dump and are pinned with static_asserts.
"""
import argparse
import json
import os
import re

NUMERIC = {
    "Int8Property": "int8_t",
    "Int16Property": "int16_t",
    "IntProperty": "int32_t",
    "Int64Property": "int64_t",
    "UInt16Property": "uint16_t",
    "UInt32Property": "uint32_t",
    "UInt64Property": "uint64_t",
    "FloatProperty": "float",
    "DoubleProperty": "double",
}

CPP_KEYWORDS = {
    "class", "public", "private", "protected", "virtual", "struct", "union",
    "template", "typename", "namespace", "using", "new", "delete", "void",
    "static", "const", "int", "char", "float", "double", "bool", "unsigned",
    "signed", "long", "short", "auto", "operator", "sizeof", "if", "else",
    "for", "while", "do", "switch", "case", "default", "return", "goto",
    "extern", "inline", "this", "true", "false", "nullptr", "NULL",
}


def sanitize(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if name in CPP_KEYWORDS or name.startswith("_"):
        name = "_" + name
    return name


class SDK:
    def __init__(self, jmap_path):
        with open(jmap_path, "r", encoding="utf-8") as f:
            self.jmap = json.load(f)
        self.objs = self.jmap["objects"]
        meta = self.jmap["metadata"]
        self.engine = f"{meta['engine_version']['major']}.{meta['engine_version']['minor']}"
        self.build = meta.get("build_change_list", "")
        self.image_base = int(self.jmap.get("image_base_address", "0x140000000"), 16)
        self.enums = {}
        self.structs = {}
        self.classes = {}
        self.pkgs = {}

    def classify(self):
        self.enum_slots = {}
        for path, o in self.objs.items():
            o["path"] = path
            t = o["type"]
            if t == "Enum":
                self.enums[path] = o
            elif t == "ScriptStruct":
                self.structs[path] = o
            elif t == "Class":
                self.classes[path] = o
            elif t == "Package":
                self.pkgs[path] = o
            for p in o.get("properties", []):
                if not p:
                    continue
                self._slot(o, p)

    def _slot(self, o, p):
        if p.get("enum") and p["type"] in ("EnumProperty", "ByteProperty"):
            sz = p.get("size") or 1
            self.enum_slots[p["enum"]] = max(self.enum_slots.get(p["enum"], 0), sz)
        for k in ("inner", "key_prop", "value_prop", "container"):
            c = p.get(k)
            if c and isinstance(c, dict):
                self._slot(o, c)

    def module_of(self, path):
        m = re.match(r"/Script/([^./]+)", path or "")
        return m.group(1) if m else ""

    def ref_paths(self, o):
        refs = []
        for p in o.get("properties", []):
            if not p:
                continue
            t = p["type"]
            if t == "StructProperty" and p.get("struct"):
                refs.append(p["struct"])
            if t == "EnumProperty":
                if p.get("enum"):
                    refs.append(p["enum"])
                c = p.get("container") or {}
                if c.get("enum"):
                    refs.append(c["enum"])
            if t == "ByteProperty" and p.get("enum"):
                refs.append(p["enum"])
            if t in ("ObjectProperty", "ClassProperty"):
                for k in ("property_class", "meta_class"):
                    if p.get(k):
                        refs.append(p[k])
            if t in ("ArrayProperty", "OptionalProperty"):
                inner = p.get("inner") or {}
                for r in self.ref_paths({"properties": [inner]}):
                    refs.append(r)
            if t in ("MapProperty", "SetProperty"):
                key = p.get("key_prop") or {}
                val = p.get("value_prop") or {}
                for r in self.ref_paths({"properties": [key, val]}):
                    refs.append(r)
            if t in ("WeakObjectProperty", "LazyObjectProperty",
                     "SoftObjectProperty", "SoftClassProperty"):
                if p.get("property_class"):
                    refs.append(p["property_class"])
        return refs

    def resolve(self, modules):
        selected = set()
        roots = []
        if modules:
            for path in self.classes:
                if self.module_of(path) in modules:
                    roots.append(path)
        else:
            roots = list(self.classes)
        stack = list(roots)
        while stack:
            path = stack.pop()
            if path in selected:
                continue
            o = self.classes.get(path)
            if o:
                selected.add(path)
                if o.get("super_struct"):
                    stack.append(o["super_struct"])
                for r in self.ref_paths(o):
                    stack.append(r)
                for itf in o.get("interfaces") or []:
                    if isinstance(itf, dict) and itf.get("class"):
                        stack.append(itf["class"])
                continue
            o = self.structs.get(path)
            if o:
                selected.add(path)
                for r in self.ref_paths(o):
                    stack.append(r)
                continue
            o = self.enums.get(path)
            if o:
                selected.add(path)
                continue
            if self.objs.get(path):
                selected.add(path)
        roots_set = set(roots)
        struct_sel = [p for p in self.structs if p in selected and p not in roots_set]
        enum_sel = [p for p in self.enums if p in selected]
        return roots_set, struct_sel, enum_sel

    def type_of(self, path, fallback="UObject"):
        if not path:
            return fallback
        if path in self.classes:
            return "U" + sanitize(name_of(self.classes[path]))
        if path in self.structs:
            return "F" + sanitize(name_of(self.structs[path]))
        if path in self.enums:
            return "E" + sanitize(name_of(self.enums[path]))
        if path in self.objs and self.objs[path]["type"] == "Class":
            return "U" + sanitize(name_of(self.objs[path]))
        return fallback

    def enum_underlying(self, path, o):
        names = o.get("names") or []
        mx = max((n[1] for n in names), default=0)
        slot = getattr(self, "enum_slots", {}).get(path, 4)
        if slot >= 8 or mx > 0xFFFFFFFF:
            return "uint64_t"
        if slot >= 4:
            if mx > 0x7FFFFFFF:
                return "uint32_t"
            return "int32_t"
        if mx > 0xFF:
            return "uint16_t"
        return "uint8_t"

    def cpp_type(self, p):
        t = p["type"]
        sz = p.get("size", 0)
        name = p.get("name", "")
        if t in NUMERIC:
            return NUMERIC[t]
        if t == "BoolProperty":
            return "bool"
        if t == "NameProperty":
            return "FName"
        if t == "StrProperty":
            return "FString"
        if t == "TextProperty":
            return "FText"
        if t == "EnumProperty":
            e = p.get("enum")
            if e:
                return self.type_of(e)
            return "uint8_t"
        if t == "ByteProperty":
            e = p.get("enum")
            if e:
                return self.type_of(e)
            return "uint8_t"
        if t == "StructProperty":
            s = p.get("struct")
            if s and (s in self.structs or s in self.classes):
                return self.type_of(s)
            return f"opaque_t<{sz}>"
        if t in ("ObjectProperty", "WeakObjectProperty", "LazyObjectProperty"):
            base = self.type_of(p.get("property_class"))
            if t == "WeakObjectProperty":
                return f"FWeakObjectPtr<{base}>"
            if t == "LazyObjectProperty":
                return f"opaque_t<{sz}>"
            return f"TObjectPtr<{base}>"
        if t in ("ClassProperty", "SoftClassProperty"):
            base = self.type_of(p.get("meta_class") or p.get("property_class"))
            if t == "SoftClassProperty":
                return f"opaque_t<{sz}>"
            return f"TObjectPtr<UClass>"
        if t == "SoftObjectProperty":
            return f"opaque_t<{sz}>"
        if t == "SoftObjectProperty":
            return f"opaque_t<{sz}>"
        if t == "ArrayProperty":
            inner = self.cpp_type(p.get("inner") or {})
            return f"TArray<{inner}>"
        if t == "OptionalProperty":
            inner = self.cpp_type(p.get("inner") or {})
            return f"opaque_t<{sz}>"
        if t == "MapProperty":
            return f"opaque_t<{sz}>"
        if t == "SetProperty":
            return f"opaque_t<{sz}>"
        return f"opaque_t<{sz}>"

    def type_name(self, obj):
        n = obj.get("name", "") or obj["path"].split(".")[-1]
        return n.split(".")[-1].replace("Default__", "")


def name_of(obj):
    return obj["path"].split(".")[-1].replace("Default__", "")


class Emitter:
    def __init__(self, sdk):
        self.s = sdk

    def basic_types(self):
        return '''#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <type_traits>
#include <algorithm>

namespace SDK {

using uintptr = std::uintptr_t;
using int32 = std::int32_t;
using uint32 = std::uint32_t;
using int64 = std::int64_t;
using uint64 = std::uint64_t;

template <std::size_t N>
struct opaque_t { uint8_t data[N]; };

struct FName {
    uint32 ComparisonIndex;
    uint32 Number;
    const char* ToString() const;
};

struct FString {
    wchar_t* Data;
    int32 Num;
    int32 Max;
    int32 Length() const { return Num; }
    const wchar_t* c_str() const { return Data; }
};

struct FText {
    opaque_t<16> raw{};
};

template <typename T>
struct TObjectPtr {
    T* Value;
    explicit operator bool() const { return Value != nullptr; }
    T* operator->() const { return Value; }
    T& operator*() const { return *Value; }
};

template <typename T>
struct FWeakObjectPtr {
    uint32 ObjectIndex;
    uint32 ObjectSerialNumber;
    T* Resolve() const;
};

template <typename T>
struct TArray {
    T* Data;
    int32 Count;
    int32 Max;
    int32 Num() const { return Count; }
    const T& operator[](int32 i) const { return Data[i]; }
    T& operator[](int32 i) { return Data[i]; }
    T& operator[](std::size_t i) { return Data[i]; }
    const T& operator[](std::size_t i) const { return Data[i]; }
};

struct UClass;

struct UObject {
    TObjectPtr<UClass> ClassPrivate;        // 0x00
    uint32 ObjectFlags;                     // 0x08
    uint32 InternalIndex;                   // 0x0C
    TObjectPtr<UObject> OuterPrivate;       // 0x10
    FName NamePrivate;                      // 0x18
    TObjectPtr<UObject> ObjectArchetype;    // 0x20

    UClass* GetClass() const { return ClassPrivate.Value; }
    FName GetFName() const { return NamePrivate; }
    const char* GetName() const { return NamePrivate.ToString(); }
    bool IsA(UClass* c) const;
    template <typename T> bool IsA() const;
    void* GetPropertyValue(std::size_t offset) const {
        return reinterpret_cast<void*>(reinterpret_cast<uint8_t*>(const_cast<UObject*>(this)) + offset);
    }
};

static inline uintptr BaseAddress = 0;
static inline uintptr SetBaseAddress(uintptr b) { return BaseAddress = b; }
static inline void* Addr(uintptr rva) { return reinterpret_cast<void*>(BaseAddress + rva); }

} // namespace SDK
'''

    def emitted_enums(self, paths):
        out = ["#pragma once", "#include <cstdint>", "", "namespace SDK {"]
        for path in paths:
            o = self.s.enums[path]
            cpp = "E" + sanitize(name_of(o))
            names = o.get("names") or []
            underlying = self.s.enum_underlying(path, o)
            out.append(f"enum class {cpp} : {underlying} {{")
            for n, v in names:
                out.append(f"    {sanitize(n)} = {v},")
            out.append("};")
            out.append("")
        out.append("} // namespace SDK")
        out.append("")
        return "\n".join(out)

    def emitted_fwd(self, enums, structs, classes):
        out = ["#pragma once", "#include <cstdint>", "", "namespace SDK {"]
        for path in enums:
            o = self.s.enums[path]
            cpp = "E" + sanitize(name_of(o))
            underlying = self.s.enum_underlying(path, o)
            out.append(f"enum class {cpp} : {underlying};")
        for path in structs:
            out.append(f"struct F{sanitize(name_of(self.s.structs[path]))};")
        seen = set()
        for path in structs:
            o = self.s.structs[path]
            for r in self.s.ref_paths(o):
                if r in self.s.classes and r not in seen:
                    seen.add(r)
                    out.append(f"struct U{sanitize(name_of(self.s.classes[r]))};")
        for path in classes:
            o = self.s.classes[path]
            for r in self.s.ref_paths(o):
                if r in self.s.classes and r not in seen:
                    seen.add(r)
                    out.append(f"struct U{sanitize(name_of(self.s.classes[r]))};")
        for path in classes:
            if path not in seen:
                out.append(f"struct U{sanitize(name_of(self.s.classes[path]))};")
        out.append("} // namespace SDK")
        out.append("")
        return "\n".join(out)

    def stagger(self, props):
        groups = {}
        order = []
        for p in props:
            off = p.get("offset", 0)
            if off not in groups:
                groups[off] = []
                order.append(off)
            groups[off].append(p)
        return order, groups

    def emit_members(self, out, props, total_size, indent="    ", base=0):
        order, groups = self.stagger(props)
        cursor = base
        for off in sorted(order):
            group = sorted(groups[off], key=lambda p: p.get("size", 0), reverse=True)
            main = group[0]
            if off > cursor:
                out.append(f"{indent}opaque_t<{off - cursor}> _pad{off};")
            cpp = self.s.cpp_type(main)
            nm = sanitize(main.get("name", "_"))
            inner = cpp.strip()
            for tag in ("TArray<", "opaque_t<"):
                if inner.startswith(tag):
                    inner = inner[len(tag):].rstrip(">")
                    break
            if nm == cpp.split("<", 1)[0] or nm == inner:
                nm += "_"
            array_dim = main.get("array_dim") or 1
            decl = f"{cpp} {nm}[{array_dim}];" if array_dim > 1 else f"{cpp} {nm};"
            out.append(f"{indent}{decl} // @{off:#x} {main['type']} size={main['size']}")
            for extra in group[1:]:
                exn = sanitize(extra.get("name", "_"))
                out.append(f"{indent}// shared offset {off:#x}: {exn} ({extra['type']}) ByteOffset={extra.get('byte_offset')} Bit={extra.get('field_mask')}")
            cursor = off + main.get("size", 0)
        if total_size and cursor < total_size:
            out.append(f"{indent}opaque_t<{total_size - cursor}> _padEnd;")
        if not props:
            out.append(f"{indent}opaque_t<{total_size or 1}> core;")

    def _with_typename(self, cpp):
        self._current_typename = cpp
        return cpp

    def struct_value_deps(self, path):
        o = self.s.structs[path]
        deps = set()
        if o.get("super_struct") in self.s.structs:
            deps.add(o["super_struct"])
        for p in o.get("properties") or []:
            if p and p.get("type") == "StructProperty" and p.get("struct") in self.s.structs:
                deps.add(p["struct"])
        return deps

    def topo_structs(self, paths):
        remaining = list(paths)
        done = set()
        result = []
        while remaining:
            progress = False
            i = 0
            while i < len(remaining):
                path = remaining[i]
                deps = self.struct_value_deps(path) & set(paths)
                if deps <= done:
                    result.append(path)
                    remaining.pop(i)
                    done.add(path)
                    progress = True
                else:
                    i += 1
            if not progress:
                result.extend(remaining)
                remaining.clear()
        return result

    def emitted_structs(self, paths):
        out = ["#pragma once", '#include "BasicTypes.hpp"', '#include "Fwd.hpp"', "", "namespace SDK {"]
        pathset = set(paths)
        for path in self.topo_structs(paths):
            o = self.s.structs[path]
            cpp = self._with_typename("F" + sanitize(name_of(o)))
            tsize = o.get("properties_size") or 1
            sup = o.get("super_struct")
            base = 0
            suffix = ""
            if sup in pathset:
                base = self.s.structs[sup].get("properties_size") or 0
                suffix = f" : public F{sanitize(name_of(self.s.structs[sup]))}"
            out.append(f"struct {cpp}{suffix} {{")
            self.emit_members(out, o.get("properties") or [], o.get("properties_size") or 0, base=base)
            out.append("};")
            out.append(f"static_assert(sizeof({cpp}) >= {tsize}, \"layout small\");")
            out.append("")
        out.append("} // namespace SDK")
        out.append("")
        return "\n".join(out)

    def class_base(self, path, pathset):
        o = self.s.classes[path]
        if path in ("CoreUObject.Object", "CoreUObject.UObject") or name_of(o) == "Object" and path.startswith("/Script/CoreUObject"):
            return None
        seen = set()
        sup = o.get("super_struct")
        while sup and sup in self.s.classes and sup not in seen:
            if sup in pathset:
                return "U" + sanitize(name_of(self.s.classes[sup]))
            seen.add(sup)
            o = self.s.classes[sup]
            sup = o.get("super_struct")
        return "UObject"

    def emitted_classes(self, paths):
        out = ["#pragma once", '#include "Enums.hpp"', '#include "Structs.hpp"', "", "namespace SDK {"]
        pathset = set(paths)
        for path in paths:
            o = self.s.classes[path]
            cpp = self._with_typename("U" + sanitize(name_of(o)))
            if cpp == "UObject" and not o.get("super_struct"):
                continue
            sup = self.class_base(path, pathset)
            tsize = o.get("properties_size") or 1
            out.append(f"struct {cpp}{':' if sup else ''}{' ' if sup else ''}{sup if sup else ''} {{")
            fs = [f for f in self.s.objs.values() if f.get("outer") == path and f["type"] == "Function"]
            for fn in fs:
                rva = int(fn.get("func", "0x0"), 16) - self.s.image_base if fn.get("func") else 0
                out.append(f"    // func {name_of(fn)}: RVA {rva:#x}")
            self.emit_members(out, o.get("properties") or [], o.get("properties_size") or 0)
            out.append("};")
            out.append(f"static_assert(sizeof({cpp}) >= {tsize}, \"layout small\");")
            out.append("")
        out.append("} // namespace SDK")
        out.append("")
        return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="jmap -> C++ layout SDK")
    ap.add_argument("--jmap", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--modules", default="", help="comma separated. empty = all")
    ap.add_argument("--no-basic", action="store_true")
    args = ap.parse_args()

    sdk = SDK(args.jmap)
    sdk.classify()
    modules = {m for m in args.modules.split(",") if m}
    roots, structs, enums = sdk.resolve(modules)

    order = list(roots)
    visited = set()
    emitted_classes = []

    def visit(p):
        if p in visited:
            return
        visited.add(p)
        o = sdk.classes[p]
        sup = o.get("super_struct")
        if sup and sup in sdk.classes and sup in roots:
            visit(sup)
        emitted_classes.append(p)

    for p in order:
        visit(p)

    em = Emitter(sdk)
    os.makedirs(args.out, exist_ok=True)
    if not args.no_basic:
        with open(os.path.join(args.out, "BasicTypes.hpp"), "w") as f:
            f.write(em.basic_types())
    with open(os.path.join(args.out, "Fwd.hpp"), "w") as f:
        f.write(em.emitted_fwd(enums, structs, emitted_classes))
    with open(os.path.join(args.out, "Enums.hpp"), "w") as f:
        f.write(em.emitted_enums(enums))
    with open(os.path.join(args.out, "Structs.hpp"), "w") as f:
        f.write(em.emitted_structs(structs))
    with open(os.path.join(args.out, "Classes.hpp"), "w") as f:
        f.write(em.emitted_classes(emitted_classes))
    print(f"engine={sdk.engine} classes={len(emitted_classes)} structs={len(structs)} enums={len(enums)}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()