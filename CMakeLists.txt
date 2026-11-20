cmake_minimum_required(VERSION 3.12)
project(hybrid_quant_core LANGUAGES CXX)

add_library(hybrid_quant_core SHARED cpp/src/core.cpp)
target_include_directories(hybrid_quant_core PUBLIC cpp/include)
target_compile_features(hybrid_quant_core PUBLIC cxx_std_14)
set_target_properties(hybrid_quant_core PROPERTIES PREFIX "" OUTPUT_NAME "hybrid_quant_core")

if(MSVC)
  target_compile_options(hybrid_quant_core PRIVATE /W4 /EHsc)
else()
  target_compile_options(hybrid_quant_core PRIVATE -Wall -Wextra -Wpedantic)
endif()
