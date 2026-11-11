"""Unit tests pinning the README's top warning (issue #77, task 3).

Issue #77's delta adds four new `@safety` scenarios to
`requirements/safety.feature`: the README must carry a prominent warning
at its top — before the factory description, above the usage
(`## Consume it`) and consumption (`## Inputs`) sections — that (a)
advises using the code-weaver workflow only in a private repo, (b)
states that everyone who can create or tag issues can create a workflow
run of the factory, and (c) states that such a run consumes tokens and
creates cost for the repo. These tests read `README.md` and assert one
per new scenario — the warning's presence, prominence and position, and
each of the three content facts. Every content fact is asserted inside
the warning block itself (the first run of blockquoted lines after the
title), never merely somewhere in the README.

Plain-stdlib by design (no third-party imports): no-argument `test_`
functions are auto-discovered by both runners (`tests/run.py` imports
every `tests/test_*.py`; house CI's "Validator unit tests" step runs
`pytest tests/`), so no `Makefile`, `tests/run.py` or
`.github/workflows/house-ci.yml` change is needed.
"""
from __future__ import annotations

import os

ROOT = os.path.join(os.path.dirname(__file__), "..")

# The README's opening structure the position test orders the warning
# against: the factory description's first line, and the usage and
# consumption section headings the warning must sit above.
DESCRIPTION = "An **AI software factory that creates programs**"
USAGE_HEADING = "## Consume it"
CONSUMPTION_HEADING = "## Inputs"

# The three content facts, phrase for phrase (matched against the
# warning block's normalized body — lowercased, backticks stripped,
# whitespace runs collapsed).
PRIVATE_REPO_ADVICE = "use the code-weaver workflow only in a private repo"
RUN_STARTERS = (
    "everyone who can create or tag issues",
    "create a workflow run of the factory",
)
RUN_CONSUMPTION = "such a run consumes tokens and creates cost for the repo"


def _read(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as f:
        return f.read()


def _warning_block(text):
    """(first, last, block) of the README's opening warning: the first
    run of contiguous blockquoted lines (a line whose left-stripped form
    starts with `>`) that follows the title line — for the warning to be
    at the top it must be the first content after the title. `first` and
    `last` are the run's 0-based line numbers; `block` is the run's body
    with each line's `>` gutter stripped."""
    lines = text.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    assert i < len(lines) and lines[i].startswith("# "), (
        "the README does not open with its title line, so nothing sits at "
        "its top")
    i += 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    assert i < len(lines) and lines[i].lstrip().startswith(">"), (
        "the first content after the README title is not the blockquoted "
        "warning — the warning is no longer at the top")
    first = i
    while i < len(lines) and lines[i].lstrip().startswith(">"):
        i += 1
    last = i - 1
    block = "\n".join(line.lstrip()[1:].lstrip()
                      for line in lines[first:last + 1])
    return first, last, block


def _warning_body():
    """The opening warning's body, ready for marker matching: the
    block's `>` gutters stripped, backticks stripped, whitespace runs
    collapsed to single spaces, lowercased."""
    _first, _last, block = _warning_block(_read("README.md"))
    return " ".join(block.replace("`", "").split()).lower()


def test_readme_carries_a_prominent_warning_at_its_top():
    """(scenario "The README carries a prominent warning at its top";
    reference
    `requirements/safety.feature::The README carries a
    prominent warning at its top`) the README's opening presents a
    warning at the top — a set-off blockquoted callout that marks itself
    as a warning and is the first content after the title line — so a
    reader meets it before the factory description and above the
    workflow's usage and consumption sections. A warning placed lower in
    the README is not a warning at its top."""
    text = _read("README.md")
    lines = text.splitlines()
    first, last, block = _warning_block(text)
    # prominence: a set-off callout that marks itself as the warning a
    # reader should heed
    body = " ".join(block.replace("`", "").split()).lower()
    assert body, "the block at the top of the README is empty"
    assert "warning" in body, (
        "the block at the top of the README does not mark itself as a "
        "warning")
    # position: after the title, before the factory description…
    title = next((n for n, line in enumerate(lines) if line.strip()), -1)
    assert title != -1, "the README has no content line"
    assert title < first, "the warning does not open the README"
    desc = next((n for n, line in enumerate(lines)
                 if DESCRIPTION in line), -1)
    assert desc != -1, (
        "the README no longer opens with the factory description")
    assert last < desc, (
        "the top warning does not sit before the factory description")
    # …and above the usage and consumption sections
    for heading in (USAGE_HEADING, CONSUMPTION_HEADING):
        h = next((n for n, line in enumerate(lines)
                  if line.startswith(heading)), -1)
        assert h != -1, f"the README has no {heading!r} section"
        assert last < h, (
            f"the top warning does not sit above the {heading!r} section")


def test_readme_warning_advises_using_the_workflow_only_in_a_private_repo():
    """(scenario "The README warning advises using the workflow only in a
    private repo"; reference
    `requirements/safety.feature::The README carries a prominent warning at its top`) the top warning advises a target
    repo's maintainers to use the code-weaver workflow only in a private
    repo — the statement is asserted inside the warning block itself, not
    merely somewhere in the README (the arc42's compatibility statement
    that the workflow works in any repo stands beside the advice; only
    the README's top warning is pinned here)."""
    body = _warning_body()
    assert PRIVATE_REPO_ADVICE in body, (
        f"the top warning does not advise using the code-weaver workflow "
        f"only in a private repo — missing {PRIVATE_REPO_ADVICE!r}")


def test_readme_warning_names_who_can_start_a_factory_run():
    """(scenario "The README warning names who can start a factory run";
    reference
    `requirements/safety.feature::The README carries a prominent warning at its top`) the top warning states that everyone who can create or
    tag issues can create a workflow run of the factory — the warning
    names the trigger surface (a `labeled` issue event, or a manual
    dispatch), not a specific person, because the trigger's only gate is
    the label. Both halves of the statement — the actor class and the run
    it can start — are asserted inside the warning block itself, not
    merely somewhere in the README."""
    body = _warning_body()
    for marker in RUN_STARTERS:
        assert marker in body, (
            "the top warning does not state who can start a factory run "
            f"— missing {marker!r}")


def test_readme_warning_states_what_a_run_consumes():
    """(scenario "The README warning states what such a run consumes";
    reference
    `requirements/safety.feature::The README carries a prominent warning at its top`) the top warning states that such a run consumes tokens
    and creates cost for the repo — the run's usage/cost accounting:
    every pi call the run makes spends tokens billed against the run's
    model configuration, and the cost lands on the repo. The statement is
    asserted inside the warning block itself, not merely somewhere in the
    README."""
    body = _warning_body()
    assert RUN_CONSUMPTION in body, (
        f"the top warning does not state what a run consumes — missing "
        f"{RUN_CONSUMPTION!r}")
