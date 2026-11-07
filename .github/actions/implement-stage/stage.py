#!/usr/bin/env python3
"""Stage 8+9 — implementation + implement check.

The plan file `PLAN_DIR/<issue_number>.md` (see plan-stage) is a Jira-ticket
state tracker: a checklist of steps, each open (`- [ ]`) or done (`- [x]`),
and the code that reads the plan keys on the checkbox, not the word.
Each invocation of this stage works on the NEXT OPEN step — implements it and
marks it done — and the per-step loop below calls again until every step is
done (or a cap is hit).

Completion logging is per step while steps remain open: after each clean
generation call the stage counts the plan file's checkboxes and, while any
step remains open, logs the per-step line ("stage 8 implementation: clean —
step <done>/<total> of the plan done; <remaining> step(s) remain") — that
form rides the shared generation loop's completion-line hook (the loop's
plain "clean — stage complete" form stays the default for the single-call
stages). Only when the per-step loop exits with no open steps left — a plan
already fully tracked when the stage starts, and a plan made fully tracked by
the last call, one form on both exit paths — does the stage log "stage 8
implementation: all <total> plan steps done — stage complete", the only
line it prints that calls the stage complete.

The per-step state also rides the stage-summary channel (the state-dir
`stage-summary.txt` the report stage merges — state rides artifacts, never
the repo tree): one "stage 8 implementation: step <k>/<n> done" line per
step a call finishes, and a "stage 8 implementation: stage complete" line
on the per-step loop's exit — written only for a plan fully tracked, so a
run that stops with steps still open (a cap) leaves the per-step lines
without it. The report stage renders from those lines: a stage that will
re-run (per-step lines without a completion line) is reported per step, and
a stage that is done is reported "stage complete".

The guard runs INVERTED-ALLOW (the guard's `!` denied-set marker): the
implementation's lane is everything EXCEPT the protected set — requirements
and the plans dir — so the allow entries carry two jobs:

  - the current issue's plan file: it is the one file inside the denied
    plans dir the implementation may edit (a live state tracker — it flips
    its own step checkboxes as it works); everything else under plans/ is
    still a violation the guard repairs with a pi call (implement:
    "implementation may only edit the current issue's plan");
  - `__pycache__`: component-matched, so pycache generated at any depth is
    admitted back over its deny. The implementation legitimately RUNS the
    suite (the implement template's verification step) and the guard must
    not revert the compiled byproducts of that run (run 40735387017's
    iteration 2 flagged exactly these).

Everything else is admitted by default — and deliberately: the guard must
never re-litigate WHERE the implementation puts its work. The old form
whitelisted the top-level dirs that existed when the stage STARTED, and a
repo whose `tests/` dir (or `docs/` set, or top-level `Makefile`) did not
exist yet had every iteration's work reverted out of the tree — the stage
then spent its whole loop budget re-creating files the guard deleted
(run 40735387017: the syncer target started with no tests dir, and its
implementation ping-ponged `tests/` for the entire cap). The implementation
has the job to implement the tests — and to create whatever new dirs and
files the work needs — so the guard's job is to protect the protected set
(requirements: an edit there is repaired in place by the guard's pi call —
the changed file named and reverted, the stage not re-run and no loop back
to the plan stage; the other issues' plans: a violation the guard repairs
the same way), not to guess which of the tree's
pre-existing directories the work belongs in.
"""
from __future__ import annotations

import os
import re
import sys

# The action directory comes from this file's own location: on this
# runner build GITHUB_ACTION_PATH is unset inside composite action
# inner steps, and on a healthy runner both sources agree anyway
action_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(action_dir)), "scripts"))

import common
import stages

# an open step in a Jira-ticket-style plan checklist
OPEN_TASK_RE = re.compile(r"^\s*-\s*\[\s*\]\s*")
# a done step in the same checklist form (`- [x]`) — the reader keys on the
# checkbox, not the word: a plan file whose unit word is reworded parses
# identically
DONE_TASK_RE = re.compile(r"^\s*-\s*\[\s*[xX]\s*\]\s*")


