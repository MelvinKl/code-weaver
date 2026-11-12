"""Shared plumbing for the code-weaver stage actions.

Contract every stage script keeps:
  - working state lives in $RUNNER_TEMP/cw — NEVER in the repo tree
    (the reporting requirement: nothing under test-results/ is ever committed)
  - every loop respects MAX_LOOPS; 0 means no cap
    (the safety requirement: every loop respects its cap)
  - pi is installed and configured for the run by stage 2 (setup-pi) —
    the later stages invoke it; only the setup stage writes its configuration
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
import sys


def repo() -> str:
    return os.environ["GITHUB_WORKSPACE"]


def env_dir(name: str) -> str:
    """A configured directory input (requirements-dir / plan-dir / doc-dir).
    Unset = empty (the stage's allow set skips it)."""
    return (os.environ.get(name) or "").strip().rstrip("/")


def state_dir() -> str:
    d = os.path.join(os.environ.get("RUNNER_TEMP") or "/tmp", "cw")
    os.makedirs(d, exist_ok=True)
    return d


def state_file(name: str) -> str:
    return os.path.join(state_dir(), name)


def log(msg: str) -> None:
    """The workflow log is the audit trail — human review reads it, and it
    is never written into the repo tree.

    On this runner build failed-job logs are ghosts, so every line is
    mirrored into the cw state dir; the stage's artifact carries the
    stage's own narrative."""
    print(msg, flush=True)
    try:
        rt = os.environ.get("RUNNER_TEMP")
        if rt:
            d = os.path.join(rt, "cw")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "stage-console.log"), "a", encoding="utf-8") as f:
                f.write(msg + "\n")
    except OSError:
        pass


def record_stage_outcome(line: str) -> None:
    """Append the stage's outcome line to the stage-summary channel, and
    mirror it into the stage console.

    The stage's STAGE STEP calls this at its completion point — not only
    the job's terminal `if: always()` "Stage summary" step. The terminal
    step is exactly the position a runner whose workflow parser mangles
    late steps drops (issue #106's baseline job: the stage ran its work,
    its terminal summary step ran as a no-op, and the artifact kept only
    the earlier stages' lines): a line written by the stage step itself
    is in the state dir while the step that wrote it is still executing,
    so it rides the artefact even where the job's tail steps are ghosts.
    The terminal step keeps its role as the fallback writer (it appends —
    never truncates — only where the stage step died before recording).
    """
    try:
        d = state_dir()
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "stage-summary.txt"), "a",
                  encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    log(line)


def record_stage_ran(artifact: str) -> None:
    """The stage job's completion marker: state/artifacts/<artifact>.txt.

    Each stage job's stage step writes its own job's marker the moment
    its stage work completes. The markers ride the cumulative artefact
    chain (every job's upload carries the state dir, earlier jobs'
    markers included) to the report job, where their union is the set of
    stage jobs whose stage step completed. That set is the report's
    evidence separating "stage N ran" (a marker or a console line of
    its) from "stage N never ran" (its job missing from the run's job
    graph — neither the marker nor the artefact exists): the distinction
    the failed run 42206491024's false 'run failed' verdict collapsed.
    """
    try:
        d = os.path.join(state_dir(), "artifacts")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{artifact}.txt"), "w",
                  encoding="utf-8") as f:
            f.write(f"{artifact}: stage step completed\n")
    except OSError:
        pass


def install_crash_diagnostics(stage: str) -> None:
    """Crash-parity for the stage scripts — the safety scenario *"a crashed
    stage leaves a persistent diagnosis on the runner"*.

    The inline-Python actions (baseline, pr-open, report) already wrap their
    bodies so an uncaught exception persists the full traceback to the
    runner's durable diag log and a one-line reason to the stage's artifact
    (the job log of a failed run is a ghost on this runner build). The
    stage.py entry points did not: a crashed LLM stage died without either
    artefact, so the report stage's failure summary omitted exactly the
    stages that crashed (the reporting scenario *"a failed run is reported
    too"*). One hook for all five stage entry points — a controlled
    sys.exit (cap reached, broken environment) is NOT a crash: those paths
    already log their reason and the hook lets them pass through.
    """
    import sys as _sys
    import traceback as _tb

    def _hook(t, v, tb):
        if t in (SystemExit, KeyboardInterrupt):
            raise _sys.exit(
                v.code if (t is SystemExit and v is not None and v.code is not None)
                else (1 if t is SystemExit else 130))
        try:
            dump = ("".join(_tb.format_exception(t, v, tb)) if tb is not None
                    else _tb.format_exc())
            d = state_dir()
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "stage-fail-reason.txt"), "w") as f:
                f.write(f"{stage} CRASHED — {v}\n")
            with open(os.path.join(d, "stage-summary.txt"), "a", encoding="utf-8") as f:
                f.write(f"{stage}: FAILED — crashed ({v}); full traceback in the "
                        f"runner's diagnostic log\n")
            try:
                with open("/opt/actions-runner/_diag/cw-diag.log", "a") as f:
                    f.write(f"=== {stage} CRASHED ===\n{dump}\n")
            except OSError:
                pass  # a runner without the diag dir: the artefact line survives
            print(f"::error::{stage} crashed — full diagnosis: "
                  f"/opt/actions-runner/_diag/cw-diag.log")
        except Exception:
            print(f"::error::{stage} crashed — {v}")
        raise _sys.exit(1)

    _sys.excepthook = _hook


class CapReached(SystemExit):
    def __init__(self, which: str, detail: str):
        super().__init__(f"::error::loop cap reached: {which} — {detail}")


def _int_cap(name: str) -> int:
    try:
        return int(os.environ.get(name, "0") or 0)
    except ValueError:
        return 0


def caps_ok(iteration: int) -> None:
    """Raise if a cap would be violated. 0 = no cap (configuration
    requirement: a loop cap of 0 means no cap)."""
    loops = _int_cap("MAX_LOOPS")
    if loops > 0 and iteration >= loops:
        raise CapReached("MAX_LOOPS", f"iteration {iteration} >= cap {loops}")


def tokens_used() -> int:
    # One ledger line per pi call: the call's (input, output) token counts.
    # A record's fields summed is the call's total token count — the report
    # stage's usage totals sum what every call spent, one record per call.
    f = state_file("tokens.txt")
    if not os.path.exists(f):
        return 0
    total = 0
    for line in open(f):
        try:
            total += sum(int(p) for p in line.split())
        except ValueError:
            pass
    return total


