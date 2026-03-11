cmake_minimum_required(VERSION 3.10)
project(test_hw LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================
# DEPENDENCIES
# ============================================================

set(STREAMPU_ROOT "/home/cleroux/PROJECTS/hulotte/streampu" CACHE PATH "Path to StreamPU")





# Verilator support (CMake config provided by Verilator 5+)
find_package(verilator REQUIRED)
find_package(Threads REQUIRED)


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


# Hardware Simulation Includes
include_directories(common/hw)
include_directories(common/sw)



add_definitions(-DHULOTTE_USE_STREAMPU)

# ============================================================
# PROJECT SOURCES
# ============================================================



# Hardware Modules - automatically discover all .sv files in src/hw/
# Each module MUST implement the standard ready/valid interface
file(GLOB HW_BLOCKS "src/hw/*.sv")

# Common Verilog sources (UART utilities, etc.)
set(HW_COMMON_SRC
    common/hw/UART_fifoed_send_V1.sv
    common/hw/uart_recv.sv
)

# Store list of hardware models to link later
set(HW_MODELS_LIST)

# Generate a Verilator model for each hardware block
foreach(HW_BLOCK ${HW_BLOCKS})
    # Extract module name from filename (e.g., increment.sv -> increment)
    get_filename_component(BLOCK_NAME ${HW_BLOCK} NAME_WE)
    
    # Create Verilator library for this block
    add_library(VerilatorModel_${BLOCK_NAME} STATIC ${HW_BLOCK})
    verilate(VerilatorModel_${BLOCK_NAME}
        SOURCES ${HW_COMMON_SRC} ${HW_BLOCK}
        TOP_MODULE ${BLOCK_NAME}
        PREFIX VModel_${BLOCK_NAME}
        TRACE
        VERILATOR_ARGS -Wno-fatal
    )
    
    # Include directories for generated Verilator headers
    target_include_directories(VerilatorModel_${BLOCK_NAME} PUBLIC common/hw)
    target_include_directories(VerilatorModel_${BLOCK_NAME} PUBLIC 
        ${CMAKE_CURRENT_BINARY_DIR}/CMakeFiles/VerilatorModel_${BLOCK_NAME}.dir)
    target_link_libraries(VerilatorModel_${BLOCK_NAME} PUBLIC Threads::Threads)
    
    # Add to list for linking after executable is created
    list(APPEND HW_MODELS_LIST VerilatorModel_${BLOCK_NAME})
endforeach()


# Custom modules - automatically discover all .cpp files in src/custom/ (glob pattern)
file(GLOB CUSTOM_SOURCES "src/custom/*.cpp")
if(CUSTOM_SOURCES)
    add_library(test_hw_custom STATIC ${CUSTOM_SOURCES})
    target_include_directories(test_hw_custom PUBLIC src)
    target_link_libraries(test_hw_custom PUBLIC ${HULOTTE_LIBS})
    set(CUSTOM_MODULE_LIBS test_hw_custom)
else()
    set(CUSTOM_MODULE_LIBS "")
endif()

# Main executable
add_executable(test_hw src/main.cpp)
target_link_libraries(test_hw ${HULOTTE_LIBS} ${CUSTOM_MODULE_LIBS})


# Link all discovered hardware blocks
if(DEFINED HW_MODELS_LIST)
    target_link_libraries(test_hw ${HW_MODELS_LIST} Threads::Threads)
endif()
