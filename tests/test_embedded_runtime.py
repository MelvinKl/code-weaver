"""Unit tests for how the published workflow file carries its runtime tree.

The reusable workflow is the file a target pins, and GitHub fetches
only that file at the called ref — the called ref is not visible to the
run's jobs. The old design answered that by relaying the ref as the
`factory-ref` input (a second pin beside the consumer's uses: line) and
cloning the factory repo at it at run time; a later rewrite answered it
by embedding the runtime tree in the file itself — a base64 tarball
behind the heredoc in stage 1's first step. The embed is retired: it
put a binary payload in a file that must be plain text, and the bloat
took the published file past its max allowed size. The current answer
lets the first job fetch the called version's tree: the called ref is
recovered from the consumer workflow (read over the GitHub API at the
run's base ref — a declared version tag resolves to the factory repo
fetched at that tag, a relative uses: to the triggering repo at its own
base ref), the fetch is an anonymous git clone of the public factory
repo that does not ride the target-scoped GH_TOKEN (the documented
contract scopes that token to the target repo, and it cannot read the
factory repo — the clone runs with no token and a cleared credential
helper, and a plain clone, unlike a checkout step, is admitted into the
runner's temp dir when the fetched repo differs from the triggered
one), and the tree lands in the runner's temp dir before the first
checkout replaces the workspace (the trigger's artifact then carries it
to every later stage job). No stage reads the `factory-ref` input
anymore (it stays declared as a legacy no-op so an older consumer's
`with:` block stays schema-valid), and the consumer relays nothing —
the uses: line is the only pin a run makes.

The pins:
- the file's payload region is gone (the embed is retired): the file
  holds no `CW_EMBEDDED_RUNTIME_TAR` heredoc, and stage 1's steps
  resolve the called ref and fetch the called version's tree into the
  stash;
- the committed tree the gate verifies carries the canonical runtime
  files the file's steps execute (a curation drift in the check's file
  set would leave a tree the stage steps cannot run from — the drift
  stays a failure, not silent);
- a run fetches the factory repo: the fetch is an owner-qualified
  `git clone` that rides a run-time-resolved ref (no ref literal
  anywhere in the file — the called ref is recovered, not declared),
  and no stage reads the `factory-ref` input (the declared legacy
  no-op).

Plain-stdlib by design (no third-party imports): the stage-10 driver
(`make test` → `python3 tests/run.py`) is a stdlib-only plain-python
contract per the Makefile. The gate script is loaded by file path (its
filename is import-safe, but the loader idiom follows
`tests/test_release_contract.py`'s `release-number.py` precedent, and a
target interpreter may not see the .github package layout).
No-argument `test_` functions — discovered automatically by both
runners (`tests/run.py` imports every `tests/test_*.py`; house CI's
"Validator unit tests" step runs `pytest tests/`), so no `Makefile`
`test` target or `tests/run.py` change is needed.
"""
from __future__ import annotations

import importlib.util
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")
FACTORY = os.path.join(".github", "workflows", "factory.yml")

# The shared-plumbing script the release flow's publication gate runs
# on the committed file and tree (--check). Load it by file path, the
# way the release-contract module loads `release-number.py`.
_spec = importlib.util.spec_from_file_location(
    "embed_runtime", os.path.join(ROOT, ".github", "scripts", "embed-runtime.py"))
embed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(embed)


def _read(relpath):
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


# The trigger job's fetch step (stage 1) — the one step whose name marks
# it as the fetch: stage 1 fetches the called version's tree at the
# called ref, while every later job's stash step is named for the
# restore (it downloads the trigger's artifact, it fetches nothing).
FETCH_STEP_MARKER = "- name: Stash the factory runtime tree (fetched at the called ref"


