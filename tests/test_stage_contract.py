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
- the extract prompt places the delta by topic — extending the existing
  topic file, creating a new file only for a topic no file yet covers
  (requirement-extraction "extraction places the delta by topic") — and
  tolerates arc42 structure variance (safety "the factory tolerates arc42
  structure variance");
- the consumer workflow pins the oracle's owner at a version tag — a
  single increasing number, the current scheme (the retired semver ref
  shape is gone) — and wires the run's harness providers through its
  secrets block; the README's example is documentation, not a pinned
  surface — the suite no longer compares its ref against the deployed
  workflow, so a release ref bump on one surface never fails the suite
  until the other is synced (reuse-by-ref "the factory is invoked as a
  reusable workflow", "every published version is a stable ref");
- the factory workflow is self-contained: every stage's steps are inlined
  in the workflow file — no own-action `uses:` reference remains (an
  own-action ref would have to be fully qualified and pinned to a ref the
  release flow could only make consistent by rewriting a workflow file,
  which it must never do; a relative path would resolve against the
  calling repo's checkout) — and every stage job's first step stashes the
  called repo's runtime tree before the first checkout, the stage steps
  running their scripts from that stash (reuse-by-ref "the factory
  workflow is self-contained", "a published version is self-contained");
- the pr job generates the PR body with pi from the requirements, the
  review-stage's verdict scope is delta-bounded (test-and-review: pi
  judges the scenarios of the feature files this run changed, plus the
  scenarios the run's changed tests reference — the accumulated oracle is
  not re-judged every run — and a run that changed no requirements and no
  referencing tests passes vacuously instead of failing as unparseable);
- the pr job generates the PR body with pi from the requirements, the
  plan and the review (pr-and-gates "a pull request is opened against
  the target branch"), and the template fallback — used when the pi call
  produced no body — describes the issue it implements: the source
  issue's number and title read from the trigger's state files (a body
  still names the issue where the job-env relay dropped the values), the
  issue's plan embedded, the requirement scenarios the run changed
  against the baseline listed, and no resolved-configuration dump
  (pr-and-gates "the PR body describes the issue it implements");
- the reviewer's report is fed into the fixer: the review runs on every
  iteration's suite output — red or green (a red suite is never a pass,
  so the review's own breakdown cannot hide one) — and its full captured
  output (the verdict block with each line's evidence, the UNFULFILLED
  lines' "what's missing / what the fix must do", the note on what the
  tests don't cover) is mirrored per iteration into the state dir; the
  fix directive names the report by path (the fixer reads it on demand —
  the no-injection idiom the review call itself uses for the test output)
  and it joins the fix call's path-referenced context; a red iteration
  whose review breaks keeps the fix loop running on the raw output, while
  the same breakdown on a green suite still fails the stage (the oracle
  cannot be assumed green) (test-and-review "The reviewer's report is fed
  into the fixer", "The review judges every iteration, red or green");
- the report stage's AI-activity section falls back to the top-level
  arc42 markdown when the doc dir is absent (reporting "the arc42
  documents the AI activity"; safety "an audit trail exists for human
  review");
- the report stage's final status report lists the run's total input and
  output tokens and the total cost — assembled from the per-call usage
  records in the state dir, the cost derived from the recorded usage, the
  run's resolved model, and the run's model configuration itself — the
  rates are the resolved model's `cost` entry in the configuration the
  setup stage materialises (a non-empty PI_MODELS secret wins over the
  repo file .pi/agent/models.json, and the report lists the source it
  priced from); a model with no cost entry is listed as unpriced — and a
  failed run's report covers the calls made before the stop (issue-43 "the
  final report lists the input and output tokens used during the run",
  "the final report lists the total cost of the run", "the usage and cost
  of a failed run are reported too");
- the report stage re-reads the PR after editing its body: a verified
  completion keeps the pointer comment (the PR body and the issue comment
  list the same usage numbers — one ledger, one set of figures), while a
  completion that could not be applied (the PR was already merged) makes
  the comment self-contained; a successful run closes the source issue
  and a failed run leaves it open (reporting "the PR description carries
  the same usage numbers as the issue comment", "a successful run closes
  the source issue", "a failed run leaves the source issue open");
- the validator skips-not-fails where the parser port is absent
  (test-and-review "the suite runs on an interpreter without pytest");
- the factory's max-loops default matches the oracle's Given (5) and the
  doc surface that repeats the value agrees with it, while the token budget
  is gone from the configuration surface (no max-tokens row on the doc
  surfaces)
  (configuration "the loop caps are configurable", "a loop cap of 0 means
  no cap");
- a file list appears in a stage instruction only where the set is the
  instruction's scope (the plan's changed-requirements list, the guard's
  off-limits list in the repair instructions, the implement target's single
  plan file) and no instruction lists project files as context to rummage
  through (configuration "a stage instruction avoids file lists that carry
  no meaning");
- the implement guard runs inverted-allow: its deny set is the protected
  set (requirements, plans) and its allow set re-admits only the current
  issue's plan file — another issue's plan is a violation the guard repairs
  with a pi call (no stage re-run; a requirements-dir edit does not loop
  back to the plan stage) while the implementation's lane (code, tests,
  docs, new dirs) is admitted (implement "implementation may only edit the
  current issue's plan");
- the shared guard repairs a violation with a pi call, not a git revert
  plus a stage re-run: the repair instructions name the off-limits files,
  instruct the revert, and keep the stage's own work valid against the task
  its initial instructions gave it; a cleared re-check completes the stage
  without re-running its generation (the extract and implement checks —
  guard-rail "a leaking stage is repaired by a pi call, not restarted",
  "a requirement edited during implementation is reverted in place"), the
  repair calls ride the documented pi-call plumbing (each finished call
  appends its usage to the run's ledger — cost-and-token-usage "the usage
  totals cover every pi call the run made"), a cap exhausted without
  clearing fails the stage with the failure report listing the violations,
  and the implement stage's old plan loop-back hook is gone (guard-rail
  "guard repairs are capped", "all three checks share one implementation");
- the plan-check keeps the plan stage inside its one allowed plan file:
  any other change is reverted by the guard's pi call (the shared remedy)
  and the plan stage re-runs its generation on the guard's cleared-repair
  record — the guard re-checks the re-run, a clean plan stage completes
  without re-running, and the extract and implement checks' machinery never
  claims the record (plan "the plan stage may only touch its own plan
  file");
- the gates stage's run query is scoped to the PR's head sha server-side
  and paginated to the end of the result set, a head with no PR-triggered
  workflow is vacuously green after the grace window, and in-progress
  runs keep the gate polling until they complete (pr-and-gates "all
  PR-triggered workflows must be green", "the gate sees the PR's runs on
  a busy repo", "a head with no PR-triggered workflow is vacuously
  green").
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile
import types

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _read(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as f:
        return f.read()


def test_extract_stage_uses_file_argument_context():
    """(setup-pi "pi reads the project files as context"; reference
    `requirements/setup-pi.feature::pi reads the project files as
    context`) the extract
    stage's pi call hands its context to pi as @-file arguments — the
    arc42 markdown, README.md and the baseline diff: the oracle is NOT
    expanded into those arguments (the call's instructions name the
    requirements directory instead, and pi reads the files it judges
    relevant on demand); the plumbing (common.pi_invoke
    context_as_args → stages → extract stage) exists at every layer of the
    call chain."""
    extract = _read(".github/actions/extract-stage/stage.py")
    assert "context_as_args=True" in extract
    stages = _read(".github/scripts/stages.py")
    assert "context_as_args" in stages
    common = _read(".github/scripts/common.py")
    assert "context_as_args" in common
    assert "@-file arguments" in common
    # the context the extract stage assembles: the arc42 markdown,
    # README.md and the baseline diff as the call's @-file arguments, and
    # the oracle NOT expanded into those arguments — the instructions name
    # the requirements directory instead (requirement-extraction
    # "requirements are derived from the project itself")
    assert "baseline.diff" in extract
    assert "include_oracle=False" in extract
    # the other stages keep the path-referenced slice — one invocation
    # never mixes the two
    plan = _read(".github/actions/plan-stage/stage.py")
    assert "context_as_args" not in plan
    review = _read(".github/actions/review-stage/stage.py")
    assert "context_as_args" not in review


def test_extract_prompt_names_the_oracle_directory():
    """(requirement-extraction "the extraction prompt names the oracle
    directory; pi picks the relevant files" — successor of "the context
    handed to pi is concrete files, never directories"; reference
    `requirements/requirement-extraction.feature::The extraction prompt
    names the oracle directory; pi picks the relevant files`) the
    extraction prompt's context paragraph is the directory form: the instructions
    name the requirements directory as the oracle's location and list no
    requirement file by name — pi reads the files it judges relevant from
    that directory on demand. The @-file arguments of the call (the
    non-oracle context) are all files that exist: a directory is never an
    @-argument — pi's @-argument handling reads files, so a directory
    there crashes pi with EISDIR; the shared context builder's
    extract-call form never expands the oracle into those arguments, and
    the plumbing drops any context entry that is not an existing file
    before it becomes an argument."""
    prompt = _read("pi-prompts/requirements.md")
    # the old form is gone: the oracle listed among the files handed to the
    # call — the directory form names the directory instead
    assert "the Gherkin oracle under" not in prompt
    # the directory is named as the oracle's location, and pi reads from
    # it on demand
    assert "The\nGherkin oracle is the requirements directory" in prompt
    assert "decide which of its files" in prompt
    assert "read those from the directory on demand" in prompt
    assert "a directory is never one of them" in prompt
    # the instructions list no requirement file by name — none of the
    # oracle's actual files appears in the template
    reqdir = os.path.join(ROOT, "requirements")
    for f in sorted(os.listdir(reqdir)):
        assert f"requirements/{f}" not in prompt, \
            (f"the instructions list no requirement file by name, "
             f"found {f!r} in the template")
    # the call's @-file arguments are all files that exist: the extract
    # stage assembles them through the shared context builder's
    # extract-call form (the oracle is not expanded into them — the
    # instructions name its directory instead), and every entry is a
    # file that exists — a directory is never an @-argument
    spec = importlib.util.spec_from_file_location(
        "cw_extract_stage",
        os.path.join(ROOT, ".github", "actions", "extract-stage", "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    import shutil
    saved = {k: os.environ.get(k) for k in
             ("REQUIREMENTS_DIR", "DOC_DIR", "RUNNER_TEMP")}
    rt = tempfile.mkdtemp(prefix="cw-extract-ctx-")
    os.environ["REQUIREMENTS_DIR"] = "requirements"
    os.environ["DOC_DIR"] = "docs"
    os.environ["RUNNER_TEMP"] = rt
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        ctx = mod.existing_context()
        for c in ctx:
            assert os.path.isfile(c), \
                (f"every @-file argument of the extract call is a file "
                 f"that exists — a directory is never an @-argument, "
                 f"got {c!r}")
        assert not any(c == "requirements" or c.startswith("requirements/")
                       for c in ctx), \
            (f"the oracle is not expanded into the extract call's "
             f"@-file arguments (its directory is named in the "
             f"instructions instead): {ctx!r}")
        # the non-oracle sources stay the call's @-file arguments
        assert any(c.startswith("docs/") for c in ctx), ctx
        assert "README.md" in ctx, ctx
    finally:
        os.chdir(cwd)
        shutil.rmtree(rt, ignore_errors=True)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_extract_prompt_places_delta_by_topic():
    """(requirement-extraction "extraction places the delta by topic";
    reference
    `requirements/requirement-extraction.feature::Extraction places the
    delta by topic`) the prompt's contract: a delta's scenarios extend
    the existing topic file
    that covers their topic — an edit to an existing file is the placement,
    not a violation — and a new file is created only for a topic no existing
    file covers, named after the topic, never after the issue. The stage
    accordingly no longer reverts a merely changed existing file (it reverts
    one that no longer parses, and a deleted topic file)."""
    prompt = _read("pi-prompts/requirements.md")
    assert "extend the existing topic file" in prompt
    assert "no existing file covers the topic" in prompt
    assert "create a new file named after the topic" in prompt
    stage = _read(".github/actions/extract-stage/stage.py")
    assert "no existing feature file may differ from the baseline" not in stage


def test_extract_prompt_names_files_after_topic():
    """(requirement-extraction "extraction places the delta by topic";
    reference
    `requirements/requirement-extraction.feature::Extraction places the
    delta by topic`)
    the oracle is structured by topic, not by issue: no file name in the
    prompt carries an issue number, and the validator enforces the same
    rule on the changed files (house CI runs it over the whole oracle, so
    the structure holds for the existing files too)."""
    prompt = _read("pi-prompts/requirements.md")
    assert "carries an issue number" in prompt
    validator = _read(".github/scripts/gherkin-validate.py")
    assert "named after an issue" in validator
    assert "ISSUE_NAMED_RE" in validator


def test_extract_prompt_tolerates_arc42_structure_variance():
    """(safety "the factory tolerates arc42 structure variance";
    reference
    `requirements/safety.feature::The factory tolerates arc42 structure
    variance`) the
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
    guarded. The delta is not in the slice: the plan stage's instructions
    carry which requirement files changed and what those files changed,
    and the files themselves stay path-referenced here (plan "the
    planner is told which requirements changed and what those changes
    are"; reference
    `requirements/plan.feature::The plan is grounded in the current
    architecture`,
    `requirements/plan.feature::The planner is told which requirements
    changed and what those changes are`)."""
    stages = _read(".github/scripts/stages.py")
    marker = 'if not dir_files(doc, at_prefix=False) and os.path.isfile("PLAN.md")'
    assert stages.count(marker) == 2  # project_context + changed_requirements_context


def test_planner_instructions_carry_the_changed_requirement_delta():
    """(plan "the planner is told which requirements changed and what
    those changes are" — successor of "the planner is told where the
    changed requirements are, not handed them in full"; reference
    `requirements/plan.feature::The planner is told which requirements
    changed and what those changes are`) the plan stage's
    prompt assembly carries the delta in the instructions: it names the
    requirement file(s) that changed since the baseline and carries what
    those files changed — the baseline diff scoped to them, the delta the
    plan must cover. The call's context stays the path-referenced slice —
    the changed requirement files + the arc42 markdown + the README,
    plain paths, read on demand — and the whole existing oracle is not
    injected into the planner."""
    import shutil
    import subprocess
    spec = importlib.util.spec_from_file_location(
        "cw_plan_stage",
        os.path.join(ROOT, ".github", "actions", "plan-stage", "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ws = tempfile.mkdtemp(prefix="cw-plan-delta-ws-")
    rt = tempfile.mkdtemp(prefix="cw-plan-delta-rt-")
    os.makedirs(os.path.join(ws, "requirements"))
    os.makedirs(os.path.join(ws, "docs"))
    # the oracle: three topic files, of which the run's extraction changes
    # only one — the rest of the oracle is not part of the delta
    with open(os.path.join(ws, "requirements", "guard-rail.feature"), "w") as f:
        f.write("Feature: Guard rail\n"
                "  Scenario: A standing scenario\n"
                "    Given a\n    When b\n    Then c\n")
    with open(os.path.join(ws, "requirements", "plan.feature"), "w") as f:
        f.write("Feature: Planning\n"
                "  Scenario: The planner is told which requirements changed\n"
                "    Given a delta\n"
                "    When the plan stage builds pi's context\n"
                "    Then the instructions name the changed files\n")
    with open(os.path.join(ws, "requirements", "safety.feature"), "w") as f:
        f.write("Feature: Safety\n"
                "  Scenario: Every loop in the pipeline respects its cap\n"
                "    Given a cap\n    When the loop runs\n    Then it stops\n")
    with open(os.path.join(ws, "docs", "01-introduction.md"), "w") as f:
        f.write("# 1. Introduction\n\nThe project.\n")
    with open(os.path.join(ws, "README.md"), "w") as f:
        f.write("# code-weaver\n\nThe factory.\n")
    git_env = {**os.environ,
               "GIT_AUTHOR_NAME": "cw-test", "GIT_AUTHOR_EMAIL": "cw@test",
               "GIT_COMMITTER_NAME": "cw-test", "GIT_COMMITTER_EMAIL": "cw@test",
               "HOME": ws}

    def git(*a, check=True):
        r = subprocess.run(["git", *a], cwd=ws, env=git_env,
                           capture_output=True, text=True)
        if check and r.returncode != 0:
            raise AssertionError(f"git {a} failed: {r.stderr.strip()[:200]}")
        return r

    git("init", "-q")
    git("add", "-A")
    git("commit", "-qm", "baseline")
    base_sha = git("rev-parse", "HEAD").stdout.strip()
    # the baseline stage's state: the baseline ref recorded for the run
    os.makedirs(os.path.join(rt, "cw"), exist_ok=True)
    with open(os.path.join(rt, "cw", "baseline.sha"), "w") as f:
        f.write(base_sha + "\n")
    # the extraction stage's committed work: one oracle file extended
    with open(os.path.join(ws, "requirements", "guard-rail.feature"), "a") as f:
        f.write("  Scenario: The changed scenario\n"
                "    Given x\n    When y\n    Then z\n")
    git("add", "-A")
    git("commit", "-qm", "stage 4 requirements-extraction: generated")
    keys = ("RUNNER_TEMP", "GITHUB_WORKSPACE", "REQUIREMENTS_DIR",
             "DOC_DIR", "PLAN_DIR")
    saved = {k: os.environ.get(k) for k in keys}
    os.environ.update({
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        "REQUIREMENTS_DIR": "requirements",
        "DOC_DIR": "docs",
        "PLAN_DIR": "plans",
    })
    cwd = os.getcwd()
    os.chdir(ws)
    try:
        # the plan stage's prompt file — the prompt pi gets alongside the
        # plan template: the delta rides the instructions
        pf = mod.build_target("42", "plans")
        prompt = open(pf, encoding="utf-8").read()
        # the instructions name the changed requirement file…
        assert "requirements/guard-rail.feature" in prompt, prompt
        # …and carry what it changed — the baseline diff scoped to it
        assert "The changed scenario" in prompt, prompt
        assert "diff --git a/requirements/guard-rail.feature" in prompt, prompt
        # the delta is scoped: the oracle's other files are neither named
        # nor carried — the whole existing oracle is not injected
        assert "plan.feature" not in prompt, prompt
        assert "safety.feature" not in prompt, prompt
        assert "Every loop in the pipeline" not in prompt, prompt
        # the call's context stays the path-referenced slice: the changed
        # requirement file + the arc42 markdown + the README, plain paths
        # (pi reads them on demand)
        ctx = mod.project_context()
        assert "requirements/guard-rail.feature" in ctx, ctx
        assert "docs/01-introduction.md" in ctx, ctx
        assert "README.md" in ctx, ctx
        assert not any(c.startswith("@") for c in ctx), ctx
        assert "requirements/plan.feature" not in ctx, ctx
        assert "requirements/safety.feature" not in ctx, ctx
        # the template's opening is the delta-carrying form — it no longer
        # just points at the changed requirements in the context
        template = _read("pi-prompts/plan.md")
        assert "Turn the **changed**\nrequirements (your context)" not in template
        assert "carries the requirement delta" in template
        assert "plan the delta your instructions carry" in template
    finally:
        os.chdir(cwd)
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_consumer_workflow_pins_owner_and_version_tag():
    """(reuse-by-ref "the factory is invoked as a reusable workflow" — both
    of its consumption shapes — and "a run triggered in the factory's own
    repo works on that repo's code") the consumer workflow consumes the
    factory one of two ways and passes issue-number + the factory settings
    via with: and GH_TOKEN via secrets:. An external target pins the
    oracle's owner, repo and path at a version tag — a moving branch ref is
    not a stable ref — and passes no factory-ref of its own: the file is
    self-contained (its runtime tree embedded), so the single pinned tag
    selects workflow file and runtime tree as one version — while the
    factory keeps the factory-ref input declared as a legacy no-op, and an
    older version's consumer block that still passes it stays schema-valid.
    The ref is a single increasing number, the current scheme's tag shape
    (the retired semver ref shape is gone — reuse-by-ref "every published
    version is a stable ref"). This repo is the factory project itself,
    and its workflow takes the external shape too: it pins the public
    release line (a version tag of the MelvinKl line), so the dogfood
    exercises exactly the published version the external targets get —
    the code a run in it works is still the triggered repo's own. The
    test accepts either shape and asserts the contract of the shape the
    file uses — in both, the with: block passes no factory-ref of its
    own (one ref selects the whole version), while the factory keeps the
    input declared as a legacy no-op. The expected outcome extends to
    the run's pi harness providers (configuration "The pi harness secrets
    ride the reusable workflow's secrets block"): the same three surfaces —
    the factory's secrets: block, the deployed consumer workflow, the README
    example — carry the four provider secret entries in the same form, while
    the uses: shape stays within its pattern (the README's example is
    documentation, not a pinned surface: the suite does not compare its ref
    against the deployed workflow, so a release ref bump on one surface
    never fails the suite until the other is synced; reference
    `requirements/reuse-by-ref.feature::The factory is invoked as a
    reusable workflow`,
    `requirements/reuse-by-ref.feature::A run triggered in the factory's
    own repo works on that repo's code`,
    `requirements/configuration.feature::The pi harness secrets ride the
    reusable workflow's secrets block`,
    `requirements/reuse-by-ref.feature::Every published version is a
    stable ref`)."""
    text = _read(".github/workflows/code-weaver.yml")
    assert "with:" in text and "GH_TOKEN" in text and "secrets:" in text
    m = re.search(r"uses:\s*([\w.-]+)/code-weaver/(\S+?)@([\w.-]+)", text)
    if m:
        # the pinned pattern: owner + path + a version tag — and no
        # factory-ref relayed beside it (the single-pin contract)
        owner, path, ref = m.groups()
        assert owner == "MelvinKl", f"oracle pins the MelvinKl owner, found {owner}"
        assert path.rstrip() == ".github/workflows/factory.yml"
        assert re.fullmatch(r"\d+", ref), (
            f"@{ref} is not a single increasing version number — the "
            "current scheme's tag shape (the retired semver ref shape is gone)")
        assert not re.search(r"factory-ref:\s*\S+", text), (
            "the single-pin pattern passes no factory-ref — one ref selects "
            "the whole version, because the file is self-contained; the "
            "input stays declared in the factory as a legacy no-op, so an "
            "older version's consumer block that still passes it remains "
            "schema-valid")
        factory = _read(".github/workflows/factory.yml")
        assert re.search(r"^\s*factory-ref:", factory, re.M), (
            "the (legacy) factory-ref input stays declared in the factory's "
            "inputs: block — schema compatibility for the with: blocks of "
            "older published versions")
    else:
        # the alternative shape: the consumer calls the factory's own
        # copy by relative uses: (the runner reads the file from the
        # triggering commit) and leaves the factory-ref input empty —
        # the stages run the tree the file embeds
        mrel = re.search(r"uses:\s*\.?/?\.github/workflows/factory\.yml\b", text)
        assert mrel, "no uses: line naming the factory"
        assert not re.search(r"factory-ref:\s*\S+", text), (
            "the dogfood pattern leaves the factory-ref input empty — the "
            "stage jobs run the repo's own runtime tree, never a clone of "
            "the factory repo at a pinned ref")
    readme = _read("README.md")
    # the extension: all three consumer surfaces carry the four harness
    # provider secret entries in the same form — the factory declares them
    # in its workflow_call secrets: block, the deployed workflow and the
    # README example wire them in their own secrets: blocks
    factory = _read(".github/workflows/factory.yml")
    for name in ("PI_MODELS", "PI_SETTINGS", "PI_MCP", "PI_EXTENSION_ENV"):
        assert f"      {name}:" in factory, \
            f"the factory's secrets: block must declare {name} as an optional entry"
        line = f"      {name}: ${{{{ secrets.{name} }}}}"
        assert line in text, \
            f"the deployed consumer workflow must wire {name} in its secrets: block"
        assert line in readme, \
            f"the README example must wire {name} in its secrets: block — same form as the deployed workflow"


def test_factory_upload_steps_opt_into_hidden_files():
    """(the runtime tree the stage jobs execute — reuse-by-ref "a run is
    the factory working the tree of the ref it ran"; reference
    `requirements/reuse-by-ref.feature::The stage jobs materialise the
    runtime tree before their first checkout`) every stage job gets
    the runtime tree from the trigger job's artifact, and the tree lives
    under cw/stash/.github/ — inside a HIDDEN directory. The
    actions/upload-artifact action excludes hidden files by default: a
    step that uploads the run's state dir without
    `include-hidden-files: true` silently drops the .github part of the
    tree, and every stage job that downloads that artifact arrives with
    its stashed stage script missing (run 41126074467 failed exactly this
    way at stage 2, after the single-pin change put the tree in the
    artifact instead of re-cloning it in each stage job)."""
    lines = _read(".github/workflows/factory.yml").splitlines()
    steps, cur = [], None
    for ln in lines:
        if re.match(r"^ {6}- \S", ln) or re.match(r"^  \S", ln):
            if cur is not None:
                steps.append(cur)
            cur = [ln]
        elif cur is not None:
            cur.append(ln)
    if cur is not None:
        steps.append(cur)
    uploads = [s for s in steps if "actions/upload-artifact" in s[0]]
    assert uploads, "no upload-artifact steps found in the factory"
    for s in uploads:
        name = re.search(r"name:\s*(\S+)", "\n".join(s))
        assert name and "include-hidden-files: true" in "\n".join(s), (
            f"the {name.group(1) if name else 'unnamed'} upload step does "
            "not opt into hidden files — the stashed tree under "
            "cw/stash/.github/ would be dropped from its artifact and "
            "every stage job would lose its stashed stage scripts")


def test_factory_workflow_is_self_contained():
    """(reuse-by-ref "the factory workflow is self-contained"; the
    successor of "the factory's workflow names its own actions by owner,
    repo and path" and the in-file half of "a published version is
    self-consistent"; reference
    `requirements/reuse-by-ref.feature::The factory workflow is
    self-contained`) no `uses:` reference to the factory's own actions
    remains — an own-action ref would have to be fully qualified
    (MelvinKl/code-weaver/.github/actions/<name>@<ref>) and pinned to a
    ref the release flow could only make consistent by rewriting a
    workflow file before the tag (a push that updates a workflow file —
    the github-actions App behind the publishing token is refused it,
    `workflows` not being a permission available to it), and a relative
    path would resolve against the calling repo's checkout, where a
    target holds no copy of the factory's scripts. The stage steps are
    inlined instead: every stage job carries the former action's steps at
    its former splice site, runs their scripts from the runtime tree the
    job's first step stashed into $RUNNER_TEMP, and no stage job is
    without that stash step."""
    text = _read(".github/workflows/factory.yml")
    own_refs = [ln.strip() for ln in text.splitlines()
                if re.search(r"\buses:\s*MelvinKl/code-weaver/\.github/actions/",
                             ln)]
    assert not own_refs, (
        f"factory.yml still references its own actions {own_refs!r} — the "
        "stage steps are inlined in the workflow; an own-action ref would "
        "need a pre-tag rewrite the release flow must never push")
    stashes = len(re.findall(r"Stash the factory runtime tree", text))
    job_keys = ("trigger", "setup-pi", "baseline", "extract", "plan",
                "implement", "review", "pr", "gates", "report")
    jobs = sum(1 for k in job_keys if re.search(rf"(?m)^  {k}:\s*$", text))
    assert stashes == jobs == len(job_keys), (
        f"{stashes} stash steps for {jobs} stage jobs — every stage job's "
        "first step must stash the called repo's runtime tree before its "
        "first checkout")
    for name in ("setup-pi", "baseline", "extract-stage", "plan-stage",
                 "implement-stage", "review-stage", "pi-run", "pr-open",
                 "gates-stage", "report"):
        contig = f"cw/stash/.github/actions/{name}"
        split = f'".github", "actions", "{name}"'
        assert contig in text or split in text, (
            f"the {name} stage does not run its script from the stashed "
            "runtime tree")


def test_review_stage_judges_only_changed_feature_files():
    """(test-and-review "Gherkin scenarios run as executable acceptance
    tests" / "each requirement is checked for fulfilment" — delta scope;
    reference
    `requirements/test-and-review.feature::Gherkin scenarios run as
    executable acceptance tests`,
    `requirements/test-and-review.feature::Each requirement is checked
    for fulfilment`,
    `requirements/test-and-review.feature::A test change is judged by
    the requirement it references`)
    the review's pi context lists the feature files changed against the
    run's baseline, never the whole requirements dir (re-judging the
    accumulated oracle on every run is the unbounded work the review must
    not do); the bounded scope extends to the run's changed test files —
    path-referenced into the review call — and the scenarios their
    docstrings reference, which join the verdict scope; and a run that
    changed no requirements and whose changed tests reference no
    scenario passes vacuously (the empty verdict block is the answer,
    not an unparseable failure)."""
    review = _read(".github/actions/review-stage/stage.py")
    # the context is delta-scoped through the shared changed-requirements
    # builder — and the old whole-dir slice is gone
    assert "changed_requirement_files()" in review
    assert "stages.dir_files(req, at_prefix=False)" not in review
    # the prompt names the changed files when there are any
    assert "feature files this run changed" in review
    # the extended scope: the run's changed test files ride the review
    # call's path-referenced context, and the scenarios their docstrings
    # reference are extracted into the verdict scope
    assert "changed_test_files()" in review
    assert "referenced_scenarios(" in review
    assert "the scenarios the changed tests reference" in review
    # a delta-free run — no changed requirements and no referencing
    # changed test — is a vacuous pass, not a zero-verdict failure
    assert "not delta_feature_files()" in review
    assert "no changed requirements" in review
    # and the oracle's prompt agrees on the scope — the changed feature
    # files' scenarios plus the scenarios the changed tests reference
    prompt = _read("pi-prompts/review.md")
    assert "the scenarios the changed tests reference" in prompt
    assert "Do NOT re-judge scenarios beyond that scope" in prompt


def test_review_judges_a_test_change_by_its_referenced_requirement():
    """(test-and-review "A test change is judged by the requirement it
    references" — the new @review scenario; reference
    `requirements/test-and-review.feature::A test change is judged by
    the requirement it references`) a run whose work changes a test:
    a test that is only for correctness may be changed freely — it
    references nothing, so no verdict is owed on its account and it is
    not a problem on its own; a test that references a requirement is
    judged against that requirement — the changed test's scenario
    reference (the docstring form the implement stage prescribes) is
    extracted into the review's verdict scope, must leave the referenced
    scenario fulfilled after the change, and a test change that leaves
    it unfulfilled is a fix-loop problem like any other unfulfilled
    scenario."""
    spec = importlib.util.spec_from_file_location(
        "cw_review_stage_sandbox",
        os.path.join(ROOT, ".github", "actions", "review-stage",
                     "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # a changed test that references a requirement puts the referenced
    # scenario into the verdict scope — the citation is read from the
    # test's docstrings; a correctness-only test contributes nothing,
    # a path mentioned in prose is not a citation, and a test file that
    # does not parse contributes no references
    import shutil
    ws = tempfile.mkdtemp(prefix="cw-review-ws-")
    saved = {k: os.environ.get(k) for k in ("GITHUB_WORKSPACE",)}
    os.environ["GITHUB_WORKSPACE"] = ws
    try:
        os.makedirs(os.path.join(ws, "tests"))
        with open(os.path.join(ws, "tests", "test_ref.py"), "w") as f:
            f.write(
                '"""The module docstring names no scenario."""\n'
                "def test_referencing():\n"
                "    '''A test that implements a Gherkin scenario cites it\n"
                "    in the machine form.\n"
                "    `requirements/guard-rail.feature::Guard repairs are capped`\n"
                "    '''\n"
                "    assert True\n"
                "def test_correctness_only():\n"
                "    '''A correctness-only check — no Gherkin scenario behind\n"
                "    it; `requirements/safety.feature` is mentioned in prose,\n"
                "    without a citation.\n"
                "    '''\n"
                "    assert True\n"
                "def test_quoting_without_citing():\n"
                "    '''Quotes a scenario name in prose (\"Guard repairs are\n"
                "    capped\") but carries no machine citation — prose is not\n"
                "    a reference.\n"
                "    '''\n"
                "    assert True\n")
        with open(os.path.join(ws, "tests", "test_broken.py"), "w") as f:
            f.write("def test_unparsed(:\n    pass\n")
        refs = mod.referenced_scenarios(["tests/test_ref.py",
                                         "tests/test_broken.py"])
        assert refs == [("guard-rail.feature", "Guard repairs are capped")], (
            "the changed tests' scenario references are extracted from "
            f"their docstrings: {refs!r}")
        # the review prompt carries the judgement rule both ways — a
        # correctness-only test may be changed freely, a referencing test
        # must leave the referenced scenario fulfilled — and the fix loop
        # consumes a test-referenced UNFULFILLED verdict like any other
        # unfulfilled scenario of the run's delta
        prompt = _read("pi-prompts/review.md")
        assert ("A changed test is judged by the requirement it references"
                in prompt)
        assert "only for correctness references no scenario" in prompt
        assert "may be changed freely" in prompt
        assert "must leave that scenario fulfilled after the change" in prompt
        review = _read(".github/actions/review-stage/stage.py")
        assert "The following Gherkin scenarios are UNFULFILLED" in review, \
            "a test change that leaves its referenced scenario unfulfilled is a fix-loop problem"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)


def test_reviewers_report_is_fed_into_the_fixer():
    """(test-and-review "The reviewer's report is fed into the fixer",
    "The review judges every iteration, red or green"; reference
    `requirements/test-and-review.feature::The reviewer's report is fed
    into the fixer`,
    `requirements/test-and-review.feature::The review judges every
    iteration, red or green`)
    the fix directive the stage-11 fixer receives is built from the
    reviewer's report, not a lossy reduction of it: the review runs on
    every iteration's suite output — red or green (a red suite is never
    a pass, so the review's own breakdown cannot hide one; the old form
    skipped the review call on a red iteration) — and its full captured
    output (the verdict block with each line's evidence, the
    UNFULFILLED lines' "what's missing / what the fix must do", the
    note on what the tests don't cover) is mirrored per iteration into
    the state dir; the directive names the report by path — the fixer
    reads it on demand, the no-injection idiom the review call itself
    uses for the test output — and the report joins the fix call's
    path-referenced context; the machine-parsed verdict summary and,
    for a red suite, the raw output tail ride alongside. A red
    iteration whose review breaks keeps the fix loop running on the raw
    output, while the same breakdown on a green suite fails the stage
    (the oracle cannot be assumed green)."""
    review = _read(".github/actions/review-stage/stage.py")
    # the review is no longer conditional on a green suite — every
    # iteration's output is reviewed, red or green
    assert "res, rrc = review(i, out)" in review
    assert "if rc == 0 else" not in review
    # the report is mirrored per iteration into the state dir (→ artifact)
    assert "review-report-" in review
    # the directive names the report by path — the fixer reads it on demand
    assert "(read it)" in review
    # the report joins the fix call's path-referenced context
    assert "report_f" in review
    # the breakdown asymmetry: a green suite with a broken review fails the
    # stage; a red suite never passes, so its broken review keeps the fix
    # loop running on the raw output
    assert "stage fails" in review
    assert "runs on the raw test output" in review
    # the review prompt tells the model its output is what the fixer reads
    prompt = _read("pi-prompts/review.md")
    assert "reads your full output" in prompt


def test_pr_body_generated_by_pi():
    """(pr-and-gates "a pull request is opened against the target
    branch"; reference
    `requirements/pr-and-gates.feature::A pull request is opened
    against the target branch`)
    stage 12 generates the PR body with pi from the requirements, the plan
    and the review — the template assembler is the fallback, and the body
    still references the source issue."""
    factory = _read(".github/workflows/factory.yml")
    assert "Generate the PR body with pi" in factory
    assert "pr-body" in factory
    prompt = _read("pi-prompts/pr-body.md")
    assert "the requirements" in prompt and "the plan" in prompt and "the review" in prompt
    assert "Reference the source issue" in prompt
    # the body describes the issue it implements — and keeps the
    # configuration out of the description (workflow-log material)
    assert "describes the issue" in prompt
    assert "resolved configuration" in prompt


def _pr_fallback_source() -> str:
    """The pr job's template-fallback step, reduced to its runnable python.
    The step's `run: |` block is a bash step that launches python over a
    `<<'EOF'` heredoc; this extracts the heredoc body (from the line that
    opens it to the closing `EOF`) and dedents it to a source string, so
    the same sandbox-exec idiom the report action's step uses applies."""
    lines = _read(".github/workflows/factory.yml").splitlines()
    start = None
    for i, ln in enumerate(lines):
        if "Assemble the PR body" in ln and "template fallback" in ln:
            start = i
            break
    assert start is not None, "the pr job's fallback step is gone"
    # the body runs from the `run: |` line (the step content's own indent
    # is the dedent base — the `run: |` line's would under-strip)
    run_line = next((i for i in range(start + 1, len(lines))
                     if lines[i].strip() == "run: |"), None)
    assert run_line is not None, "the fallback step lost its `run: |` block"
    body, indent = [], None
    for cont in lines[run_line + 1:]:
        if not cont.strip():
            body.append("")
            continue
        ind = len(cont) - len(cont.lstrip(" "))
        if indent is None:
            indent = ind
        body.append(cont[indent:])
    src = body
    her_start = None
    for j, l in enumerate(src):
        if "<<" in l and "EOF" in l:
            her_start = j
            break
    assert her_start is not None, \
        "the fallback step no longer runs python via a heredoc"
    her_end = next((k for k in range(her_start + 1, len(src))
                    if src[k].strip() == "EOF"), None)
    assert her_end is not None, "the fallback heredoc never closes"
    return "\n".join(src[her_start + 1:her_end])


def test_pr_body_fallback_describes_the_issue():
    """(pr-and-gates "the PR body describes the issue it implements";
    reference
    `requirements/pr-and-gates.feature::The PR body describes the issue
    it implements`) the
    template fallback — used when the pi call produced no body —
    describes the issue: it names the source issue's number and title
    from the trigger's state files (a job-env relay that dropped
    CW_ISSUE / CW_TITLE must not yield a body that reads 'issue: # —'),
    embeds the issue's plan, lists the requirement scenarios the run
    changed against the baseline (and only those), and carries no
    resolved-configuration dump."""
    import shutil
    import subprocess
    import tempfile
    src = _pr_fallback_source()
    ws = tempfile.mkdtemp(prefix="cw-pr-ws-")
    rt = tempfile.mkdtemp(prefix="cw-pr-rt-")
    trig = os.path.join(rt, "cw", "state", "trigger")
    os.makedirs(trig)
    os.makedirs(os.path.join(ws, "requirements"))
    with open(os.path.join(ws, "requirements", "topic.feature"), "w") as f:
        f.write("Feature: Topic\n"
                "  Scenario: A standing scenario\n"
                "    Given a\n    When b\n    Then c\n")
    git_env = {**os.environ,
               "GIT_AUTHOR_NAME": "cw-test", "GIT_AUTHOR_EMAIL": "cw@test",
               "GIT_COMMITTER_NAME": "cw-test", "GIT_COMMITTER_EMAIL": "cw@test",
               "HOME": ws}

    def git(*a, check=True):
        r = subprocess.run(["git", *a], cwd=ws, env=git_env,
                           capture_output=True, text=True)
        if check and r.returncode != 0:
            raise AssertionError(f"git {a} failed: {r.stderr.strip()[:200]}")
        return r

    git("init", "-q")
    git("add", "-A")
    git("commit", "-qm", "baseline")
    base_sha = git("rev-parse", "HEAD").stdout.strip()
    # the run's delta: the issue's plan + a new scenario in the topic file
    os.makedirs(os.path.join(ws, "plans"))
    with open(os.path.join(ws, "plans", "42.md"), "w") as f:
        f.write("# Issue #42 — the test plan\n\n**Tasks**\n\n- [x] build the thing\n")
    with open(os.path.join(ws, "requirements", "topic.feature"), "a") as f:
        f.write("  Scenario: The changed scenario\n"
                "    Given x\n    When y\n    Then z\n")
    git("add", "-A")
    git("commit", "-qm", "delta")
    with open(os.path.join(trig, "issue-number.txt"), "w") as f:
        f.write("42\n")
    with open(os.path.join(trig, "issue-title.txt"), "w") as f:
        f.write("The test issue\n")
    with open(os.path.join(trig, "base-sha.txt"), "w") as f:
        f.write(base_sha + "\n")
    out = os.path.join(rt, "cw", "pr-body.md")
    keys = ("PATH", "RUNNER_TEMP", "GITHUB_WORKSPACE", "CW_ISSUE",
            "CW_TITLE", "CW_TARGET", "CW_MODEL", "CW_RUNNER",
            "REQUIREMENTS_DIR", "PLAN_DIR")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        # the job-env relay drops the trigger's values on this runner
        # build — the fallback reads them from the state files instead
        "CW_ISSUE": "",
        "CW_TITLE": "",
        "CW_TARGET": "main",
        "REQUIREMENTS_DIR": "requirements",
        "PLAN_DIR": "plans",
    })
    argv_saved, hook = sys.argv, sys.excepthook
    sys.argv = ["python3", out]
    try:
        exec(compile(src, "<factory.yml pr fallback step>", "exec"),
             {"__name__": "cw_pr_fallback_test"})
        body = open(out, encoding="utf-8").read()
    finally:
        sys.argv, sys.excepthook = argv_saved, hook
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)
    # names the issue from the trigger's state files (the env was empty)
    assert "#42" in body and "The test issue" in body, body
    # embeds the plan — what the run set out to build
    assert "## The plan for this issue" in body
    assert "build the thing" in body, body
    # lists the scenarios the run changed against the baseline, and only
    # those (the standing scenario is not part of the delta)
    assert "The changed scenario" in body, body
    assert "A standing scenario" not in body, body
    # carries no resolved-configuration dump
    assert "## Resolved configuration" not in body, body
    # stage 15 still owns the completion
    assert "Stage 15" in body


def test_report_falls_back_to_top_level_arc42():
    """(reporting "the arc42 documents the AI activity"; safety "an audit
    trail exists for human review"; reference
    `requirements/reporting.feature::The arc42 documents the AI
    activity`,
    `requirements/safety.feature::An audit trail exists for human
    review`) the report stage appends the
    AI-activity section to the arc42 markdown under the doc dir — and
    falls back to the top-level PLAN.md where a target has no doc dir."""
    action = _read(".github/workflows/factory.yml")
    assert '## AI activity (code-weaver)' in action
    assert 'elif os.path.isfile("PLAN.md")' in action
    docs = os.path.join(ROOT, "docs")
    assert os.path.isdir(docs), "the repo's arc42 set lives under docs/ (one chapter per file)"
    ch1 = os.path.join(docs, "01-introduction.md")
    assert os.path.isfile(ch1)
    assert "## AI activity (code-weaver)" in open(ch1, encoding="utf-8").read()


def _report_action_source() -> str:
    """The report stage's inline python — its `run: |` block (the step's
    whole body), dedented to a runnable source. The stage's steps are
    inlined in the workflow (the former action file is gone), so the block
    is read off the report job's inlined status-report step. The tests exec
    it against a sandboxed state dir: the assembled report is a function of
    the state dir's contents (the per-call usage ledger, the trigger's
    resolved configuration) and the step's env, so no live workflow is
    needed."""
    lines = _read(".github/workflows/factory.yml").splitlines()
    lines = lines[lines.index(next(ln for ln in lines
                                   if ln.startswith("  report:"))):]
    step = None
    for i, ln in enumerate(lines):
        if "Write the final status report" in ln:
            step = i
            break
    assert step is not None, "the report stage's status-report step is gone"
    for i in range(step, len(lines)):
        if lines[i].lstrip() == "run: |":
            body, indent = [], None
            for cont in lines[i + 1:]:
                if not cont.strip():
                    body.append("")
                    continue
                ind = len(cont) - len(cont.lstrip(" "))
                if ind <= 8:
                    break
                if indent is None:
                    indent = ind
                body.append(cont[indent:])
            src = "\n".join(body)
            assert src.lstrip().startswith("try:"), \
                "the step's run block is no longer the status-report python"
            return src
    raise AssertionError(
        "no `run: |` block on the report stage's status-report step")


def _models_config(r_in: float, r_out: float) -> str:
    """A minimal pi models.json (the shape the setup stage parses) with one
    provider: Ornith priced at the given USD-per-1M rates, and a second
    model with no `cost` entry — the unpriced case the report lists when
    the configuration carries the model but not its rates."""
    return ('{\n'
            '  "providers": {\n'
            '    "test": {\n'
            '      "baseUrl": "http://example.invalid/v1",\n'
            '      "api": "openai-completions",\n'
            '      "models": [\n'
            '        {"id": "Ornith-1.5-35B-A3B",\n'
            f'         "cost": {{"input": {r_in}, "output": {r_out},\n'
            '                  "cacheRead": 0.05, "cacheWrite": 0}},\n'
            '        {"id": "Some-Other-Runner-Model",\n'
            '         "contextWindow": 8192}\n'
            '      ]\n'
            '    }\n'
            '  }\n'
            '}\n')


def _run_report_action(run_result="success", pr_number="7", issue_number="42",
                       ledger=None, model="Ornith-1.5-35B-A3B",
                       view_body="## Progress so far",
                       shared_module="fallback",
                       models_config=None, pi_models_env=None):
    """Exec the report action's inline python in a sandbox: a plain temp
    workspace (no git repo, no doc dir, no PLAN.md — the arc42-activity
    path has nothing to touch), a temp RUNNER_TEMP carrying the merged
    stage state (the per-call usage ledger the report job's artifact
    downloads leave behind, plus the trigger's resolved configuration),
    and a fake `gh` on PATH that serves the PR view and captures the issue
    comment body it is posted with — no network. The PR view the fake
    serves is `view_body` for EVERY read (before and after the edit):
    '## Progress so far' simulates a PR whose body never took the
    completion (already merged / edit refused), a body carrying the
    '## Final status' marker simulates a verified completion. Returns
    (the final PR body, the issue comment, whether the source issue was
    closed).

    `shared_module` parameterises the step's `import common` resolution:
    the default "fallback" is the forced-fallback setup every standing
    test in this file relies on — the scripts dir scrubbed from sys.path
    and the `common` module popped from sys.modules, so the import fails
    and the body runs on the step's local fallback definitions (the path
    this runner build takes in production); "import" instead stashes a
    copy of the repo's .github tree into the sandbox's
    $RUNNER_TEMP/cw/stash — the tree the report job's first step stashes
    before its first checkout — so the step's own scripts-dir insertion
    resolves the shared module from the stashed tree and the shared
    module's definitions bind the body's five plumbing names (the import
    path task 1's test pins). The `common` module is popped from
    sys.modules either way: a module another test module cached would
    satisfy the import in place of the tree."""
    import shutil
    import tempfile
    ws = tempfile.mkdtemp(prefix="cw-report-ws-")
    rt = tempfile.mkdtemp(prefix="cw-report-rt-")
    cw = os.path.join(rt, "cw")
    os.makedirs(cw)
    if ledger is not None:
        with open(os.path.join(cw, "tokens.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(ledger) + "\n")
    with open(os.path.join(cw, "resolved-config.txt"), "w", encoding="utf-8") as f:
        f.write("### Code Weaver — resolved configuration "
                "(workflow log; never committed)\n"
                f"- issue: #{issue_number}\n"
                f"- LLM model (which configured model): `{model}`\n"
                f"- caps: max-loops=`5` (0 = no cap)\n")
    with open(os.path.join(cw, "stage-summary.txt"), "w", encoding="utf-8") as f:
        f.write("stage 4 extract: clean — stage complete\n")
    if models_config is not None:
        # the run's model configuration as the repo-file provider — the
        # .pi/agent/models.json the report job resolves in the workspace
        # (the provider the setup stage falls back to when the secret is
        # absent)
        agent = os.path.join(ws, ".pi", "agent")
        os.makedirs(agent)
        with open(os.path.join(agent, "models.json"), "w", encoding="utf-8") as f:
            f.write(models_config)
    fake = tempfile.mkdtemp(prefix="cw-report-fake-")
    binp = os.path.join(fake, "bin")
    os.makedirs(binp)
    comment_f = os.path.join(fake, "issue-comment.txt")
    view_json = json.dumps(
        {"body": view_body,
         "head": {"sha": "f" * 40, "ref": "ai/code-weaver/7"},
         "html_url": "https://gh.example/pr/7"})
    with open(os.path.join(binp, "gh"), "w", encoding="utf-8") as f:
        f.write("#!%s\n" % sys.executable +
                "import json, os, sys\n"
                "args = sys.argv[1:]\n"
                "body = ''\n"
                "for a in args:\n"
                "    if a.startswith('body='):\n"
                "        body = a[len('body='): ]\n"
                "if args[:1] == ['api'] and any('pulls/' in a for a in args):\n"
                f"    print({view_json!r})\n"
                "    sys.exit(0)\n"
                "if args[:1] == ['api'] and 'state=closed' in args:\n"
                "    open(os.environ['FAKE_GH_OUT'] + '.closed', 'w')"
                ".write('closed')\n"
                "if body:\n"
                "    open(os.environ['FAKE_GH_OUT'], 'w').write(body)\n"
                "if args[:2] == ['pr', 'edit'] and '--body-file' in args:\n"
                "    bf = args[args.index('--body-file') + 1]\n"
                "    open(os.environ['FAKE_GH_OUT'] + '.pr-body', 'w')"
                ".write(open(bf).read())\n")
    os.chmod(os.path.join(binp, "gh"), 0o755)
    keys = ("PATH", "RUNNER_TEMP", "GITHUB_WORKSPACE", "GITHUB_REPOSITORY",
            "GH_TOKEN", "GITHUB_ACTION_PATH", "AI_BRANCH", "DOC_DIR",
            "CW_RUN_RESULT", "CW_PR_NUMBER", "CW_ISSUE_NUMBER",
            "CW_PI_MODELS", "INPUT_PI_MODELS", "FAKE_GH_OUT")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "PATH": binp + os.pathsep + (saved["PATH"] or ""),
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        "GITHUB_REPOSITORY": "code-weaver/test-target",
        "GH_TOKEN": "fake-token",
        "GITHUB_ACTION_PATH": "",
        "FAKE_GH_OUT": comment_f,
        "CW_RUN_RESULT": run_result,
        "CW_ISSUE_NUMBER": issue_number,
        "CW_PR_NUMBER": pr_number,
        # the run's model configuration provider relay — set when the test
        # names pi_models_env (the secret wins over the repo file), empty
        # otherwise (an empty provider value is an absent provider)
        "CW_PI_MODELS": pi_models_env or "",
    })
    hook, cwd = sys.excepthook, os.getcwd()
    os.chdir(ws)
    # a `common` module another test module cached in this process is
    # popped first (restored in the finally): it would satisfy the step's
    # import in place of the tree and the resolution under test would not
    # be the one that ran.
    common_mod = sys.modules.pop("common", None)
    path_saved = list(sys.path)
    if shared_module == "fallback":
        # the forced-fallback setup every standing test in the file relies
        # on: the action's `import common` must fail here, as it does on
        # this runner build (the action dir's `/./` segment breaks the
        # scripts path resolution): the action then runs on its local
        # fallback definitions — the path production takes. Otherwise the
        # scripts dir already on sys.path would satisfy the import and the
        # fallback definitions would never land.
        scripts_dir = os.path.realpath(
            os.path.join(ROOT, ".github", "scripts"))
        sys.path[:] = [p for p in sys.path
                       if p and os.path.realpath(p) != scripts_dir]
    else:
        # the import path: the report job's first step stashed the runtime
        # tree to $RUNNER_TEMP/cw/stash before its first checkout — the
        # copy below is that same tree, so the step's own scripts-dir
        # insertion puts a resolvable scripts dir at the front of sys.path
        # and the shared module resolves from the stashed tree
        shutil.copytree(os.path.join(ROOT, ".github"),
                        os.path.join(cw, "stash", ".github"))
    out = {"pr_body": "", "comment": ""}
    try:
        try:
            exec(compile(_report_action_source(),
                          "<report action.yml run block>", "exec"),
                 {"__name__": "cw_report_action_test"})
        except SystemExit:
            pass
        pf = os.path.join(cw, "final-pr-body.md")
        if os.path.isfile(pf):
            out["pr_body"] = open(pf, encoding="utf-8").read()
        if os.path.isfile(comment_f):
            out["comment"] = open(comment_f, encoding="utf-8").read()
        out["closed"] = os.path.isfile(comment_f + ".closed")
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        sys.path[:] = path_saved
        if common_mod is not None:
            sys.modules["common"] = common_mod
        else:
            # the import path ran: drop the module it loaded from the
            # stash (the temp tree is removed below) so no later test
            # picks it up
            sys.modules.pop("common", None)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)
        shutil.rmtree(fake, ignore_errors=True)
    return out["pr_body"], out["comment"], out["closed"]


def test_report_step_plumbing_is_bound_on_the_import_path():
    """(reporting "The report step's plumbing is bound on a runner where the
    shared module imports" — new scenario; reference
    `requirements/reporting.feature::The report step's plumbing is bound
    on a runner where the shared module imports`) on a runner where the
    shared module resolves from the runtime tree the report job stashed to
    $RUNNER_TEMP before its first checkout, the step's `import common`
    succeeds, and its five plumbing names — the state dir, the state file,
    the log, the gh api, the branch push — are bound for the step's body to
    the shared module's definitions: the body's bare-name calls resolve on
    that path, the step does not die with an undefined-name error before
    any of its report work has run (the crash wrapper's stage-fail-reason
    diagnosis is not produced), and the report completes (the final PR body
    carries the final status, the issue comment is posted, a successful run
    closes the source issue). The sandbox mirrors the standing harness (a
    temp workspace, a merged-state RUNNER_TEMP, a fake `gh` on PATH) with
    the import resolution flipped: the stashed runtime tree carries a
    resolvable scripts dir, so the step's own scripts-dir insertion puts the
    shared module on sys.path and the import lands. A `common` cached in
    sys.modules by another test module would satisfy the import without
    resolving from the stashed tree — it is popped for the run (restored
    after) so the stash is the resolution source."""
    import shutil
    ws = tempfile.mkdtemp(prefix="cw-report-ws-")
    rt = tempfile.mkdtemp(prefix="cw-report-rt-")
    cw = os.path.join(rt, "cw")
    os.makedirs(cw)
    # the report job's first step stashed the runtime tree to
    # $RUNNER_TEMP/cw/stash before its first checkout — the tree the step's
    # scripts-dir resolution reads, so on a runner where that path works the
    # shared module resolves from the stash
    shutil.copytree(os.path.join(ROOT, ".github"),
                    os.path.join(cw, "stash", ".github"))
    with open(os.path.join(cw, "resolved-config.txt"), "w", encoding="utf-8") as f:
        f.write("### Code Weaver — resolved configuration "
                "(workflow log; never committed)\n"
                "- issue: #42\n"
                "- LLM model (which configured model): `Ornith-1.5-35B-A3B`\n"
                "- caps: max-loops=`5` (0 = no cap)\n")
    with open(os.path.join(cw, "stage-summary.txt"), "w", encoding="utf-8") as f:
        f.write("stage 4 extract: clean — stage complete\n")
    fake = tempfile.mkdtemp(prefix="cw-report-fake-")
    binp = os.path.join(fake, "bin")
    os.makedirs(binp)
    comment_f = os.path.join(fake, "issue-comment.txt")
    # a PR view carrying the '## Final status' marker: a verified completion
    view_json = json.dumps(
        {"body": "## Progress so far\n\n## Final status\n"
                "- **Run result:** success\n",
         "head": {"sha": "f" * 40, "ref": "ai/code-weaver/42"},
         "html_url": "https://gh.example/pr/7"})
    with open(os.path.join(binp, "gh"), "w", encoding="utf-8") as f:
        f.write("#!%s\n" % sys.executable +
                "import json, os, sys\n"
                "args = sys.argv[1:]\n"
                "body = ''\n"
                "for a in args:\n"
                "    if a.startswith('body='):\n"
                "        body = a[len('body='): ]\n"
                "if args[:1] == ['api'] and any('pulls/' in a for a in args):\n"
                f"    print({view_json!r})\n"
                "    sys.exit(0)\n"
                "if args[:1] == ['api'] and 'state=closed' in args:\n"
                "    open(os.environ['FAKE_GH_OUT'] + '.closed', 'w')"
                ".write('closed')\n"
                "if body:\n"
                "    open(os.environ['FAKE_GH_OUT'], 'w').write(body)\n"
                "if args[:2] == ['pr', 'edit'] and '--body-file' in args:\n"
                "    bf = args[args.index('--body-file') + 1]\n"
                "    open(os.environ['FAKE_GH_OUT'] + '.pr-body', 'w')"
                ".write(open(bf).read())\n")
    os.chmod(os.path.join(binp, "gh"), 0o755)
    keys = ("PATH", "RUNNER_TEMP", "GITHUB_WORKSPACE", "GITHUB_REPOSITORY",
            "GH_TOKEN", "GITHUB_ACTION_PATH", "AI_BRANCH", "DOC_DIR",
            "CW_RUN_RESULT", "CW_PR_NUMBER", "CW_ISSUE_NUMBER", "FAKE_GH_OUT")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "PATH": binp + os.pathsep + (saved["PATH"] or ""),
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        "GITHUB_REPOSITORY": "code-weaver/test-target",
        "GH_TOKEN": "fake-token",
        "GITHUB_ACTION_PATH": "",
        "FAKE_GH_OUT": comment_f,
        "CW_RUN_RESULT": "success",
        "CW_ISSUE_NUMBER": "42",
        "CW_PR_NUMBER": "7",
    })
    hook, cwd = sys.excepthook, os.getcwd()
    common_mod = sys.modules.pop("common", None)
    path_saved = list(sys.path)
    os.chdir(ws)
    ns = {"__name__": "cw_report_action_import_path"}
    crashed = False
    pr_body = comment = ""
    closed = False
    try:
        try:
            exec(compile(_report_action_source(),
                          "<report action.yml run block>", "exec"), ns)
        except SystemExit:
            pass
        crashed = os.path.isfile(os.path.join(cw, "stage-fail-reason.txt"))
        pf = os.path.join(cw, "final-pr-body.md")
        if os.path.isfile(pf):
            pr_body = open(pf, encoding="utf-8").read()
        if os.path.isfile(comment_f):
            comment = open(comment_f, encoding="utf-8").read()
        closed = os.path.isfile(comment_f + ".closed")
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        sys.path[:] = path_saved
        if common_mod is not None:
            sys.modules["common"] = common_mod
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)
        shutil.rmtree(fake, ignore_errors=True)
    # the shared module resolved from the stashed runtime tree — the import
    # path's resolution source, not a copy elsewhere on sys.path
    mod = ns.get("common")
    assert isinstance(mod, types.ModuleType), \
        "the import path: `import common` must resolve the shared module"
    assert os.path.realpath(mod.__file__).startswith(
        os.path.realpath(os.path.join(cw, "stash", ".github", "scripts"))), \
        ("the shared module must resolve from the runtime tree the job "
         f"stashed to $RUNNER_TEMP, got {mod.__file__!r}")
    # the five plumbing names are bound for the step's body to the shared
    # module's definitions — the body's bare-name calls resolve on the
    # import path
    for name in ("state_dir", "state_file", "log", "gh_api", "push_branch"):
        assert ns.get(name) is getattr(mod, name), \
            (f"the import path must bind the body's {name} to the shared "
             f"module's definition, got {ns.get(name)!r}")
    # the step completes rather than crashing: the crash wrapper's
    # stage-fail-reason diagnosis (the one it writes before any report work)
    # is not produced — an undefined-name error would have written it
    assert not crashed, \
        ("the step died with an error before any report work — the crash "
         "wrapper's diagnosis was produced on the import path")
    # the report completes on the import path: the final PR body carries the
    # final status, the issue comment is posted, a successful run closes the
    # source issue
    assert "## Final status" in pr_body and "success" in pr_body, \
        f"the final PR body must carry the final status: {pr_body!r}"
    assert comment, "the issue comment must be posted on the import path"
    assert closed, "a successful run closes the source issue"


def test_report_fallback_plumbing_completes_the_report_as_the_import_path():
    """(reporting "The report step's fallback plumbing stays effective
    where the shared module cannot import" — new scenario; the "stays
    effective" half is the standing stage-contract tests, which force the
    import failure and assert the report the forced-fallback run
    completes; reference
    `requirements/reporting.feature::The report step's fallback plumbing
    stays effective where the shared module cannot import`) where the
    shared module does not resolve from the runtime
    tree, the step's ImportError branch stays in force — the body runs on
    its local fallback definitions and completes its report AS ON THE
    IMPORT PATH: the two paths are behaviourally equivalent for the
    report's output — one ledger, one set of numbers on both surfaces.
    The standing sandbox runs on both import resolutions (the
    forced-fallback path the standing tests use — the scripts dir scrubbed
    from sys.path, the `common` module popped; and the import path task 1
    makes work — the shared module resolving from the runtime tree the job
    stashed to $RUNNER_TEMP) and the two completed reports are asserted to
    agree: the same final-status content on the PR-body surface and the
    same issue comment — the usage totals, the stage outcomes, the
    pointer-vs-self-contained comment form — and the same close state."""
    ledger = ["10000 2000", "5000 1500"]
    # the run's one ledger: the totals every surface of both paths'
    # reports must carry
    totals = ("- **Total input tokens:** 15000",
              "- **Total output tokens:** 3500")
    # the completion timestamp is minute-granularity and the two runs may
    # straddle a minute boundary — normalise it before the equality
    norm = lambda s: re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC",
                            "<completed>", s)
    # the two comment forms the completion verification selects: a
    # verified completion keeps the pointer comment, a completion that
    # could not be applied makes the comment self-contained
    for view_body in ("## Progress so far\n\n## Final status\n- stale\n",
                      "## Progress so far"):
        fb_body, fb_comment, fb_closed = _run_report_action(
            ledger=ledger, view_body=view_body)
        im_body, im_comment, im_closed = _run_report_action(
            shared_module="import", ledger=ledger, view_body=view_body)
        for pr_body, comment, closed in (
                (fb_body, fb_comment, fb_closed),
                (im_body, im_comment, im_closed)):
            # the report completes on that path: the PR body carries the
            # final status, the usage totals and the stage outcomes
            assert "## Final status" in pr_body and "success" in pr_body, \
                f"the final PR body must carry the final status: {pr_body!r}"
            for line in totals:
                assert line in pr_body, \
                    f"the PR body lists the run's totals: {pr_body!r}"
                assert line in comment, \
                    f"the issue comment lists the same totals: {comment!r}"
            assert "### Stage outcomes" in pr_body, pr_body
            assert "stage 4 extract: clean" in pr_body, pr_body
            if "## Final status" in view_body:
                assert "final status is in the PR body" in comment, \
                    (f"a verified completion keeps the pointer comment: "
                     f"{comment!r}")
            else:
                assert "could not be completed" in comment, comment
                assert "### Stage outcomes" in comment, comment
                assert "stage 4 extract: clean" in comment, comment
            assert closed, "a successful run closes the source issue"
        # the two completed reports agree: the same final-status content
        # on the PR-body surface and the same issue comment (the usage
        # totals, the stage outcomes, the pointer-vs-self-contained form)
        # and the same close state
        assert norm(im_body) == norm(fb_body), \
            ("the fallback-completed report must equal the import path's: "
             f"{im_body!r} != {fb_body!r}")
        assert norm(im_comment) == norm(fb_comment), \
            ("the fallback-completed issue comment must equal the import "
             f"path's: {im_comment!r} != {fb_comment!r}")
        assert im_closed == fb_closed, \
            (f"the close state must agree on both paths: "
             f"{im_closed} != {fb_closed}")


def test_report_lists_usage_totals_assembled_from_the_ledger():
    """(issue-43 "the final report lists the input and output tokens used
    during the run", "the usage totals cover every pi call the run
    made"; reference
    `requirements/cost-and-token-usage.feature::The final report lists
    the input and output tokens used during the run`,
    `requirements/cost-and-token-usage.feature::The usage totals cover
    every pi call the run made`)
    the report action assembles the run's usage totals from the per-call
    usage records in the state dir (one tokens.txt line per pi call: input
    + output tokens; the report job downloads the stages' artifacts in
    pipeline order, so the ledger surviving the downloads is the complete
    one) into the final status report: the PR body lists the total input
    and the total output tokens across the run, and the source-issue
    comment carries the same totals."""
    pr_body, comment, _closed = _run_report_action(
        ledger=["10000 2000", "5000 1500"])
    for surface in (pr_body, comment):
        assert "- **Total input tokens:** 15000" in surface, \
            ("the report must total every pi call the run made "
             f"(10000 + 5000 input): {surface!r}")
        assert "- **Total output tokens:** 3500" in surface, \
            ("the report must total every pi call the run made "
             f"(2000 + 1500 output): {surface!r}")


def test_report_cost_derives_from_usage_and_resolved_model():
    """(issue-43 "the final report lists the total cost of the run" —
    "the listed cost is consistent with the run's recorded token usage";
    reference
    `requirements/cost-and-token-usage.feature::The final report lists
    the total cost of the run`)
    the listed cost is derived from the recorded usage, keyed on the run's
    resolved model (the llm-model setting from the trigger's
    resolved-config state), and priced at the rates the run's model
    configuration declares for that model — the `cost` object of the
    model's models.json entry, read from the configuration's provider the
    way the setup stage resolves it (here the repo file
    .pi/agent/models.json, the source the report lists so the cost stays
    auditable); a model the configuration carries no cost entry for is
    listed as unpriced, and the recorded usage
    totals still land in the report."""
    # 15000 in / 3500 out across the run; the resolved model is priced by
    # the configuration the sandbox writes as the repo file
    ledger = ["10000 2000", "5000 1500"]
    r_in, r_out = 0.10, 0.20
    priced = (f"- **Total cost:** ${(15000 * r_in + 3500 * r_out) / 1e6:.4f} "
              f"(model `Ornith-1.5-35B-A3B` @ ${r_in:.2f}/M input, "
              f"${r_out:.2f}/M output — rates from the repo file "
              f".pi/agent/models.json)")
    pr_body, comment, _closed = _run_report_action(
        ledger=ledger, models_config=_models_config(r_in, r_out))
    for surface in (pr_body, comment):
        assert priced in surface, \
            ("the listed cost must be recorded usage × the resolved model's "
             f"configuration rates, with the source listed: {surface!r}")
    # a model the configuration carries but gives no cost entry for is
    # listed as unpriced — the usage totals are reported regardless
    pr_body, comment, _closed = _run_report_action(
        ledger=ledger, model="Some-Other-Runner-Model",
        models_config=_models_config(r_in, r_out))
    unpriced = (f"- **Total cost:** unpriced (model "
                f"`Some-Other-Runner-Model` has no cost rates in the "
                f"run's model configuration — put the model's cost rates in "
                ".pi/agent/models.json (or the models-configuration "
                f"secret))")
    for surface in (pr_body, comment):
        assert unpriced in surface, \
            f"a model with no cost entry is listed as unpriced: {surface!r}"
        assert "- **Total input tokens:** 15000" in surface
        assert "- **Total output tokens:** 3500" in surface


def test_report_cost_prices_at_the_secret_provider_over_the_repo_file():
    """(the same issue-43 cost pin — provider resolution; reference
    `requirements/cost-and-token-usage.feature::The final report lists
    the total cost of the run`) the rates the report prices with are the
    ones the run's model
    configuration declares, and the configuration is resolved the way the
    setup stage resolves it: a non-empty PI_MODELS secret wins over the
    repo file .pi/agent/models.json. The sandbox carries both providers at
    different rates — the report must list the secret's rates, name the
    provider it priced from, and stay consistent with the recorded
    usage."""
    ledger = ["10000 2000"]
    r_in, r_out = 0.30, 0.40
    priced = (f"- **Total cost:** ${(10000 * r_in + 2000 * r_out) / 1e6:.4f} "
              f"(model `Ornith-1.5-35B-A3B` @ ${r_in:.2f}/M input, "
              f"${r_out:.2f}/M output — rates from the run's model "
              f"configuration (a GitHub secret))")
    pr_body, comment, _closed = _run_report_action(
        ledger=ledger,
        models_config=_models_config(0.10, 0.20),
        pi_models_env=_models_config(0.30, 0.40))
    for surface in (pr_body, comment):
        assert priced in surface, \
            ("a non-empty PI_MODELS secret wins over the repo file — "
             f"the report must price at the secret's rates: {surface!r}")


def test_failed_run_report_covers_the_calls_before_the_stop():
    """(issue-43 "the usage and cost of a failed run are reported too";
    reference
    `requirements/cost-and-token-usage.feature::The usage and cost of a
    failed run are reported too`) the report job runs on success and
    failure: a run that stopped early
    in a failed stage is reported with the usage and cost of the pi calls
    made before the stop — a stage that never ran (its artifact never
    uploaded) contributes nothing, so the totals cover exactly the
    pre-stop calls. The failed run's issue comment lists the tokens and
    the cost (with a PR: alongside the stage outcomes; without one, the
    no-PR failure comment: the PR body has no final status to complete).
    """
    # the run made pi calls in one stage before it stopped; the later
    # stages never ran, so the ledger holds exactly the pre-stop calls
    ledger = ["3000 400"]
    r_in, r_out = 0.10, 0.20
    priced = (f"- **Total cost:** ${(3000 * r_in + 400 * r_out) / 1e6:.4f} "
              f"(model `Ornith-1.5-35B-A3B` @ ${r_in:.2f}/M input, "
              f"${r_out:.2f}/M output — rates from the repo file "
              f".pi/agent/models.json)")
    # a failed run that reached the PR: the comment (and the PR body's
    # final status) carry the pre-stop usage and cost
    pr_body, comment, _closed = _run_report_action(
        run_result="failure", ledger=ledger,
        models_config=_models_config(r_in, r_out))
    for surface in (pr_body, comment):
        for line in ("- **Total input tokens:** 3000",
                     "- **Total output tokens:** 400",
                     priced):
            assert line in surface, \
                ("a failed run is reported with the calls made before "
                 f"the stop: {surface!r}")
    # a run that died before the PR existed: the no-PR failure comment
    # still lists the pre-stop usage and cost
    pr_body, comment, _closed = _run_report_action(
        run_result="failure", pr_number="",
        ledger=ledger, models_config=_models_config(r_in, r_out))
    assert pr_body == "", "no PR was opened — there is no PR body to complete"
    for line in ("- **Total input tokens:** 3000",
                 "- **Total output tokens:** 400",
                 priced):
        assert line in comment, \
            f"the no-PR failure report still lists the pre-stop usage: {comment!r}"


def test_report_verifies_the_pr_body_completion():
    """(reporting "the PR description carries the same usage numbers as
    the issue comment"; reference
    `requirements/reporting.feature::The PR description carries the
    same usage numbers as the issue comment`) after editing the PR body
    the stage re-reads the
    PR: where the completion is verifiably in the body, the issue comment
    is the pointer form — 'final status is in the PR body' — and still
    lists the usage lines, the same strings the body carries (one ledger,
    one set of numbers on both surfaces), and the run's success closes the
    source issue."""
    pr_body, comment, closed = _run_report_action(
        ledger=["10000 2000", "5000 1500"],
        view_body="## Progress so far\n\n## Final status\n- stale\n")
    assert "final status is in the PR body" in comment, \
        f"a verified completion keeps the pointer comment: {comment!r}"
    for line in ("- **Total input tokens:** 15000",
                 "- **Total output tokens:** 3500"):
        assert line in comment, f"the comment lists the run's usage: {comment!r}"
        assert line in pr_body, \
            ("the PR description carries the same numbers the comment "
             f"posts: {pr_body!r}")
    assert closed, "a successful run closes the source issue"


def test_report_unverified_completion_makes_the_comment_self_contained():
    """(reporting "the PR description carries the same usage numbers as
    the issue comment"; reference
    `requirements/reporting.feature::The PR description carries the
    same usage numbers as the issue comment`) where the completion could
    not be applied to the
    PR — the re-read shows a body without it (the PR was already merged,
    or the edit was refused on both write paths) — the issue comment
    carries the full final status itself: the usage lines and the stage
    outcomes — and makes no claim that the PR body carries them."""
    pr_body, comment, closed = _run_report_action(
        ledger=["10000 2000", "5000 1500"])
    assert "final status is in the PR body" not in comment, \
        f"the comment must not claim what the PR body never got: {comment!r}"
    assert "could not be completed" in comment
    assert "- **Total input tokens:** 15000" in comment
    assert "- **Total output tokens:** 3500" in comment
    assert "### Stage outcomes" in comment
    assert "stage 4 extract: clean" in comment
    assert closed, "a successful run closes the source issue either way"


def test_failed_run_leaves_the_source_issue_open():
    """(reporting "a failed run leaves the source issue open";
    reference
    `requirements/reporting.feature::A failed run leaves the source
    issue open`) a failure
    reports the stage outcomes and the pre-stop usage on the issue — but
    never closes it: the issue stays open for a re-trigger."""
    pr_body, comment, closed = _run_report_action(
        run_result="failure", ledger=["3000 400"])
    assert "run failed" in comment
    assert "left open" in comment, \
        f"a failed run's comment states the issue stays open: {comment!r}"
    assert not closed, "a failed run must not close the source issue"


def test_validator_skips_when_parser_port_absent():
    """(test-and-review "the suite runs on an interpreter without
    pytest"; reference
    `requirements/test-and-review.feature::The suite runs on an
    interpreter without pytest`) where the official Gherkin-parser port
    is absent, the oracle check is
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


def test_stage_instructions_avoid_file_lists_without_meaning():
    """(configuration "A stage instruction avoids file lists that carry no
    meaning"; reference
    `requirements/configuration.feature::A stage instruction avoids file
    lists that carry no meaning`) a file list appears in a stage
    instruction only where the set is the instruction's scope, and no
    instruction lists project files as context to rummage through: the
    rummage phrasing is gone from every stage's instruction surface (the
    five prompt templates, the prompt files the stages assemble — the
    plan target, the implement target, the review prompt, the PR body
    prompt — and the guard's repair instructions), the scoped file lists
    appear exactly where the scenario names them (the plan's
    changed-requirements list, the guard's off-limits list in the repair
    instructions, the implement target's single plan file), and each is
    tied in the instructions to the scope it bounds."""
    import shutil
    # no instruction lists project files as context to rummage through —
    # the rummage phrasing is gone from every stage's instruction surface:
    # the five prompt templates, the prompt-file assembly in the stage
    # scripts, the PR body prompt assembly in the workflow, and the
    # guard's repair instructions. (The plumbing's bracketed context block
    # is the invocation's path-referenced slice — the standing @config
    # scenario governs what the invocation embeds; this rule governs what
    # the instructions say.)
    surfaces = (
        "pi-prompts/requirements.md",
        "pi-prompts/plan.md",
        "pi-prompts/implement.md",
        "pi-prompts/review.md",
        "pi-prompts/pr-body.md",
        ".github/actions/extract-stage/stage.py",
        ".github/actions/plan-stage/stage.py",
        ".github/actions/implement-stage/stage.py",
        ".github/actions/review-stage/stage.py",
        ".github/workflows/factory.yml",
        ".github/scripts/common.py",
    )
    for path in surfaces:
        text = _read(path).lower()
        for phrase in ("rummage", "browse", "the ones you need",
                       "open what you need", "as you like"):
            assert phrase not in text, (
                f"{path} lists project files as context to rummage "
                f"through ({phrase!r}) — a file list appears in an "
                f"instruction only where the set is the instruction's "
                f"scope")
    # a file-list segment in a prompt template (two or more consecutive
    # bullet lines naming files) must be tied to the scope it bounds —
    # today none of the five templates carries one (the oracle reaches the
    # extract call as its directory; the plan's delta list, the guard's
    # off-limits list and the implement target's plan file ride the
    # assembled prompt files)
    file_bullet = re.compile(
        r"^\s*[-*]\s+.*(?:`[^`]+\.(?:md|feature|py|txt|json|yml|toml)`"
        r"|\b[\w.-]+/[^\s`]*\.(?:md|feature|py|txt|json|yml|toml)\b)")
    scope_ties = ("the delta this plan must cover", "your task's input",
                  "verdict scope", "exactly this plan file",
                  "the off-limits files that changed",
                  "no other file may change", "generated from all of them")
    for template in ("requirements", "plan", "implement", "review",
                     "pr-body"):
        lines = _read(f"pi-prompts/{template}.md").splitlines()
        run = 0
        for i, line in enumerate(lines):
            if not file_bullet.match(line):
                run = 0
                continue
            run += 1
            if run >= 2:
                header = next((l.strip() for l in reversed(lines[:i])
                               if l.strip()), "")
                assert any(t in header for t in scope_ties), (
                    f"pi-prompts/{template}.md lists files as context to "
                    f"rummage through — the list's set is not the "
                    f"instruction's scope (introduced by {header!r})")
    # the scoped file lists appear exactly where the scenario names them,
    # each tied in the instructions to the scope it bounds —
    # (1) the plan's changed-requirements list: the delta section the plan
    # target carries — the list is introduced as the delta's input and the
    # changes ride as the delta the plan must cover
    plan_stage = _read(".github/actions/plan-stage/stage.py")
    assert "## The requirement delta (your task's input)" in plan_stage
    assert "The following requirement files changed since the run's " \
        in plan_stage
    assert "the delta this plan must cover" in plan_stage
    # (2) the guard's off-limits list in the repair instructions — the
    # assembled instructions name the off-limits files, the list is
    # introduced as the revert's scope, and the revert is bounded to the
    # named files (no other file may change)
    spec = importlib.util.spec_from_file_location(
        "cw_guard_repair_instructions",
        os.path.join(ROOT, ".github", "scripts", "common.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cw_guard_repair_instructions"] = mod  # the @dataclass resolves its module
    try:
        spec.loader.exec_module(mod)
        ins = mod._guard_repair_instructions(
            "baseline-sha", ["requirements/guard-rail.feature",
                              "plans/9.md"],
            "stage 8 implementation", "implement")
        assert "The off-limits files that changed against the stage's " \
            "baseline" in ins
        assert "  - requirements/guard-rail.feature" in ins
        assert "  - plans/9.md" in ins
        assert "Revert exactly the named files — no other file may change." \
            in ins
        assert "Keep the stage's own work valid against the task its " \
            "initial instructions gave it" in ins
    finally:
        sys.modules.pop("cw_guard_repair_instructions", None)
    # (3) the implement target's single plan file — the target names
    # exactly the one plan file the stage works, and only that one
    spec = importlib.util.spec_from_file_location(
        "cw_implement_target",
        os.path.join(ROOT, ".github", "actions", "implement-stage",
                     "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    saved = {k: os.environ.get(k) for k in ("RUNNER_TEMP",)}
    rt = tempfile.mkdtemp(prefix="cw-instr-scope-")
    os.environ["RUNNER_TEMP"] = rt
    try:
        target = open(mod.build_target("42", "plans"),
                      encoding="utf-8").read()
        assert "Open and update exactly this plan file (and only this " \
            "issue's plan)" in target
        assert "    plans/42.md" in target
        assert target.count(".md") == 1, \
            "the implement target names exactly one plan file"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(rt, ignore_errors=True)
    # the review prompt's file lists are scope lists — the changed feature
    # files' scenarios and the scenarios the changed tests reference join
    # the verdict scope (the set is the instruction's scope, as the
    # plan's delta list is) — and the PR body prompt's context list is the
    # body's scope: the body is generated from all of its context files,
    # each role naming the part of the body its source supplies
    review_stage = _read(".github/actions/review-stage/stage.py")
    assert "are in your verdict scope" in review_stage
    assert "the verdict scope with the changed feature files'" in review_stage
    factory = _read(".github/workflows/factory.yml")
    assert "The context files the pi call carries — the body is " \
        in factory
    assert "generated from all of them" in factory
    assert "each role naming the part of the body its source supplies:" \
        in factory


def test_loop_cap_defaults_match_oracle():
    """(configuration "the loop caps are configurable", "a loop cap of 0
    means no cap"; reference
    `requirements/configuration.feature::The loop caps are
    configurable`,
    `requirements/configuration.feature::A loop cap of 0 means no
    cap`) the oracle's Given pins the factory's max-loops default
    as 5 — the reusable workflow declares it, and the doc surface that
    repeats the value (the README's input table, the arc42 quality chapter)
    agrees with it; the token budget is gone from the configuration surface
    — no max-tokens row on the doc surfaces, no token-budget default
    wording — and the old 25 / 5,000,000 pair is gone from the tree. A
    target still lowers or raises the cap per repo — the inputs → job env →
    caps_ok machinery is unchanged (0 = no cap). The loop rename the
    delta's adjusted configuration/cost/safety scenarios carry lands on
    these surfaces: the quality chapter's "Loop caps" bullet and the README
    state the loop name as "guard repair", and "guard re-run" appears on
    neither."""
    factory = _read(".github/workflows/factory.yml")
    assert _workflow_input_default(factory, "max-loops") == "5", \
        "the oracle pins the MAX_LOOPS default as 5"
    readme = _read("README.md")
    quality = _read("docs/09-quality-requirements.md")
    assert "| `max-loops` | `5` |" in readme
    assert "default 5" in quality
    # the token budget is gone from the doc surfaces that used to repeat
    # it: no max-tokens row, no token-budget default wording
    assert "| `max-tokens` |" not in readme
    assert "default 500,000" not in quality
    # the old declared pair is gone from every surface that repeats it
    assert "| `max-loops` | `25` |" not in readme
    assert "| `max-tokens` | `5000000` |" not in readme
    assert "default 25" not in quality
    for surface in (factory, readme, quality):
        assert "5000000" not in surface
        assert "5,000,000" not in surface
    # the loop-cap surfaces state the loop name as "guard repair" (the
    # delta's rename), and the old "guard re-run" name appears on none of
    # them
    assert "guard repair" in quality
    assert "guard re-run" not in quality
    assert "guard repair" in readme
    assert "guard re-run" not in readme


def test_implement_guard_protects_requirements_and_other_plans():
    """(implement "implementation may only edit the current issue's
    plan"; reference
    `requirements/implement.feature::Implementation may only edit the
    current issue's plan`)
    the implement guard runs inverted-allow — the stage's DENY set is the
    protected set (requirements + plans dir, the guard's `!` entries) and
    its ALLOW set re-admits exactly the current issue's plan file plus
    `__pycache__`: another issue's plan file and a requirements file are
    violations the guard repairs with a pi call (no stage re-run; a
    requirements-dir edit does not loop back to the plan stage), while
    everything else is the implementation's lane — judged with the guard's
    own predicate (common.guard_denied)."""
    spec = importlib.util.spec_from_file_location(
        "cw_implement_stage",
        os.path.join(ROOT, ".github", "actions", "implement-stage", "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    spec_c = importlib.util.spec_from_file_location(
        "cw_common", os.path.join(ROOT, ".github", "scripts", "common.py"))
    common = importlib.util.module_from_spec(spec_c)
    sys.modules["cw_common"] = common  # the @dataclass GuardResult resolves its module
    spec_c.loader.exec_module(common)
    saved = {k: os.environ.get(k) for k in ("PLAN_DIR", "REQUIREMENTS_DIR")}
    os.environ["PLAN_DIR"] = "plans"
    os.environ["REQUIREMENTS_DIR"] = "requirements"
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        deny = mod.protected_dirs()
        assert "plans" in deny, "the plans dir is denied"
        assert "requirements" in deny, "the requirements dir is denied"
        # main()'s allow construction, replayed: the re-admissions over the
        # deny set are the current issue's plan file + pycache at any depth
        current = mod.current_plan_path("20", "plans")
        assert current == "plans/20.md"
        assert os.path.isfile(current), "this repo carries its own issue-20 plan"
        allow = ["__pycache__"]
        if current:
            allow.append(current)
        assert common.guard_denied(current, allow, deny) is False, \
            "the current issue's plan file must be admitted over the deny"
        assert common.guard_denied("plans/7.md", allow, deny), \
            "another issue's plan file must be off-limits"
        assert common.guard_denied("requirements/trigger.feature", allow, deny), \
            "the requirements dir stays off-limits"
        # the implementation's lane: everything else is admitted — the code
        # dirs, the tests the implementation has the job to implement
        # (including a `tests/` dir that did not exist at stage start), the
        # arc42 set, the README, and pycache the suite runs generate at any
        # depth (run 40735387017's iterations reverted these)
        for f in ("src/app.py", "tests/run.py", "tests/test_sync.py",
                  "tests/__pycache__/test_sync.cpython-313.pyc",
                  "docs/07-runtime-view.md", "README.md", "Makefile",
                  ".github/workflows/sync.yml"):
            assert not common.guard_denied(f, allow, deny), \
                f"{f} is the implementation's lane and must be admitted"
    finally:
        os.chdir(cwd)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# The fake `pi` both guard sandboxes put on PATH: it records each
# call's instructions to the state dir, performs the revert the
# instructions name when its mode says so ("revert" — every call;
# "revert-second" — the second call only; "noop" — never), and
# closes with a usage-carrying JSONL event stream (a message_end
# with input/output usage, then agent_settled) the way a real
# `pi --mode json` call's stdout reads.
_FAKE_PI = (
        "#!" + sys.executable + "\n"
        "import json, os, subprocess, sys\n"
        "ins = sys.argv[-1]\n"
        "sd = os.path.join(os.environ['RUNNER_TEMP'], 'cw')\n"
        "os.makedirs(sd, exist_ok=True)\n"
        "with open(os.path.join(sd, 'fake-pi-call.txt'), 'a') as f:\n"
        "    f.write(ins + chr(10))\n"
        "cf = os.path.join(sd, 'fake-pi-count.txt')\n"
        "n = (int(open(cf).read().strip() or 0)\n"
        "      if os.path.exists(cf) else 0) + 1\n"
        "with open(cf, 'w') as f:\n"
        "    f.write(str(n))\n"
        "mode = os.environ.get('FAKE_PI_MODE', 'noop')\n"
        "if mode == 'revert' or (mode == 'revert-second' and n >= 2):\n"
        "    import re\n"
        "    ws = os.environ['GITHUB_WORKSPACE']\n"
        "    m = re.search(r'baseline `([^`]+)`', ins)\n"
        "    baseline = m.group(1) if m else 'HEAD'\n"
        "    for fm in re.finditer(r'  - (\\S+)', ins):\n"
        "        p = fm.group(1)\n"
        "        full = os.path.join(ws, p)\n"
        "        known = subprocess.run(\n"
        "            ['git', 'cat-file', '-e', baseline + ':' + p],\n"
        "            cwd=ws, capture_output=True).returncode == 0\n"
        "        if known:\n"
        "            subprocess.run(['git', 'checkout', baseline, '--', p],\n"
        "                           cwd=ws, check=True)\n"
        "        elif os.path.isdir(full):\n"
        "            subprocess.run(['git', 'clean', '-fdq', '--', p],\n"
        "                           cwd=ws)\n"
        "        elif os.path.exists(full):\n"
        "            tracked = subprocess.run(\n"
        "                ['git', 'ls-files', '--', p],\n"
        "                cwd=ws, capture_output=True).stdout.strip()\n"
        "            if tracked:\n"
        "                subprocess.run(['git', 'rm', '-f', '--', p],\n"
        "                                cwd=ws, check=True)\n"
        "            else:\n"
        "                os.remove(full)\n"
        "print(json.dumps({'type': 'message_end', 'message': {\n"
        "    'role': 'assistant',\n"
        "    'content': 'the named files are reverted',\n"
        "    'usage': {'input': 11, 'output': 7}}}))\n"
        "print(json.dumps({'type': 'agent_settled'}))\n"
)


def _guard_repair_sandbox(allow, deny, mode, max_loops,
                          stage="stage 6 planning", template="plan",
                          leak=True):
    """A sandbox that exercises the shared guard's repair loop end to end:
    a temp git repo with a committed baseline (a requirements feature file,
    the issue's plan file, a src file), the scenario's leak (an off-limits
    edit in the requirements dir) applied to the working tree on top of the
    stage's own allowed work, and a fake `pi` on
    PATH that records each call's instructions to the state dir and
    performs the revert they name when its mode says so ("revert" — every
    call; "revert-second" — the second call only; "noop" — never). The
    canonical guard (common.guard, imported in-process) then runs its real
    detection + repair loop against a real baseline and a real working tree
    with no model in the middle. Returns a namespace: repo (the repo
    dir), rt (the state-dir root), baseline (the baseline sha), mod (the
    common module), result (the guard's GuardResult — None when the guard
    exited the stage instead), exit_code (the SystemExit the guard
    raised), calls (the recorded repair-call instructions), fail_reason
    (the failure report the guard wrote to the state dir, if any) and
    cleanup (restore the env and remove the temp dirs)."""
    import shutil
    import subprocess
    import tempfile
    repo = tempfile.mkdtemp(prefix="cw-guard-repo-")
    rt = tempfile.mkdtemp(prefix="cw-guard-rt-")
    fake = tempfile.mkdtemp(prefix="cw-guard-fake-")
    os.makedirs(os.path.join(repo, "requirements"))
    os.makedirs(os.path.join(repo, "plans"))
    os.makedirs(os.path.join(repo, "src"))
    with open(os.path.join(repo, "requirements", "guard-rail.feature"), "w") as f:
        f.write("Feature: baseline\n  Scenario: the baseline scenario\n"
                "    Given the baseline tree\n")
    with open(os.path.join(repo, "plans", "69.md"), "w") as f:
        f.write("# Issue 69\n- [ ] a task\n")
    with open(os.path.join(repo, "src", "app.py"), "w") as f:
        f.write("print('baseline')\n")

    def g(*a):
        return subprocess.run(["git", *a], cwd=repo, capture_output=True,
                              text=True)
    g("init", "-q")
    g("config", "user.email", "guard@sandbox")
    g("config", "user.name", "guard sandbox")
    g("add", "-A")
    g("commit", "-q", "-m", "baseline")
    baseline = g("rev-parse", "HEAD").stdout.strip()
    assert baseline, "the sandbox baseline commit failed"

    # the stage's own work (an allowed change to the plan file) plus — when
    # the scenario asks for the leak — an off-limits edit in the
    # requirements dir
    with open(os.path.join(repo, "plans", "69.md"), "a") as f:
        f.write("- [x] a task\n")
    if leak:
        with open(os.path.join(repo, "requirements", "guard-rail.feature"),
                  "a") as f:
            f.write("  Scenario: a leak\n"
                    "    Given the stage edited the oracle\n")

    os.makedirs(os.path.join(fake, "bin"))
    with open(os.path.join(fake, "bin", "pi"), "w") as f:
        f.write(_FAKE_PI)
    os.chmod(os.path.join(fake, "bin", "pi"), 0o755)

    keys = ("GITHUB_WORKSPACE", "RUNNER_TEMP", "LLM_MODEL", "MAX_LOOPS",
            "PATH", "FAKE_PI_MODE")
    saved = {k: os.environ.get(k) for k in keys}
    saved_gitcfg = {k: v for k, v in os.environ.items()
                    if k.startswith("GIT_CONFIG_")}
    for k in saved_gitcfg:
        os.environ.pop(k)
    os.environ.update({
        "GITHUB_WORKSPACE": repo,
        "RUNNER_TEMP": rt,
        "LLM_MODEL": "fake-model",
        "MAX_LOOPS": str(max_loops),
        "PATH": os.path.join(fake, "bin") + os.pathsep + (saved["PATH"] or ""),
        "FAKE_PI_MODE": mode,
    })

    spec = importlib.util.spec_from_file_location(
        "cw_common_guard_sandbox",
        os.path.join(ROOT, ".github", "scripts", "common.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cw_common_guard_sandbox"] = mod
    spec.loader.exec_module(mod)

    ns = {"repo": repo, "rt": rt, "fake": fake, "baseline": baseline,
          "mod": mod, "result": None, "exit_code": None, "calls": "",
          "fail_reason": None}
    try:
        ns["result"] = mod.guard(baseline, allow, deny,
                                 stage=stage, template=template)
    except SystemExit as e:
        ns["exit_code"] = e.code
    try:
        ns["calls"] = open(os.path.join(rt, "cw", "fake-pi-call.txt")).read()
    except OSError:
        pass
    try:
        ns["fail_reason"] = open(
            os.path.join(rt, "cw", "stage-fail-reason.txt"),
            encoding="utf-8").read()
    except OSError:
        pass

    def cleanup():
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for k in saved_gitcfg:
            os.environ[k] = saved_gitcfg[k]
        for d in (repo, rt, fake):
            shutil.rmtree(d, ignore_errors=True)
    ns["cleanup"] = cleanup
    return ns


def test_guard_repairs_a_violation_with_a_pi_call():
    """(guard-rail "a leaking stage is repaired by a pi call, not
    restarted", "guard repairs are capped"; reference
    `requirements/guard-rail.feature::A leaking stage is repaired by a
    pi call, not restarted`,
    `requirements/guard-rail.feature::Guard repairs are capped`,
    `requirements/cost-and-token-usage.feature::The usage totals cover
    every pi call the run made`,
    `requirements/plan.feature::The plan stage may only touch its own
    plan file`) an off-limits change in the
    working tree makes the shared guard call pi — its instructions name
    the off-limits files, instruct pi to revert the changes to the named
    files, and instruct pi to keep the stage's own work valid against the
    task its initial instructions gave it; a clean re-check after the
    repair returns a passing result — the guard records the cleared
    repair in the state dir: the extract and implement stages complete
    without re-running their generation, the plan stage re-runs on it
    (plan "the plan stage may only touch its own plan file"); the allowed
    changes stay intact, the off-limits file is reverted in place; the
    repair calls ride the
    documented shared pi-call plumbing — each finished call appends its
    usage to the run's ledger (cost-and-token-usage "the usage totals
    cover every pi call the run made"); the repair loop is bounded by
    MAX_LOOPS (0 = no cap — a cap of 2 stops the loop after two repair
    calls, a 0 cap lets the same calls run to the clearing one), and a
    cap exhausted without clearing the violation fails the stage with a
    failure report listing the violations."""
    # a violation the repair clears on its first call
    ns = _guard_repair_sandbox(["plans"], [], "revert", "3")
    try:
        assert ns["exit_code"] is None, \
            ("a cleared repair completes the stage — the guard did not "
             f"exit the stage: {ns['exit_code']!r}")
        assert ns["result"].ok, \
            "a clean re-check after the repair lets the stage pass"
        # the guard called pi to repair the violation — one call cleared
        # it; the stage was not reverted and re-run
        n_calls = ns["calls"].count("You are repairing a guard violation")
        assert n_calls == 1, \
            f"one repair call cleared the violation — no re-run: {n_calls}"
        # the call names the off-limits file that changed
        assert "requirements/guard-rail.feature" in ns["calls"], \
            "the repair call's instructions name the off-limits file"
        # ... instruct pi to revert the changes to the named files
        assert "Revert the changes to the named files" in ns["calls"]
        assert ns["baseline"] in ns["calls"], \
            "the revert is to the stage's baseline"
        # ... and to keep the stage's own work valid against the task its
        # initial instructions gave it
        assert "Keep the stage's own work valid against the task its " \
            "initial instructions gave it" in ns["calls"]
        assert "pi-prompts/plan.md" in ns["calls"], \
            "the stage's initial instructions are its prompt template"
        # the off-limits file is reverted in place; the stage's own work
        # (an allowed change) stays intact
        feat = open(os.path.join(ns["repo"], "requirements",
                                 "guard-rail.feature")).read()
        assert "a leak" not in feat, \
            "the off-limits change is reverted in place"
        plan = open(os.path.join(ns["repo"], "plans", "69.md")).read()
        assert "- [x] a task" in plan, \
            "the allowed changes stay intact"
        # the finished repair call appends its usage to the run's ledger
        # (the new call kind rides the documented pi-call machinery)
        ledger = open(os.path.join(ns["rt"], "cw", "tokens.txt"),
                      encoding="utf-8").read()
        assert "11 7" in ledger, \
            f"each finished call appends its usage to the ledger: {ledger!r}"
    finally:
        ns["cleanup"]()
    # a cap exhausted without clearing the violation fails the stage with a
    # failure report listing the violations
    ns2 = _guard_repair_sandbox(["plans"], [], "noop", "2")
    try:
        assert ns2["exit_code"] == 1, \
            "a cap exhausted without clearing the violation fails the stage"
        n_calls = ns2["calls"].count("You are repairing a guard violation")
        assert n_calls == 2, \
            f"the guard's repair call runs MAX_LOOPS (2) times: {n_calls}"
        assert ns2["fail_reason"] is not None, \
            "the stage fails with a failure report"
        assert "requirements/guard-rail.feature" in ns2["fail_reason"], \
            "the failure report lists the violations (the named off-limits files)"
    finally:
        ns2["cleanup"]()
    # MAX_LOOPS 0 = no cap: the loop runs past a small count to the call
    # that clears the violation
    ns3 = _guard_repair_sandbox(["plans"], [], "revert-second", "0")
    try:
        assert ns3["exit_code"] is None and ns3["result"].ok, \
            "a cap of 0 is no cap — the repair loop runs to the clearing call"
        n_calls = ns3["calls"].count("You are repairing a guard violation")
        assert n_calls == 2, \
            f"the clearing call was the second one: {n_calls}"
        feat = open(os.path.join(ns3["repo"], "requirements",
                                 "guard-rail.feature")).read()
        assert "a leak" not in feat, \
            "the second repair call cleared the violation"
    finally:
        ns3["cleanup"]()


def _guard_fallback_sandbox(allow, deny, mode, max_loops,
                            stage="stage 6 planning", template="plan"):
    """The fallback-form twin of _guard_repair_sandbox: the same temp git
    repo (a committed baseline, the stage's own allowed work, the
    off-limits leak) and the same fake `pi` on PATH, but the guard runs as
    the SELF-CONTAINED fallback — a copy of guard-check.py laid out where
    the sibling scripts/ dir is absent (the degenerate sparse checkout the
    fallback exists for), run as a subprocess the way run_guard runs the
    canonical external script. Returns a namespace: repo (the repo dir),
    rt (the state-dir root), baseline, returncode (the guard CLI's exit),
    out (its captured stdout — the narrative run_guard relays), err, and
    cleanup (restore the env and remove the temp dirs)."""
    import shutil
    import subprocess
    import tempfile
    repo = tempfile.mkdtemp(prefix="cw-guardfb-repo-")
    rt = tempfile.mkdtemp(prefix="cw-guardfb-rt-")
    fake = tempfile.mkdtemp(prefix="cw-guardfb-fake-")
    tree = tempfile.mkdtemp(prefix="cw-guardfb-tree-")
    os.makedirs(os.path.join(repo, "requirements"))
    os.makedirs(os.path.join(repo, "plans"))
    os.makedirs(os.path.join(repo, "src"))
    with open(os.path.join(repo, "requirements", "guard-rail.feature"),
              "w") as f:
        f.write("Feature: baseline\n  Scenario: the baseline scenario\n"
                "    Given the baseline tree\n")
    with open(os.path.join(repo, "plans", "69.md"), "w") as f:
        f.write("# Issue 69\n- [ ] a task\n")
    with open(os.path.join(repo, "src", "app.py"), "w") as f:
        f.write("print('baseline')\n")

    def g(*a):
        return subprocess.run(["git", *a], cwd=repo, capture_output=True,
                              text=True)
    g("init", "-q")
    g("config", "user.email", "guard@sandbox")
    g("config", "user.name", "guard sandbox")
    g("add", "-A")
    g("commit", "-q", "-m", "baseline")
    baseline = g("rev-parse", "HEAD").stdout.strip()
    assert baseline, "the sandbox baseline commit failed"

    # the stage's own work (an allowed change to the plan file) plus the
    # scenario's leak (an off-limits edit in the requirements dir)
    with open(os.path.join(repo, "plans", "69.md"), "a") as f:
        f.write("- [x] a task\n")
    with open(os.path.join(repo, "requirements", "guard-rail.feature"),
              "a") as f:
        f.write("  Scenario: a leak\n"
                "    Given the stage edited the oracle\n")

    os.makedirs(os.path.join(fake, "bin"))
    with open(os.path.join(fake, "bin", "pi"), "w") as f:
        f.write(_FAKE_PI)
    os.chmod(os.path.join(fake, "bin", "pi"), 0o755)

    # the fallback is the self-contained guard: a copy of the entry script
    # laid out where the sibling scripts/ dir is absent (its _load() finds
    # no canonical common.py and defines the inline fallback)
    os.makedirs(os.path.join(tree, "guard-check"))
    shutil.copy(os.path.join(ROOT, ".github", "actions", "guard-check",
                             "guard-check.py"),
                os.path.join(tree, "guard-check", "guard-check.py"))

    keys = ("GITHUB_WORKSPACE", "RUNNER_TEMP", "LLM_MODEL", "MAX_LOOPS",
            "PATH", "FAKE_PI_MODE")
    saved = {k: os.environ.get(k) for k in keys}
    saved_gitcfg = {k: v for k, v in os.environ.items()
                    if k.startswith("GIT_CONFIG_")}
    for k in saved_gitcfg:
        os.environ.pop(k)
    os.environ.update({
        "GITHUB_WORKSPACE": repo,
        "RUNNER_TEMP": rt,
        "LLM_MODEL": "fake-model",
        "MAX_LOOPS": str(max_loops),
        "PATH": os.path.join(fake, "bin") + os.pathsep + (saved["PATH"] or ""),
        "FAKE_PI_MODE": mode,
    })

    args = [sys.executable, os.path.join(tree, "guard-check",
                                         "guard-check.py"), baseline,
            *allow]
    if deny:
        args += ["!", *deny]
    r = subprocess.run(args, cwd=repo, capture_output=True, text=True)

    ns = {"repo": repo, "rt": rt, "fake": fake, "tree": tree,
          "baseline": baseline, "returncode": r.returncode,
          "out": r.stdout, "err": r.stderr}

    def cleanup():
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for k in saved_gitcfg:
            os.environ[k] = saved_gitcfg[k]
        for d in (repo, rt, fake, tree):
            shutil.rmtree(d, ignore_errors=True)
    ns["cleanup"] = cleanup
    return ns


def test_guard_fallback_matches_the_canonical_repair():
    """(guard-rail "All three checks share one implementation" — one
    script, three call sites, the self-contained fallback included;
    "A leaking stage is repaired by a pi call, not restarted";
    reference
    `requirements/guard-rail.feature::All three checks share one
    implementation`,
    `requirements/guard-rail.feature::A leaking stage is repaired by a
    pi call, not restarted`,
    `requirements/cost-and-token-usage.feature::The usage totals cover
    every pi call the run made`) the fallback the guard entry script
    falls back to when the sibling scripts/ dir is absent (the
    degenerate sparse checkout the fallback exists for) keeps the
    canonical guard's semantics end to end: the same detection, the
    same bounded repair loop through a pi call, a cleared re-check
    passing the stage without re-running its generation — and the
    cleared repair's bookkeeping stays whole: the reverts are committed
    so they ride the branch, the state-dir record names the files the
    call reverted, and each finished repair call appends its usage to
    the run's token ledger (cost-and-token-usage "The usage totals
    cover every pi call the run made")."""
    import subprocess
    ns = _guard_fallback_sandbox(["plans"], [], "revert", "3")
    try:
        assert ns["returncode"] == 0, \
            (f"a cleared repair passes the guard (exit 0): exit "
             f"{ns['returncode']}, stderr: {ns['err']!r}")
        # the off-limits file is reverted in place; the stage's own work
        # (an allowed change) stays intact
        feat = open(os.path.join(ns["repo"], "requirements",
                                 "guard-rail.feature")).read()
        assert "a leak" not in feat, \
            "the off-limits change is reverted in place"
        plan = open(os.path.join(ns["repo"], "plans", "69.md")).read()
        assert "- [x] a task" in plan, \
            "the allowed changes stay intact"

        def show(ref, path):
            r = subprocess.run(["git", "show", f"{ref}:{path}"],
                               cwd=ns["repo"], capture_output=True,
                               text=True)
            return r.stdout if r.returncode == 0 else None

        # the reverts are committed to the branch — the off-limits file
        # rides at its baseline content (a later stage's guard would
        # otherwise re-flag it against the stage baseline), and the
        # stage's own allowed work rides with them
        assert show("HEAD", "requirements/guard-rail.feature") == \
            show(ns["baseline"], "requirements/guard-rail.feature"), \
            "the cleared repair's reverts are committed to the branch"
        assert "- [x] a task" in (show("HEAD", "plans/69.md") or ""), \
            "the stage's own work is committed alongside the reverts"
        # the cleared-repair record names the files the call reverted
        record = open(os.path.join(ns["rt"], "cw",
                                   "stage-guard-repaired.txt"),
                      encoding="utf-8").read()
        assert "requirements/guard-rail.feature" in record, \
            f"the record names the cleared files: {record!r}"
        # the finished repair call appends its usage to the run's ledger
        ledger = open(os.path.join(ns["rt"], "cw", "tokens.txt"),
                      encoding="utf-8").read()
        assert "11 7" in ledger, \
            f"each finished call appends its usage to the ledger: {ledger!r}"
    finally:
        ns["cleanup"]()


def test_plan_stage_may_only_touch_its_own_plan_file():
    """(plan "the plan stage may only touch its own plan file"; reference
    `requirements/plan.feature::The plan stage may only touch its own
    plan file`,
    `requirements/guard-rail.feature::All three checks share one
    implementation`,
    `requirements/guard-rail.feature::A leaking stage is repaired by a
    pi call, not restarted`,
    `requirements/guard-rail.feature::A requirement edited during
    implementation is reverted in place`) when the plan stage wrote a
    change outside its one allowed plan file, the plan-check (the shared
    guard — one implementation, three call sites) reverts it with the
    shared remedy — the guard's pi call, the off-limits file named, told
    to be reverted, the plan told to stay valid — and the plan stage
    re-runs: the guard records the cleared repair in the state dir
    (stage-guard-repaired.txt), the plan stage's loop machinery claims
    the record and re-runs the generation, the guard re-checking the
    re-run — only the plan file is left changed. A clean plan stage
    writes no record and completes without re-running, and the extract
    and implement checks' machinery never claims the record — their
    stages complete without re-running, while all three checks share the
    one guard implementation."""
    # a leak at the plan check: the shared guard repairs it with a pi
    # call and records the cleared repair in the state dir — the record
    # the plan stage's loop machinery claims to re-run the generation
    ns = _guard_repair_sandbox(["plans/69.md"], [], "revert", "3")
    try:
        assert ns["exit_code"] is None and ns["result"].ok, \
            "a cleared repair lets the plan check pass"
        assert "You are repairing a guard violation" in ns["calls"], \
            "the guard repairs the violation with a pi call (the shared remedy)"
        assert "requirements/guard-rail.feature" in ns["calls"], \
            "the repair call names the off-limits file"
        feat = open(os.path.join(ns["repo"], "requirements",
                                 "guard-rail.feature")).read()
        assert "a leak" not in feat, \
            "any other change is reverted"
        plan = open(os.path.join(ns["repo"], "plans", "69.md")).read()
        assert "- [x] a task" in plan, \
            "the plan file (the stage's own work) stays intact"
        marker = os.path.join(ns["rt"], "cw", "stage-guard-repaired.txt")
        assert os.path.exists(marker), \
            "the guard records the cleared repair in the state dir"
        assert "requirements/guard-rail.feature" in open(marker).read(), \
            "the record names the reverted off-limits file"
    finally:
        ns["cleanup"]()
    # the plan stage's machinery claims the record and re-runs the
    # generation; the extract and implement stages' machinery never
    # claims it (their stages complete without re-running)
    plan_stage = _read(".github/actions/plan-stage/stage.py")
    assert "rerun_on_repair=True" in plan_stage, \
        "the plan stage re-runs its generation on the guard's cleared repair"
    assert "rerun_on_repair" not in _read(
        ".github/actions/extract-stage/stage.py"), \
        "the extract check keeps the repair-without-re-run form"
    assert "rerun_on_repair" not in _read(
        ".github/actions/implement-stage/stage.py"), \
        "the implement check keeps the repair-without-re-run form"
    stages = _read(".github/scripts/stages.py")
    assert "rerun_on_repair" in stages, \
        "the loop machinery carries the claim of the guard's cleared-repair record"
    assert "stage-guard-repaired" in stages, \
        "the loop machinery claims the record and re-runs the generation"
    assert "stage-guard-repaired" in _read(".github/scripts/common.py"), \
        "the shared guard writes the record the plan stage's machinery claims"
    # a clean plan stage: no violation, no repair call, no record — the
    # stage completes without re-running
    ns2 = _guard_repair_sandbox(["plans/69.md"], [], "revert", "3",
                                leak=False)
    try:
        assert ns2["exit_code"] is None and ns2["result"].ok, \
            "a clean plan stage passes the guard"
        assert ns2["calls"] == "", \
            "a clean stage makes no repair call"
        assert not os.path.exists(
            os.path.join(ns2["rt"], "cw", "stage-guard-repaired.txt")), \
            "a clean stage writes no repair record — no re-run"
    finally:
        ns2["cleanup"]()


def test_implement_stage_has_no_plan_loop_back():
    """(guard-rail "a requirement edited during implementation is reverted
    in place", implement "implementation must not edit requirements";
    reference
    `requirements/guard-rail.feature::A requirement edited during
    implementation is reverted in place`,
    `requirements/implement.feature::Implementation must not edit
    requirements`) a requirements-dir violation at the implement check is
    repaired in place
    by the shared guard's pi call — the implement stage's violation hook no
    longer regenerates the plan and no loop back to the plan stage exists
    (the hook is gone from the stage and from the shared loop machinery's
    signature; the stage docstring and the implement prompt's hard rule are
    reworded to the repair-in-place form). The inverted-allow detection
    shape is unchanged — a requirements-dir edit is still a violation; only
    the remedy is the repair call, and the plan file is left byte-identical
    (nothing regenerates it)."""
    stage = _read(".github/actions/implement-stage/stage.py")
    assert "plan_loop_back" not in stage, \
        "the implement stage's loop-back hook is removed — a requirements-dir violation is repaired in place"
    assert "on_violation" not in stage, \
        "the stage no longer hands a violation to a loop-back hook"
    assert "loops back to the plan stage" not in stage, \
        "the module docstring's loop-back sentences are reworded to the repair-in-place form"
    stages = _read(".github/scripts/stages.py")
    assert "on_violation" not in stages, \
        "the shared loop machinery carries no loop-back hook any more"
    prompt = _read("pi-prompts/implement.md")
    assert "loops back to planning" not in prompt, \
        "the implement prompt's hard rule is reworded to the repair-in-place form"
    assert "reverted in place" in prompt and \
        "guard's pi repair call" in prompt, \
        "the hard rule names the guard's pi repair call as the remedy"
    # behaviour: the implement guard's inverted-allow shape (deny =
    # {requirements, plans}; the current issue's plan file re-allowed) with
    # a requirements-dir violation — repaired in place by the same shared
    # guard, no plan regeneration
    ns = _guard_repair_sandbox(
        ["plans/69.md", "__pycache__"], ["requirements", "plans"],
        "revert", "3",
        stage="stage 8 implementation", template="implement")
    try:
        assert ns["exit_code"] is None and ns["result"].ok, \
            "a requirements-dir violation at the implement check is repaired in place"
        plan = open(os.path.join(ns["repo"], "plans", "69.md")).read()
        assert plan == "# Issue 69\n- [ ] a task\n- [x] a task\n", \
            "the plan file is not regenerated — no loop back to the plan stage"
        feat = open(os.path.join(ns["repo"], "requirements",
                                 "guard-rail.feature")).read()
        assert "a leak" not in feat, \
            "the guard calls pi with the changed file named to revert the edit"
        assert "requirements/guard-rail.feature" in ns["calls"], \
            "the repair call's instructions name the changed file"
        assert "pi-prompts/implement.md" in ns["calls"], \
            "the call keeps the stage's own work valid against the task its initial instructions gave it"
    finally:
        ns["cleanup"]()


def test_implement_instructions_prescribe_the_test_reference():
    """(implement "Tests are generated for the new behaviour" — the new
    And step; test-and-review "Tests reference the Gherkin requirement
    they arose from", "A changed requirement pulls in the tests that
    reference it"; reference
    `requirements/implement.feature::Tests are generated for the new
    behaviour`,
    `requirements/test-and-review.feature::Tests reference the Gherkin
    requirement they arose from`,
    `requirements/test-and-review.feature::A changed requirement pulls in
    the tests that reference it`) the implement prompt template
    prescribes the reference convention the suite and the oracle join on:
    a test that implements a Gherkin scenario carries a reference to the
    scenario it arose from — the machine form is the test's docstring
    citing the scenario, and a test that is only for correctness carries
    no such reference; a scenario changed in place pulls in the tests
    that reference it — the adjusted tests fulfil the requirement as it
    now reads."""
    prompt = _read("pi-prompts/implement.md")
    # a test that implements a Gherkin scenario carries a reference to
    # the scenario it arose from — the machine form is the docstring
    # citation `<feature file>::<scenario name>`, in the example shape
    assert "Gherkin scenario carries a reference to the scenario it" in prompt
    assert "citing the scenario as" in prompt
    assert "`<feature file>::<scenario name>`" in prompt
    assert ("requirements/guard-rail.feature::Guard repairs are capped"
            in prompt)
    # a test that is only for correctness carries no such reference
    assert "is only for correctness carries no such reference" in prompt
    # a scenario changed in place pulls in the tests that reference it —
    # the adjusted tests fulfil the requirement as it now reads
    assert ("changed a Gherkin scenario in place, adjust every test that"
            in prompt)
    assert "references that changed scenario with it" in prompt
    assert "the adjusted tests fulfil" in prompt
    assert "the requirement as it now reads" in prompt


def test_tests_that_implement_scenarios_reference_them():
    """(test-and-review "Tests reference the Gherkin requirement they
    arose from", "A changed requirement pulls in the tests that reference
    it"; reference
    `requirements/test-and-review.feature::Tests reference the Gherkin
    requirement they arose from`,
    `requirements/test-and-review.feature::A changed requirement pulls in
    the tests that reference it`) the suite-level form of the reference
    convention: over the test suite under tests/, every test that
    implements a Gherkin scenario carries a reference to the scenario it
    arose from — the cited feature file exists under requirements/ and
    the cited scenario name is a scenario of that file — and a test with
    no such reference is one that is only for correctness. The suite's
    standing prose form (the scenario name quoted in the test's
    docstring) is the mention side of the join: a scenario the docstring
    quotes must be cited in the machine form, so the review stage can
    extract the reference from the run's changed tests, and a run that
    changed a scenario in place can find the tests to adjust with it."""
    import ast
    reqdir = os.path.join(ROOT, "requirements")
    scenarios = {}
    for fname in sorted(os.listdir(reqdir)):
        if not fname.endswith(".feature"):
            continue
        with open(os.path.join(reqdir, fname), encoding="utf-8") as f:
            scenarios[fname] = [
                m.group(1).strip() for line in f
                for m in [re.match(
                    r"^\s*Scenario(?:\s+Outline)?\s*:\s*(.+?)\s*$", line)]
                if m]
    owners = {}
    for fname, names in scenarios.items():
        for name in names:
            owners.setdefault(name.lower(), []).append(fname)
    checked = cited = 0
    testsdir = os.path.join(ROOT, "tests")
    for fname in sorted(os.listdir(testsdir)):
        if not (fname.startswith("test_") and fname.endswith(".py")):
            continue
        with open(os.path.join(testsdir, fname), encoding="utf-8") as f:
            src = f.read()
        for node in ast.parse(src).body:
            if not (isinstance(node, ast.FunctionDef)
                    and node.name.startswith("test_")):
                continue
            doc = " ".join((ast.get_docstring(node) or "").split())
            cites = [(f, n.strip()) for f, n in re.findall(
                r"`requirements/([\w.-]+\.feature)::([^`]+)`", doc)]
            # every cited feature file exists under requirements/ and the
            # cited scenario name is a scenario of that file
            for f, n in cites:
                assert f in scenarios, (
                    f"{fname}::{node.name} cites {f!r} — no oracle file "
                    f"under requirements/")
                assert n in scenarios[f], (
                    f"{fname}::{node.name} cites {n!r}, which is not a "
                    f"scenario of requirements/{f}")
                cited += 1
            # every scenario the docstring quotes in the suite's standing
            # prose form is cited in the machine form
            for q in re.findall(r'"([^"]+)"', doc):
                q = " ".join(q.split())
                if q.lower() in owners:
                    assert any(c in owners[q.lower()]
                               and n.lower() == q.lower()
                               for c, n in cites), (
                        f"{fname}::{node.name} quotes scenario {q!r} (a "
                        f"scenario of {sorted('requirements/' + f for f in owners[q.lower()])}) "
                        f"but carries no <feature file>::<scenario name> "
                        f"reference to it")
            checked += 1
    assert checked, "no test functions discovered under tests/"
    assert cited, "no test in the suite carries a scenario reference"


def _run_gates_stage(pages, head_sha="a" * 40, empty_polls=None):
    """Exec the gates stage's python in a sandbox: a temp RUNNER_TEMP state
    dir, a fake `gh` on PATH serving the canned `actions/runs` pages in
    call order (recording every query URL), and a no-op `time.sleep` so
    the poll loop runs at test speed — no network, no pi. Returns (exit
    code, the stage-summary file's text, the recorded query URLs).

    `pages` is the list of response bodies the fake serves, one per call
    (the last page repeats once the list is exhausted) — exactly the page
    walk `pr_runs` performs against the live endpoint.
    """
    import shutil
    import tempfile as _tf
    ws = _tf.mkdtemp(prefix="cw-gates-ws-")
    rt = _tf.mkdtemp(prefix="cw-gates-rt-")
    fake = _tf.mkdtemp(prefix="cw-gates-fake-")
    binp = os.path.join(fake, "bin")
    os.makedirs(binp)
    pages_f = os.path.join(fake, "pages.json")
    urls_f = os.path.join(fake, "urls.txt")
    with open(pages_f, "w", encoding="utf-8") as f:
        json.dump(pages, f)
    with open(os.path.join(binp, "gh"), "w", encoding="utf-8") as f:
        f.write("#!%s\n" % sys.executable +
                "import json, os, sys\n"
                "args = sys.argv[1:]\n"
                "logf = os.environ['FAKE_GH_URLS']\n"
                "n = sum(1 for _ in open(logf)) if os.path.exists(logf) else 0\n"
                "with open(logf, 'a') as lf:\n"
                "    lf.write((args[-1] if args else '') + chr(10))\n"
                "if any('actions/runs' in a for a in args):\n"
                "    pages = json.load(open(os.environ['FAKE_GH_PAGES']))\n"
                "    print(json.dumps(pages[min(n, len(pages) - 1)]))\n"
                "else:\n"
                "    print('{}')\n")
    os.chmod(os.path.join(binp, "gh"), 0o755)
    keys = ("PATH", "RUNNER_TEMP", "GITHUB_WORKSPACE", "GITHUB_REPOSITORY",
            "GH_TOKEN", "CW_HEAD_SHA", "CW_GATE_EMPTY_POLLS", "CW_GATE_POLLS",
            "AI_BRANCH", "FAKE_GH_PAGES", "FAKE_GH_URLS", "INPUT_HEAD_SHA")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "PATH": binp + os.pathsep + (saved["PATH"] or ""),
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        "GITHUB_REPOSITORY": "code-weaver/test-target",
        "GH_TOKEN": "fake-token",
        "AI_BRANCH": "ai/code-weaver/test",
        "CW_HEAD_SHA": head_sha,
        "FAKE_GH_PAGES": pages_f,
        "FAKE_GH_URLS": urls_f,
    })
    if empty_polls is not None:
        os.environ["CW_GATE_EMPTY_POLLS"] = str(empty_polls)
    # a no-op `time` stands in for the stdlib one so the poll loop does not
    # sleep for real: the stage's `import time` picks the stub up via
    # sys.modules (nothing else in the sandbox touches time)
    real_time = sys.modules.get("time")
    stub = types.ModuleType("time")
    stub.sleep = lambda s: None
    sys.modules["time"] = stub
    ns = {"__name__": "__main__",
          "__file__": os.path.join(ROOT, ".github", "actions", "gates-stage",
                                   "stage.py")}
    hook, cwd = sys.excepthook, os.getcwd()
    code = 0
    summary = ""
    urls = []
    os.chdir(ws)
    try:
        try:
            exec(compile(_read(".github/actions/gates-stage/stage.py"),
                         ns["__file__"], "exec"), ns)
        except SystemExit as e:
            code = (e.code if isinstance(e.code, int)
                    else (0 if e.code is None else 1))
        # read the state the stage left behind before the finally block
        # removes the temp dirs
        sf = os.path.join(rt, "cw", "stage-summary.txt")
        if os.path.isfile(sf):
            summary = open(sf, encoding="utf-8").read()
        if os.path.isfile(urls_f):
            urls = [l.strip() for l in open(urls_f) if l.strip()]
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        sys.modules["time"] = real_time
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)
        shutil.rmtree(fake, ignore_errors=True)
    return code, summary, urls


def test_gates_stage_query_is_scoped_to_the_pr_head():
    """(pr-and-gates "all PR-triggered workflows must be green";
    reference
    `requirements/pr-and-gates.feature::All PR-triggered workflows must
    be green`)
    the run query is scoped to the PR's head sha server-side — never a
    client-side filter over the repo-wide listing's first 100 newest runs —
    and the client-side event filter keeps push-triggered runs on the same
    sha out of the gate (they are not triggered on the pull request)."""
    sha = "b" * 40
    pages = [{"total_count": 3, "workflow_runs": [
        {"id": 1, "name": "house CI", "event": "pull_request",
         "head_sha": sha, "status": "completed", "conclusion": "success"},
        {"id": 2, "name": "fork-safe CI", "event": "pull_request_target",
         "head_sha": sha, "status": "completed", "conclusion": "success"},
        {"id": 3, "name": "push-only CI", "event": "push",
         "head_sha": sha, "status": "completed", "conclusion": "failure"},
    ]}]
    code, summary, urls = _run_gates_stage(pages, head_sha=sha)
    assert code == 0, \
        f"a green head passes the gates (push runs are not part of them): {summary!r}"
    assert "all 2 green" in summary, \
        f"the gate covers exactly the PR-triggered runs: {summary!r}"
    assert urls, "the gate never queried the runs endpoint"
    for u in urls:
        assert "head_sha=" + sha in u, \
            f"the run query must be scoped to the PR's head sha: {u}"
        assert "per_page=100" in u, f"the run query must page explicitly: {u}"


def test_gates_stage_sees_runs_beyond_the_first_hundred():
    """(pr-and-gates "the gate sees the PR's runs on a busy repo";
    reference
    `requirements/pr-and-gates.feature::The gate sees the PR's runs on a
    busy repo`)
    the run query walks the result set to its end — a full page means a
    next page exists — so a PR whose runs sit past the listing's first 100
    is still polled and judged. This is the field failure behind the
    rewrite: the earlier version read only that first page and hard-failed
    a healthy head whose runs it never saw."""
    sha = "e" * 40
    full = {"total_count": 101, "workflow_runs": [
        {"id": i, "name": f"noise {i}", "event": "push",
         "head_sha": sha, "status": "completed", "conclusion": "success"}
        for i in range(100)]}
    tail = {"total_count": 101, "workflow_runs": [
        {"id": 101, "name": "house CI", "event": "pull_request",
         "head_sha": sha, "status": "completed", "conclusion": "success"}]}
    code, summary, urls = _run_gates_stage([full, tail], head_sha=sha)
    assert code == 0, \
        f"the gate must find the PR's run on page two: {summary!r}"
    assert "all 1 green" in summary, \
        f"the gate judges exactly the PR-triggered runs: {summary!r}"
    assert any("page=2" in u for u in urls), \
        "a full page must page on — the run set was never walked to its end"


def test_gates_stage_empty_head_is_vacuously_green():
    """(pr-and-gates "a head with no PR-triggered workflow is vacuously
    green"; reference
    `requirements/pr-and-gates.feature::A head with no PR-triggered
    workflow is vacuously green`)
    a head with no visible PR-triggered run succeeds after the grace
    window: the earlier version's vacuously-green return was dead code
    inside the all-completed branch, so such a head fell through to the
    in-progress branch and hard-failed its poll cap twenty minutes later
    instead of letting the factory proceed."""
    code, summary, urls = _run_gates_stage(
        [{"total_count": 0, "workflow_runs": []}],
        head_sha="c" * 40, empty_polls=2)
    assert code == 0, \
        f"an empty gate set is vacuously green, not a poll-cap failure: {summary!r}"
    assert "vacuously green" in summary, \
        f"the summary records the vacuous pass: {summary!r}"
    assert urls, "the grace window must actually poll the endpoint"


def test_gates_stage_polls_in_progress_runs_to_green():
    """(pr-and-gates "all PR-triggered workflows must be green";
    reference
    `requirements/pr-and-gates.feature::All PR-triggered workflows must
    be green`)
    runs that are still in progress keep the gate polling (bounded by the
    poll cap, the job timeout behind that), and the gate proceeds only once
    every run has completed green — the stage's exit reflects the final
    state, not the first poll."""
    sha = "d" * 40
    running = {"id": 1, "name": "house CI", "event": "pull_request",
               "head_sha": sha, "status": "in_progress", "conclusion": None}
    done = {"id": 1, "name": "house CI", "event": "pull_request",
            "head_sha": sha, "status": "completed", "conclusion": "success"}
    code, summary, urls = _run_gates_stage(
        [{"total_count": 1, "workflow_runs": [running]},
         {"total_count": 1, "workflow_runs": [done]}],
        head_sha=sha)
    assert code == 0 and "all 1 green" in summary, \
        f"the gate waits out the in-progress run and then passes: {summary!r}"
    assert len(urls) >= 2, \
        "the gate must re-poll until every run has completed"
