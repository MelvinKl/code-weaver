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
    `requirements/labeled-only-trigger.feature::The README example and the repo's own deployed workflow declare
    the same labeled-only trigger`) the
    README's consumption example declares `issues.types` as exactly
    `[labeled]` — no `opened`, no `edited`."""
    types = _readme_example_types()
    assert types == ["labeled"], f"README example declares {types!r}"
    assert "opened" not in types and "edited" not in types


def test_deployed_consumer_workflow_declares_labeled_only():
    """(scenario "The repo's own deployed workflow uses a labeled-only
    trigger"; reference
    `requirements/labeled-only-trigger.feature::The README example and the repo's own deployed workflow declare
    the same labeled-only trigger`) the consumer workflow this repo
    deploys on itself declares
    `on.issues.types` as exactly `[labeled]` — no `opened`, no `edited`."""
    types = _types_list(_read(".github/workflows/code-weaver.yml"))
    assert types == ["labeled"], f"deployed workflow declares {types!r}"


def test_readme_example_and_deployed_workflow_agree():
    """(scenario "The documented example and the deployed workflow agree on
    the trigger"; reference
    `requirements/labeled-only-trigger.feature::The README example and the repo's own deployed workflow declare
    the same labeled-only trigger`) both extractions
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
    `requirements/labeled-only-trigger.feature::An issue opened or edited without a label addition does not
    start a factory run`,
    `requirements/labeled-only-trigger.feature::An issue opened or edited without a label addition does not
    start a factory run`,
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
    `requirements/trigger.feature::Editing an issue to add the label starts
    the factory`,
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


def _trigger_region():
    """The trigger job's region of the workflow file — from its
    2-indent job key line to the next job's — the unit the
    trigger-region idiom asserts on."""
    text = _read(".github/workflows/factory.yml")
    start = text.index("  trigger:")
    end = text.index("  setup-pi:")
    return text[start:end]


def _resolve_step():
    """The trigger's resolve step — the step the run's configuration
    validation, the resolved-configuration record and the acceptance
    (`started=true`, the state files) all live in — from its list entry
    to the next step's."""
    region = _trigger_region()
    start = region.index("      - id: resolve")
    end = region.find("      - uses:", start)
    return region[start:end if end == -1 else end]


def _stage_jobs_gate_on_the_trigger():
    """The "no stage runs after the trigger" half, asserted on the
    workflow file: every one of the nine stage jobs lists the trigger
    — directly or through its predecessor — in its `needs:` chain and
    gates its run on the trigger's `started` output, so a failed trigger
    leaves `started` false and every stage job skips."""
    text = _read(".github/workflows/factory.yml")
    lines = text.splitlines()
    job_keys = ("setup-pi", "baseline", "extract", "plan", "implement",
                "review", "pr", "gates", "report")
    starts = [i for i, ln in enumerate(lines)
              if ln.startswith("  ") and not ln.startswith("   ")
              and ln.strip() in {k + ":" for k in job_keys}]
    assert len(starts) == len(job_keys), \
        (f"the factory's nine stage jobs are not all found in the "
         f"workflow file: {len(starts)}")
    for a, b in zip(starts, starts[1:] + [len(lines)]):
        name = lines[a].strip()[:-1]
        section = "\n".join(lines[a:b])
        assert "needs:" in section, \
            f"the {name} job declares no needs: chain"
        assert "needs.trigger.outputs.started" in section, \
            (f"the {name} job does not gate its run on the trigger's "
             f"started output — a failed trigger would not skip it")


