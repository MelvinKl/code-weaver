#!/usr/bin/env python3
"""Stage 12 — push the AI branch, open (or update) the pull request.

The pr job's terminal stage body — the former inline python of its
`Push the AI branch and open (or update) the PR` step, moved into the
runtime tree the job's stash step materialises (issue #106's
flat-file discipline: the file's step only launches the script from the
stash). The body pushes the AI branch and opens (or, where a PR from
this head already exists, updates) the pull request against the
trigger's resolved target branch; the PR's number and url are relayed
the documented way — the job-outputs file beside the state dir's
`state/pr/` files the gates and report jobs read.

At its completion point the body records its outcome line and its
completion marker in the state dir (the artefact channel): the stage
STEP writes both — a job tail the runner's parser mangles into a no-op
must not be the stage's verdict's only writer (issue #106). The report
stage cross-checks the line and the marker to tell "stage 12 ran" from
"stage 12 never ran".
"""
try:
    import os, sys, json
    action_dir = os.path.join(os.environ.get("RUNNER_TEMP", ""), "cw", "stash", ".github", "actions", "pr-open")
    scripts = os.path.join(os.path.dirname(os.path.dirname(action_dir)), "scripts")
    if os.path.isdir(scripts):
        sys.path.insert(0, scripts)
    try:
        import common
    except ImportError:
        common = None
    # the run's resolved extension env applied to this stage's process
    # environment at entry (the artefact-channel half of the relay that
    # keeps the every-step contract whole on a runner build whose
    # GITHUB_ENV write ghosts): every CLI the stage then spawns
    # inherits the provider's values
    if common:
        common.apply_extension_env()

    # The factory's single git entry point (one function every
    # git call routes through — the test suite mocks that one
    # function, so no test spawns the real git binary; this step
    # runs in its own interpreter, so it carries its own copy,
    # and a test-injected entry point in its globals wins)
    if "git_exec" not in globals():
        def git_exec(argv, **kw):
            import subprocess
            # the child's git reads the workspace's safe.directory entry
            # from its OWN process environment: actions/checkout's
            # safe.directory shim is written into a temporary HOME that
            # exists for the checkout step alone, so a git child running
            # in a later step of the same job (this stage's git work
            # against the checked-out workspace) would otherwise read a
            # user-global configuration without the entry, and git would
            # refuse the workspace with 'detected dubious ownership'
            # where the runner process does not own it (the death of run
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
            # (one value a file, beside the trigger's recorded state);
            # this state-file read is the artefact-channel half that
            # keeps the relay whole on a runner build whose GITHUB_ENV
            # write ghosts: applied to the git child's environment with
            # the provider's leave-untouched rule (a value already
            # present wins over the run's provided one), so the stage's
            # git work runs with the provider's variables in the git
            # process env — where it carries GIT_AUTHOR_NAME /
            # GIT_AUTHOR_EMAIL, git's environment-over-configuration
            # precedence makes the provider's account the commit's
            # author. A run without the provider recorded no file: the
            # child's environment is exactly as before.
            d = os.path.join(os.environ.get("RUNNER_TEMP", ""), "cw",
                             "state", "trigger")
            try:
                fns = os.listdir(d)
            except OSError:
                fns = []
            for fn in sorted(fns):
                if not (fn.startswith("extension-env-")
                        and fn.endswith(".txt")):
                    continue
                k = fn[len("extension-env-"):-len(".txt")]
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
        _cw_persist("12 pr-open", dump, v)
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
        raise SystemExit(
            f"::error::input '{name}' unbound (no INPUT_{n}, "
            f"no CW_{n}, no state file)")
    head, base = _cw_in("head"), _cw_in("base")
    title, body_file, issue = (_cw_in("title"),
                               _cw_in("body-file"),
                               _cw_in("issue-number"))
    repo = os.environ["GITHUB_WORKSPACE"]
    token = os.environ.get("GH_TOKEN", "")

    if common:
        common.push_branch(head)
    else:
        # minimal push without the shared script (degenerate checkout) —
        # token rides in the push URL only; the origin remote is untouched
        git_exec(
            ["push", "--force",
             f"https://x-access-token:{token}@github.com/{os.environ['GITHUB_REPOSITORY']}",
             head],
            cwd=repo, check=True,
            env={k: v for k, v in os.environ.items() if k != "GH_TOKEN"})

    def gh(*a):
        import subprocess
        return subprocess.run(["gh", *a], cwd=repo, capture_output=True,
                              text=True, env={**os.environ, "GH_TOKEN": token})

    # a PR from this head already exists? update it, don't duplicate
    view = gh("pr", "view", head, "--json", "number,url")
    if view.returncode == 0 and view.stdout.strip():
        pr = json.loads(view.stdout)
        gh("pr", "edit", str(pr["number"]), "--body-file", body_file)
        number, url = str(pr["number"]), pr["url"]
    else:
        cr = gh("pr", "create", "--base", base, "--head", head,
                "--title", title, "--body-file", body_file)
        if cr.returncode != 0:
            print(f"::error::pr create failed: {cr.stderr.strip()[:300]}")
            sys.exit(1)
        view = gh("pr", "view", head, "--json", "number,url")
        pr = json.loads(view.stdout)
        number, url = str(pr["number"]), pr["url"]

    if common:
        common.log(f"stage 12: PR #{number} open — {url} (ai-branch {head} → {base})")
    gh("issue", "comment", issue,
       "--body", f"🏭 **code-weaver** — pull request open: {url}\n\n"
                 f"Base: `{base}` — head: `{head}`. The PR body carries the "
                 f"final status report (stage 15 completes it). Merging is a human decision.")
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"pr-number={number}\npr-url={url}\n")
    # state files — the gates & report jobs read the PR identity from
    # the artifact (the job-outputs relay is not their value channel —
    # and on this runner build it ghosts entirely, so the state files are
    # the only channel of the pair). An empty state/pr dir (a write the
    # body lost in the #106 flat-file migration) rides no artefact at all
    # — the gates job then resolves an empty PR number, its head-sha probe
    # 404s, and the run dies in the gate before the report stage ever
    # renders (runs 43085640068 and 43175773049)
    st = os.path.join(os.environ.get("RUNNER_TEMP", ""),
                      "cw", "state", "pr")
    os.makedirs(st, exist_ok=True)
    with open(os.path.join(st, "pr-number.txt"), "w") as f:
        f.write(str(number))
    with open(os.path.join(st, "pr-url.txt"), "w") as f:
        f.write(url)
    # the stage's outcome line + completion marker — written by the stage
    # STEP itself (a job tail the runner's parser mangles into a no-op
    # must not be the stage's verdict's only writer — issue #106). The
    # line and the marker ride the state dir on the artefact chain to the
    # report stage, which cross-checks them to tell "stage 12 ran" from
    # "stage 12 never ran".
    try:
        sd = os.path.join(os.environ.get("RUNNER_TEMP") or "/tmp", "cw")
        os.makedirs(sd, exist_ok=True)
        with open(os.path.join(sd, "stage-summary.txt"), "a",
                  encoding="utf-8") as f:
            f.write(f"stage 12 pr: PR #{number} open — {url}\n")
        adir = os.path.join(sd, "artifacts")
        os.makedirs(adir, exist_ok=True)
        with open(os.path.join(adir, "cw-pr.txt"), "w",
                  encoding="utf-8") as f:
            f.write("cw-pr: stage step completed\n")
    except OSError:
        pass
except SystemExit:
    raise
except BaseException as e:
    # explicit wrap: inside this handler the exception
    # context is alive, so the persisted traceback is always
    # complete; the excepthook below is the backstop
    import traceback as _tb
    _cw_persist("12 pr-open", _tb.format_exc(), e)
    raise
