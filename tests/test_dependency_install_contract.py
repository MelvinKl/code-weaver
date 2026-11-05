"""Unit tests pinning the project-dependency-install step (issue #82).

The target project's dependencies: the factory's pipeline installs pi
itself (stage 2) and configures the run's pi harness, but carries no
step that installs the target project's own dependencies. The mechanism
is one optional reusable-workflow input and one inlined step per
consuming job:

- declaration — the `dependency-install` input of the factory's
  `workflow_call` inputs (string, optional, empty default: an older
  consumer's `with:` block stays schema-valid): the command the run's
  pipeline runs to install the target project's dependencies. It is an
  input, not a secret — an install command is project configuration,
  and the four harness providers on the `secrets:` block belong to the
  pi harness and are deliberately not extended by it;
- execution — the `implement` job (stage 8) and the `review` job (stage
  10, the `make test` suite run) each carry the step after their
  checkout of the AI branch and before their stage-script step (in
  `implement`, before the stage-baseline recording, so the install's
  footprint is never counted as the stage's work by the guard): a
  one-time install in one job's workspace cannot serve the next job's
  replaced workspace, so the install runs per consuming job, and no
  other job gains the step and no new job is added;
- no-op — where the input is empty the step logs and exits 0 without
  touching the workspace: a target that declares nothing runs
  unchanged; the trigger's resolved-config log records the declaration
  (or its absence) like every other resolved input;
- documentation — the README (Inputs table + the consumption example)
  and the arc42 chapters covering the mechanism state the same input,
  the same placement and the same unchanged-when-undeclared behaviour
  on the same surfaces.
- upgrade (issue 18) — beside the install step, the implement job
  (stage 8) carries the dependency-upgrade step, inlined workflow text
  (no new job — the pipeline count stays): positioned after its checkout
  of the AI branch and before its stage step and its stage-baseline
  recording, the setting relayed through the documented CW_<name> step
  env idiom; where the setting (the workflow's optional
  dependency-upgrade input, default on) is at its default and the target
  has declared the dependency-install command, the step runs that
  command to upgrade the project's dependencies to newer versions and
  commits the footprint to the AI branch — the documented cross-job
  channel the consuming stages (the implementation stage, the review
  job's suite run) work through; where the setting is off, or no install
  command is declared, the step is a no-op — it guards on the relayed
  value, logs and exits 0 without touching the workspace — and the
  run's stages, pull request and final status report are unchanged by
  the upgrade's absence; the documented surfaces (the README — the
  Inputs-table row and the consumption example — plus the arc42
  chapters covering the mechanism) state the stage, its default, the
  turn-off input, the before-implementation placement and the
  unchanged-when-off behaviour on the same surfaces.
- resolved pi call cap (issue 97) and resolved job timeout (issue 98)
  — this module also pins entries of the trigger's
  resolved-configuration record: the record (the workflow-log block the
  trigger tees into the resolved-config file that rides the trigger's
  artifact) lists the run's resolved pi call cap with the rest of the
  resolved configuration — the declared value where a target declared
  one, the 21600 default where the input is undeclared — and the record
  stays in the workflow log, never committed to the repo; the record
  lists the run's resolved job timeout with the rest of the resolved
  configuration too — the declared value where a target declared one,
  the 480 default where the input is undeclared — and it carries no
  exceedance line any more: with the validation moved to trigger time,
  a run whose declared cap leaves the stage's non-call work no headroom
  inside the job timeout fails before any stage runs, so the record's
  pi-cap line simply carries the resolved value.

The workflow reads are line-based (stdlib only — the documented
`on:`/YAML 1.1 gotcha makes a whole-document parse the wrong tool for
a workflow's event map), and the doc reader follows the setup-pi
docs-contract and oracle-count precedent (the README plus every arc42
chapter, the AI-activity section cut — its per-run records are history,
never the stated contract).

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

FACTORY = ".github/workflows/factory.yml"

# The heading that opens the AI-activity section (chapter 1 carries it in
# this repo): its entries record per-run fulfilled counts and stage
# listings — past records, never the stated contract.
AI_ACTIVITY_HEADING = "## AI activity"


def _read(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as f:
        return f.read()


def _workflow_call_block(factory: str, key: str) -> str:
    """The reusable workflow's `on.workflow_call.<key>` block, sliced
    line-based: from its 4-indent key line to the next 4-indent (or
    shallower) line."""
    lines = factory.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln == f"    {key}:"),
                 None)
    assert start is not None, f"the factory's workflow_call has no {key} block"
    block = []
    for ln in lines[start + 1:]:
        if ln.strip():
            indent = len(ln) - len(ln.lstrip(" "))
            if indent <= 4:
                break
        block.append(ln)
    return "\n".join(block)


def _input_entry(block: str, name: str) -> str:
    """One entry of the workflow_call inputs block: from its 6-indent key
    line to the next 6-indent (or shallower) line."""
    lines = block.splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if ln.strip() == f"{name}:"), None)
    assert start is not None, f"no {name} input in the factory's inputs block"
    entry = [lines[start]]
    for cont in lines[start + 1:]:
        if cont.strip():
            indent = len(cont) - len(cont.lstrip(" "))
            if indent <= 6:
                break
        entry.append(cont)
    return "\n".join(entry)


def _job_region(factory: str, name: str, next_name: str = None) -> str:
    """A job's region: from its 2-indent job key to the next job key (to
    the end of the file for the last job)."""
    start = factory.index(f"  {name}:")
    end = (factory.index(f"  {next_name}:", start)
           if next_name is not None else len(factory))
    return factory[start:end]


def _step_index(region: str, predicate) -> int:
    """The region's line index of the first step whose opener line (a
    6-indent `- ` item) matches the predicate; -1 if no step matches."""
    for i, ln in enumerate(region.splitlines()):
        if ln.startswith("      - ") and predicate(ln):
            return i
    return -1


def _step_block(region: str, step_index: int) -> str:
    """The step's full text: from its opener line to the next step opener
    (or the end of the region)."""
    lines = region.splitlines()
    end = next((k for k in range(step_index + 1, len(lines))
                if lines[k].startswith("      - ")), len(lines))
    return "\n".join(lines[step_index:end])


def _resolved_config_block(factory: str) -> str:
    """The trigger resolve step's resolved-config `{ … }` group — from the
    opening brace before its heading echo to the `} | tee` line that closes
    it: the group is what writes the file the audit reads."""
    trig = _job_region(factory, "trigger", "setup-pi")
    heading = "### Code Weaver — resolved configuration"
    i = trig.find(heading)
    assert i != -1, "the trigger lost its resolved-config heading"
    start = trig.rfind("{", 0, i)
    assert start != -1, "the resolved-config group lost its opening brace"
    end = trig.find("} | tee", i)
    assert end != -1, "the resolved-config group lost its `} | tee` close"
    return trig[start:end]


# ── task 1: the declaration channel ─────────────────────────────────────


def test_factory_exposes_the_optional_dependency_install_input():
    """(project-dependencies "The factory provides a way for a target to
    add a project-dependency-install step"; reference
    `requirements/project-dependencies.feature::The factory provides a
    way for a target to add a project-dependency-install step`) the
    factory-side half of the declaration channel: the input is declared
    under the workflow_call inputs as optional (required: false) with an
    empty default — an older consumer's `with:` block stays schema-valid;
    the trigger's resolved-config log records the declaration or its
    absence (the documented audit surface for resolved inputs); and the
    four harness providers on the `secrets:` block are untouched — the
    new channel is an input, and no secret value rides a `with:` input."""
    factory = _read(FACTORY)
    entry = _input_entry(_workflow_call_block(factory, "inputs"),
                         "dependency-install")
    assert "type: string" in entry, \
        "the dependency-install input is not a string input"
    assert "required: false" in entry, \
        "the dependency-install input must be optional — an older " \
        "consumer's with: block stays schema-valid"
    assert 'default: ""' in entry, \
        "the dependency-install input must default to empty — a target " \
        "that declares no step runs unchanged"
    # the resolved-config log records the declaration — and the
    # undeclared case
    block = _resolved_config_block(factory)
    assert "dependency-install" in block, \
        "the trigger's resolved-config log does not record the " \
        "dependency-install declaration"
    assert "not declared" in block, \
        "the trigger's resolved-config log does not record the undeclared case"
    assert "inputs.dependency-install" in block, \
        "the trigger's resolved-config log does not record the declared value"
    # the four harness providers on the secrets: block are untouched —
    # the new channel is an input, and no secret value rides a with: input
    secrets_block = _workflow_call_block(factory, "secrets")
    for name in ("PI_MODELS", "PI_SETTINGS", "PI_MCP", "PI_EXTENSION_ENV"):
        assert f"      {name}:" in secrets_block, \
            f"the harness provider {name} left the factory's secrets block"
    assert "GH_TOKEN:" in secrets_block
    assert "dependency-install" not in secrets_block, \
        "the dependency-install channel is an input — it must not be a " \
        "secrets-block entry"


# ── task 2: execution in the two consuming jobs, no-op where empty ─────


def test_declared_step_runs_before_the_stages_that_consume_the_dependencies():
    """(project-dependencies "The declared dependency-install step runs
    before the stages that consume the dependencies"; reference
    `requirements/project-dependencies.feature::The declared
    dependency-install step runs before the stages that consume the
    dependencies`) both stage jobs whose stages consume the project's
    dependencies — implement (stage 8) and review (stage 10, the
    `make test` suite run) — carry the step, and in each its position is
    after the job's checkout of the AI branch and before the job's
    stage-script step, so the stage (and the suite run) executes against
    a workspace the declared step has already installed into; the step
    relays the input through the documented CW_<name> step env idiom."""
    factory = _read(FACTORY)
    for job, next_job, stage_step in (
            ("implement", "review", "Stage 8 — implement the plans"),
            ("review", "pr", "Stage 10-11 — run the oracle, review, fix")):
        region = _job_region(factory, job, next_job)
        checkout = _step_index(region,
                               lambda ln: "- uses: actions/checkout" in ln)
        step = _step_index(region,
                           lambda ln: "name:" in ln
                           and "dependency-install" in ln)
        stage = _step_index(region, lambda ln: stage_step in ln)
        assert checkout != -1, f"the {job} job lost its AI-branch checkout step"
        assert step != -1, \
            f"the {job} job carries no dependency-install step"
        assert stage != -1, f"the {job} job lost its stage-script step"
        assert checkout < step < stage, (
            f"the {job} job's dependency-install step is not after the "
            f"checkout and before the stage (checkout line {checkout}, "
            f"step line {step}, stage line {stage}) — the stage must run "
            "against the installed environment")
        block = _step_block(region, step)
        assert "CW_DEPENDENCY_INSTALL: ${{ inputs.dependency-install }}" in block, \
            f"the {job} job's step does not relay the input through the " \
            "CW_ step env idiom"


def test_undeclared_target_runs_unchanged():
    """(project-dependencies "A target that declares no dependency-install
    step runs unchanged"; reference
    `requirements/project-dependencies.feature::A target that declares no
    dependency-install step runs unchanged`) where the input is empty the
    step is a no-op — its body guards on the relayed value, logs the
    undeclared case and exits without touching the workspace — and only
    the two consuming jobs carry the step: every other job (trigger,
    setup-pi, baseline, extract, plan, pr, gates, report) is untouched,
    so the run's stages, pull request and final status report are
    unchanged by the mechanism's presence."""
    factory = _read(FACTORY)
    job_keys = ("trigger", "setup-pi", "baseline", "extract", "plan",
                "implement", "review", "pr", "gates", "report")
    next_of = dict(zip(job_keys, job_keys[1:] + (None,)))
    for job in job_keys:
        region = _job_region(factory, job, next_of[job])
        install = [ln for ln in region.splitlines()
                   if ln.startswith("      - name: ")
                   and "dependency-install" in ln]
        if job in ("implement", "review"):
            assert len(install) == 1, \
                f"the {job} job must carry exactly one dependency-install step"
        else:
            assert not install, (
                f"the {job} job gained a dependency-install step — only "
                "the two consuming jobs carry it; a step in another job "
                "would change the run's stages, pull request or final "
                "status report")
    # the empty-value path is a no-op in both consuming jobs: the body
    # guards on the relayed value, logs the undeclared case and exits 0
    # before the command runs — without touching the workspace
    for job, next_job in (("implement", "review"), ("review", "pr")):
        region = _job_region(factory, job, next_job)
        i = _step_index(region,
                        lambda ln: "name:" in ln
                        and "dependency-install" in ln)
        assert i != -1, f"the {job} job carries no dependency-install step"
        block = _step_block(region, i)
        assert "CW_DEPENDENCY_INSTALL" in block, \
            f"the {job} job's step does not guard on the relayed value"
        assert "if [ -z" in block and "exit 0" in block, \
            f"the {job} job's step has no empty-value no-op path"
        assert "no project-dependency-install step is declared" in block, \
            f"the {job} job's step does not log the undeclared case"
        assert block.index("if [ -z") < block.index("bash -c"), \
            f"the {job} job's no-op path exits after the install runs"


