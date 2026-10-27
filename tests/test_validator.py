"""Unit tests for the Gherkin validator the factory uses to keep its
requirements oracle executable (and that a target repo's gate can reuse).

Plain-python by design: every test is a no-argument function that raises
on failure. The same files run under pytest where it exists (plain
functions are valid pytest tests) and under the stdlib-only runner
`python3 tests/run.py` where it does not (a runner whose system python is
externally-managed may have no pytest and no way to install it).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile

spec = importlib.util.spec_from_file_location(
    "gherkin_validate",
    os.path.join(os.path.dirname(__file__), "..", ".github", "scripts",
                 "gherkin-validate.py"),
)
mod = importlib.util.module_from_spec(spec)
sys.modules["gherkin_validate"] = mod
spec.loader.exec_module(mod)

try:
    from gherkin import Parser  # noqa: E402  (used for the API-shape check)
except ImportError:
    Parser = None  # a target interpreter without the parser port: the
    # oracle check is reported skipped, not failed, when it runs there


VALID = """Feature: a tiny oracle
  Scenario: it parses
    Given a well-formed feature
    When the official parser reads it
    Then it is valid Gherkin
"""

INVALID = """Scenario: no Feature line above it
    Given the parser must reject it
"""

EMPTY_SCENARIOS = """Feature: nothing executable
  Background:
    Given only a background
"""


def test_valid_feature_passes():
    if Parser is None:
        return  # skipped-not-failed on an interpreter without the port
    with tempfile.TemporaryDirectory() as d:
        cwd = os.getcwd()
        os.chdir(d)
        try:
            with open("ok.feature", "w") as f:
                f.write(VALID)
            assert mod.validate_file("ok.feature") == (0, [])
        finally:
            os.chdir(cwd)


def test_invalid_feature_fails():
    if Parser is None:
        return  # skipped-not-failed on an interpreter without the port
    with tempfile.TemporaryDirectory() as d:
        cwd = os.getcwd()
        os.chdir(d)
        try:
            with open("bad.feature", "w") as f:
                f.write(INVALID)
            rc, errs = mod.validate_file("bad.feature")
            assert rc == 1 and any("parse error" in e for e in errs)
        finally:
            os.chdir(cwd)


def test_feature_without_scenarios_fails():
    if Parser is None:
        return  # skipped-not-failed on an interpreter without the port
    with tempfile.TemporaryDirectory() as d:
        cwd = os.getcwd()
        os.chdir(d)
        try:
            with open("empty.feature", "w") as f:
                f.write(EMPTY_SCENARIOS)
            rc, errs = mod.validate_file("empty.feature")
            assert rc == 1 and any("no Scenario" in e for e in errs)
        finally:
            os.chdir(cwd)


def test_issue_named_file_fails():
    """The oracle is structured by topic, not by issue — a file named after
    the issue that produced it would scatter a topic across the issue history
    and force a search to sweep every Gherkin file instead of directing it at
    the topic's file. The naming rule needs no parser, so it holds (and is
    testable) even on an interpreter without the official parser port."""
    with tempfile.TemporaryDirectory() as d:
        cwd = os.getcwd()
        os.chdir(d)
        try:
            for name in ("issue-7-merge-base.feature", "issue_7.feature"):
                with open(name, "w") as f:
                    f.write(VALID)
                rc, errs = mod.validate_file(name)
                assert rc == 1, f"{name} must fail the topic-naming check"
                assert any("named after an issue" in e for e in errs)
        finally:
            os.chdir(cwd)


def test_topic_named_file_passes():
    """A file named after the topic it covers passes the naming check; on an
    interpreter without the parser port the parse half skips-not-fails while
    the naming rule still applies."""
    with tempfile.TemporaryDirectory() as d:
        cwd = os.getcwd()
        os.chdir(d)
        try:
            with open("merge-base.feature", "w") as f:
                f.write(VALID)
            rc, errs = mod.validate_file("merge-base.feature")
            assert rc == 0, f"a topic-named file must pass: {errs}"
            assert not any("named after an issue" in e for e in errs)
        finally:
            os.chdir(cwd)


def test_directory_walk():
    with tempfile.TemporaryDirectory() as d:
        cwd = os.getcwd()
        os.chdir(d)
        try:
            os.mkdir("reqs")
            with open("reqs/ok.feature", "w") as f:
                f.write(VALID)
            with open("reqs/bad.feature", "w") as f:
                f.write(INVALID)
            feats = list(mod.iter_features(["reqs"]))
            assert {os.path.basename(p) for p in feats} == {
                "ok.feature", "bad.feature"}
        finally:
            os.chdir(cwd)


def test_parser_api_shape():
    """The official-parser port this validator builds on must expose the
    API the validator calls (Parser().parse() → matchers + document).
    Skipped — not failed — on an interpreter without the port."""
    if Parser is None:
        return
    res = Parser().parse(VALID)
    # this port returns the document mapping directly ({"feature": ...});
    # other ports wrap it under "gherkinDocument" — accept both, require a
    # parsed feature inside
    if isinstance(res, dict) and "gherkinDocument" in res:
        doc = res["gherkinDocument"]
    else:
        doc = res
    feat = doc["feature"] if isinstance(doc, dict) else doc.feature
    assert doc is not None and feat is not None


def test_repos_own_oracle_is_clean():
    """The repo's own requirements/ oracle must validate — the factory's
    stage 10 runs it as acceptance tests, and a broken oracle would
    poison every run. Skipped-not-failed on an interpreter without the
    parser port (the suite runs on an interpreter without pytest — and
    one without the port)."""
    if Parser is None:
        return
    root = os.path.join(os.path.dirname(__file__), "..")
    files = list(mod.iter_features([os.path.join(root, "requirements")]))
    assert files, "the oracle directory vanished"
    for path in files:
        rc, errs = mod.validate_file(path)
        assert rc == 0, f"{path}: {errs}"