def test_non_numeric_job_timeout_fails_the_run_at_trigger():
    """(configuration "A non-numeric job timeout fails the run at
    trigger"; reference
    `requirements/configuration.feature::A declared timeout that fails the trigger's validation ends the
    run before any stage runs`) the trigger validates the run's
    configuration before it records or accepts the run: a declared
    job-timeout value that is not a number of minutes fails the trigger
    with a precise error naming the offending value — the validation
    block resolves the input's value (the declared value, or the
    input's default where the consumer leaves the input undeclared)
    and checks it is a number of minutes, exiting the step non-zero
    before the run is accepted (the step's first line wrote
    started=false, and the acceptance writes started=true later — the
    validation sits between them) — and the stage jobs gate on the
    trigger's started output, so a failed trigger skips every stage:
    no stage runs after the trigger."""
    step = _resolve_step()
    # the block resolves the declared job-timeout value
    assert 'JOB_TIMEOUT="${{ inputs.job-timeout }}"' in step, \
        ("the trigger's validation block does not resolve the declared "
         "job-timeout input's value")
    # and checks it is a number of minutes
    check = '[[ "$JOB_TIMEOUT" =~ ^[0-9]+$ ]]'
    assert check in step, \
        ("the trigger's validation block does not check the declared "
         "job-timeout for a number of minutes")
    # a value that is not a number of minutes fails the trigger with a
    # precise error naming the offending value, before any stage work
    fail = "job-timeout '${JOB_TIMEOUT}' is not a number of minutes"
    assert fail in step, \
        ("the trigger's validation does not fail with a precise error "
         "naming the offending job-timeout value")
    assert "exit 1" in step, \
        "a non-numeric job timeout does not fail the trigger step"
    assert step.index(check) < step.index('echo "started=true"'), \
        ("the job-timeout validation does not run before the trigger "
         "accepts the run — a failed trigger would not keep the stages "
         "skipped")
    _stage_jobs_gate_on_the_trigger()


def test_job_timeout_with_no_headroom_fails_the_run_at_trigger():
    """(configuration "A job timeout with no headroom over the resolved
    pi call cap fails the run at trigger"; reference
    `requirements/configuration.feature::A declared timeout that fails the trigger's validation ends the
    run before any stage runs`) the
    trigger validates the run's configuration before it records or
    accepts the run: where the declared job timeout does not exceed the
    resolved pi call cap — the target's declared pi-timeout value, or
    the 21600 default where undeclared — by at least the headroom the
    stage's own non-call work needs around each call, the block compares
    the resolved job timeout against the resolved pi cap plus the
    headroom and fails the trigger on a shortfall with a precise error
    naming both resolved values and the headroom — and the stage jobs
    gate on the trigger's started output, so a failed trigger skips
    every stage: no stage runs after the trigger. The default pair
    passes at exactly the margin: the comparison is inclusive, and the
    factory's own defaults (the 28800-second job timeout, the
    21600-second cap) leave precisely the 7200-second headroom, so a
    consumer that declares nothing validates and its run is
    unchanged."""
    step = _resolve_step()
    # the headroom the stage's own non-call work needs around each call
    # — named and fixed, derived from the two documented input defaults
    assert "HEADROOM_SECONDS=7200" in step, \
        ("the trigger's validation block does not name the headroom "
         "the stage's own non-call work needs around each call")
    assert "28800 s minus 21600 s = 7200 s" in step, \
        ("the trigger's validation block does not derive the headroom "
         "from the two documented input defaults (the 480-minute "
         "default job timeout minus the 21600-second default pi call "
         "cap)")
    # the resolved pi call cap — the target's declared pi-timeout value,
    # or the 21600 default where undeclared
    assert 'PI_CAP="${{ inputs.pi-timeout }}"' in step, \
        ("the trigger's validation block does not resolve the declared "
         "pi-timeout input's value as the run's pi call cap")
    # the comparison: the resolved job timeout must exceed the resolved
    # pi cap plus the headroom — the block fails the trigger on a
    # shortfall, and the comparison is inclusive, so the default pair
    # (28800 s against 21600 s plus the 7200 s headroom) passes at
    # exactly the margin
    compare = ('[ "$JOB_TIMEOUT_SECONDS" -ge '
               '$(( PI_CAP + HEADROOM_SECONDS )) ]')
    assert compare in step, \
        ("the trigger's validation block does not compare the resolved "
         "job timeout against the resolved pi cap plus the headroom")
    # a shortfall fails the trigger with a precise error naming both
    # resolved values and the headroom, before the run is accepted
    fail = ("does not exceed the resolved pi call cap (${PI_CAP} s) "
            "by at least the ${HEADROOM_SECONDS}-second headroom")
    assert fail in step, \
        ("the trigger's validation does not fail with a precise error "
         "naming both resolved values and the headroom")
    assert "exit 1" in step, \
        "a job timeout with no headroom over the resolved pi call cap " \
        "does not fail the trigger step"
    assert step.index(compare) < step.index('echo "started=true"'), \
        ("the headroom validation does not run before the trigger "
         "accepts the run — a failed trigger would not keep the stages "
         "skipped")
    _stage_jobs_gate_on_the_trigger()


