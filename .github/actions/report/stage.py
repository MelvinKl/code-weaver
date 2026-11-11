#!/usr/bin/env python3
"""Stage 15 — the final status report (PR body + issue comment +
arc42 activity).

The report stage's body — the former ~490-line inline python of the
report job's `Write the final status report` step, moved into the
runtime tree the job's stash step materialises (issue #106: the runner's
workflow parser dropped the `extract` job and phantom-stepped every job
on the published file's giant inline bodies; the flat-file discipline
keeps the stage scripts in the stashed tree, the file's step only
launches them). The body keeps the dual-path import (the shared module's
five plumbing names bind where it resolves from the stashed tree, the
local fallback definitions where it does not — the path this runner
build takes in production) and the crash parity of every other stage
body.

The body completes the run's final status on both report surfaces: the
PR body's `## Final status` section (verified on the PR after the edit
— a completion that did not land makes the issue comment
self-contained) and the issue comment itself (a successful run closes
the source issue, a failed run leaves it open for a re-trigger), and
records the AI-activity entry in the arc42 set. The run's usage and
cost assemble from the per-call ledger the state dir carries, priced
from the run's model configuration.

The no-PR verdict distinguishes the three cases the state channel
separates (issue #106's false "run failed": stages 2–3 had run, their
outcome lines lost in the truncating artefact channel, and the old
verdict read "no line" as "the stage failed"): a stage whose recorded
line carries FAILED — the run failed there; a stage that never ran (no
outcome line, no completion marker, no console evidence — its job is
not in the run's job graph) — the pipeline stopped there; a stage that
ran (its marker or console evidence survived) but recorded no outcome —
a channel loss, not evidence of failure, reported as an undetermined
outcome instead of a declared failure.
"""
try:
    import os, sys, glob, json, re, datetime

    # The factory's single git entry point — one function every
    # git call in the factory's python routes through, so the test
    # suite can mock that one function (a test never spawns the
    # real git binary). This step's python may run without the
    # common module, so it carries its own copy; a test-injected
    # entry point in this script's globals is honoured over it.
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
    action_dir = os.path.join(os.environ.get("RUNNER_TEMP", ""), "cw", "stash", ".github", "actions", "report")
    scripts = os.path.join(os.path.dirname(os.path.dirname(action_dir)), "scripts")
    if os.path.isdir(scripts):
        sys.path.insert(0, scripts)
    try:
        import common
        # import path — the shared module resolved from the stashed
        # runtime tree: bind the body's five bare-name plumbing calls
        # (the state dir, the state file, the log, the gh api, the
        # branch push) to the shared module's definitions, so the
        # body's bare-name calls resolve on that path and the step
        # completes its report instead of dying with an
        # undefined-name error before any of its report work; a
        # runner where the module does not resolve falls through to
        # the ImportError branch below, whose local fallback
        # definitions bind the same names
        state_dir = common.state_dir
        state_file = common.state_file
        log = common.log
        gh_api = common.gh_api
        push_branch = common.push_branch
    except ImportError:
        def state_dir():
            d = os.path.join(os.environ.get("RUNNER_TEMP") or "/tmp", "cw")
            os.makedirs(d, exist_ok=True)
            return d
        def state_file(n):
            return os.path.join(state_dir(), n)
        def log(m):
            print(m, flush=True)
        def gh_api(p, accept="application/vnd.github+json", data=None):
            import subprocess
            env = {**os.environ, "GH_TOKEN": os.environ.get("GH_TOKEN", "")}
            args = ["gh", "api", "-H", f"Accept: {accept}"]
            if data is not None:
                args += ["-f", f"body={data}"]
            args.append(p)
            r = subprocess.run(args, capture_output=True, text=True, env=env)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip()[:300])
            return r.stdout
        def push_branch(branch, force=True):
            token = os.environ.get("GH_TOKEN", "")
            git_exec(["push", "--force",
                      f"https://x-access-token:{token}@github.com/{os.environ['GITHUB_REPOSITORY']}", branch],
                     cwd=os.environ["GITHUB_WORKSPACE"], check=True,
                     env={k: v for k, v in os.environ.items() if k != "GH_TOKEN"})

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
        _cw_persist("15 report", dump, v)
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
    repo = os.environ["GITHUB_WORKSPACE"]
    result = _cw_in("run-result")
    pr = (_cw_in_opt("pr-number") or "").strip()
    issue = _cw_in("issue-number")
    now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")

    # merge every stage's summary line (the jobs downloaded their
    # cw-* state artifacts into the state dir before calling us)
    stage_lines = []
    for f in sorted(glob.glob(os.path.join(state_dir(), "**", "stage-summary.txt"), recursive=True)):
        for line in open(f):
            if line.strip() and line.strip() not in stage_lines:
                stage_lines.append(line.strip())
    # the stage-outcome assembly renders from those lines: the
    # implement stage records its per-step state on this channel
    # (one "stage 8 implementation: step <k>/<n> done" line per
    # step it finished, a "stage complete" line only when its
    # plan is fully tracked). A stage that is done — its lines
    # carry one that says "stage complete" — is reported
    # "stage complete": its per-step lines stay out of the
    # outcome. A stage whose work was intentionally skipped — the
    # extract stage on a bug-labelled run, whose skip its
    # bug-skip branch records on this channel (its line's outcome
    # part begins with "skipped") — is listed as skipped, never as
    # "stage complete": a stage that did no work is not a done
    # stage, so a completion line it recorded alongside the skip
    # stays out of the outcome. A stage that will re-run —
    # per-step lines without a completion line — is reported per
    # step, "step <k>/<n> done" for each of its finished steps.
    # Both report surfaces the report completes (the PR body and
    # the issue comment) render the same table.
    _per_step = re.compile(r"^step \d+/\d+ done$")
    _skipped = re.compile(r"^skipped\b")
    _rendered = []
    _group = None
    _glines = []
    def _flush():
        if _group is None:
            # a line not in the "stage …:" form stays as recorded
            _rendered.extend(_glines)
        elif any(_skipped.match(l.split(": ", 1)[1])
                 for l in _glines):
            # a stage whose work was intentionally skipped (the
            # extract stage on a bug-labelled run): listed as
            # skipped — the skip is listed, not silently omitted;
            # a stage that did no work is not a done stage, so a
            # completion line it recorded alongside the skip is
            # never rendered "stage complete"
            _rendered.extend(l for l in _glines
                            if "stage complete" not in l)
        elif any("stage complete" in l for l in _glines):
            # a stage that is done: reported "stage complete" —
            # the per-step lines it recorded along the way stay
            # out of the outcome
            _rendered.extend(l for l in _glines
                            if not _per_step.match(
                                l.split(": ", 1)[1]))
        else:
            # a stage that will re-run (per-step lines, no
            # completion line) is reported per step; every other
            # stage's lines stay as recorded
            _rendered.extend(_glines)
    for l in stage_lines:
        _label, _sep, _rest = l.partition(": ")
        g = (_label
             if (_sep and _label.startswith("stage "))
             else None)
        if g != _group:
            if _glines:
                _flush()
            _group, _glines = g, []
        _glines.append(l)
    if _glines:
        _flush()
    stage_table = "\n".join(f"- {l}" for l in _rendered) or "- (no stage summaries captured)"
    # the stage-status evidence the verdicts below cross-check — the
    # channel the state dir carries after the report job's artifact
    # downloads merge the stages' state into it (issue #106: the old
    # verdict read "no outcome line" as "the stage failed", and the
    # truncating summary channel left it exactly one line of the run
    # that had in fact completed three stages).
    #   the outcome lines — merged above, attributed to a stage number
    #   the completion markers — each stage job's stage step writes one
    #   (state/artifacts/cw-<job>.txt) the moment its stage work
    #   completes; the cumulative artefact chain carries every earlier
    #   job's marker to this job, so the union is the set of stage jobs
    #   whose stage step completed
    #   the stage console — every line the stage python logs (the
    #   crash-parity mirror), attributed to its stage's log prefix
    # A stage with no outcome line, no marker and no console line is a
    # stage whose job never ran — the job the runner's parser dropped
    # from the run's job graph (issue #106: extract missing, every
    # downstream stage skipped). A stage with a marker or a console line
    # but no outcome line RAN — its verdict is a channel loss, not a
    # recorded failure.
    _stage_nos = {}
    for _ln in stage_lines:
        _m = re.match(r"^stage (\d+)", _ln)
        if _m:
            _stage_nos.setdefault(int(_m.group(1)), []).append(_ln)
    _markers = set()
    for _mf in sorted(glob.glob(os.path.join(state_dir(), "artifacts", "*.txt"))):
        _markers.add(os.path.basename(_mf)[:-4])
    _console = ""
    _cf = state_file("stage-console.log")
    if os.path.isfile(_cf):
        _console = open(_cf, encoding="utf-8", errors="replace").read()
    _console_prefix = {
        "trigger": ("stage 1",),
        "setup-pi": ("setup-pi",),
        "baseline": ("baseline",),
        "extract": ("stage 4",),
        "plan": ("stage 6",),
        "implement": ("stage 8",),
        "review": ("stage 10",),
        "pr": ("stage 12",),
        "gates": ("stage 13",),
    }
    _job_stages = {
        "trigger": (1,), "setup-pi": (2,), "baseline": (3,),
        "extract": (4, 5), "plan": (6, 7), "implement": (8, 9),
        "review": (10, 11), "pr": (12,), "gates": (13, 14),
    }
    def _job_status(job):
        lines = [l for n in _job_stages[job] for l in _stage_nos.get(n, [])]
        if lines:
            return "recorded", lines
        if f"cw-{job}" in _markers:
            return "ran-no-outcome", []
        if any(any(cl.startswith(pref) for pref in _console_prefix[job])
               for cl in _console.splitlines()):
            return "ran-no-outcome", []
        return "never-ran", []
    _job_order = ("trigger", "setup-pi", "baseline", "extract", "plan",
                  "implement", "review", "pr", "gates")
    _statuses = {j: _job_status(j) for j in _job_order}
    _failed = [l for l in stage_lines if "FAILED" in l]
    _gap = next((j for j in _job_order if _statuses[j][0] != "recorded"),
                None)
    # run usage & cost for the final status report — assembled from
    # the per-call usage records in the state dir: one tokens.txt
    # line per pi call carrying the call's input and output token
    # counts (the shared pi-call plumbing appends a record as each
    # call finishes, and the record travels with the run's state
    # artifacts like every other stage value). Each stage's artifact
    # carries the cumulative ledger, and the report job downloads the
    # stages' artifacts in pipeline order — the ledger surviving the
    # downloads is the complete one: it covers every pi call the run
    # made, and a stage that never ran (its artifact never uploaded)
    # contributes nothing
    tot_in = tot_out = 0
    have_usage = False
    led = state_file("tokens.txt")
    if os.path.isfile(led):
        for line in open(led, encoding="utf-8", errors="replace"):
            p = line.split()
            if len(p) != 2:
                continue
            try:
                i, o = int(p[0]), int(p[1])
            except ValueError:
                continue
            tot_in += i
            tot_out += o
            have_usage = True
    # the total cost is derived from the recorded usage, keyed on the
    # run's resolved model — the llm-model setting, the only
    # documented adjustable LLM setting; its resolved value rides the
    # trigger's resolved-config state, which the report job downloads
    # first. The rates come from the run's model configuration itself
    # — the provider the setup stage materialised (a non-empty
    # models-configuration secret wins over the repo file
    # .pi/agent/models.json, which this job resolves the same way): the per-model `cost`
    # object in its models.json entry carries the USD-per-1M-tokens
    # rates, and the report lists the rates used with the source it
    # read them from, so the listed cost is auditable and consistent
    # with the recorded usage; a model the configuration carries no
    # cost entry for is listed as unpriced
    model = ""
    cfg = state_file("resolved-config.txt")
    if os.path.isfile(cfg):
        for line in open(cfg, encoding="utf-8", errors="replace"):
            if line.startswith("- LLM model"):
                p = line.split("`")
                if len(p) >= 2:
                    model = p[1].strip()
                break
    # the run's model configuration — resolved the way the setup
    # stage resolves it: a non-empty models-configuration secret
    # (the CW_ relay this job's env carries) wins over the repo
    # file .pi/agent/models.json in the workspace
    models_raw = _cw_in_opt("pi-models")
    models_source = ("the run's model configuration (a GitHub secret)"
                      if models_raw
                      else "the repo file .pi/agent/models.json")
    if not models_raw:
        fp = os.path.join(os.environ.get("GITHUB_WORKSPACE") or ".",
                          ".pi", "agent", "models.json")
        if os.path.isfile(fp):
            try:
                with open(fp, encoding="utf-8") as f:
                    models_raw = f.read()
            except OSError:
                models_raw = None
    # USD per 1M tokens for the resolved model — the `cost`
    # object of its models.json entry (input, output,
    # cacheRead, cacheWrite). The usage ledger records input and
    # output only, so the cost is the input/output part of it
    r_in = r_out = None
    if models_raw:
        try:
            data = json.loads(models_raw)
        except Exception:
            data = None
        if data is not None:
            def _walk(o):
                # the providers' models lists — the same shape the
                # setup stage's model-set check walks
                if isinstance(o, dict):
                    for k, v in o.items():
                        if k == "models" and isinstance(v, list):
                            for m in v:
                                yield m
                        else:
                            yield from _walk(v)
                elif isinstance(o, list):
                    for v in o:
                        yield from _walk(v)
            for m in _walk(data):
                if isinstance(m, dict) and m.get("id") == model:
                    c = m.get("cost")
                    if isinstance(c, dict):
                        try:
                            r_in = float(c.get("input"))
                            r_out = float(c.get("output"))
                        except (TypeError, ValueError):
                            r_in = r_out = None
                    break
    if not have_usage:
        usage_lines = ("- **Total input tokens:** 0\n"
                       "- **Total output tokens:** 0\n"
                       "- **Total cost:** $0.00 (no pi call recorded usage)")
    elif r_in is None or r_out is None:
        usage_lines = (f"- **Total input tokens:** {tot_in}\n"
                       f"- **Total output tokens:** {tot_out}\n"
                       f"- **Total cost:** unpriced (model `{model}` "
                       "has no cost rates in the run's model "
                       "configuration — put the model's cost rates "
                       "in .pi/agent/models.json (or the models-"
                       "configuration secret))")
    else:
        usage_lines = (f"- **Total input tokens:** {tot_in}\n"
                       f"- **Total output tokens:** {tot_out}\n"
                       f"- **Total cost:** ${(tot_in * r_in + tot_out * r_out) / 1e6:.4f} "
                       f"(model `{model}` @ ${r_in:.2f}/M input, ${r_out:.2f}/M output — "
                       f"rates from {models_source})")

    if pr:
        view = json.loads(gh_api(
            f"repos/{os.environ['GITHUB_REPOSITORY']}/pulls/{pr}"))
        body = view.get("body") or ""
        head = view["head"]["sha"]
        final = (body.split("\n## Final status")[0]
                 + "\n## Final status\n"
                 + f"- **Run result:** {result}\n- **Completed:** {now}\n"
                 + f"- **AI branch:** `{view['head']['ref']}` @ `{head[:12]}`\n"
                 + f"- **Source issue:** #{issue}\n"
                 + usage_lines + "\n"
                 + "### Stage outcomes\n" + stage_table + "\n"
                 + "\n_Merging this PR is a human decision — the factory never merges._\n")
        import subprocess
        with open(state_file("final-pr-body.md"), "w") as f:
            f.write(final)
        subprocess.run(["gh", "pr", "edit", pr, "--body-file", state_file("final-pr-body.md")],
                       cwd=repo, env={**os.environ, "GH_TOKEN": os.environ.get("GH_TOKEN", "")},
                       check=False)
        # the completion must be VERIFIED on the PR before the
        # comment claims 'final status is in the PR body': gh pr edit
        # is a GraphQL mutation a PR that was merged in the meantime
        # refuses — and check=False would swallow that, leaving an
        # issue comment claiming the description carries the final
        # status it never got (the PR description would then disagree
        # with the usage numbers the issue comment posts). Re-read the
        # PR: its body must carry the completion.
        def _body_landed():
            try:
                again = json.loads(gh_api(
                    f"repos/{os.environ['GITHUB_REPOSITORY']}/pulls/{pr}"))
            except Exception as e:
                log(f"stage 15: could not re-read PR #{pr} after the edit: "
                    f"{str(e).strip()[:120]}")
                return False
            return "\n## Final status" in (again.get("body") or "")
        completed = _body_landed()
        if not completed:
            # the REST edit is a different write path than the GraphQL
            # mutation — a merged PR's description can still be edited
            # over REST; try it, then verify again. If it still does
            # not land, the comment below is self-contained.
            log(f"stage 15: PR #{pr} body did not take the completion — "
                f"trying the REST edit")
            subprocess.run(["gh", "api", "-X", "PATCH",
                            f"repos/{os.environ['GITHUB_REPOSITORY']}/pulls/{pr}",
                            "-f", f"body={final}"],
                           cwd=repo, capture_output=True, text=True,
                           env={**os.environ, "GH_TOKEN": os.environ.get("GH_TOKEN", "")})
            completed = _body_landed()
        # the arc42 docs get the AI-activity section (docs changes are
        # within the implementation allow-set — this commit is the
        # report stage's own, made after the guards have run)
        doc_dir = (os.environ.get("DOC_DIR") or "").strip().rstrip("/")
        entry = (f"\n### {now} — code-weaver run for issue #{issue}\n"
                 f"- result: {result}\n- PR: {pr}\n"
                 + usage_lines + "\n"
                 + "- stages:\n"
                 + "\n".join(f"  - {l}" for l in stage_lines) + "\n")
        touched = False
        # arc42 activity commits only land on the AI branch — if the run
        # died before the branch existed, the checkout is at the base ref
        # and the target tree must stay untouched
        on_ai_branch = git_exec(["branch", "--show-current"], cwd=repo,
                                capture_output=True, text=True).stdout.strip() \
            == os.environ.get("AI_BRANCH", "")
        if on_ai_branch:
            if doc_dir and os.path.isdir(doc_dir):
                arc42_files = sorted(glob.glob(
                    os.path.join(doc_dir, "**", "*.md"), recursive=True))
            elif os.path.isfile("PLAN.md"):
                # a repo without a doc dir documents itself in its
                # top-level arc42 markdown — fall back to it so the
                # AI-activity section still lands on the arc42 set
                arc42_files = [os.path.join(repo, "PLAN.md")]
            else:
                arc42_files = []
            for md in arc42_files:
                text = open(md).read()
                marker = "## AI activity (code-weaver)"
                if marker in text:
                    text = text.rstrip("\n") + entry
                elif text:
                    text = text.rstrip("\n") + f"\n\n{marker}\n" + entry
                else:
                    text = f"{marker}\n" + entry
                open(md, "w").write(text)
                touched = True
                break  # the first arc42 file carries the activity log
        if touched:
            git_exec(["add", "-A"], cwd=repo, check=True)
            st = git_exec(["status", "--porcelain"], cwd=repo,
                          capture_output=True, text=True)
            if st.stdout.strip():
                git_exec(["commit", "-q",
                          "-m", "report: AI-activity recorded"],
                         cwd=repo, check=True)
                push_branch(os.environ.get("AI_BRANCH", ""))
        url = view.get("html_url", "")
        ok = result == "success"
        # a successful run closes the issue it was working on: the
        # work is done, the PR is the remaining human gate, and a
        # closed issue stays out of the trigger's lane. A failed run
        # leaves the issue open for a re-trigger. The close is
        # best-effort — a refusal (e.g. a token without the scope)
        # must not sink the report that already landed
        closed = None
        if ok:
            r = subprocess.run(["gh", "api", "-X", "PATCH",
                                f"repos/{os.environ['GITHUB_REPOSITORY']}/issues/{issue}",
                                "-f", "state=closed",
                                "-f", "state_reason=completed"],
                               capture_output=True, text=True,
                               env={**os.environ, "GH_TOKEN": os.environ.get("GH_TOKEN", "")})
            closed = r.returncode == 0
            if not closed:
                log(f"::warning::stage 15: could not close issue #{issue}: "
                    f"{r.stderr.strip()[:120]}")
        close_note = ("closed — the run succeeded" if closed is True else
                      "close refused — the run succeeded, but the issue "
                      "stays open (see the workflow log)" if closed is False else
                      "left open — re-trigger to retry")
        if ok and completed:
            data = ("✅ **code-weaver run finished** — final status is in the PR body.\n"
                    f"- result: **{result}**\n- completed: {now}\n"
                    f"- pull request: {url}\n- source: #{issue} ({close_note})\n"
                    f"{usage_lines}\n")
        elif ok:
            # the completion could not be applied to the description
            # (the PR was already merged, or the edit was refused on
            # both write paths): the comment then carries the full
            # final status itself — the same usage numbers and stage
            # outcomes the PR body was to get — and makes no claim
            # that the PR body carries them
            data = ("✅ **code-weaver run finished** — the PR body could not be "
                    "completed (the PR was already merged or the edit was "
                    "refused), so this comment carries the full final status.\n"
                    f"- result: **{result}**\n- completed: {now}\n"
                    f"- pull request: {url}\n- source: #{issue} ({close_note})\n"
                    + usage_lines + "\n"
                    + "### Stage outcomes\n" + stage_table + "\n")
        else:
            # the same three-case distinction the no-PR verdict makes —
            # the comment names where the pipeline stopped (or that a
            # stage ran but recorded no outcome — a channel loss) beside
            # the stage outcomes
            _stop = ""
            if _failed:
                _stop = f"\n- the run's recorded failure: {_failed[0]}"
            elif _gap is not None:
                if _statuses[_gap][0] == "never-ran":
                    _stop = (f"\n- the pipeline stopped at stage job `{_gap}` "
                              "(it never ran — its job is not in the run's "
                              "job graph)")
                else:
                    _stop = (f"\n- stage job `{_gap}` ran but recorded no "
                              "outcome — a channel loss, not evidence of "
                              "failure")
            data = (f"❌ **code-weaver run failed** — the pull request is incomplete.\n"
                    f"- result: **{result}**\n- completed: {now}\n"
                    f"- pull request: {url}\n- source: #{issue} ({close_note})\n"
                    f"{_stop}"
                    f"- stage outcomes:\n{stage_table}\n"
                    f"{usage_lines}\n")
        gh_api(f"repos/{os.environ['GITHUB_REPOSITORY']}/issues/{issue}/comments",
               data=data)
        log(f"stage 15: PR #{pr} body completion "
            f"{'verified on the PR' if completed else 'NOT applied — the issue comment is self-contained'}; "
            f"issue #{issue} {'closed' if closed else 'left open'}; "
            f"arc42 activity {'recorded' if touched else 'n/a'}")
    else:
        # the no-PR verdict, the three cases the state channel separates
        # (issue #106: the old form read "no outcome line" as "the stage
        # failed" — the run's stages 2–3 had run, their lines lost in the
        # truncating channel, and the verdict declared a failure):
        #   1. a recorded line carries FAILED — the run failed at the
        #      stage whose line records it;
        #   2. the first unrecorded stage never ran (no outcome line, no
        #      completion marker, no console evidence — its job is not in
        #      the run's job graph) — the pipeline stopped there;
        #   3. the first unrecorded stage RAN (its marker or its console
        #      evidence survived) but recorded no outcome — a channel
        #      loss, not evidence of failure: the comment reports the
        #      outcome as undetermined instead of declaring a failure.
        if _failed:
            data = (f"❌ **code-weaver run failed** — before a pull request "
                    "could be opened.\n"
                    f"- result: **{result}**\n- completed: {now}\n"
                    f"- the run's recorded failure: {_failed[0]}\n"
                    f"- stage outcomes:\n{stage_table}\n"
                    f"{usage_lines}\n"
                    "- full logs: the workflow run's artifacts (the repo tree "
                    "is never used for report files).\n")
        elif _gap is None:
            data = ("❌ **code-weaver run failed** before a pull request "
                    "could be opened.\n"
                    f"- result: **{result}**\n- completed: {now}\n"
                    f"- stage outcomes:\n{stage_table}\n"
                    f"{usage_lines}\n"
                    "- full logs: the workflow run's artifacts (the repo tree "
                    "is never used for report files).\n")
        elif _statuses[_gap][0] == "never-ran":
            last = next((j for j in reversed(_job_order)
                         if _statuses[j][0] == "recorded"), None)
            data = (f"❌ **code-weaver run failed** — the pipeline stopped "
                    f"before a pull request could be opened: **stage job "
                    f"`{_gap}` never ran** (no outcome line, no completion "
                    "marker, no console evidence — its job did not enter "
                    "the run's job graph)"
                    + (f"; the last stage with a recorded outcome is "
                       f"`{last}`" if last else "") + ".\n"
                    f"- result: **{result}**\n- completed: {now}\n"
                    f"- stage outcomes:\n{stage_table}\n"
                    f"{usage_lines}\n"
                    "- full logs: the workflow run's artifacts (the repo tree "
                    "is never used for report files).\n")
        else:
            data = ("⚠️ **code-weaver run — outcome undetermined** (a stage "
                    "ran but recorded no outcome on the artefact channel — "
                    "a channel loss, not evidence of failure).\n"
                    f"- result: **{result}**\n- completed: {now}\n"
                    f"- stage job `{_gap}` ran (its completion marker or "
                    "console evidence is in the run's artefacts) but "
                    "recorded no outcome line; a pull request was not "
                    "opened\n"
                    f"- stage outcomes:\n{stage_table}\n"
                    f"{usage_lines}\n"
                    "- full logs: the workflow run's artifacts (the repo tree "
                    "is never used for report files).\n")
        gh_api(f"repos/{os.environ['GITHUB_REPOSITORY']}/issues/{issue}/comments",
               data=data)
        log(f"stage 15: no PR — reported on issue #{issue} "
            f"(stage outcomes: {len(stage_lines)} line(s); "
            f"first unrecorded stage job: "
            f"{_gap or 'none — every stage recorded an outcome'})")
except SystemExit:
    raise
except BaseException as e:
    # explicit wrap: inside this handler the exception
    # context is alive, so the persisted traceback is always
    # complete; the excepthook below is the backstop
    import traceback as _tb
    _cw_persist("15 report", _tb.format_exc(), e)
    raise
