cmake_minimum_required(VERSION 3.16)
project(kirby-retro-launcher-cpp VERSION 0.1.0 LANGUAGES CXX)

# Portage C++/Qt 6 du launcher (version Python dans ../launcher).
# Bibliothèque, jaquettes, téléchargement des ROMs, détection RetroArch
# et lancement des jeux.

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets Network)

add_executable(kirby-retro-launcher-cpp
    src/main.cpp
    src/app_config.h
    src/app_config.cpp
    src/api.h
    src/api.cpp
    src/covers.h
    src/covers.cpp
    src/detect.h
    src/detect.cpp
    src/launch.h
    src/launch.cpp
    src/mainwindow.h
    src/mainwindow.cpp
    src/settingsdialog.h
    src/settingsdialog.cpp
    resources.qrc
)

target_include_directories(kirby-retro-launcher-cpp PRIVATE src)
target_link_libraries(kirby-retro-launcher-cpp PRIVATE Qt6::Widgets Qt6::Network)