def tokens_add(record: tuple[int, int]) -> None:
    """Append one per-call usage record to the run's token ledger — the
    call's input and output token counts, one line. The ledger lives in the
    state dir and travels with the run's state artifacts, like every other
    stage value."""
    with open(state_file("tokens.txt"), "a") as f:
        f.write(f"{record[0]} {record[1]}\n")


def gh_api(path: str, accept: str = "application/vnd.github+json", data: str | None = None) -> str:
    env = {**os.environ, "GH_TOKEN": os.environ.get("GH_TOKEN", "")}
    args = ["gh", "api", "-H", f"Accept: {accept}"]
    if data is not None:
        args += ["-f", f"body={data}"]
    args.append(path)
    r = subprocess.run(args, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {r.stderr.strip()[:300]}")
    return r.stdout


USAGE_RE = re.compile(r"(\d+) in, (\d+) out, \d+ cache read, (\d+) total tok")
# An older pi build predates `--mode` and rejects it at startup (before any
# model call runs); its argument parser names the flag in the error. A
# startup flag rejection is the one failure a one-shot text-mode retry can
# repair — anything else stays a broken-environment failure.
MODE_REJECTED_RE = re.compile(r"unknown option.*--mode|Invalid mode")


def pi_stream_capture(raw: str) -> tuple[bool, list[str], tuple[int, int] | None, bool]:
    """Reconstruct the model's words from a `pi --mode json` event stream.

    Returns (is_jsonl, texts, usage, settled):

      is_jsonl — at least one line parsed as a JSON event carrying a
                 `type` field. False = the stdout is not a JSONL stream
                 (an older pi build in plain-text mode): the raw capture
                 is kept as the model output.
      texts    — the text of EVERY completed assistant message, in stream
                 order. This is the capture contract the stages rely on:
                 a model may deliver its substantive output (e.g. the
                 review's verdict block) in a non-final turn and close
                 with a bare summary — text mode captured only the LAST
                 message, losing the block (run 40200905062: stage 10
                 failed on a fully reviewed run).
      usage    — the call's (input, output) token counts: the sums of the
                 `usage.input` / `usage.output` fields across the call's
                 completed assistant messages; None when no completed
                 assistant message carried a parseable usage record (such a
                 call appends no ledger line).
      settled  — the stream reached its `agent_settled` event. A
                 non-settled stream is a provider stream that died
                 mid-flight; stages retry that call, they don't fail on
                 it (a dropped stream can still leave completed turns).

    Records are split on LF only: pi's JSONL framing treats Unicode line
    separators (U+2028/U+2029) inside JSON strings as payload, not record
    boundaries — splitlines() would shred such a record. A trailing partial
    line (a stream cut off mid-record) simply fails to parse and is skipped;
    every complete record before it survives."""
    is_jsonl = False
    texts: list[str] = []
    usage: tuple[int, int] | None = None
    settled = False
    for line in raw.split("\n"):
        line = line.rstrip("\r")
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict) or "type" not in d:
            continue
        is_jsonl = True
        if d.get("type") == "agent_settled":
            settled = True
        elif d.get("type") == "message_end":
            m = d.get("message")
            if not isinstance(m, dict) or m.get("role") != "assistant":
                continue
            c = m.get("content")
            if isinstance(c, str):
                texts.append(c)
            elif isinstance(c, list):
                texts.append("".join(b.get("text", "")
                                     for b in c
                                     if isinstance(b, dict)
                                     and b.get("type") == "text"))
            u = m.get("usage")
            if isinstance(u, dict):
                i_tok = u.get("input")
                o_tok = u.get("output")
                if isinstance(i_tok, int) and isinstance(o_tok, int):
                    if usage is None:
                        usage = (0, 0)
                    usage = (usage[0] + i_tok, usage[1] + o_tok)
    return is_jsonl, texts, usage, settled


# The stage jobs' job-level `timeout-minutes` backstop, in minutes — a
# target-side input: the reusable workflow's `job-timeout` input (a string,
# optional, default "480") is what the five stage jobs that make pi calls
# carry as their job-level timeout-minutes, and a consumer that leaves the
# input undeclared runs under this constant's value. The stage code knows
# that same value through this shared constant, so the file's declaration
# and the code's knowledge are one property and can never drift apart (the
# stage-contract test pins the match to the input's default). The per-call
# cap (resolve_pi_timeout) is a different property — a target sets it per
# repo through the pi-timeout input — and it is honoured as resolved: the
# trigger-time validation is the enforcement point (a declared value that
# leaves the stage's non-call work no headroom inside the job's timeout
# fails the run at trigger time, and no stage runs after the trigger), so a
# run that reaches a stage has validated that its resolved cap leaves that
# headroom.
JOB_TIMEOUT_MINUTES = 480


PI_TIMEOUT_DEFAULT = 21600


def resolve_pi_timeout() -> int:
    """The per-call pi time cap, resolved through the documented chain
    (chapter 3's settings flow): the reusable workflow's `pi-timeout`
    input's value first — the workflow's own binding `INPUT_PI_TIMEOUT` on
    a healthy runner, then `CW_PI_TIMEOUT`, the job-env entry every stage
    job relays from the input — then the 21600 (360-minute) code default:
    a consumer that leaves the input undeclared keeps the cap its run ran
    under before the input existed, so such a run is unchanged. Every pi
    invocation in the pipeline resolves through this one function — the
    stages' generation calls, the guard's repair call, the pr job's
    PR-body call, the setup stage's smoke check — no call site keeps a
    private default of its own. A declared value that is not an integer
    number of seconds is not a cap: it is skipped for the next link of the
    chain, and for the default at its end."""
    for key in ("INPUT_PI_TIMEOUT", "CW_PI_TIMEOUT"):
        v = (os.environ.get(key) or "").strip()
        if not v:
            continue
        try:
            return int(v)
        except ValueError:
            log(f"::error::the declared pi call cap {v!r} is not an "
                f"integer number of seconds — the value is skipped for "
                f"the {PI_TIMEOUT_DEFAULT}s default")
    return PI_TIMEOUT_DEFAULT


