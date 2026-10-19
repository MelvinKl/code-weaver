#!/usr/bin/env python3
"""Validate Gherkin source files with Cucumber's official Gherkin parser.

Usage: gherkin-validate.py <file-or-dir>…
Exit 0 only if every .feature file parses AND each feature has at least one
Scenario (the oracle must be executable: the test-and-review stage runs every
scenario as an acceptance test).

The `gherkin` import is Cucumber's official Python port — the same parser the
requirements must satisfy, so a file that validates here validates everywhere
Cucumber runs."""
from __future__ import annotations

import os
import sys


def fail(msg: str) -> None:
    print(f"FAIL {msg}", file=sys.stderr)


def scenario_count(doc) -> int:
    n = 0
    for child in doc["feature"]["children"]:
        if child.get("scenario") is not None:
            n += 1
        rule = child.get("rule")
        if isinstance(rule, dict):
            for rc in rule.get("children", []):
                if rc.get("scenario") is not None:
                    n += 1
    return n


def validate_file(path: str) -> tuple[int, list[str]]:
    from gherkin import Parser

    with open(path, encoding="utf-8") as f:
        source = f.read()
    try:
        doc = Parser().parse(source)
    except Exception as e:  # CompositeParserException / friends
        return 1, [f"{path}: parse error: {str(e).splitlines()[0][:160]}"]
    if "errors" in doc and doc["errors"]:
        return 1, [f"{path}: gherkin errors: " + "; ".join(
            str(e.get("message", e))[:120] for e in doc["errors"])]
    if not source.lstrip().startswith("#! language") and "Feature:" not in source:
        return 1, [f"{path}: no 'Feature:' line"]
    n = scenario_count(doc)
    errs = []
    if n == 0:
        errs.append(f"{path}: no Scenario — a requirement-free feature is not executable")
    return (1 if errs else 0), errs


def iter_features(paths: list[str]):
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for fn in sorted(files):
                    if fn.endswith(".feature"):
                        yield os.path.join(root, fn)
        elif p.endswith(".feature"):
            yield p


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: gherkin-validate.py <file-or-dir>…", file=sys.stderr)
        return 2
    total = ok = 0
    problems: list[str] = []
    for path in iter_features(sys.argv[1:]):
        total += 1
        rc, errs = validate_file(path)
        if rc == 0:
            ok += 1
            print(f"ok   {os.path.relpath(path)}")
        else:
            problems += errs
    for line in problems:
        fail(line)
    print(f"gherkin-validate: {ok}/{total} feature files valid" + (" — INVALID: " + ", ".join(
        os.path.basename(p.split(':')[0]) for p in problems) if problems else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
