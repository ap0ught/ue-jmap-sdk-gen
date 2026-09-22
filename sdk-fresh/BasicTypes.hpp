#pragma once
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
