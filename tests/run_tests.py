#!/usr/bin/env python3
"""Run Shadowcode tests without pytest installed.
Usage: python3 tests/run_tests.py
Discovers test_* functions in test_shadowcode.py, gives each a fresh
tmp dir (pytest's tmp_path fixture is emulated)."""
import sys, tempfile, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
import test_shadowcode as t

passed, failed = [], []
for name in sorted(dir(t)):
    if not name.startswith("test_"):
        continue
    fn = getattr(t, name)
    try:
        if "tmp_path" in fn.__code__.co_varnames:
            with tempfile.TemporaryDirectory() as d:
                fn(Path(d))
        else:
            fn()
        passed.append(name)
        print(f"PASS {name}")
    except Exception:
        failed.append(name)
        print(f"FAIL {name}")
        traceback.print_exc()
print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