def protected_dirs() -> list[str]:
    """The dirs the implementation's guard DENIES (the inverted-allow deny
    set, passed as the `!` entries): the requirements dir (the Gherkin
    oracle — an edit there is repaired in place by the guard's pi call:
    the changed file named and reverted, no loop back to the plan stage)
    and the plans dir (only the current issue's plan file is re-allowed over
    it — main() adds that one file to the allow set; every other plan is a
    violation the guard repairs the same way)."""
    out = [common.env_dir("REQUIREMENTS_DIR"), common.env_dir("PLAN_DIR")]
    return [d for d in out if d]


def source_dirs() -> list[str]:
    """The top-level dirs of the tree, minus the protected set and the
    VCS/dependency noise — the repo's real layout.

    The guard call itself no longer uses these (the inverted-allow allow
    set is main()'s re-admissions, and every other dir is admitted by
    default): the stage keeps the function for its layout view, and this
    repo's contract tests pin its protected-dir exclusions."""
    protected = {common.env_dir("REQUIREMENTS_DIR"), common.env_dir("PLAN_DIR")}
    noise = {".git", "node_modules", "__pycache__", ".venv", ".tox", ".mypy_cache"}
    return [e for e in sorted(os.listdir("."))
            if os.path.isdir(e)
            and e not in protected
            and e not in noise
            and (not e.startswith(".") or e == ".github")]


def current_plan_path(issue: str, plan_dir: str) -> str:
    """The one plan file this issue's implementation may edit:
    `PLAN_DIR/<issue_number>.md`."""
    if not (issue and plan_dir):
        return ""
    return os.path.join(plan_dir, f"{issue}.md")


def build_target(issue: str, plan_dir: str) -> str:
    """A one-line instruction naming the exact plan path for THIS issue —
    passed to pi as the prompt alongside the implement template. The template
    refers to `plans/<issue_number>.md` as a placeholder; the concrete issue
    number and path come from here (rebuilt every run so a resume targets the
    same file). Empty (a blank prompt) when the issue/plan dir is unresolved."""
    pf = common.state_file("implement-target.md")
    if not (issue and plan_dir):
        open(pf, "w", encoding="utf-8").write("")
        return pf
    with open(pf, "w", encoding="utf-8") as f:
        f.write(f"The plan for issue number {issue}. Open and update exactly "
                f"this plan file (and only this issue's plan):")
        f.write(f"\n\n    ```\n    {stages.plan_path(issue, plan_dir)}\n    ```\n")
    return pf


def has_open_task(path: str) -> bool:
    """True if the plan still has an open (`- [ ]`) step to work on."""
    if not (path and os.path.isfile(path)):
        return False
    with open(path, encoding="utf-8") as f:
        return any(OPEN_TASK_RE.match(line) for line in f)


def count_plan_steps(path: str) -> tuple[int, int]:
    """(done, total) — the plan file's checkbox counts: every checklist
    line is a step, done when it carries the done checkbox (`- [x]`),
    open when it carries the open one (`- [ ]`). The reader keys on the
    checkbox, not the word, so a plan file whose unit word is reworded
    still parses — its total is the done + open checkboxes."""
    done = total = 0
    if not (path and os.path.isfile(path)):
        return 0, 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if DONE_TASK_RE.match(line):
                done += 1
                total += 1
            elif OPEN_TASK_RE.match(line):
                total += 1
    return done, total


