#!/usr/bin/env python3
"""Stage 6+7 — planning + plan check.

pi writes the plan for THIS issue as a single Jira-ticket-style markdown file
at `PLAN_DIR/<issue_number>.md`: one plan per issue, no overall plan. The
planner is told which requirement files changed since the baseline AND what
those files changed — the delta the plan must cover rides the stage's
instructions (the baseline diff scoped to the changed files); the changed
files themselves ride the path-referenced context slice (pi reads them on
demand), and the whole Gherkin oracle is not handed to it in full (the
no-injection rule). The guard verifies only that one plan file changed;
any other change is reverted by the guard's pi call and the plan stage
re-runs — the guard records the cleared repair in the state dir, and the
stage's loop machinery claims it and re-runs the generation, the guard
re-checking the re-run (plan: "the plan stage may only touch its own plan
file").
"""
from __future__ import annotations

import os
import subprocess
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
    diff = subprocess.run(
        ["git", "diff", stages.baseline_sha(), "--", *files],
        cwd=common.repo(), capture_output=True, text=True,
        check=False,
    ).stdout
    return files, diff


def delta_section() -> str:
    """The "what those files changed" half of the delta the plan's
    instructions carry: the changed requirement files, named one per line,
    followed by their changes — the run's baseline diff scoped to them.
    A run with no changed requirement files names none and carries no
    diff — there is no delta to plan."""
    files, diff = requirement_delta()
    s = "\n## The requirement delta (your task's input)\n\n"
    if not files:
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


def build_target(issue: str, plan_dir: str) -> str:
    """The plan stage's prompt file — passed to pi as the prompt alongside
    the plan template. It names the exact output path and the "one file
    per issue" rule, and it carries the requirement delta: which
    requirement files changed since the baseline and what those files
    changed (the baseline diff scoped to them — the delta the plan must
    cover). The changed files stay referenced by path in the call's
    context; the instructions carry the delta, never the whole oracle.
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
    return pf


def run_plan_stage() -> None:
    plan_dir = common.env_dir("PLAN_DIR")
    issue = common.cw_state("issue-number") or common.cw_input_opt("issue-number") or ""
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
    )


def main() -> None:
    common.install_crash_diagnostics("stage 6 planning")
    run_plan_stage()


if __name__ == "__main__":
    main()
