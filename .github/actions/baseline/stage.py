#!/usr/bin/env python3
"""Stage 3 — cut the AI branch, record the baseline.

The baseline stage's body — the former inline python of the baseline job's
`Stage 3 — cut the AI branch, record the baseline` step, moved into the
runtime tree the job's stash step materialises (issue #106: the runner's
workflow parser diverged from the standard YAML engines on the giant
inline bodies, and the flat-file discipline keeps the stage scripts in
the stashed tree, the file's step only launches them).

The body keeps the dual-path import: on a runner where the shared module
resolves from the stashed runtime tree its plumbing names bind to
`common`'s definitions; on a runner where the import fails it runs on the
local fallback definitions (the path this runner build takes in
production). The crash parity is the inline form (the explicit
try/except wrap persists the full traceback to the runner's diagnostic
log and a one-line reason to the stage's artefacts; the excepthook is
the backstop) — a crashed stage leaves a persistent diagnosis, the job
log of a failed run being a ghost on this runner build.

At its completion point the body records its outcome line and its
completion marker in the state dir (the artefact channel): the stage
STEP writes both — the job's terminal `Stage summary` step, on a runner
whose parser mangles that step into a no-op (issue #106's baseline job:
the stage ran, the terminal step wrote nothing, the artifact kept only
the earlier stages' lines), is the fallback writer, not the verdict's
only writer. The report stage cross-checks the line and the marker to
tell "stage 3 ran" from "stage 3 never ran".
"""
try:
    import os, subprocess, sys
    action_dir = os.path.join(os.environ.get("RUNNER_TEMP", ""), "cw", "stash", ".github", "actions", "baseline")
    scripts = os.path.join(os.path.dirname(os.path.dirname(action_dir)), "scripts")
    if os.path.isdir(scripts):
        sys.path.insert(0, scripts)
    try:
        from common import state_dir, state_file, log
    except ImportError:
        def state_dir():
            d = os.path.join(os.environ.get("RUNNER_TEMP") or "/tmp", "cw")
            os.makedirs(d, exist_ok=True)
            return d
        def state_file(n):
            return os.path.join(state_dir(), n)
        def log(m):
            print(m, flush=True)

    # a crashed stage must leave a persistent diagnosis (the job log dies
    # with the run; a ghost run's logs are unreachable from the API) —
    # the full traceback goes to the runner's diag dir + one line to the
    # stage-fail-reason state file the summary/upload steps carry on
    def _cw_persist(stage, dump, value):
        # one writer for both paths (the explicit try/except wrap and the
        # excepthook) — the job-visible ::error:: line, the stage-fail-reason
        # state file (carried on by the summary/upload steps), and the
        # runner's durable diag log (the job log dies with the run)
        if globals().get("_cw_persisted"):
            return
        globals()["_cw_persisted"] = True
        try:
            d = os.path.join(os.environ.get("RUNNER_TEMP") or "/tmp", "cw")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "stage-fail-reason.txt"), "w") as f:
                f.write(f"stage {stage} FAILED — {value}\n")
            with open("/opt/actions-runner/_diag/cw-diag.log", "a") as f:
                f.write(f"=== stage {stage} FAILED ===\n{dump}\n")
            print(f"::error::stage {stage} failed — full diagnosis: /opt/actions-runner/_diag/cw-diag.log")
        except Exception:
            print(f"::error::stage {stage} failed — {value}")

    def _cw_on_uncaught(t, v, tb):
        import traceback as _tb
        # the hook receives (type, value, traceback) from the interpreter —
        # sys.exc_info() is already cleared by the time it runs, so the
        # arguments are the source of truth; format_exc() is the fallback
        if tb is not None:
            dump = "".join(_tb.format_exception(t, v, tb))
        else:
            dump = _tb.format_exc()
            if not dump.strip() or dump.strip() == "NoneType: None":
                dump = f"(no exception context at hook time — type: {t!r}, value: {v!r})"
        _cw_persist("3 baseline", dump, v)
        raise SystemExit(1)
    sys.excepthook = _cw_on_uncaught
    def _cw_in(name):
        # INPUT_<name> (a healthy runner's action-input binding) or
        # CW_<name> (the job/step env the factory sets — on this
        # runner build, composite actions' with: values never reach
        # the inner steps as INPUT_* at all; see probe v4)
        n = name.upper().replace("-", "_")
        for k in (f"INPUT_{n}", f"CW_{n}"):
            v = os.environ.get(k)
            if v:
                return v
        # state files — this runner build's composite-action inner
        # steps also miss the job-level GITHUB_ENV values, so the
        # files the triggering stage wrote into the artifact are
        # the authoritative source
        import pathlib
        for d in ("trigger", "pr"):
            f = pathlib.Path(os.environ.get("RUNNER_TEMP", "")) / "cw" / "state" / d / (name + ".txt")
            if f.is_file():
                v = f.read_text().strip()
                if v:
                    return v
        # a value that ends in a separator is a mangled derivation
        # (e.g. an empty issue number in 'ai/code-weaver/') — treat
        # it as unbound rather than creating a broken ref
        for k in (f"INPUT_{n}", f"CW_{n}"):
            v = os.environ.get(k) or ""
            if v and v.endswith(("/", ".", "_")):
                raise SystemExit(
                    f"::error::input '{name}' value {v!r} is a "
                    f"mangled derivation (empty component)")
        raise SystemExit(
            f"::error::input '{name}' unbound (no INPUT_{n}, "
            f"no CW_{n}, no state file)")
    base_ref = _cw_in("base-ref")
    ai_branch = _cw_in("ai-branch")
    repo = os.environ["GITHUB_WORKSPACE"]

    # The factory's single git entry point — one function every
    # git call in the factory's python routes through, so the test
    # suite can mock that one function (a test never spawns the
    # real git binary). This step's python runs in its own
    # interpreter, so it carries its own copy; a test-injected
    # entry point in this script's globals is honoured over it.
    if "git_exec" not in globals():
        def git_exec(argv, **kw):
            # the child's git reads the workspace's safe.directory entry
            # from its OWN process environment: actions/checkout's
            # safe.directory shim is written into a temporary HOME that
            # exists for the checkout step alone, so a git child running
            # in a later step of the same job (this stage's fetch /
            # branch cut / commit / push against the checked-out
            # workspace) would otherwise read a user-global
            # configuration without the entry, and git would refuse the
            # workspace with 'detected dubious ownership' where the
            # runner process does not own it (the death of run
            # 42968837898's baseline stage). The managed entries pin
            # the runner user's home directory, the current working
            # directory, and — where the step's GITHUB_WORKSPACE is
            # known — the workspace itself as safe.directory, on a copy
            # of the environment sanitised of any leaked GIT_CONFIG_*
            # entries (a dangling key the count never fills would make
            # the child's git die on the missing key).
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith("GIT_CONFIG_")}
            # the run's resolved extension env — the setup-pi stage
            # records the provider's values in the run's state dir
            # (one value a file, beside the trigger's recorded state).
            # The per-job Read trigger state relay's GITHUB_ENV half
            # feeds the job's env; this state-file read is the
            # artefact-channel half that keeps the relay whole on a
            # runner build whose GITHUB_ENV write ghosts: applied to
            # the git child's environment with the provider's
            # leave-untouched rule (a value already present wins over
            # the run's provided one), so the branch cut and the
            # factory's commit identity it configures run with the
            # provider's variables in the git process env — where it
            # carries GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL, git's
            # environment-over-configuration precedence makes the
            # provider's account the commit's author. A run without the
            # provider recorded no file: the child's environment is
            # exactly as before.
            d = os.path.join(os.environ.get("RUNNER_TEMP", ""), "cw",
                             "state", "trigger")
            try:
                fns = os.listdir(d)
            except OSError:
                fns = []
            for fn in sorted(fns):
                if not (fn.startswith("pi-extension-env-")
                        and fn.endswith(".txt")):
                    continue
                k = fn[len("pi-extension-env-"):-len(".txt")]
                try:
                    v = open(os.path.join(d, fn),
                             encoding="utf-8").read()
                except OSError:
                    continue
                v = v.strip()
                if v and not env.get(k):
                    env[k] = v
            entries = [("safe.directory", os.path.expanduser("~")),
                       ("safe.directory", os.getcwd())]
            ws = os.environ.get("GITHUB_WORKSPACE")
            if ws:
                entries.append(("safe.directory", ws))
            env["GIT_CONFIG_COUNT"] = str(len(entries))
            for i, (k, v) in enumerate(entries):
                env["GIT_CONFIG_KEY_%d" % i] = k
                env["GIT_CONFIG_VALUE_%d" % i] = v
            kw["env"] = env
            return subprocess.run(["git"] + list(argv), **kw)

    def g(*args, check=True):
        r = git_exec(list(args), cwd=repo,
                     capture_output=True, text=True)
        if check and r.returncode != 0:
            # surface git's own diagnosis (a bare check=True traceback
            # hides it in e.stderr) before the uncaught-exception hook
            # persists everything
            print(f"::error::git {' '.join(args)} failed (exit {r.returncode}): "
                  f"{r.stderr.strip()[:400]}")
            raise subprocess.CalledProcessError(r.returncode, ["git", *args],
                                                output=r.stdout, stderr=r.stderr)
        return r

    # baseline ref = head of the target branch
    g("fetch", "--no-recurse-submodules", "origin", base_ref)
    base_sha = g("rev-parse", f"origin/{base_ref}").stdout.strip()

    # A NEW run for an issue whose AI branch already exists (the
    # owner's re-trigger after a failed/aborted run) REUSES that
    # branch: every stage runs again, in place, from the branch's
    # current state (the idempotent re-run contract — generated
    # files are updated in place; the guard measures against the
    # baseline ref below, so the accumulated work is what it sees).
    # Only an absent branch is cut fresh from the target — re-cutting
    # would discard the previous run's committed work.
    g("fetch", "--no-recurse-submodules", "origin", ai_branch, check=False)
    if g("rev-parse", f"origin/{ai_branch}", check=False).returncode == 0:
        resume_sha = g("rev-parse", f"origin/{ai_branch}").stdout.strip()
        g("checkout", "-B", ai_branch, f"origin/{ai_branch}")
        log(f"baseline: reusing existing {ai_branch} at {resume_sha} "
            f"(previous run's work); baseline ref = head of "
            f"{base_ref} {base_sha}")
    else:
        g("checkout", "-B", ai_branch, base_sha)
        log(f"baseline: {ai_branch} cut at {base_sha} (head of "
            f"{base_ref}); fresh cut")
    g("config", "user.name", "Code Weaver")
    g("config", "user.email", "code-weaver@users.noreply.github.com")

    # the issue's change set, snapshotted as state (empty at a fresh cut —
    # it grows as stages write, and anchors every guard check)
    state = state_dir()
    with open(state_file("baseline.sha"), "w") as f:
        f.write(base_sha + "\n")
    diff = g("diff", base_sha).stdout
    with open(state_file("baseline.diff"), "w") as f:
        f.write(diff)

    log(f"baseline: {ai_branch} cut at {base_sha} (head of {base_ref}); "
        f"baseline diff {len(diff)} bytes → state (not the repo tree)")
    # the stage's outcome line + completion marker — written by the stage
    # STEP itself (the job's terminal "Stage summary" step, on a runner
    # whose parser mangles that step into a no-op, must not be the
    # stage's verdict's only writer — issue #106: the baseline stage ran
    # its work, its terminal summary step wrote nothing, and the artifact
    # kept only the earlier stages' lines). The line and the marker ride
    # the state dir on the artefact chain to the report stage, which
    # cross-checks them to tell "stage 3 ran" from "stage 3 never ran".
    try:
        with open(state_file("stage-summary.txt"), "a",
                  encoding="utf-8") as f:
            f.write(f"stage 3 baseline: branch {ai_branch} at {base_sha}\n")
        adir = os.path.join(state_dir(), "artifacts")
        os.makedirs(adir, exist_ok=True)
        with open(os.path.join(adir, "cw-baseline.txt"), "w",
                  encoding="utf-8") as f:
            f.write("cw-baseline: stage step completed\n")
    except OSError:
        pass
except SystemExit:
    raise
except BaseException as e:
    # explicit wrap: inside this handler the exception
    # context is alive, so the persisted traceback is always
    # complete; the excepthook below is the backstop
    import traceback as _tb
    _cw_persist("3 baseline", _tb.format_exc(), e)
    raise