# ── task 3: the documented surfaces state the same ─────────────────────


def _normalize(text: str) -> str:
    """The surface ready for marker matching: the AI-activity section cut,
    backticks stripped (the docs backtick names; the markers are plain),
    and whitespace runs collapsed to single spaces (prose wraps at any
    width)."""
    i = text.find(AI_ACTIVITY_HEADING)
    if i != -1:
        text = text[:i]
    return " ".join(text.replace("`", "").split())


def _doc_surfaces():
    """[(relpath, normalized text)] — the README plus every arc42 chapter
    file under `docs/` (one chapter per file) — the same surface set the
    release-contract, setup-pi docs-contract and oracle-count modules
    pin against."""
    surfaces = [("README.md", _normalize(_read("README.md")))]
    docs = os.path.join(ROOT, "docs")
    surfaces += [(os.path.join("docs", fname),
                  _normalize(_read(os.path.join(docs, fname))))
                 for fname in sorted(os.listdir(docs))
                 if fname.endswith(".md")]
    return surfaces


def test_readme_and_arc42_document_the_dependency_install_mechanism():
    """(project-dependencies "The README documents how to add the
    project-dependency-install step"; reference
    `requirements/project-dependencies.feature::The README documents how
    to add the project-dependency-install step`) the documented surfaces
    (the README plus every arc42 chapter, the AI-activity section cut)
    state the mechanism on the same surfaces: the README's instructions
    show how to declare the step the run's pipeline executes — the
    Inputs-table entry and the consumption example name the same input —
    and every surface that covers the mechanism states the input name,
    the before-the-consuming-stages placement and the
    unchanged-when-undeclared behaviour."""
    surfaces = _doc_surfaces()
    by_relpath = dict(surfaces)
    # the README's instructions show how to declare the step: the
    # Inputs-table entry names the input with its empty default
    readme = by_relpath["README.md"]
    assert "| dependency-install | *(empty)* |" in readme, \
        "the README's Inputs table has no dependency-install entry"
    # and the consumption example shows the declaration in the with:
    # block — how a maintainer adds the step
    raw = _read("README.md")
    start = raw.index("## Consume it")
    end = raw.find("\n## ", start)
    example = raw[start:end] if end != -1 else raw[start:]
    assert "dependency-install:" in example, \
        "the README's consumption example does not show the declaration"
    # the arc42 chapters that cover the mechanism name the same input
    covering = [p for p, t in surfaces if "dependency-install" in t]
    for p in ("docs/04-context-and-scope.md", "docs/05-solution-strategy.md",
              "docs/06-building-block-view.md", "docs/07-runtime-view.md",
              "docs/08-deployment-view.md", "docs/11-glossary.md"):
        assert p in covering, \
            f"{p} no longer covers the dependency-install mechanism"
    # the scenario's And step: the arc42 documentation covering the same
    # mechanism states the same — every surface that names the input also
    # states the before-the-consuming-stages placement and the
    # unchanged-when-undeclared behaviour
    for p, t in surfaces:
        if "dependency-install" not in t:
            continue
        assert "before its stage" in t, (
            f"{p} covers the dependency-install mechanism but does not "
            "state that the step runs before the stage that consumes the "
            "dependencies")
        assert "the run is unchanged" in t, (
            f"{p} covers the dependency-install mechanism but does not "
            "state that a target that declares nothing runs unchanged")


