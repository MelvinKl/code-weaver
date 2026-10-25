#!/usr/bin/env python3
"""Stage 6+7 — planning + plan check.

pi writes the plan for THIS issue as a single Jira-ticket-style markdown file
at `PLAN_DIR/<issue_number>.md`: one plan per issue, no overall plan. The
planner is told where only the CHANGED requirement files (the delta) are —
not handed the whole Gherkin oracle in full (the no-injection rule); it reads
them on demand. The guard verifies only that one plan file changed; any
other change reverts and re-runs.
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
    README."""
    return stages.changed_requirements_context()


def build_target(issue: str, plan_dir: str) -> str:
    """A tiny instruction file naming the exact output path and the "one
    file per issue" rule — passed to pi as the prompt alongside the plan
    template. Rebuilt every run so a re-run overwrites the same file."""
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
    )


def main() -> None:
    common.install_crash_diagnostics("stage 6 planning")
    run_plan_stage()


if __name__ == "__main__":
    main()
