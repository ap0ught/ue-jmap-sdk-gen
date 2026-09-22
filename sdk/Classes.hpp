#pragma once
#include "Enums.hpp"
#include "Structs.hpp"

namespace SDK {
struct UTinyActor: UObject {
    FName Name; // @0x0 NameProperty size=8
    FTinyTopoA Pos; // @0x8 StructProperty size=4
    opaque_t<12> _padEnd;
};
static_assert(sizeof(UTinyActor) >= 24, "layout small");

struct UPopup: UObject {
    FName Text; // @0x0 NameProperty size=8
};
static_assert(sizeof(UPopup) >= 8, "layout small");

struct UTinyPlayer: UObject {
    // func TinyPlayer:Hello: RVA 0x1234560
    // func TinyPlayer:VerifyFunc: RVA 0xaaaaaa
    int32_t Health; // @0x0 IntProperty size=4
    opaque_t<4> _pad8;
    ETinyLevel Level; // @0x8 EnumProperty size=4
    ETinyByte Status; // @0xc ByteProperty size=1
    opaque_t<3> _pad16;
    ETinyBig Big; // @0x10 EnumProperty size=4
    opaque_t<4> _pad24;
    opaque_t<40> SoftMesh; // @0x18 SoftObjectProperty size=40
    opaque_t<40> SoftClass; // @0x40 SoftClassProperty size=40
    TObjectPtr<UTinyActor> Spawner; // @0x68 ObjectProperty size=8
    TArray<int32_t> Items; // @0x70 ArrayProperty size=16
    FVector Pos; // @0x80 StructProperty size=24
    FTinyOrphan Orphan; // @0x98 StructProperty size=12
    FTinyTopoC TopoC; // @0xa4 StructProperty size=4
    FTinyNames Names; // @0xa8 StructProperty size=16
    FTinyDerived Derived; // @0xb8 StructProperty size=8
    FTinyBase Base; // @0xc0 StructProperty size=4
    opaque_t<4> _padEnd;
};
static_assert(sizeof(UTinyPlayer) >= 200, "layout small");

} // namespace SDK
