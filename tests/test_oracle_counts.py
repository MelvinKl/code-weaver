"""Unit tests pinning the documented oracle counts to the requirements
tree (issue #23, task 3).

The README and the arc42 chapters state how many feature files and
scenarios the oracle holds (the README's repository-layout line and
Requirements section; chapter 1's introduction; chapter 6's
building-block table; chapter 11's "Oracle" glossary entry). The
extraction that grew the tree to 149 scenarios (ten new, no new file)
left the stated figure at 135 — already stale, because nothing ever
compared the stated counts to the tree. This test is that missing
comparison (requirement-extraction "The documented oracle counts match
the requirements tree" — new):

- the stated counts are read from the doc surfaces — the README plus
  every arc42 chapter (the release-contract module's `_doc_surfaces`
  reader is the precedent);
- the stated number of feature files must equal the number of
  `.feature` files under `requirements/`, and the stated scenario count
  must equal the number of scenarios the tree holds;
- the AI-activity section's per-run entries (e.g. "121 scenarios
  fulfilled") are past records of what a run's review verified, not
  stated oracle counts — the section is cut out of the surfaces before
  the counts are read.

Plain-stdlib by design (no third-party imports): no-argument `test_`
functions are auto-discovered by both runners (`tests/run.py` imports
every `tests/test_*.py`; house CI's "Validator unit tests" step runs
`pytest tests/`), so no `Makefile`, `tests/run.py` or
`.github/workflows/house-ci.yml` change is needed.
"""
from __future__ import annotations

import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")

# The heading that opens the AI-activity section (chapter 1 carries it in
# this repo): its entries record per-run fulfilled counts — past records,
# never the stated oracle counts.
AI_ACTIVITY_HEADING = "## AI activity"


def _read(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as f:
        return f.read()


def _doc_surfaces():
    """[(relpath, text)] — the README plus every arc42 chapter file under
    `docs/` (one chapter per file) — the same surface set the
    release-contract module pins against."""
    surfaces = [("README.md", _read("README.md"))]
    docs = os.path.join(ROOT, "docs")
    surfaces += [(os.path.join("docs", fname),
                  _read(os.path.join("docs", fname)))
                 for fname in sorted(os.listdir(docs))
                 if fname.endswith(".md")]
    return surfaces


def _stated_counts(text):
    """(file counts, scenario counts) the surface states. Whitespace is
    collapsed first, so a count wrapped across a line break (chapter 11's
    glossary entry) still reads; the AI-activity section is cut, so its
    per-run records never enter the stated set. Both shapes a surface
    states are collected: the "N files, M scenarios" pair (the layout
    line, chapter 1, the chapter 6 table row, the chapter 11 glossary
    entry) and the scenario-only form (one or two words between the count
    and "scenarios" — the README's "**M Gherkin scenarios**", chapter 1's
    "every one of the M scenarios")."""
    i = text.find(AI_ACTIVITY_HEADING)
    text = " ".join((text[:i] if i != -1 else text).split())
    files, scenarios = [], []
    for n_files, n_scenarios in re.findall(
            r"(\d+) files, (\d+) scenarios", text):
        files.append(int(n_files))
        scenarios.append(int(n_scenarios))
    scenarios += [int(n) for n in re.findall(
        r"\b(\d+)\s+(?:\w+\s+)?scenarios\b", text)]
    return files, scenarios


def _tree_counts():
    """(number of `.feature` files under requirements/, number of
    scenarios the tree holds) — scenarios counted as `Scenario:` /
    `Scenario Outline:` definition lines, the shapes the official-parser
    validator already parses."""
    reqs = os.path.join(ROOT, "requirements")
    names = sorted(f for f in os.listdir(reqs) if f.endswith(".feature"))
    scenarios = 0
    for fname in names:
        with open(os.path.join(reqs, fname), encoding="utf-8") as f:
            scenarios += sum(
                1 for line in f
                if re.match(r"^\s*Scenario(?:\s+Outline)?\s*:\s", line))
    return len(names), scenarios


def test_documented_oracle_counts_match_the_requirements_tree():
    """(requirement-extraction "The documented oracle counts match the
    requirements tree" — new; reference
    `requirements/requirement-extraction.feature::The documented oracle
    counts match the requirements tree`) the README and the arc42
    chapters state how
    many feature files and scenarios the oracle holds; read against the
    requirements/ tree, the stated number of feature files equals the
    number of files under requirements/ and the stated number of
    scenarios equals the number of scenarios the tree holds. Both kinds
    are asserted stated at all: a documentation that states no count
    would pass a bare equality the way the review stage must not pass on
    an empty verdict block (guard-rail "A run that changed scenarios ...
    still fails")."""
    files, scenarios = _tree_counts()
    stated_files, stated_scenarios = [], []
    for _relpath, text in _doc_surfaces():
        f, s = _stated_counts(text)
        stated_files += f
        stated_scenarios += s
    assert stated_files, (
        "no doc surface (README or arc42 chapter) states how many feature "
        "files the oracle holds — a count the tree holds is a count the "
        "documentation states")
    assert stated_scenarios, (
        "no doc surface (README or arc42 chapter) states how many "
        "scenarios the oracle holds — a count the tree holds is a count "
        "the documentation states")
    assert set(stated_files) == {files}, (
        f"the documented feature-file count {sorted(set(stated_files))!r} "
        f"disagrees with the tree, which holds {files} `.feature` files "
        "under requirements/")
    assert set(stated_scenarios) == {scenarios}, (
        f"the documented scenario count {sorted(set(stated_scenarios))!r} "
        f"disagrees with the tree, which holds {scenarios} scenarios "
        "under requirements/")
