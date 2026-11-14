#!/usr/bin/env python3
"""Stage 6+7 — planning + plan check.

pi writes the plan for THIS issue as a single Jira-ticket-style markdown file
at `PLAN_DIR/<issue_number>.md`: one plan per issue, no overall plan. The
planner is told which requirement files changed since the baseline AND what
those files changed — the delta the plan must cover rides the stage's
instructions (the baseline diff scoped to the changed files); the changed
files themselves ride the path-referenced context slice (pi reads them on
demand), and the whole Gherkin oracle is not handed to it in full (the
no-injection rule). Where the run's delta is the brownfield shape —
every changed requirement file new against the baseline (the extraction
created the requirements directory, so the baseline knows none of
them) — the target attaches the brownfield clause: the requirements
were extracted from the project's existing code, the plan names the
extracted scenarios it must cover, its steps are scoped to adjusting the
tests to reference those scenarios, and no plan step implements code;
where a changed existing file is among the delta (the standing runs),
the clause is not attached. Where the run's issue is a bug issue —
the trigger's recorded bug-issue flag, derived against the resolved
bug label — and the run skipped the extraction for it, so no
requirement file changed since the baseline, the target takes the
empty-delta branch: the instructions name no requirement file as
changed and carry the issue itself — its number, title and body — as
what the plan must cover; the issue data rides the trigger's state
files (the documented authoritative channel for the issue's number
and title, plus the body file the extract stage reads). The plan
still lands at one file per issue, and the brownfield clause is not
attached to this shape — a bug run's delta is empty (no files at
all), unlike the brownfield shape where every changed file is *new*.
Where the run's extraction stopped instead of skipping — the no-delta
stop (a bug-labelled issue with an empty body, or the standing
empty-body stop): the extract stage records the run-level no-delta-stop
flag in the run's state dir (beside the trigger's recorded state — it
rides the cumulative artefact chain to every later stage job, the
per-job env relay in-process, like the other trigger-state keys), and
the update stage (the plan job's inlined step — it checks the same
flag in its step and no-ops) and the plan stage check it before their
own work: the run is not forwarded to the update stage or the plan
stage — the plan stage stops cleanly without a pi call
(no plan file, no prompt assembly — the bug branch's empty-body form,
which would plan from the issue title alone, is never reached) and
records its own outcome line on the stage-summary channel, which the
report renders as skipped, never as "stage complete". A bug-labelled
run whose extraction merely skipped (a non-empty-body bug issue) records
no flag and proceeds to the empty-delta branch above.
The guard verifies only that one plan file
changed;
any other change is reverted by the guard's pi call and the plan stage
re-runs — the guard records the cleared repair in the state dir, and the
stage's loop machinery claims it and re-runs the generation, the guard
re-checking the re-run (plan: "the plan stage may only touch its own plan
file").
"""
from __future__ import annotations

import os
import sys

# The action directory comes from this file's own location: on this
# runner build GITHUB_ACTION_PATH is unset inside composite action
# inner steps, and on a healthy runner both sources agree anyway
action_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(action_dir)), "scripts"))

import common
import stages


def project_context() -> list[str]:
    """The project files pi reads as context for planning: only the changed
    requirements (the delta), plus the arc42 documentation (doc dir) and the
    README. What those files changed is not context — it rides the stage's
    instructions (the prompt file); the files stay path-referenced here, and
    pi reads them on demand."""
    return stages.changed_requirements_context()


def delta_is_brownfield() -> bool:
    """The recognising rule the plan and implement stages share: the run's
    delta is the brownfield shape when **every** requirement file that
    changed against the baseline is *new* (the extraction created the
    requirements directory, so the baseline knows none of them — the
    full-derivation shape, as opposed to the standing in-place delta).
    A run with no changed requirement file is not that shape — there is
    no delta to plan."""
    files = stages.changed_requirement_files()
    if not files:
        return False
    baseline = stages.baseline_sha()
    for f in files:
        if common.git_exec(["cat-file", "-e", f"{baseline}:{f}"],
                           cwd=common.repo(),
                           capture_output=True).returncode == 0:
            return False
    return True


