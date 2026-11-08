"""The release flow's publication gate: check the published version
is consistent.

A published version is the factory workflow file and its runtime tree
(the .github scripts, the stage scripts, the pi prompt templates) as
one: the ref the consumer's uses: line pins selects a tag, the tag
points at a commit of the factory repo, and that commit's tree carries
both halves — the file GitHub fetches for the run, and the runtime
tree the file's stage steps execute, which the run's first job fetches
at the called ref. The file itself is static plain text: the embed the
old design owed — the runtime tree in the file as a base64 tarball
behind stage 1's first step's heredoc, the release pipeline rewriting
it into the file before every tag — is retired (a binary payload in a
file that must be plain text, and the bloat that took the published
file past its max allowed size).

The check (its `--check` mode; the release flow runs it as its pre-tag
gate step and fails a publish it would cut from here with the exact
cause) verifies the version the tag would point at — the committed
file, the committed tree — is consistent:

- the file is plain text — it stores no binary payload: no NUL byte,
  and the retired embed's form is not back (the
  CW_EMBEDDED_RUNTIME_TAR heredoc region, a base64-blob line of its
  wrapped body);
- the file is at most 500kb — read conservatively as 500,000 bytes
  (decimal): a file at most that is also under 500×1024, so the cap
  holds under either reading of `kb` — the max allowed size for the
  file;
- the tagged commit's tree carries the runtime tree the file's stage
  steps execute: the canonical marker files the workflow's own
  verification step checks resolve within the committed tree, and
  every script the file's stage steps reference resolves to a file
  the curation below carries (a generalisation of the
  canonical-marker check: a curation drift that the stage steps'
  references would not anticipate fails the gate, before the tag).

The structure check (its `--verify-structure` mode; the release flow
runs it as the second pre-tag gate step) verifies the committed file is
PARSER-SAFE — issue #106: the runner's workflow parser diverged from
the standard YAML engines on the published file (N+1 phantom steps per
job, the `extract` job dropped from the run's job graph, a step script
truncated mid-body — a run that collapsed while every listed job read
success/skipped). Standard engines (PyYAML, YAML 1.1; ruamel, YAML
1.2) read the same bytes cleanly, so the trigger is a file shape the
runner's parser mishandles — the gate keeps the file in the shape both
standard engines agree on, and fails a publish that would leave it out
of that shape:

- the job/step structure parses to the pinned graph under every
  standard engine available to the checker (the release flow installs
  both PyYAML and ruamel before the gate; an interpreter with neither
  reports the engine half as not run, and the line lint below still
  guards the file) — the 10 jobs in pipeline order (`extract` among
  them: its absence is the run's collapse), and the pinned step count
  of every job (a drift in either fails the gate until it is re-pinned
  deliberately);
- no step mapping declares keys after its `run` block scalar — a block
  that terminates inside the step mapping (a dedented sibling key
  ending the block) is the divergence's trigger site (the published
  file's two `pr` job steps declared `env:` after their `run: |`
  blocks); every step's `run` is its step mapping's last key;
- no step carries a giant inline body — the flat-file discipline: the
  stage scripts live in the runtime tree (the file's steps launch them
  from the stash), and a `run` block over the line budget would be
  exactly the body shape the parser mishandles (the published file's
  486-line report body, its 165-line baseline body);
- no run block's heredoc terminator is indented past the block's base
  indent — the block scalar's dedent strips the base, and a bash
  heredoc terminator must then sit at column 0 in the executed script
  (indented past the base it keeps its extra indent after the dedent,
  is not a terminator, and the shell reads the rest of the step's
  script as the heredoc's body — the step dies at run time while the
  file parses cleanly and keeps every other shape above: the trigger
  step of the published version's failed runs #151/#152 died exactly
  here, its issue-meta heredoc's terminator four deeper than the
  block's base — issue #112); and no run block opens a heredoc it
  never terminates (a script ending mid-heredoc is the same death —
  bash's "here-document delimited by end-of-file").

A maintainer who changes the runtime tree commits the tree; the tag
the release flow cuts points at a commit whose tree is consistent
with the file — no per-release rewrite of the file is owed. Versions
published before the embed's retirement keep the embedded form — they
are immutable published artifacts that still decode their own tree;
the gate governs the versions published from this change on.

Plain-stdlib by design (no third-party imports): a runner whose
system python is externally-managed can still run it, and the
contract test (tests/test_embedded_runtime.py) loads it by file path
with no third-party import available (the loader idiom follows
tests/test_release_contract.py's `release-number.py` precedent).
"""
from __future__ import annotations

