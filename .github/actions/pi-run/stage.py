#!/usr/bin/env python3
"""The pr job's PR-body pi call.

The body the pr job's `Generate the PR body with pi` step used to carry
inline — one headless pi run against the `pr-body` prompt template (the
PR body the stage 15 report completes), moved into the runtime tree the
job's stash step materialises (issue #106's flat-file discipline: the
file's step only launches the script from the stash). The step's env
relays the call's values (the run's model, the template name, the prompt
file the previous step assembled, the context file list that step
relayed); the call rides the shared pi-call plumbing where it resolves,
with the local fallback definitions where it does not, and a crashed
call persists its diagnosis the way every other stage body does.
"""
try:
    import os, sys
    action_dir = os.path.join(os.environ.get("RUNNER_TEMP", ""), "cw", "stash", ".github", "actions", "pi-run")
    scripts = os.path.join(os.path.dirname(os.path.dirname(action_dir)), "scripts")
    if os.path.isdir(scripts):
        sys.path.insert(0, scripts)
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
        _cw_persist("pi-run (LLM stages)", dump, v)
        raise SystemExit(1)
    sys.excepthook = _cw_on_uncaught
    from common import pi_invoke, resolve_pi_timeout, state_file
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
        raise SystemExit(
            f"::error::input '{name}' unbound (no INPUT_{n}, "
            f"no CW_{n}, no state file)")
    def _cw_in_opt(name):
        n = name.upper().replace("-", "_")
        for k in (f"INPUT_{n}", f"CW_{n}"):
            v = os.environ.get(k)
            if v:
                return v
        import pathlib
        for d in ("trigger", "pr"):
            f = pathlib.Path(os.environ.get("RUNNER_TEMP", "")) / "cw" / "state" / d / (name + ".txt")
            if f.is_file():
                v = f.read_text().strip()
                if v:
                    return v
        return None

    prompts = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(action_dir))), "pi-prompts")
    template = _cw_in("template")
    sp = os.path.join(prompts, template + ".md")
    if not os.path.exists(sp):
        print(f"::error::unknown pi prompt template '{template}' (have: "
              f"{sorted(os.path.basename(p) for p in os.listdir(prompts)) if os.path.isdir(prompts) else 'none'})")
        sys.exit(1)
    r = pi_invoke(
        model=_cw_in("model"),
        system_prompt_file=sp,
        prompt_file=_cw_in_opt("prompt-file"),
        context=(_cw_in_opt("context") or "").split(),
        timeout=resolve_pi_timeout(),
    )
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"pi-exit-code={r.returncode}\n")
        f.write(f"pi-out-file={state_file('last-pi.out')}\n")
    if r.returncode != 0:
        sys.exit(1)
except SystemExit:
    raise
except BaseException as e:
    # explicit wrap: inside this handler the exception
    # context is alive, so the persisted traceback is always
    # complete; the excepthook below is the backstop
    import traceback as _tb
    _cw_persist("pi-run (LLM stages)", _tb.format_exc(), e)
    raise
