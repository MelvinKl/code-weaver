#!/usr/bin/env python3
"""Stages 13+14 — PR gates + gate-fix loop.

Polls the target repo's workflow runs triggered on the PR's head sha: the
factory proceeds only when every one has completed AND all are green
("all PR-triggered workflows must be green"). A red gate fetches the
failing job logs, pi fixes the implementation, the branch is re-pushed,
and the gates re-poll. Fix iterations are bounded by MAX_LOOPS (0 = no cap);
polling has its own count plus the job timeout as the hard backstop.
Nowhere in this script — or the factory — is there a merge call: merging
the PR stays a human decision.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

# The action directory comes from this file's own location: on this
# runner build GITHUB_ACTION_PATH is unset inside composite action
# inner steps, and on a healthy runner both sources agree anyway
action_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(action_dir)), "scripts"))

import common
import stages

POLL_SECONDS = 30
POLL_MAX = int(os.environ.get("CW_GATE_POLLS", "40"))  # + job timeout backstops


def pr_runs(head_sha: str) -> list[dict]:
    data = json.loads(common.gh_api(
        f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs?per_page=100"))
    out = []
    for r in data.get("workflow_runs", []):
        if r.get("head_sha") == head_sha and r.get("event") in (
                "pull_request", "pull_request_target"):
            out.append(r)
    return out


def failing_logs(runs: list[dict]) -> str:
    """The tail of the failed jobs' logs (state dir — never the repo tree)."""
    chunks = []
    for r in runs:
        if r.get("conclusion") == "success" or r.get("status") != "completed":
            continue
        try:
            jobs = json.loads(common.gh_api(
                f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{r['id']}/jobs"
                f"?per_page=100"))
            for j in jobs.get("jobs", []):
                if j.get("conclusion") == "failure":
                    raw = common.gh_api(
                        f"repos/{os.environ['GITHUB_REPOSITORY']}"
                        f"/actions/runs/{r['id']}/jobs/{j['id']}/logs",
                        accept="application/octet-stream").decode("utf-8", "replace")
                    chunks.append(f"### {r['name']} / {j['name']}\n"
                                   + "\n".join(raw.splitlines()[-150:]))
        except Exception as e:
            chunks.append(f"### {r['name']} (log fetch failed: {e})")
    return "\n\n".join(chunks) if chunks else "(no failing job logs retrievable)"


def _cw_in(name: str) -> str:
    """INPUT_<name> (a healthy runner's action-input binding) or CW_<name>
    (the step env the factory sets — on this runner build, composite
    actions' with: values never reach the inner steps as INPUT_* at all).
    """
    n = name.upper().replace("-", "_")
    for k in (f"INPUT_{n}", f"CW_{n}"):
        v = os.environ.get(k)
        if v:
            return v
    import pathlib
    for d in ("trigger", "pr"):
        f = pathlib.Path(os.environ.get("RUNNER_TEMP", "")) / "cw" / "state" / d / (name + ".txt")
        if f.is_file():
            v = f.read_text().strip()
            if v:
                return v
    raise SystemExit(
        f"::error::input '{name}' unbound (no INPUT_{n}, no CW_{n}, "
        f"no state file)")


def main() -> None:
    head_sha = _cw_in("head-sha")
    polls = 0
    fix_iter = 0
    while True:
        runs = pr_runs(head_sha)
        if runs and all(r.get("status") == "completed" for r in runs):
            failed = [r for r in runs if r.get("conclusion") != "success"]
            if not runs:
                common.log("stage 13: no PR-triggered workflows on this head — "
                           "vacuously green")
                return
            if not failed:
                common.log(f"stage 13: all {len(runs)} PR-triggered workflow(s) green")
                open(common.state_file("stage-summary.txt"), "a").write(
                    f"stage 13 pr-gates: all {len(runs)} green\n")
                return
            # stage 14 — bounded fix loop
            common.caps_ok(fix_iter, 0)
            logs = failing_logs(runs)
            log_f = common.state_file(f"gate-failures-{fix_iter}.log")
            with open(log_f, "w") as f:
                f.write(logs)
            names = ", ".join(f"{r['name']}({r.get('conclusion')})" for r in failed)
            common.log(f"stage 14: red gate(s): {names} — fixing (iteration {fix_iter})")
            prompt = common.state_file(f"gate-fix-prompt-{fix_iter}.txt")
            with open(prompt, "w") as f:
                f.write(
                    "The pull request's CI gates failed. Failing runs and the tail "
                    f"of their job logs:\n\n{logs}\n\n"
                    "Fix the implementation (code/tests/docs) so the gates pass. "
                    "You must NOT edit any file under the requirements dir.")
            r = stages.pi_stage("implement", prompt_file=prompt,
                                context=stages.project_context())
            if r.returncode != 0:
                common.log("::error::stage 14: pi gate-fix run failed")
                sys.exit(1)
            if common.commit_all(f"stage 14: gate fix (iteration {fix_iter})"):
                common.push_branch(os.environ["AI_BRANCH"])
            # a re-pushed head means NEW workflow runs — re-resolve the sha
            data = json.loads(common.gh_api(
                f"repos/{os.environ['GITHUB_REPOSITORY']}/branches/"
                f"{os.environ['AI_BRANCH']}"))
            head_sha = data["commit"]["sha"]
            fix_iter += 1
            polls = 0
            continue
        # still running — poll (bounded count; the job timeout is the backstop)
        polls += 1
        if polls > POLL_MAX:
            common.log("::error::stage 13: gate polling exceeded its cap while "
                       "runs were still in progress")
            sys.exit(1)
        pending = ", ".join(f"{r['name']}({r.get('status')})" for r in runs) or "none yet"
        common.log(f"stage 13: waiting for PR-triggered runs: {pending} "
                   f"(poll {polls}/{POLL_MAX})")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
