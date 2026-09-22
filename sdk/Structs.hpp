#pragma once
#include "BasicTypes.hpp"
#include "Fwd.hpp"

namespace SDK {
struct FTinyTopoA {
    float V; // @0x0 FloatProperty size=4
};
static_assert(sizeof(FTinyTopoA) >= 4, "layout small");

struct FTinyBase {
    float Base; // @0x0 FloatProperty size=4
};
static_assert(sizeof(FTinyBase) >= 4, "layout small");

struct FTinyDerived : public FTinyBase {
    float Extra; // @0x4 FloatProperty size=4
};
static_assert(sizeof(FTinyDerived) >= 8, "layout small");

struct FVector {
    float X; // @0x0 FloatProperty size=4
    float Y; // @0x4 FloatProperty size=4
    float Z; // @0x8 FloatProperty size=4
    opaque_t<12> _padEnd;
};
static_assert(sizeof(FVector) >= 24, "layout small");

struct FTinyTopoB {
    FTinyTopoA A; // @0x0 StructProperty size=4
};
static_assert(sizeof(FTinyTopoB) >= 4, "layout small");

struct FTinyOrphan {
    opaque_t<8> _pad8;
    float Own; // @0x8 FloatProperty size=4
};
static_assert(sizeof(FTinyOrphan) >= 12, "layout small");

struct FTinyNames {
    FName FName_; // @0x0 NameProperty size=8
    FName Title; // @0x8 NameProperty size=8
};
static_assert(sizeof(FTinyNames) >= 16, "layout small");

struct FTinyTopoC {
    FTinyTopoB B; // @0x0 StructProperty size=4
};
static_assert(sizeof(FTinyTopoC) >= 4, "layout small");

} // namespace SDK
