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
import time


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


FASTMODE_THRESHOLD_DEFAULT = 5


def resolve_fastmode_threshold() -> int:
    """The fastmode threshold, resolved through the documented chain
    (chapter 3's settings flow): the reusable workflow's
    `fastmode-threshold` input's value first — the workflow's own binding
    `INPUT_FASTMODE_THRESHOLD` on a healthy runner, then
    `CW_FASTMODE_THRESHOLD`, the job-env entry the implement job relays
    from the input — then the 5-step code default: a consumer that leaves
    the input undeclared keeps the default, and a plan whose step count is
    at or above it keeps the standing one-step-at-a-time behaviour. No
    trigger-time validation guards this input (the trigger-validation
    scenario's Examples table covers the timeout pair only): a declared
    value resolves as-is through the chain, and a value that is not an
    integer number of steps is not a threshold — it is skipped for the
    next link of the chain, and for the default at its end."""
    for key in ("INPUT_FASTMODE_THRESHOLD", "CW_FASTMODE_THRESHOLD"):
        v = (os.environ.get(key) or "").strip()
        if not v:
            continue
        try:
            return int(v)
        except ValueError:
            log(f"::error::the declared fastmode threshold {v!r} is not an "
                f"integer number of steps — the value is skipped for the "
                f"{FASTMODE_THRESHOLD_DEFAULT}-step default")
    return FASTMODE_THRESHOLD_DEFAULT


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
    state dir — one value a file (`extension-env-<name>.txt`, beside
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
    account the commit's author). The consumers of the read are the run's
    programs, one apply each: every stage process (its entry snapshot,
    and the per-call apply its pi invocations and git children ride), the
    guard program (its own entry apply — a program like any other, its
    git children and its pi repair call included), and the workflow's
    inline step programs (each carries its own copy of the single git
    entry point, the copy applying the same recorded values to the git
    child's environment). A run without the provider recorded no file —
    the list is empty and no program sets anything."""
    root = os.path.join(os.environ.get("RUNNER_TEMP", ""), "cw",
                        "state", "trigger")
    try:
        names = os.listdir(root)
    except OSError:
        return []
    out = []
    for fname in sorted(names):
        if not (fname.startswith("extension-env-")
                and fname.endswith(".txt")):
            continue
        name = fname[len("extension-env-"):-len(".txt")]
        try:
            with open(os.path.join(root, fname), encoding="utf-8") as f:
                value = f.read().strip()
        except OSError:
            continue
        if value:
            out.append((name, value))
    return out


def apply_extension_env() -> list[str]:
    """The setup-pi stage's recorded extension env — its resolved values
    from a non-empty EXTENSION_ENV provider, each recorded as a state
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
    variable and the environment is unchanged. The same call serves the
    guard program's own entry (a program of the run like any stage: a
    stage that spawns it finds the values already fixed in the inherited
    environment — a no-op — and a standalone invocation finds the empty
    environment to fix, so its git children and its pi call carry the
    values in every process shape). The return is the list of the
    variables this call set — the entry snapshot's marker is built from
    it (a stage whose entry found the recorded values certified in the
    state dir carries that fact in its process environment for every
    later consumer of the relay, the commit-identity guard's declared
    check among them)."""
    applied = []
    for name, value in recorded_extension_env():
        if value and not os.environ.get(name):
            os.environ[name] = value
            applied.append(name)
    return applied


def _entry_snapshot_file() -> str:
    """The entry's own persistence — the path of the state file the
    stage's entry writes with the values it applied to the process
    environment, beside the trigger's recorded state. The root it
    lives in is the entry's trigger root, resolved through the entry's
    marker where the marker is valid (a marker naming a root this
    process's relay no longer points at is another scenario's — stale,
    like the guard rejects it), and through the canonical trigger dir
    where it is not (a process whose marker the host erased re-derives
    the root the same way the entry did)."""
    marker = os.environ.get("CW_EXT_ENV_APPLIED") or ""
    root, _, names = marker.partition("\x1f")
    rt = os.environ.get("RUNNER_TEMP", "")
    if not (names.strip() and root
            and (root == os.path.join(rt, "cw", "state", "trigger")
                 or not rt)):
        root = os.path.join(rt, "cw", "state", "trigger") if rt else ""
    if not root:
        return ""
    return os.path.join(root, "entry-applied-extension-env.txt")


def _read_entry_snapshot() -> dict[str, str]:
    """The values the stage's entry persisted after fixing them into
    the process environment — {name: value}, empty where the file is
    absent or reads empty. A file the process wrote itself: where the
    host resets the process's view of files it had previously read
    (the restored tree's files answer empty past the reset), the
    process's own write is the record the read answers — data here is
    the certificate the host's reset left standing, and an empty read
    is the diagnosis that the host took the process's own writes too.
    """
    path = _entry_snapshot_file()
    if not path or not os.path.isfile(path):
        return {}
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return {}
    values = {}
    for line in text.splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if name and value:
            values[name] = value
    return values


# provider → (declaration flag, recorded-value state name, job-env relay
# marker) — the state names ride the state dir with a .txt suffix (the
# writer's name); the check appends it when it tests the value file:
# the setup-pi stage records each declared value-carrying harness provider's
# declaration and its recorded value as state files in the run's state dir,
# on the same state-dir artefact channel the extension-env values ride
# (beside the trigger's recorded state; the cumulative artefact chain
# carries them to every later stage job, whose per-job Read trigger state
# relay exports the declaration and a single-line delivery marker into the
# job's env — the marker, never the value's content: the content is
# multi-line JSON, and the relay's GITHUB_ENV format is line-based).
HARNESS_PROVIDER_STATE = {
    "models": ("harness-models-declared", "harness-models",
               "CW_HARNESS_MODELS_DELIVERED"),
    "settings": ("harness-settings-declared", "harness-settings",
                 "CW_HARNESS_SETTINGS_DELIVERED"),
    "mcp": ("harness-mcp-declared", "harness-mcp",
            "CW_HARNESS_MCP_DELIVERED"),
}


# The bounded catch-up wait the stage's entry opens with (see
# delivery_check's docstring): this runner host's filesystem has been
# observed to lag its own writes — the download step reported complete
# (its digest verified) while the extraction's final entries were still
# materialising on disk, so the entry would otherwise read a
# half-restored state dir. Hold the entry until the state dir is
# quiescent AND every certified file's DATA has materialised: the
# certification is a content read — this host's file entries and size
# fields have been observed to land ahead of their data, and a file
# counts materialised only when a read of it returns non-empty content
# (a healthy, complete tree settles on the first stable sample, a few
# hundred milliseconds; a tree the filesystem is still catching up keeps
# the wait open while its data lands; and a tree that never catches up
# runs the bound out — the wait then hands the data-less names back and
# the check fails the providers those files belong to, loudly, at the
# entry). The wait must never mask the check or fail the stage itself.
_SETTLE_POLL_SECONDS = 0.1
_SETTLE_STABLE_SAMPLES = 3
_SETTLE_DEADLINE_SECONDS = 30.0


def _wait_for_restored_tree(stage: str, root: str, declared) -> list[str]:
    """The bounded catch-up wait the shared stage-entry check opens with.

    Returns the names of the state files whose ENTRY is present in the
    restored dir but whose DATA still reads empty when the wait ends —
    this host's data-lags-its-entries shape (run 44601846177's extract
    stage: every value file's entry and size field read non-zero the
    moment the download step unpacked them, while a read of the file's
    content returned empty for the stage process's whole life — a later
    step's fresh process saw the data). The caller (the check) routes
    the providers those names belong to its declared-but-lost failure
    instead of passing them valueless.

    The certification is a content read, never a metadata test: a file
    counts materialised only when a read of it returns non-empty
    content, and the fingerprint rides the read content — a file whose
    entry and size landed but whose data has not keeps the wait open
    while its data materialises (and a file whose data lands mid-wait
    flips the fingerprint, resetting the stability count). A tree that
    never materialises its certified files runs the bound out: the wait
    then hands the data-less names back, and the check fails the stage
    at its entry on them — loudly, before the stage spends a pi call on
    a run that would commit without its identity.
    """
    expected = {value_file + ".txt"
                for _provider, (flag, value_file, _marker)
                in HARNESS_PROVIDER_STATE.items()
                if declared(flag, "CW_" + flag.replace("-", "_").upper())}
    ext_declared = declared("ext-env-declared", "CW_EXT_ENV_DECLARED")

    def _certified_files(snapshot: set) -> list[str]:
        # the files the wait certifies: the declared providers' value
        # files, the extension group's value files where the provider is
        # declared, and every provider declaration flag whose entry is
        # visible (an unreadable flag is a loss of the declaration
        # itself — the check's declared probe would otherwise read
        # absent and pass the provider vacuously)
        fns = [f for f in expected if f in snapshot]
        if ext_declared:
            fns += [f for f in sorted(snapshot)
                    if f.startswith("extension-env-")
                    and f.endswith(".txt")]
        fns += [f for f in sorted(snapshot)
                if f.endswith("-declared.txt")]
        return sorted(set(fns))

    try:
        def read_data(fname: str) -> str:
            try:
                with open(os.path.join(root, fname),
                          encoding="utf-8") as fh:
                    return fh.read()
            except OSError:
                return ""

        def materialised(snapshot: set) -> tuple:
            # every certified file reads its data back non-empty; returns
            # (all materialised, the names that are not)
            missing = []
            for f in _certified_files(snapshot):
                if not read_data(f).strip():
                    missing.append(f)
            return (not missing, missing)

        def complete(snapshot: set, mat: tuple) -> bool:
            if not expected <= snapshot:
                return False
            if ext_declared:
                return (any(f.startswith("extension-env-")
                            and f.endswith(".txt") for f in snapshot)
                        and mat[0])
            return mat[0] if _certified_files(snapshot) else True

        def fingerprint(snapshot: set):
            # the certified files' read CONTENT rides the fingerprint, so
            # data still materialising (or landing mid-wait) keeps the
            # wait open until it settles
            contents = tuple((f, read_data(f))
                             for f in _certified_files(snapshot))
            return (snapshot, contents)

        prev = None
        stable = 0
        seen = set()
        mat = (True, [])
        deadline = time.monotonic() + _SETTLE_DEADLINE_SECONDS
        while time.monotonic() < deadline:
            try:
                snap = set(os.listdir(root))
            except OSError:
                snap = set()
            key = fingerprint(snap)
            mat = materialised(snap)
            if key == prev:
                stable += 1
            else:
                prev = key
                stable = 0
            seen |= snap
            if stable >= _SETTLE_STABLE_SAMPLES and complete(seen, mat):
                log(f"{stage}: restored state dir settled and complete "
                    f"({len(snap)} file(s)) — the entry check "
                    f"reads a full dir, and every certified file's "
                    f"data read non-empty")
                return []
            time.sleep(_SETTLE_POLL_SECONDS)
        missing = expected - (prev[0] if prev else set())
        missing_data = mat[1] if prev else []
        if missing or missing_data:
            log(f"::warning::{stage} — the restored state dir had not "
                f"caught up within {int(_SETTLE_DEADLINE_SECONDS)}s "
                f"(entries still missing {sorted(missing) or '—'}; "
                f"present but data-less {missing_data or '—'}); the "
                f"entry check fails the providers those files belong "
                f"to instead of passing them valueless")
        return missing_data
    except Exception:
        # the wait must never mask the check or fail the stage itself —
        # a wait that cannot certify hands back no data-less names, and
        # the check runs against whatever is on disk
        return []

def delivery_check(stage: str) -> None:
    """The shared stage-entry delivery check — every stage job runs it at
    its entry, before any stage work or pi call of the stage: for each of
    the run's four harness providers (the model configuration, the
    additional packages, the MCP configuration, the extension's
    environment), the ones **declared** for the run must have their
    recorded values **restored into the job** — both relay halves: the
    state files present in the restored state dir (the artefact-channel
    half; the setup stage's recorded values ride the cumulative artefact
    chain there), and the values carried in the job's env (the per-job
    Read trigger state relay's in-process half).

    A declared provider whose recorded values did not arrive — neither
    half delivered — **fails the stage at its entry**, before any pi call
    of the stage is spent: the explicit error names the provider and
    reports each relay half — the job's environment and the state dir —
    and the run's artefact log names the relay loss as the failure's
    cause (the stage's artefact carries the one-line reason). A provider
    that is **not** declared (flag absent or false, no state file
    expected) passes the check: the run is unchanged — no files, no
    flag, no spurious failure. A harness that would otherwise **fall back
    silently** (an element that would run absent when its provider is
    absent — the additional packages, the MCP servers, the extension's
    environment) is treated as the same class of loss: a declared-but-
    lost provider fails the entry check instead of degrading quietly.

    The setup-pi stage is the **writer** of the harness providers' recorded
    state: at its entry the values it records during its work do not yet
    exist in the run's state dir, so its own entry check verifies no prior
    delivery and passes — the every-stage entry uniformity keeps the gate
    at the writer's entry too, and the check has its teeth on the other
    stage jobs, whose entry checks verify the setup stage's delivery.

    The check also records the stage's delivery line on the stage-summary
    channel — one line per stage that ran the check, in the three forms the
    delivery contract names ("extension env: delivered (N values)",
    "extension env: missing (provider declared)",
    "extension env: n/a (no provider)"): the line is written on both the
    pass and the fail path — a declared provider whose recorded values did
    not arrive fails the stage at its entry, and its line must still ride
    the artefact the failed job uploads — and the cumulative channel rides
    the run's state artefacts, so the report stage's final status and the
    run's artefact log carry the full delivery picture, the line of every
    stage that ran. The writer's own line it records at its completion
    point (its entry check is the vacuous pass): the writer's line
    reflects the values the stage recorded for the run —
    "delivered (N values)", or "n/a (no provider)" where the provider is
    absent.

    The entry opens with a bounded catch-up wait on the restored state
    dir: on this runner host the filesystem has been observed to lag its
    own writes — the download step reported complete (its digest
    verified) while the extraction's final entries were still
    materialising on disk, so the entry check would otherwise read a
    half-restored dir (the run's own artefacts carry the byte-complete
    zip beside the stage's missing files, which surface only into the
    job's later upload). The wait holds the entry until the dir is
    quiescent AND every certified file's data has materialised — the
    certification is a content read, never a metadata test: this host's
    file entries and size fields have been observed to land ahead of
    their data (run 44601846177's extract stage: every value file's
    entry and size read non-zero the moment the download step unpacked
    them while a read of the content returned empty, the entry's
    snapshot fixed nothing, the check passed on the entries' presence,
    and the stage spent its full pi run before its commit's child died
    on the missing identity). A file counts materialised only when a
    read of it returns non-empty content; a healthy, complete tree
    settles on the first stable sample (a few hundred milliseconds), a
    tree the filesystem is still catching up keeps the wait open while
    its data lands, and a tree that never catches up runs the bound out
    — the wait then hands the data-less names back and the check fails
    the providers those files belong to, loudly, at the entry. The wait
    can never mask the check: any error of its own hands back no
    data-less names and lets the check run against whatever is on
    disk.
    """
    root = os.path.join(os.environ.get("RUNNER_TEMP", ""), "cw", "state",
                        "trigger")

    def declared(flag: str, env_key: str) -> bool:
        # the declaration itself rides both relay halves: the trigger's
        # state file is the authoritative source, the per-job env relay
        # its in-process twin
        return (cw_state(flag) or os.environ.get(env_key) or "") \
            .strip() == "true"

    # every stage job's entry opens with the bounded catch-up wait
    # (writer's entry included — its own work reads the trigger's state
    # files, the same files this host's filesystem lands late): hold
    # the entry until the state dir is quiescent AND every declared
    # value file has landed — entry, and its data, on disk — then
    # re-read the dir the check reads.
    # the wait's certification is a content read (a file counts
    # materialised only when a read of it returns non-empty content —
    # this host's file entries and size fields have been observed to
    # land ahead of their data): the names it hands back are the state
    # files whose entry is present but whose data did not materialise
    # within the settle window — the providers those files belong to
    # are routed to the declared-but-lost failure below, never passed
    # valueless
    missing_data = set(_wait_for_restored_tree(stage, root, declared))

    # The entry snapshot of the recorded extension env into this
    # process, taken at the one moment the wait has certified the
    # restored tree: the values are fixed in the process environment
    # here, and every later consumer of the relay in this process reads
    # that — the git children (their env is a snapshot of os.environ,
    # taken at each call), the commit-identity guard's declared probe.
    # No consumer re-reads the state dir for a value it needs at process
    # scope: this host's filesystem has shown it cannot be re-trusted on
    # that timescale (a run whose tree was complete and proven at entry
    # still committed minutes later against a fresh re-read that
    # answered empty — the entry's snapshot makes the later read a
    # no-op fallback). The marker the snapshot records is in-process
    # ground truth the relay's own files cannot un-make, and the guard's
    # declared check accepts it beside the two relay halves. One
    # consumer does re-read — and only the entry's own persistence
    # file, never the relay's: this host has since reset a long-lived
    # stage process's view mid-run (the applied values and the marker
    # erased together, the process's reads of the restored tree's files
    # answering empty, a fresh process on the same host reading them
    # fine) — where the child-env builders find the marker gone, they
    # re-derive the applied values from the file the process wrote
    # itself (a write the host's reset may leave standing), re-fix them
    # into the process environment, and re-set the marker — the
    # process's view made whole again, and a later commit whose identity
    # still does not resolve fails the diagnosis's marker branch naming
    # the mid-run loss, never the raw fatal. Where the file itself
    # reads empty, no in-process record of the entry survives, and the
    # failure then names the host's process-view reset as the cause.
    # A writer
    # stage's entry takes the same snapshot and finds nothing (its own
    # recorded values do not exist at its own entry) — the uniformity
    # holds, the marker is simply absent there. A tree genuinely lost
    # at entry takes no snapshot and fails the check below, loudly, as
    # before: the wait and the snapshot can certify only what is on
    # disk, and they never mask an absence.
    applied = apply_extension_env()
    if applied:
        # The marker encodes the state dir root this entry used, beside
        # the variables it fixed: a marker naming a root this process's
        # relay no longer points at is another scenario's (the validator
        # suite reuses one process across its scenarios) — stale, and the
        # guard rejects it. The entry that set the marker is the only
        # one the marker certifies.
        os.environ["CW_EXT_ENV_APPLIED"] = root + "\x1f" \
            + ",".join(sorted(applied))
        # The entry's own persistence — the values the entry fixed into
        # the process environment, also written to a state file of the
        # process's own (a write through the process's own write path,
        # beside the relay's files the host's reset empties on re-read;
        # the name stays out of the provider's value-file glob and the
        # declaration flags' pattern — the delivery count and the
        # check's verdicts never see it as a provider's file). A
        # child-env build later in the process, finding the marker the
        # host erased, re-derives the applied values from this file
        # (leave-untouched) and re-sets the marker — the process's view
        # made whole again; where the file itself reads empty, the
        # failure names the host's process-view reset.
        try:
            with open(os.path.join(root, "entry-applied-extension-env.txt"),
                      "w", encoding="utf-8") as f:
                f.write("# the stage's entry applied these extension-env "
                        "values to its process environment\n"
                        "# (the in-process environment is not a durable "
                        "store — a host may reset a long-lived "
                        "process's view mid-run)\n")
                for name in sorted(applied):
                    f.write(f"{name}={os.environ.get(name, '')}\n")
        except OSError:
            pass  # a persistence the host denies is no gate: the marker
            # and the check's verdict stand without it
    else:
        # an entry that certifies nothing retracts a stale marker an
        # earlier entry in this process left behind — the marker's
        # scope is the entry that set it, and a later entry re-derives
        # it wholly from its own view of the state dir
        os.environ.pop("CW_EXT_ENV_APPLIED", None)

    if "setup-pi" in stage:
        log(f"{stage}: entry delivery check — the setup-pi stage is the "
            f"harness writer: the providers' recorded values it writes "
            f"during its work do not yet exist at its own entry, so its "
            f"entry check verifies no prior delivery (a vacuous pass); "
            f"the other stage jobs' entry checks verify this stage's "
            f"recorded values arrived")
        return
    try:
        present = set(os.listdir(root))
    except OSError:
        present = set()

    lost = []
    # the extension's environment — its declaration is the trigger's
    # presence-only provider-declaration flag; its recorded values are
    # the extension-env-*.txt state files the setup stage wrote
    ext_outcome = "n/a (no provider)"
    ext_flagless = ("ext-env-declared.txt" in present
                    and "ext-env-declared.txt" in missing_data)
    if ext_flagless:
        # the provider's declaration flag is present but unreadable: the
        # declared probe cannot be trusted — it would read the flag empty
        # and pass the provider vacuously, and the stage would run
        # valueless, dying at its commit on the missing identity. The
        # flag's entry is present: the provider WAS declared, and an
        # unreadable declaration is a relay loss the check names
        ext_outcome = "missing (provider declared)"
        lost.append(
            ("extension-env",
             "declared for the run, but its declaration flag "
             f"ext-env-declared.txt is present in the restored state dir "
             f"{root} with unreadable data — the declared probe cannot be "
             "trusted; treated as a relay loss, the stage fails at its "
             "entry"))
    elif declared("ext-env-declared", "CW_EXT_ENV_DECLARED"):
        ext_files = sorted(f for f in present
                           if f.startswith("extension-env-")
                           and f.endswith(".txt"))
        ext_data_missing = [f for f in ext_files if f in missing_data]
        state_half = bool(ext_files) and not ext_data_missing
        env_half = bool((os.environ.get("CW_EXT_ENV_KEYS") or "").strip())
        if state_half or env_half:
            # the delivered value count — the values the entry's snapshot
            # actually fixed into this process's environment (the wait
            # certified their data materialised, so that count is truth);
            # where the state-file half is the one that was lost, it is
            # the keys the per-job relay exported into the job's env
            n = (len(applied) if state_half
                 else len([k for k in
                           (os.environ.get("CW_EXT_ENV_KEYS") or "")
                           .split(",") if k]))
            ext_outcome = f"delivered ({n} values)"
            state_desc = (f"delivered ({len(ext_files)} value file(s))"
                          if state_half else "lost")
            log(f"{stage}: entry delivery check — extension-env declared, "
                f"the recorded values arrived (state-dir half: {state_desc}; "
                f"job-env half: {'delivered' if env_half else 'lost'})")
        else:
            ext_outcome = "missing (provider declared)"
            if ext_files:
                # the second shape of the same loss: the value files'
                # entries ARE present in the restored state dir, but
                # their data did not materialise within the settle window
                # — the runner host's file data lagged its entries past
                # the wait's bound (run 44601846177: the entry's
                # snapshot read every value empty, the check passed on
                # the entries' presence, and the stage spent its full pi
                # run before its commit's child died on the missing
                # identity)
                shape = ("the value files' entries are present in the "
                         "restored state dir but their data did not "
                         f"materialise within the settle window "
                         f"({', '.join(ext_data_missing)} still read "
                         "empty — the runner host's file data lagged its "
                         "entries); treated as lost")
            else:
                shape = ("no extension-env-*.txt state file in the "
                         f"restored state dir {root}")
            lost.append(
                ("extension-env",
                 "declared for the run, but its recorded values were not "
                 f"restored into the job — state-dir half lost ({shape}); "
                 "job-env half lost (CW_EXT_ENV_KEYS unset — the per-job "
                 "Read trigger state relay exported no recorded value)"))
    # the stage's delivery line on the stage-summary channel — written
    # before the check's verdict (a declared-but-lost provider fails the
    # stage at its entry, and its line must still ride the artefact the
    # failed job uploads); the report's stage-outcome table renders it
    # beside the stage's outcome lines
    record_stage_outcome(f"{stage}: extension env: {ext_outcome}")
    # the value-carrying providers — each declared by a state file the
    # setup stage recorded on the same channel; a harness that would fall
    # back silently when its provider is absent is the same class of loss
    for provider, (flag, value_file, marker) in HARNESS_PROVIDER_STATE.items():
        flagf = flag + ".txt"
        if flagf in present and flagf in missing_data:
            # the provider's declaration flag is present but unreadable —
            # the declared probe cannot be trusted (it would read the
            # flag empty and pass the provider vacuously); an unreadable
            # declaration is a relay loss the check names
            lost.append(
                (provider,
                 f"declared flag {flagf} present in the restored state "
                 f"dir with unreadable data — the declared probe cannot "
                 "be trusted; treated as a relay loss, the stage fails "
                 "at its entry"))
            continue
        if not declared(flag, "CW_" + flag.replace("-", "_").upper()):
            log(f"{stage}: entry delivery check — {provider} not declared "
                f"for the run (no provider) — the check passes it, the "
                f"run's documented fall-through for the element is "
                f"unchanged (no files, no flag, no spurious failure)")
            continue
        # the state file on disk carries the .txt suffix (the writer's
        # name); the tuple's value_file is the bare state name
        state_half = (flagf and (value_file + ".txt") in present
                      and (value_file + ".txt") not in missing_data)
        env_half = bool((os.environ.get(marker) or "").strip())
        if state_half or env_half:
            log(f"{stage}: entry delivery check — {provider} declared, "
                f"the recorded values arrived (state-dir half: "
                f"{'delivered' if state_half else 'lost'}; job-env half: "
                f"{'delivered' if env_half else 'lost'})")
        else:
            vfile = value_file + ".txt"
            if vfile in present:
                # the second shape of the same loss: the state file's
                # entry is present but its data did not materialise within
                # the settle window (the runner host's file data lagged
                # its entries) — treated as lost
                shape = (f"the recorded state file {vfile} is present "
                         "but its data did not materialise within the "
                         "settle window — it still reads empty (the "
                         "runner host's file data lagged its entries); "
                         "treated as lost")
            else:
                shape = (f"the recorded state file {vfile} is absent "
                         f"from the restored state dir {root}")
            lost.append(
                (provider,
                 "declared for the run, but its recorded values were not "
                 f"restored into the job — state-dir half lost ({shape}); "
                 f"job-env half lost ({marker} unset — the per-job Read "
                 "trigger state relay exported no delivery marker)"))
    if lost:
        # the failure rides the documented crash-diagnostics channel — the
        # stage's artefact carries the one-line reason (chapter 9), and a
        # controlled sys.exit is not a crash (the crash hook's diagnosis
        # is for uncaught exceptions; this is the check's verdict)
        detail = "\n".join(f"  - {name}: {why}" for name, why in lost)
        names = " ".join(name for name, _ in lost)
        report = (f"the delivery check at the stage's entry found the "
                  f"declared provider(s) {names} recorded values not "
                  f"restored into the job — the relay loss is the "
                  f"failure's cause")
        log(f"::error::{stage} — the delivery check at the stage's entry: "
            f"the declared harness provider(s) {names} were not restored "
            f"into this job. The check logs which relay half delivered "
            f"what (the job's environment and the state dir):\n{detail}\n"
            f"The stage fails at its entry, before any pi call of the "
            f"stage is spent; a harness that would otherwise fall back "
            f"silently is treated as the same class of loss.")
        d = state_dir()
        os.makedirs(d, exist_ok=True)
        try:
            with open(os.path.join(d, "stage-fail-reason.txt"), "w") as f:
                f.write(f"{stage}: FAILED — {report}\n")
        except OSError:
            pass  # the job-visible line survives
        sys.exit(1)
    log(f"{stage}: entry delivery check — passed: every declared harness "
        f"provider's recorded values are restored into the job; a run "
        f"whose extension-env provider is absent is unchanged by the "
        f"check (no files, no flag, no spurious failure)")


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
    # The entry's persistence re-applied to the process environment:
    # the pi child inherits the process environment (the spawn passes
    # no env of its own), and a host that has since reset that view —
    # the entry's marker gone, the restored files' reads answering
    # empty — would run the call valueless. Where the marker is gone
    # and the file the process wrote itself at its entry reads, re-fix
    # the applied values into the process environment (a value the
    # environment still carries wins) and re-set the entry's marker on
    # the values it names — the process's view made whole again
    if not os.environ.get("CW_EXT_ENV_APPLIED"):
        applied = _read_entry_snapshot()
        if applied:
            for name, value in applied.items():
                if value and not os.environ.get(name):
                    os.environ[name] = value
            os.environ["CW_EXT_ENV_APPLIED"] = \
                os.path.dirname(_entry_snapshot_file()) + "\x1f" \
                + ",".join(sorted(applied))
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
    """Commit whatever the stage produced (empty = no-op).

    A commit that dies on a stale index.lock — this runner build loses
    file operations: the unlink of a lock a completed git child released
    never lands, so the next git child in the same repository dies on the
    file the prior child believes it released — clears the lock and
    retries the commit once. The stage's process is the repository's only
    git actor at this point (the pi call completed before the commit; the
    guard runs after it), so clearing a lock the failure's text names is
    safe. The single retry and the signature gate keep a genuinely broken
    repository failing loud rather than looping: a failure without the
    stale-lock signature re-raises as-is, and a second failed commit
    fails the stage.
    """
    git_exec(["add", "-A"], cwd=repo(), check=True)
    dirty = git_exec(["status", "--porcelain"], cwd=repo(),
                     capture_output=True, text=True)
    if not dirty.stdout.strip():
        return False
    try:
        git_exec(["commit", "-q", "-m", message], cwd=repo(),
                 check=True)
    except RuntimeError as e:
        if "index.lock" in str(e) and "File exists" in str(e):
            _clear_stale_index_lock()
            log("the commit died on a stale index.lock — the released "
                "unlink never landed on this runner build; cleared, "
                "retrying the commit once (bounded)")
            git_exec(["commit", "-q", "-m", message], cwd=repo(),
                     check=True)
        else:
            raise
    return True


def _clear_stale_index_lock() -> None:
    """Clear a stale index.lock the failure's text named.

    The lock lives in the repository's git dir — for a worktree that is
    the dir its .git file names, not the worktree's own .git file."""
    gd = os.path.join(repo(), ".git")
    if os.path.isfile(gd):
        try:
            line = open(gd, encoding="utf-8").readline().strip()
            if line.startswith("gitdir:"):
                gd = line[len("gitdir:"):].strip()
        except OSError:
            pass
    lock = os.path.join(gd, "index.lock")
    if os.path.exists(lock):
        os.remove(lock)


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

    The entry point also guards the commit's identity: a commit whose
    identity cannot be resolved is a factory-level failure, not the raw
    git "please tell me who you are" fatal. Where the extension-env
    provider WAS declared for the run and its values did not arrive in
    the job (neither relay half delivered the identity variables the
    run's commits resolve from — GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL are
    absent from the child's environment), and the runner's own git
    configuration (the user-global configuration the fallback the
    provider's variables override — probed read-only with a sanitised
    env) carries no commit identity either, the entry point fails the
    commit with the factory-level diagnosis that names the declared
    provider whose values never arrived — the commit child never spawns,
    so the raw git fatal is not the outermost failure signal of the run,
    and the diagnosis rides the stage's crash-diagnostics channel (the
    stage's artefact carries the one-line reason). The factory writes no
    identity of its own: no GIT_AUTHOR_* is composed into a child's
    environment by the diagnosis, and a provider that is not declared
    keeps the documented commit-identity behaviour exactly (where the
    provider is empty or absent the run's commit identity is whatever
    the runner's own git configuration provides).
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
    # The entry's persistence re-applied: a host that resets this
    # process's view mid-run erases the values the entry fixed (and the
    # marker with them), and this call's fresh re-read of the restored
    # files answers empty — the child would go valueless and the commit
    # die on an identity the entry certified. The file the process wrote
    # itself at its entry is the surviving certificate: where the marker
    # is gone, re-derive the applied values from it — into the process
    # environment (the process's view made whole for every later call)
    # and into the child's environment this call is building (a value
    # the environment still carries wins — leave-untouched) — and
    # re-set the entry's marker on the values it names
    if not os.environ.get("CW_EXT_ENV_APPLIED"):
        applied = _read_entry_snapshot()
        if applied:
            for name, value in applied.items():
                if value and not os.environ.get(name):
                    os.environ[name] = value
                if value and not env.get(name):
                    env[name] = value
            os.environ["CW_EXT_ENV_APPLIED"] = \
                os.path.dirname(_entry_snapshot_file()) + "\x1f" \
                + ",".join(sorted(applied))
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
    # the factory-level no-identity diagnosis — a commit whose identity
    # cannot be resolved fails with the diagnosis that names the lost
    # provider, before the commit child is handed to subprocess.run
    # (the raw git "tell me who you are" fatal is not the outermost
    # failure signal of the run; the factory writes no identity of its
    # own — see the docstring)
    if argv and argv[0] == "commit":
        _diagnose_unresolvable_commit_identity(env)
    # the entry point captures the child's streams itself where the
    # caller did not redirect them: on this runner build the job's logs
    # ghost and the state dir's diagnostics can vanish from the upload,
    # so a failed child's own words must ride in the raised error's
    # message (the crash channel), not in a stream the runner pointed
    # somewhere the artefact never reaches
    if ("capture_output" not in kwargs and "stdout" not in kwargs
            and "stderr" not in kwargs):
        kwargs["capture_output"] = True
    try:
        return subprocess.run(["git"] + list(argv), **kwargs)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(_git_failure_message(argv, e)) from e


def _git_failure_message(argv: list[str],
                          e: subprocess.CalledProcessError) -> str:
    """The child's own words on why git died.

    The raw CalledProcessError carries only 'returned non-zero exit
    status N'; the entry point raises carrying the child's stderr — the
    git fatal that names the cause (a stale lock a released unlink never
    landed, a dubious-ownership refusal, a configuration fatal), the run's
    token redacted out of it (a push URL echo), tailed — the last lines
    are the diagnosis, not the progress. The message rides the stage's
    crash channel and its console, so the artefact names the cause where
    the job log ghosts. A commit that dies on an identity the entry
    certified — the host having since reset the process's view, the
    entry's marker gone and its own snapshot file reading empty — adds
    the host's process-view reset to the message, so the artefact names
    the cause's cause (a runner-host reset the factory cannot recover
    from in-process) beside the fatal it produced."""
    out = e.stderr if e.stderr is not None else e.stdout
    if out is None:
        out = e.output
    if isinstance(out, bytes):
        out = out.decode("utf-8", "replace")
    if out:
        token = os.environ.get("GH_TOKEN", "")
        if token:
            out = out.replace(token, "***")
        out = " ".join(line.strip() for line in out.splitlines()
                       if line.strip())
        msg = (f"git {argv[0]} failed (exit {e.returncode}): "
               + out[-400:])
    else:
        msg = (f"git {argv[0]} failed (exit {e.returncode}) "
               "with no captured output")
    if (argv and argv[0] == "commit"
            and "Committer identity unknown" in (out or "")
            and not os.environ.get("CW_EXT_ENV_APPLIED")
            and not _read_entry_snapshot()):
        # The host's process-view reset, named: the entry's own
        # persistence — this process's write of the values it
        # certified at its entry — reads empty too, so no in-process
        # record of the entry survives. A fresh process on the same
        # host reads the restored tree fine (the upload proves it);
        # the reset is of the long-lived process's view, and it is the
        # runner host's to make whole, not the factory's
        msg += (" — the entry's own snapshot file (this process's write "
                "of the values it certified at its entry) reads empty "
                "now too: this host has reset the long-lived process's "
                "view — its environment reverted to the step's launch "
                "state and its reads of files it had read non-empty "
                "answer empty, while a fresh process on the same host "
                "reads them fine. A runner-host process-view reset the "
                "factory cannot recover from in-process")
    return msg


def _diagnose_unresolvable_commit_identity(env: dict) -> None:
    """The factory-level diagnosis for a commit whose identity cannot be
    resolved — the guard the git entry point applies to a commit call:
    where the extension-env provider was declared for the run and its
    values did not arrive in the job, and the runner's own git
    configuration carries no commit identity either, the commit fails
    with the diagnosis that names the declared provider whose values
    never arrived (the run's commit identity is the provider's, and a
    declared provider whose values never arrived is the cause).

    The probe the diagnosis runs: the commit's identity resolves in the
    child's environment (the provider's values applied by the entry
    point, either relay half, or a value the runner's environment
    already carries) before any probe runs — the diagnosis needs no
    probe where the identity resolves in env. Where it does not, the
    runner's own git configuration is probed read-only — a config query
    on the user-global scope (the configuration the scenario names as
    the fallback the provider's variables override), on an env
    sanitised of any leaked GIT_CONFIG_* entries (a dangling key the
    count never fills would make git die on the missing key before the
    answer). A probe that cannot answer (no git, a config that hangs)
    is treated as "no identity in the runner's configuration" — the
    diagnosis's conservative direction: where the provider was
    declared, a commit that cannot resolve an identity is a relay loss
    the factory names, never a silent degradation onto an identity the
    run did not provide.

    The diagnosis fires only where the provider was DECLARED for the
    run: an undeclared provider keeps the documented commit-identity
    behaviour exactly — where the provider is empty or absent the run's
    commit identity is whatever the runner's own git configuration
    provides, and a runner whose configuration carries none meets git's
    own fatal as the run's own misconfiguration. The factory writes no
    identity of its own: the diagnosis raises — it composes no
    GIT_AUTHOR_* of its own into any child's environment — and the
    raise rides the stage's crash-diagnostics channel, which persists
    the one-line reason to the stage's artefact. The two forms the
    diagnosis takes: a relay loss (the declared provider's values
    never arrived — the entry check's declared-but-lost finding)
    and a provider-content gap (the entry's snapshot certified
    values into the process, yet none of its recorded variables
    resolves a commit identity — the marker's root scoping keeps a
    marker another scenario's entry left in a reused process from
    answering for this one).
    """
    if ((env.get("GIT_AUTHOR_NAME") or "").strip()
            and (env.get("GIT_AUTHOR_EMAIL") or "").strip()):
        return  # the identity resolves in the child's environment
    probe_env = {k: v for k, v in env.items()
                 if not k.startswith("GIT_CONFIG_")}
    has_identity = False
    try:
        for key in ("user.name", "user.email"):
            probe = ["config", "--global", key]
            r = subprocess.run(["git"] + probe, capture_output=True,
                               text=True, env=probe_env, timeout=30)
            if r.returncode == 0 and (r.stdout or "").strip():
                has_identity = True
                break
    except (OSError, subprocess.SubprocessError):
        pass  # a probe that cannot answer: the diagnosis's direction
    if has_identity:
        return  # the runner's own configuration resolves the identity
    # The entry snapshot's marker is the third declared source — the
    # in-process ground truth the stage fixed at its entry, the one the
    # relay's own files cannot un-make when this host's filesystem
    # answers a later re-read empty. The marker encodes the state dir
    # root its entry used: a marker naming a root this process's relay
    # no longer points at is another scenario's (the validator's suite
    # reuses one process across its scenarios) — stale, rejected. Where
    # the current root cannot be derived at all (RUNNER_TEMP itself lost
    # from the process environment — the shape this host has shown), the
    # entry's certified root is the best available truth: the marker
    # stands, and a commit that still cannot resolve an identity is a
    # loss the factory names, never a raw git fatal
    marker = os.environ.get("CW_EXT_ENV_APPLIED") or ""
    marker_root, _, marker_names = marker.partition("\x1f")
    _rt = os.environ.get("RUNNER_TEMP", "")
    marker_valid = bool(marker_names.strip()) and bool(marker_root) \
        and (marker_root == os.path.join(_rt, "cw", "state", "trigger")
             or not _rt)
    declared = ((cw_state("ext-env-declared")
                 or os.environ.get("CW_EXT_ENV_DECLARED") or "").strip()
                == "true"
                or marker_valid)
    if not declared:
        return  # an undeclared provider keeps the documented behaviour
    if marker_valid:
        # the entry snapshot certified the provider's values into this
        # process — a commit that still cannot resolve an identity is
        # not a relay loss, it is a provider-content gap: none of the
        # declared provider's recorded variables is the commit identity
        raise RuntimeError(
            "git commit cannot resolve a commit identity: the extension-env "
            "provider was declared for the run and its values were certified "
            "into this process at the stage's entry, yet none of its recorded "
            "variables resolves a commit identity (no GIT_AUTHOR_NAME / "
            "GIT_AUTHOR_EMAIL among them, and the runner's own git "
            "configuration carries none) — the provider's content is the "
            "run's commit identity's source; the factory writes no identity "
            "of its own")
    raise RuntimeError(
        "git commit cannot resolve a commit identity: the extension-env "
        "provider was declared for the run and its values never arrived "
        "in this job (the entry delivery check's relay loss — neither "
        "the recorded state files nor the per-job env relay delivered "
        "them), and the runner's own git configuration carries no commit "
        "identity — the declared provider is the run's commit identity's "
        "source; the factory writes no identity of its own")


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
    guard call.

    The program takes the relay's entry apply into its OWN process at its
    own entry, before any CLI call of it: the guard's git children (the
    detection's diff/ls-files, the repair's commit) and its pi repair call
    must carry the provider's values in every process shape the program
    runs in — a stage that spawns the guard hands it the stage's process
    environment (whose entry already snapshotted the recorded values: the
    apply's leave-untouched rule makes it a no-op there), while a
    standalone invocation (the degenerate checkout, a developer's hand)
    has no inheriting spawner — the apply reads the recorded values from
    the run's state dir at the program's entry and fixes them in the
    program's process environment, so every CLI the program then spawns
    carries them (the every-program half of the relay's every-step
    contract: EXTENSION_ENV present in every call the run makes, in
    every program that makes a call)."""
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
    # the program's own entry apply of the recorded extension env into its
    # own process (the docstring's every-program half): the stage-spawned
    # form finds the values already present in the environment the stage
    # handed it (a no-op — the stage's entry snapshot carried them into
    # the spawner's process environment), the standalone form finds an
    # empty environment and fixes the recorded values from the run's state
    # dir — after which every git child and pi call of the program builds
    # its environment from a process that carries them
    apply_extension_env()
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