# The brownfield marker the target writes when the run's delta is the
# brownfield shape: it marks the shape the template's brownfield clause
# keys on, and restates the scope that clause governs — the requirements
# were extracted from the project's existing code, the plan names the
# extracted scenarios it must cover, its steps are scoped to adjusting
# the tests to reference those scenarios, and no plan step implements
# code — so the instructions handed to pi carry the scope either way.
BROWNFIELD_MARKER = (
    "## The run's delta is the brownfield shape\n\n"
    "Every requirement file that changed against the run's baseline is "
    "new — the extraction created the requirements directory, so the "
    "baseline knows none of them. The brownfield clause of your "
    "instructions governs this run: the requirements were extracted "
    "from the project's existing code, so (a) the plan names the "
    "extracted scenarios it must cover, and (b) the plan's steps are "
    "scoped to adjusting the tests to reference those scenarios — no "
    "plan step implements code.\n"
)


def requirement_delta() -> tuple[list[str], str]:
    """The delta the plan must cover: the requirement files that changed
    since the run's baseline, and what those files changed — computed from
    the run's baseline diff (against the baseline the baseline stage
    recorded as state), scoped to those files. The changed files
    themselves ride the call's path-referenced context slice — pi reads
    them on demand; the instructions carry the delta, and the whole
    existing oracle is not injected into the planner (plan: "the planner
    is told which requirements changed and what those changes are")."""
    files = stages.changed_requirement_files()
    if not files:
        return files, ""
    diff = common.git_exec(
        ["diff", stages.baseline_sha(), "--", *files],
        cwd=common.repo(), capture_output=True, text=True, check=False,
    ).stdout
    return files, diff


def delta_section() -> str:
    """The "what those files changed" half of the delta the plan's
    instructions carry: the changed requirement files, named one per line,
    followed by their changes — the run's baseline diff scoped to them.
    A run with no changed requirement files names none and carries no
    diff — there is no delta to plan, except a bug-labelled run whose
    extraction was skipped: its empty delta names none the same way, and
    the plan is built from the issue itself, which the target's issue
    section carries."""
    files, diff = requirement_delta()
    s = "\n## The requirement delta (your task's input)\n\n"
    if not files:
        if _is_bug_run():
            # the empty-delta branch the bug skip creates: no requirement
            # file is named as changed — the plan is built from the issue
            # itself (the target's issue section carries it)
            return s + ("No requirement files changed since the run's "
                        "baseline — the run skipped the requirements "
                        "extraction (a bug-labelled issue), so no "
                        "requirement file is named as changed.\n")
        return s + ("No requirement files changed since the run's baseline "
                    "— there is no delta to plan.\n")
    s += ("The following requirement files changed since the run's "
          "baseline:\n\n")
    s += "".join(f"- `{f}`\n" for f in files)
    if diff.strip():
        s += ("\nWhat those files changed — the delta this plan must cover — "
              "is the run's baseline diff scoped to those files:\n\n"
              "```diff\n" + diff.rstrip() + "\n```\n")
    else:
        s += ("\nTheir changes against the baseline are not part of the "
              "recorded diff (new or untracked files) — read the changed "
              "files on demand from the call's context to see what the "
              "delta is.\n")
    return s


def _is_bug_run() -> bool:
    """Whether the run's issue is a bug issue — the trigger's recorded
    state value (the issue's labels compared against the resolved bug
    label): the state file in the trigger's state dir is the documented
    record (it rides the trigger's artifact to every later stage job),
    and the per-job env relay (CW_BUG_ISSUE) is the in-process channel
    the same value rides. A run the trigger did not record the flag for
    is not a bug run — the standing prompt assembly is unchanged for
    it."""
    v = (common.cw_state("bug-issue")
         or common.cw_input_opt("bug-issue") or "")
    return v.strip().lower() == "true"


