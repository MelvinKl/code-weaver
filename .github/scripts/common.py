"""Shared plumbing for the code-weaver stage actions.

Contract every stage script keeps:
  - working state lives in $RUNNER_TEMP/cw — NEVER in the repo tree
    (the reporting requirement: nothing under test-results/ is ever committed)
  - every loop respects MAX_LOOPS and MAX_TOKENS; 0 means no cap
    (the safety requirement: every loop respects its cap)
  - pi is pre-installed & pre-configured in the runner environment —
    stages invoke it, they never install or reconfigure it
"""
from __future__ import annotations

import dataclasses
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
    is never written into the repo tree."""
    print(msg, flush=True)


class CapReached(SystemExit):
    def __init__(self, which: str, detail: str):
        super().__init__(f"::error::loop cap reached: {which} — {detail}")


def _int_cap(name: str) -> int:
    try:
        return int(os.environ.get(name, "0") or 0)
    except ValueError:
        return 0


def caps_ok(iteration: int, extra_tokens: int = 0) -> None:
    """Raise if a cap would be violated. 0 = no cap (configuration
    requirement: a loop cap of 0 means no cap)."""
    loops = _int_cap("MAX_LOOPS")
    if loops > 0 and iteration >= loops:
        raise CapReached("MAX_LOOPS", f"iteration {iteration} >= cap {loops}")
    tokens = _int_cap("MAX_TOKENS")
    if tokens > 0 and tokens_used() + extra_tokens >= tokens:
        raise CapReached("MAX_TOKENS", f"budget {tokens_used() + extra_tokens} >= {tokens}")


def tokens_used() -> int:
    f = state_file("tokens.txt")
    if not os.path.exists(f):
        return 0
    total = 0
    for line in open(f):
        try:
            total += int(line.strip() or 0)
        except ValueError:
            pass
    return total


def tokens_add(n: int) -> None:
    with open(state_file("tokens.txt"), "a") as f:
        f.write(f"{n}\n")


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


def pi_invoke(
    model: str,
    system_prompt_file: str,
    prompt_file: str | None = None,
    context: list[str] | tuple[str, ...] = (),
    timeout: int = 1800,
) -> subprocess.CompletedProcess:
    """One headless pi run. The backend comes from the pi configuration that
    is a pre-requisite of the runner environment — this never passes or
    overrides it (setup-pi requirement). Only the model is selected here."""
    with open(system_prompt_file, encoding="utf-8") as f:
        system_prompt = f.read()
    cmd = ["pi", "--print", "--model", model, "--system-prompt", system_prompt]
    if prompt_file:
        with open(prompt_file, encoding="utf-8") as f:
            cmd.append(f.read())
    cmd += list(context)
    out_f = state_file(f"pi-{os.path.basename(system_prompt_file)}.out")
    err_f = state_file(f"pi-{os.path.basename(system_prompt_file)}.err")
    log(f"$ pi --print --model {model} --system-prompt @{os.path.basename(system_prompt_file)} {' '.join(context)}")
    with open(out_f, "w") as out, open(err_f, "w") as err:
        r = subprocess.run(cmd, stdout=out, stderr=err, cwd=repo(), timeout=timeout)
    usage = 0
    try:
        err_text = open(err_f, encoding="utf-8", errors="replace").read()
        for m in USAGE_RE.finditer(err_text):
            usage = int(m.group(3))  # last summary line wins
        if usage:
            tokens_add(usage)
            log(f"token usage: {usage} total ({tokens_used()} accumulated; cap {_int_cap('MAX_TOKENS') or 'none'})")
    except (OSError, ValueError):
        pass
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


@dataclasses.dataclass
class GuardResult:
    ok: bool
    violations: list[str]


def guard(baseline: str, allow: list[str] | tuple[str, ...]) -> GuardResult:
    """The one shared guard idiom (plan §4.1): everything in the baseline
    diff that is not under an allowed prefix is reverted exactly (modified
    files checked out from the baseline, untracked ones cleaned), and the
    result is returned so the stage can re-run its generation. Invoked three
    times by the three check stages with different allowed paths — one script
    (guard-check.py), three calls."""
    allow = [a.rstrip("/") for a in allow if a]
    violations = []
    for f in changed_files(baseline):
        if any(f == a or f.startswith(a + "/") for a in allow):
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
    r = subprocess.run(args, cwd=repo(), capture_output=True, text=True, env={
        **os.environ, "GIT_CONFIG_COUNT": "3",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.cookie",
        "GIT_CONFIG_VALUE_0": "",
    })
    # rewrite any token in the URL back out of the log
    if r.returncode != 0:
        clean = (r.stderr or r.stdout).replace(token, "***") if token else (r.stderr or "")
        raise RuntimeError(f"git push failed: {clean.strip()[:300]}")


def git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + args, cwd=repo(), capture_output=True, text=True, check=check)


def action_path() -> str:
    """Directory of the running composite action inside the code-weaver
    checkout — sibling actions/scripts resolve from here.

    On this runner build GITHUB_ACTION_PATH is unset inside composite
    action inner steps (same bug family as the missing INPUT_* binding),
    so the actions directory is anchored from this file's own location:
    common.py lives at <repo>/.github/scripts/common.py."""
    p = os.environ.get("GITHUB_ACTION_PATH")
    if p:
        # This runner build points it at the action dir with a "/./"
        # segment and a trailing slash; raw dirname() arithmetic eats the
        # trailing slash as a level and lands one dir too deep, so
        # normalize before any caller walks up from here.
        return os.path.normpath(p)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(repo_root, ".github", "actions", "stage")


def sibling_action(name: str) -> str:
    return os.path.join(os.path.dirname(action_path()), name)


def external_guard() -> str | None:
    """The canonical single guard script (one script, three call sites)."""
    p = os.path.join(os.path.dirname(action_path()), "scripts", "guard-check.py")
    return p if os.path.exists(p) else None


def main_guard_cli() -> None:
    """guard-check.py entry point:  guard-check.py <baseline-ref> <allowed>…
    exit 0 = clean stage, 1 = violations reverted (caller re-runs the stage)."""
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("usage: guard-check.py <baseline-ref> <allowed-path>…")
        sys.exit(2)
    baseline, allow = args[0], args[1:]
    r = guard(baseline, allow)
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
