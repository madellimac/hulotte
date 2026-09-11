cmake_minimum_required(VERSION 3.10)
project(test_custom LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================
# DEPENDENCIES
# ============================================================

set(STREAMPU_ROOT "/home/cleroux/PROJECTS/hulotte/streampu" CACHE PATH "Path to StreamPU")






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


# Standard StreamPU Only

# Configure StreamPU paths
set(STREAMPU_INCLUDE_DIRS
    ${STREAMPU_ROOT}/include
    ${STREAMPU_ROOT}/src
    ${STREAMPU_ROOT}/lib/rang/include
    ${STREAMPU_ROOT}/lib/json/include
)
include_directories(${STREAMPU_INCLUDE_DIRS})

# Find StreamPU library
if(EXISTS "${STREAMPU_ROOT}/build/lib/libstreampu.a")
    set(HULOTTE_LIBS "${STREAMPU_ROOT}/build/lib/libstreampu.a")
else()
    message(FATAL_ERROR "libstreampu.a not found at ${STREAMPU_ROOT}/build/lib/libstreampu.a")
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
    add_library(test_custom_common STATIC ${COMMON_SW_SOURCES})
    target_include_directories(test_custom_common PUBLIC common/sw)
    target_link_libraries(test_custom_common PUBLIC ${HULOTTE_LIBS})

    if(Boost_FOUND)
        target_include_directories(test_custom_common PUBLIC ${Boost_INCLUDE_DIRS})
        target_link_libraries(test_custom_common PUBLIC ${Boost_LIBRARIES})
    endif()

    set(COMMON_MODULE_LIBS test_custom_common)
else()
    set(COMMON_MODULE_LIBS "")
endif()


# Custom modules - automatically discover all .cpp files in src/custom/ (glob pattern)
file(GLOB CUSTOM_SOURCES "src/custom/*.cpp")
if(CUSTOM_SOURCES)
    add_library(test_custom_custom STATIC ${CUSTOM_SOURCES})
    target_include_directories(test_custom_custom PUBLIC src)
    target_link_libraries(test_custom_custom PUBLIC ${HULOTTE_LIBS})
    set(CUSTOM_MODULE_LIBS test_custom_custom)
else()
    set(CUSTOM_MODULE_LIBS "")
endif()

# Main executable
add_executable(test_custom src/main.cpp)

# Include directories for common modules (including SerialPort if Boost available)
if(Boost_FOUND)
    target_include_directories(test_custom PRIVATE ${Boost_INCLUDE_DIRS})
endif()

target_link_libraries(test_custom ${HULOTTE_LIBS} ${COMMON_MODULE_LIBS} ${CUSTOM_MODULE_LIBS})



# Link Boost if found
if(Boost_FOUND)
    target_link_libraries(test_custom ${Boost_LIBRARIES})
endif()