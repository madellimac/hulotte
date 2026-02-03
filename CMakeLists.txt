cmake_minimum_required(VERSION 3.10)
project(Hulotte VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================
# OPTIONS CONFIGURABLES
# ============================================================
option(HULOTTE_USE_STREAMPU   "Use StreamPU library (required)" ON)
option(HULOTTE_USE_AFF3CT     "Use AFF3CT library" OFF)
option(HULOTTE_BUILD_EXAMPLES "Build example programs" ON)

# ============================================================
# CHEMINS PAR DÉFAUT (modifiables via -D)
# ============================================================
set(STREAMPU_ROOT "${CMAKE_SOURCE_DIR}/../aff3ct/lib/streampu" 
    CACHE PATH "Path to StreamPU")
set(AFF3CT_ROOT "${CMAKE_SOURCE_DIR}/../aff3ct" 
    CACHE PATH "Path to AFF3CT")

# ============================================================
# VÉRIFICATION StreamPU (obligatoire)
# ============================================================
if(HULOTTE_USE_STREAMPU)
    message(STATUS "Looking for StreamPU at ${STREAMPU_ROOT}...")
    
    if(NOT EXISTS "${STREAMPU_ROOT}/include/streampu.hpp")
        message(FATAL_ERROR 
            "StreamPU not found at ${STREAMPU_ROOT}\n"
            "Please set -DSTREAMPU_ROOT=/path/to/streampu")
    endif()
    
    # Chemins d'inclusion StreamPU
    set(STREAMPU_INCLUDE_DIRS
        ${STREAMPU_ROOT}/include
        ${STREAMPU_ROOT}/src
        ${STREAMPU_ROOT}/lib/rang/include
        ${STREAMPU_ROOT}/lib/json/include
    )
    include_directories(${STREAMPU_INCLUDE_DIRS})
    
    # Bibliothèque StreamPU
    find_library(STREAMPU_LIBRARY 
        NAMES libstreampu.a streampu
        PATHS ${STREAMPU_ROOT}/build/lib ${STREAMPU_ROOT}/build_release/lib
        NO_DEFAULT_PATH
    )
    
    if(NOT STREAMPU_LIBRARY)
        message(FATAL_ERROR 
            "libstreampu.a not found. Please build StreamPU:\n"
            "  cd ${STREAMPU_ROOT}\n"
            "  mkdir build && cd build\n"
            "  cmake .. && make -j")
    endif()
    
    set(HULOTTE_LIBS ${STREAMPU_LIBRARY})
    add_definitions(-DHULOTTE_USE_STREAMPU)
    message(STATUS "StreamPU found: ${STREAMPU_LIBRARY}")
    
    # cpptrace (nécessaire si StreamPU a été construit avec stacktrace)
    find_library(CPPTRACE_LIBRARY NAMES cpptrace libcpptrace.a
        PATHS
          ${STREAMPU_ROOT}/build/lib/cpptrace/lib
          ${STREAMPU_ROOT}/build/streampu/lib/cpptrace/lib
          ${STREAMPU_ROOT}/lib/cpptrace/lib
          ${AFF3CT_ROOT}/build/lib/streampu/lib/cpptrace/lib
        NO_DEFAULT_PATH)
    if(NOT CPPTRACE_LIBRARY)
      file(GLOB_RECURSE CPPTRACE_LIBRARY "${STREAMPU_ROOT}/**/libcpptrace.a")
    endif()
    if(CPPTRACE_LIBRARY)
      message(STATUS "cpptrace found: ${CPPTRACE_LIBRARY}")
      include_directories(${STREAMPU_ROOT}/lib/cpptrace/include)
      list(APPEND HULOTTE_LIBS ${CPPTRACE_LIBRARY})  # après streampu (ordre de lien)
    else()
      message(WARNING "libcpptrace.a introuvable. Rebuild StreamPU sans stacktrace ou fournis libcpptrace.a.")
    endif()
endif()

# ============================================================
# VÉRIFICATION AFF3CT (optionnel)
# ============================================================
if(HULOTTE_USE_AFF3CT)
    message(STATUS "Looking for AFF3CT at ${AFF3CT_ROOT}...")
    
    if(NOT EXISTS "${AFF3CT_ROOT}/include/aff3ct.hpp")
        message(WARNING 
            "AFF3CT not found at ${AFF3CT_ROOT}\n"
            "Set -DAFF3CT_ROOT=/path/to/aff3ct or disable with -DHULOTTE_USE_AFF3CT=OFF")
        set(HULOTTE_USE_AFF3CT OFF CACHE BOOL "" FORCE)
    else()
        # Chemins d'inclusion AFF3CT
        set(AFF3CT_INCLUDE_DIRS
            ${AFF3CT_ROOT}/include
            ${AFF3CT_ROOT}/src
            ${AFF3CT_ROOT}/lib/MIPP/src
            ${AFF3CT_ROOT}/lib/cli/src
            ${AFF3CT_ROOT}/lib/date/include/date
        )
        include_directories(${AFF3CT_INCLUDE_DIRS})
        
        # Bibliothèque AFF3CT
        file(GLOB AFF3CT_LIBRARY "${AFF3CT_ROOT}/build/lib/libaff3ct*.a")
        if(NOT AFF3CT_LIBRARY)
            message(FATAL_ERROR 
                "libaff3ct*.a not found. Please build AFF3CT:\n"
                "  cd ${AFF3CT_ROOT}\n"
                "  mkdir build && cd build\n"
                "  cmake .. -DAFF3CT_COMPILE_STATIC_LIB=ON && make -j")
        endif()
        
        list(APPEND HULOTTE_LIBS ${AFF3CT_LIBRARY})
        add_definitions(-DHULOTTE_USE_AFF3CT)
        add_definitions(-DAFF3CT_POLAR_BIT_PACKING)
        add_definitions(-DAFF3CT_MULTI_PREC)
        message(STATUS "AFF3CT found: ${AFF3CT_LIBRARY}")
    endif()
endif()

# ============================================================
# EXEMPLES
# ============================================================
if(HULOTTE_BUILD_EXAMPLES)
    add_subdirectory(examples)
endif()

# ============================================================
# RÉSUMÉ
# ============================================================
message(STATUS "")
message(STATUS "========================================")
message(STATUS "Hulotte Configuration")
message(STATUS "========================================")
message(STATUS "  StreamPU support : ${HULOTTE_USE_STREAMPU}")
message(STATUS "  AFF3CT support   : ${HULOTTE_USE_AFF3CT}")
message(STATUS "  Build examples   : ${HULOTTE_BUILD_EXAMPLES}")
message(STATUS "========================================")
message(STATUS "")