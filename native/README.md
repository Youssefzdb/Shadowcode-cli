# Native component (C/C++)

Real performance component, not a stub: a fast line counter,
fuzzy matcher, and directory searcher, in C++17 with a C ABI.

## Build

```bash
cd ~/workspace/shadowcode/native
make            # shadowcode-native + libshadowcode_native.so
make test       # runs tests/run_tests.sh
```

## CLI interface

```bash
./shadowcode-native count <file>
# lines=<n> nonempty=<n>
./shadowcode-native fuzzy <query> <candidate>
# score=<0..100>
./shadowcode-native search <dir> <query> [cap]
# path:line: text  (one hit per line, stdout)
```

## Library interface (from Python / Go / TS)

```c
#include "shadowcode_native.h"
int sc_count_lines(const char* path, int64_t* out_lines, int64_t* out_nonempty);
int sc_fuzzy_score(const char* query, const char* candidate);
int sc_search_dir(const char* root, const char* query, int cap);
```

Python example (ctypes, no rebuild of the Python core needed):

```python
import ctypes
lib = ctypes.CDLL("native/libshadowcode_native.so")
lib.sc_fuzzy_score.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
lib.sc_fuzzy_score(b"scd", b"shadowcode")  # > 0
```

Go example: cgo with `#cgo LDFLAGS: -L../native -lshadowcode_native`.
TS example: spawn `./native/shadowcode-native search <dir> <query>`
and parse its stdout lines (same shape as the Python search tool).
