cmake_minimum_required(VERSION 3.16)
project(bmp_tasks C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")

# Каждая цель — отдельная задача. Выберите нужную цель запуска в CLion.
set(BMP_TASKS I1A_info I1B_copy I2A_invert I2B_gray I2C_bright I2D_threshold)
foreach(task IN LISTS BMP_TASKS)
    add_executable(${task} solutions/${task}.c)
    if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(${task} PRIVATE -Wall -Wextra -Wpedantic -Werror)
    elseif(MSVC)
        target_compile_options(${task} PRIVATE /W4 /utf-8)
    endif()
endforeach()

# CTest позволяет запускать тот же набор проверок прямо из CLion.
include(CTest)
if(BUILD_TESTING)
    # В Windows у CLion есть собственный Python для отладчика.
    # Используем его, если Python не был явно указан пользователем.
    if(WIN32 AND NOT Python3_EXECUTABLE)
        get_filename_component(_compiler_dir "${CMAKE_C_COMPILER}" DIRECTORY)
        get_filename_component(_cmake_dir "${CMAKE_COMMAND}" DIRECTORY)
        foreach(_candidate
                "${_compiler_dir}/../../lldb/win/x64/bin/python.exe"
                "${_cmake_dir}/../../../../lldb/win/x64/bin/python.exe")
            if(EXISTS "${_candidate}")
                execute_process(
                    COMMAND "${_candidate}" -c "import argparse, json, pathlib, random, struct, subprocess"
                    RESULT_VARIABLE _python_status
                    OUTPUT_QUIET ERROR_QUIET TIMEOUT 10)
                if(_python_status EQUAL 0)
                    get_filename_component(Python3_EXECUTABLE "${_candidate}" ABSOLUTE)
                    break()
                endif()
            endif()
        endforeach()
    endif()
    find_package(Python3 3.8 REQUIRED COMPONENTS Interpreter)

    add_test(NAME bmp_tasks_all
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/check_solutions.py"
            --bin-dir "$<TARGET_FILE_DIR:I1A_info>"
            --compiler "${CMAKE_C_COMPILER}"
            --work-dir "${CMAKE_CURRENT_BINARY_DIR}/test_files"
            --report "${CMAKE_CURRENT_BINARY_DIR}/test_report.json")
    set_tests_properties(bmp_tasks_all PROPERTIES
        TIMEOUT 120
        ENVIRONMENT "PYTHONUTF8=1")

    # Команда собирает все шесть программ, затем запускает CTest.
    add_custom_target(check
        COMMAND "${CMAKE_CTEST_COMMAND}" --verbose --output-on-failure -C "$<CONFIG>"
        DEPENDS ${BMP_TASKS}
        WORKING_DIRECTORY "${CMAKE_BINARY_DIR}"
        USES_TERMINAL
        VERBATIM)
endif()
