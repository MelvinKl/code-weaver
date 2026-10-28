#!/usr/bin/env python3
"""Stage 8+9 — implementation + implement check.

The plan file `PLAN_DIR/<issue_number>.md` (see plan-stage) is a Jira-ticket
state tracker: a checklist of tasks, each open (`- [ ]`) or done (`- [x]`).
Each invocation of this stage works on the NEXT OPEN task — implements it and
marks it done — and the per-task loop below calls again until every task is
done (or a cap is hit).

The guard runs INVERTED-ALLOW (the guard's `!` denied-set marker): the
implementation's lane is everything EXCEPT the protected set — requirements
and the plans dir — so the allow entries carry two jobs:

  - the current issue's plan file: it is the one file inside the denied
    plans dir the implementation may edit (a live state tracker — it flips
    its own task checkboxes as it works); everything else under plans/ is
    still a violation the guard reverts (implement: "implementation may
    only edit the current issue's plan");
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
(requirements: an edit there loops back to the plan stage; the other
issues' plans: a violation the guard reverts), not to guess which of the
tree's pre-existing directories the work belongs in.
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

# an open task in a Jira-ticket-style plan checklist
OPEN_TASK_RE = re.compile(r"^\s*-\s*\[\s*\]\s*")


def protected_dirs() -> list[str]:
    """The dirs the implementation's guard DENIES (the inverted-allow deny
    set, passed as the `!` entries): the requirements dir (the Gherkin
    oracle — an edit there loops back to the plan stage) and the plans dir
    (only the current issue's plan file is re-allowed over it — main() adds
    that one file to the allow set; every other plan is a violation the
    guard reverts)."""
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
    """True if the plan still has an open (`- [ ]`) task to work on."""
    if not (path and os.path.isfile(path)):
        return False
    with open(path, encoding="utf-8") as f:
        return any(OPEN_TASK_RE.match(line) for line in f)


def plan_loop_back(violations: list[str]) -> bool | None:
    """The one violation class that loops back to planning: an edit inside
    the requirements dir. (The current issue's plan is in the allow set — a
    plan edit is never a violation here.)

    The shared guard's external form prints its revert list but does not
    return it (run_guard hands the stage a count, not files), so on that
    path `violations` arrives empty and the hook re-derives the decision key
    itself: while the requirements dir still differs from the stage
    baseline, an implementation edit there is the standing loop-back trigger
    and the plan regenerates before the implementation runs again. The
    in-process fallback does hand the list over, where the filter at the top
    is the same decision."""
    req = common.env_dir("REQUIREMENTS_DIR")
    if not req:
        return None
    protected = [v for v in violations if stages.under(v, req)]
    if not protected:
        changed = common.changed_files(stages.stage_baseline())
        protected = [f for f in changed if stages.under(f, req)]
    if not protected:
        return None  # ordinary leak — the shared revert+re-run path handles it
    plan_dir = common.env_dir("PLAN_DIR")
    issue = common.cw_state("issue-number") or common.cw_input_opt("issue-number") or ""
    allowed = stages.plan_stage_allow(issue, plan_dir)

    def regenerate() -> None:
        stages.run_generation_stage(
            stage="stage 6 planning (re-run from implement)",
            template="plan",
            allow=allowed,
            context=stages.changed_requirements_context(),
        )

    common.log("implement: off-limits edit inside the requirements dir → "
               "looping back to the plan stage (stage 6), then implementing "
               "again against the regenerated, requirement-faithful plan")
    regenerate()
    common.commit_all("implement: plan regenerated (loop-back)")
    return True


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
    # implementation makes, the guard does not revert their byproducts).
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

    # One task per invocation, looped until the plan is fully tracked out or
    # a cap is reached. `allow_noop=False` so an empty model response is a
    # wedged model (there is still an open task), never a false "already done".
    i = 0
    no_progress = 0
    while True:
        common.caps_ok(i)
        if not (current and has_open_task(current)):
            common.log("stage 8 implementation: no open tasks remain — the plan "
                       f"({current}) is fully tracked; stage complete")
            return
        before = set(common.changed_files(stages.baseline_sha()))
        stages.run_generation_stage(
            stage="stage 8 implementation",
            template="implement",
            allow=allow,
            deny=deny,
            context=context,
            prompt_file=build_target(issue, plan_dir),
            on_violation=plan_loop_back,
            allow_noop=False,
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