def test_declared_pi_call_cap_the_job_timeout_cannot_exceed_fails_the_run_at_trigger():
    """(configuration "A declared pi call cap the job timeout cannot
    exceed fails the run at trigger"; reference
    `requirements/configuration.feature::A declared timeout that fails the trigger's validation ends the
    run before any stage runs`) the declared-cap
    view of the trigger's configuration validation, the same comparison
    its job-timeout half makes — the run's job timeout is the target's
    declared job-timeout value, or its "480" default where the consumer
    leaves the input undeclared, and where the target declares a pi call
    cap longer than the job timeout minus the headroom the stage's
    non-call work needs, the trigger fails the run at trigger time with
    a precise error (one trigger-side validation discharges both views
    of the same inequality) — and the stage jobs gate on the trigger's
    started output, so no stage runs after the trigger."""
    factory = _read(".github/workflows/factory.yml")
    # the run's job timeout — the target's declared job-timeout value,
    # or its "480" default (the input's declared default)
    assert 'default: "480"' in factory, \
        "the job-timeout input does not declare its 480 default"
    step = _resolve_step()
    assert 'JOB_TIMEOUT="${{ inputs.job-timeout }}"' in step, \
        ("the trigger's validation block does not resolve the run's job "
         "timeout from the declared job-timeout input")
    # the cap-side view of the same comparison: a declared pi call cap
    # longer than the job timeout minus the headroom fails the run
    assert "longer than the job timeout minus the headroom" in step, \
        ("the trigger's validation block does not carry the declared-"
         "cap view — a cap longer than the job timeout minus the "
         "headroom — of the same comparison")
    # the comparison: a declared cap passes only at or under the job
    # timeout minus the headroom — beyond it, the trigger fails before
    # the run is accepted
    compare = ('[ "$JOB_TIMEOUT_SECONDS" -ge '
               '$(( PI_CAP + HEADROOM_SECONDS )) ]')
    assert compare in step, \
        ("the trigger's validation does not compare the declared pi "
         "call cap against the job timeout minus the headroom")
    assert "exit 1" in step, \
        ("a declared pi call cap the job timeout cannot exceed does not "
         "fail the trigger step")
    assert step.index(compare) < step.index('echo "started=true"'), \
        ("the cap-side validation does not run before the trigger "
         "accepts the run — a failed trigger would not keep the stages "
         "skipped")
    _stage_jobs_gate_on_the_trigger()