def _fetch_step_block(text):
    """The fetch step's block — from its list entry to the next step's
    entry at the same indent — or `None` where the file holds no such
    step."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().startswith(FETCH_STEP_MARKER):
            indent = len(ln) - len(ln.lstrip())
            block = [ln]
            for cont in lines[i + 1:]:
                if (cont.strip()
                        and (len(cont) - len(cont.lstrip())) <= indent
                        and cont.lstrip().startswith("- ")):
                    break
                block.append(cont)
            return "\n".join(block)
    return None


# The file's jobs in file order — the trigger plus the nine stage jobs
# that follow it (the header comment's "15 logical stages over 10
# jobs"). The per-job loop that reads them refuses to run on a key the
# file no longer holds: a job added without a cw-trigger download would
# otherwise slip past the pin.
JOB_KEYS = ("trigger", "setup-pi", "baseline", "extract", "plan",
            "implement", "review", "pr", "gates", "report")


def _job_block(text, job_key):
    """The lines of one job — from its two-indent `key:` line to the
    next job's two-indent key line (the `# ── stage N ──` separator
    comments between jobs ride the following job's block; a job's own
    keys all sit at four indent or deeper, so none of them ends its
    block)."""
    lines = text.splitlines()
    block, started = [], False
    for ln in lines:
        if started and re.match(r"^  [a-z][\w-]*:\s*$", ln):
            break
        if started or ln == f"  {job_key}:":
            block.append(ln)
            started = True
    return block


def _job_steps(job_lines):
    """The job's steps as line blocks — each from its six-indent `- ` entry
    to the next six-indent `- ` entry (or the steps list's end): a step's
    own lines all sit at six indent or deeper, while a line back to four
    indent or shallower ends the list."""
    steps, cur = [], None
    for ln in job_lines:
        if ln.startswith("      - "):
            if cur is not None:
                steps.append(cur)
            cur = [ln]
        elif cur is not None:
            if ln.strip() and len(ln) - len(ln.lstrip()) < 6:
                steps.append(cur)
                cur = None
            else:
                cur.append(ln)
    if cur is not None:
        steps.append(cur)
    return steps


def test_factory_file_carries_its_runtime_tree_embedded():
    """(reuse-by-ref "a published version is self-contained" — the
    scenario adjusted in place by the issue-100 delta; reference
    `requirements/reuse-by-ref.feature::A published version is
    self-contained`) the embed is retired: the file stores no binary
    content, so the payload region (the heredoc body of stage 1's first
    step) is gone from the file, and the stage-1 steps that replace it
    resolve the called ref — recovered from the consumer workflow read
    over the GitHub API at the run's base ref (GitHub fetched the file
    at the ref the consumer's uses: line declared, and the jobs are not
    told which ref that was) — and clone the called version's tree into
    the stash before the first checkout replaces the workspace: the
    ref's published version carries the file and the tree together, the
    file storing no binary payload — the shape the adjusted scenario's
    Given and Then state. The scenario is unchanged by the issue-104
    delta: what flips in place is the mechanism half these pins read —
    the fetch is the run-step clone the delta's new scenario forces,
    not the checkout-action step it retires."""
    text = _read(FACTORY)
    assert "CW_EMBEDDED_RUNTIME_TAR" not in text, (
        "the workflow file still holds the CW_EMBEDDED_RUNTIME_TAR "
        "heredoc — the payload region is gone: the embed is retired, and "
        "the file stores no binary content")
    # stage 1 resolves the called ref — from the consumer workflow,
    # read over the GitHub API at the run's base ref (no checkout has
    # happened yet, so nothing has replaced the workspace)
    assert "id: called-version" in text, (
        "stage 1 does not resolve the called version — the called ref is "
        "recovered from the consumer workflow, and the fetch rides the "
        "recovered value")
    assert re.search(r"gh api[^\n]*contents/\.github/workflows/", text), (
        "stage 1 does not read the consumer workflow over the GitHub API "
        "— the called ref is recovered from that file as committed at the "
        "run's base ref")
    # ...and clones the called version's tree into the stash — the
    # run-step form the issue-104 delta re-anchors these pins to (the
    # old checkout-action's ref:/path: action inputs disappear when the
    # step becomes a run step): the ref is expressed from the
    # run-time-resolved called-ref output, and the destination sits
    # under $RUNNER_TEMP/cw/stash (no ref literal anywhere in the file
    # — the called ref is recovered, not declared)
    fetch = _fetch_step_block(text)
    assert fetch is not None, (
        "stage 1 has no fetch step for the called version's tree — the "
        "step that stashes the tree the stage steps run from is gone")
    assert re.search(
        r"steps\.called-version\.outputs\.called-ref", fetch), (
        "the fetch does not ride the run-time-resolved ref — the called "
        "ref is recovered from the consumer workflow, and no ref literal "
        "may stand in the fetch's ref")
    assert "$RUNNER_TEMP/cw/stash" in fetch, (
        "stage 1 does not fetch the called version's tree into the stash "
        "($RUNNER_TEMP/cw/stash) before the first checkout replaces the "
        "workspace")

def test_embedded_tree_holds_the_canonical_runtime_files():
    """(the same scenario, made silent-safe; reference
    `requirements/reuse-by-ref.feature::A published version is
    self-contained`) the committed tree the gate verifies — the
    curated file set the check covers (the prefixes the first job's
    fetch materialises) — carries the canonical runtime files the
    file's steps execute: a curation drift in the check's file set
    (a prefix lost, an exclusion over-broad) would leave a tree the
    stage steps cannot run from — the drift stays a failure, not
    silent, and the missing file is named."""
    names = set(arcname for arcname, _ in embed.runtime_files(ROOT))
    for marker in (".github/scripts/common.py",
                   ".github/scripts/stages.py",
                   ".github/scripts/gherkin-validate.py",
                   ".github/scripts/release-number.py",
                   ".github/actions/setup-pi/stage.py",
                   ".github/actions/extract-stage/stage.py",
                   ".github/actions/plan-stage/stage.py",
                   ".github/actions/implement-stage/stage.py",
                   ".github/actions/review-stage/stage.py",
                   ".github/actions/gates-stage/stage.py",
                   ".github/actions/guard-check/guard-check.py",
                   "pi-prompts/requirements.md",
                   "pi-prompts/plan.md",
                   "pi-prompts/implement.md",
                   "pi-prompts/review.md",
                   "pi-prompts/pr-body.md"):
        assert marker in names, (
            f"the committed tree the gate verifies is missing {marker} "
            "— the curation changed under the stage code's "
            "__file__-relative resolution")


def test_no_run_fetches_the_factory_repo():
    """(reuse-by-ref "a published version is self-contained" — the
    single-pin property, its expectation inverted by the issue-100
    delta; reference
    `requirements/reuse-by-ref.feature::A published version is
    self-contained`) the fetch returns: a run now DOES fetch the
    factory repo, owner-qualified, as its fetch source — the called
    ref selects a published version, the tag's commit carries the file
    and the runtime tree together, and stage 1 fetches that tree. The
    scenario's content stays true after the issue-104 delta flipped
    the fetch's mechanism in place — one ref selects the whole
    version, and the file stores no binary payload; what flips is the
    mechanism half, named as forced by the delta's new scenario (a
    different-repo checkout into a path outside the job's workspace is
    the form the checkout action refuses): the fetch is a `git clone`
    run step whose source URL derives from the run-time-resolved
    `called-repo` output and whose ref rides the run-time-resolved
    `called-ref` output (no repo or ref literal in the fetch — the
    recovery step resolves both values at run time), and no stage
    reads the `factory-ref` input (the input stays a declared legacy
    no-op)."""
    text = _read(FACTORY)
    # the fetch's form after the issue-104 flip: a run step that
    # git-clones — the checkout-action form is the one that refused
    # the different-repo shape the delta's new scenario pins
    assert "git clone" in text, (
        "factory.yml no longer git-clones at run time — the fetch is a "
        "plain run step that clones the called repo at the called ref "
        "into the stash (the form that works on a target repo different "
        "from the factory's own repo)")
    # the inversion: the run now fetches the factory repo,
    # owner-qualified, as the fetch source (the recovery step's
    # comment names the owner/repo the owner-qualified uses: line it
    # parses)
    assert "MelvinKl/code-weaver" in text, (
        "factory.yml no longer names the owner-qualified factory repo — "
        "a run fetches it: stage 1's fetch is the clone of the factory "
        "repo at the called ref")
    # the fetch is a run step whose source derives from the
    # run-time-resolved called-repo output and whose ref rides the
    # run-time-resolved called-ref output — no repo or ref literal in
    # the fetch (the recovery step resolves both values)
    fetch = _fetch_step_block(text)
    assert fetch is not None, (
        "factory.yml has no fetch step for the called version's tree — "
        "the step that clones the called repo at the called ref into "
        "the stash is gone")
    assert re.search(
        r"CALLER_REPO=\"\$\{\{\s*steps\.called-version\.outputs\.called-repo\s*\}\}\"",
        fetch), (
        "the fetch's source does not derive from the run-time-resolved "
        "repo — the called version's source is recovered from the "
        "consumer workflow, and no literal repo may stand in the "
        "fetch's source")
    assert re.search(
        r"CALLER_REF=\"\$\{\{\s*steps\.called-version\.outputs\.called-ref\s*\}\}\"",
        fetch), (
        "the fetch's ref is not expressed from the run-time-resolved "
        "ref — the called ref is recovered from the consumer workflow "
        "at run time, and no ref literal may stand in the fetch's "
        "ref")
    # and the clone's URL is built from the shell value — no literal
    # repo in the fetch's source
    assert not re.search(
        r"clone[^\n]*https?://github\.com/[\w.-]+/[\w.-]+", fetch), (
        "the fetch's clone names a literal repo in its URL — the called "
        "repo is recovered from the consumer workflow at run time, and "
        "no literal repo may stand in the fetch's source")
    # no stage reads the factory-ref input (the input stays a declared
    # legacy no-op)
    assert "inputs.factory-ref" not in text, (
        "a stage still reads the factory-ref input — the consumer's "
        "uses: line is the only pin a run makes; the input is a declared "
        "legacy no-op")

def test_runtime_tree_fetch_succeeds_on_a_different_target_repo():
    """(reuse-by-ref "the runtime tree fetch succeeds on a target repo
    different from the factory's own repo" — added by the issue-104
    delta; reference
    `requirements/reuse-by-ref.feature::The runtime tree fetch succeeds
    on a target repo different from the factory's own repo`) a factory
    run on a target repo that is different from the factory's own repo:
    the first job fetches the called version's runtime tree from the
    factory repo at the called ref into the runner's temp dir, the
    fetch completes without failing, and the materialised runtime tree
    is the called version's — the tree of the ref the consumer's
    uses: line selects. The crash the scenario pins: the fetch was a
    checkout-action step, and the checkout action refuses a
    different-repo checkout into a path outside the job's workspace
    ("Repository path ... is not under ..."), so on any target repo
    different from the factory's own repo the step died with an empty
    stash. The pins: no actions/checkout step in the file combines a
    (runtime-resolved, potentially different) repository: input with a
    path: outside the job's workspace — the combination the action
    refuses; and the fetch is a run step that clones the called repo
    at the called ref into $RUNNER_TEMP/cw/stash — its source deriving
    from the run-time-resolved called-repo output (never the triggered
    (target) repo, and no repo or ref literal standing in for either —
    the recovery step decides both values)."""
    text = _read(FACTORY)
    lines = text.splitlines()
    # no actions/checkout step in the file combines a (runtime-
    # resolved, potentially different) repository: input with a path:
    # outside the job's workspace — that combination is what the
    # checkout action refuses ("Repository path ... is not under
    # ..."), and it is what the scenario's "the fetch completes
    # without failing" rules out for the different-repo shape
    for i, ln in enumerate(lines):
        if "uses: actions/checkout" not in ln:
            continue
        block = "\n".join(lines[i:i + 12])
        repo = re.search(r"^\s*repository:\s*(\S+)", block, re.M)
        path = re.search(r"^\s*path:\s*(\S+)", block, re.M)
        assert not (repo is not None and path is not None
                    and "github.workspace" not in path.group(1)), (
            f"an actions/checkout step combines a repository: input "
            f"({repo.group(1)!r}) with a path: outside the job's "
            f"workspace ({path.group(1)!r}) — the checkout action "
            "refuses that combination when the checked-out repo "
            "differs from the triggered one ('Repository path ... is "
            "not under ...'), and a factory run on a target repo "
            "different from the factory's own repo would die in its "
            "first job")
    # the fetch is a run step — the different-repo shape the scenario
    # pins is the one a checkout-action step refuses, and a plain
    # clone is what works on it
    fetch = _fetch_step_block(text)
    assert fetch is not None, (
        "factory.yml has no fetch step for the called version's runtime "
        "tree — the first job of a run on a target repo different from "
        "the factory's own repo would have no runtime tree at all")
    assert "run:" in fetch, (
        "the fetch is not a run step — the different-repo shape the "
        "scenario pins is the one a checkout-action step refuses, and "
        "the fetch must be the plain clone that works on it")
    # the source derives from the run-time-resolved called-repo output —
    # on a target repo different from the factory's own repo the called
    # repo is the factory repo, never the triggered (target) repo, and
    # no repo or ref literal stands in the fetch
    assert "steps.called-version.outputs.called-repo" in fetch, (
        "the fetch's source does not derive from the run-time-resolved "
        "called-repo — on a target repo different from the factory's own "
        "repo the fetch source is the factory repo the consumer's uses: "
        "line selects, not the triggered repo")
    assert "GITHUB_REPOSITORY" not in fetch, (
        "the fetch's source is the triggered (target) repo — on a "
        "target repo different from the factory's own repo the called "
        "repo is the factory repo, and the fetch must clone the called "
        "repo, not the run's own repository")
    assert "steps.called-version.outputs.called-ref" in fetch, (
        "the fetch's ref is not expressed from the run-time-resolved "
        "called-ref — the materialised tree must be the called "
        "version's, the tree of the ref the consumer's uses: line "
        "selects")
    # no repo or ref literal in the fetch — the clone's source and the
    # ref it fetches are shell values the step's own expressions feed
    assert not re.search(
        r"clone[^\n]*https?://github\.com/[\w.-]+/[\w.-]+", fetch), (
        "the fetch's clone names a literal repo in its URL — the called "
        "repo is recovered from the consumer workflow at run time, and "
        "no literal repo may stand in the fetch's source")
    # the destination is under the runner's temp dir, outside the
    # workspace every later checkout replaces — the boundary the stash
    # must sit at
    assert "$RUNNER_TEMP/cw/stash" in fetch, (
        "the fetch does not materialise the called version's tree under "
        "$RUNNER_TEMP/cw/stash — the stash must sit in the runner's temp "
        "dir, the one place every later checkout leaves alone")

def test_trigger_artifact_carries_the_stashed_tree_to_every_stage_job():
    """(reuse-by-ref "the trigger's artifact carries the stashed runtime
    tree to every stage job" — added by the issue-104 delta; reference
    `requirements/reuse-by-ref.feature::The trigger's artifact carries
    the stashed runtime tree to every stage job`) a factory run on a
    target repo that is different from the factory's own repo, whose
    first job materialised the called version's runtime tree into the
    runner's temp dir: when the trigger job uploads its state artifact,
    the artifact contains the stashed runtime tree — including the
    hidden directory the stage scripts live under — every later stage
    job restores the tree from the trigger's artifact before its first
    checkout, and no stage job of the run dies on a missing stashed
    runtime file. The chain the pins verify end to end: the trigger's
    cw-trigger upload (the runner's temp cw dir — the stashed tree
    sits under it — running always() and opting into hidden files,
    which keeps the tree's .github/ half on the artifact, the part the
    artifact API would otherwise drop), every later job's first step
    (the cw-trigger download into the same dir, ahead of the job's
    first checkout — the one that replaces the workspace, and only the
    runner's temp dir survives it), and each stage step that runs a
    script from the stashed tree (the guard that fails precisely on a
    missing stashed file — the named file, an explicit ::error:: and
    exit 1, not an opaque crash). With the fetch (the delta's other
    new scenario) succeeding and the upload carrying the tree, no file
    is missing, so no stage job of the run dies on a missing stashed
    runtime file."""
    text = _read(FACTORY)
    lines = text.splitlines()
    # the job key list is the file's own job set — a job added without
    # a cw-trigger download would otherwise slip past the per-job loop
    file_jobs = re.findall(r"(?m)^  ([a-z][\w-]*):\s*$",
                           text.split("jobs:", 1)[1])
    assert file_jobs == list(JOB_KEYS), (
        f"the file's jobs {file_jobs!r} are no longer the trigger plus "
        f"the nine stage jobs {list(JOB_KEYS[1:])!r} — the per-job loop "
        "that pins every later stage job's first step would miss a job "
        "the file gained (or read one it lost)")
    # the trigger's upload step carries the stashed tree — including
    # the hidden .github/ part the stage scripts live under
    uploads = [s for s in _job_steps(_job_block(text, "trigger"))
               if "uses: actions/upload-artifact" in s[0]]
    assert len(uploads) == 1, (
        "the trigger job holds no (or more than one) upload-artifact "
        "step — the cw-trigger upload is the half of the chain that "
        "carries the stashed tree to every later stage job")
    up = "\n".join(uploads[0])
    assert "name: cw-trigger" in up, (
        "the trigger's upload is not named cw-trigger — every later "
        "stage job restores the tree from the artifact by that name")
    assert "if: always()" in up, (
        "the trigger's upload does not run always() — a trigger that "
        "fails after the fetch would skip the upload, and every later "
        "stage job would arrive with its stashed runtime tree missing")
    path = re.search(r"^\s*path:\s*(.+?)\s*$", up, re.M)
    assert path and path.group(1) == "${{ runner.temp }}/cw", (
        "the trigger's upload does not upload the runner's temp cw "
        "dir — the stashed tree the first job fetched sits under it")
    assert "include-hidden-files: true" in up, (
        "the trigger's upload does not opt into hidden files — the "
        "stashed tree lives under the hidden .github/ directory (the "
        "stage scripts resolve their scripts from there), and "
        "upload-artifact drops hidden files by default: without the "
        "opt-in the artifact carries the tree with its .github/ half "
        "missing, and every stage job arrives with its stashed stage "
        "script missing")
    # and the upload's path actually covers the stash: both spellings
    # of the runner's temp dir normalise to the same dir, and the
    # fetch's destination sits under the uploaded path
    canon = (lambda s: s.replace("${{ runner.temp }}", "")
                   .replace("$RUNNER_TEMP", ""))
    assert canon("$RUNNER_TEMP/cw/stash").startswith(
        canon(path.group(1)) + "/"), (
        "the trigger's upload path does not cover the stash — the "
        "fetched runtime tree would not ride the artifact")
    # every later stage job's first step restores the tree from the
    # trigger's artifact before the job's first checkout
    for job in JOB_KEYS[1:]:
        steps = _job_steps(_job_block(text, job))
        assert steps, f"the {job} job has no steps to pin"
        first = "\n".join(steps[0])
        assert "uses: actions/download-artifact" in first and \
            "name: cw-trigger" in first, (
            f"the {job} job's first step does not download the "
            "trigger's cw-trigger artifact — every later stage job "
            "restores the stashed runtime tree from it before its "
            "first checkout")
        assert "path: ${{ runner.temp }}/cw" in first, (
            f"the {job} job's first step does not restore the tree "
            "into the runner's temp cw dir — the download must land "
            "the tree back at the same repo-relative layout the fetch "
            "left it")
        first_checkout = next(
            (i for i, s in enumerate(steps)
             if "uses: actions/checkout" in s[0]), None)
        assert first_checkout is not None and first_checkout > 0, (
            f"the {job} job's first checkout does not follow its "
            "first step — the restore must precede the first checkout "
            "that replaces the workspace (only the runner's temp dir "
            "survives it)")
    # each stage step that runs a script from the stashed tree guards a
    # missing stashed runtime file with a precise failure that names
    # the file — an explicit ::error:: and exit 1, not an opaque crash
    entries = [i for i, ln in enumerate(lines)
               if re.match(r'\s*S="\$RUNNER_TEMP/cw/stash/', ln)]
    assert entries, (
        "no stage step runs a script from the stashed runtime tree — "
        "the stage jobs would have nothing that dies on a missing "
        "stashed runtime file, and the scenario's guard half pins "
        "nothing")
    for i in entries:
        guard = lines[i + 1] if i + 1 < len(lines) else ""
        assert re.search(r'\[ -f "\$S" \] \|\|', guard), (
            f"the stage step that runs {lines[i].strip()} does not "
            "guard a missing stashed script — a missing file would "
            "surface as an opaque crash, not a precise failure")
        assert "::error::" in guard and "$S" in guard and "exit 1" in guard, (
            f"the guard on the stashed script {lines[i].strip()} does "
            "not fail precisely — it must name the missing file (an "
            "explicit ::error:: carrying $S) and exit 1")

def test_no_stage_reads_the_factory_ref_input():
    """(the input the double pin relayed; reference
    `requirements/reuse-by-ref.feature::The whole version is one ref`)
    no step expression in the
    file reads `inputs.factory-ref` anymore — the input stays declared
    (a legacy no-op, so an older consumer's with: block stays
    schema-valid), but the runtime tree is the file's own: reading the
    input would put a second version selection back into the run."""
    text = _read(FACTORY)
    assert "factory-ref:" in text, (
        "the factory-ref input declaration is gone — an older consumer "
        "with: block that passes it must stay schema-valid")
    assert "inputs.factory-ref" not in text, (
        "a stage still reads the factory-ref input — the consumer's "
        "uses: line is the only pin a run makes; the input is a legacy "
        "no-op")
    # and the declared entry is the deprecated no-op (not the old
    # "the stage jobs clone their runtime tree from" contract)
    assert re.search(
        r'(?m)^\s*description:\s*[\"\']?\(legacy\).*no stage reads it', text), (
        "the factory-ref input's declaration no longer marks it as the "
        "legacy no-op")

def test_factory_file_stays_within_the_max_allowed_size():
    """(reuse-by-ref "the factory workflow file stays within the max
    allowed size" — the issue-100 delta's added scenario; reference
    `requirements/reuse-by-ref.feature::The factory workflow file stays
    within the max allowed size`) the measured size of
    `.github/workflows/factory.yml` is at most 500kb — the max allowed
    size for the file: the base64-tarball embed that the issue retires is
    what took the published file past it (528kb when the issue was
    filed). The check reads the figure conservatively, as 500,000 bytes
    (decimal): a file at most that is also under 500×1024, so the pin
    holds under either reading of `kb`. The cap is a checked property of
    the published file — this pins the committed file against it."""
    size = os.path.getsize(os.path.join(ROOT, FACTORY))
    assert size <= 500000, (
        f"the factory workflow file is {size} bytes — past its max "
        f"allowed size (at most 500kb, read conservatively as 500,000 "
        f"bytes)")

def test_factory_file_stores_no_binary_content():
    """(reuse-by-ref "the factory workflow file stores no binary
    content" — the issue-100 delta's added scenario; reference
    `requirements/reuse-by-ref.feature::The factory workflow file stores
    no binary content`) the file is plain text — it decodes, and no NUL
    byte stands anywhere in it — and the runtime tree its steps execute
    is not embedded in the file as a base64 tarball: the retired payload
    was the tarball's base64 across a `CW_EMBEDDED_RUNTIME_TAR` heredoc
    in stage 1's first step (a 76-column wrap — 68 base64 characters a
    line, the heredoc's body the step fed `base64 -d`), and neither the
    heredoc region nor a line of that base64-blob form remains in the
    file (its surviving `base64 -d` is the consumer workflow's
    API-content decode — a short line, a different purpose)."""
    with open(os.path.join(ROOT, FACTORY), "rb") as f:
        data = f.read()
    assert b"\x00" not in data, (
        "the workflow file holds a NUL byte — it stores binary content, "
        "and a workflow file must be plain text")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise AssertionError(
            "the workflow file does not decode as text — it stores "
            f"binary content ({e})") from None
    assert "CW_EMBEDDED_RUNTIME_TAR" not in text, (
        "the workflow file still opens the CW_EMBEDDED_RUNTIME_TAR "
        "heredoc — the retired payload region is back in the file")
    for ln in text.splitlines():
        body = ln.strip()
        if body and re.fullmatch(r"[A-Za-z0-9+/]{64,}={0,2}", body):
            raise AssertionError(
                "the workflow file holds a base64 blob line — the "
                "retired embed's form (the runtime tree's base64 across "
                f"the heredoc's wrapped lines): {body[:40]!r}…")

def _run_block_fixture(terminator_indent=None, *, close=True,
                       dashed=False, terminator_extra=""):
    """A minimal workflow the structure scan reads: one job, one step,
    a run block (base indent 10) whose heredoc's one body line sits at
    the block's base, its terminator at `terminator_indent` (ten — the
    block's base — where unspecified) with `terminator_extra` between
    the base and the word (a `<<-` dash strips leading tabs from the
    terminator, so a tab there is still a terminator; a space is not),
    or absent where `close` is false (the block opens the heredoc it
    never terminates)."""
    opener = "cat > f <<-'EOF'" if dashed else "cat > f <<EOF"
    lines = [
        "name: t",
        "on: push",
        "jobs:",
        "  trigger:",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - name: resolve",
        "        run: |",
        "          " + opener,
        "          body line",
    ]
    if close:
        lines.append(" " * (terminator_indent
                            if terminator_indent is not None else 10)
                     + terminator_extra + "EOF")
    lines.append("          echo done")
    return "\n".join(lines)


def test_committed_factory_file_holds_no_heredoc_terminator_past_its_block_base():
    """(scenario "A workflow file whose heredoc terminator indents past
    the run block's base publishes no version" — the file the gate
    guards; reference
    `requirements/auto-release-on-main.feature::A workflow file whose
    heredoc terminator indents past the run block's base publishes no
    version`) the committed factory.yml's run blocks: every heredoc
    terminator sits at its block's base indent (the runner's dedent
    leaves it at column 0 in the executed script — indented past the
    base, the terminator would not be a terminator: bash would read
    the rest of the step's script as the heredoc's body and the step
    would die at run time — the trigger step's failure in runs
    #151/#152: its issue-meta heredoc's terminator, and the pr job's
    two `python3 -` heredocs' terminators, all sat four deeper than
    their blocks' base in the published file, while the structure
    gate's other shapes — the engine parse, the keys-after-run check,
    the line budget — all held, so the version published and every run
    since died at trigger)."""
    text = _read(FACTORY)
    violations = embed.heredoc_terminator_violations(text)
    assert not violations, (
        "the committed factory.yml leaves heredoc terminator(s) off "
        "column 0 in the executed script: "
        + "; ".join(violations))


def test_a_heredoc_terminator_indented_past_its_block_base_is_a_structure_violation():
    """(the same scenario — the gate's check itself; reference
    `requirements/auto-release-on-main.feature::A workflow file whose
    heredoc terminator indents past the run block's base publishes no
    version`) a run block whose heredoc terminator sits four deeper
    than the block's base: the dedent strips the base, leaves the
    terminator four into column 0 — not a terminator there — and the
    structure gate fails the file with the exact cause (the step, the
    line, the terminator, the base): the version the tag would point
    at is not published, and a target pin never lands on a file whose
    step script bash reads to end of file."""
    fixture = _run_block_fixture(terminator_indent=14)
    violations = embed.heredoc_terminator_violations(fixture)
    assert len(violations) == 1, f"{violations!r}"
    v = violations[0]
    assert "resolve" in v and "'EOF'" in v, v
    assert "indented 14" in v and "base is 10" in v, v
    # the full structure gate carries the same verdict (the publish's
    # pre-tag gate reads it)
    ok, message = embed.verify_structure(
        fixture, expected_jobs=("trigger",),
        expected_step_counts={"trigger": 1})
    assert not ok
    assert "terminator" in message, message


def test_a_heredoc_terminator_at_its_block_base_is_not_a_structure_violation():
    """(the same scenario — the fixed shape; reference
    `requirements/auto-release-on-main.feature::A workflow file whose
    heredoc terminator indents past the run block's base publishes no
    version`) a run block whose heredoc terminator sits at the block's
    base: the dedent strips the base, leaves it at column 0 in the
    executed script — a terminator there — and the gate's check
    passes it."""
    fixture = _run_block_fixture()
    assert embed.heredoc_terminator_violations(fixture) == []
    ok, message = embed.verify_structure(
        fixture, expected_jobs=("trigger",),
        expected_step_counts={"trigger": 1})
    # the engine half's verdict is environment-dependent (a
    # stdlib-only test driver's interpreter may import no YAML
    # engine) — the shape this check pins is the heredoc half: no
    # violation of it (the failure form names the terminator and its
    # indent — neither marker appears in the verdict)
    assert "is not parser-safe" not in message, message
    assert "'EOF' is indented" not in message, message


def test_a_dashed_heredoc_terminator_indented_with_a_space_is_a_structure_violation():
    """(the same scenario — the `<<-` form's one legal exception;
    reference
    `requirements/auto-release-on-main.feature::A workflow file whose
    heredoc terminator indents past the run block's base publishes no
    version`) a `<<-DELIM` opener strips the terminator's leading tabs
    — a terminator whose extra indent past the base is a tab (only)
    still terminates; one that carries a space does not, and the gate
    fails it."""
    assert embed.heredoc_terminator_violations(
        _run_block_fixture(dashed=True, terminator_extra="\t")) == []
    violations = embed.heredoc_terminator_violations(
        _run_block_fixture(dashed=True, terminator_extra=" "))
    assert violations, (
        "the space-indented <<-'EOF' terminator is not reported — the "
        "dash strips leading tabs, never a space")
    v = violations[0]
    assert "'EOF'" in v and "indented 11" in v and "base is 10" in v, v


def test_a_heredoc_opened_but_never_terminated_in_its_block_is_a_structure_violation():
    """(the same scenario — the check's other half; reference
    `requirements/auto-release-on-main.feature::A workflow file whose
    heredoc terminator indents past the run block's base publishes no
    version`) a run block that opens a heredoc whose terminator line
    never comes: the executed script ends mid-heredoc (bash's
    "here-document delimited by end-of-file") — the same run-time
    death, and the gate names the opener's line."""
    fixture = _run_block_fixture(close=False)
    violations = embed.heredoc_terminator_violations(fixture)
    assert len(violations) == 1, f"{violations!r}"
    assert "never terminated" in violations[0], violations[0]
