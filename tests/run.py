#!/usr/bin/env python3
"""Run the test suite with plain python — no pytest required.

The factory's test stage must work on runners whose default interpreter
has no pytest (and no way to install it: Debian's system python is
externally-managed and this runner build lacks the venv/ensurepip
module). The discovery-and-call contract is deliberately minimal:

  - every tests/test_*.py module is imported;
  - every function whose name starts with test_ and takes no arguments
    is a test;
  - a test passes if it returns without raising;
  - the summary line and exit code mirror what the stage needs:
    `N passed, M failed` and exit 1 on any failure.

The same test files also run under pytest where it exists (plain
functions are valid pytest tests), so a target repo's own gate keeps
working with either runner.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import traceback

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def discover():
    """[(module, [test function names])] for every tests/test_*.py."""
    out = []
    for fname in sorted(os.listdir(TESTS_DIR)):
        if not (fname.startswith("test_") and fname.endswith(".py")):
            continue
        name = fname[: -len(".py")]
        spec = importlib.util.spec_from_file_location(
            name, os.path.join(TESTS_DIR, fname))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fns = [n for n in dir(mod)
               if n.startswith("test_") and callable(getattr(mod, n))]
        out.append((mod, sorted(fns)))
    return out


def main() -> int:
    passed = failed = 0
    for mod, fns in discover():
        mod_name = mod.__name__
        for fn in fns:
            label = f"{mod_name}.{fn}"
            try:
                getattr(mod, fn)()
            except Exception:
                failed += 1
                tb = traceback.format_exc().strip().splitlines()
                print(f"FAIL {label}")
                for line in tb[-4:]:
                    print(f"     {line}")
            else:
                passed += 1
                print(f"PASS {label}")
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
