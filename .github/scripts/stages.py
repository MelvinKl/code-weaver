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


def stage_baseline() -> str:
    """The rolling baseline the guard measures this stage against: the
    branch tip as the stage started (the stage action records it), falling
    back to the trigger's base sha.

    A stage's guard must judge only THIS stage's work. The trigger's base
    sha would re-flag every earlier stage's committed outputs (extraction's
    feature file) as off-limits changes and revert them out of the tree —
    which then breaks the next stage's context files."""
    p = common.state_file("stage-baseline.sha")
    try:
        v = open(p, encoding="utf-8").read().strip()
        if v:
            return v
    except OSError:
        pass
    return baseline_sha()
def pi_stage(template: str, prompt_file: str | None = None,
             context: list[str] | tuple[str, ...] = (),
             inject: list[str] | tuple[str, ...] = (),
             timeout: int = 21600):
    # 360-minute cap: the user's model is slow (a thinking phase at ~13
    # tok/s over a large context legitimately runs for hours); the stage jobs
    # give 8 hours around each call, and a cut-off call is retried inside
    # the bounded loop. Overridable per call via CW_PI_TIMEOUT.
    """One pi invocation against a pi-prompts/ template — the same
    common.pi_invoke the declarative pi-run action wraps. The thinking level
    is never pinned here (pi-jev chooses it per prompt). `context` files are
    only referenced by path; only `inject` files are handed to pi in full."""
    sp = os.path.join(repo_root(), "pi-prompts", template + ".md")
    return common.pi_invoke(os.environ["LLM_MODEL"], sp, prompt_file,
                            list(context), list(inject), timeout)


def run_guard(baseline: str, allow: list[str]):
    """Prefer the canonical external script (one self-contained script);
    fall back to the shared in-process implementation — same semantics."""
    ext = common.external_guard()
    if ext:
        r = subprocess.run([sys.executable, ext, baseline, *allow],
                           cwd=common.repo(), capture_output=True, text=True)
        return common.GuardResult(ok=(r.returncode == 0), violations=[])
    return common.guard(baseline, allow)


def dir_files(d: str, at_prefix: bool = True) -> list[str]:
    """A directory's files, sorted for a deterministic prompt.

    pi's @-argument handling reads every argument as a file (it even sniffs
    image mime types), so a directory there crashes pi with EISDIR — context
    entries are always concrete files; directories are expanded to the files
    they contain. A missing dir yields an empty list (skipped, not fatal).

    With `at_prefix` (the default) the paths come back pi @-arguments; with
    `at_prefix=False` they come back plain paths for callers that only need to
    tell pi where a file lives (pi now references files by path rather than
    injecting them)."""
    if not d or not os.path.isdir(d):
        return []
    out = [os.path.join(d, f) for f in sorted(os.listdir(d))
           if os.path.isfile(os.path.join(d, f))]
    return ["@" + p for p in out] if at_prefix else out


def project_context() -> list[str]:
    """The project files pi is told where to find — the arc42 markdown under
    the doc dir, the existing Gherkin oracle, and the README.

    These are plain paths (not pi @-arguments): pi references them by path and
    reads what it needs on demand rather than having them all injected into
    the prompt (embedding every project file costs far too many tokens)."""
    req, doc = common.env_dir("REQUIREMENTS_DIR"), common.env_dir("DOC_DIR")
    ctx: list[str] = dir_files(req, at_prefix=False) + dir_files(
        doc, at_prefix=False)
    if os.path.isfile("README.md"):
        ctx.append("README.md")
    return ctx


def changed_requirement_files() -> list[str]:
    """The requirement files that changed since the trigger baseline — the
    delta requirements. The planner is only told where these are (not handed
    them in full) — see the no-injection rule below."""
    req = common.env_dir("REQUIREMENTS_DIR")
    if not req:
        return []
    baseline = baseline_sha()
    return sorted({f for f in common.changed_files(baseline) if under(f, req)})


def changed_requirements_context() -> list[str]:
    """The project files the PLANNER is told where to find: only the changed
    requirements, plus the arc42 documentation (doc dir) and the README.

    These are plain paths (not pi @-arguments), consistent with the
    no-injection rule — pi is told where the files are and reads what the
    planning task needs on demand rather than having them all embedded in the
    prompt (embedding every project file costs far too many tokens). Only the
    system prompt and the implement stage's plan file are ever injected."""
    ctx = list(changed_requirement_files())
    doc = common.env_dir("DOC_DIR")
    if doc:
        ctx.extend(dir_files(doc, at_prefix=False))
    if os.path.isfile("README.md"):
        ctx.append("README.md")
    return ctx


def plan_path(issue: str, plan_dir: str) -> str:
    """The one and only plan file for an issue: `PLAN_DIR/<issue_number>.md`.
    Empty string when the issue or plan dir is unresolved (idle run)."""
    if not (issue and plan_dir):
        return ""
    return os.path.join(plan_dir, f"{issue}.md")


def plan_stage_allow(issue: str, plan_dir: str) -> list[str]:
    """The plan-stage allow set: ONLY this issue's plan file — the planner
    writes one file per issue and must never touch another issue's plan or
    create an overall plan. Falls back to the whole plan dir when the issue
    or plan dir is unresolved."""
    p = plan_path(issue, plan_dir)
    if p:
        return [p]
    return [plan_dir] if plan_dir else []


def under(path: str, prefix: str) -> bool:
    p = prefix.rstrip("/")
    return path == p or path.startswith(p + "/")


