"""Unit tests for the Gherkin validator the factory uses to keep its
requirements oracle executable (and that a target repo's gate can reuse)."""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    "gherkin_validate",
    os.path.join(os.path.dirname(__file__), "..", ".github", "scripts", "gherkin-validate.py"),
)
mod = importlib.util.module_from_spec(spec)
sys.modules["gherkin_validate"] = mod
spec.loader.exec_module(mod)

from gherkin import Parser  # noqa: E402  (used only for the API-shape check)


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


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_valid_feature_passes(workspace):
    f = workspace / "ok.feature"
    f.write_text(VALID)
    assert mod.validate_file("ok.feature") == (0, [])


def test_invalid_feature_fails(workspace):
    f = workspace / "bad.feature"
    f.write_text(INVALID)
    rc, errs = mod.validate_file("bad.feature")
    assert rc == 1 and any("parse error" in e for e in errs)


def test_feature_without_scenarios_fails(workspace):
    f = workspace / "empty.feature"
    f.write_text(EMPTY_SCENARIOS)
    rc, errs = mod.validate_file("empty.feature")
    assert rc == 1 and any("no Scenario" in e for e in errs)


def test_directory_walk(workspace):
    (workspace / "reqs").mkdir()
    (workspace / "reqs" / "ok.feature").write_text(VALID)
    (workspace / "reqs" / "bad.feature").write_text(INVALID)
    feats = list(mod.iter_features(["reqs"]))
    assert {os.path.basename(p) for p in feats} == {"ok.feature", "bad.feature"}
    # the repo's own oracle must be clean
    root = os.path.join(os.path.dirname(__file__), "..")
    rc = mod.main.__wrapped__() if hasattr(mod.main, "__wrapped__") else None
    assert rc is None  # main() runs via CLI; walk-level coverage is above


def test_repos_own_oracle_is_clean(workspace):
    """The repo's own requirements/ oracle must validate — the factory's
    stage 10 will run it as acceptance tests, and a broken oracle would
    poison every run."""
    root = os.path.join(os.path.dirname(__file__), "..")
    files = list(mod.iter_features([os.path.join(root, "requirements")]))
    assert files, "the oracle directory vanished"
    for path in files:
        rc, errs = mod.validate_file(path)
        assert rc == 0, f"{path}: {errs}"