# ── task 4: the dependency-upgrade step (issue 18) ───────────────────


def test_upgrade_step_sits_before_the_implementation_stage():
    """(project-dependencies "The factory's run upgrades the target
    project's dependencies"; reference
    `requirements/project-dependencies.feature::The factory's run
    upgrades the target project's dependencies`) the factory's pipeline
    carries the dependency-upgrade mechanism as an inlined step in the
    existing implement job (the job whose stage is the implementation
    stage, stage 8) — the documented extension idiom: no new job is
    added, the pipeline count stays. The step is positioned after the
    job's checkout of the AI branch and before the job's stage step,
    with the job's stage-baseline recording after the step, so the
    upgrade's footprint is never counted as the stage's work by the
    guard (the documented dependency-install placement idiom, chapter
    7); the setting is relayed through the documented CW_<name> step
    env idiom, and the step executes where the setting is at its
    default (on): it has no workflow-level skip, and the body's early
    exits are only the off value and the no-declared-command no-op —
    the upgrade command rides the dependency-install input, the
    documented channel by which a target names a command for its own
    project environment, and a target that declares none has no upgrade
    to run. The unchanged-run half mirrors the dependency-install job
    sweep: no other job carries the step, and where the setting is off
    the step's no-op path guards on the relayed value, logs the off case
    and exits before touching the workspace (the off path of "The
    dependency-upgrade setting is configurable"; reference
    `requirements/configuration.feature::The dependency-upgrade
    setting is configurable`)."""
    factory = _read(FACTORY)
    region = _job_region(factory, "implement", "review")
    checkout = _step_index(region,
                           lambda ln: "- uses: actions/checkout" in ln)
    step = _step_index(region,
                       lambda ln: "name:" in ln
                       and "dependency-upgrade" in ln)
    stage = _step_index(region,
                        lambda ln: "Stage 8 — implement the plans" in ln)
    assert checkout != -1, \
        "the implement job lost its AI-branch checkout step"
    assert step != -1, \
        "the implement job carries no dependency-upgrade step"
    assert stage != -1, "the implement job lost its stage step"
    assert checkout < step < stage, (
        f"the implement job's dependency-upgrade step is not after the "
        f"checkout and before the stage (checkout line {checkout}, "
        f"step line {step}, stage line {stage}) — the stage's "
        "stage-baseline recording measures the stage's work, and a "
        "footprint after it would be counted as the stage's work by "
        "the guard")
    # the stage-baseline recording (the guard's measurement point) is
    # the stage step's — and it sits after the upgrade step
    assert "stage-baseline.sha" in _step_block(region, stage), \
        "the implement job's stage step no longer records the " \
        "stage-baseline"
    # the setting is relayed through the documented CW_<name> step env
    # idiom
    block = _step_block(region, step)
    assert "CW_DEPENDENCY_UPGRADE: ${{ inputs.dependency-upgrade }}" \
        in block, \
        "the step does not relay the setting through the CW_ step env " \
        "idiom"
    # the step executes where the setting is at its default (on): no
    # workflow-level skip, and the body's early exits are only the off
    # value and the no-declared-command no-op
    assert not any(ln.strip().startswith("if:")
                   for ln in block.splitlines()), \
        "the upgrade step carries a workflow-level skip — it must run " \
        "in the job and gate on the relayed setting"
    assert 'if [ "${CW_DEPENDENCY_UPGRADE:-on}" = "off" ]; then' in block, \
        "the step does not guard on the relayed setting's off value"
    assert 'if [ -z "${CW_DEPENDENCY_INSTALL:-}" ]' in block, \
        "the step has no no-declared-command no-op path — a target " \
        "that declares none has no upgrade to run (the documented " \
        "no-op property of the dependency-install input)"
    # the off path: guard, log, exit 0 — all before the workspace is
    # touched (the upgrade command, the commit)
    off = block.index('if [ "${CW_DEPENDENCY_UPGRADE:-on}" = "off" ]')
    off_exit = block.index("exit 0", off)
    assert off < off_exit < block.index("bash -c"), \
        "the off path does not guard, log and exit before the upgrade " \
        "runs"
    off_seg = block[off:off_exit]
    assert "runs without the dependency-upgrade stage" in off_seg, \
        "the off path does not log that the pipeline runs without the " \
        "stage"
    assert "unchanged" in off_seg, \
        "the off path does not log the run as unchanged by the " \
        "upgrade's absence"
    # the unchanged-run half (the dependency-install job-sweep idiom):
    # only the implement job carries the step
    job_keys = ("trigger", "setup-pi", "baseline", "extract", "plan",
                "implement", "review", "pr", "gates", "report")
    next_of = dict(zip(job_keys, job_keys[1:] + (None,)))
    for job in job_keys:
        region = _job_region(factory, job, next_of[job])
        upgrade = [ln for ln in region.splitlines()
                   if ln.startswith("      - name: ")
                   and "dependency-upgrade" in ln]
        if job == "implement":
            assert len(upgrade) == 1, \
                "the implement job must carry exactly one " \
                "dependency-upgrade step"
        else:
            assert not upgrade, (
                f"the {job} job gained a dependency-upgrade step — the "
                "mechanism is an inlined step in the consuming job "
                "only; a step in another job would change the run's "
                "stages, pull request or final status report")


