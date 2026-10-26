"""Minimal test runner for tests that need FreeCAD.

    scripts/fc.sh scripts/run_tests.py [-k SUBSTRING]

Runs every function named test_* in hwkan_gfbox/tests/test_*.py (optionally
only those whose "module::function" contains SUBSTRING). Exit status 1 if
any test fails or none matched.
"""
import glob
import importlib
import os
import sys
import traceback

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)
TESTS = os.path.join(PROJECT, "hwkan_gfbox", "tests")

from hwkan_gfbox.fcmain import run  # noqa: E402


def main(args):
    pattern = args[args.index("-k") + 1] if "-k" in args else None
    passed = failed = 0
    for path in sorted(glob.glob(os.path.join(TESTS, "test_*.py"))):
        module_name = os.path.splitext(os.path.basename(path))[0]
        module = importlib.import_module(f"hwkan_gfbox.tests.{module_name}")
        for fn_name in sorted(n for n in dir(module) if n.startswith("test_")):
            full = f"{module_name}::{fn_name}"
            if pattern and pattern not in full:
                continue
            try:
                getattr(module, fn_name)()
            except Exception:
                failed += 1
                print(f"FAIL {full}")
                traceback.print_exc(file=sys.stdout)
            else:
                passed += 1
                print(f"PASS {full}")
    print(f"{passed} passed, {failed} failed")
    if passed + failed == 0:
        print("no tests matched")
        return 1
    return 1 if failed else 0


run(main)
