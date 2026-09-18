cmake_minimum_required(VERSION 3.21)

project(HulotteDependencies NONE)

include(ExternalProject)

option(HULOTTE_INSTALL_STREAMPU "Build standalone StreamPU" OFF)
option(HULOTTE_INSTALL_AFF3CT "Build AFF3CT with its bundled StreamPU" OFF)
option(HULOTTE_INSTALL_SURFER "Reserve the optional Surfer dependency" OFF)

set(HULOTTE_STREAMPU_REPOSITORY "https://github.com/aff3ct/streampu.git" CACHE STRING "StreamPU Git repository")
set(HULOTTE_STREAMPU_TAG "master" CACHE STRING "StreamPU Git tag or branch")
set(HULOTTE_AFF3CT_REPOSITORY "https://github.com/aff3ct/aff3ct.git" CACHE STRING "AFF3CT Git repository")
set(HULOTTE_AFF3CT_TAG "master" CACHE STRING "AFF3CT Git tag or branch")
set(HULOTTE_DEPENDENCY_SOURCE_DIR "${CMAKE_BINARY_DIR}/dependencies/src" CACHE PATH "Dependency source directory")
set(HULOTTE_DEPENDENCY_BINARY_DIR "${CMAKE_BINARY_DIR}/dependencies/build" CACHE PATH "Dependency build directory")
set(HULOTTE_MANIFEST "${CMAKE_BINARY_DIR}/hulotte-dependencies.json" CACHE FILEPATH "Generated dependency manifest")

file(MAKE_DIRECTORY "${HULOTTE_DEPENDENCY_SOURCE_DIR}" "${HULOTTE_DEPENDENCY_BINARY_DIR}")

set(_hulotte_targets)
set(_streampu_root "")
set(_aff3ct_root "")
set(_stream_pu_mode "none")
if(HULOTTE_INSTALL_STREAMPU)
    set(_stream_pu_mode "standalone")
endif()

if(HULOTTE_INSTALL_STREAMPU)
    set(_install_stream_pu_json "true")
else()
    set(_install_stream_pu_json "false")
endif()
if(HULOTTE_INSTALL_AFF3CT)
    set(_install_aff3ct_json "true")
else()
    set(_install_aff3ct_json "false")
endif()
if(HULOTTE_INSTALL_SURFER)
    set(_install_surfer_json "true")
else()
    set(_install_surfer_json "false")
endif()

if(HULOTTE_INSTALL_STREAMPU)
    set(_streampu_root "${HULOTTE_DEPENDENCY_SOURCE_DIR}/streampu")
    ExternalProject_Add(hulotte_streampu
        GIT_REPOSITORY "${HULOTTE_STREAMPU_REPOSITORY}"
        GIT_TAG "${HULOTTE_STREAMPU_TAG}"
        GIT_SHALLOW TRUE
        SOURCE_DIR "${_streampu_root}"
        BINARY_DIR "${HULOTTE_DEPENDENCY_BINARY_DIR}/streampu"
        CMAKE_ARGS
            -DCMAKE_BUILD_TYPE=Release
            -DCMAKE_INSTALL_PREFIX=<INSTALL_DIR>
            -DSPU_COMPILE_STATIC_LIB=ON
            -DSPU_COMPILE_SHARED_LIB=OFF
            -DSPU_LINK_HWLOC=OFF
        BUILD_COMMAND ${CMAKE_COMMAND} --build <BINARY_DIR> --parallel
        INSTALL_COMMAND ""
        UPDATE_DISCONNECTED TRUE
    )
    list(APPEND _hulotte_targets hulotte_streampu)
endif()

if(HULOTTE_INSTALL_AFF3CT)
    set(_aff3ct_root "${HULOTTE_DEPENDENCY_SOURCE_DIR}/aff3ct")
    ExternalProject_Add(hulotte_aff3ct
        GIT_REPOSITORY "${HULOTTE_AFF3CT_REPOSITORY}"
        GIT_TAG "${HULOTTE_AFF3CT_TAG}"
        GIT_SHALLOW TRUE
        SOURCE_DIR "${_aff3ct_root}"
        BINARY_DIR "${HULOTTE_DEPENDENCY_BINARY_DIR}/aff3ct"
        CMAKE_ARGS
            -DCMAKE_BUILD_TYPE=Release
            -DCMAKE_INSTALL_PREFIX=<INSTALL_DIR>
            -DAFF3CT_COMPILE_EXE=OFF
            -DAFF3CT_COMPILE_STATIC_LIB=ON
            -DAFF3CT_COMPILE_SHARED_LIB=OFF
            -DAFF3CT_LINK_HWLOC=OFF
            -DAFF3CT_EXT_STRINGS=ON
            -DSPU_COMPILE_STATIC_LIB=ON
        BUILD_COMMAND ${CMAKE_COMMAND} --build <BINARY_DIR> --parallel
        INSTALL_COMMAND ""
        UPDATE_DISCONNECTED TRUE
    )
    list(APPEND _hulotte_targets hulotte_aff3ct)
endif()

if(HULOTTE_INSTALL_SURFER)
    message(STATUS "Surfer is selected; its binary download will be added in a later dependency phase.")
endif()

if(NOT _hulotte_targets)
    message(FATAL_ERROR "Select at least one native dependency: HULOTTE_INSTALL_STREAMPU or HULOTTE_INSTALL_AFF3CT")
endif()

add_custom_target(hulotte-dependencies ALL DEPENDS ${_hulotte_targets})

file(WRITE "${HULOTTE_MANIFEST}" "{\n")
file(APPEND "${HULOTTE_MANIFEST}" "  \"stream_pu_mode\": \"${_stream_pu_mode}\",\n")
file(APPEND "${HULOTTE_MANIFEST}" "  \"install_streampu\": ${_install_stream_pu_json},\n")
file(APPEND "${HULOTTE_MANIFEST}" "  \"install_aff3ct\": ${_install_aff3ct_json},\n")
file(APPEND "${HULOTTE_MANIFEST}" "  \"streampu_root\": \"${_streampu_root}\",\n")
file(APPEND "${HULOTTE_MANIFEST}" "  \"aff3ct_root\": \"${_aff3ct_root}\",\n")
file(APPEND "${HULOTTE_MANIFEST}" "  \"install_surfer\": ${_install_surfer_json}\n")
file(APPEND "${HULOTTE_MANIFEST}" "}\n")

add_custom_command(TARGET hulotte-dependencies POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E echo "Hulotte dependency manifest: ${HULOTTE_MANIFEST}"
)
