CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Iinclude
SRC = src/shadowcode_native.cpp

all: shadowcode-native libshadowcode_native.so

shadowcode-native: src/main.cpp $(SRC) include/shadowcode_native.h
	$(CXX) $(CXXFLAGS) src/main.cpp $(SRC) -o $@

libshadowcode_native.so: $(SRC) include/shadowcode_native.h
	$(CXX) $(CXXFLAGS) -fPIC -shared $(SRC) -o $@

test: all
	./tests/run_tests.sh

clean:
	rm -f shadowcode-native libshadowcode_native.so

.PHONY: all test clean
