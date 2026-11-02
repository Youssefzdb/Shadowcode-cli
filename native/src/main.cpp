// main.cpp — shadowcode-native CLI: count | fuzzy | search
// Usage:
//   shadowcode-native count <file>
//   shadowcode-native fuzzy <query> <candidate>
//   shadowcode-native search <dir> <query> [cap]
#include "shadowcode_native.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
int main(int argc, char** argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: count|fuzzy|search ...\n"); return 2; }
    if (!std::strcmp(argv[1], "count") && argc >= 3) {
        int64_t lines = 0, nonempty = 0;
        if (sc_count_lines(argv[2], &lines, &nonempty) != 0) { std::fprintf(stderr, "cannot open %s\n", argv[2]); return 1; }
        std::printf("lines=%lld nonempty=%lld\n", (long long)lines, (long long)nonempty);
        return 0;
    }
    if (!std::strcmp(argv[1], "fuzzy") && argc >= 4) {
        std::printf("score=%d\n", sc_fuzzy_score(argv[2], argv[3]));
        return 0;
    }
    if (!std::strcmp(argv[1], "search") && argc >= 4) {
        int cap = argc >= 5 ? std::atoi(argv[4]) : 100;
        int n = sc_search_dir(argv[2], argv[3], cap);
        if (n < 0) { std::fprintf(stderr, "search failed\n"); return 1; }
        return 0;
    }
    std::fprintf(stderr, "usage: count|fuzzy|search ...\n");
    return 2;
}
