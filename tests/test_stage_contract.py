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
- the consumer workflow and the README pin the oracle's owner at a
  version tag — a single increasing number, the current scheme (the
  retired semver ref shape is gone) — and the two surfaces declare the
  same owner, the same path and the same tag in lock-step
  (reuse-by-ref "the factory is invoked as a reusable workflow",
  "every published version is a stable ref");
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
  review-stage's verdict oracle is delta-scoped (test-and-review: pi judges
  only the scenarios of the feature files this run changed — the accumulated
  oracle is not re-judged every run — and a run that changed no requirements
  passes vacuously instead of failing as unparseable);
- the pr job generates the PR body with pi from the requirements, the
  plan and the review (pr-and-gates "a pull request is opened against
  the target branch"), and the template fallback — used when the pi call
  produced no body — describes the issue it implements: the source
  issue's number and title read from the trigger's state files (a body
  still names the issue where the job-env relay dropped the values), the
  issue's plan embedded, the requirement scenarios the run changed
  against the baseline listed, and no resolved-configuration dump
  (pr-and-gates "the PR body describes the issue it implements");
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
- the implement guard runs inverted-allow: its deny set is the protected
  set (requirements, plans) and its allow set re-admits only the current
  issue's plan file — another issue's plan is a violation the guard reverts
  while the implementation's lane (code, tests, docs, new dirs) is
  admitted (implement "implementation may only edit the current issue's
  plan");
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
    settings via with: and GH_TOKEN via secrets:. The ref is a single
    increasing number: the current scheme's tag shape (the retired
    semver ref shape is gone — reuse-by-ref "every published version is
    a stable ref": "its tag is a single increasing version number"). The
    expected outcome extends to the run's pi harness providers
    (configuration "The pi harness secrets ride the reusable workflow's
    secrets block"): the same three surfaces — the factory's secrets:
    block, the deployed consumer workflow, the README example — carry the
    four provider secret entries in the same form, while the owner, path
    and ref pin stays unchanged — the lock-step chapter 8 states (both
    the deployed consumer workflow and the README's example declare the
    same owner, path and tag)."""
    text = _read(".github/workflows/code-weaver.yml")
    m = re.search(r"uses:\s*([\w.-]+)/code-weaver/(\S+?)@([\w.-]+)", text)
    assert m, "no uses: line naming the factory"
    owner, path, ref = m.groups()
    assert owner == "MelvinKl", f"oracle pins the MelvinKl owner, found {owner}"
    assert path.rstrip() == ".github/workflows/factory.yml"
    assert re.fullmatch(r"\d+", ref), (
        f"@{ref} is not a single increasing version number — the current "
        "scheme's tag shape (the retired semver ref shape is gone)")
    assert "with:" in text and "GH_TOKEN" in text and "secrets:" in text
    # the deployed consumer workflow and the README's consumption example
    # declare the same owner, the same path and the same tag (lock-step)
    readme = _read("README.md")
    rm = re.search(r"uses:\s*([\w.-]+)/code-weaver/(\S+?)@([\w.-]+)", readme)
    assert rm and rm.groups()[:3] == (owner, path, ref), (
        "the README's example drifted from the deployed workflow — the "
        "lock-step spans the full owner, path and ref")
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


def test_factory_workflow_is_self_contained():
    """(reuse-by-ref "the factory workflow is self-contained"; the
    successor of "the factory's workflow names its own actions by owner,
    repo and path" and the in-file half of "a published version is
    self-consistent") no `uses:` reference to the factory's own actions
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
    """(pr-and-gates "the PR body describes the issue it implements") the
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
    trail exists for human review") the report stage appends the
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


def _run_report_action(run_result="success", pr_number="7", issue_number="42",
                       ledger=None, model="Ornith-1.5-35B-A3B",
                       view_body="## Progress so far"):
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
    closed)."""
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
        out["closed"] = os.path.isfile(comment_f + ".closed")
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
    return out["pr_body"], out["comment"], out["closed"]


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
    pr_body, comment, _closed = _run_report_action(ledger=ledger)
    for surface in (pr_body, comment):
        assert priced in surface, \
            ("the listed cost must be recorded usage × the resolved model's "
             f"rate, with the rate listed: {surface!r}")
    # a model with no rate entry is listed as unpriced — the usage totals
    # are reported regardless
    pr_body, comment, _closed = _run_report_action(
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
    pr_body, comment, _closed = _run_report_action(
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
    pr_body, comment, _closed = _run_report_action(
        run_result="failure", pr_number="", ledger=ledger)
    assert pr_body == "", "no PR was opened — there is no PR body to complete"
    for line in ("- **Total input tokens:** 3000",
                 "- **Total output tokens:** 400",
                 priced):
        assert line in comment, \
            f"the no-PR failure report still lists the pre-stop usage: {comment!r}"


def test_report_verifies_the_pr_body_completion():
    """(reporting "the PR description carries the same usage numbers as
    the issue comment") after editing the PR body the stage re-reads the
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
    the issue comment") where the completion could not be applied to the
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
    """(reporting "a failed run leaves the source issue open") a failure
    reports the stage outcomes and the pre-stop usage on the issue — but
    never closes it: the issue stays open for a re-trigger."""
    pr_body, comment, closed = _run_report_action(
        run_result="failure", ledger=["3000 400"])
    assert "run failed" in comment
    assert "left open" in comment, \
        f"a failed run's comment states the issue stays open: {comment!r}"
    assert not closed, "a failed run must not close the source issue"


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


def test_implement_guard_protects_requirements_and_other_plans():
    """(implement "implementation may only edit the current issue's
    plan") the implement guard runs inverted-allow — the stage's DENY set
    is the protected set (requirements + plans dir, the guard's `!`
    entries) and its ALLOW set re-admits exactly the current issue's plan
    file plus `__pycache__`: another issue's plan file and a requirements
    file are violations the guard reverts, while everything else is the
    implementation's lane — judged with the guard's own predicate
    (common.guard_denied)."""
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
    """(pr-and-gates "all PR-triggered workflows must be green") the run
    query is scoped to the PR's head sha server-side — never a client-side
    filter over the repo-wide listing's first 100 newest runs — and the
    client-side event filter keeps push-triggered runs on the same sha out
    of the gate (they are not triggered on the pull request)."""
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
    """(pr-and-gates "the gate sees the PR's runs on a busy repo") the run
    query walks the result set to its end — a full page means a next page
    exists — so a PR whose runs sit past the listing's first 100 is still
    polled and judged. This is the field failure behind the rewrite: the
    earlier version read only that first page and hard-failed a healthy
    head whose runs it never saw."""
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
    green") a head with no visible PR-triggered run succeeds after the grace
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
    """(pr-and-gates "all PR-triggered workflows must be green") runs that
    are still in progress keep the gate polling (bounded by the poll cap,
    the job timeout behind that), and the gate proceeds only once every
    run has completed green — the stage's exit reflects the final state,
    not the first poll."""
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
