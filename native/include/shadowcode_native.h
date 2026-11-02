// shadowcode_native.h — fast file scanner / line counter / fuzzy matcher.
// C++17, no dependencies. Built as a CLI binary (shadowcode-native)
// and as a shared library (libshadowcode_native.so) with a C ABI,
// so Python (ctypes), Go (cgo), and TS (via the CLI) can all call it.
// See native/README.md for the interface.
#pragma once
#include <cstddef>
#include <cstdint>
#ifdef __cplusplus
extern "C" {
#endif
// Count lines and non-empty lines in a file. Returns 0 on success,
// -1 if the file cannot be opened. out_lines / out_nonempty are set.
int sc_count_lines(const char* path, int64_t* out_lines, int64_t* out_nonempty);
// Fuzzy match score for query against candidate (0..100, higher is
// better; 0 = no match). Case-insensitive, subsequence-based with
// bonuses for consecutive matches and word starts.
int sc_fuzzy_score(const char* query, const char* candidate);
// Scan a directory tree (skipping .git, node_modules, __pycache__,
// dist) and print "path:line: text" hits for a substring query to
// stdout, one per line, capped at `cap`. Returns the hit count,
// or -1 on a walk error. Case-insensitive.
int sc_search_dir(const char* root, const char* query, int cap);
#ifdef __cplusplus
}
#endif
