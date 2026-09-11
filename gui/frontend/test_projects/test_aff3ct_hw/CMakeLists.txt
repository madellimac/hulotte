cmake_minimum_required(VERSION 3.10)
project(test_aff3ct_hw LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================
# DEPENDENCIES
# ============================================================

set(STREAMPU_ROOT "/home/cleroux/PROJECTS/hulotte/streampu" CACHE PATH "Path to StreamPU")



set(AFF3CT_ROOT "/home/cleroux/PROJECTS/hulotte/aff3ct" CACHE PATH "Path to AFF3CT")



# Verilator support (CMake config provided by Verilator 5+)
find_package(verilator REQUIRED)
find_package(Threads REQUIRED)


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


# Hardware simulation includes
include_directories(common/hw)



add_definitions(-DHULOTTE_USE_STREAMPU)

# ============================================================
# PROJECT SOURCES
# ============================================================



# Hardware Modules - automatically discover all .sv files in src/hw/
# Each module MUST implement the standard ready/valid interface.
# Files ending in 'Core.sv' are sub-modules (not Verilator top-levels) and are
# excluded from this list — they are included as extra sources by their wrapper.
file(GLOB HW_BLOCKS "src/hw/*.sv")
list(FILTER HW_BLOCKS EXCLUDE REGEX ".*Core\.sv$")

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
    get_filename_component(BLOCK_DIR ${HW_BLOCK} DIRECTORY)

    # Include companion *Core.sv if it exists (UART-wrapped modules)
    set(CORE_FILE "${BLOCK_DIR}/${BLOCK_NAME}Core.sv")
    if(EXISTS "${CORE_FILE}")
        set(EXTRA_SOURCES ${CORE_FILE})
    else()
        set(EXTRA_SOURCES "")
    endif()

    # Create Verilator library for this block
    add_library(VerilatorModel_${BLOCK_NAME} STATIC ${HW_BLOCK})
    verilate(VerilatorModel_${BLOCK_NAME}
        SOURCES ${HW_COMMON_SRC} ${HW_BLOCK} ${EXTRA_SOURCES}
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



# Common StreamPU support modules copied to common/sw
file(GLOB COMMON_SW_SOURCES "common/sw/*.cpp")
if(NOT Boost_FOUND)
    list(FILTER COMMON_SW_SOURCES EXCLUDE REGEX ".*(SerialPort|UartFrameIO)\\.cpp$")
endif()

if(COMMON_SW_SOURCES)
    add_library(test_aff3ct_hw_common STATIC ${COMMON_SW_SOURCES})
    target_include_directories(test_aff3ct_hw_common PUBLIC common/sw)
    target_link_libraries(test_aff3ct_hw_common PUBLIC ${HULOTTE_LIBS})

    if(Boost_FOUND)
        target_include_directories(test_aff3ct_hw_common PUBLIC ${Boost_INCLUDE_DIRS})
        target_link_libraries(test_aff3ct_hw_common PUBLIC ${Boost_LIBRARIES})
    endif()

    set(COMMON_MODULE_LIBS test_aff3ct_hw_common)
else()
    set(COMMON_MODULE_LIBS "")
endif()


# Custom modules - automatically discover all .cpp files in src/custom/ (glob pattern)
file(GLOB CUSTOM_SOURCES "src/custom/*.cpp")
if(CUSTOM_SOURCES)
    add_library(test_aff3ct_hw_custom STATIC ${CUSTOM_SOURCES})
    target_include_directories(test_aff3ct_hw_custom PUBLIC src)
    target_link_libraries(test_aff3ct_hw_custom PUBLIC ${HULOTTE_LIBS})
    set(CUSTOM_MODULE_LIBS test_aff3ct_hw_custom)
else()
    set(CUSTOM_MODULE_LIBS "")
endif()

# Main executable
add_executable(test_aff3ct_hw src/main.cpp)

# Include directories for common modules (including SerialPort if Boost available)
if(Boost_FOUND)
    target_include_directories(test_aff3ct_hw PRIVATE ${Boost_INCLUDE_DIRS})
endif()

target_link_libraries(test_aff3ct_hw ${HULOTTE_LIBS} ${COMMON_MODULE_LIBS} ${CUSTOM_MODULE_LIBS})


# Link all discovered hardware blocks
if(DEFINED HW_MODELS_LIST)
    target_link_libraries(test_aff3ct_hw ${HW_MODELS_LIST} Threads::Threads)
endif()


# Link Boost if found
if(Boost_FOUND)
    target_link_libraries(test_aff3ct_hw ${Boost_LIBRARIES})
endif()