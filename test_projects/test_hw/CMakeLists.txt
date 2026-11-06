cmake_minimum_required(VERSION 3.10)
project(test_hw LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================
# DEPENDENCIES
# ============================================================

set(STREAMPU_ROOT "/Users/cleroux/Documents/work/recherche/PROJECT/hulotte/streampu" CACHE PATH "Path to StreamPU")





# Verilator
find_package(Verilator REQUIRED)
find_package(Threads REQUIRED)


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


# Hardware Simulation Includes
include_directories(common/hw)
include_directories(common/sw)



add_definitions(-DHULOTTE_USE_STREAMPU)

# ============================================================
# PROJECT SOURCES
# ============================================================



# Hardware Module (Verilog)
set(VERILOG_SRC src/hw/Top_Level.sv)

add_library(VTop_Level STATIC ${VERILOG_SRC})
set_property(TARGET VTop_Level PROPERTY LINKER_LANGUAGE CXX)

# Verilate the module (generate C++)
# This creates a library VTop_Level__ALL.a
verilate(VTop_Level
    SOURCES ${VERILOG_SRC}
    TOP_MODULE Top_Level
    INCLUDE_DIRS src/hw
    VERILATOR_ARGS -Wno-fatal --trace
)

# Shared Simulation Wrapper
add_library(VerilatorSimulation STATIC
    common/hw/VerilatorSimulation.cpp
)
target_include_directories(VerilatorSimulation PUBLIC common/hw)

# Link the Verilated model to our wrapper
target_link_libraries(VerilatorSimulation PUBLIC VTop_Level)



# Main executable
add_executable(test_hw src/main.cpp)
target_link_libraries(test_hw ${HULOTTE_LIBS})



# Link Hardware Simulation
target_link_libraries(test_hw VerilatorSimulation Threads::Threads)
