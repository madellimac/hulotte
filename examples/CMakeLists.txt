# Custom module library for examples
add_library(hulotte_custom STATIC custom/MyCustomModule.cpp)
target_include_directories(hulotte_custom PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(hulotte_custom ${HULOTTE_LIBS})

# Exemple 1 : StreamPU uniquement
add_subdirectory(ex1_spu_only)

# Exemple 2 : StreamPU + module custom
add_subdirectory(ex2_spu_custom)

# Exemple 3 : StreamPU + AFF3CT (si activé)
if(HULOTTE_USE_AFF3CT)
    add_subdirectory(ex3_spu_aff3ct)
else()
    message(STATUS "Skipping ex3_spu_aff3ct (AFF3CT disabled)")
endif()