import os
import re
import sys

# The runtime tree the stage steps execute, repo-relative — the curated
# subset of the checkout: the shared .github scripts (the stage code
# imports from here), the .github actions' stage scripts (the inlined
# steps run them from the stash), and the pi prompt templates (the pi
# invocations read them from here). The first job of a run fetches
# exactly these prefixes (its sparse checkout) into the stash,
# preserving the repo-relative layout the stage code resolves against
# ($RUNNER_TEMP/cw/stash), and the gate verifies the committed tree
# against this same curation.
RUNTIME_PREFIXES = (".github/scripts", ".github/actions", "pi-prompts")

# The max allowed size for the published workflow file, read
# conservatively as 500,000 bytes (decimal): a file at most that is
# also under 500×1024, so the cap holds under either reading of `kb`.
MAX_ALLOWED_SIZE = 500_000

# The retired embed's payload-region anchor inside the workflow file:
# its reappearance in the file is the binary payload's form back.
EMBED_MARKER = "CW_EMBEDDED_RUNTIME_TAR"

# The canonical marker files the workflow's own verification step
# checks the fetched tree against (the files the stage steps run from
# and the shared code resolves against) — the same set, here as the
# committed tree's half of the file↔tree consistency: a tagged
# commit's tree missing one is not the tree the file's stage steps
# execute.
CANONICAL_RUNTIME_FILES = (
    ".github/scripts/common.py",
    ".github/scripts/stages.py",
    ".github/scripts/gherkin-validate.py",
    ".github/scripts/release-number.py",
    ".github/actions/setup-pi/stage.py",
    ".github/actions/baseline/stage.py",
    ".github/actions/extract-stage/stage.py",
    ".github/actions/plan-stage/stage.py",
    ".github/actions/implement-stage/stage.py",
    ".github/actions/review-stage/stage.py",
    ".github/actions/pr-open/stage.py",
    ".github/actions/pi-run/stage.py",
    ".github/actions/gates-stage/stage.py",
    ".github/actions/report/stage.py",
    ".github/actions/guard-check/guard-check.py",
    "pi-prompts/requirements.md",
    "pi-prompts/plan.md",
    "pi-prompts/implement.md",
    "pi-prompts/review.md",
    "pi-prompts/pr-body.md",
)

# The script references the file's stage steps make — a path under the
# runtime tree the step runs (a stage script the step launches, a
# shared module its python binds, a prompt template the pi invocation
# reads): every one must resolve to a file present in the committed
# tree. The forms the inlined steps use — repo-relative, or prefixed
# by the stash the step resolves against
# ($RUNNER_TEMP/cw/stash/<repo-relative path> — the prefix the match
# drops) — both end in the path under the runtime tree.
SCRIPT_REFERENCE = re.compile(
    r"\.github/(?:scripts|actions)/[A-Za-z0-9._/-]*[A-Za-z0-9_]\.(?:py|md)"
    r"|pi-prompts/[A-Za-z0-9._-]*[A-Za-z0-9_-]\.md")