def test_trigger_records_the_bug_issue_flag():
    """(scenario "The trigger records whether the issue carries the bug
    label"; reference
    `requirements/trigger.feature::The trigger records whether the issue
    carries the bug label`) when the trigger stage records a run for an
    issue that carries both the trigger label and the bug label, the
    run's recorded state carries that the issue is a bug issue: the
    trigger derives the flag against the resolved bug label (the
    bug-label input's value — the target's declared value, its "bug"
    default where the consumer leaves the input undeclared), not a
    hard-coded one, and records it as a state file in the trigger's
    state dir — the documented record of the run, every value a file;
    the state file travels on the trigger's artifact to every later
    stage job (whose first step downloads the artifact back into its
    state dir), and the per-job env relay the Read trigger state step
    feeds from the restored files carries it in-process (the relay line
    carries the run's trigger-state keys — the bug-issue flag and the
    extract stage's no-delta stop flag). The trigger's
    gate stays untouched — the flag is recorded, never gated on: the
    trigger label (or a manual dispatch) starts a run, and an issue
    carrying only the bug label still starts no factory."""
    step = _resolve_step()
    # the flag is derived against the RESOLVED bug label — the step's
    # env entry the workflow's bug-label input feeds (Step 1's setting:
    # a target that declares another value in its with: block has that
    # value resolve through the documented settings channel)
    assert "BUG_LABEL: ${{ inputs.bug-label }}" in step, \
        ("the trigger's resolve step does not bind the resolved bug "
         "label from the workflow's bug-label input")
    assert 'grep -qx -- "$BUG_LABEL"' in step, \
        ("the trigger does not derive the bug-issue flag by comparing "
         "the issue's labels against the resolved bug label")
    # the flag is recorded in the run's recorded state — a state file in
    # the trigger's state dir, written for every accepted run (both
    # truth values: the run's state carries whether the issue carries
    # the bug label, "true" and "false" alike)
    assert ('echo "$BUG_ISSUE" > '
            '"$RUNNER_TEMP/cw/state/trigger/bug-issue.txt"') in step, \
        ("the trigger does not record the bug-issue flag as a state "
         "file in the trigger's state dir")
    # the state file travels on the trigger's artifact — the upload
    # covers the whole cw state dir (with the hidden-file opt-in) and
    # runs always(), so the flag rides it to every later stage job
    region = _trigger_region()
    assert "name: cw-trigger" in region, \
        "the trigger's artifact is not named cw-trigger"
    assert "path: ${{ runner.temp }}/cw" in region, \
        ("the trigger's upload does not cover the cw state dir the "
         "bug-issue flag file lives in")
    assert "include-hidden-files: true" in region, \
        "the trigger's upload does not opt into hidden files"
    # and every later stage job's state dir receives it: each stage
    # job whose section carries a Read trigger state step (which feeds
    # the per-job env relay from the restored state files) relays the
    # key, so the flag reaches the stage's environment in every job
    # that reads the trigger state
    lines = _read(".github/workflows/factory.yml").splitlines()
    job_keys = ("setup-pi", "baseline", "extract", "plan", "implement",
                "review", "pr", "gates", "report")
    starts = [i for i, ln in enumerate(lines)
              if ln.startswith("  ") and not ln.startswith("   ")
              and ln.strip() in {k + ":" for k in job_keys}]
    assert len(starts) == len(job_keys), \
        ("the factory's nine stage jobs are not all found in the "
         f"workflow file: {len(starts)}")
    relay = ("for k in started issue-number issue-title base-ref "
             "base-sha head title base bug-issue no-delta-stop; do")
    relayed = 0
    for a, b in zip(starts, starts[1:] + [len(lines)]):
        name = lines[a].strip()[:-1]
        section = "\n".join(lines[a:b])
        if "Read trigger state" in section:
            relayed += 1
            assert relay in section, \
                (f"the {name} job's Read trigger state step does not "
                 "relay the bug-issue flag into the job's env — the "
                 "later stage job's state dir receives the flag, but "
                 "the per-job env channel does not carry it")
    assert relayed == 8, \
        (f"the bug-issue flag is relayed by {relayed} of the eight "
         "stage jobs that read the trigger state")
    # the gate stays untouched: the flag is a newly recorded value, not
    # a new gate — the standing trigger gate scenarios keep holding
    # beside the new one (an issue carrying only the bug label still
    # starts no factory, the trigger label is the gate)
    assert "factory idle" in step
    assert "started.txt" in step
    assert 'grep -qx -- "$AI_REQUIREMENTS_LABEL"' in step
