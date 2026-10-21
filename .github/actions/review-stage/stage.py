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

VERDICT_RE = re.compile(r"^SCENARIO\s+(\S+)::(.+?):\s*(FULFILLED|UNFULFILLED)\s*(—|$)")


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
    v = []
    for line in text.splitlines():
        m = VERDICT_RE.match(line.strip())
        if m:
            v.append((m.group(1), m.group(2).strip(), m.group(3)))
    return v


def review(i: int, test_out: str):
    prompt = common.state_file(f"review-prompt-{i}.txt")
    with open(prompt, "w") as f:
        f.write(
            f"The test output of this iteration is in {test_out} (read it).\n"
            f"Review it together with the Gherkin requirements and the current diff.\n"
        )
    req = common.env_dir("REQUIREMENTS_DIR")
    # every @-argument is read as a file — the requirements dir expands to
    # its feature files (a directory argument would crash pi with EISDIR)
    context = ["@" + test_out, *stages.dir_files(req)] if req else ["@" + test_out]
    r = stages.pi_stage("review", prompt_file=prompt, context=context)
    if r.returncode != 0:
        out = common.state_file("last-pi.out")
        try:
            out_now = open(out, encoding="utf-8", errors="replace").read()
        except OSError:
            out_now = ""
        if not out_now.strip():
            # no output and non-zero exit = the provider stream died under
            # us (backend recreated / connection dropped) — ride the 124
            # path: a dropped stream is retried, not fatal
            return None, 124
        # any other non-zero WITH output is a broken environment — the loop fails
        return None, r.returncode
    out = common.state_file("last-pi.out")
    text = open(out, encoding="utf-8", errors="replace").read()
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
    i = 0
    prev_cut = False
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
        with open(common.state_file(f"review-iteration-{i}.md"), "w") as f:
            f.write(f"# iteration {i}\n\n## test (exit {rc})\n```\n{tail(out)}\n```\n\n"
                    f"## fix directive\n```\n{directive}\n```\n")
        fix_prompt = common.state_file(f"fix-prompt-{i}.txt")
        with open(fix_prompt, "w") as f:
            f.write(directive)
        common.log(f"stage 11: fix loop — iteration {i} (log: review-iteration-{i}.md)")
        r = stages.pi_stage("implement", prompt_file=fix_prompt,
                            context=stages.project_context())
        if r.returncode not in (0, 124):
            out = common.state_file("pi-implement.md.out")
            try:
                out_now = open(out, encoding="utf-8", errors="replace").read()
            except OSError:
                out_now = ""
            if out_now.strip():
                common.log("::error::stage 11: pi fix run failed — stage fails")
                sys.exit(1)
            # died with no output = the provider stream dropped under it —
            # ride the 124 path
            r.returncode = 124
        if r.returncode == 124:
            # cut off (or the stream died) mid-flight: whatever it touched was
            # never committed; the next iteration audits the tree and
            # finishes the work
            common.log(f"::warning::stage 11: fix run {i} died (exit 124) — "
                       f"no partial work is committed; the next prompt audits "
                       f"the tree and finishes it")
            i += 1
            continue
        if common.commit_all(f"stage 11: fix (iteration {i})"):
            common.push_branch(os.environ["AI_BRANCH"])
        i += 1


if __name__ == "__main__":
    main()
