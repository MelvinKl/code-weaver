"""Unit tests pinning the stage contracts the post-review fix loop fixed.

Plain-stdlib by design (no third-party imports): the stage-10 driver
(`make test` → `python3 tests/run.py`) is a stdlib-only plain-python
contract, and no-argument `test_` functions are auto-discovered by both
runners (this runner and house CI's `pytest tests/`).

The pins (one per scenario the fix loop had to fulfil):
- the extract stage is the `@`-file slice of the context contract —
  setup-pi "pi reads the project files as context"; requirement-extraction
  "requirements are derived from the project itself" — while the other
  stages keep the path-referenced slice (configuration "project files are
  referenced by path, not injected into the pi call");
- the extract prompt never edits an existing feature file
  (requirement-extraction "extraction writes one new file named after the
  issue") and tolerates arc42 structure variance (safety "the factory
  tolerates arc42 structure variance");
- the consumer workflow and the README pin the oracle's owner and a
  version tag (reuse-by-ref "the factory is invoked as a reusable
  workflow");
- the pr job generates the PR body with pi from the requirements, the
  review-stage's verdict oracle is delta-scoped (test-and-review: pi judges
  only the scenarios of the feature files this run changed — the accumulated
  oracle is not re-judged every run — and a run that changed no requirements
  passes vacuously instead of failing as unparseable);
- the pr job generates the PR body with pi from the requirements, the
  plan and the review (pr-and-gates "a pull request is opened against
  the target branch");
- the report stage's AI-activity section falls back to the top-level
  arc42 markdown when the doc dir is absent (reporting "the arc42
  documents the AI activity"; safety "an audit trail exists for human
  review");
- the validator skips-not-fails where the parser port is absent
  (test-and-review "the suite runs on an interpreter without pytest");
- the factory's loop-cap defaults match the oracle's Given (MAX_LOOPS 5 /
  MAX_TOTAL_TOKENS 500000) and the doc surface that repeats the values
  agrees with them
  (configuration "the loop caps are configurable", "a loop cap of 0 means
  no cap");
- the implement guard is plan-file-precise: `source_dirs()` excludes the
  plan dir, and the constructed allow set admits the current issue's plan
  file while rejecting any other plan file (implement "implementation may
  only edit the current issue's plan", "the allow set covers the repo's
  real layout").
"""
from __future__ import annotations