def repo_root() -> str:
    """Repo root from this file's location (…/.github/scripts/…)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def default_factory_path() -> str:
    return os.path.join(repo_root(), ".github", "workflows", "factory.yml")


def runtime_files(root: str):
    """[(arcname, abspath)] — the curated runtime tree, sorted by arcname:
    every regular file under the curated prefixes, `__pycache__` dirs
    and *.pyc excluded (the tracked tree is source; a compiled cache
    would make the curation environment-dependent). This is the file
    set the gate verifies: the tree the first job's fetch materialises
    and the tag the flow cuts must carry."""
    out = []
    for prefix in RUNTIME_PREFIXES:
        base = os.path.join(root, prefix)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
            for fname in sorted(filenames):
                if fname.endswith(".pyc"):
                    continue
                abspath = os.path.join(dirpath, fname)
                arcname = os.path.relpath(abspath, root)
                out.append((arcname.replace(os.sep, "/"), abspath))
    out.sort(key=lambda p: p[0])
    return out


def parse_engines():
    """[(name, loader)] — the standard YAML engines importable in this
    interpreter: PyYAML (YAML 1.1) and ruamel (YAML 1.2, pure python).
    The structure check's engine half runs the published file through
    every engine available: with both, both must agree on the job/step
    structure; with one, that one's parse is the assertion; with
    neither, the engine half reports not run (the line lint still
    guards the file) — the release flow installs both before its gate
    step, so the gate itself always runs the engine half.
    (The issue's parse comparison is the basis: the published file's
    bytes parse cleanly under exactly these engines — 10 jobs including
    `extract`, the per-job step counts — while the runner's parser
    reads the same bytes differently. The gate's job is to keep the
    file in the shape the standard engines agree on, so a divergence is
    caught at publish, not at the run's collapse.)"""
    engines = []
    try:
        import io
        import yaml
        engines.append(("PyYAML (YAML 1.1)",
                        lambda t: yaml.safe_load(io.StringIO(t))))
    except ImportError:
        pass
    try:
        import io
        from ruamel.yaml import YAML
        def _ruamel(t):
            y = YAML(typ="safe", pure=True)
            return y.load(io.StringIO(t))
        engines.append(("ruamel (YAML 1.2)", _ruamel))
    except ImportError:
        pass
    return engines


# The published workflow's job graph — the 10 jobs in pipeline order
# (the file's own header: "15 logical stages over 10 jobs"). The
# structure check asserts the parse yields exactly this set of job keys
# in this order — `extract` among them: its absence from the run's job
# graph is the failed run's collapse (the runner's parser dropped the
# job; every downstream stage skipped; the report's old verdict read
# the missing stage's absent outcome line as a failure).
EXPECTED_JOBS = ("trigger", "setup-pi", "baseline", "extract", "plan",
                 "implement", "review", "pr", "gates", "report")

# The pinned step count of every job — the parse comparison of the
# published file under the standard engines (the issue's repro table).
# The gate asserts a standard-engine parse reproduces exactly these
# counts: a change to the file's job/step SHAPE fails the gate until it
# is re-pinned deliberately here — the published file must not drift in
# structure silently (a drift is where a parser divergence would enter
# unpublish-verified), and the pin names the exact expected shape in
# the gate's failure message.
EXPECTED_STEP_COUNTS = {
    "trigger": 7,
    "setup-pi": 6,  # re-pinned: +1 — the job's Setup Node step (a pristine
    # runner has no npm for stage 2's pi install: node is provisioned by
    # the job, never presumed)
    "baseline": 9,  # re-pinned: +1 — the job's second restore step (the
    # setup-pi stage's artefact, downloaded alongside the trigger's, so
    # the cumulative chain carries the setup state past the
    # setup→baseline hop — every later artefact needs it, and the first
    # pi-calling stage after baseline dies at the pi call it cannot
    # resolve without it; run 42480359617)
    "extract": 8,
    "plan": 8,
    "implement": 10,
    "review": 9,
    "pr": 16,
    "gates": 10,
    "report": 15,
}

# A step's `run` block scalar over this many lines is a giant inline
# body: the flat-file discipline moves the stage bodies into the
# runtime tree (the file's steps launch the scripts from the stash),
# and the oversized block is the body shape the runner's parser
# mishandles (the published file's 486-line report body and 165-line
# baseline body were the candidate trigger sites).
MAX_RUN_BLOCK_LINES = 200


def _step_key_scan(text: str):
    """The line-lint half of the structure check — engine-independent
    (plain stdlib, it runs where no YAML engine imports): walk the file
    the way the workflow's own indentation discipline defines it (jobs
    at two indent, job keys at four, step list items at six, step keys
    at eight), and yield, for every step, (the step's name, the
    ordered keys of its mapping with their line numbers, and the extent
    of its `run` block scalar as [key line, content start, block
    indent, line count, the block's lines (line, raw) in order]).
    The three shape tests then run on that scan: a step that declares
    keys AFTER its `run` key (a block scalar that terminates inside the
    step mapping — the divergence's trigger site), a `run` block
    scalar past the giant-body budget, and a run block whose heredoc
    terminator the block's dedent leaves off column 0 in the executed
    script (the shape `heredoc_terminator_violations` checks — the
    engine half cannot see it)."""
    lines = text.splitlines()
    jobs_key = None
    for i, ln in enumerate(lines):
        if ln.startswith("jobs:"):
            jobs_key = i
            break
    if jobs_key is None:
        return
    step = [None, [], None]  # name, [(line, key)], run-state
    def flush():
        if step[0] is not None:
            yield (step[0], list(step[1]), step[2])
        step[0], step[1], step[2] = None, [], None
    for i in range(jobs_key + 1, len(lines)):
        ln = lines[i]
        if not ln.strip() or ln.lstrip().startswith("#"):
            # a blank line inside an open run block stays in the block
            # (a block scalar keeps its blank lines, and the scan skips
            # comments everywhere) — collected here, in order, for the
            # heredoc-terminator lint that walks the block's lines
            if step[2] is not None and step[2][1] is not None:
                step[2][3].append((i, ln))
            continue
        ind = len(ln) - len(ln.lstrip())
        body = ln.strip()
        if ind < 2:
            for st in flush():
                yield st
            continue
        if ind == 2:
            # a job key ends the current job's last step
            for st in flush():
                yield st
            continue
        if ind == 4:
            for st in flush():
                yield st
            continue
        if ind == 6 and body.startswith("- "):
            for st in flush():
                yield st
            rest = body[2:].strip()
            step[0] = rest
            if ":" in rest:
                k = rest.split(":", 1)[0].strip()
                v = rest.split(":", 1)[1].strip()
                if k:
                    step[1].append((i, k))
                if k == "run" and v.startswith(("|", ">")):
                    step[2] = [i, None, 0, []]
            continue
        if ind == 8 and ":" in body and not body.startswith("-"):
            k = body.split(":", 1)[0].strip()
            v = body.split(":", 1)[1].strip()
            if k:
                step[1].append((i, k))
            if k == "run" and v.startswith(("|", ">")):
                step[2] = [i, None, 0, []]
            continue
        # a line at or below the run block's content indent ends the
        # block; a line at or beyond it extends it
        if step[2] is not None:
            if step[2][1] is None and ln.strip():
                step[2][1] = ind
            if step[2][1] is not None:
                if ind >= step[2][1]:
                    step[2][2] += 1
                    step[2][3].append((i, ln))
                    continue
                step[2] = None
    for st in flush():
        yield st


# A bash heredoc opener: `<<` (the lookbehind keeps a `<<<` herestring
# out — the third `<` opens no heredoc), an optional `-` (whose
# terminators bash strips leading tabs from), an optionally quoted
# delimiter word, the matching closing quote where one opened.
_HEREDOC_OPEN = re.compile(
    r"(?<!<)<<?-?(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def heredoc_terminator_violations(text: str) -> list[str]:
    """The run-block heredoc-terminator check — the shape no YAML
    engine sees: every `run` block scalar the runner dedents to its
    base indent (the block's first content line) before the shell reads
    it, and a bash heredoc terminator must sit at column 0 in that
    executed script. A terminator line indented deeper in the file
    keeps its extra indent after the dedent — it is then not a
    terminator — and the shell reads the rest of the step's script as
    the heredoc's body: the "here-document delimited by end-of-file"
    warning, then a syntax error, the step dead at run time while the
    file parses cleanly and keeps every other structure shape the gate
    checks (the trigger step of the published version's failed runs
    died exactly this way — issue #112).

    `text` is a workflow file; one violation per —
    - heredoc terminator the dedent leaves off column 0 (a `<<DELIM`
      or `<<'DELIM'`/`<<"DELIM"` terminator indented past the block's
      base — any extra indent breaks it; a `<<-DELIM` terminator whose
      extra indent carries a space — the dash strips leading tabs
      only);
    - heredoc the block opens but never terminates (the executed
      script ends mid-heredoc: the same death, the terminator line
      absent altogether).

    Plain-stdlib by design: the check walks the file the workflow's
    own indentation discipline defines it (the `_step_key_scan`
    shape), no YAML engine required."""
    violations = []
    for step_name, _keys, run_state in _step_key_scan(text):
        if run_state is None:
            continue
        _key_line, base, _count, block_lines = run_state
        if base is None:
            continue
        pending = {}  # delimiter -> (the opener's dash, opener line)
        for lineno, ln in block_lines:
            if not ln.strip():
                continue
            stripped = ln.strip()
            if stripped.startswith("#"):
                # a comment opens no heredoc (outside a pending one it
                # is skipped; inside one it is body — the pending set
                # it leaves unchanged)
                continue
            # a pending heredoc's terminator: the line is the
            # delimiter word itself
            closing = [d for d in pending if stripped == d]
            if closing:
                for d in closing:
                    dash, _opener = pending.pop(d)
                    lead = ln[:len(ln) - len(ln.lstrip())]
                    extra = lead[base:] if len(lead) > base else ""
                    if dash:
                        # the dash strips the terminator's leading
                        # tabs: the executed line must be tabs (only)
                        # plus the word
                        ok = all(c == "\t" for c in extra) \
                            and ln[len(lead):] == d
                    else:
                        # no dash: the executed line is the word alone
                        # at column 0 — any indent past the base stands
                        ok = extra == "" and ln[len(lead):] == d
                    if not ok:
                        violations.append(
                            f"step {step_name!r}'s run block line "
                            f"{lineno + 1}: the heredoc terminator "
                            f"{d!r} is indented {len(lead)} — its "
                            f"block's base is {base}; the runner's "
                            f"dedent strips the base and leaves the "
                            f"terminator {len(lead) - base} past "
                            f"column 0 in the executed script, where a "
                            f"{'<<-' if dash else '<<'}{d} terminator "
                            "must sit at column 0: the shell would "
                            "read the rest of the step's script as the "
                            "heredoc's body (the 'here-document "
                            "delimited by end-of-file' warning, then a "
                            "syntax error) and the step dies at run "
                            "time on a file every standard engine "
                            "parses cleanly")
                continue
            # an opener line (a line inside a pending heredoc's body is
            # body — bash reads it as that heredoc's content until the
            # terminator)
            if not pending:
                for om in _HEREDOC_OPEN.finditer(ln):
                    d = om.group(2)
                    if d not in pending:
                        pending[d] = (om.group(0)[2] == "-", lineno)
        for d, (dash, opener_ln) in pending.items():
            violations.append(
                f"step {step_name!r}'s run block line {opener_ln + 1}: "
                f"the `{'<<-' if dash else '<<'}{d}` heredoc is opened "
                "but never terminated inside the block — the executed "
                "script ends mid-heredoc (bash's 'here-document "
                "delimited by end-of-file'), the step dies at run time "
                "on a file every standard engine parses cleanly")
    return violations


def single_brace_context_violations(text: str) -> list[str]:
    """A `${` with whitespace after the opening brace, in a step
    field value or a run body — the single-brace corruption the
    console-mirror re-indent left in the baseline/pr/report stage
    steps (run #154's baseline step died at process start on
    `working-directory: ${ github.workspace }` — the second
    corruption of the same three steps whose heredoc terminators
    `heredoc_terminator_violations` covers).

    The runner's expression syntax is `${{ }}` — both braces, no
    space: a `${` whose next character is whitespace is not an
    expression, and the runner passes the literal text through as
    the field's value. A `working-directory` then names a path that
    does not exist — the runner cannot start the step's process
    there (the job dies before the step's first line runs) — and
    inside a run body the same text is a bash syntax error (a
    `${` whose first character is whitespace opens no parameter).
    Plain-stdlib by design, on each step's own line range (the
    `_step_key_scan` shape); comments are skipped, so a line
    documenting the corruption can still quote it."""
    violations = []
    pattern = re.compile(r"\$\{\s")
    lines = text.splitlines()
    for step_name, keys, run_state in _step_key_scan(text):
        if not keys:
            continue
        start = min(l for l, _ in keys)
        block_ends = ([run_state[3][-1][0]]
                      if run_state is not None and run_state[3]
                      else [])
        end = max([l for l, _ in keys] + block_ends)
        for lineno in range(start, min(end + 1, len(lines))):
            ln = lines[lineno]
            body = ln.strip()
            if not body or body.startswith("#"):
                continue
            if not pattern.search(ln):
                continue
            snippet = body if len(body) <= 72 else body[:69] + "…"
            violations.append(
                f"step {step_name!r} line {lineno + 1} holds "
                f"`{snippet}` — a `${{` with whitespace after the "
                "opening brace is not a context expression (the "
                "runner's expression syntax is `${{ }}` — both "
                "braces, no space): the runner passes the literal "
                "text through as the field's value, a "
                "working-directory names a directory that does not "
                "exist and the step's process cannot start there "
                "(inside a run body the same text is a bash syntax "
                "error)")
    return violations


def verify_structure(text: str, expected_jobs=EXPECTED_JOBS,
                     expected_step_counts=EXPECTED_STEP_COUNTS,
                     max_run_block_lines=MAX_RUN_BLOCK_LINES):
    """(ok, message) — the parser-safety gate: the committed file's
    job/step structure (under every standard engine available) and its
    line shapes (the engine-independent lint) match the pinned safe
    form. Fails, with the exact cause, when —
    (a) a standard engine's parse does not yield the pinned job graph
        (a job missing — `extract`'s absence is the run's collapse — or
        a job's step count off the pin);
    (b) the available engines disagree with each other on the
        job/step structure (a file the standard engines themselves
        read differently is not a file a runner parser can be trusted
        with);
    (c) a step mapping declares keys after its `run` block scalar
        (the block terminates inside the step mapping — the divergence's
        trigger site);
    (d) a `run` block scalar is a giant inline body past the budget
        (the flat-file discipline: the body belongs in the runtime
        tree);
    (e) a run block's heredoc terminator is indented past the block's
        base indent (the block scalar's dedent leaves it off column 0
        in the executed script — not a terminator there: the shell
        reads the rest of the step's script as the heredoc's body and
        the step dies at run time on a file the engines parse
        cleanly), or a run block opens a heredoc it never terminates
        (the executed script ends mid-heredoc: bash's "here-document
        delimited by end-of-file");
    (f) a step field value or run-body line carries a single-brace
        `${` with whitespace after the opening brace — not a
        context expression (the runner's syntax is `${{ }}`, both
        braces, no space): the runner passes the literal text
        through, a `working-directory` names a directory that does
        not exist and the step's process dies at start — the
        console-mirror re-indent's second corruption of the three
        steps whose heredoc terminators check (e) covers (run
        #154's baseline step)."""
    violations = []
    # (1) the engine half — every standard engine available must parse
    # the file to the pinned job/step structure
    engines = parse_engines()
    if not engines:
        violations.append(
            "no standard YAML engine (PyYAML, ruamel.yaml) is importable "
            "in the checker — the engine half of the structure check did "
            "not run (the line lint below still guards the file; the "
            "release flow installs both engines before its gate step)")
    else:
        structures = {}
        for name, load in engines:
            try:
                doc = load(text)
            except Exception as e:
                violations.append(
                    f"{name} failed to parse the committed workflow "
                    f"file ({e}) — a file a standard engine cannot parse "
                    "is not a version to publish")
                continue
            jobs = doc.get("jobs") if isinstance(doc, dict) else None
            if not isinstance(jobs, dict):
                violations.append(
                    f"{name}'s parse of the committed workflow file holds "
                    "no jobs mapping — the file is not a workflow the "
                    "pinned job graph reads from")
                continue
            structures[name] = (
                list(jobs.keys()),
                {k: len(v.get("steps", [])) if isinstance(v, dict) else -1
                 for k, v in jobs.items()})
        for name, (job_keys, counts) in structures.items():
            for j in expected_jobs:
                if j not in job_keys:
                    violations.append(
                        f"{name}'s parse of the committed workflow file "
                        f"is missing the `{j}` job — the pinned job graph "
                        f"({', '.join(expected_jobs)}) is the factory's "
                        "shape: a missing job is a run whose downstream "
                        "stages skip and whose report reads a false "
                        "failure (the issue's collapse)")
            extra = [j for j in job_keys if j not in expected_jobs]
            if extra:
                violations.append(
                    f"{name}'s parse of the committed workflow file holds "
                    f"job(s) outside the pinned graph: {extra} — the "
                    "published file's job shape has drifted")
            if list(job_keys) != list(expected_jobs):
                violations.append(
                    f"{name}'s parse reads the jobs in a different order "
                    f"than the pinned pipeline ({', '.join(expected_jobs)}): "
                    f"{job_keys}")
            for j, want in expected_step_counts.items():
                got = counts.get(j)
                if got != want:
                    violations.append(
                        f"{name}'s parse counts {got} steps in the `{j}` "
                        f"job — the pinned count is {want} (the published "
                        "file's job/step shape drifted; re-pin the gate "
                        "deliberately where the change is intended)")
        names = list(structures)
        for i in range(len(names)):
            for j2 in range(i + 1, len(names)):
                if structures[names[i]] != structures[names[j2]]:
                    violations.append(
                        f"the standard engines disagree on the committed "
                        f"file's structure — {names[i]} and {names[j2]} "
                        "parse different job/step shapes: a file the "
                        "standard YAML families read differently is not a "
                        "file a runner's parser can be trusted with")
    # (2) the line-lint half — engine-independent shape checks
    for step_name, keys, run_state in _step_key_scan(text):
        key_names = [k for _, k in keys]
        if "run" in key_names:
            ri = key_names.index("run")
            after = [k for k in key_names[ri + 1:]]
            if after:
                violations.append(
                    f"step {step_name!r} declares keys {after} AFTER its "
                    "`run` key — the step's block scalar terminates inside "
                    "the step mapping (a dedented sibling key ends the "
                    "block): the shape the runner's workflow parser "
                    "diverges on (issue #106's two `pr` job steps), and "
                    "the published file's steps keep `run` as their step "
                    "mapping's last key (reorder the step — env before "
                    "run)")
            if run_state is not None and run_state[2] > max_run_block_lines:
                violations.append(
                    f"step {step_name!r}'s `run` block is "
                    f"{run_state[2]} lines — a giant inline body past the "
                    f"{max_run_block_lines}-line budget: the body belongs "
                    "in the runtime tree (the file's step launches the "
                    "stashed script), not in the published file")
    # (3) the heredoc-terminator half — a run block whose heredoc
    # terminator is indented past the block's base (the dedent leaves
    # it off column 0 in the executed script: the shell reads the rest
    # of the step's script as the heredoc's body, the step dies at run
    # time) or a heredoc the block opens but never terminates (the
    # script ends mid-heredoc) — valid YAML, the pinned job/step
    # graph, no keys after the run block, the line budget met: every
    # other gate shape holds, and this is the one the engine half
    # cannot see (the failure that killed the published version's
    # trigger step — issue #112)
    violations.extend(heredoc_terminator_violations(text))
    # (4) the single-brace-context half — a step field value or run
    # body line carrying a `${` with whitespace after the opening
    # brace (not the runner's `${{ }}` expression syntax: the
    # literal text is passed through as the field's value, a
    # working-directory names a directory that does not exist and
    # the step's process cannot start — the console-mirror
    # re-indent's second corruption of the three steps check (3)
    # covers, run #154's baseline step; valid YAML, the pinned
    # job/step graph, every other gate shape holding)
    violations.extend(single_brace_context_violations(text))
    if violations:
        return False, ("the committed workflow file is not parser-safe — "
                       + "; ".join(violations))
    return True, (
        "the committed workflow file is parser-safe — its job/step "
        "structure parses to the pinned graph under "
        + (" and ".join(n for n, _ in engines) if engines
           else "no standard engine (engine half not run)")
        + "; no step declares keys after its run block; no run block "
        f"exceeds the {max_run_block_lines}-line giant-body budget; no "
        "run block's heredoc terminator is indented past the block's "
        "base, no block opens a heredoc it never terminates, and no "
        "step field or run body carries a `${` with whitespace after "
        "the opening brace")


def check(root: str, path: str):
    """(ok, message) — the publication gate's check: the version the
    tag would point at (the committed file, the committed tree) is
    consistent. Fails, with the exact cause, when —
    (a) the file is not plain text: it stores a binary payload (a NUL
        byte, undecodable bytes, or the retired embed's form — the
        CW_EMBEDDED_RUNTIME_TAR heredoc region, a base64-blob line);
    (b) the file is past the max allowed size (at most 500kb — read
        conservatively as 500,000 bytes);
    (c) the committed tree carries no runtime tree the file's stage
        steps execute: a canonical marker file the workflow's own
        verification step checks is missing from the tree, or a script
        the file's stage steps reference resolves to no file the
        curation carries (a curation drift that leaves a tree the
        stage steps cannot run from)."""
    with open(path, "rb") as f:
        data = f.read()
    if b"\x00" in data:
        return False, (
            "the committed workflow file holds a NUL byte — it stores "
            "binary content, and a workflow file must be plain text")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        return False, (
            "the committed workflow file does not decode as text — it "
            f"stores binary content ({e})")
    if EMBED_MARKER in text:
        return False, (
            "the committed workflow file opens the retired "
            f"{EMBED_MARKER} heredoc — the embedded base64 tarball's "
            "form is back in a file that must be plain text")
    for ln in text.splitlines():
        body = ln.strip()
        if body and re.fullmatch(r"[A-Za-z0-9+/]{64,}={0,2}", body):
            return False, (
                "the committed workflow file holds a base64 blob line "
                "— the retired embed's form (the runtime tree's base64 "
                f"across the heredoc's wrapped lines): {body[:40]!r}…")
    if len(data) > MAX_ALLOWED_SIZE:
        return False, (
            f"the committed workflow file is {len(data)} bytes — past "
            f"its max allowed size (at most 500kb, read "
            f"conservatively as {MAX_ALLOWED_SIZE} bytes)")
    tree = set(arcname for arcname, _ in runtime_files(root))
    for marker in CANONICAL_RUNTIME_FILES:
        if marker not in tree:
            return False, (
                f"the tagged commit's tree is missing {marker} — the "
                "canonical runtime files the file's stage steps execute "
                "must resolve within it")
    for ref in sorted(set(SCRIPT_REFERENCE.findall(text))):
        if ref not in tree:
            return False, (
                f"the file's stage steps reference {ref} — the "
                "committed tree carries no such file: a curation "
                "drift that leaves a tree the stage steps cannot "
                "run from")
    return True, (
        f"the published version is consistent — the committed workflow "
        f"file is plain text ({len(data)} bytes, within the max "
        f"allowed size of {MAX_ALLOWED_SIZE}), and the tagged "
        f"commit's tree carries the runtime tree its stage steps "
        f"execute ({len(tree)} curated files; every canonical marker "
        f"and stage-step script reference resolves)")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = repo_root()
    path = next(
        (a for a in argv if not a.startswith("-")),
        default_factory_path())
    # The release flow's two publication gates are the only modes: the
    # file↔tree consistency check (`--check` — the file is static plain
    # text, nothing here rewrites it: the splice that once rewrote the
    # file's payload region retires with the embed, a maintainer who
    # changes the runtime tree commits the tree, and the gate verifies
    # the tag's commit against the file) and the parser-safety structure
    # check (`--verify-structure` — the file's job/step graph and its
    # line shapes stay in the form the standard engines agree on, where
    # the runner's parser does not diverge). The no-argument form runs
    # both, a local rehearsal of the flow's two pre-tag gates.
    if "--verify-structure" in argv:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        ok, message = verify_structure(text)
        print(("ok:   " if ok else "INCONSISTENT: ") + message)
        return 0 if ok else 1
    if "--check" in argv:
        ok, message = check(root, path)
        print(("ok:   " if ok else "INCONSISTENT: ") + message)
        return 0 if ok else 1
    ok1, m1 = check(root, path)
    with open(path, encoding="utf-8") as f:
        ok2, m2 = verify_structure(f.read())
    print(("ok:   " if ok1 else "INCONSISTENT: ") + m1)
    print(("ok:   " if ok2 else "INCONSISTENT: ") + m2)
    return 0 if (ok1 and ok2) else 1


if __name__ == "__main__":
    sys.exit(main())
