#!/usr/bin/env python3
"""The single guard script (plan §4.1) — invoked three times with different
allowed paths.

  guard-check.py <baseline-ref> <allowed-path>… [! <denied-path>…]

exit 0 → the stage passes the guard — clean (everything changed is inside
the allowed paths), or a violation the guard's repair call cleared in place
(the off-limits files reverted by the call and committed to the branch, a cleared re-check; the stage
completes without re-running its generation — the guard records the
cleared repair in the state dir (stage-guard-repaired.txt, naming the
files the call reverted); the plan
stage's loop machinery claims it to re-run the plan stage's generation,
the other checks' stages complete without re-running)
exit 1 → the guard did not let the stage pass — its repair loop exhausted
MAX_LOOPS without clearing the violation (a failure report listing the
violations is logged and written to the state dir; the stage fails on it),
or its repair call hit a broken environment

Plain entries admit. A `!` section marker switches to inverted-allow
entries, which DENY: the implementation guard's lane is "everything except
the protected set" (its call passes deny = {requirements, plans} +
allow = {this issue's plan file, `__pycache__`}) — a changed file is a
violation when it is denied AND no allow entry admits it (the deny set is
matched by prefix, the allow set also admits paths that carry an allow
entry as a component). The other stages' whitelist calls pass plain
entries only, where a denied file is one no allow entry matches.

Canonical implementation lives in .github/scripts/common.py (shared by every
stage); this file is a thin entry point so the guard is one self-contained
script. If the scripts dir is not materialised next to this action (degenerate
sparse checkout), an inline fallback with identical semantics is used."""
from __future__ import annotations

import os
import sys


