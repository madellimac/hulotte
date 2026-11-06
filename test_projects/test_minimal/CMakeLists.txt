cmake_minimum_required(VERSION 3.10)
project(test_minimal LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================
# DEPENDENCIES
# ============================================================

set(STREAMPU_ROOT "/Users/cleroux/Documents/work/recherche/PROJECT/hulotte/streampu" CACHE PATH "Path to StreamPU")






set(HULOTTE_ROOT "/Users/cleroux/Documents/work/recherche/PROJECT/hulotte" CACHE PATH "Path to Hulotte")

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
endif()




add_definitions(-DHULOTTE_USE_STREAMPU)

# ============================================================
# PROJECT SOURCES
# ============================================================





# Main executable
add_executable(test_minimal src/main.cpp)
target_link_libraries(test_minimal ${HULOTTE_LIBS})