def _issue_section(issue: str) -> str:
    """The empty-delta branch's payload: the issue itself — its number,
    title and body — as what the plan must cover. The issue data rides
    the trigger's state files — `issue-title.txt` from the trigger's
    state dir, the body from `issue-body.md`, the state file the extract
    stage reads — the documented authoritative channel for the issue's
    number and title (both ride the trigger's artifact to every stage
    job, the per-job env relay in-process). A body the trigger did not
    record is carried as empty — the plan is still built from the
    number and title."""
    title = common.cw_state("issue-title") or ""
    try:
        body = open(common.state_file("issue-body.md"),
                    encoding="utf-8").read().strip()
    except OSError:
        body = ""
    s = ("\n## The plan must cover the issue itself\n\n"
         "This run skipped the requirements extraction (the issue is a "
         "bug issue) and no requirement file changed since the run's "
         "baseline: no requirement file is named as changed, and the "
         "plan you write is built from the issue itself — the issue "
         "below is what the plan must cover.\n\n"
         f"Issue number: #{issue}\n\n"
         f"Issue title: {title or '(no title recorded)'}\n\n"
         "Issue body:\n\n")
    if body:
        s += body + "\n"
    else:
        s += ("(the issue body is empty — plan from the number and "
              "title)\n")
    return s


def build_target(issue: str, plan_dir: str) -> str:
    """The plan stage's prompt file — passed to pi as the prompt alongside
    the plan template. It names the exact output path and the "one file
    per issue" rule, and it carries the requirement delta: which
    requirement files changed since the baseline and what those files
    changed (the baseline diff scoped to them — the delta the plan must
    cover). Where the delta is the brownfield shape (every changed
    requirement file new against the baseline), the target also attaches
    the brownfield marker — the scope the template's brownfield clause
    governs. Where the run is a bug issue and no requirement file
    changed since the baseline (the extraction was skipped for it), the
    target also carries the issue itself — its number, title and body —
    as what the plan must cover (the empty-delta branch the skip
    creates), and the brownfield marker is not attached to that shape.
    The changed files stay referenced by path in the call's context; the
    instructions carry the delta, never the whole oracle.
    Rebuilt every run so a re-run overwrites the same file."""
    pf = common.state_file("plan-target.md")
    with open(pf, "w", encoding="utf-8") as f:
        f.write("# Output target\n\n")
        f.write("You write EXACTLY ONE plan file — the plan for THIS issue "
                "only.\n\n")
        if issue:
            f.write(f"- Issue number: `#{issue}`\n")
            f.write(f"- Write your plan to that exact path (overwrite any "
                    f"previous version of it):\n\n")
            f.write(f"    ```\n    {stages.plan_path(issue, plan_dir)}\n    ```\n\n")
        f.write("Do NOT create any other file in the plans directory and do "
                "NOT create an overall/aggregate plan: every issue gets its "
                "own single plan file.\n")
        f.write(delta_section())
        # The empty-delta branch the bug skip creates: where the run is a
        # bug issue and no requirement file changed since the baseline,
        # the instructions carry the issue itself — its number, title and
        # body — as what the plan must cover.
        if _is_bug_run() and not requirement_delta()[0]:
            f.write(_issue_section(issue))
        # The brownfield scope attaches only where the delta is the
        # all-new-files shape — where a changed existing file is among the
        # delta (the standing runs), the instructions are exactly the
        # standing ones and the marker is not written. A bug run's delta
        # is empty (no files at all), so the marker is not attached to
        # that shape either.
        if delta_is_brownfield():
            f.write(BROWNFIELD_MARKER)
    return pf


