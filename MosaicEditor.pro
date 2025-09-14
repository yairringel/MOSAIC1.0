QT += core widgets
CONFIG += c++17

TARGET = MosaicEditor
TEMPLATE = app

# Source files
SOURCES += \
    main.cpp \
    mosaiccanvas.cpp

# Header files
HEADERS += \
    mosaiccanvas.h

# Compiler settings
win32 {
    CONFIG += windows
    QMAKE_CXXFLAGS += /W3
}

unix {
    QMAKE_CXXFLAGS += -Wall -Wextra
}

# Output directory
DESTDIR = bin
OBJECTS_DIR = build/obj
MOC_DIR = build/moc
RCC_DIR = build/rcc
UI_DIR = build/ui