def _load():
    here = os.path.dirname(os.path.abspath(__file__))
    scripts = os.path.join(os.path.dirname(os.path.dirname(here)), "scripts")
    if os.path.isdir(scripts):
        sys.path.insert(0, scripts)
        from common import changed_files, guard, main_guard_cli  # noqa: PLC0411
        return main_guard_cli
    # Fallback: same idiom, self-contained (only reached if the sibling
    # scripts/ dir is absent from the checkout).
    import dataclasses
    import subprocess

    def changed_files(baseline: str):
        tracked = subprocess.run(
            ["git", "diff", "--name-only", baseline, "--", "."],
            cwd=os.environ["GITHUB_WORKSPACE"], capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=os.environ["GITHUB_WORKSPACE"], capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        return sorted(set(tracked + untracked))

    def guard_denied(f, allow, deny):
        # Identical to common.guard_denied (see there for the semantics).
        allow = [a.rstrip("/") for a in allow if a]
        deny = [a.rstrip("/") for a in deny if a]
        if not any(f == a or f.startswith(a + "/") or a in f.split("/")
                   for a in allow):
            if not deny:
                return True
            return any(f == d or f.startswith(d + "/") for d in deny)
        return False

    @dataclasses.dataclass
    class GuardResult:
        ok: bool
        violations: list

    def guard(baseline: str, allow, deny=(), stage="", template=""):
        allow = [a.rstrip("/") for a in allow if a]
        deny = [a.rstrip("/") for a in deny if a]
        # a fresh guard call starts without a repair record: the state dir is
        # shared across a run's stages, and a previous stage's cleared repair
        # must not re-trigger a later stage's re-run
        try:
            os.remove(os.path.join(os.environ.get("RUNNER_TEMP") or "/tmp",
                                   "cw", "stage-guard-repaired.txt"))
        except OSError:
            pass

        def violations():
            return [f for f in changed_files(baseline)
                    if guard_denied(f, allow, deny)]

        v = violations()
        if not v:
            print(f"guard: OK — only {' '.join(allow) or '(baseline)'} changed", flush=True)
            return GuardResult(True, [])
        print(f"::error::guard: {len(v)} off-limits file(s) in the working "
              f"tree ({' '.join(v)}) — repairing with a pi call (the "
              f"off-limits files reverted, the stage's own work kept valid; "
              f"the plan stage re-runs its generation on the cleared repair, "
              f"the other stages complete without re-running)", flush=True)
        ws = os.environ["GITHUB_WORKSPACE"]
        sd = os.path.join(os.environ.get("RUNNER_TEMP") or "/tmp", "cw")
        os.makedirs(sd, exist_ok=True)
        model = os.environ.get("LLM_MODEL") or ""

        def fail_stage(report):
            print(f"::error::guard: {report}", flush=True)
            try:
                with open(os.path.join(sd, "stage-fail-reason.txt"), "w") as f:
                    f.write(f"{stage or 'the stage'}: FAILED — {report}\n")
                with open(os.path.join(sd, "stage-summary.txt"), "a",
                          encoding="utf-8") as f:
                    f.write(f"{stage or 'the stage'}: FAILED — {report}\n")
            except OSError:
                pass
            sys.exit(1)

        def ledger_usage(raw: bytes):
            """The repair call's (input, output) token counts — the sums of
            the usage.input / usage.output fields across the call's
            completed assistant messages (the shared plumbing's
            pi_stream_capture idiom); None when no completed assistant
            message carried a parseable usage record — such a call
            appends no ledger line, so the usage totals cover exactly the
            calls that reported usage (cost-and-token-usage "the usage
            totals cover every pi call the run made")."""
            import json
            usage = None
            for line in (raw or b"").decode("utf-8", "replace").split("\n"):
                line = line.rstrip("\r")
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(d, dict) or d.get("type") != "message_end":
                    continue
                m = d.get("message")
                if not isinstance(m, dict) or m.get("role") != "assistant":
                    continue
                u = m.get("usage")
                if isinstance(u, dict):
                    i_tok = u.get("input")
                    o_tok = u.get("output")
                    if isinstance(i_tok, int) and isinstance(o_tok, int):
                        if usage is None:
                            usage = (i_tok, o_tok)
                        else:
                            usage = (usage[0] + i_tok, usage[1] + o_tok)
            return usage

        attempt = 0
        cleared = []
        while True:
            try:
                loops = int(os.environ.get("MAX_LOOPS", "0") or 0)
            except ValueError:
                loops = 0
            if loops > 0 and attempt >= loops:
                fail_stage("the guard's repair cap (MAX_LOOPS) is exhausted "
                           f"without clearing the violation — "
                           f"{len(v)} off-limits file(s) still changed: "
                           f"{' '.join(v)}")
            # one repair pi call through the same invocation form the
            # stages use: the instructions name the off-limits files,
            # instruct the revert, and keep the stage's own work valid
            # against the task its initial instructions gave it
            ins = os.path.join(sd, "guard-repair.md")
            label = stage or "the stage"
            files = "\n".join(f"  - {f}" for f in v)
            with open(ins, "w", encoding="utf-8") as f:
                f.write(
                    f"You are repairing a guard violation in {label}. The "
                    "stage's working tree carries changes outside the "
                    "stage's allowed file set.\n\n"
                    "The off-limits files that changed against the "
                    f"stage's baseline (`{baseline}`) are:\n\n{files}\n\n"
                    "1. Revert the changes to the named files — each back to "
                    f"its state at the baseline `{baseline}`: a file the "
                    "baseline knew — `git checkout <baseline> -- <file>`; a "
                    "file the baseline does not know — remove it from the "
                    "tree. Revert exactly the named files — no other file "
                    "may change.\n"
                    "2. Keep the stage's own work valid against the task its "
                    "initial instructions gave it (the stage's prompt "
                    "template under `pi-prompts/`).\n")
            try:
                r = subprocess.run(
                    ["pi", "--approve", "--print", "--mode", "json",
                     "--model", model,
                     open(ins, encoding="utf-8").read()],
                    cwd=ws, capture_output=True, timeout=21600)
            except subprocess.TimeoutExpired:
                r = subprocess.CompletedProcess(args=[], returncode=124,
                                                stdout=b"", stderr=b"")
            # as the call finishes, its usage record appends to the run's
            # token ledger (one line per call, like the shared plumbing);
            # a call that left no parseable usage record appends no line
            usage = ledger_usage(r.stdout)
            if usage is not None:
                with open(os.path.join(sd, "tokens.txt"), "a") as f:
                    f.write(f"{usage[0]} {usage[1]}\n")
            if r.returncode not in (0, 124):
                if not (r.stdout or b"").strip():
                    print("::warning::guard: the repair call died with no "
                          "output — a dropped provider stream, not a broken "
                          "environment; the iteration is consumed",
                          flush=True)
                else:
                    fail_stage(f"the repair call failed (exit "
                               f"{r.returncode}) — a broken environment is "
                               f"not looped over")
            elif r.returncode == 124:
                print("::warning::guard: the repair call was cut off at the "
                      "pi call cap (exit 124) — a slow model, not a broken "
                      "environment; the iteration is consumed", flush=True)
            cleared.extend(f for f in v if f not in cleared)
            v = violations()
            if not v:
                # the repair cleared the violation: commit the reverted
                # files so the reverts ride the branch (the canonical
                # guard's commit_all idiom — a clean tree commits nothing),
                # then record the cleared repair in the state dir naming
                # the files the call reverted — the plan stage's loop
                # machinery claims the record to re-run the plan stage's
                # generation (the other stages' machinery leaves it
                # unclaimed)
                subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
                dirty = subprocess.run(
                    ["git", "status", "--porcelain"], cwd=ws,
                    capture_output=True, text=True)
                if dirty.stdout.strip():
                    subprocess.run(
                        ["git", "commit", "-q",
                         "-m", "guard repair: off-limits changes "
                               "reverted in place"],
                        cwd=ws, check=True)
                try:
                    with open(os.path.join(sd,
                                           "stage-guard-repaired.txt"), "w") as f:
                        f.write(f"{stage or 'the stage'}: the guard's pi "
                                f"call reverted the off-limits change(s) — "
                                f"{', '.join(cleared)}\n")
                except OSError:
                    pass
                print("guard: OK after repair — the off-limits change is "
                      "reverted in place; the stage completes without "
                      "re-running its generation", flush=True)
                return GuardResult(True, cleared)
            attempt += 1

    def main_guard_cli():
        args = sys.argv[1:]
        if not args or args[0] in ("-h", "--help"):
            print("usage: guard-check.py <baseline-ref> <allowed-path>… "
                  "[! <denied-path>…]")
            sys.exit(2)
        baseline = args[0]
        tail = args[1:]
        if "!" in tail:
            i = tail.index("!")
            allow, deny = tail[:i], [a for a in tail[i + 1:] if a]
        else:
            allow, deny = tail, []
        r = guard(baseline, allow, deny,
                  stage=os.environ.get("CW_GUARD_STAGE", ""),
                  template=os.environ.get("CW_GUARD_TEMPLATE", ""))
        sys.exit(0 if r.ok else 1)

    return main_guard_cli


if __name__ == "__main__":
    _load()()
