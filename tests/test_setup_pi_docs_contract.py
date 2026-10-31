"""Unit tests pinning the documented setup-pi contract (issue #23,
task 4).

The setup stage flipped from verify-only — pi a pre-requisite of the
runner environment, the factory never installing or re-configuring it —
to install-and-configure for the run (task 1: the harness providers ride
the reusable workflow's `secrets:` block; task 2: the stage installs pi
and materialises the provided harness into the agent directory). This
test pins the documentation side of that flip — the two new `@docs`
scenarios of `requirements/setup-pi.feature`:

- "The documented setup stage installs and configures pi for the run" —
  the README's stage list and the arc42 chapters state the setup stage
  installs pi and configures it for the workflow run, and state that no
  pre-installed or pre-configured pi is a pre-requisite of the runner
  environment;
- "The documentation lists the harness providers" — the README and the
  deployment chapter list the providers (the GitHub secrets and the repo
  files `.pi/agent/models.json`, `.pi/settings.json` and
  `.pi/mcp.json`, plus the `.env`-style secret for the extension's
  environment variables) and state that an empty or absent settings
  provider leaves pi without additional packages;
- negative — no surface still states the retired verify-only mechanism.

The readers follow the release-contract module's `_doc_surfaces` /
`_paragraph` precedent: plain stdlib, the README plus every arc42 chapter
(one chapter per file), whitespace collapsed (prose wraps at any width),
backticks stripped (the docs backtick `pi`; the markers are plain), and
the AI-activity section cut — its per-run records are history, never the
stated contract (the oracle-count test cuts it for the same reason).

Plain-stdlib by design (no third-party imports): no-argument `test_`
functions are auto-discovered by both runners (`tests/run.py` imports
every `tests/test_*.py`; house CI's "Validator unit tests" step runs
`pytest tests/`), so no `Makefile`, `tests/run.py` or
`.github/workflows/house-ci.yml` change is needed.
"""
from __future__ import annotations

import os

ROOT = os.path.join(os.path.dirname(__file__), "..")

# The heading that opens the AI-activity section (chapter 1 carries it in
# this repo): its entries list the stages a historical run executed —
# per-run records, never the stated contract.
AI_ACTIVITY_HEADING = "## AI activity"