def main() -> None:
    common.install_crash_diagnostics("stage 8 implementation")
    plan_dir = common.env_dir("PLAN_DIR")
    issue = common.cw_state("issue-number") or common.cw_input_opt("issue-number") or ""
    current = current_plan_path(issue, plan_dir)
    # The inverted-allow call: DENY = the protected set (requirements,
    # plans) — everything else is the implementation's lane (code, tests,
    # the arc42 docs, README, Makefile, new dirs…); ALLOW = the one file
    # inside the denied plans dir the implementation edits (its live state
    # tracker) + `__pycache__` (component-matched: the suite runs the
    # implementation makes, the guard never flags their byproducts).
    deny = protected_dirs()
    allow = ["__pycache__"]
    if current:
        allow.append(current)
    common.log(f"stage 8 implementation: guard denies {' '.join(deny)}; "
               f"everything else is admitted (code, tests, docs, README, new "
               f"dirs) — re-allowed over the deny: {' '.join(allow)}")
    context = stages.project_context()  # referenced by path, not injected
    # ONLY this issue's current plan file is handed to pi in full: it is the
    # live state tracker this stage both reads and updates, and the plan is
    # the one documented exception to the no-injection rule. Inject it as a
    # plain path (pi_invoke turns it into a single @-argument) — it is never
    # appended to context, which is only referenced by path. Every other
    # context file is therefore only referenced by path (embedding the whole
    # project costs far too many tokens); pi reads what it needs on demand.
    inject = [current] if current else []

    # One step per invocation, looped until the plan is fully tracked out or
    # a cap is reached. `allow_noop=False` so an empty model response is a
    # wedged model (there is still an open step), never a false "already done".
    # The completion-line hook below is this stage's own per-step completion:
    # the shared loop calls it where its plain "clean — stage complete" form
    # would go — after each clean call it counts the plan file's checkboxes,
    # and while any step remains open it logs the per-step line instead of a
    # stage completion. All steps done → the hook logs nothing: the loop's
    # exit check below prints the all-steps-done line on both exit paths (a
    # plan already fully tracked when the stage starts, and a plan made fully
    # tracked by the last call), and that is the only line this stage prints
    # that calls the stage complete. The hook also records the per-step
    # state on the stage-summary channel (the state dir the report stage
    # merges — state rides artifacts, never the repo tree): one "stage 8
    # implementation: step <k>/<n> done" line per step the call finished;
    # the exit check below appends the "stage complete" line for a plan
    # made fully tracked, and a run that stops with steps still open
    # (a cap) carries the per-step lines without it.
    # The plan's done count before the stage's first call — the hook
    # advances it after each completed call, so each call's diff names
    # exactly the steps THAT call finished (steps a previous run already
    # did — a re-run resumes where the last run left off — are not steps
    # this run finished).
    done_before, _total_start = count_plan_steps(current)

    def per_step_line() -> str | None:
        nonlocal done_before
        done, total = count_plan_steps(current)
        if done > done_before:
            for k in range(done_before + 1, done + 1):
                with open(common.state_file("stage-summary.txt"), "a",
                          encoding="utf-8") as f:
                    f.write(f"stage 8 implementation: step {k}/{total} "
                            f"done\n")
        done_before = done
        if total - done > 0:
            return (f"stage 8 implementation: clean — step {done}/{total} "
                    f"of the plan done; {total - done} step(s) remain")
        return None

    i = 0
    no_progress = 0
    while True:
        common.caps_ok(i)
        if not (current and has_open_task(current)):
            # the per-step loop's exit: the plan has no open steps left.
            # One form on both exit paths (a plan already fully tracked
            # when the stage starts, and a plan made fully tracked by the
            # last call) — the full step count, the only line that calls
            # the stage complete
            _, total = count_plan_steps(current)
            common.log(f"stage 8 implementation: all {total} plan steps "
                       f"done — stage complete")
            # that completion rides the stage-summary channel too — the
            # only point that writes the line: a run that stops with steps
            # still open (a cap) leaves the per-step lines without it, and
            # the report renders that stage as one that will re-run
            with open(common.state_file("stage-summary.txt"), "a",
                      encoding="utf-8") as f:
                f.write("stage 8 implementation: stage complete\n")
            # the stage is done — its completion marker rides with the line
            common.record_stage_ran("cw-implement")
            return
        before = set(common.changed_files(stages.baseline_sha()))
        stages.run_generation_stage(
            stage="stage 8 implementation",
            template="implement",
            allow=allow,
            deny=deny,
            context=context,
            prompt_file=build_target(issue, plan_dir),
            allow_noop=False,
            completion_line=per_step_line,
        )
        after = set(common.changed_files(stages.baseline_sha()))
        if not (after - before):
            # the call left nothing changed vs the run's baseline — a model
            # that talks without implementing would otherwise loop forever;
            # bound it and fail clean, like the empty-response path.
            no_progress += 1
            if no_progress >= 4:
                common.log("::error::stage 8: the model made no lasting progress "
                           "for 4 calls in a row — the stage fails clean")
                sys.exit(1)
            common.log("stage 8: the call produced no change vs the run's "
                       "baseline — retrying (no_progress "
                       f"{no_progress}/4)")
            i += 1
            continue
        no_progress = 0
        i += 1


if __name__ == "__main__":
    main()