def ensure_pi_on_path() -> None:
    """Make the runner's PATH resolve `pi` to the copy the setup-pi stage
    installed for the run — the contract every later pi invocation in the
    run relies on (setup-pi: "every later pi invocation in the run uses
    that installed copy").

    A runner whose user PATH already carries the agent directory's bin/
    (a machine where pi is normally used) needs nothing. A pristine
    runner (a hosted label) does not: the setup-pi stage extends the PATH
    and writes the install location to the state file `setup-pi-install.txt`
    that the run's state artefact carries to every later job — this call
    re-extends the process's PATH from that location (the env relay
    `PI_PATH`/`PI_INSTALL_DIR` first) before the call, so the installed
    copy resolves on any runner. It never raises: a location it cannot
    find only means the setup stage's state did not reach this job (or
    the process runs off-runner), and the pi invocation's own failure
    carries the broken-environment diagnostic downstream."""
    import shutil as _shutil
    if _shutil.which("pi") is not None:
        return
    candidate = None
    v = os.environ.get("PI_PATH", "").strip()
    if v:
        candidate = v
    else:
        v = os.environ.get("PI_INSTALL_DIR", "").strip()
        if v:
            candidate = os.path.join(v, "bin")
    if candidate is None:
        try:
            with open(state_file("setup-pi-install.txt"), encoding="utf-8") as f:
                for line in f:
                    k, _, val = line.strip().partition("=")
                    if k == "PI_PATH" and val:
                        candidate = val
                    elif k == "PI_INSTALL_DIR" and val:
                        candidate = os.path.join(val, "bin")
        except OSError:
            pass
    if candidate is None or not os.path.isdir(os.path.dirname(candidate)):
        log("::warning::pi is not on the runner's PATH and the run's state "
            "carries no install location the setup-pi stage recorded — the "
            "setup-pi stage's state did not reach this job (or the process "
            "runs off-runner); the pi call's own failure carries the "
            "diagnostic")
        return
    os.environ["PATH"] = os.path.dirname(candidate) + os.pathsep \
        + os.environ.get("PATH", "")


def recorded_extension_env() -> list[tuple[str, str]]:
    """The setup-pi stage's recorded extension env, read from the run's
    state dir — one value a file (`pi-extension-env-<name>.txt`, beside
    the trigger's recorded state; the files ride the cumulative
    artefact chain to every later stage job). The single read both
    apply halves share: apply_extension_env applies the values to the
    process environment (every pi invocation of the run carries them in
    its process environment — the artefact-channel half of the per-job
    Read trigger state relay, the link that resolves on a runner build
    whose GITHUB_ENV write ghosts), and git_exec applies the same values
    to the git child's environment (the run's git operations ride them —
    where the provider carries GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL, git's
    environment-over-configuration precedence makes the provider's
    account the commit's author). A run without the provider recorded no
    file — the list is empty and neither half sets anything."""
    root = os.path.join(os.environ.get("RUNNER_TEMP", ""), "cw",
                        "state", "trigger")
    try:
        names = os.listdir(root)
    except OSError:
        return []
    out = []
    for fname in sorted(names):
        if not (fname.startswith("pi-extension-env-")
                and fname.endswith(".txt")):
            continue
        name = fname[len("pi-extension-env-"):-len(".txt")]
        try:
            with open(os.path.join(root, fname), encoding="utf-8") as f:
                value = f.read().strip()
        except OSError:
            continue
        if value:
            out.append((name, value))
    return out


def apply_extension_env() -> None:
    """The setup-pi stage's recorded extension env — its resolved values
    from a non-empty PI_EXTENSION_ENV provider, each recorded as a state
    file in the run's state dir (one value a file, beside the trigger's
    recorded state; the per-job Read trigger state relay feeds the same
    files into the job's env, the in-process half of the documented
    `CW_*`/state-file relay). This call applies the recorded values to the
    process environment, read through recorded_extension_env — the single
    state-file read both apply halves share (git_exec applies the same
    values to the git child's environment) — the artefact-channel half
    of that relay, and the link it resolves through on a runner build
    whose GITHUB_ENV write ghosts: every pi invocation of the run rides
    this, so every one of them carries the values in its process
    environment. The provider's leave-untouched rule applies: a value
    already present in the environment wins over the run's provided one.
    A run without the provider recorded no file — this call sets no
    variable and the environment is unchanged."""
    for name, value in recorded_extension_env():
        if value and not os.environ.get(name):
            os.environ[name] = value


