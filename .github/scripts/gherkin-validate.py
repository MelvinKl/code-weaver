#!/usr/bin/env python3
"""Validate Gherkin source files with Cucumber's official Gherkin parser.

Usage: gherkin-validate.py <file-or-dir>…
Exit 0 only if every .feature file parses AND each feature has at least one
Scenario (the oracle must be executable: the test-and-review stage runs every
scenario as an acceptance test) AND no file is named after an issue (the
oracle is structured by topic, not by issue — an issue-named file would
scatter a topic across the issue history and force a search to sweep every
Gherkin file instead of directing it at the topic's file). The naming check
needs no parser, so it holds even where the official parser port is absent.

The `gherkin` import is Cucumber's official Python port — the same parser the
requirements must satisfy, so a file that validates here validates everywhere
Cucumber runs."""
from __future__ import annotations

import os
import re
import sys

try:
    from gherkin import Parser
except ImportError:
    # An interpreter without the official parser port (the suite must run on
    # an interpreter without pytest — and one without the port): the parse
    # check is skipped-not-failed there, never a failure. The naming check
    # below needs no parser and still applies.
    Parser = None


# A feature file named after the issue that produced it breaks the
# topic-structured oracle. The pattern is the per-issue naming convention
# itself (issue-<N>, issue_<N>, issue <N>), so a legitimate topic slug that
# happens to contain digits ("arc42-…") stays admissible while every
# issue-named file is rejected.
ISSUE_NAMED_RE = re.compile(r"issue[-_ ]?\d+", re.IGNORECASE)


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
    errs: list[str] = []
    # Topic structure, enforced before (and without) the parser: a file
    # named after an issue would make a search for its topic sweep the whole
    # oracle; the file must be named after the topic it covers.
    if ISSUE_NAMED_RE.search(os.path.basename(path)):
        errs.append(f"{path}: named after an issue — the oracle is structured "
                    f"by topic; name the file after the topic it covers")
    if Parser is None:
        if errs:
            errs.append(f"{path}: parse check skipped — the official Gherkin "
                        f"parser port is not installed on this interpreter "
                        f"(skipped, not failed)")
            return 1, errs
        return (0, [f"{path}: skipped — the official Gherkin parser port is "
                    f"not installed on this interpreter (skipped, not failed)"])
    with open(path, encoding="utf-8") as f:
        source = f.read()
    try:
        doc = Parser().parse(source)
    except Exception as e:  # CompositeParserException / friends
        return 1, errs + [f"{path}: parse error: {str(e).splitlines()[0][:160]}"]
    if "errors" in doc and doc["errors"]:
        errs += [f"{path}: gherkin errors: " + "; ".join(
            str(e.get("message", e))[:120] for e in doc["errors"])]
    if not source.lstrip().startswith("#! language") and "Feature:" not in source:
        errs.append(f"{path}: no 'Feature:' line")
    n = scenario_count(doc)
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
    # Without the official parser port the parse check is
    # skipped-not-failed (the suite must run on an interpreter that may lack
    # it); the topic-naming check needs no parser and still runs.
    if Parser is None:
        print("gherkin-validate: SKIP — the official Gherkin parser port is not "
              "installed on this interpreter; the parse check is skipped, "
              "not failed (the topic-naming check still runs)")
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
