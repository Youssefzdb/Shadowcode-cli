#!/usr/bin/env python3
"""Benchmark: pure-Python search vs C++ native search (cycle 7).

Mock/local data only, no live provider, no network. Generates a test
tree in a temp dir, plants a known plain-substring needle, then times:
  - pure Python: Tools.search_files with SHADOWCODE_NO_NATIVE=1
    (a regex walk; the needle is plain, so regex == substring here)
  - native C++: native_scanner.native_search (CLI subprocess)
    — only if native/shadowcode-native exists; otherwise reported
    as unavailable, never faked.
Results are printed as a table with hit counts, so a speed claim
without the same hit count is visibly wrong. The tree is deleted
afterwards. Usage: python3 scripts/benchmark_search.py [--files N]
[--lines N] [--repeats N] [--query WORD]
"""
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shadowcode_pkg.native_scanner import native_search, native_available  # noqa: E402
from shadowcode_pkg.tools import Tools  # noqa: E402


def build_tree(root: Path, n_files: int, n_lines: int, query: str) -> int:
    planted = 0
    for i in range(n_files):
        sub = root / f"dir{i % 10}"
        sub.mkdir(parents=True, exist_ok=True)
        lines = []
        for j in range(n_lines):
            if i % 10 == 0 and j == n_lines // 2:
                lines.append(f"line {j} contains {query} here")
                planted += 1
            else:
                lines.append(f"line {j} filler text number {i} {j} lorem ipsum")
        (sub / f"file{i:04d}.txt").write_text("\n".join(lines) + "\n")
    return planted


def timeit(fn, repeats: int):
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        out = fn()
        times.append(time.perf_counter() - t0)
    return statistics.median(times), out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=500)
    ap.add_argument("--lines", type=int, default=100)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--query", default="benchneedle")
    args = ap.parse_args()
    root = Path(tempfile.mkdtemp(prefix="shadowcode-bench-"))
    try:
        planted = build_tree(root, args.files, args.lines, args.query)
        print(f"tree: {args.files} files x {args.lines} lines, planted hits: {planted}")
        print(f"native binary available: {native_available()}")
        os.environ["SHADOWCODE_NO_NATIVE"] = "1"
        tools = Tools(str(root))
        med_py, out_py = timeit(lambda: tools.search_files(args.query), args.repeats)
        hits_py = 0 if out_py == "no matches" else len(out_py.splitlines())
        print(f"pure Python search: median {med_py*1000:.1f} ms over {args.repeats} runs, hits={hits_py}")
        # Native run must NOT inherit the pure-Python flag, or it would
        # (correctly) refuse to run and the comparison would be empty.
        os.environ.pop("SHADOWCODE_NO_NATIVE", None)
        if native_available():
            med_nat, hits_nat = timeit(lambda: native_search(str(root), args.query) or [], args.repeats)
            print(f"native C++ search: median {med_nat*1000:.1f} ms over {args.repeats} runs, hits={len(hits_nat)}")
            if med_nat > 0:
                print(f"speedup (python/native): {med_py/med_nat:.2f}x")
            if hits_py != len(hits_nat):
                print(f"WARNING: hit counts differ (python={hits_py} native={len(hits_nat)}) — not directly comparable")
        else:
            print("native C++ search: unavailable (no binary) — no comparison claimed")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
