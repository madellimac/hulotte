cmake_minimum_required(VERSION 3.10)
project(test_aff3ct_custom LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================
# DEPENDENCIES
# ============================================================

set(STREAMPU_ROOT "/home/cleroux/PROJECTS/hulotte/streampu" CACHE PATH "Path to StreamPU")



set(AFF3CT_ROOT "/home/cleroux/PROJECTS/hulotte/aff3ct" CACHE PATH "Path to AFF3CT")




# Boost ASIO (for SerialPort/UartFrameIO modules)
find_package(Boost QUIET COMPONENTS system)
if(Boost_FOUND)
    message(STATUS "Found Boost: ${Boost_INCLUDE_DIRS}")
    add_definitions(-DHULOTTE_USE_BOOST_ASIO)
else()
    message(WARNING "Boost ASIO not found - SerialPort/UartFrameIO modules will not be available")
endif()

# ============================================================
# LOAD HULOTTE ENVIRONMENT
# ============================================================


# Configure AFF3CT paths
set(AFF3CT_INCLUDE_DIRS
    ${AFF3CT_ROOT}/include
    ${AFF3CT_ROOT}/src
    ${AFF3CT_ROOT}/lib/MIPP/src
    ${AFF3CT_ROOT}/lib/cli/src
    ${AFF3CT_ROOT}/lib/date/include/date
)
include_directories(${AFF3CT_INCLUDE_DIRS})

# Find AFF3CT library
file(GLOB AFF3CT_LIBRARY "${AFF3CT_ROOT}/build/lib/libaff3ct*.a")

if(AFF3CT_LIBRARY)
    message(STATUS "Found AFF3CT: ${AFF3CT_LIBRARY}")
    
    # When using AFF3CT, use the StreamPU headers/symbols bundled in AFF3CT
    # to avoid Diamond Dependency / ABI mismatches.
    set(STREAMPU_INCLUDE_DIRS
        ${AFF3CT_ROOT}/lib/streampu/include
        ${AFF3CT_ROOT}/lib/streampu/lib/rang/include
        ${AFF3CT_ROOT}/lib/streampu/lib/json/include
    )
    include_directories(${STREAMPU_INCLUDE_DIRS})
    
    # Link ONLY AFF3CT (it contains StreamPU symbols)
    set(HULOTTE_LIBS ${AFF3CT_LIBRARY})
    
    add_definitions(-DHULOTTE_USE_AFF3CT)
    add_definitions(-DAFF3CT_POLAR_BIT_PACKING)
    add_definitions(-DAFF3CT_MULTI_PREC)
    add_definitions(-DSPU_STACKTRACE)
else()
    message(WARNING "AFF3CT library not found! Falling back to standalone StreamPU.")
    
    # Standalone StreamPU
    set(STREAMPU_INCLUDE_DIRS
        ${STREAMPU_ROOT}/include
        ${STREAMPU_ROOT}/src
        ${STREAMPU_ROOT}/lib/rang/include
        ${STREAMPU_ROOT}/lib/json/include
    )
    include_directories(${STREAMPU_INCLUDE_DIRS})
    
    if(EXISTS "${STREAMPU_ROOT}/build/lib/libstreampu.a")
        set(HULOTTE_LIBS "${STREAMPU_ROOT}/build/lib/libstreampu.a")
    else()
        message(FATAL_ERROR "libstreampu.a not found at ${STREAMPU_ROOT}/build/lib/libstreampu.a")
    endif()
endif()


# Find cpptrace (optional, for better error messages)
find_library(CPPTRACE_LIBRARY NAMES cpptrace libcpptrace.a
    PATHS ${STREAMPU_ROOT}/build/lib/cpptrace/lib)

if(CPPTRACE_LIBRARY)
    list(APPEND HULOTTE_LIBS ${CPPTRACE_LIBRARY})
    include_directories(${STREAMPU_ROOT}/lib/cpptrace/include)
    add_definitions(-DSPU_STACKTRACE)
endif()


# SW support files (Comparator, etc.) — always available for StreamPU projects
include_directories(common/sw)




add_definitions(-DHULOTTE_USE_STREAMPU)

# ============================================================
# PROJECT SOURCES
# ============================================================





# Common StreamPU support modules copied to common/sw
file(GLOB COMMON_SW_SOURCES "common/sw/*.cpp")
if(NOT Boost_FOUND)
    list(FILTER COMMON_SW_SOURCES EXCLUDE REGEX ".*(SerialPort|UartFrameIO)\\.cpp$")
endif()

if(COMMON_SW_SOURCES)
    add_library(test_aff3ct_custom_common STATIC ${COMMON_SW_SOURCES})
    target_include_directories(test_aff3ct_custom_common PUBLIC common/sw)
    target_link_libraries(test_aff3ct_custom_common PUBLIC ${HULOTTE_LIBS})

    if(Boost_FOUND)
        target_include_directories(test_aff3ct_custom_common PUBLIC ${Boost_INCLUDE_DIRS})
        target_link_libraries(test_aff3ct_custom_common PUBLIC ${Boost_LIBRARIES})
    endif()

    set(COMMON_MODULE_LIBS test_aff3ct_custom_common)
else()
    set(COMMON_MODULE_LIBS "")
endif()


# Custom modules - automatically discover all .cpp files in src/custom/ (glob pattern)
file(GLOB CUSTOM_SOURCES "src/custom/*.cpp")
if(CUSTOM_SOURCES)
    add_library(test_aff3ct_custom_custom STATIC ${CUSTOM_SOURCES})
    target_include_directories(test_aff3ct_custom_custom PUBLIC src)
    target_link_libraries(test_aff3ct_custom_custom PUBLIC ${HULOTTE_LIBS})
    set(CUSTOM_MODULE_LIBS test_aff3ct_custom_custom)
else()
    set(CUSTOM_MODULE_LIBS "")
endif()

# Main executable
add_executable(test_aff3ct_custom src/main.cpp)

# Include directories for common modules (including SerialPort if Boost available)
if(Boost_FOUND)
    target_include_directories(test_aff3ct_custom PRIVATE ${Boost_INCLUDE_DIRS})
endif()

target_link_libraries(test_aff3ct_custom ${HULOTTE_LIBS} ${COMMON_MODULE_LIBS} ${CUSTOM_MODULE_LIBS})



# Link Boost if found
if(Boost_FOUND)
    target_link_libraries(test_aff3ct_custom ${Boost_LIBRARIES})
endif()