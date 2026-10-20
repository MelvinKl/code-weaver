#!/usr/bin/env python3
"""Stage 8+9 — implementation + implement check.

pi implements the plan(s) as code under the source dirs, generates tests,
keeps the arc42 markdown under the doc dir complete and the README current.
The guard's allow set is code + tests + docs + README — it deliberately
EXCLUDES the requirements dir (and the plan dir): if implementation edits a
requirement, the guard reverts the file and the stage loops back to the plan
stage (regenerating the plan against the unchanged requirement) before
implementing again — "a requirement edited during implementation loops back
to planning"."""
from __future__ import annotations

import os
import sys

# The action directory comes from this file's own location: on this
# runner build GITHUB_ACTION_PATH is populated with a value that does
# not point at the action dir (composite inner steps included), and on a
# healthy runner the two are identical anyway
action_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(action_dir)), "scripts"))

import common
import stages


def source_dirs() -> list[str]:
    protected = {common.env_dir("REQUIREMENTS_DIR"), common.env_dir("PLAN_DIR")}
    known = ["src", "tests", "lib", "app", "packages", "services", "internal"]
    if any(os.path.isdir(d) for d in known):
        return [d for d in known if os.path.isdir(d)]
    # Flat repo: allow every top-level entry except the protected dirs
    # ("." itself allows nothing in the guard's prefix test).
    return [e for e in sorted(os.listdir("."))
            if e not in protected and e not in (".git", "node_modules")]


def plan_loop_back(violations: list[str]) -> bool | None:
    req, plan = common.env_dir("REQUIREMENTS_DIR"), common.env_dir("PLAN_DIR")
    protected = [v for v in violations
                 if stages.under(v, req) or stages.under(v, plan)]
    if not protected:
        return None  # ordinary leak — the shared revert+re-run path handles it
    common.log("implement: off-limits edit inside requirements/plans → "
               "looping back to the plan stage (stage 6), then implementing "
               "again against the regenerated, requirement-faithful plan")
    stages.run_generation_stage(
        stage="stage 6 planning (re-run from implement)",
        template="plan",
        allow=[plan],
        context=stages.project_context(),
    )
    common.commit_all("implement: plan regenerated (loop-back)")
    return True


def main() -> None:
    doc = common.env_dir("DOC_DIR")
    allow = source_dirs()
    if doc and doc not in allow:
        allow.append(doc)
    if "README.md" not in allow:
        allow.append("README.md")
    context = stages.project_context()
    plan = common.env_dir("PLAN_DIR")
    if plan:
        context.append("@" + plan)
    stages.run_generation_stage(
        stage="stage 8 implementation",
        template="implement",
        allow=allow,
        context=context,
        on_violation=plan_loop_back,
    )


if __name__ == "__main__":
    main()
