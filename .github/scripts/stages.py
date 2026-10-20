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
    """The stage-3 baseline ref (state file wins, then the job env).

    A materialized-but-empty value counts as absent: this runner build
    turns missing step env entries into empty variables, and
    'git diff --name-only ""' dies with exit 128."""
    f = common.state_file("baseline.sha")
    if os.path.exists(f):
        v = open(f).read().strip()
        if v:
            return v
    return os.environ.get("BASELINE_REF") or "HEAD"


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
    doc dir, the existing Gherkin oracle, and the README. Missing parts are
    skipped, not fatal.

    pi's @-argument handling reads every argument as a file (it even sniffs
    image mime types), so a directory there crashes pi with EISDIR — context
    entries are always concrete files, with directories expanded to the files
    they contain (sorted for a deterministic prompt)."""
    ctx: list[str] = []
    req, doc = common.env_dir("REQUIREMENTS_DIR"), common.env_dir("DOC_DIR")
    for d in (req, doc):
        if d and os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                p = os.path.join(d, f)
                if os.path.isfile(p):
                    ctx.append("@" + p)
    if os.path.isfile("README.md"):
        ctx.append("@README.md")
    return ctx


def under(path: str, prefix: str) -> bool:
    p = prefix.rstrip("/")
    return path == p or path.startswith(p + "/")


def run_generation_stage(stage: str, template: str, allow: list[str],
                         context: list[str], prompt_file: str | None = None,
                         post_ok=None, on_violation=None) -> None:
    """generate → commit → guard → (clean: post_ok check / break;
    leak: revert + re-run) — bounded by the loop caps.

    A model response that is empty AND changes nothing does not consume
    the loop budget (it would otherwise burn an iteration the guard can
    only trivially pass); it is retried in place, itself bounded, so a
    silently-wedged model cannot loop the stage forever."""
    baseline = baseline_sha()
    i = 0
    empty = 0
    while True:
        common.caps_ok(i)
        # a callable prompt_file is rebuilt every iteration: loop feedback
        # (e.g. the validator's verdict on the previous attempt) rides the
        # next prompt
        pf = prompt_file() if callable(prompt_file) else prompt_file
        r = pi_stage(template, pf, context)
        if r.returncode != 0:
            common.log(f"::error::{stage}: pi run failed (exit {r.returncode}) — "
                       f"a broken environment is not looped over")
            sys.exit(1)
        out_f = common.state_file(f"pi-{template}.md.out")
        try:
            produced = open(out_f, encoding="utf-8", errors="replace").read()
        except OSError:
            produced = ""
        if not produced.strip() and not common.changed_files(baseline):
            empty += 1
            if empty > 3:
                common.log(f"::error::{stage}: model kept returning empty output — "
                           f"the retry tolerance is bounded, the stage fails clean")
                sys.exit(1)
            common.log(f"{stage}: empty model response, no file changes — retrying "
                       f"without consuming the loop budget (extra {empty}/3)")
            continue
        empty = 0
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