def test_upgrade_footprint_reaches_the_consuming_stages_intact():
    """(project-dependencies "The dependency upgrade does not break the
    project's current functionality"; reference
    `requirements/project-dependencies.feature::The dependency upgrade
    does not break the project's current functionality`) the upgrade's
    footprint reaches the run's consuming stages through the AI branch
    — the branch is the only documented cross-job workspace channel
    (chapter 7: each job's checkout replaces the workspace, so a change
    in one job's workspace reaches the next job only once it is
    committed to the branch): the implement job's upgrade step commits
    the footprint to the checked-out AI branch, and the job pushes the
    branch after the step; the review job's checkout of the same branch
    (the trigger-state relay) materialises the upgraded tree, where the
    review job's existing documented dependency-install step installs
    the upgraded set before the stage — the make test suite run (which
    executes every scenario) runs against a project whose functionality
    is intact."""
    factory = _read(FACTORY)
    impl = _job_region(factory, "implement", "review")
    step = _step_index(impl,
                       lambda ln: "name:" in ln
                       and "dependency-upgrade" in ln)
    assert step != -1, \
        "the implement job carries no dependency-upgrade step"
    block = _step_block(impl, step)
    # the footprint commits to the checked-out branch (the AI branch),
    # after the upgrade runs
    assert "git commit" in block, \
        "the upgrade step never commits the footprint — the consuming " \
        "stages could not see the upgraded project"
    assert block.index("bash -c") < block.index("git commit"), \
        "the upgrade step commits before the upgrade runs"
    # and the commit rides the branch work the job pushes — the
    # cross-job channel
    push = _step_index(impl, lambda ln: "Push the AI branch" in ln)
    assert push != -1, "the implement job lost its AI-branch push step"
    assert step < push, \
        "the implement job does not push the AI branch after the " \
        "upgrade step — the footprint would not leave the job"
    # the review job's checkout of the same branch materialises the
    # upgraded tree, and its documented dependency-install step then
    # installs the upgraded set before the stage's suite run
    review = _job_region(factory, "review", "pr")
    rcheckout = _step_index(review,
                            lambda ln: "- uses: actions/checkout" in ln)
    rinstall = _step_index(review,
                           lambda ln: "name:" in ln
                           and "dependency-install" in ln)
    rstage = _step_index(review,
                         lambda ln:
                         "Stage 10-11 — run the oracle, review, fix" in ln)
    assert rcheckout != -1, \
        "the review job lost its AI-branch checkout step"
    assert rinstall != -1, \
        "the review job lost its dependency-install step"
    assert rstage != -1, "the review job lost its stage step"
    assert rcheckout < rinstall < rstage, (
        "the review job's dependency-install step is not after the "
        "checkout and before the stage — the suite run would not work "
        "against the upgraded environment")
    assert "ref: ${{ steps.state.outputs.checkout-ref }}" in \
        _step_block(review, rcheckout), (
        "the review job's checkout does not take the AI branch from the "
        "trigger-state relay — the documented cross-job channel the "
        "upgrade's footprint rides")