def run_generation_stage(stage: str, template: str, allow: list[str],
                         context: list[str], prompt_file: str | None = None,
                         inject: list[str] | tuple[str, ...] = (),
                         post_ok=None, on_violation=None,
                         allow_noop: bool = True) -> None:
    """generate → commit → guard → (clean: post_ok check / break;
    leak: revert + re-run) — bounded by the loop caps.

    A model response that is empty AND changes nothing does not consume
    the loop budget (it would otherwise burn an iteration the guard can
    only trivially pass); it is retried in place, itself bounded, so a
    silently-wedged model cannot loop the stage forever.

    `allow_noop` (default: True) selects the empty-response behaviour: when
    False the stage never treats an empty response as "the work is already
    in place" (it only ever retries, then fails clean). The per-task
    implementation loop needs False — an empty response while a task is open
    means a wedged model, never an already-complete branch."""
    baseline = stage_baseline()
    i = 0
    empty = 0
    while True:
        common.caps_ok(i)
        # a callable prompt_file is rebuilt every iteration: loop feedback
        # (e.g. the validator's verdict on the previous attempt) rides the
        # next prompt
        pf = prompt_file() if callable(prompt_file) else prompt_file
        try:
            r = pi_stage(template, pf, context, inject=inject)
        except Exception:
            import traceback
            common.log(f"::error::{stage}: pi run crashed (the environment is "
                       f"broken, not the model) —\n"
                       f"{traceback.format_exc().rstrip()}")
            sys.exit(1)
        if r.returncode == 124:
            common.log(f"::warning::{stage}: pi run cut off at the call cap "
                       f"(exit 124) — the iteration is consumed and the loop "
                       f"retries; a slow model is not a broken environment")
        elif r.returncode != 0:
            out_f = common.state_file(f"pi-{template}.md.out")
            try:
                out_now = open(out_f, encoding="utf-8",
                                errors="replace").read()
            except OSError:
                out_now = ""
            if not out_now.strip():
                # the provider stream died under us (the backend process was
                # recreated / the connection dropped): pi exits with no
                # output and no file changes. That is a transport hiccup, not
                # a broken environment — retry it exactly as a cut-off call.
                tail = (r.stderr or "").strip().splitlines()
                tail = tail[-1] if tail else "no stderr"
                common.log(
                    f"::warning::{stage}: pi run died with no output "
                    f"(exit {r.returncode}; stderr: {tail[:120]}) — a "
                    f"dropped model stream, not a broken environment; the "
                    f"iteration is consumed and the loop retries")
            else:
                common.log(f"::error::{stage}: pi run failed (exit "
                           f"{r.returncode}) — a broken environment is not "
                           f"looped over")
                sys.exit(1)
        out_f = common.state_file(f"pi-{template}.md.out")
        try:
            produced = open(out_f, encoding="utf-8", errors="replace").read()
        except OSError:
            produced = ""
        # The stage's console persists the model's words per iteration: the
        # next iteration truncates the live file, and failed-job logs are
        # ghosts on this runner build.
        if produced.strip():
            import shutil
            try:
                shutil.copyfile(out_f, common.state_file(f"pi-{template}-iter{i}.out"))
            except OSError:
                pass
            common.log(f"{stage}: model output (iteration {i}, "
                       f"{len(produced)} chars) tail:\n"
                       f"{'—' * 40}\n{produced[-1500:]}")
        if not produced.strip() and not common.changed_files(baseline):
            if not allow_noop:
                # A per-task loop: an empty response means a wedged model
                # (there is still an open task to do), never an already
                # complete branch — retry, then fail clean.
                empty += 1
                if empty > 3:
                    common.log(f"::error::{stage}: model kept returning empty "
                               f"output — the retry tolerance is bounded, the "
                               f"stage fails clean")
                    sys.exit(1)
                common.log(f"{stage}: empty model response, no file changes — "
                           f"retrying without consuming the loop budget "
                           f"(extra {empty}/3)")
                continue
            # Re-run semantics (a new run for the same issue reuses the
            # previous run's branch — the owner's rule): an implementation
            # whose work is already on the branch has nothing to write — the
            # model's empty answer is the truth, not a dropped stream. The
            # stage-start snapshot (`baseline` above) cannot see the previous
            # run's work, but the RUN's baseline can (the target's head,
            # recorded at stage 3): a non-empty diff against it means the
            # implementation is already in place, and this run's stage is
            # satisfied as a no-op — green, not an error (field case: run
            # 40134426478's stage 8 burned four ~20-min phantom retries on
            # exactly this and failed clean). A genuinely empty tree still
            # takes the bounded-retry path below.
            run_diff = common.changed_files(baseline_sha())
            if run_diff:
                common.log(f"{stage}: empty model response, and the work is "
                           f"already in place on the branch ({len(run_diff)} "
                           f"file(s) vs the run baseline) — a re-run of "
                           f"implemented work is a satisfied no-op")
                common.log(f"{stage}: clean — stage complete (no-op)")
                return
            empty += 1
            if empty > 3:
                common.log(f"::error::{stage}: model kept returning empty output — "
                           f"the retry tolerance is bounded, the stage fails clean")
                sys.exit(1)
            common.log(f"{stage}: empty model response, no file changes — retrying "
                       f"without consuming the loop budget (extra {empty}/3)")
            continue
        empty = 0
        try:
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
        except Exception:
            import traceback
            common.log(f"::error::{stage}: stage logic crashed —\n"
                       f"{traceback.format_exc().rstrip()}")
            sys.exit(1)
