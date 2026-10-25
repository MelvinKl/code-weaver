#!/usr/bin/env python3
"""Stages 10+11 — test & review: the self-correcting loop.

  run the target's test suite (contract: `make test`) → the Gherkin oracle
  executes: every scenario is an acceptance test
  → pi (review prompt) marks every scenario FULFILLED/UNFULFILLED against the
    results and reviews the whole diff
  → green & all fulfilled → stage 10 done
  → otherwise a fix directive is built, pi fixes, the suite + review re-run.
Bounded by MAX_LOOPS / MAX_TOKENS (0 = no cap). Each iteration — test output,
verdict, fix directive — is logged into the state dir and travels as a
workflow artifact: the audit trail lives in the workflow log/artifacts, and
nothing under test-results/ is ever committed to the repo.

The review call's captured output is the model's FULL transcript: the pi
invocation runs `--print --mode json` and the harness reconstructs EVERY
completed assistant message into the `.out` file (pi_stream_capture in
common.py). A model observed delivering the REVIEW-VERDICT block in a
non-final turn and closing with a bare summary ("the full result is above")
made the text-mode capture — last message only — parse zero verdicts and fail
the stage on a fully reviewed run (run 40200905062, stage 10-11); with all
messages captured the verdict reaches the parser whichever turn it rode in.
A `pi-<template>.md.settled` marker records whether the stream reached
`agent_settled`: non-zero exit WITHOUT settlement is a provider stream that
died mid-flight (retried, never fatal — a dropped stream can still leave
completed turns behind), a settled non-zero exit is a broken environment.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

# The action directory comes from this file's own location: on this
# runner build GITHUB_ACTION_PATH is unset inside composite action
# inner steps, and on a healthy runner both sources agree anyway
action_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(action_dir)), "scripts"))

import common
import stages

# The prompt prescribes `SCENARIO <file>::<name>: <verdict>` — the models
# have nonetheless been observed emitting `name — <verdict>` (an em dash
# where the format wants a colon) and qualifying the verdict
# (`FULFILLED (orchestration) —`). The parser accepts both separators and
# an optional parenthetical qualifier; it verifies the verdict, it does
# not re-litigate the format.
VERDICT_RE = re.compile(
    r"^SCENARIO\s+(\S+)::(.+?)\s*[:—]\s*(FULFILLED|UNFULFILLED)"
    r"(?:\s*\([^)]*\))?\s*(—|$)")

# common.pi_invoke writes each call's output under the state dir as
# `pi-<template>.out` — this is the review call's output file: the
# reconstructed text of EVERY completed assistant message (the JSON-mode
# capture — see the module docstring). (The old `last-pi.out` name
# pre-dated that contract: reading it was a FileNotFoundError that killed
# the stage on a perfectly good pi run.)
REVIEW_OUT = "pi-review.md.out"


def _stream_settled(template: str) -> bool | None:
    """Did the call's stream reach `agent_settled` (True/False), or is the
    marker absent (None — an older pi build in text mode: the stage falls
    back to the legacy "no output" retry heuristic)?"""
    try:
        return open(common.state_file(f"pi-{template}.md.settled"),
                    encoding="utf-8").read().strip() == "yes"
    except OSError:
        return None


def test_driver() -> list[str]:
    """The target repo's test suite. The factory's contract with targets is
    `make test`; npm test / pytest are fallbacks for repos that drive their
    suite elsewhere. No driver → the stage fails clearly."""
    if shutil.which("make") and subprocess.run(["make", "-n", "test"], cwd=common.repo(),
                                               capture_output=True).returncode == 0:
        return ["make", "test"]
    pkg = os.path.join(common.repo(), "package.json")
    if os.path.exists(pkg):
        import json
        try:
            if json.load(open(pkg)).get("scripts", {}).get("test"):
                return ["npm", "test"]
        except Exception:
            pass
    if os.path.exists(os.path.join(common.repo(), "pyproject.toml")) or os.path.isdir(
            os.path.join(common.repo(), "tests")):
        return [sys.executable, "-m", "pytest", "-q"]
    common.log("::error::no test driver found — the target's contract is `make test` "
               "(or an npm/pytest suite)")
    sys.exit(1)


def run_tests(i: int) -> tuple[int, str]:
    out = common.state_file(f"test-run-{i}.txt")
    driver = test_driver()
    common.log(f"stage 10: running test suite ({' '.join(driver)}) — iteration {i}")
    with open(out, "w") as f:
        r = subprocess.run(driver, cwd=common.repo(), stdout=f,
                           stderr=subprocess.STDOUT, timeout=1800)
    return r.returncode, out


def parse_verdicts(text: str) -> list[tuple[str, str, str]]:
    # The captured transcript holds every assistant message: a model that
    # repeats the verdict block across turns (or corrects a line in a later
    # one) yields duplicate `<file>::<name>` entries. Dedupe on the scenario
    # identity with the LATER verdict winning — a model correcting itself
    # between turns is trusted over its earlier draft; first-seen order is
    # kept for a stable report.
    seen: dict[tuple[str, str], tuple[str, str, str]] = {}
    for line in text.splitlines():
        m = VERDICT_RE.match(line.strip())
        if m:
            key = (m.group(1), m.group(2).strip())
            seen[key] = (key[0], key[1], m.group(3))
    return list(seen.values())


def _verdict_file() -> tuple[str | None, str | None]:
    """Look for the verdict block in the repo tree. The models have been
    observed writing the block to a file (e.g. `review-verdict.txt`) and
    only summarising it in the response. The candidate must carry a real
    SCENARIO verdict line — the marker alone is not a signal: the factory's
    own machinery (`stage.py` sources, the `review.md` prompt) mentions the
    marker in its code, and the first sorted match would otherwise be a
    factory file, `git rm`-ing the pipeline's own code off the branch.
    Factory-machinery paths are excluded outright."""
    try:
        changed = common.changed_files("HEAD")
    except Exception:
        return None, None
    for f in changed:
        if f.startswith((".github/", "pi-prompts/")):
            continue
        p = os.path.join(common.repo(), f)
        if not os.path.isfile(p):
            continue
        try:
            t = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "REVIEW-VERDICT" in t and parse_verdicts(t):
            return f, t
    return None, None


def review(i: int, test_out: str):
    prompt = common.state_file(f"review-prompt-{i}.txt")
    with open(prompt, "w") as f:
        f.write(
            f"The test output of this iteration is in {test_out} (read it).\n"
            f"Review it together with the Gherkin requirements and the current diff.\n"
        )
    req = common.env_dir("REQUIREMENTS_DIR")
    # referenced by path, NOT injected — embedding the test output and every
    # requirement file in full would cost far too many tokens; pi reads what
    # the review needs on demand. test_out is an absolute state-dir path and
    # is already named in the prompt ("read it"); the requirements dir
    # expands to its feature files (a directory argument would crash pi with
    # EISDIR).
    context = ([test_out, *stages.dir_files(req, at_prefix=False)] if req
               else [test_out])
    r = stages.pi_stage("review", prompt_file=prompt, context=context)
    if r.returncode != 0:
        out = common.state_file(REVIEW_OUT)
        try:
            out_now = open(out, encoding="utf-8", errors="replace").read()
        except OSError:
            out_now = ""
        if not out_now.strip():
            # no output and non-zero exit = the provider stream died under
            # us (backend recreated / connection dropped) — ride the 124
            # path: a dropped stream is retried, not fatal
            return None, 124
        # JSON-mode capture: a non-empty output does NOT prove the call ran
        # to completion — completed turns survive a stream that later died.
        # The marker decides: non-settled = a dropped provider stream, ride
        # the 124 path (retried, not fatal); settled (or marker absent on a
        # text-mode build) = a broken environment — the loop fails.
        if _stream_settled("review.md") is False:
            common.log("::warning::stage 10: the review call exited "
                       f"{r.returncode} without its stream settling — the "
                       "provider stream died mid-flight (completed turns "
                       "captured); a dropped stream is retried, not fatal")
            return None, 124
        # any other non-zero WITH output is a broken environment — the loop fails
        return None, r.returncode
    out = common.state_file(REVIEW_OUT)
    try:
        text = open(out, encoding="utf-8", errors="replace").read()
    except OSError:
        common.log("::error::stage 10: the review call exited clean but its "
                   f"output file is missing or unreadable ({out}) — the "
                   "oracle cannot be assumed green")
        return None, 1
    verdicts = parse_verdicts(text)
    if not verdicts:
        # The block is the oracle — accept it from a file the review call
        # wrote instead of answering: mirror it to the state dir (the audit
        # trail) and remove the repo copy (it must never ride a later fix
        # commit), then parse from the mirror.
        f, t = _verdict_file()
        if f is not None:
            common.log(f"::warning::stage 10: the review wrote its verdict block "
                       f"to {f} instead of the response — parsed from the "
                       f"file (mirrored to the state dir; the repo copy is "
                       f"removed)")
            with open(common.state_file(f"review-verdict-{i}.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write(t)
            if subprocess.run(["git", "ls-files", "--", f], cwd=common.repo(),
                              capture_output=True).stdout.strip():
                subprocess.run(["git", "rm", "-f", "--", f], cwd=common.repo(),
                               check=False)
            else:
                p = os.path.join(common.repo(), f)
                if os.path.exists(p):
                    os.remove(p)
            text = t
            verdicts = parse_verdicts(text)
    if not verdicts:
        # the oracle must be marked explicitly — an unparseable review is a
        # stage failure, never a silent pass
        common.log("::error::stage 10: the review emitted no parseable "
                   "SCENARIO verdicts — the oracle cannot be assumed green")
        return None, r.returncode
    return (verdicts, text), r.returncode


def tail(path: str, n: int = 200) -> str:
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    return "\n".join(lines[-n:])


def main() -> None:
    common.install_crash_diagnostics("stage 10-11 test & review")
    i = 0
    prev_cut = False
    pending_audit = False
    while True:
        common.caps_ok(i)
        rc, out = run_tests(i)
        res, rrc = review(i, out) if rc == 0 else (None, 0)
        verdicts = res[0] if res else None

        if rc == 0 and res is None:
            if rrc == 124:
                common.log("::warning::stage 10: the review call was cut off "
                           "at its cap — a slow model, not a broken one; the "
                           "loop retries (the iteration is consumed)")
                prev_cut = True
                i += 1
                continue
            common.log("::error::stage 10: review failed or unparseable — "
                       "stage fails")
            sys.exit(1)
        if rc == 0 and verdicts is not None:
            unfulfilled = [v for v in verdicts if v[2] != "FULFILLED"]
            if not unfulfilled:
                common.log(f"stage 10: suite green — all {len(verdicts)} scenarios FULFILLED")
                open(common.state_file("stage-summary.txt"), "a").write(
                    f"stage 10 test-and-review: green — {len(verdicts)} scenarios fulfilled\n")
                return
            bad_desc = "\n".join(f"- {f}::{name} — {ev}" for f, name, ev in unfulfilled)
            directive = (
                "The following Gherkin scenarios are UNFULFILLED. Fix the implementation "
                "(code, generated tests, docs) until they are fulfilled. "
                "You must NOT edit any file under the requirements dir — a requirement "
                "that cannot be fulfilled is reported, not rewritten:\n" + bad_desc
            )
        elif rc == 0:
            common.log("::error::stage 10: review unparseable — stage fails")
            sys.exit(1)
        else:
            directive = (
                "The test suite failed. Make it green by fixing the implementation "
                "(never the requirements). Failing output (tail):\n" + tail(out)
            )

        # iteration log — state dir only (→ artifact); the repo tree is never
        # used as scratch space
        if pending_audit:
            # The previous fix call died mid-edit: whatever it touched is
            # uncommitted working-tree state. The next prompt carries the
            # audit directive (scenario: “a review or fix call cut off at its
            # cap is retried, not fatal” — “the next prompt tells the model
            # to audit the partial work before continuing”).
            directive = ("The previous fix call was cut off mid-edit. First audit "
                         "the working tree for its partial changes — finish what is "
                         "sound, roll back what is not — then act on the findings:\n\n"
                         + directive)
            pending_audit = False
        with open(common.state_file(f"review-iteration-{i}.md"), "w") as f:
            f.write(f"# iteration {i}\n\n## test (exit {rc})\n```\n{tail(out)}\n```\n\n"
                    f"## fix directive\n```\n{directive}\n```\n")
        fix_prompt = common.state_file(f"fix-prompt-{i}.txt")
        with open(fix_prompt, "w") as f:
            f.write(directive)
        common.log(f"stage 11: fix loop — iteration {i} (log: review-iteration-{i}.md)")
        # Capture the tip before the call: the model may commit its own work
        # during the call, in which case the tree is clean at commit_all time
        # and a plain `if commit_all(...): push` would silently leave the
        # fix work on a dead runner (observed: the re-triggered issue-#3 run
        # committed its fix locally and never pushed it).
        pre = common.git(["rev-parse", "HEAD"], check=False)
        pre_tip = pre.stdout.strip() if pre.returncode == 0 else ""
        r = stages.pi_stage("implement", prompt_file=fix_prompt,
                            context=stages.project_context())
        if r.returncode not in (0, 124):
            out = common.state_file("pi-implement.md.out")
            try:
                out_now = open(out, encoding="utf-8", errors="replace").read()
            except OSError:
                out_now = ""
            if out_now.strip() and _stream_settled("implement.md") is not False:
                common.log("::error::stage 11: pi fix run failed — stage fails")
                sys.exit(1)
            # died with no output — or with completed turns but a stream
            # that never settled — = the provider stream dropped under it,
            # ride the 124 path (the next prompt audits the partial work)
            r.returncode = 124
        if r.returncode == 124:
            # cut off (or the stream died) mid-flight: whatever it touched was
            # never committed; the next iteration audits the tree and
            # finishes the work
            common.log(f"::warning::stage 11: fix run {i} died (exit 124) — "
                       f"no partial work is committed; the next prompt audits "
                       f"the tree and finishes it")
            pending_audit = True
            i += 1
            continue
        pending_audit = False
        pushed = common.commit_all(f"stage 11: fix (iteration {i})")
        tip = common.git(["rev-parse", "HEAD"], check=False)
        tip_now = tip.stdout.strip() if tip.returncode == 0 else ""
        # push when OUR commit landed OR the tip moved under us (the model
        # committed its own work during the call)
        if pushed or (pre_tip and tip_now and tip_now != pre_tip):
            common.push_branch(os.environ["AI_BRANCH"])
        i += 1


if __name__ == "__main__":
    main()
