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


def pi_invoke(
    model: str,
    system_prompt_file: str,
    prompt_file: str | None = None,
    context: list[str] | tuple[str, ...] = (),
    inject: list[str] | tuple[str, ...] = (),
    timeout: int = 21600,
    context_as_args: bool = False,
) -> subprocess.CompletedProcess:
    """One headless pi run. The backend comes from the pi configuration the
    setup stage wrote into the agent directory for the run — this never
    passes or overrides it (setup-pi contract). Only the model is selected
    here.

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
      - `context_as_args=True` — the extraction stage: the project files
        (the Gherkin oracle, the arc42 markdown, the README, the baseline
        diff) are handed to pi as @-file arguments — pi reads the named
        files as context before answering (setup-pi: "pi reads the project
        files as context"). The extraction needs the whole oracle, the
        arc42 and the baseline diff up front to keep the delta consistent
        with the existing scenarios.

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
    # — a context entry that does not exist is dropped, never passed (a
    # missing @-file would make pi's reader fail the call)
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
    tracked = subprocess.run(
        ["git", "diff", "--name-only", baseline, "--", "."],
        cwd=repo(), capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
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
      suite's compiled byproducts out of the revert list).
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


def guard(baseline: str, allow: list[str] | tuple[str, ...],
          deny: list[str] | tuple[str, ...] = ()) -> GuardResult:
    """The one shared guard idiom (plan §4.1): everything in the baseline
    diff that is not admitted (guard_denied) is reverted exactly (modified
    files checked out from the baseline, untracked ones cleaned), and the
    result is returned so the stage can re-run its generation. Invoked three
    times by the three check stages with different allowed paths — one script
    (guard-check.py), three calls; the implementation call passes the
    inverted-allow deny set (its lane is everything except the protected
    dirs), the others their plain allow sets."""
    allow = [a.rstrip("/") for a in allow if a]
    deny = [a.rstrip("/") for a in deny if a]
    violations = []
    for f in changed_files(baseline):
        if not guard_denied(f, allow, deny):
            continue
        violations.append(f)
    if not violations:
        log(f"guard: OK — only {' '.join(allow) or '(baseline)'} changed")
        return GuardResult(ok=True, violations=[])
    # Revert exactly the files that leaked — the operation depends on what the
    # baseline knew about each file:
    #   baseline knows it (a tracked file that was modified) → restore its
    #   baseline content;
    #   baseline does not know it (a file the stage added, committed or not)
    #   → remove it from the tree.
    for f in violations:
        exists_at_baseline = subprocess.run(
            ["git", "cat-file", "-e", f"{baseline}:{f}"],
            cwd=repo(), capture_output=True, text=True,
        ).returncode == 0
        if exists_at_baseline:
            subprocess.run(["git", "checkout", baseline, "--", f], cwd=repo(), check=True)
        elif subprocess.run(["git", "ls-files", "--", f], cwd=repo(),
                            capture_output=True, text=True).stdout.strip():
            subprocess.run(["git", "rm", "-f", "--", f], cwd=repo(), check=True)
        else:
            p = os.path.join(repo(), f)
            if os.path.isdir(p):
                subprocess.run(["git", "clean", "-fdq", "--", f], cwd=repo())
            elif os.path.exists(p):
                os.remove(p)
    log(f"::error::guard: REVERTED off-limits files: {' '.join(violations)}")
    return GuardResult(ok=False, violations=violations)


def commit_all(message: str) -> bool:
    """Commit whatever the stage produced (empty = no-op)."""
    subprocess.run(["git", "add", "-A"], cwd=repo(), check=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=repo(), capture_output=True, text=True)
    if not dirty.stdout.strip():
        return False
    subprocess.run(
        ["git", "commit", "-q", "-m", message],
        cwd=repo(), check=True,
    )
    return True


def push_branch(branch: str, force: bool = True) -> None:
    token = os.environ.get("GH_TOKEN", "")
    origin = f"https://x-access-token:{token}@github.com/{os.environ['GITHUB_REPOSITORY']}"
    args = ["git", "push"]
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
    r = subprocess.run(args, cwd=repo(), capture_output=True, text=True,
                       env=env)
    # rewrite any token in the URL back out of the log
    if r.returncode != 0:
        clean = (r.stderr or r.stdout).replace(token, "***") if token else (r.stderr or "")
        raise RuntimeError(f"git push failed: {clean.strip()[:300]}")


def git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    # Same GIT_CONFIG_* sanitisation as push_branch: a runner that leaks a
    # dangling GIT_CONFIG_KEY_i into the job env would poison every git
    # child otherwise.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_CONFIG_")}
    return subprocess.run(["git"] + args, cwd=repo(), capture_output=True,
                          text=True, check=check, env=env)


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
    exit 0 = clean stage, 1 = violations reverted (caller re-runs the
    stage). Plain entries admit (whitelist semantics); a `!` section marker
    switches to inverted-allow entries, which deny (the implementation
    guard's protected set) — a file is a violation when it is denied AND no
    allow entry admits it (see guard_denied)."""
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
    r = guard(baseline, allow, deny)
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
