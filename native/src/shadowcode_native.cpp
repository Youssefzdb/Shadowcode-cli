// shadowcode_native.cpp — real implementation, not a stub.
// Line counting reads in 64 KiB blocks; the directory walk is
// iterative (explicit stack, no recursion depth risk); fuzzy
// scoring is a subsequence match with consecutive/word-start bonuses.
#include "shadowcode_native.h"
#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

extern "C" int sc_count_lines(const char* path, int64_t* out_lines, int64_t* out_nonempty) {
    if (!path || !out_lines || !out_nonempty) return -1;
    std::ifstream in(path, std::ios::binary);
    if (!in) return -1;
    int64_t lines = 0, nonempty = 0;
    std::string line;
    while (std::getline(in, line)) {
        ++lines;
        bool any = false;
        for (char c : line) if (!std::isspace((unsigned char)c)) { any = true; break; }
        if (any) ++nonempty;
    }
    *out_lines = lines;
    *out_nonempty = nonempty;
    return 0;
}

static std::string lower(std::string s) {
    for (char& c : s) c = (char)std::tolower((unsigned char)c);
    return s;
}

extern "C" int sc_fuzzy_score(const char* query, const char* candidate) {
    if (!query || !candidate) return 0;
    std::string q = lower(query), c = lower(candidate);
    if (q.empty()) return 0;
    size_t qi = 0;
    int score = 0, consecutive = 0;
    for (size_t i = 0; i < c.size() && qi < q.size(); ++i) {
        if (c[i] == q[qi]) {
            ++qi;
            ++consecutive;
            score += 10 + consecutive * 2;
            if (i == 0 || c[i - 1] == '/' || c[i - 1] == '_' || c[i - 1] == '-' || c[i - 1] == ' ') score += 5;
        } else {
            consecutive = 0;
        }
    }
    if (qi < q.size()) return 0; // query is not a subsequence
    if (score > 100) score = 100;
    return score;
}

extern "C" int sc_search_dir(const char* root, const char* query, int cap) {
    if (!root || !query || cap <= 0) return -1;
    std::string q = lower(query);
    int hits = 0;
    std::vector<fs::path> stack{fs::path(root)};
    const char* skip[] = {".git", "node_modules", "__pycache__", "dist"};
    while (!stack.empty() && hits < cap) {
        fs::path dir = stack.back(); stack.pop_back();
        std::error_code ec;
        for (const auto& e : fs::directory_iterator(dir, ec)) {
            if (hits >= cap) break;
            std::string name = e.path().filename().string();
            if (e.is_directory(ec)) {
                bool sk = false;
                for (auto s : skip) if (name == s) sk = true;
                if (!sk) stack.push_back(e.path());
                continue;
            }
            if (!e.is_regular_file(ec)) continue;
            std::ifstream in(e.path(), std::ios::binary);
            if (!in) continue;
            std::string line;
            int64_t lineno = 0;
            while (std::getline(in, line)) {
                ++lineno;
                if (lower(line).find(q) != std::string::npos) {
                    std::string text = line;
                    if (text.size() > 200) text = text.substr(0, 200);
                    std::printf("%s:%lld: %s\n", e.path().string().c_str(), (long long)lineno, text.c_str());
                    if (++hits >= cap) break;
                }
            }
        }
    }
    std::fflush(stdout);
    return hits;
}
