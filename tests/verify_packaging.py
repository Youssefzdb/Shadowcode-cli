#!/usr/bin/env python3
"""Verify packaging WITHOUT installing anything (no pip install -e .).

Checks, offline:
- py_compile on main.py and shadowcode_pkg/*.py
- pyproject.toml parses (tomllib), has [project] name/version,
  [project.scripts] shadowcode = "main:main", and that target
  exists and is callable (import main, check main.main)
- version in pyproject.toml matches shadowcode_pkg.__version__
- declared packages/modules exist on disk
- README.md exists and is non-empty
Run: python3 tests/verify_packaging.py  (exit 0 = all checks pass)
"""
import sys, tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    return cond

ok = True
import py_compile
for f in [ROOT / "main.py", *sorted((ROOT / "shadowcode_pkg").glob("*.py"))]:
    try:
        py_compile.compile(str(f), doraise=True)
        ok &= check(True, f"py_compile {f.name}")
    except Exception as e:
        ok &= check(False, f"py_compile {f.name}: {e}")

with open(ROOT / "pyproject.toml", "rb") as fh:
    proj = tomllib.load(fh)
name = proj.get("project", {}).get("name")
ver = proj.get("project", {}).get("version")
scripts = proj.get("project", {}).get("scripts", {})
ok &= check(name == "shadowcode", f"project name = {name!r}")
ok &= check(bool(ver), f"project version = {ver!r}")
ok &= check(scripts.get("shadowcode") == "main:main",
            f"entry point shadowcode = {scripts.get('shadowcode')!r}")

import main as main_mod
ok &= check(callable(getattr(main_mod, "main", None)), "main:main is callable")
from shadowcode_pkg import __version__ as pkg_ver
ok &= check(pkg_ver == ver, f"package version {pkg_ver!r} matches pyproject {ver!r}")
for mod in ["main.py"]:
    ok &= check((ROOT / mod).is_file(), f"module file {mod} exists")
for pkg in proj.get("tool", {}).get("setuptools", {}).get("packages", []):
    ok &= check((ROOT / pkg).is_dir(), f"package dir {pkg}/ exists")
readme = ROOT / "README.md"
ok &= check(readme.is_file() and readme.stat().st_size > 100, "README.md exists and non-empty")
# NOTE: pip install -e . itself is NOT run here — it is a morning
# approval (see MORNING_APPROVALS.md). This script only verifies
# that the install *would* have a well-formed target to install.
print("\npackaging verification: " + ("OK" if ok else "FAILED"))
sys.exit(0 if ok else 1)