def pi_invoke(
    model: str,
    system_prompt_file: str,
    prompt_file: str | None = None,
    context: list[str] | tuple[str, ...] = (),
    inject: list[str] | tuple[str, ...] = (),
    timeout: int | None = None,
    context_as_args: bool = False,
) -> subprocess.CompletedProcess:
    """One headless pi run. The backend comes from the pi configuration the
    setup stage wrote into the agent directory for the run — this never
    passes or overrides it (setup-pi contract). Only the model is selected
    here.

    The call's time cap resolves through the documented chain
    (resolve_pi_timeout): `INPUT_PI_TIMEOUT`, then `CW_PI_TIMEOUT` — the
    job-env relay every stage job carries from the reusable workflow's
    `pi-timeout` input — then the 21600 code default, and the resolved
    cap is honoured as resolved: the trigger-time validation is the
    enforcement point (a declared value that leaves the stage's non-call
    work no headroom inside the job's timeout fails the run at trigger
    time, and no stage runs after the trigger), so a run that reaches a
    stage has validated that its resolved cap leaves that headroom, and
    no clamp is applied. An explicit `timeout` overrides the resolution
    for that one call; a caller that passes none rides the resolved cap.

    The thinking level is deliberately NOT passed: pi-jev is configured
    (PI_JEV_THINKING / --jev-thinking) and classifies *each* prompt and picks
    the reasoning level itself — escalating for planning/debugging, and
    de-escalating for short mechanical tasks. Pinning --thinking here would
    strip
    that per-prompt control, so this never sets it.

    Files are NOT injected into the prompt. Passing every context file in as
    an @path argument embeds it in full — far too much token overhead. Only
    two things are handed to pi directly:

      - the stage instructions, folded into the USER text (pi's own default
        system prompt is left in place — a bespoke --system-prompt would both
        overwrite it and cost more tokens), and
      - the files named in `inject` (only the implement stage's plan files,
        the one file set pi must be given in full — it is the live state
        tracker the stage both reads and updates).

    The context contract has two slices, and one invocation uses exactly one
    (the requirements decide which stage sits in which slice):

      - `context_as_args=False` — the default (plan / implement / review /
        pr-body calls): every other file is only referenced by path; its
        contents are NOT embedded in the prompt, pi reads the ones the task
        needs on demand with its read tool, and the invocation's token
        overhead stays small (configuration: "project files are referenced
        by path, not injected into the pi call");
      - `context_as_args=True` — the extraction stage: the NON-oracle
        project files (the arc42 markdown, the README, the baseline diff)
        are handed to pi as @-file arguments — pi reads the named files as
        context before answering (setup-pi: "pi reads the project files as
        context"). The Gherkin oracle is NOT one of them: the stage's
        instructions name its directory as the oracle's location and list
        no requirement file by name — pi reads the files it judges relevant
        from that directory on demand, and a directory is never an
        @-argument (its handling reads files, so one there would crash pi
        with EISDIR). The extraction reads the arc42 and the baseline diff
        up front to keep the delta consistent with the existing scenarios.

    The invocation is `pi --print --mode json`: one-shot, stdout is a
    JSONL event stream. The stream is captured in full and EVERY completed
    assistant message is reconstructed into the `.out` file — not just the
    last one. Text mode captures only the last message, and a model observed
    delivering its REVIEW-VERDICT block in a non-final turn and closing with
    a bare summary made stage 10 parse a summary with no verdict lines and
    fail a fully reviewed run (run 40200905062, stage 10-11).
    A `pi-<template>.md.settled` marker records whether the stream reached
    `agent_settled`: a stage that finds output but a non-settled stream
    retries the call (the provider stream died mid-flight), while a settled
    non-zero exit stays a broken-environment failure.

    As the call finishes, its usage record is appended to the run's token
    ledger in the state dir — one `tokens.txt` line per call carrying the
    call's input and output token counts (the sums over the call's
    completed assistant messages, or the stderr usage summary line on the
    text-mode fallback of an older pi build). A call that left no parseable
    usage record appends no line. The record travels with the run's state
    artifacts like every other stage value."""
    if timeout is None:
        timeout = resolve_pi_timeout()
    ensure_pi_on_path()
    apply_extension_env()
    with open(system_prompt_file, encoding="utf-8") as f:
        instructions = f.read()
    # --print keeps the one-shot contract the oracle pins ("a stage
    # invokes pi with --print"); --mode json makes stdout a JSONL event
    # stream so the capture below sees EVERY assistant message, not only
    # the last (text mode loses a verdict block the model sends in an
    # earlier turn and then summarises — see the docstring)
    cmd = ["pi", "--approve", "--print", "--mode", "json", "--model", model]
    # Give the stage instructions as normal USER text — never --system-prompt:
    # pi's default system prompt is shorter than a bespoke prompt, so folding
    # the instructions into the user prompt keeps pi's default system prompt
    # in place AND costs fewer tokens.
    prompt_text = instructions
    if prompt_file:
        with open(prompt_file, encoding="utf-8") as f:
            prompt_text = f"{instructions}\n\n{f.read()}".strip()
    # the context slice (see the docstring): path-referenced by default;
    # @-file arguments only when the stage opts in (the extraction stage)
    # — a context entry that is not an existing file is dropped, never
    # passed: a missing @-file would make pi's reader fail the call, and a
    # directory would crash pi with EISDIR (a directory is never an
    # @-argument)
    ctx = [c for c in context if os.path.isfile(c)]
    if ctx:
        if context_as_args:
            prompt_text = (
                prompt_text
                + "\n\n[The following project files are handed to pi as "
                "@-file arguments — pi reads the named files as context "
                "before answering:]\n"
                + "\n".join(f"  - {c}" for c in ctx)
            ).strip()
            cmd += ["@" + c for c in ctx]
        else:
            prompt_text = (
                prompt_text
                + "\n\n[The following files are available to read on demand "
                "via the read tool — do not recreate them, only open what "
                "the task needs:]\n"
                + "\n".join(f"  - {c}" for c in ctx)
            ).strip()
    if prompt_text:
        cmd.append(prompt_text)
    # the one injected file set: the implement stage's plan files
    for p in inject:
        cmd.append("@" + p)
    out_f = state_file(f"pi-{os.path.basename(system_prompt_file)}.out")
    err_f = state_file(f"pi-{os.path.basename(system_prompt_file)}.err")
    # yes/no — did the stream reach `agent_settled`? Stages use it to tell
    # "the provider stream died mid-flight" (retry) from "the environment
    # is broken" (fail): in JSON mode a dropped stream can still leave
    # completed turns behind, so a non-empty capture no longer proves the
    # call ran to completion.
    settled_f = state_file(f"pi-{os.path.basename(system_prompt_file)}"
                           ".md.settled")
    label = (f"$ pi --print --mode json --model {model}   # instructions from "
             f"{os.path.basename(system_prompt_file)} (as user text, no --system-prompt)")
    hints = []
    if context:
        hints.append(f"context: {' '.join(context)}"
                     + (" (as @-file arguments)" if context_as_args else ""))
    if inject:
        hints.append(f"inject: {' '.join(inject)}")
    if hints:
        label += " (" + "; ".join(hints) + ")"
    log(label)

    def run_once(c: list[str]) -> subprocess.CompletedProcess:
        with open(out_f, "w") as out, open(err_f, "w") as err:
            try:
                return subprocess.run(c, stdout=out, stderr=err,
                                       cwd=repo(), timeout=timeout)
            except subprocess.TimeoutExpired:
                # A slow model is not a broken environment: the call is cut
                # off cleanly (exit 124) and the stage's bounded loop decides
                # what to do with the partial work — it is not a hard failure.
                log(f"::warning::pi call exceeded its {timeout}s cap and was "
                    f"cut off (exit 124) — treated as a slow model, not a "
                    f"broken environment")
                return subprocess.CompletedProcess(args=c, returncode=124,
                                                  stdout=None, stderr=None)

    def err_text() -> str:
        try:
            return open(err_f, encoding="utf-8", errors="replace").read()
        except OSError:
            return ""

    def capture(c: list[str]) -> tuple[subprocess.CompletedProcess,
                                       bool, tuple[int, int] | None, bool]:
        r = run_once(c)
        raw = ""
        try:
            raw = open(out_f, encoding="utf-8", errors="replace").read()
        except OSError:
            raw = ""
        is_jsonl, texts, usage, settled = pi_stream_capture(raw)
        if is_jsonl:
            # Reconstruct the captured output from the event stream. The
            # raw stdout is JSONL, so .out becomes the concatenated text of
            # every completed assistant message — the stages' parser then
            # sees the verdict block whichever turn the model sent it in.
            with open(out_f, "w", encoding="utf-8") as f:
                f.write("\n\n".join(t for t in texts if t.strip()))
            with open(settled_f, "w", encoding="utf-8") as f:
                f.write("yes" if settled else "no")
        else:
            # A non-JSON stream (an older pi build answering in plain text,
            # or the text-mode retry below) keeps the raw capture; the old
            # stderr usage summary still records the call — now as its
            # (input, output) counts.
            usage = None
            for m in USAGE_RE.finditer(err_text()):
                usage = (int(m.group(1)), int(m.group(2)))  # last summary line wins
        return r, is_jsonl, usage, settled

    r, is_jsonl, usage, settled = capture(cmd)
    # One-shot fallback: this pi build predates --mode json and rejected
    # the flag at startup — no model call ever ran. Retry in plain text
    # mode; the stages keep working on the legacy last-message capture.
    if MODE_REJECTED_RE.search(err_text()) and r.returncode not in (0, 124):
        log("::warning::this pi build rejects '--mode json' — retrying the "
            "call in text mode (last-message capture, not the full transcript)")
        cmd_text = list(cmd)
        try:
            i = cmd_text.index("--mode")
            del cmd_text[i:i + 2]
        except ValueError:
            pass
        r, is_jsonl, usage, settled = capture(cmd_text)
    if usage is not None:
        tokens_add(usage)
        log(f"token usage: {usage[0]} in, {usage[1]} out "
            f"({tokens_used()} accumulated in the run's usage ledger)")
    if r.returncode != 0:
        log(f"::error::pi run '{system_prompt_file}' failed (exit {r.returncode}) — stderr: {err_f}")
    return r


