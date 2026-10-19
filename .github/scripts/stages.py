"""Shared loop machinery for the factory's generation & review stages.

Every stage script (extract-stage, plan-stage, implement-stage,
review-stage) imports this and keeps the same contract:
  - loops are bounded by MAX_LOOPS / MAX_TOKENS — 0 means no cap
  - the guard is the one shared idiom (common.guard / guard-check.py)
  - iteration state & logs live in the state dir, never the repo tree
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import common


def repo_root() -> str:
    """Repo root of the code-weaver checkout (…/.github/actions/<stage> → root)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(common.action_path())))


def baseline_sha() -> str:
    """The stage-3 baseline ref (state file wins, then the job env)."""
    f = common.state_file("baseline.sha")
    if os.path.exists(f):
        return open(f).read().strip()
    return os.environ.get("BASELINE_REF", "HEAD")


def pi_stage(template: str, prompt_file: str | None = None,
             context: list[str] | tuple[str, ...] = (), timeout: int = 1800):
    """One pi invocation against a pi-prompts/ template — the same
    common.pi_invoke the declarative pi-run action wraps."""
    sp = os.path.join(repo_root(), "pi-prompts", template + ".md")
    return common.pi_invoke(os.environ["LLM_MODEL"], sp, prompt_file, list(context), timeout)


def run_guard(baseline: str, allow: list[str]):
    """Prefer the canonical external script (one self-contained script);
    fall back to the shared in-process implementation — same semantics."""
    ext = common.external_guard()
    if ext:
        r = subprocess.run([sys.executable, ext, baseline, *allow],
                           cwd=common.repo(), capture_output=True, text=True)
        return common.GuardResult(ok=(r.returncode == 0), violations=[])
    return common.guard(baseline, allow)


def project_context() -> list[str]:
    """The project files pi reads as context — the arc42 markdown under the
    doc dir (a set of files, structure may vary), the existing Gherkin
    oracle, and the README. Missing parts are skipped, not fatal."""
    ctx: list[str] = []
    req, doc = common.env_dir("REQUIREMENTS_DIR"), common.env_dir("DOC_DIR")
    if req and os.path.isdir(req):
        ctx.append("@" + req)
    if os.path.isfile("README.md"):
        ctx.append("@README.md")
    if doc and os.path.isdir(doc):
        ctx.append("@" + doc)
    return ctx


def under(path: str, prefix: str) -> bool:
    p = prefix.rstrip("/")
    return path == p or path.startswith(p + "/")


def run_generation_stage(stage: str, template: str, allow: list[str],
                         context: list[str], prompt_file: str | None = None,
                         post_ok=None, on_violation=None) -> None:
    """generate → commit → guard → (clean: post_ok check / break;
    leak: revert + re-run) — bounded by the loop caps."""
    baseline = baseline_sha()
    i = 0
    while True:
        common.caps_ok(i)
        r = pi_stage(template, prompt_file, context)
        if r.returncode != 0:
            common.log(f"::error::{stage}: pi run failed (exit {r.returncode}) — "
                       f"a broken environment is not looped over")
            sys.exit(1)
        common.commit_all(f"{stage}: generated (iteration {i})")
        res = run_guard(baseline, allow)
        if res.ok:
            if post_ok is not None and post_ok() is False:
                i += 1
                continue
            common.log(f"{stage}: clean — stage complete")
            return
        common.log(f"{stage}: guard violations → {' '.join(res.violations)}")
        if on_violation is not None and on_violation(res.violations):
            # the hook took ownership (e.g. implement looping back to plan)
            i += 1
            continue
        common.commit_all(f"{stage}: guard reverted off-limits files")
        i += 1
