"""Unit tests for the issue-#20 labeled-only trigger contract.

The code-weaver trigger is restricted to the `labeled` issue event — in both
the README's "Consume it (by ref)" example and the consumer workflow this
repo deploys on itself (`.github/workflows/code-weaver.yml`): opening or
editing an issue no longer schedules a factory run; only a label addition
(and the unchanged manual dispatch) does. The reusable factory
(`.github/workflows/factory.yml`) is deliberately unchanged — its stage-1
label gate is event-agnostic — and these tests pin that gate verbatim.

Plain-stdlib by design (no third-party imports): the stage-10 driver
(`make test` → `python3 tests/run.py`) is a stdlib-only plain-python
contract per the Makefile, and a full `yaml.safe_load` would read `on:` as
the boolean `True` under YAML 1.1 anyway, so a whole-document parse is
wrong for a workflow's event map. No-argument `test_` functions —
discovered automatically by both runners (`tests/run.py` imports every
`tests/test_*.py`; house CI's "Validator unit tests" step runs
`pytest tests/`), so no `Makefile`, `tests/run.py` or
`.github/workflows/house-ci.yml` changes are needed.
"""
from __future__ import annotations

import os

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _read(relpath):
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


def _types_list(text):
    """The value of the first `types:` line whose remainder is a `[ … ]`
    flow sequence — the comma-split elements stripped of whitespace (empty
    elements dropped); `None` if no such line exists."""
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("types:"):
            continue
        rest = s[len("types:"):].strip()
        if rest.startswith("[") and rest.endswith("]"):
            els = [e.strip() for e in rest[1:-1].split(",")]
            return [e for e in els if e] or None
    return None


def _readme_example_types():
    """The `types:` list of the first fenced code block in the README's
    `## Consume it` section (from its opening fence line — which may carry
    a language tag — to the matching closing fence line; the tag is
    harmless because `_types_list` scans lines)."""
    text = _read("README.md")
    start = text.index("## Consume it")
    end = text.find("\n## ", start)
    section = text[start:] if end == -1 else text[start:end]
    in_block = False
    block = []
    for line in section.splitlines():
        if line.strip().startswith("```"):
            if not in_block:
                in_block = True
            else:
                return _types_list("\n".join(block))
        if in_block:
            block.append(line)
    raise AssertionError("the README's Consume-it section has no fenced code block")


def test_readme_example_declares_labeled_only():
    """(scenario "The README example shows a labeled-only trigger";
    reference
    `requirements/labeled-only-trigger.feature::The README example shows a
    labeled-only trigger`) the
    README's consumption example declares `issues.types` as exactly
    `[labeled]` — no `opened`, no `edited`."""
    types = _readme_example_types()
    assert types == ["labeled"], f"README example declares {types!r}"
    assert "opened" not in types and "edited" not in types


def test_deployed_consumer_workflow_declares_labeled_only():
    """(scenario "The repo's own deployed workflow uses a labeled-only
    trigger"; reference
    `requirements/labeled-only-trigger.feature::The repo's own deployed
    workflow uses a labeled-only trigger`) the consumer workflow this repo
    deploys on itself declares
    `on.issues.types` as exactly `[labeled]` — no `opened`, no `edited`."""
    types = _types_list(_read(".github/workflows/code-weaver.yml"))
    assert types == ["labeled"], f"deployed workflow declares {types!r}"


def test_readme_example_and_deployed_workflow_agree():
    """(scenario "The documented example and the deployed workflow agree on
    the trigger"; reference
    `requirements/labeled-only-trigger.feature::The documented example and
    the deployed workflow agree on the trigger`) both extractions
    are non-empty, equal to each other, and
    each is exactly the single type `labeled` — the two declared triggers
    stay character-for-character the same."""
    example = _readme_example_types()
    workflow = _types_list(_read(".github/workflows/code-weaver.yml"))
    assert example is not None and workflow is not None
    assert example == workflow
    assert example == ["labeled"]


def test_consumer_workflow_never_fires_on_opened_or_edited():
    """(scenarios "Opening an issue does not start a factory run" and
    "Editing an issue without a label change does not start a factory
    run"; reference
    `requirements/labeled-only-trigger.feature::Opening an issue does not
    start a factory run`,
    `requirements/labeled-only-trigger.feature::Editing an issue without a
    label change does not start a factory run`,
    `requirements/trigger.feature::A manual dispatch processes a named
    issue`) GitHub schedules a consumer workflow run only for declared
    event types,
    so `opened` and `edited` must be excluded from `on.issues.types` — and
    the unchanged manual dispatch must stay declared (regression guard for
    `requirements/trigger.feature`'s "A manual dispatch processes a named
    issue")."""
    text = _read(".github/workflows/code-weaver.yml")
    types = _types_list(text)
    assert types is not None
    assert "opened" not in types and "edited" not in types
    assert "workflow_dispatch" in text
    assert "issue_number" in text


def test_factory_trigger_gate_unchanged():
    """(scenarios "Adding the trigger label still starts the factory and
    records the issue" and "Adding a label that is not the trigger label
    leaves the factory idle"; reference
    `requirements/labeled-only-trigger.feature::Adding the trigger label
    still starts the factory and records the issue`,
    `requirements/labeled-only-trigger.feature::Adding a label that is not
    the trigger label leaves the factory idle`)
    the reusable factory is event-agnostic by design — issue #20 changes
    only the consumer layer, so stage 1's gate is unchanged; these six
    markers pin it verbatim so the gate (and its `factory idle` negative
    path) cannot regress."""
    text = _read(".github/workflows/factory.yml")
    start = text.index("  trigger:")
    end = text.index("  setup-pi:")
    gate = text[start:end]
    for marker in (
        'gh api "repos/$GITHUB_REPOSITORY/issues/$ISSUE"',  # the issue/label query
        ".labels[].name",  # the issue's label set
        "factory idle",  # the non-trigger label negative path
        "started.txt",  # the started flag
        "issue-number.txt",  # records the issue number
        "issue-body.md",  # records the issue body
    ):
        assert marker in gate, f"stage-1 trigger gate lost verbatim marker {marker!r}"