def extract_stopped_no_delta() -> bool:
    """Whether the run's requirement extraction stopped with no delta —
    the run-level stop signal the extract stage records in the run's
    state dir when it takes the no-delta stop (a bug-labelled issue with
    an empty body, or the standing empty-body stop): a state file beside
    the trigger's recorded state (`no-delta-stop`) — the state file
    rides the cumulative artefact chain to every later stage job, the
    per-job env relay (CW_NO_DELTA_STOP) is the in-process channel, like
    the other trigger-state keys. The plan stage checks that flag before
    its own work: the run that stopped at the extraction is not forwarded
    to the plan stage — the stage stops cleanly on the signal without a
    pi call (no plan file, no prompt assembly — the bug branch's
    empty-body form, which would plan from the issue title alone, is
    never reached), recording its own outcome line on the stage-summary
    channel, which the report renders as skipped, never as "stage
    complete". A bug-labelled run that merely skipped the derivation (a
    non-empty-body bug issue) records no flag: its run proceeds to a plan
    built from the issue itself (the empty-delta branch the skip
    creates)."""
    v = (common.cw_state("no-delta-stop")
         or common.cw_input_opt("no-delta-stop") or "")
    return v.strip().lower() == "true"


def run_plan_stage() -> None:
    plan_dir = common.env_dir("PLAN_DIR")
    issue = common.cw_state("issue-number") or common.cw_input_opt("issue-number") or ""
    # The no-delta stop's run-level half: where the run's requirement
    # extraction stopped with no delta (a bug-labelled issue with an
    # empty body, or the standing empty-body stop), the extract stage
    # recorded the stop flag in the run's state dir, and the run is not
    # forwarded to the update stage (its step checks the same flag and
    # no-ops) or to the plan stage: the stage checks the flag before
    # build_target() and its generation loop, and stops cleanly on it —
    # no pi call, no plan file, and no prompt assembly (the bug branch's
    # empty-body form, which would plan from the issue title alone, is
    # never reached) — recording its own outcome line on the
    # stage-summary channel (the report renders it as skipped, never as
    # "stage complete"); the completion marker rides with the line, as on
    # the extract stage's clean stops. A bug-labelled run whose extraction
    # merely skipped (a non-empty-body bug issue) records no flag: its run
    # proceeds to a plan built from the issue itself.
    if extract_stopped_no_delta():
        common.log("stage 6: the run's requirement extraction stopped "
                   "with no delta — the run is not forwarded to the "
                   "update stage (its step checks the same flag and "
                   "no-ops) or to the plan stage: no pi call is made "
                   "for the stage, no plan file is written, the stage "
                   "stops cleanly")
        common.record_stage_outcome(
            "stage 6 planning: skipped (the run's requirement extraction "
            "stopped with no delta — the run is not forwarded to the "
            "update stage or the plan stage; no pi call, no plan file "
            "written)")
        common.record_stage_ran("cw-plan")
        return
    context = project_context()

    # The plan lives at one file per issue. Allow ONLY that file in the
    # guard: the planner must not write another issue's plan, and there is
    # no overall plan to write.
    allowed = stages.plan_path(issue, plan_dir)
    if allowed:
        os.makedirs(os.path.dirname(allowed) or ".", exist_ok=True)
    allow = stages.plan_stage_allow(issue, plan_dir)

    stages.run_generation_stage(
        stage="stage 6 planning",
        template="plan",
        allow=allow,
        context=context,
        prompt_file=build_target(issue, plan_dir),
        # the plan-check form: any change outside the one allowed plan file
        # is reverted by the guard's repair call, and the plan stage re-runs
        # its generation on the guard's cleared-repair record — the guard
        # re-checks the re-run (plan: "the plan stage may only touch its own
        # plan file")
        rerun_on_repair=True,
        # the loop's completion point records the stage's outcome line and
        # completion marker (the report cross-checks them)
        artifact="cw-plan",
    )


def main() -> None:
    common.install_crash_diagnostics("stage 6 planning")
    # the run's resolved extension env applied to this stage's process
    # environment at entry (the artefact-channel half of the relay that
    # keeps the every-step contract whole on a runner build whose
    # GITHUB_ENV write ghosts): every CLI the stage then spawns — its pi
    # invocations, its git children — inherits the provider's values
    common.apply_extension_env()
    run_plan_stage()


if __name__ == "__main__":
    main()