# ── task 5: the documented surfaces state the same (issue 18) ────────


def test_readme_and_arc42_document_the_dependency_upgrade_stage():
    """(project-dependencies "The README and the arc42 documentation
    describe the dependency-upgrade stage"; reference
    `requirements/project-dependencies.feature::The README and the
    arc42 documentation describe the dependency-upgrade stage`) the
    documented surfaces (the README plus every arc42 chapter, the
    AI-activity section cut) state the mechanism on the same surfaces:
    the README's Inputs-table entry names the setting with its on
    default, the consumption example shows the setting in the with:
    block, and every surface that covers the mechanism states the
    stage, its default, the turn-off input, the before-implementation
    placement and the unchanged-when-off behaviour (a run with the
    setting off — the stages, the pull request and the final status
    report as if the mechanism were absent — the documented
    unchanged-by-the-mechanism's-presence property, the step's no-op)."""
    surfaces = _doc_surfaces()
    by_relpath = dict(surfaces)
    # the README's Inputs-table entry names the setting with its on
    # default — and how a target turns it off
    readme = by_relpath["README.md"]
    assert "| dependency-upgrade | on |" in readme, \
        "the README's Inputs table has no dependency-upgrade entry"
    # and the consumption example shows the setting in the with: block
    raw = _read("README.md")
    start = raw.index("## Consume it")
    end = raw.find("\n## ", start)
    example = raw[start:end] if end != -1 else raw[start:]
    assert "dependency-upgrade:" in example, \
        "the README's consumption example does not show the setting"
    # the arc42 chapters that cover the mechanism name the same setting
    covering = [p for p, t in surfaces if "dependency-upgrade" in t]
    for p in ("docs/04-context-and-scope.md",
              "docs/05-solution-strategy.md",
              "docs/06-building-block-view.md", "docs/07-runtime-view.md",
              "docs/08-deployment-view.md", "docs/11-glossary.md"):
        assert p in covering, \
            f"{p} no longer covers the dependency-upgrade mechanism"
    # the scenario's And step: the arc42 documentation covering the
    # same mechanism states the same — every surface that names the
    # setting also states the stage, its default, the turn-off input,
    # the before-implementation placement and the unchanged-when-off
    # behaviour
    for p, t in surfaces:
        if "dependency-upgrade" not in t:
            continue
        assert "upgrades the project's dependencies to newer versions" in t, (
            f"{p} covers the dependency-upgrade mechanism but does not "
            "state that the stage upgrades the project's dependencies "
            "to newer versions")
        assert "default is on" in t, (
            f"{p} covers the dependency-upgrade mechanism but does not "
            "state that the setting's default is on")
        assert "dependency-upgrade: off line in the with: block" in t, (
            f"{p} covers the dependency-upgrade mechanism but does not "
            "state how a target turns the setting off through its "
            "consumer workflow")
        assert "before the implementation stage" in t, (
            f"{p} covers the dependency-upgrade mechanism but does not "
            "state that the stage runs before the implementation stage")
        assert "unchanged by the upgrade's absence" in t, (
            f"{p} covers the dependency-upgrade mechanism but does not "
            "state that a run with the setting off is unchanged")