import importlib.util
import os
import re
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _read(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as f:
        return f.read()


def test_extract_stage_uses_file_argument_context():
    """(setup-pi "pi reads the project files as context") the extract
    stage's pi call hands its project context to pi as @-file arguments;
    the plumbing (common.pi_invoke context_as_args → stages → extract
    stage) exists at every layer of the call chain."""
    extract = _read(".github/actions/extract-stage/stage.py")
    assert "context_as_args=True" in extract
    stages = _read(".github/scripts/stages.py")
    assert "context_as_args" in stages
    common = _read(".github/scripts/common.py")
    assert "context_as_args" in common
    assert "@-file arguments" in common
    # the context the extract stage assembles: oracle + arc42 + README +
    # the baseline diff (requirement-extraction "requirements are derived
    # from the project itself")
    assert "baseline.diff" in extract
    # the other stages keep the path-referenced slice — one invocation
    # never mixes the two
    plan = _read(".github/actions/plan-stage/stage.py")
    assert "context_as_args" not in plan
    review = _read(".github/actions/review-stage/stage.py")
    assert "context_as_args" not in review


def test_extract_prompt_forbids_editing_existing_files():
    """(requirement-extraction "extraction writes one new file named after
    the issue") the prompt's contract: exactly one new file, and no
    existing feature file may differ from the baseline — a changed
    existing file is a violation the guard reverts."""
    prompt = _read("pi-prompts/requirements.md")
    assert "exactly one new file" in prompt
    assert "Never edit an existing" in prompt
    assert "byte-identical" in prompt
    stage = _read(".github/actions/extract-stage/stage.py")
    assert "no existing feature file may differ from the baseline" in stage


def test_extract_prompt_tolerates_arc42_structure_variance():
    """(safety "the factory tolerates arc42 structure variance") the
    extraction prompt carries the structural-variance rule verbatim: it
    tolerates the structural difference, and extraction proceeds on the
    readable parts."""
    prompt = _read("pi-prompts/requirements.md")
    assert "Tolerate arc42 structure variance" in prompt
    assert "tolerates the structural difference" in prompt
    assert "proceeds on the readable parts" in prompt


def test_planner_context_falls_back_to_top_level_arc42():
    """(plan "the plan is grounded in the current architecture") the
    context builders reference the top-level PLAN.md as the arc42 set
    where the doc dir yields no arc42 files — both builders, identically
    guarded."""
    stages = _read(".github/scripts/stages.py")
    marker = 'if not dir_files(doc, at_prefix=False) and os.path.isfile("PLAN.md")'
    assert stages.count(marker) == 2  # project_context + changed_requirements_context


def test_consumer_workflow_pins_owner_and_version_tag():
    """(reuse-by-ref "the factory is invoked as a reusable workflow") the
    consumer workflow uses the oracle's owner at a version tag — a moving
    branch ref is not a stable ref — and passes issue-number + the factory
    settings via with: and GH_TOKEN via secrets:; the README's example
    agrees on the owner and the ref."""
    text = _read(".github/workflows/code-weaver.yml")
    m = re.search(r"uses:\s*([\w.-]+)/code-weaver/(\S+?)@([\w.-]+)", text)
    assert m, "no uses: line naming the factory"
    owner, path, ref = m.groups()
    assert owner == "MelvinKl", f"oracle pins the MelvinKl owner, found {owner}"
    assert path.rstrip() == ".github/workflows/factory.yml"
    assert re.fullmatch(r"v\d+\.\d+\.\d+", ref), f"@{ref} is not a version tag"
    assert "with:" in text and "GH_TOKEN" in text and "secrets:" in text
    # the README's consumption example agrees on the owner and the ref
    readme = _read("README.md")
    rm = re.search(r"uses:\s*([\w.-]+)/code-weaver/(\S+?)@([\w.-]+)", readme)
    assert rm and rm.groups()[:2] == (owner, path), "README example drifted from the deployed workflow"


def test_review_stage_judges_only_changed_feature_files():
    """(test-and-review "Gherkin scenarios run as executable acceptance
    tests" / "each requirement is checked for fulfilment" — delta scope) the
    review's pi context lists the feature files changed against the run's
    baseline, never the whole requirements dir (re-judging the accumulated
    oracle on every run is the unbounded work the review must not do), and a
    run that changed no requirements passes vacuously (the empty verdict
    block is the answer, not an unparseable failure)."""
    review = _read(".github/actions/review-stage/stage.py")
    # the context is delta-scoped through the shared changed-requirements
    # builder — and the old whole-dir slice is gone
    assert "changed_requirement_files()" in review
    assert "stages.dir_files(req, at_prefix=False)" not in review
    # the prompt names the changed files when there are any
    assert "feature files this run changed" in review
    # a delta-free run is a vacuous pass, not a zero-verdict failure
    assert "not delta_feature_files()" in review
    assert "no changed requirements" in review
    # and the oracle's prompt agrees on the scope
    prompt = _read("pi-prompts/review.md")
    assert "of the changed\n   feature files only" in prompt
    assert "Do NOT re-judge scenarios from other feature files" in prompt


def test_pr_body_generated_by_pi():
    """(pr-and-gates "a pull request is opened against the target branch")
    stage 12 generates the PR body with pi from the requirements, the
    plan and the review — the template assembler is the fallback, and the
    body still references the source issue."""
    factory = _read(".github/workflows/factory.yml")
    assert "Generate the PR body with pi" in factory
    assert "pr-body" in factory
    prompt = _read("pi-prompts/pr-body.md")
    assert "the requirements" in prompt and "the plan" in prompt and "the review" in prompt
    assert "Reference the source issue" in prompt


def test_report_falls_back_to_top_level_arc42():
    """(reporting "the arc42 documents the AI activity"; safety "an audit
    trail exists for human review") the report stage appends the
    AI-activity section to the arc42 markdown under the doc dir — and
    falls back to the top-level PLAN.md where a target has no doc dir."""
    action = _read(".github/actions/report/action.yml")
    assert '## AI activity (code-weaver)' in action
    assert 'elif os.path.isfile("PLAN.md")' in action
    docs = os.path.join(ROOT, "docs")
    assert os.path.isdir(docs), "the repo's arc42 set lives under docs/ (one chapter per file)"
    ch1 = os.path.join(docs, "01-introduction.md")
    assert os.path.isfile(ch1)
    assert "## AI activity (code-weaver)" in open(ch1, encoding="utf-8").read()


def test_validator_skips_when_parser_port_absent():
    """(test-and-review "the suite runs on an interpreter without pytest")
    where the official Gherkin-parser port is absent, the oracle check is
    skipped-not-failed: validate_file reports a skip and exits clean, and
    the validator's own parser-dependent unit tests skip with it."""
    spec = importlib.util.spec_from_file_location(
        "gw_stage_contract",
        os.path.join(ROOT, ".github", "scripts", "gherkin-validate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    real = mod.Parser
    try:
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd()
            os.chdir(d)
            try:
                with open("ok.feature", "w", encoding="utf-8") as f:
                    f.write("Feature: a tiny oracle\n  Scenario: it parses\n    Given x\n")
                mod.Parser = None  # simulate an interpreter without the port
                rc, errs = mod.validate_file("ok.feature")
                assert rc == 0, f"absent port must not fail, got rc={rc}: {errs}"
                assert any("skipped" in e for e in errs)
            finally:
                os.chdir(cwd)
        # the test file carries the skip guards for its parser-dependent tests
        tv = _read("tests/test_validator.py")
        assert tv.count("if Parser is None") >= 4
    finally:
        mod.Parser = real


def _workflow_input_default(factory: str, name: str) -> str:
    """A reusable-workflow input's default, line-based (stdlib only — the
    inputs block is flat, and the whole-document yaml parse this repo's
    trigger-contract tests deliberately avoid is not needed here)."""
    lines = factory.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip() == f"{name}:":
            for j in range(i + 1, min(i + 5, len(lines))):
                m = re.search(r'^\s+default:\s*"([^"]*)"', lines[j])
                if m:
                    return m.group(1)
            break
    raise AssertionError(f"no default found for input {name!r}")


def test_loop_cap_defaults_match_oracle():
    """(configuration "the loop caps are configurable", "a loop cap of 0
    means no cap") the oracle's Given pins the factory's defaults as
    MAX_LOOPS 5 / MAX_TOTAL_TOKENS 500000 — the reusable workflow declares
    exactly that pair, and the doc surface that repeats the values (the
    PLAN.md §5 config table, the README's input table, the arc42 quality
    chapter) agrees with it; the old 25 / 5,000,000 pair is gone from the
    tree. A target still lowers or raises the caps per repo — the
    inputs → job env → caps_ok machinery is unchanged (0 = no cap)."""
    factory = _read(".github/workflows/factory.yml")
    assert _workflow_input_default(factory, "max-loops") == "5", \
        "the oracle pins the MAX_LOOPS default as 5"
    assert _workflow_input_default(factory, "max-tokens") == "500000", \
        "the oracle pins the MAX_TOTAL_TOKENS default as 500000"
    plan = _read("PLAN.md")
    readme = _read("README.md")
    quality = _read("docs/09-quality-requirements.md")
    assert "| `max-loops` | `5` |" in plan
    assert "| `max-tokens` | `500000` |" in plan
    assert "| `max-loops` | `5` |" in readme
    assert "| `max-tokens` | `500000` |" in readme
    assert "default 5" in quality
    assert "default 500,000" in quality
    # the old declared pair is gone from every surface that repeats it
    assert "| `max-loops` | `25` |" not in plan
    assert "| `max-tokens` | `5000000` |" not in plan
    assert "| `max-loops` | `25` |" not in readme
    assert "| `max-tokens` | `5000000` |" not in readme
    assert "default 25" not in quality
    for surface in (factory, plan, readme, quality):
        assert "5000000" not in surface
        assert "5,000,000" not in surface


def test_implement_guard_allows_only_the_current_issue_plan():
    """(implement "implementation may only edit the current issue's
    plan", "the allow set covers the repo's real layout") the implement
    guard's source dirs exclude the plan dir (alongside the requirements
    dir) while keeping the repo's real code layout (`.github/` for a
    factory repo); the stage re-allows exactly the current issue's plan
    file, so another issue's plan file is a violation the guard reverts —
    the stage docstring's "only that one file" claim is what the code
    does, judged with the guard's own prefix-matching predicate."""
    spec = importlib.util.spec_from_file_location(
        "cw_implement_stage",
        os.path.join(ROOT, ".github", "actions", "implement-stage", "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    saved = {k: os.environ.get(k) for k in ("PLAN_DIR", "REQUIREMENTS_DIR")}
    os.environ["PLAN_DIR"] = "plans"
    os.environ["REQUIREMENTS_DIR"] = "requirements"
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        dirs = mod.source_dirs()
        assert "plans" not in dirs, "the plan dir must not be a source dir"
        assert "requirements" not in dirs, "the requirements dir stays off-limits"
        assert ".github" in dirs, "the repo's real layout stays allowed"
        # main()'s allow construction, replayed: only the current issue's
        # plan file is re-allowed (and the idle-run fallback, which the
        # stage takes only when no issue is resolved, is not this case)
        current = mod.current_plan_path("20", "plans")
        assert current == "plans/20.md"
        assert os.path.isfile(current), "this repo carries its own issue-20 plan"
        allow = list(dirs)
        if current and current not in allow:
            allow.append(current)
        admitted = lambda f: any(f == a or f.startswith(a + "/")
                                 for a in allow)
        assert admitted(current), "the current issue's plan file must be admitted"
        assert not admitted("plans/7.md"), \
            "another issue's plan file must be off-limits"
        assert not admitted("requirements/trigger.feature")
    finally:
        os.chdir(cwd)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
