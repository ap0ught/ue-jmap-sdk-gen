#pragma once
#include <cstdint>

namespace SDK {
enum class ETinyByte : uint8_t {
    Off = 0,
    On = 1,
};

enum class ETinyLevel : int32_t {
    Low = 0,
    Mid = 2,
    High = 4,
};

enum class ETinyBig : uint32_t {
    Zero = 0,
    Max = 4294967295,
};

} // namespace SDK