# ── task 6: the resolved pi call cap rides the record (issue 97) ─────


def test_resolved_pi_call_cap_rides_the_resolved_configuration_record():
    """(configuration "The resolved pi call cap rides the
    resolved-configuration record" and "The resolved job timeout rides
    the resolved-configuration record"; references
    `requirements/configuration.feature::The resolved pi call cap rides
    the resolved-configuration record`,
    `requirements/configuration.feature::The resolved job timeout rides
    the resolved-configuration record`) the trigger's
    resolved-configuration record — the workflow-log block its resolve
    step tees into the resolved-config file that rides the trigger's
    artifact — lists the run's resolved pi call cap with the rest of the
    resolved configuration: the declared value where a target declared
    one, the 21600 default where the input is undeclared (the input's
    declared default is the value an undeclared consumer resolves, so
    the record's line carries both branches — the value and the default
    it names); the record lists the run's resolved job timeout with the
    rest of the resolved configuration too — the declared value where a
    target declared one, the 480 default where the input is undeclared
    (the same both-branches shape); and the record stays in the workflow
    log and the run's artifacts, never committed to the repo — its
    heading says so, and the file it tees is the one the trigger's
    artifact uploads. The record carries no exceedance branch any more —
    with the validation moved to trigger time, a run whose declared cap
    leaves the stage's non-call work no headroom inside the job timeout
    fails before any stage runs, so the record's pi-cap line simply
    carries the resolved value."""
    factory = _read(FACTORY)
    block = _resolved_config_block(factory)
    # the pi call cap line: the declared-value branch — the record lists
    # the input's value
    assert "inputs.pi-timeout" in block, (
        "the trigger's resolved-config record does not list the "
        "resolved pi call cap from the pi-timeout input")
    # the default branch: an undeclared consumer's value is the input's
    # declared default — the line names it
    assert "21600" in block, (
        "the trigger's resolved-config record does not name the 21600 "
        "default a target that leaves the input undeclared keeps")
    # the job timeout line: the declared-value branch — the record lists
    # the input's value
    assert "inputs.job-timeout" in block, (
        "the trigger's resolved-config record does not list the "
        "resolved job timeout from the job-timeout input")
    # the default branch: an undeclared consumer's value is the input's
    # declared default — the line names it
    assert "480" in block, (
        "the trigger's resolved-config record does not name the 480 "
        "default a target that leaves the input undeclared keeps")
    # the record's location and never-committed property (its heading)
    assert "workflow log" in block, (
        "the resolved-config record's heading no longer states the "
        "workflow-log location")
    assert "never committed" in block, (
        "the resolved-config record's heading no longer states the "
        "never-committed property")
    # the file the group tees rides the trigger's artifact
    trig = _job_region(factory, "trigger", "setup-pi")
    assert "resolved-config.txt" in trig, (
        "the trigger no longer tees its resolved configuration into "
        "the file that rides the trigger's artifact")
