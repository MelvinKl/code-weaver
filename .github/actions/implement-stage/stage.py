#!/usr/bin/env python3
"""Stage 8+9 — implementation + implement check.

The plan file `PLAN_DIR/<issue_number>.md` (see plan-stage) is a Jira-ticket
state tracker: a checklist of tasks, each open (`- [ ]`) or done (`- [x]`).
Each invocation of this stage works on the NEXT OPEN task — implements it and
marks it done — and the per-task loop below calls again until every task is
done (or a cap is hit). The guard's allow set therefore includes only THIS
issue's plan file, never another issue's plan: the implementation must never
edit a plan that does not belong to the current issue.

The guard deliberately EXCLUDES only the requirements dir: if implementation
edits a requirement, the guard reverts the file and the stage loops back to
the plan stage (regenerating the plan against the unchanged requirement)
before implementing again — "a requirement edited during implementation loops
back to planning".
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


def source_dirs() -> list[str]:
    """The code dirs the implementation may touch.

    Every top-level directory except the protected one (requirements) and
    the VCS/dependency noise. The conventional source dirs
    (src, tests, lib, app, packages, services, internal) are included
    wherever they exist — and so are the repo's other code locations:
    a factory repo keeps its own source under .github/, and having a
    tests/ dir must not make the guard conclude the implementation
    lives only there. Hidden dirs are excluded except .github, where
    the factory's own workflows and actions live.

    The plan is a live state tracker of THIS issue's tasks, not code, so it
    is not a source dir here — main() adds the current issue's plan file to
    the allow set explicitly (and ONLY that one file — never another
    issue's plan)."""
    protected = {common.env_dir("REQUIREMENTS_DIR")}
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


def has_open_task(path: str) -> bool:
    """True if the plan still has an open (`- [ ]`) task to work on."""
    if not (path and os.path.isfile(path)):
        return False
    with open(path, encoding="utf-8") as f:
        return any(OPEN_TASK_RE.match(line) for line in f)


def plan_loop_back(violations: list[str]) -> bool | None:
    """The one violation class that loops back to planning: an edit inside
    the requirements dir. (The current issue's plan is in the allow set — a
    plan edit is never a violation here.)"""
    req = common.env_dir("REQUIREMENTS_DIR")
    protected = [v for v in violations if stages.under(v, req)]
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

    allow = source_dirs()
    # ONLY this issue's plan file is editable — never another issue's plan.
    if current and current not in allow:
        allow.append(current)
    elif plan_dir:
        # no issue resolved (idle run) — fall back to the whole plan dir
        if plan_dir not in allow:
            allow.append(plan_dir)
    if "README.md" not in allow:
        allow.append("README.md")
    # A repo with no docs/ dir documents itself in its top-level planning
    # markdown (`PLAN.md`): that file is the arc42 set the implementation
    # keeps complete, like README.md, so it joins the allow set.
    if os.path.isfile("PLAN.md") and "PLAN.md" not in allow:
        allow.append("PLAN.md")

    # The current issue's plan file is context too (pi reads its task state
    # to pick up where tracking left off); it is a single file, never a
    # directory, as an @-argument.
    context = stages.project_context()
    if current:
        context.append("@" + current)

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
            context=context,
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