def _read(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as f:
        return f.read()


def _normalize(text):
    """The surface ready for marker matching: the AI-activity section cut,
    backticks stripped, whitespace runs collapsed to single spaces."""
    i = text.find(AI_ACTIVITY_HEADING)
    if i != -1:
        text = text[:i]
    return " ".join(text.replace("`", "").split())


def _doc_surfaces():
    """[(relpath, normalized text)] — the README plus every arc42 chapter
    file under `docs/` (one chapter per file) — the same surface set the
    release-contract and oracle-count modules pin against."""
    surfaces = [("README.md", _normalize(_read("README.md")))]
    docs = os.path.join(ROOT, "docs")
    surfaces += [(os.path.join("docs", fname),
                  _normalize(_read(os.path.join("docs", fname))))
                 for fname in sorted(os.listdir(docs))
                 if fname.endswith(".md")]
    return surfaces


def _by_relpath():
    return dict(_doc_surfaces())


def _setup_surfaces():
    """The doc surfaces that discuss the setup stage (the AI-activity
    section is cut, so chapter 1's historical per-run stage listings do
    not count as a discussion)."""
    return [(p, t) for p, t in _doc_surfaces()
            if "setup-pi" in t or "setup stage" in t]


# The retired verify-only contract, phrase for phrase: every marker is a
# phrase the old documentation stated affirmatively (pi a runner
# pre-requisite; the factory never installing; "installing or configuring
# pi inside CI" out of scope). The new contract states the negation ("no
# pre-installed or pre-configured pi is a pre-requisite …"), which
# contains none of these markers.
RETIRED_MARKERS = (
    "pre-installed and pre-configured",
    "pre-installed & pre-configured",
    "pre-installed and configured",
    "pre-installed & configured",
    "pi installed & configured",
    "installed and configured",
    "must have, ahead of time",
    "never installs or re-configures pi",
    "never installs or configures it",
    "verify (never install)",
    "verify pre-installed pi",
    "installing or configuring pi inside CI",
    "assumes a runner environment where pi is ready",
    "fixed pre-requisite",
    "is a reference, never an override",
)

# The provider list the README and the deployment chapter must carry
# (setup-pi "The documentation lists the harness providers"): the
# repo-file half under `.pi/`, the `.env`-style secret for the
# extension's environment variables, the GitHub-secret form, and the
# empty-settings consequence.
PROVIDER_MARKERS = (
    ".pi/agent/models.json",
    ".pi/settings.json",
    ".pi/mcp.json",
    ".env",
    "extension's environment",
    "github secret",
    "an empty or absent settings provider leaves pi without additional packages",
)


def test_documented_setup_stage_installs_and_configures_pi():
    """(setup-pi "The documented setup stage installs and configures pi
    for the run" — new, @docs; reference
    `requirements/setup-pi.feature::The documented setup stage installs
    and configures pi for the run`) the README's stage list and the arc42
    chapters that discuss the setup stage state the new contract — the
    setup stage installs pi and configures it for the workflow run. Every
    surface that discusses the stage must carry both statements: a chapter
    that kept the verify-only story next to the new code is a false doc.
    The README's stage-list item itself is asserted on its own (the
    surface a consumer reads first)."""
    surfaces = _setup_surfaces()
    assert surfaces, ("no doc surface (README or arc42 chapter) discusses "
                      "the setup stage — the contract must be stated, not "
                      "only implied")
    for relpath, text in surfaces:
        low = text.lower()
        assert "installs pi" in low, (
            f"{relpath} discusses the setup stage but does not state it "
            f"installs pi — the stage installs pi for the run")
        assert "configures it for the workflow run" in low, (
            f"{relpath} discusses the setup stage but does not state it "
            f"configures it for the workflow run")
    readme = _by_relpath()["README.md"]
    i = readme.find("2. **setup-pi**")
    j = readme.find("3. **baseline**")
    assert i != -1 and j != -1 and j > i, \
        "the README's stage list has no setup-pi item"
    item = readme[i:j].lower()
    assert "installs pi for the run and configures it for the workflow run" in item, \
        f"the README's stage-list item 2 does not state the install-and-configure contract — {item!r}"
    assert "no pre-installed or pre-configured pi is a pre-requisite" in item, \
        "the README's stage-list item 2 does not state that no pre-installed or pre-configured pi is a pre-requisite"


def test_documented_surfaces_state_no_pi_prerequisite():
    """(same scenario — the second Then; reference
    `requirements/setup-pi.feature::The documented setup stage installs
    and configures pi for the run`) the surfaces state that no
    pre-installed or pre-configured pi is a pre-requisite of the runner
    environment: every surface that discusses the setup stage carries the
    negation, with "pre-requisite" reserved for what survives (the `gh`
    CLI, the runner user's `~/.config` ownership)."""
    for relpath, text in _setup_surfaces():
        low = text.lower()
        assert "no pre-installed or pre-configured pi" in low, (
            f"{relpath} does not state that no pre-installed or "
            f"pre-configured pi is a pre-requisite of the runner "
            f"environment")
        assert "pre-requisite" in low, (
            f"{relpath} states no pi pre-requisite but names no surviving "
            f"runner pre-requisite (the gh CLI / ~/.config ownership)")


def test_documentation_lists_the_harness_providers():
    """(setup-pi "The documentation lists the harness providers" — new,
    @docs; reference
    `requirements/setup-pi.feature::The documentation lists the harness
    providers`) the README and the arc42 deployment chapter list the providers
    — the GitHub secrets and the repo files `.pi/agent/models.json`,
    `.pi/settings.json` and `.pi/mcp.json`, plus the `.env`-style secret
    for the extension's environment variables — and state that an empty
    or absent settings provider leaves pi without additional packages."""
    for relpath in ("README.md", "docs/08-deployment-view.md"):
        low = _by_relpath()[relpath].lower()
        for marker in PROVIDER_MARKERS:
            assert marker in low, (
                f"{relpath} does not list the harness providers — missing "
                f"{marker!r}")


def test_no_documented_surface_states_the_retired_setup_contract():
    """(the negative half of both @docs scenarios; reference
    `requirements/setup-pi.feature::The documented setup stage installs
    and configures pi for the run`,
    `requirements/setup-pi.feature::The documentation lists the harness
    providers`) no surface — the README
    or any arc42 chapter — still states the retired verify-only
    mechanism: pi "a pre-requisite of the runner environment"
    (affirmatively), the factory "never installs or re-configures pi", or
    "installing or configuring pi inside CI" as out of scope. A doc that
    kept the old story next to the new code is a false doc."""
    for relpath, text in _doc_surfaces():
        low = text.lower()
        for marker in RETIRED_MARKERS:
            assert marker not in low, (
                f"{relpath} still states the retired setup contract "
                f"({marker!r}) — the setup stage installs and configures "
                "pi for the run; no pre-installed or pre-configured pi is "
                "a pre-requisite of the runner environment")