def changed_files(baseline: str) -> list[str]:
    """Tracked changes against the baseline + untracked files (the plan §4.1
    idiom, in Python)."""
    tracked = git_exec(
        ["diff", "--name-only", baseline, "--", "."],
        cwd=repo(), capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    untracked = git_exec(
        ["ls-files", "--others", "--exclude-standard"],
        cwd=repo(), capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    return sorted(set(tracked + untracked))


def guard_denied(f: str, allow: list[str], deny: list[str]) -> bool:
    """The shared admit/deny predicate of one guard call: a changed file is
    denied when it is off-limits AND not explicitly allowed.

    - `allow` — the stage's allowed paths (plain entries). An allow entry
      admits exactly: the entry as a file, everything under it as a
      directory prefix, and every path that CARRIES the entry as one of its
      path components (the implementation guard's `__pycache__` entry
      re-admits pycache at any depth this way — its call's deny set is only
      {requirements, plans}, so the component match is what keeps the
      suite's compiled byproducts out of the violation list).
    - `deny` — the inverted-allow marker (`"!" + path` in the CLI): the
      entry denies itself and everything under it. The implementation
      stage's lane is "everything EXCEPT the protected set" — its guard
      call passes deny = {requirements, plans} + allow = {this issue's plan
      file}, so a file is a violation only when it is protected AND no
      allow entry admits it. A deny entry without any allow entry denies
      everything, so the stages' ordinary whitelist calls (allow only,
      deny empty) are unchanged."""
    allow = [a.rstrip("/") for a in allow if a]
    deny = [a.rstrip("/") for a in deny if a]
    if not any(f == a or f.startswith(a + "/") or a in f.split("/")
               for a in allow):
        if not deny:
            return True  # whitelist semantics: not allowed → off-limits
        return any(f == d or f.startswith(d + "/") for d in deny)
    return False


@dataclasses.dataclass
class GuardResult:
    ok: bool
    violations: list[str]


def _guard_violations(baseline: str, allow: list[str],
                      deny: list[str]) -> list[str]:
    """The shared guard's detection — the half the remedy change does not
    touch: every working-tree change against the stage's baseline (tracked +
    untracked, `changed_files`) that the stage's allowed set does not admit
    (guard_denied). The three check sites keep their per-stage file sets and
    this one shared predicate."""
    return [f for f in changed_files(baseline)
            if guard_denied(f, allow, deny)]


def _guard_repair_instructions(baseline: str, violations: list[str],
                               stage: str, template: str) -> str:
    """The guard's repair instructions — the state-dir file the repair pi
    call reads (the shape the shared plumbing already folds into its user
    text). The instructions (a) name the off-limits files that changed,
    (b) instruct pi to revert the changes to the named files, and
    (c) instruct pi to keep the stage's own work valid against the task its
    initial instructions gave it — the stage's prompt template referenced
    by path, not embedded (the no-injection rule)."""
    label = stage or "the stage"
    files = "\n".join(f"  - {f}" for f in violations)
    if template:
        task = ("the task its initial instructions gave it — the stage's "
                f"prompt template `pi-prompts/{template}.md` (read it if "
                "the repair needs the task's context)")
    else:
        task = ("the task its initial instructions gave it — the stage's "
                "prompt template under `pi-prompts/`")
    return (
        f"You are repairing a guard violation in {label}. The stage's "
        "working tree carries changes outside the stage's allowed file set, "
        "and the guard must restore the protected set without disturbing the "
        "stage's own work.\n\n"
        "The off-limits files that changed against the stage's baseline "
        f"(`{baseline}`) are:\n\n"
        f"{files}\n\n"
        "Do exactly this:\n\n"
        "1. Revert the changes to the named files — each back to its state "
        f"at the baseline `{baseline}`: a file the baseline knew — `git "
        f"checkout {baseline} -- <file>`; a file the baseline does not know "
        "(one the stage added) — remove it from the tree (`git rm -f -- "
        "<file>` for a tracked one, a plain deletion for an untracked one). "
        "Revert exactly the named files — no other file may change.\n\n"
        "2. Keep the stage's own work valid against " + task + ". The "
        "stage's allowed changes stay intact; adjust the stage's own work "
        "only where reverting the named files invalidates it.\n"
    )


def _guard_repair_call(baseline: str, violations: list[str],
                       stage: str, template: str
                       ) -> tuple[subprocess.CompletedProcess, str]:
    """One repair call of the guard's bounded repair loop — a pi call
    through the documented shared pi-call plumbing (pi_invoke: the call
    every stage's invocation goes through — the run's resolved model, the
    run's resolved pi call cap — the `pi-timeout` input's value through
    the documented chain, the 21600 default where it is undeclared — each
    finished call appending its input and output token counts to the run's
    usage ledger). The repair instructions are assembled in the plumbing as
    a state-dir file the call reads. Returns the completed process and its
    class: "done" (the call ran to
    completion), "cut" (cut off at the resolved cap — a slow model,
    retried inside the loop), "dropped" (a non-zero exit with no output —
    the provider stream died mid-flight, retried inside the loop),
    "broken" (a non-zero exit with output — a broken environment; a slow
    model is never a broken environment, and a broken environment is not
    looped over)."""
    model = os.environ.get("LLM_MODEL") or ""
    ins = state_file("guard-repair.md")
    with open(ins, "w", encoding="utf-8") as f:
        f.write(_guard_repair_instructions(baseline, violations, stage,
                                           template))
    r = pi_invoke(model, ins)
    if r.returncode == 0:
        return r, "done"
    if r.returncode == 124:
        return r, "cut"
    try:
        has_out = bool(open(state_file("pi-guard-repair.md.out"),
                            encoding="utf-8",
                            errors="replace").read().strip())
    except OSError:
        has_out = False
    return r, ("dropped" if not has_out else "broken")


def _guard_stage_failure(stage: str, violations: list[str]) -> None:
    """The stop the guard makes when its repair cap is exhausted without
    clearing the violation: a failure report listing the violations (the
    named off-limits files) — the job-visible `::error::` line, the
    stage-fail-reason state file the run's summary step carries on to the
    report, and the stage-summary mirror — then the stage exits non-zero
    (a controlled stop, not a crash: the crash hook's diagnosis is for
    uncaught exceptions, this is the guard's verdict)."""
    label = stage or "the stage"
    report = (f"the guard's repair cap (MAX_LOOPS) is exhausted without "
              f"clearing the violation — {len(violations)} off-limits "
              f"file(s) still changed: {' '.join(violations)}")
    log(f"::error::guard: {report}")
    d = state_dir()
    os.makedirs(d, exist_ok=True)
    try:
        with open(os.path.join(d, "stage-fail-reason.txt"), "w") as f:
            f.write(f"{label}: FAILED — {report}\n")
        with open(os.path.join(d, "stage-summary.txt"), "a",
                  encoding="utf-8") as f:
            f.write(f"{label}: FAILED — {report}\n")
    except OSError:
        pass  # the job-visible line survives
    sys.exit(1)


def _guard_repair(baseline: str, allow: list[str], deny: list[str],
                  violations: list[str], stage: str, template: str
                  ) -> GuardResult:
    """The guard's remedy for a detected violation — a bounded repair loop,
    not a git revert plus a stage re-run. Each iteration makes one pi call
    through the documented shared pi-call plumbing: the instructions name
    the off-limits files that changed, instruct pi to revert the changes to
    the named files, and instruct pi to keep the stage's own work valid
    against the task its initial instructions gave it. After the call the
    guard re-checks the working tree against the stage baseline + allowed
    set — a cleared re-check lets the stage complete WITHOUT re-running its
    generation (the pipeline proceeds to the next stage; the reverts are
    committed so they ride the branch), and the guard records the cleared
    repair in the state dir (`stage-guard-repaired.txt`) — the plan
    stage's loop machinery claims that record and re-runs the plan stage's
    generation, the guard re-checking the re-run (plan "the plan stage may
    only touch its own plan file": any other change is reverted and the
    plan stage re-runs); the other stages' machinery leaves the record
    unclaimed and their stages complete without re-running. The repair
    calls consume iterations
    of the same documented cap machinery (caps_ok): bounded by MAX_LOOPS,
    0 = no cap; a repair call cut off at the resolved pi call cap, or
    dropped by a dead provider stream, consumes its iteration and is
    retried inside the loop (a slow model is not a broken environment);
    a cap exhausted without clearing the violation exits the stage with the
    failure report listing the violations."""
    attempt = 0
    cleared: list[str] = []
    while True:
        try:
            caps_ok(attempt)
        except CapReached:
            _guard_stage_failure(stage, violations)
        r, kind = _guard_repair_call(baseline, violations, stage, template)
        if kind == "broken":
            log(f"::error::guard: the repair call failed (exit "
                f"{r.returncode}) — a broken environment is not looped over")
            sys.exit(1)
        if kind == "cut":
            log("::warning::guard: the repair call was cut off at the pi "
                "call cap (exit 124) — a slow model, not a broken "
                "environment; the iteration is consumed")
        elif kind == "dropped":
            log("::warning::guard: the repair call died with no output "
                f"(exit {r.returncode}) — a dropped provider stream, not "
                "a broken environment; the iteration is consumed")
        else:
            log(f"guard: the repair call completed (off-limits: "
                f"{' '.join(violations)}) — re-checking the working tree")
        # after the call the guard re-checks the working tree against the
        # stage baseline + allowed set
        cleared.extend(v for v in violations if v not in cleared)
        violations = _guard_violations(baseline, allow, deny)
        if not violations:
            # the repair cleared the violation: commit the reverted files so
            # the reverts ride the branch, then let the stage complete
            # without re-running its generation — and record the cleared
            # repair in the state dir (the plan stage's loop machinery
            # claims the record and re-runs the plan stage's generation on
            # it, the guard re-checking the re-run; the other stages' loop
            # machinery leaves it unclaimed — a stage's guard call clears a
            # stale record from a previous stage's guard call at its start)
            commit_all("guard repair: off-limits changes reverted in place")
            try:
                with open(state_file("stage-guard-repaired.txt"), "w",
                          encoding="utf-8") as f:
                    f.write(f"{stage or 'the stage'}: the guard's pi call "
                            f"reverted the off-limits change(s) — "
                            f"{', '.join(cleared)}\n")
            except OSError:
                pass  # the record rides the state dir; a write failure is a
                       # log gap, not a verdict change
            log(f"guard: OK after repair — {' '.join(cleared)} reverted in "
                f"place; the stage's own work stays valid, the stage "
                f"completes without re-running its generation")
            log("guard: the cleared repair is recorded in the state dir "
                "(stage-guard-repaired.txt) — a stage that re-runs on a "
                "repaired violation (the plan stage) re-runs its generation "
                "on it")
            return GuardResult(ok=True, violations=cleared)
        attempt += 1


def guard(baseline: str, allow: list[str] | tuple[str, ...],
          deny: list[str] | tuple[str, ...] = (), stage: str = "",
          template: str = "") -> GuardResult:
    """The one shared guard idiom (plan §4.1) — one implementation, three
    call sites (the three check stages, each with its own per-stage allowed
    file set): collect the working-tree changes against the stage's baseline
    and compare them against the stage's allowed set — a clean stage
    passes. A violation is repaired with a pi call — the off-limits files
    named, pi told to revert the changes to the named files, and told to
    keep the stage's own work valid against the task its initial
    instructions gave it — instead of the guard reverting the files by git
    and the stage being re-run: after each repair call the guard re-checks
    the working tree against the stage baseline + allowed set, a cleared
    re-check lets the stage complete without re-running its generation
    (and records the cleared repair in the state dir —
    stage-guard-repaired.txt, which the plan stage's loop machinery claims
    to re-run the plan stage's generation, the guard re-checking the
    re-run; the other checks' stages complete without re-running), and a
    repair cap (MAX_LOOPS, 0 = no cap) exhausted without clearing the
    violation fails the stage with a failure report listing the
    violations. Invoked three times by the three check stages with
    different allowed paths — one script (guard-check.py), three calls; the
    implementation call passes the inverted-allow deny set (its lane is
    everything except the protected dirs), the others their plain allow
    sets. `stage` / `template` are the stage's identity for the repair
    instructions (the CLI form reads them from the CW_GUARD_STAGE /
    CW_GUARD_TEMPLATE env entries the stage sets for its guard call)."""
    allow = [a.rstrip("/") for a in allow if a]
    deny = [a.rstrip("/") for a in deny if a]
    # a fresh guard call starts without a repair record: the state dir is
    # shared across a run's stages, and a previous stage's cleared repair
    # must not re-trigger a later stage's re-run
    try:
        os.remove(state_file("stage-guard-repaired.txt"))
    except OSError:
        pass
    violations = _guard_violations(baseline, allow, deny)
    if not violations:
        log(f"guard: OK — only {' '.join(allow) or '(baseline)'} changed")
        return GuardResult(ok=True, violations=[])
    log(f"::error::guard: {len(violations)} off-limits file(s) in the "
        f"working tree ({' '.join(violations)}) — repairing with a pi "
        f"call (the off-limits files reverted, the stage's own work kept "
        f"valid; the plan stage re-runs its generation on the cleared "
        f"repair, the other stages complete without re-running)")
    return _guard_repair(baseline, allow, deny, violations, stage,
                         template)


def commit_all(message: str) -> bool:
    """Commit whatever the stage produced (empty = no-op)."""
    git_exec(["add", "-A"], cwd=repo(), check=True)
    dirty = git_exec(["status", "--porcelain"], cwd=repo(),
                     capture_output=True, text=True)
    if not dirty.stdout.strip():
        return False
    git_exec(["commit", "-q", "-m", message], cwd=repo(), check=True)
    return True


def ai_branch() -> str:
    """The run's AI branch name — the documented stage-value channel:
    the `AI_BRANCH` job env every stage job writes, then the `CW_` env
    entry, then the trigger's state file (the artifact channel the other
    stage values ride). Empty string where the run resolves no branch
    (an idle run) — the stage-completion push then skips with a log line
    rather than failing."""
    return (os.environ.get("AI_BRANCH") or os.environ.get("CW_AI_BRANCH")
            or cw_state("ai-branch") or "")


def push_branch(branch: str, force: bool = True) -> None:
    token = os.environ.get("GH_TOKEN", "")
    origin = f"https://x-access-token:{token}@github.com/{os.environ['GITHUB_REPOSITORY']}"
    args = ["push"]
    if force:
        args.append("--force")
    args += ["origin", branch]
    # GIT_CONFIG_COUNT must name exactly the keys we set, and the inherited
    # environment must not carry the runner's own GIT_CONFIG_* entries: a
    # stray GIT_CONFIG_KEY_1 without its value (observed on this runner
    # build) makes git die with "missing config key GIT_CONFIG_KEY_1" the
    # moment COUNT names an index the parent never filled — the fix loop's
    # push crashed the review stage exactly this way (run 39913220223; the
    # crash hook's artefact is how the diagnosis survived the ghost job
    # log).
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_CONFIG_")}
    env.update({
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.cookie",
        "GIT_CONFIG_VALUE_0": "",
    })
    r = git_exec(args, cwd=repo(), capture_output=True, text=True, env=env)
    # rewrite any token in the URL back out of the log
    if r.returncode != 0:
        clean = (r.stderr or r.stdout).replace(token, "***") if token else (r.stderr or "")
        raise RuntimeError(f"git push failed: {clean.strip()[:300]}")


def git_exec(argv: list[str], **kwargs) -> subprocess.CompletedProcess:
    """The factory's single git entry point.

    Every git call in the factory's python routes through this one
    function: it takes the git arguments plus every extra parameter a
    git child may need (cwd, env, check, capture_output, text,
    timeout) and hands them straight to subprocess.run. The test suite
    mocks this one function — a mock here keeps the whole suite off the
    real git binary (a test that spawned real git would read the
    runner's git configuration and could touch a real repository's
    state, which no test may do: test-and-review "tests never invoke
    the real git binary"). Each inline workflow step's python runs in
    its own interpreter and carries the same one-function shape with
    its own copy.

    The child's git reads the workspace's safe.directory entry from its
    OWN process environment: actions/checkout's safe.directory shim is
    written into a temporary HOME that exists for the checkout step
    alone, so a git child running in a LATER step of the same job (the
    stage's branch cut, fetch, commit and push against the checked-out
    workspace) would read a user-global configuration without the
    entry, and git refuses the workspace with 'detected dubious
    ownership' where the runner process does not own it (the death of
    run 42968837898's baseline stage). The managed entries pin the
    runner user's home directory, the current working directory, and —
    where the step's GITHUB_WORKSPACE is known (set on every runner
    step, unset for a local invocation) — the workspace itself as
    safe.directory; they are appended after any GIT_CONFIG_* entries
    the caller already composed (the push's empty-cookie entry keeps
    its index), so the child's configuration is complete and
    count-consistent whatever the user-global configuration holds.

    The child's environment also carries the run's resolved extension
    env — the values the setup-pi stage recorded in the run's state dir
    (one value a file, beside the trigger's recorded state; the per-job
    Read trigger state relay's GITHUB_ENV half feeds the job's env, this
    state-file read is the artefact-channel half that keeps the relay
    whole on a runner build whose GITHUB_ENV write ghosts), applied to
    the child's environment under their own names with the provider's
    leave-untouched rule (a value already present in the environment
    wins over the run's provided one). Where the provider carries
    GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL, git's
    environment-over-configuration precedence makes the provider's
    account the commit's author — the run's commits are attributed to
    the account the provider names, not to the identity the run's git
    configuration would otherwise yield; where the provider is
    empty/absent no values are applied and the child's environment is
    exactly as before — the sanitised push idiom's GIT_CONFIG hygiene
    identity stands as the fallback the provider's variables override.
    """
    env = dict(kwargs.pop("env", None) or os.environ)
    try:
        n = int(env.get("GIT_CONFIG_COUNT", "0"))
    except ValueError:
        n = 0
    for k in [k for k in env
              if k.startswith("GIT_CONFIG_KEY_") or k.startswith("GIT_CONFIG_VALUE_")]:
        if k.rsplit("_", 1)[-1].isdigit() and int(k.rsplit("_", 1)[-1]) >= n:
            del env[k]  # a dangling caller/runner entry beyond the count
    # the run's resolved extension env applied to the git child's
    # environment — the git half of the same relay, on the same
    # recorded values (the provider's variables are not GIT_CONFIG_*
    # entries, so they keep the managed entries' indices clear): where
    # the provider carries GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL, git's
    # environment-over-configuration precedence makes the provider's
    # account the commit's author; a run without the provider recorded
    # no file and the child's environment is exactly as before
    for name, value in recorded_extension_env():
        if value and not env.get(name):
            env[name] = value
    entries = [
        ("safe.directory", os.path.expanduser("~")),
        ("safe.directory", os.getcwd()),
    ]
    ws = os.environ.get("GITHUB_WORKSPACE")
    if ws:
        entries.append(("safe.directory", ws))
    env["GIT_CONFIG_COUNT"] = str(n + len(entries))
    for i, (k, v) in enumerate(entries, start=n):
        env["GIT_CONFIG_KEY_%d" % i] = k
        env["GIT_CONFIG_VALUE_%d" % i] = v
    kwargs["env"] = env
    return subprocess.run(["git"] + list(argv), **kwargs)


def git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    # Same GIT_CONFIG_* sanitisation as push_branch: a runner that leaks a
    # dangling GIT_CONFIG_KEY_i into the job env would poison every git
    # child otherwise.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_CONFIG_")}
    return git_exec(args, cwd=repo(), capture_output=True, text=True,
                    check=check, env=env)


def action_path() -> str:
    """Directory of the running stage inside the factory runtime tree —
    sibling actions/scripts resolve from here.

    The tree is anchored from this file's own location: common.py lives
    at <tree>/.github/scripts/common.py. In the factory the stage scripts
    run from the stash (each stage job's first step copies the called
    repo's .github tree into $RUNNER_TEMP before any checkout replaces
    the workspace with the target repo), so this file's location IS the
    stashed tree's scripts dir; a dev/standalone invocation of a stage
    script runs it from the checkout itself and the same anchor resolves
    there. GITHUB_ACTION_PATH is deliberately not consulted: the workflow
    has no composite-action boundary left for it to point at, and a
    healthy runner would point it at the target repo's (absent) action
    dir."""
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(repo_root, ".github", "actions", "stage")


def sibling_action(name: str) -> str:
    return os.path.join(os.path.dirname(action_path()), name)


def external_guard() -> str | None:
    """The canonical single guard script (one script, three call sites)."""
    p = os.path.join(os.path.dirname(action_path()), "scripts", "guard-check.py")
    return p if os.path.exists(p) else None


def main_guard_cli() -> None:
    """guard-check.py entry point:
        guard-check.py <baseline-ref> <allowed-path>… [! <denied-path>…]
    exit 0 = the stage passes the guard — clean (everything changed is
    inside the allowed paths), or a violation the guard's repair call
    cleared in place (the off-limits files reverted by the call, a cleared
    re-check — the stage completes without re-running its generation; the
    guard records the cleared repair in the state dir
    (stage-guard-repaired.txt) — the plan stage's loop machinery claims it
    to re-run the plan stage's generation, the other checks' stages complete
    without re-running);
    exit 1 = the guard did not let the stage pass — its repair loop
    exhausted MAX_LOOPS without clearing the violation (a failure report
    listing the violations is logged and written to the state dir; the
    stage fails on it), or its repair call hit a broken environment.
    Plain entries admit (whitelist semantics); a `!` section marker
    switches to inverted-allow entries, which deny (the implementation
    guard's protected set) — a file is a violation when it is denied AND no
    allow entry admits it (see guard_denied). The stage's identity for the
    repair instructions (its label and prompt template) rides the
    CW_GUARD_STAGE / CW_GUARD_TEMPLATE env entries the stage sets for its
    guard call."""
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("usage: guard-check.py <baseline-ref> <allowed-path>… "
              "[! <denied-path>…]")
        sys.exit(2)
    baseline = args[0]
    tail = args[1:]
    if "!" in tail:
        # the marker splits the tail: the plain entries before it admit, the
        # entries after it deny (the implementation guard's protected set)
        i = tail.index("!")
        allow, deny = tail[:i], [a for a in tail[i + 1:] if a]
    else:
        allow, deny = tail, []
    r = guard(baseline, allow, deny,
              stage=os.environ.get("CW_GUARD_STAGE", ""),
              template=os.environ.get("CW_GUARD_TEMPLATE", ""))
    sys.exit(0 if r.ok else 1)


def cw_state(name: str) -> str | None:
    """The stage-artifact state files — the oracle's stage-results
    channel: <RUNNER_TEMP>/cw/state/<trigger|pr>/<name>.txt.

    On this runner build a composite action's inner steps receive neither
    the with:→INPUT_* binding nor the job-level GITHUB_ENV values, so the
    file the triggering stage wrote is the authoritative source."""
    root = os.path.join(os.environ.get("RUNNER_TEMP", ""), "cw", "state")
    for d in ("trigger", "pr"):
        f = os.path.join(root, d, name + ".txt")
        if os.path.isfile(f):
            v = open(f).read().strip()
            if v:
                return v
    return None


def cw_input(name: str) -> str:
    """A stage input's value: INPUT_<name> first (a healthy runner's
    action-input binding), then CW_<name> (the job/step env the factory
    sets — on this runner build a composite action's with: values never
    reach its inner steps as INPUT_* at all), then the trigger artifact's
    state file, else a precise error."""
    n = name.upper().replace("-", "_")
    for key in (f"INPUT_{n}", f"CW_{n}"):
        v = os.environ.get(key)
        if v:
            return v
    v = cw_state(name)
    if v:
        return v
    raise SystemExit(
        f"::error::input '{name}' unbound (no INPUT_{n}, no CW_{n}, "
        f"no state file)")


def cw_input_opt(name: str) -> str | None:
    """Like cw_input but optional: None instead of an error."""
    n = name.upper().replace("-", "_")
    for key in (f"INPUT_{n}", f"CW_{n}"):
        v = os.environ.get(key)
        if v:
            return v
    return cw_state(name)
