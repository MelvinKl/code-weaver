#!/usr/bin/env python3
"""Stage 8+9 — implementation + implement check.

pi implements the plan(s) as code under the source dirs, generates tests,
keeps the arc42 markdown under the doc dir complete and the README current,
and keeps the plan(s) current as a STATE TRACKER: each plan task it finishes
is marked done in the plan file, so a re-run of the stage sees what is left.
The guard's allow set is therefore code + tests + docs + README + the PLAN
dir; it deliberately EXCLUDES only the requirements dir: if implementation
edits a requirement, the guard reverts the file and the stage loops back to
the plan stage (regenerating the plan against the unchanged requirement)
before implementing again — “a requirement edited during implementation loops
back to planning”."""
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

    The plan dir is documentation, not code, so it is not a source dir
    here — main() adds it to the allow set explicitly: the plan is a
    live state tracker and the implementation must be allowed to update
    it (finished tasks marked done), not be reverted for doing so."""
    protected = {common.env_dir("REQUIREMENTS_DIR")}
    noise = {".git", "node_modules", "__pycache__", ".venv", ".tox", ".mypy_cache"}
    return [e for e in sorted(os.listdir("."))
            if os.path.isdir(e)
            and e not in protected
            and e not in noise
            and (not e.startswith(".") or e == ".github")]


def plan_loop_back(violations: list[str]) -> bool | None:
    """The one violation class that loops back to planning: an edit inside
    the requirements dir. (The plan dir is in the allow set — the plan is
    a live state tracker — so a plan edit is never a violation here.)"""
    req = common.env_dir("REQUIREMENTS_DIR")
    protected = [v for v in violations if stages.under(v, req)]
    if not protected:
        return None  # ordinary leak — the shared revert+re-run path handles it
    common.log("implement: off-limits edit inside the requirements dir → "
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
    plan = common.env_dir("PLAN_DIR")
    doc = common.env_dir("DOC_DIR")
    allow = source_dirs()
    # The plan is a live state tracker: the implementation marks finished
    # plan tasks done in the plan file, so the guard must allow the plan
    # dir — reverting those edits would burn the loop budget re-fighting
    # the same state update every iteration.
    if plan and plan not in allow:
        allow.append(plan)
    if doc and doc not in allow:
        allow.append(doc)
    if "README.md" not in allow:
        allow.append("README.md")
    context = stages.project_context()
    if plan:
        # the plan dir's files (pi reads every @-argument as a file; a
        # directory argument crashes it with EISDIR)
        context.extend(stages.dir_files(plan))
    stages.run_generation_stage(
        stage="stage 8 implementation",
        template="implement",
        allow=allow,
        context=context,
        on_violation=plan_loop_back,
    )


if __name__ == "__main__":
    main()
