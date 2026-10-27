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
- the report stage's final status report lists the run's total input and
  output tokens and the total cost — assembled from the per-call usage
  records in the state dir, the cost derived from the recorded usage and
  the run's resolved model (rate listed; unpriced for a model with no
  rate entry), and a failed run's report covering the calls made before
  the stop (issue-43 "the final report lists the input and output tokens
  used during the run", "the final report lists the total cost of the
  run", "the usage and cost of a failed run are reported too");
- the validator skips-not-fails where the parser port is absent
  (test-and-review "the suite runs on an interpreter without pytest");
- the factory's max-loops default matches the oracle's Given (5) and the
  doc surface that repeats the value agrees with it, while the token budget
  is gone from the configuration surface (no max-tokens row on the doc
  surfaces)
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
import sys
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


def test_extract_prompt_places_delta_by_topic():
    """(requirement-extraction "extraction places the delta by topic") the
    prompt's contract: a delta's scenarios extend the existing topic file
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
    """(requirement-extraction "extraction places the delta by topic") the
    oracle is structured by topic, not by issue: no file name in the prompt
    carries an issue number, and the validator enforces the same rule on the
    changed files (house CI runs it over the whole oracle, so the structure
    holds for the existing files too)."""
    prompt = _read("pi-prompts/requirements.md")
    assert "carries an issue number" in prompt
    validator = _read(".github/scripts/gherkin-validate.py")
    assert "named after an issue" in validator
    assert "ISSUE_NAMED_RE" in validator


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


def _report_action_source() -> str:
    """The report action's inline python — its `run: |` block (the step's
    whole body), dedented to a runnable source. The tests exec it against
    a sandboxed state dir: the assembled report is a function of the state
    dir's contents (the per-call usage ledger, the trigger's resolved
    configuration) and the action's inputs, so no live workflow is needed.
    """
    lines = _read(".github/actions/report/action.yml").splitlines()
    step = None
    for i, ln in enumerate(lines):
        if "Write the final status report" in ln:
            step = i
            break
    assert step is not None, "the report action's status-report step is gone"
    for i in range(step, len(lines)):
        if lines[i].rstrip() == "      run: |":
            body, indent = [], None
            for cont in lines[i + 1:]:
                if not cont.strip():
                    body.append("")
                    continue
                ind = len(cont) - len(cont.lstrip(" "))
                if ind < 8:
                    break
                if indent is None:
                    indent = ind
                body.append(cont[indent:])
            src = "\n".join(body)
            assert src.lstrip().startswith("try:"), \
                "the step's run block is no longer the status-report python"
            return src
    raise AssertionError(
        "no `run: |` block on the report action's status-report step")


def _run_report_action(run_result="success", pr_number="7", issue_number="42",
                       ledger=None, model="Ornith-1.5-35B-A3B"):
    """Exec the report action's inline python in a sandbox: a plain temp
    workspace (no git repo, no doc dir, no PLAN.md — the arc42-activity
    path has nothing to touch), a temp RUNNER_TEMP carrying the merged
    stage state (the per-call usage ledger the report job's artifact
    downloads leave behind, plus the trigger's resolved configuration),
    and a fake `gh` on PATH that serves the PR view and captures the issue
    comment body it is posted with — no network. Returns (the final PR
    body, the issue comment)."""
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
    fake = tempfile.mkdtemp(prefix="cw-report-fake-")
    binp = os.path.join(fake, "bin")
    os.makedirs(binp)
    comment_f = os.path.join(fake, "issue-comment.txt")
    with open(os.path.join(binp, "gh"), "w", encoding="utf-8") as f:
        f.write("#!%s\n" % sys.executable +
                "import json, os, sys\n"
                "args = sys.argv[1:]\n"
                "body = ''\n"
                "for a in args:\n"
                "    if a.startswith('body='):\n"
                "        body = a[len('body='): ]\n"
                "if args[:1] == ['api'] and any('pulls/' in a for a in args):\n"
                "    print(json.dumps({'body': '## Progress so far',\n"
                "                      'head': {'sha': 'f' * 40,\n"
                "                                'ref': 'ai/code-weaver/7'},\n"
                "                      'html_url': 'https://gh.example/pr/7'}))\n"
                "    sys.exit(0)\n"
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
        "CW_RUN_RESULT": run_result,
        "CW_ISSUE_NUMBER": issue_number,
        "CW_PR_NUMBER": pr_number,
    })
    hook, cwd = sys.excepthook, os.getcwd()
    os.chdir(ws)
    # the action's `import common` must fail here, as it does on this
    # runner build (the action dir's `/./` segment breaks the scripts path
    # resolution): the action then runs on its local fallback definitions
    # — the path production takes. Otherwise a `common` already imported
    # by another test module in this process (or the scripts dir already on
    # sys.path) would satisfy the import and the fallback definitions
    # would never land.
    scripts_dir = os.path.realpath(
        os.path.join(ROOT, ".github", "scripts"))
    path_saved = list(sys.path)
    sys.path[:] = [p for p in sys.path
                   if p and os.path.realpath(p) != scripts_dir]
    common_mod = sys.modules.pop("common", None)
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
    return out["pr_body"], out["comment"]


def test_report_lists_usage_totals_assembled_from_the_ledger():
    """(issue-43 "the final report lists the input and output tokens used
    during the run", "the usage totals cover every pi call the run made")
    the report action assembles the run's usage totals from the per-call
    usage records in the state dir (one tokens.txt line per pi call: input
    + output tokens; the report job downloads the stages' artifacts in
    pipeline order, so the ledger surviving the downloads is the complete
    one) into the final status report: the PR body lists the total input
    and the total output tokens across the run, and the source-issue
    comment carries the same totals."""
    pr_body, comment = _run_report_action(
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
    "the listed cost is consistent with the run's recorded token usage")
    the listed cost is derived from the recorded usage, keyed on the run's
    resolved model (the llm-model setting from the trigger's
    resolved-config state), via the report's per-model rate table — the
    rate used is listed in the report so the cost is auditable; a model
    with no rate entry is listed as unpriced, and the recorded usage
    totals still land in the report."""
    # 15000 in / 3500 out across the run; the resolved model is priced
    ledger = ["10000 2000", "5000 1500"]
    r_in, r_out = 0.10, 0.20
    priced = (f"- **Total cost:** ${(15000 * r_in + 3500 * r_out) / 1e6:.4f} "
              f"(model `Ornith-1.5-35B-A3B` @ ${r_in:.2f}/M input, "
              f"${r_out:.2f}/M output)")
    pr_body, comment = _run_report_action(ledger=ledger)
    for surface in (pr_body, comment):
        assert priced in surface, \
            ("the listed cost must be recorded usage × the resolved model's "
             f"rate, with the rate listed: {surface!r}")
    # a model with no rate entry is listed as unpriced — the usage totals
    # are reported regardless
    pr_body, comment = _run_report_action(
        ledger=ledger, model="Some-Other-Runner-Model")
    unpriced = (f"- **Total cost:** unpriced "
                f"(model `Some-Other-Runner-Model` has no rate entry — "
                "the owner extends the report's rate table)")
    for surface in (pr_body, comment):
        assert unpriced in surface, \
            f"a model with no rate entry is listed as unpriced: {surface!r}"
        assert "- **Total input tokens:** 15000" in surface
        assert "- **Total output tokens:** 3500" in surface


def test_failed_run_report_covers_the_calls_before_the_stop():
    """(issue-43 "the usage and cost of a failed run are reported too")
    the report job runs on success and failure: a run that stopped early
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
              f"${r_out:.2f}/M output)")
    # a failed run that reached the PR: the comment (and the PR body's
    # final status) carry the pre-stop usage and cost
    pr_body, comment = _run_report_action(
        run_result="failure", ledger=ledger)
    for surface in (pr_body, comment):
        for line in ("- **Total input tokens:** 3000",
                     "- **Total output tokens:** 400",
                     priced):
            assert line in surface, \
                ("a failed run is reported with the calls made before "
                 f"the stop: {surface!r}")
    # a run that died before the PR existed: the no-PR failure comment
    # still lists the pre-stop usage and cost
    pr_body, comment = _run_report_action(
        run_result="failure", pr_number="", ledger=ledger)
    assert pr_body == "", "no PR was opened — there is no PR body to complete"
    for line in ("- **Total input tokens:** 3000",
                 "- **Total output tokens:** 400",
                 priced):
        assert line in comment, \
            f"the no-PR failure report still lists the pre-stop usage: {comment!r}"


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
    means no cap") the oracle's Given pins the factory's max-loops default
    as 5 — the reusable workflow declares it, and the doc surface that
    repeats the value (the README's input table, the arc42 quality chapter)
    agrees with it; the token budget is gone from the configuration surface
    — no max-tokens row on the doc surfaces, no token-budget default
    wording — and the old 25 / 5,000,000 pair is gone from the tree. A
    target still lowers or raises the cap per repo — the inputs → job env →
    caps_ok machinery is unchanged (0 = no cap)."""
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
