#!/usr/bin/env python3
"""Stage 6+7 — planning + plan check.

pi writes markdown plan(s) under the plan dir: one or more files may be
combined (several requirement changes per plan), but the plans must cover
every requirement change and stay grounded in the documented (arc42
markdown) architecture. The guard verifies only the plan dir changed."""
from __future__ import annotations

import os
import sys

# GITHUB_ACTION_PATH is unset in composite-action inner steps on this
# runner build (same bug family as the missing INPUT_* binding);
# __file__ is always exact — stage.py lives in the action dir
if os.environ.get("GITHUB_ACTION_PATH"):
    action_dir = os.environ["GITHUB_ACTION_PATH"]
else:
    action_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(action_dir)), "scripts"))

import common
import stages


def main() -> None:
    plan = common.env_dir("PLAN_DIR")
    stages.run_generation_stage(
        stage="stage 6 planning",
        template="plan",
        allow=[plan],
        context=stages.project_context(),
    )


if __name__ == "__main__":
    main()
