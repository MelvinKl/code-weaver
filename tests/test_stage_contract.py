"""Unit tests pinning the stage contracts the post-review fix loop fixed.

Plain-stdlib by design (no third-party imports): the stage-10 driver
(`make test` → `python3 tests/run.py`) is a stdlib-only plain-python
contract, and no-argument `test_` functions are auto-discovered by both
runners (this runner and house CI's `pytest tests/`).

The pins (one per scenario the fix loop had to fulfil):
- the extract stage's entry logic branches on the target's requirements
  directory: an empty issue body takes the "no delta requirements" stop
  only where the target HAS a requirements directory (requirement-
  extraction "An empty issue body does not produce invented requirements"
  — adjusted: the new Given "the target project has a requirements
  directory" narrows the stop's precondition), and a target without one
  is a first factory run on that project — the stage proceeds to its
  generation loop with the full-derivation prompt (derive the full
  requirement set from the project's current code, documentation and
  tests; a source the project lacks is skipped rather than failing; the
  .feature files it writes create the requirements directory; the
  template's first-run clause governs the shape) (requirement-extraction
  "A first-time run without a requirements dir extracts the full
  requirements" — new);
- the extract stage is the `@`-file slice of the context contract —
  setup-pi "pi reads the project files as context"; requirement-extraction
  "requirements are derived from the project itself" — while the other
  stages keep the path-referenced slice (configuration "project files are
  referenced by path, not injected into the pi call");
- the extract prompt places the delta by topic — extending the existing
  topic file, creating a new file only for a topic no file yet covers
  (requirement-extraction "extraction places the delta by topic") — and
  tolerates arc42 structure variance (safety "the factory tolerates arc42
  structure variance");
- the consumer workflow pins the oracle's owner at a version tag — a
  single increasing number, the current scheme (the retired semver ref
  shape is gone) — and wires the run's harness providers through its
  secrets block; the README's example is documentation, not a pinned
  surface — the suite no longer compares its ref against the deployed
  workflow, so a release ref bump on one surface never fails the suite
  until the other is synced (reuse-by-ref "the factory is invoked as a
  reusable workflow", "every published version is a stable ref");
- the factory workflow is self-contained: every stage's steps are inlined
  in the workflow file — no own-action `uses:` reference remains (an
  own-action ref would have to be fully qualified and pinned to a ref the
  release flow could only make consistent by rewriting a workflow file,
  which it must never do; a relative path would resolve against the
  calling repo's checkout) — and every stage job's first step stashes the
  called repo's runtime tree before the first checkout, the stage steps
  running their scripts from that stash (reuse-by-ref "the factory
  workflow is self-contained", "a published version is self-contained");
- the pr job generates the PR body with pi from the requirements, the
  review-stage's verdict scope is delta-bounded (test-and-review: pi
  judges the scenarios of the feature files this run changed, plus the
  scenarios the run's changed tests reference — the accumulated oracle is
  not re-judged every run — and a run that changed no requirements and no
  referencing tests passes vacuously instead of failing as unparseable);
- the pr job generates the PR body with pi from the requirements, the
  plan and the review (pr-and-gates "a pull request is opened against
  the target branch"), and the template fallback — used when the pi call
  produced no body — describes the issue it implements: the source
  issue's number and title read from the trigger's state files (a body
  still names the issue where the job-env relay dropped the values), the
  issue's plan embedded, the requirement scenarios the run changed
  against the baseline listed, and no resolved-configuration dump
  (pr-and-gates "the PR body describes the issue it implements");
- the reviewer's report is fed into the fixer: the review runs on every
  iteration's suite output — red or green (a red suite is never a pass,
  so the review's own breakdown cannot hide one) — and its full captured
  output (the verdict block with each line's evidence, the UNFULFILLED
  lines' "what's missing / what the fix must do", the note on what the
  tests don't cover) is mirrored per iteration into the state dir; the
  fix directive names the report by path (the fixer reads it on demand —
  the no-injection idiom the review call itself uses for the test output)
  and it joins the fix call's path-referenced context; a red iteration
  whose review breaks keeps the fix loop running on the raw output, while
  the same breakdown on a green suite still fails the stage (the oracle
  cannot be assumed green) (test-and-review "The reviewer's report is fed
  into the fixer", "The review judges every iteration, red or green");
- the report stage's AI-activity section falls back to the top-level
  arc42 markdown when the doc dir is absent (reporting "the arc42
  documents the AI activity"; safety "an audit trail exists for human
  review");
- the report stage's final status report lists the run's total input and
  output tokens and the total cost — assembled from the per-call usage
  records in the state dir, the cost derived from the recorded usage, the
  run's resolved model, and the run's model configuration itself — the
  rates are the resolved model's `cost` entry in the configuration the
  setup stage materialises (a non-empty PI_MODELS secret wins over the
  repo file .pi/agent/models.json, and the report lists the source it
  priced from); a model with no cost entry is listed as unpriced — and a
  failed run's report covers the calls made before the stop (issue-43 "the
  final report lists the input and output tokens used during the run",
  "the final report lists the total cost of the run", "the usage and cost
  of a failed run are reported too");
- the report stage re-reads the PR after editing its body: a verified
  completion keeps the pointer comment (the PR body and the issue comment
  list the same usage numbers — one ledger, one set of figures), while a
  completion that could not be applied (the PR was already merged) makes
  the comment self-contained; a successful run closes the source issue
  and a failed run leaves it open (reporting "the PR description carries
  the same usage numbers as the issue comment", "a successful run closes
  the source issue", "a failed run leaves the source issue open");
- the validator skips-not-fails where the parser port is absent
  (test-and-review "the suite runs on an interpreter without pytest");
- the factory's max-loops default matches the oracle's Given (5) and the
  doc surface that repeats the value agrees with it, while the token budget
  is gone from the configuration surface (no max-tokens row on the doc
  surfaces)
  (configuration "the loop caps are configurable", "a loop cap of 0 means
  no cap");
- the factory's dependency-upgrade setting rides the documented settings
  channel on its declaration side: the reusable workflow declares it on
  its input surface (a string input, optional — an older consumer's with:
  block stays schema-valid — default on), and the trigger's resolved-config
  log records it in both values it can take — the on default names the
  value, and a target-declared off value records that the run's pipeline
  runs without the dependency-upgrade stage, the run's stages, pull
  request and final status report unchanged by the upgrade's absence
  (configuration "the dependency-upgrade setting is configurable");
- a file list appears in a stage instruction only where the set is the
  instruction's scope (the plan's changed-requirements list, the guard's
  off-limits list in the repair instructions, the implement target's single
  plan file) and no instruction lists project files as context to rummage
  through (configuration "a stage instruction avoids file lists that carry
  no meaning");
- the implement guard runs inverted-allow: its deny set is the protected
  set (requirements, plans) and its allow set re-admits only the current
  issue's plan file — another issue's plan is a violation the guard repairs
  with a pi call (no stage re-run; a requirements-dir edit does not loop
  back to the plan stage) while the implementation's lane (code, tests,
  docs, new dirs) is admitted (implement "implementation may only edit the
  current issue's plan");
- the shared guard repairs a violation with a pi call, not a git revert
  plus a stage re-run: the repair instructions name the off-limits files,
  instruct the revert, and keep the stage's own work valid against the task
  its initial instructions gave it; a cleared re-check completes the stage
  without re-running its generation (the extract and implement checks —
  guard-rail "a leaking stage is repaired by a pi call, not restarted",
  "a requirement edited during implementation is reverted in place"), the
  repair calls ride the documented pi-call plumbing (each finished call
  appends its usage to the run's ledger — cost-and-token-usage "the usage
  totals cover every pi call the run made"), a cap exhausted without
  clearing fails the stage with the failure report listing the violations,
  and the implement stage's old plan loop-back hook is gone (guard-rail
  "guard repairs are capped", "all three checks share one implementation");
- the plan-check keeps the plan stage inside its one allowed plan file:
  any other change is reverted by the guard's pi call (the shared remedy)
  and the plan stage re-runs its generation on the guard's cleared-repair
  record — the guard re-checks the re-run, a clean plan stage completes
  without re-running, and the extract and implement checks' machinery never
  claims the record (plan "the plan stage may only touch its own plan
  file");
- the gates stage's run query is scoped to the PR's head sha server-side
  and paginated to the end of the result set, a head with no PR-triggered
  workflow is vacuously green after the grace window, and in-progress
  runs keep the gate polling until they complete (pr-and-gates "all
  PR-triggered workflows must be green", "the gate sees the PR's runs on
  a busy repo", "a head with no PR-triggered workflow is vacuously
  green");
- the stage-completion push: a generation stage that completes clean
  pushes the AI branch to the remote inside the stage machinery — the
  shared loop's completion points (after the guard has passed, and the
  no-op exit path), not only the job-tail workflow step a terminated
  run never reaches — so a run terminated after the stage completes
  loses none of the completed stage's work; the branch name resolves
  through the documented stage-value channel (the AI_BRANCH job env,
  the CW_/trigger-state fallback), an unresolvable branch (an idle
  run) skips with a log line, and a push that actually fails fails the
  stage (safety "A completed stage's work is committed and pushed to
  the AI branch"); for the implement stage, whose per-step loop runs one
  shared-loop call per step, the loop's completion push is a push after
  each completed step — before the stage starts the next step — and the
  sandbox proves that order from the sequence the fake model records
  (the step's commit, then the push, then the next step's pi call), the
  pushed tip's tree holding the flipped plan checkbox — a re-triggered
  run finds the step still done (implement "Every completed
  implementation step is committed and pushed");
- no test in the suite spawns the real git binary: the factory's python
  routes every git call through one mockable function (the shared
  module's git_exec — each inline workflow step carries its own copy of
  the same one-function shape), and the sandboxes mock that one function
  with an in-test fake model of a git repository (test-and-review "tests
  never invoke the real git binary") — a test's git child on the runner
  would read the runner's git configuration and could touch a real
  repository's state.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import types

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _read(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as f:
        return f.read()


# ── The in-test fake git ──────────────────────────────────────────────
#
# No test in this suite may invoke the real git binary (test-and-review
# "tests never invoke the real git binary"): a test's git child would
# read the runner's git configuration, and a test must never touch real
# repository state. The factory's production code routes every git call
# through one mockable function — common.git_exec, the factory's single
# git entry point (each inline workflow step carries its own copy of the
# same one-function shape) — and the sandboxes mock that one function
# with this small in-memory model of a git repository: commits as
# file-content snapshots, the worktree as the real temp files the test
# writes, pushes recorded (the model keeps them no-ops), and — where a
# sandbox names the model's events file — an ordered log of the model's
# git calls appended to that file, which the sandbox's fake `pi`
# interleaves with its own invocation lines. The production code under
# test runs its real logic against the fake; no process is ever spawned
# for a git call.

class _FakeRepo:
    """A model of one git repository: `commits` maps a sha to the tree
    it holds ({relpath: content}), `heads` lists the shas in commit
    order (HEAD = the last), `index` is the tracked set. The worktree is
    the real directory tree the test writes under `root` — the model
    reads it for the worktree side of every comparison. `pushes` records
    the push invocations the production code under test makes — each as
    (target branch, branch tip at the push moment), the model keeping a
    push a no-op: the stage-completion push the stage machinery makes at
    its completion points is asserted on by the stage-sandbox tests
    (safety: "a completed stage's work is committed and pushed to the AI
    branch"). `events_file` (None by default; a sandbox names it to turn
    the recording on) is the file the model appends one line to per git
    call it handles (the commit's new sha, the push's target branch and
    tip, the plain subcommand otherwise): where a sandbox must prove the
    order of the stage's git calls against the stage's pi calls — the
    implement sandbox's push-before-the-next-step assertion — its fake
    `pi` appends its own invocation line to the same file, so the test
    reads one ordered sequence interleaving the two (the pi subprocess
    runs while the stage process is blocked, the git calls run when it
    resumes — the appends are strictly ordered)."""

    def __init__(self, root):
        self.root = root
        self.commits = {}
        self.heads = []
        self.index = set()
        self.pushes = []
        self.events_file = None
        self._n = 0

    def _read(self, rel):
        with open(os.path.join(self.root, rel), "rb") as f:
            return f.read().decode("utf-8", "replace")

    def worktree_files(self):
        out = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            for fn in filenames:
                out.append(os.path.relpath(os.path.join(dirpath, fn),
                                            self.root).replace(os.sep, "/"))
        return sorted(out)

    def _resolve(self, ref):
        if ref == "HEAD":
            return self.heads[-1] if self.heads else None
        if ref.startswith("HEAD~") and ref[5:].isdigit():
            i = len(self.heads) - 1 - int(ref[5:])
            return self.heads[i] if 0 <= i < len(self.heads) else None
        return ref if ref in self.commits else None

    def _changed(self, ref_tree, paths):
        """(kind, path) pairs for the files that differ between the ref's
        tree and the worktree over the pathset — git's diff-against-a-
        commit compares the union of the commit's tree and the index: a
        file the ref knew is modified or deleted, a tracked file the ref
        did not know is new; an untracked file is not part of a diff
        against a commit at all."""
        out = []
        for p in sorted(set(ref_tree) | self.index):
            if paths and not any(s == "." or p == s or p.startswith(s + "/")
                                 for s in paths):
                continue
            if p in ref_tree:
                if not os.path.exists(os.path.join(self.root, p)):
                    out.append(("D", p))
                elif self._read(p) != ref_tree[p]:
                    out.append(("M", p))
            else:
                out.append(("A", p))
        return out

    def _diff_text(self, ref_tree, paths):
        import difflib
        blocks = []
        for kind, p in self._changed(ref_tree, paths):
            old = ref_tree.get(p)
            new = (self._read(p) if os.path.isfile(os.path.join(self.root, p))
                   else None)
            if kind == "A":
                blocks.append(
                    f"diff --git a/{p} b/{p}\nnew file mode 100644\n"
                    f"--- /dev/null\n+++ b/{p}\n"
                    + "".join("+" + ln + "\n"
                              for ln in (new or "").splitlines()))
            elif kind == "D":
                blocks.append(
                    f"diff --git a/{p} b/{p}\ndeleted file mode 100644\n"
                    f"--- a/{p}\n+++ /dev/null\n"
                    + "".join("-" + ln + "\n"
                              for ln in (old or "").splitlines()))
            else:
                blocks.append(
                    f"diff --git a/{p} b/{p}\n"
                    + "\n".join(difflib.unified_diff(
                        (old or "").splitlines(), (new or "").splitlines(),
                        fromfile=f"a/{p}", tofile=f"b/{p}",
                        lineterm="")))
        return "\n".join(b.rstrip("\n") for b in blocks)

    def exec(self, argv, **kw):
        """The mock installed over the factory's single git entry point:
        handles the subset of git the factory's code and the sandboxes'
        fixtures call, and returns a CompletedProcess the way
        subprocess.run would. A subcommand the model does not cover fails
        loudly (the gap is a test bug, not a silent pass)."""
        cmd = [str(a) for a in argv]
        out, err, code = "", "", 0
        sub = cmd[0] if cmd else ""
        if sub in ("init", "config", "fetch", "branch"):
            pass
        elif sub == "push":
            # recorded no-op: the production code under test may push
            # (the stage-completion push), and the sandbox's assertions
            # read what the push carried — the push's target branch and
            # the branch tip at the push moment
            refs = [a for a in cmd[1:]
                    if not a.startswith("-") and "://" not in a]
            self.pushes.append((refs[-1] if refs else None,
                                self.heads[-1] if self.heads else None))
        elif sub == "add":
            if "-A" in cmd or "--all" in cmd:
                self.index |= set(self.worktree_files())
            else:
                paths = [a for a in cmd[1:]
                         if not a.startswith("-") and a != "--"]
                for s in paths:
                    self.index |= {p for p in self.worktree_files()
                                   if p == s or p.startswith(s + "/")}
        elif sub == "commit":
            self._n += 1
            sha = format(self._n, "040x")
            self.commits[sha] = {
                p: self._read(p) for p in sorted(self.index)
                if os.path.isfile(os.path.join(self.root, p))}
            self.heads.append(sha)
        elif sub == "rev-parse":
            ref = cmd[1] if len(cmd) > 1 else ""
            sha = self._resolve(ref)
            if sha is None:
                code, err = 128, f"unknown revision {ref!r} (fake model)"
            else:
                out = sha + "\n"
        elif sub == "diff":
            args = [a for a in cmd[1:] if a != "--"]
            name_only = "--name-only" in args
            rest = [a for a in args if a != "--name-only"]
            ref = rest[0] if rest else "HEAD"
            paths = rest[1:]
            sha = self._resolve(ref)
            if sha is None:
                code, err = 128, f"unknown revision {ref!r} (fake model)"
            else:
                ch = self._changed(self.commits[sha], paths)
                if name_only:
                    out = ("\n".join(p for _, p in ch) + "\n") if ch else ""
                else:
                    out = self._diff_text(self.commits[sha], paths) \
                        if ch else ""
        elif sub == "ls-files":
            files = self.worktree_files()
            if "--others" in cmd:
                out = "\n".join(p for p in files if p not in self.index)
                if out:
                    out += "\n"
            else:
                paths = [a for a in cmd[1:]
                         if not a.startswith("-") and a != "--"]
                matched = [p for p in sorted(self.index)
                           if any(s == "." or p == s
                                   or p.startswith(s + "/")
                                  for s in paths)]
                if matched:
                    out = "\n".join(matched) + "\n"
                else:
                    # git ls-files exits 1 when the pathspec matches
                    # nothing
                    code = 1
        elif sub == "cat-file":
            ref, _, path = (cmd[2] if len(cmd) > 2 else "").partition(":")
            sha = (self._resolve(ref) if ref else
                   (self.heads[-1] if self.heads else None))
            tree = self.commits.get(sha or "", {})
            known = (path == ""
                     or any(p == path or p.startswith(path + "/")
                            for p in tree))
            code = 0 if known else 1
        elif sub == "show":
            ref, _, path = (cmd[1] if len(cmd) > 1 else "").partition(":")
            tree = self.commits.get(self._resolve(ref) or "", {})
            if path in tree:
                out = tree[path]
            else:
                code, err = 1, f"ambiguous or nonexistent object {cmd[1]!r}"
        elif sub == "checkout":
            ref = cmd[1]
            path = (cmd[cmd.index("--") + 1] if "--" in cmd else
                    (cmd[2] if len(cmd) > 2 else ""))
            tree = self.commits.get(self._resolve(ref) or "", {})
            targets = [p for p in tree
                       if p == path or p.startswith(path + "/")]
            if not targets:
                code, err = 1, f"pathspec '{path}' did not match (fake model)"
            for p in targets:
                full = os.path.join(self.root, p)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w") as f:
                    f.write(tree[p])
        elif sub == "clean":
            paths = [a for a in cmd[1:] if not a.startswith("-") and a != "--"]
            for p in self.worktree_files():
                if p in self.index:
                    continue
                if any(p == s or p.startswith(s + "/") for s in paths):
                    os.remove(os.path.join(self.root, p))
        elif sub == "rm":
            import shutil as _sh
            paths = [a for a in cmd[1:] if not a.startswith("-") and a != "--"]
            for p in sorted(self.index):
                if not any(p == s or p.startswith(s + "/") for s in paths):
                    continue
                self.index.discard(p)
                full = os.path.join(self.root, p)
                if os.path.isdir(full):
                    _sh.rmtree(full, ignore_errors=True)
                elif os.path.exists(full):
                    os.remove(full)
        elif sub == "status":
            head_tree = self.commits.get(self._resolve("HEAD") or "", {})
            lines = []
            for p in sorted(self.index):
                full = os.path.join(self.root, p)
                if not os.path.exists(full):
                    lines.append(f" D {p}")
                elif p not in head_tree or self._read(p) != head_tree[p]:
                    lines.append(("A " if p not in head_tree else " M ") + p)
            for p in self.worktree_files():
                if p not in self.index:
                    lines.append(f"?? {p}")
            out = "\n".join(lines)
            if out:
                out += "\n"
        else:
            code, err = 129, (f"the fake git model does not cover `git "
                               f"{sub}` — a test's git call bypassed the "
                               "sandbox's fake model")
        # the events file the sandbox named: one appended line per handled
        # call (the commit's new sha, the push's target branch and tip,
        # the plain subcommand otherwise) — the sandbox's fake `pi`
        # appends its own invocation line to the same file, so the test
        # reads one ordered sequence interleaving the stage's git calls
        # with its pi calls; a log-write failure is swallowed (the fake
        # stays a no-op recorder, never a source of stage failure)
        if self.events_file is not None:
            if sub == "commit" and self.heads:
                entry = "commit " + self.heads[-1]
            elif sub == "push" and self.pushes:
                entry = ("push " + str(self.pushes[-1][0])
                         + " " + str(self.pushes[-1][1]))
            else:
                entry = sub or "(no subcommand)"
            try:
                with open(self.events_file, "a", encoding="utf-8") as f:
                    f.write(entry + "\n")
            except OSError:
                pass
        return subprocess.CompletedProcess(cmd, code, out, err)


# root (realpath) → model: the sandboxes register the workspace their
# fixture builds, so a git call routed to the shared mock resolves the
# repository its cwd lives in
_FAKE_REPOS = {}


def _fake_git_exec(argv, **kw):
    """The mock installed over the factory's single git entry point.
    Routes the call to the fake model of the repository the call's cwd
    lives in; a call whose cwd carries no model is a test wiring bug — it
    fails loudly rather than silently spawning the real git binary."""
    root = os.path.realpath(kw.get("cwd") or os.getcwd())
    repo = _FAKE_REPOS.get(root)
    if repo is None:
        return subprocess.CompletedProcess(
            list(argv), 128, "",
            f"fake git: no repository model for cwd {root!r} — a git "
            "call bypassed the sandbox's fake model")
    return repo.exec(list(argv), **kw)


def _patch_git_exec():
    """Point the factory's single git entry point at the in-test fake on
    every loaded module that carries one: the shared module under
    whatever name the sandbox's import created (plus the spec-loaded
    copies), and the guard-check entry script's self-contained fallback
    copy. Returns the restore function the sandbox's cleanup calls.
    A call through an unpatched path would spawn the real git binary —
    the loud failure in _fake_git_exec is the backstop for the module-
    object paths the sandbox's own code takes."""
    patched = []
    for m in list(sys.modules.values()):
        f = (getattr(m, "__file__", "") or "").replace(os.sep, "/")
        # the shared module (under whatever name a sandbox's import created
        # or a spec load used) and the guard-check entry script — both the
        # repo's and a tree copy the sandbox lays out outside .github/
        if not (f.endswith(".github/scripts/common.py")
                or f.endswith("guard-check/guard-check.py")):
            continue
        if not hasattr(m, "git_exec"):
            continue
        patched.append((m, m.git_exec))
        m.git_exec = _fake_git_exec

    def restore():
        for m, orig in patched:
            m.git_exec = orig
    return restore


def _write_baseline_snapshot(fake, rt):
    """Mirror the model's baseline (HEAD) tree into the state dir as
    cw/baseline-tree/ — the fixture half of the fake `pi`'s revert: the
    fake restores the snapshot onto the named paths without a git child.
    The guard's repair commit runs after the revert, so the snapshot is
    the baseline's content, not the repaired tree's."""
    snap = os.path.join(rt, "cw", "baseline-tree")
    tree = fake.commits.get(fake.heads[-1] or "", {})
    for rel, content in tree.items():
        p = os.path.join(snap, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)


def test_extract_stage_uses_file_argument_context():
    """(setup-pi "pi reads the project files as context"; reference
    `requirements/setup-pi.feature::pi reads the project files as
    context`) the extract
    stage's pi call hands its context to pi as @-file arguments — the
    arc42 markdown, README.md and the baseline diff: the oracle is NOT
    expanded into those arguments (the call's instructions name the
    requirements directory instead, and pi reads the files it judges
    relevant on demand); the plumbing (common.pi_invoke
    context_as_args → stages → extract stage) exists at every layer of the
    call chain."""
    extract = _read(".github/actions/extract-stage/stage.py")
    assert "context_as_args=True" in extract
    stages = _read(".github/scripts/stages.py")
    assert "context_as_args" in stages
    common = _read(".github/scripts/common.py")
    assert "context_as_args" in common
    assert "@-file arguments" in common
    # the context the extract stage assembles: the arc42 markdown,
    # README.md and the baseline diff as the call's @-file arguments, and
    # the oracle NOT expanded into those arguments — the instructions name
    # the requirements directory instead (requirement-extraction
    # "requirements are derived from the project itself")
    assert "baseline.diff" in extract
    assert "include_oracle=False" in extract
    # the other stages keep the path-referenced slice — one invocation
    # never mixes the two
    plan = _read(".github/actions/plan-stage/stage.py")
    assert "context_as_args" not in plan
    review = _read(".github/actions/review-stage/stage.py")
    assert "context_as_args" not in review


def test_extract_prompt_names_the_oracle_directory():
    """(requirement-extraction "the extraction prompt names the oracle
    directory; pi picks the relevant files" — successor of "the context
    handed to pi is concrete files, never directories"; reference
    `requirements/requirement-extraction.feature::The extraction prompt
    names the oracle directory; pi picks the relevant files`) the
    extraction prompt's context paragraph is the directory form: the instructions
    name the requirements directory as the oracle's location and list no
    requirement file by name — pi reads the files it judges relevant from
    that directory on demand. The @-file arguments of the call (the
    non-oracle context) are all files that exist: a directory is never an
    @-argument — pi's @-argument handling reads files, so a directory
    there crashes pi with EISDIR; the shared context builder's
    extract-call form never expands the oracle into those arguments, and
    the plumbing drops any context entry that is not an existing file
    before it becomes an argument."""
    prompt = _read("pi-prompts/requirements.md")
    # the old form is gone: the oracle listed among the files handed to the
    # call — the directory form names the directory instead
    assert "the Gherkin oracle under" not in prompt
    # the directory is named as the oracle's location, and pi reads from
    # it on demand
    assert "The\nGherkin oracle is the requirements directory" in prompt
    assert "decide which of its files" in prompt
    assert "read those from the directory on demand" in prompt
    assert "a directory is never one of them" in prompt
    # the instructions list no requirement file by name — none of the
    # oracle's actual files appears in the template
    reqdir = os.path.join(ROOT, "requirements")
    for f in sorted(os.listdir(reqdir)):
        assert f"requirements/{f}" not in prompt, \
            (f"the instructions list no requirement file by name, "
             f"found {f!r} in the template")
    # the call's @-file arguments are all files that exist: the extract
    # stage assembles them through the shared context builder's
    # extract-call form (the oracle is not expanded into them — the
    # instructions name its directory instead), and every entry is a
    # file that exists — a directory is never an @-argument
    spec = importlib.util.spec_from_file_location(
        "cw_extract_stage",
        os.path.join(ROOT, ".github", "actions", "extract-stage", "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    import shutil
    saved = {k: os.environ.get(k) for k in
             ("REQUIREMENTS_DIR", "DOC_DIR", "RUNNER_TEMP")}
    rt = tempfile.mkdtemp(prefix="cw-extract-ctx-")
    os.environ["REQUIREMENTS_DIR"] = "requirements"
    os.environ["DOC_DIR"] = "docs"
    os.environ["RUNNER_TEMP"] = rt
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        ctx = mod.existing_context()
        for c in ctx:
            assert os.path.isfile(c), \
                (f"every @-file argument of the extract call is a file "
                 f"that exists — a directory is never an @-argument, "
                 f"got {c!r}")
        assert not any(c == "requirements" or c.startswith("requirements/")
                       for c in ctx), \
            (f"the oracle is not expanded into the extract call's "
             f"@-file arguments (its directory is named in the "
             f"instructions instead): {ctx!r}")
        # the non-oracle sources stay the call's @-file arguments
        assert any(c.startswith("docs/") for c in ctx), ctx
        assert "README.md" in ctx, ctx
    finally:
        os.chdir(cwd)
        shutil.rmtree(rt, ignore_errors=True)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_extract_prompt_places_delta_by_topic():
    """(requirement-extraction "extraction places the delta by topic";
    reference
    `requirements/requirement-extraction.feature::Extraction places the
    delta by topic`) the prompt's contract: a delta's scenarios extend
    the existing topic file
    that covers their topic — an edit to an existing file is the placement,
    not a violation — and a new file is created only for a topic no existing
    file covers, named after the topic, never after the issue. The stage
    accordingly no longer reverts a merely changed existing file (it reverts
    one that no longer parses, and a deleted topic file)."""
    prompt = _read("pi-prompts/requirements.md")
    assert "extend the existing topic file" in prompt
    assert "no existing file covers the topic" in prompt
    assert "create a new file named after the topic" in prompt
    stage = _read(".github/actions/extract-stage/stage.py")
    assert "no existing feature file may differ from the baseline" not in stage


def test_extract_prompt_names_files_after_topic():
    """(requirement-extraction "extraction places the delta by topic";
    reference
    `requirements/requirement-extraction.feature::Extraction places the
    delta by topic`)
    the oracle is structured by topic, not by issue: no file name in the
    prompt carries an issue number, and the validator enforces the same
    rule on the changed files (house CI runs it over the whole oracle, so
    the structure holds for the existing files too)."""
    prompt = _read("pi-prompts/requirements.md")
    assert "carries an issue number" in prompt
    validator = _read(".github/scripts/gherkin-validate.py")
    assert "named after an issue" in validator
    assert "ISSUE_NAMED_RE" in validator


def test_extract_prompt_tolerates_arc42_structure_variance():
    """(safety "the factory tolerates arc42 structure variance";
    reference
    `requirements/safety.feature::The factory tolerates arc42 structure
    variance`) the
    extraction prompt carries the structural-variance rule verbatim: it
    tolerates the structural difference, and extraction proceeds on the
    readable parts."""
    prompt = _read("pi-prompts/requirements.md")
    assert "Tolerate arc42 structure variance" in prompt
    assert "tolerates the structural difference" in prompt
    assert "proceeds on the readable parts" in prompt


def test_extract_first_run_without_requirements_dir_derives_full_requirements():
    """(requirement-extraction "A first-time run without a requirements
    dir extracts the full requirements" — new @brownfield scenario;
    reference
    `requirements/requirement-extraction.feature::A first-time run
    without a requirements dir extracts the full requirements`) a target
    without a requirements directory is a first factory run on that
    project: the extract stage's entry logic does not take the no-delta
    stop there (the stop is conditioned on the target having a
    requirements directory — the sibling scenario's adjusted Given step
    pins that other branch), runs its generation loop instead, and the
    pi prompt it builds carries the full-derivation directive — derive
    the full requirement set from the project's current code,
    documentation and tests; a source the project lacks is skipped
    rather than failing the extraction; the .feature files it writes
    create the requirements directory — while the template's
    first-run clause governs the shape of that work. The @-file slice
    stays the handed context, a directory never among its entries, its
    already-optional pieces skipped where absent (the sandbox's target
    has no baseline diff, so none rides the slice)."""
    import shutil
    spec = importlib.util.spec_from_file_location(
        "cw_extract_first_run",
        os.path.join(ROOT, ".github", "actions", "extract-stage",
                     "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ws = tempfile.mkdtemp(prefix="cw-extract-first-run-ws-")
    rt = tempfile.mkdtemp(prefix="cw-extract-first-run-rt-")
    # the target project: code, documentation and tests — but NO
    # requirements directory (a first factory run on that project)
    os.makedirs(os.path.join(ws, "src"))
    with open(os.path.join(ws, "src", "app.py"), "w") as f:
        f.write("print('a brownfield project')\n")
    os.makedirs(os.path.join(ws, "docs"))
    with open(os.path.join(ws, "docs", "01-introduction.md"), "w") as f:
        f.write("# 1. Introduction\n\nThe project.\n")
    with open(os.path.join(ws, "README.md"), "w") as f:
        f.write("# the project\n\nThe project.\n")
    os.makedirs(os.path.join(ws, "tests"))
    with open(os.path.join(ws, "tests", "test_app.py"), "w") as f:
        f.write("def test_it():\n    assert True\n")
    # the trigger's state: an empty issue body — the case the standing
    # no-delta stop was built for
    os.makedirs(os.path.join(rt, "cw"))
    with open(os.path.join(rt, "cw", "issue-body.md"), "w") as f:
        f.write("")
    keys = ("RUNNER_TEMP", "GITHUB_WORKSPACE", "REQUIREMENTS_DIR",
             "DOC_DIR")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        # the configured dir — absent in the target
        "REQUIREMENTS_DIR": "requirements",
        "DOC_DIR": "docs",
    })
    # the generation loop the stage would run, faked: it records the
    # call and materialises the prompt file the loop builds (the loop
    # calls the prompt builder every iteration)
    calls = []

    def fake_run_generation_stage(**kw):
        calls.append(kw)
        if callable(kw.get("prompt_file")):
            kw["prompt_file"]()
    orig = mod.stages.run_generation_stage
    mod.stages.run_generation_stage = fake_run_generation_stage
    hook, cwd = sys.excepthook, os.getcwd()
    os.chdir(ws)
    try:
        mod.main()
        # the stage did not take the no-delta stop — the stop is
        # conditioned on the target having a requirements directory,
        # and this target has none: the generation loop ran
        assert calls, \
            ("a first run proceeds to its generation loop instead of "
             "the no-delta stop")
        kw = calls[0]
        assert kw["template"] == "requirements"
        assert kw["allow"] == ["requirements"], \
            ("the extract guard's allow set (the requirements dir) already "
             "admits the files that create it")
        assert kw["context_as_args"] is True
        # the pi prompt it builds carries the full-derivation directive
        prompt = open(os.path.join(rt, "cw", "issue-prompt.md"),
                      encoding="utf-8").read()
        assert ("This run is a first run on a target without a "
                "requirements directory" in prompt), prompt
        assert ("derive the project's **full** requirement set from the "
                "project's current code, documentation and tests"
                in prompt), prompt
        assert ("a source the project does not have is skipped rather "
                "than failing the extraction" in prompt), prompt
        assert ("write the requirements as `.feature` files that create "
                "the requirements directory" in prompt), prompt
        # the template's first-run clause is what governs the shape of
        # the work the directive names
        template = _read("pi-prompts/requirements.md")
        assert ("A first run on a target without a requirements "
                "directory" in template)
        # the @-file slice stays the handed context: every entry is a
        # file that exists (a directory is never an @-argument), the
        # oracle is not expanded into the slice, and the already-
        # optional pieces absent in the target (its baseline diff) are
        # skipped where absent
        for c in kw["context"]:
            assert os.path.isfile(os.path.join(ws, c)), \
                (f"every @-file argument of the extract call is a file "
                 f"that exists — a directory is never an @-argument, "
                 f"got {c!r}")
            assert not c.startswith("requirements"), \
                f"the oracle is not expanded into the @-file slice: {c!r}"
        assert not any(os.path.basename(c) == "baseline.diff"
                       for c in kw["context"]), \
            (f"an already-optional piece absent in the target is "
             f"skipped where absent: {kw['context']!r}")
        assert any(c.startswith("docs/") for c in kw["context"]), \
            f"the arc42 markdown rides the handed context: {kw['context']!r}"
        # the stop's report is not what the stage wrote
        summary = os.path.join(rt, "cw", "stage-summary.txt")
        text = open(summary, encoding="utf-8").read() \
            if os.path.exists(summary) else ""
        assert "no delta requirements" not in text, text
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        mod.stages.run_generation_stage = orig
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)


def test_extract_empty_issue_body_stops_where_requirements_dir_exists():
    """(requirement-extraction "An empty issue body does not produce
    invented requirements" — adjusted; reference
    `requirements/requirement-extraction.feature::An empty issue body
    does not produce invented requirements`) the adjusted step is the
    new Given "the target project has a requirements directory": it
    narrows the stop's precondition — the empty-body no-delta stop
    applies only where the target has a requirements directory, and
    the scenario's Then outcomes are unchanged: no requirement file is
    written, and the factory reports "no delta requirements" and stops
    cleanly. No test in the suite cited the scenario before this delta,
    so the adjusted requirement is pinned by this new test, not by an
    edit to an older one."""
    import shutil
    spec = importlib.util.spec_from_file_location(
        "cw_extract_empty_body",
        os.path.join(ROOT, ".github", "actions", "extract-stage",
                     "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ws = tempfile.mkdtemp(prefix="cw-extract-empty-ws-")
    rt = tempfile.mkdtemp(prefix="cw-extract-empty-rt-")
    # the target project HAS a requirements directory (the scenario's
    # adjusted Given step) — the standing delta case
    os.makedirs(os.path.join(ws, "requirements"))
    feat = ("Feature: Guard rail\n"
            "  Scenario: A standing scenario\n"
            "    Given a\n    When b\n    Then c\n")
    with open(os.path.join(ws, "requirements", "guard-rail.feature"),
              "w") as f:
        f.write(feat)
    with open(os.path.join(ws, "README.md"), "w") as f:
        f.write("# the project\n")
    # the trigger's state: an empty issue body
    os.makedirs(os.path.join(rt, "cw"))
    with open(os.path.join(rt, "cw", "issue-body.md"), "w") as f:
        f.write("")
    keys = ("RUNNER_TEMP", "GITHUB_WORKSPACE", "REQUIREMENTS_DIR",
             "DOC_DIR")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        "REQUIREMENTS_DIR": "requirements",
        "DOC_DIR": "docs",
    })
    calls = []

    def fake_run_generation_stage(**kw):
        calls.append(kw)
    orig = mod.stages.run_generation_stage
    mod.stages.run_generation_stage = fake_run_generation_stage
    hook, cwd = sys.excepthook, os.getcwd()
    os.chdir(ws)
    try:
        mod.main()
        # the stage stops before its generation loop — the empty-body
        # stop takes the target having a requirements directory
        assert not calls, \
            ("the empty-body stop stops the stage before its generation "
             "loop")
        # it writes no requirement file: the oracle is untouched
        assert open(os.path.join(ws, "requirements",
                                 "guard-rail.feature")).read() == feat
        assert [f for f in os.listdir(os.path.join(ws, "requirements"))
                if f != "guard-rail.feature"] == [], \
            "no requirement file is written"
        # the clean stop reports "no delta requirements"
        summary = os.path.join(rt, "cw", "stage-summary.txt")
        assert "no delta requirements" in open(summary,
                                               encoding="utf-8").read()
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        mod.stages.run_generation_stage = orig
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)


def test_planner_context_falls_back_to_top_level_arc42():
    """(plan "the plan is grounded in the current architecture") the
    context builders reference the top-level PLAN.md as the arc42 set
    where the doc dir yields no arc42 files — both builders, identically
    guarded. The delta is not in the slice: the plan stage's instructions
    carry which requirement files changed and what those files changed,
    and the files themselves stay path-referenced here (plan "the
    planner is told which requirements changed and what those changes
    are"; reference
    `requirements/plan.feature::The plan is grounded in the current
    architecture`,
    `requirements/plan.feature::The planner is told which requirements
    changed and what those changes are`)."""
    stages = _read(".github/scripts/stages.py")
    marker = 'if not dir_files(doc, at_prefix=False) and os.path.isfile("PLAN.md")'
    assert stages.count(marker) == 2  # project_context + changed_requirements_context


def test_planner_instructions_carry_the_changed_requirement_delta():
    """(plan "the planner is told which requirements changed and what
    those changes are" — successor of "the planner is told where the
    changed requirements are, not handed them in full"; reference
    `requirements/plan.feature::The planner is told which requirements
    changed and what those changes are`) the plan stage's
    prompt assembly carries the delta in the instructions: it names the
    requirement file(s) that changed since the baseline and carries what
    those files changed — the baseline diff scoped to them, the delta the
    plan must cover. The call's context stays the path-referenced slice —
    the changed requirement files + the arc42 markdown + the README,
    plain paths, read on demand — and the whole existing oracle is not
    injected into the planner."""
    import shutil
    spec = importlib.util.spec_from_file_location(
        "cw_plan_stage",
        os.path.join(ROOT, ".github", "actions", "plan-stage", "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ws = tempfile.mkdtemp(prefix="cw-plan-delta-ws-")
    rt = tempfile.mkdtemp(prefix="cw-plan-delta-rt-")
    os.makedirs(os.path.join(ws, "requirements"))
    os.makedirs(os.path.join(ws, "docs"))
    # the oracle: three topic files, of which the run's extraction changes
    # only one — the rest of the oracle is not part of the delta
    with open(os.path.join(ws, "requirements", "guard-rail.feature"), "w") as f:
        f.write("Feature: Guard rail\n"
                "  Scenario: A standing scenario\n"
                "    Given a\n    When b\n    Then c\n")
    with open(os.path.join(ws, "requirements", "plan.feature"), "w") as f:
        f.write("Feature: Planning\n"
                "  Scenario: The planner is told which requirements changed\n"
                "    Given a delta\n"
                "    When the plan stage builds pi's context\n"
                "    Then the instructions name the changed files\n")
    with open(os.path.join(ws, "requirements", "safety.feature"), "w") as f:
        f.write("Feature: Safety\n"
                "  Scenario: Every loop in the pipeline respects its cap\n"
                "    Given a cap\n    When the loop runs\n    Then it stops\n")
    with open(os.path.join(ws, "docs", "01-introduction.md"), "w") as f:
        f.write("# 1. Introduction\n\nThe project.\n")
    with open(os.path.join(ws, "README.md"), "w") as f:
        f.write("# code-weaver\n\nThe factory.\n")
    # the sandbox's fake model stands in for the git binary: the factory's
    # single git entry point is mocked, so no git process is spawned
    fake = _FakeRepo(ws)
    ws_key = os.path.realpath(ws)
    _FAKE_REPOS[ws_key] = fake
    restore_git = _patch_git_exec()
    fake.exec(["init", "-q"])
    fake.exec(["add", "-A"])
    fake.exec(["commit", "-qm", "baseline"])
    base_sha = fake.exec(["rev-parse", "HEAD"]).stdout.strip()
    assert base_sha, "the sandbox's fake baseline commit failed"
    # the baseline stage's state: the baseline ref recorded for the run
    os.makedirs(os.path.join(rt, "cw"), exist_ok=True)
    with open(os.path.join(rt, "cw", "baseline.sha"), "w") as f:
        f.write(base_sha + "\n")
    # the extraction stage's committed work: one oracle file extended
    with open(os.path.join(ws, "requirements", "guard-rail.feature"), "a") as f:
        f.write("  Scenario: The changed scenario\n"
                "    Given x\n    When y\n    Then z\n")
    fake.exec(["add", "-A"])
    fake.exec(["commit", "-qm", "stage 4 requirements-extraction: generated"])
    keys = ("RUNNER_TEMP", "GITHUB_WORKSPACE", "REQUIREMENTS_DIR",
             "DOC_DIR", "PLAN_DIR")
    saved = {k: os.environ.get(k) for k in keys}
    os.environ.update({
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        "REQUIREMENTS_DIR": "requirements",
        "DOC_DIR": "docs",
        "PLAN_DIR": "plans",
    })
    cwd = os.getcwd()
    os.chdir(ws)
    try:
        # the plan stage's prompt file — the prompt pi gets alongside the
        # plan template: the delta rides the instructions
        pf = mod.build_target("42", "plans")
        prompt = open(pf, encoding="utf-8").read()
        # the instructions name the changed requirement file…
        assert "requirements/guard-rail.feature" in prompt, prompt
        # …and carry what it changed — the baseline diff scoped to it
        assert "The changed scenario" in prompt, prompt
        assert "diff --git a/requirements/guard-rail.feature" in prompt, prompt
        # the delta is scoped: the oracle's other files are neither named
        # nor carried — the whole existing oracle is not injected
        assert "plan.feature" not in prompt, prompt
        assert "safety.feature" not in prompt, prompt
        assert "Every loop in the pipeline" not in prompt, prompt
        # the call's context stays the path-referenced slice: the changed
        # requirement file + the arc42 markdown + the README, plain paths
        # (pi reads them on demand)
        ctx = mod.project_context()
        assert "requirements/guard-rail.feature" in ctx, ctx
        assert "docs/01-introduction.md" in ctx, ctx
        assert "README.md" in ctx, ctx
        assert not any(c.startswith("@") for c in ctx), ctx
        assert "requirements/plan.feature" not in ctx, ctx
        assert "requirements/safety.feature" not in ctx, ctx
        # the template's opening is the delta-carrying form — it no longer
        # just points at the changed requirements in the context
        template = _read("pi-prompts/plan.md")
        assert "Turn the **changed**\nrequirements (your context)" not in template
        assert "carries the requirement delta" in template
        assert "plan the delta your instructions carry" in template
    finally:
        os.chdir(cwd)
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        restore_git()
        _FAKE_REPOS.pop(ws_key, None)


def test_plan_prompt_clause_scopes_brownfield_tasks_to_test_references():
    """(plan "A brown field plan scopes its steps to the test references"
    — new @brownfield scenario; reference
    `requirements/plan.feature::A brown field plan scopes its steps to the
    test references`) the plan prompt template carries the brownfield
    clause: where the run's delta is the brownfield shape — every
    requirement file that changed against the baseline is *new* (the
    extraction created the requirements directory, so the baseline
    knows none of them) — the requirements were extracted from the
    project's existing code, and the plan (a) names the extracted
    scenarios it must cover and (b) scopes its steps to adjusting the
    tests to reference those scenarios, with no plan step that
    implements code; where the delta is not that shape (a changed
    existing file among the delta, as on the standing runs) the clause
    does not apply — the standing instructions are exactly as they are
    today."""
    template = _read("pi-prompts/plan.md")
    # the clause keys on the shape marker the target's prompt file writes
    assert "marks the run's delta as the **brownfield\nshape**" in template
    # the recognising rule: every changed requirement file is new against
    # the baseline, because the extraction created the requirements dir
    assert ("every requirement file that changed against the run's\n"
            "baseline is *new*") in template
    assert "the extraction created the requirements directory" in template
    assert "so the baseline knows none of them" in template
    # the scope's premise: the requirements were extracted from the
    # project's existing code
    assert ("the requirements were\n"
            "extracted from the project's existing code") in template
    # (a) the plan names the extracted scenarios it must cover
    assert ("(a) the plan names the extracted scenarios it\n"
            "must cover") in template
    # (b) the plan's steps are scoped to adjusting the tests to
    # reference those scenarios
    assert ("(b) the plan's steps are scoped to adjusting the tests\n"
            "to reference those scenarios") in template
    # no plan step implements code
    assert "no plan step implements code" in template
    # where the delta is not that shape, the clause does not apply —
    # the standing instructions govern
    assert "Where the\ndelta is not that shape" in template
    assert "this clause does not apply" in template


def test_plan_target_attaches_brownfield_scope_to_an_all_new_delta():
    """(plan "A brown field plan scopes its steps to the test references"
    — new @brownfield scenario; reference
    `requirements/plan.feature::A brown field plan scopes its steps to the
    test references`) the plan stage's prompt assembly attaches the
    brownfield scope to the instructions it generates exactly when the
    run's delta is the brownfield shape — every changed requirement
    file is new against the baseline (the extraction created the
    requirements directory, so the baseline knows none of them): the
    generated target carries the brownfield scope — the requirements
    were extracted from the project's existing code, the plan names the
    extracted scenarios it must cover, its steps are scoped to
    adjusting the tests to reference those scenarios, no plan step
    implements code — alongside the delta section. Where a changed
    existing file is among the delta (the standing runs' shape), the
    scope is not attached — the standing delta section stands alone,
    exactly as the standing test pins it (its sandbox delta changes an
    existing file and stays green unedited)."""
    import shutil
    spec = importlib.util.spec_from_file_location(
        "cw_plan_brownfield",
        os.path.join(ROOT, ".github", "actions", "plan-stage", "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ws = tempfile.mkdtemp(prefix="cw-plan-brownfield-ws-")
    rt = tempfile.mkdtemp(prefix="cw-plan-brownfield-rt-")
    # the brownfield target: code, documentation and tests — but no
    # requirements directory (the baseline knows none of its files)
    os.makedirs(os.path.join(ws, "src"))
    with open(os.path.join(ws, "src", "app.py"), "w") as f:
        f.write("print('a brownfield project')\n")
    os.makedirs(os.path.join(ws, "docs"))
    with open(os.path.join(ws, "docs", "01-introduction.md"), "w") as f:
        f.write("# 1. Introduction\n\nThe project.\n")
    with open(os.path.join(ws, "README.md"), "w") as f:
        f.write("# the project\n\nThe project.\n")
    os.makedirs(os.path.join(ws, "tests"))
    with open(os.path.join(ws, "tests", "test_app.py"), "w") as f:
        f.write("def test_it():\n    assert True\n")
    # the sandbox's fake model stands in for the git binary: the factory's
    # single git entry point is mocked, so no git process is spawned
    fake = _FakeRepo(ws)
    ws_key = os.path.realpath(ws)
    _FAKE_REPOS[ws_key] = fake
    restore_git = _patch_git_exec()
    fake.exec(["init", "-q"])
    fake.exec(["add", "-A"])
    fake.exec(["commit", "-qm", "baseline"])
    # the baseline stage's state: the baseline ref recorded for the run
    os.makedirs(os.path.join(rt, "cw"), exist_ok=True)
    with open(os.path.join(rt, "cw", "baseline.sha"), "w") as f:
        f.write(fake.exec(["rev-parse", "HEAD"]).stdout.strip() + "\n")
    keys = ("RUNNER_TEMP", "GITHUB_WORKSPACE", "REQUIREMENTS_DIR",
             "DOC_DIR", "PLAN_DIR")
    saved = {k: os.environ.get(k) for k in keys}
    os.environ.update({
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        "REQUIREMENTS_DIR": "requirements",
        "DOC_DIR": "docs",
        "PLAN_DIR": "plans",
    })
    cwd = os.getcwd()
    os.chdir(ws)
    try:
        # the extraction stage's committed work on a first run: it
        # created the requirements directory, so every changed
        # requirement file is new against the baseline (the delta is
        # the brownfield shape)
        os.makedirs(os.path.join(ws, "requirements"))
        with open(os.path.join(ws, "requirements", "overview.feature"),
                  "w") as f:
            f.write("Feature: Overview\n"
                    "  Scenario: A first extracted scenario\n"
                    "    Given a\n    When b\n    Then c\n")
        with open(os.path.join(ws, "requirements", "safety.feature"),
                  "w") as f:
            f.write("Feature: Safety\n"
                    "  Scenario: A second extracted scenario\n"
                    "    Given a\n    When b\n    Then c\n")
        fake.exec(["add", "-A"])
        fake.exec(["commit", "-qm",
                  "stage 4 requirements-extraction: generated"])
        assert mod.delta_is_brownfield() is True
        # the generated target: the brownfield scope alongside the
        # delta section
        pf = mod.build_target("42", "plans")
        prompt = open(pf, encoding="utf-8").read()
        # the delta section names every changed (new) requirement file
        assert "## The requirement delta (your task's input)" in prompt
        assert "requirements/overview.feature" in prompt, prompt
        assert "requirements/safety.feature" in prompt, prompt
        # the brownfield scope is attached — the shape marker, the
        # recognition rule it states, and the scope the new scenario
        # demands
        assert ("## The run's delta is the brownfield shape"
                in prompt), prompt
        assert ("Every requirement file that changed against the run's "
                "baseline is new" in prompt), prompt
        assert ("the requirements were extracted from the project's "
                "existing code" in prompt), prompt
        assert ("the plan names the extracted scenarios it must cover"
                in prompt), prompt
        assert ("the plan's steps are scoped to adjusting the tests to "
                "reference those scenarios" in prompt), prompt
        assert "no plan step implements code" in prompt, prompt
        # the marker keys on the template's brownfield clause — the
        # instructions handed to pi (the template plus the target)
        # govern the plan through it
        assert ("The brownfield clause of your instructions governs"
                in prompt), prompt
        assert "brownfield" in _read("pi-prompts/plan.md")
        # a standing run over the now-known oracle: the baseline knows
        # the requirements directory, and its delta changes an existing
        # file in place — not the all-new shape, so the scope is not
        # attached and the standing instructions stand
        with open(os.path.join(ws, "requirements", "overview.feature"),
                  "a") as f:
            f.write("  Scenario: A standing change\n"
                    "    Given x\n    When y\n    Then z\n")
        fake.exec(["add", "-A"])
        fake.exec(["commit", "-qm",
                  "stage 4 requirements-extraction: generated"])
        with open(os.path.join(rt, "cw", "baseline.sha"), "w") as f:
            f.write(fake.exec(["rev-parse", "HEAD~1"]).stdout.strip() + "\n")
        assert mod.delta_is_brownfield() is False
        pf2 = mod.build_target("42", "plans")
        prompt2 = open(pf2, encoding="utf-8").read()
        assert "## The requirement delta (your task's input)" in prompt2
        assert "requirements/overview.feature" in prompt2, prompt2
        assert "## The run's delta is the brownfield shape" not in prompt2
    finally:
        os.chdir(cwd)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)
        restore_git()
        _FAKE_REPOS.pop(ws_key, None)


def test_consumer_workflow_pins_owner_and_version_tag():
    """(reuse-by-ref "the factory is invoked as a reusable workflow" — both
    of its consumption shapes — and "a run triggered in the factory's own
    repo works on that repo's code") the consumer workflow consumes the
    factory one of two ways and passes issue-number + the factory settings
    via with: and GH_TOKEN via secrets:. An external target pins the
    oracle's owner, repo and path at a version tag — a moving branch ref is
    not a stable ref — and passes no factory-ref of its own: the file is
    self-contained (its stage steps inlined in it, storing no binary
    payload) and the tagged version's tree carries the runtime tree the
    file's steps execute, so the single pinned tag selects workflow file
    and runtime tree as one published version — while the factory keeps
    the factory-ref input declared as a legacy no-op, and an older
    version's consumer block that still passes it stays schema-valid.
    The ref is a single increasing number, the current scheme's tag shape
    (the retired semver ref shape is gone — reuse-by-ref "every published
    version is a stable ref"). This repo is the factory project itself,
    and its workflow takes the external shape too: it pins the public
    release line (a version tag of the MelvinKl line), so the dogfood
    exercises exactly the published version the external targets get —
    the code a run in it works is still the triggered repo's own. The
    test accepts either shape and asserts the contract of the shape the
    file uses — in both, the with: block passes no factory-ref of its
    own (one ref selects the whole version), while the factory keeps the
    input declared as a legacy no-op. The expected outcome extends to
    the run's pi harness providers (configuration "The pi harness secrets
    ride the reusable workflow's secrets block"): the same three surfaces —
    the factory's secrets: block, the deployed consumer workflow, the README
    example — carry the four provider secret entries in the same form, while
    the uses: shape stays within its pattern (the README's example is
    documentation, not a pinned surface: the suite does not compare its ref
    against the deployed workflow, so a release ref bump on one surface
    never fails the suite until the other is synced; reference
    `requirements/reuse-by-ref.feature::The factory is invoked as a
    reusable workflow`,
    `requirements/reuse-by-ref.feature::A run triggered in the factory's
    own repo works on that repo's code`,
    `requirements/configuration.feature::The pi harness secrets ride the
    reusable workflow's secrets block`,
    `requirements/reuse-by-ref.feature::Every published version is a
    stable ref`)."""
    text = _read(".github/workflows/code-weaver.yml")
    assert "with:" in text and "GH_TOKEN" in text and "secrets:" in text
    m = re.search(r"uses:\s*([\w.-]+)/code-weaver/(\S+?)@([\w.-]+)", text)
    if m:
        # the pinned pattern: owner + path + a version tag — and no
        # factory-ref relayed beside it (the single-pin contract)
        owner, path, ref = m.groups()
        assert owner == "MelvinKl", f"oracle pins the MelvinKl owner, found {owner}"
        assert path.rstrip() == ".github/workflows/factory.yml"
        assert re.fullmatch(r"\d+", ref), (
            f"@{ref} is not a single increasing version number — the "
            "current scheme's tag shape (the retired semver ref shape is gone)")
        assert not re.search(r"factory-ref:\s*\S+", text), (
            "the single-pin pattern passes no factory-ref — one ref selects "
            "the whole version, because the file is self-contained; the "
            "input stays declared in the factory as a legacy no-op, so an "
            "older version's consumer block that still passes it remains "
            "schema-valid")
        factory = _read(".github/workflows/factory.yml")
        assert re.search(r"^\s*factory-ref:", factory, re.M), (
            "the (legacy) factory-ref input stays declared in the factory's "
            "inputs: block — schema compatibility for the with: blocks of "
            "older published versions")
    else:
        # the alternative shape: the consumer calls the factory's own
        # copy by relative uses: (the runner reads the file from the
        # triggering commit) and leaves the factory-ref input empty —
        # the stages run the tree the first job fetches from the
        # triggering repo at the run's base ref
        mrel = re.search(r"uses:\s*\.?/?\.github/workflows/factory\.yml\b", text)
        assert mrel, "no uses: line naming the factory"
        assert not re.search(r"factory-ref:\s*\S+", text), (
            "the dogfood pattern leaves the factory-ref input empty — the "
            "stage jobs run the repo's own runtime tree, never a clone of "
            "the factory repo at a pinned ref")
    readme = _read("README.md")
    # the extension: all three consumer surfaces carry the four harness
    # provider secret entries in the same form — the factory declares them
    # in its workflow_call secrets: block, the deployed workflow and the
    # README example wire them in their own secrets: blocks
    factory = _read(".github/workflows/factory.yml")
    for name in ("PI_MODELS", "PI_SETTINGS", "PI_MCP", "PI_EXTENSION_ENV"):
        assert f"      {name}:" in factory, \
            f"the factory's secrets: block must declare {name} as an optional entry"
        line = f"      {name}: ${{{{ secrets.{name} }}}}"
        assert line in text, \
            f"the deployed consumer workflow must wire {name} in its secrets: block"
        assert line in readme, \
            f"the README example must wire {name} in its secrets: block — same form as the deployed workflow"


def test_factory_upload_steps_opt_into_hidden_files():
    """(the runtime tree the stage jobs execute — reuse-by-ref "a run is
    the factory working the tree of the ref it ran"; reference
    `requirements/reuse-by-ref.feature::The stage jobs materialise the
    runtime tree before their first checkout`) every stage job gets
    the runtime tree from the trigger job's artifact, and the tree lives
    under cw/stash/.github/ — inside a HIDDEN directory. The
    actions/upload-artifact action excludes hidden files by default: a
    step that uploads the run's state dir without
    `include-hidden-files: true` silently drops the .github part of the
    tree, and every stage job that downloads that artifact arrives with
    its stashed stage script missing (run 41126074467 failed exactly this
    way at stage 2, after the single-pin change put the tree in the
    artifact instead of re-cloning it in each stage job)."""
    lines = _read(".github/workflows/factory.yml").splitlines()
    steps, cur = [], None
    for ln in lines:
        if re.match(r"^ {6}- \S", ln) or re.match(r"^  \S", ln):
            if cur is not None:
                steps.append(cur)
            cur = [ln]
        elif cur is not None:
            cur.append(ln)
    if cur is not None:
        steps.append(cur)
    uploads = [s for s in steps if "actions/upload-artifact" in s[0]]
    assert uploads, "no upload-artifact steps found in the factory"
    for s in uploads:
        name = re.search(r"name:\s*(\S+)", "\n".join(s))
        assert name and "include-hidden-files: true" in "\n".join(s), (
            f"the {name.group(1) if name else 'unnamed'} upload step does "
            "not opt into hidden files — the stashed tree under "
            "cw/stash/.github/ would be dropped from its artifact and "
            "every stage job would lose its stashed stage scripts")


def test_factory_workflow_is_self_contained():
    """(reuse-by-ref "the factory workflow is self-contained"; the
    successor of "the factory's workflow names its own actions by owner,
    repo and path" and the in-file half of "a published version is
    self-consistent"; reference
    `requirements/reuse-by-ref.feature::The factory workflow is
    self-contained`) no `uses:` reference to the factory's own actions
    remains — an own-action ref would have to be fully qualified
    (MelvinKl/code-weaver/.github/actions/<name>@<ref>) and pinned to a
    ref the release flow could only make consistent by rewriting a
    workflow file before the tag (a push that updates a workflow file —
    the github-actions App behind the publishing token is refused it,
    `workflows` not being a permission available to it), and a relative
    path would resolve against the calling repo's checkout, where a
    target holds no copy of the factory's scripts. The stage steps are
    inlined instead: the file stores no binary content — the runtime tree
    its steps execute is not embedded in it — and every stage job carries
    the former action's steps at its former splice site, runs their
    scripts from the called version's runtime tree stashed into
    $RUNNER_TEMP (stage 1 fetches it at the called ref; every later
    job's first step restores it from the trigger's artifact before its
    checkout), and no stage job is without that stash step."""
    text = _read(".github/workflows/factory.yml")
    own_refs = [ln.strip() for ln in text.splitlines()
                if re.search(r"\buses:\s*MelvinKl/code-weaver/\.github/actions/",
                             ln)]
    assert not own_refs, (
        f"factory.yml still references its own actions {own_refs!r} — the "
        "stage steps are inlined in the workflow; an own-action ref would "
        "need a pre-tag rewrite the release flow must never push")
    stashes = len(re.findall(r"Stash the factory runtime tree", text))
    job_keys = ("trigger", "setup-pi", "baseline", "extract", "plan",
                "implement", "review", "pr", "gates", "report")
    jobs = sum(1 for k in job_keys if re.search(rf"(?m)^  {k}:\s*$", text))
    assert stashes == jobs == len(job_keys), (
        f"{stashes} stash steps for {jobs} stage jobs — every stage job's "
        "first step must stash the called repo's runtime tree before its "
        "first checkout")
    for name in ("setup-pi", "baseline", "extract-stage", "plan-stage",
                 "implement-stage", "review-stage", "pi-run", "pr-open",
                 "gates-stage", "report"):
        contig = f"cw/stash/.github/actions/{name}"
        split = f'".github", "actions", "{name}"'
        assert contig in text or split in text, (
            f"the {name} stage does not run its script from the stashed "
            "runtime tree")


def test_review_stage_judges_only_changed_feature_files():
    """(test-and-review "Gherkin scenarios run as executable acceptance
    tests" / "each requirement is checked for fulfilment" — delta scope;
    reference
    `requirements/test-and-review.feature::Gherkin scenarios run as
    executable acceptance tests`,
    `requirements/test-and-review.feature::Each requirement is checked
    for fulfilment`,
    `requirements/test-and-review.feature::A test change is judged by
    the requirement it references`)
    the review's pi context lists the feature files changed against the
    run's baseline, never the whole requirements dir (re-judging the
    accumulated oracle on every run is the unbounded work the review must
    not do); the bounded scope extends to the run's changed test files —
    path-referenced into the review call — and the scenarios their
    docstrings reference, which join the verdict scope; and a run that
    changed no requirements and whose changed tests reference no
    scenario passes vacuously (the empty verdict block is the answer,
    not an unparseable failure)."""
    review = _read(".github/actions/review-stage/stage.py")
    # the context is delta-scoped through the shared changed-requirements
    # builder — and the old whole-dir slice is gone
    assert "changed_requirement_files()" in review
    assert "stages.dir_files(req, at_prefix=False)" not in review
    # the prompt names the changed files when there are any
    assert "feature files this run changed" in review
    # the extended scope: the run's changed test files ride the review
    # call's path-referenced context, and the scenarios their docstrings
    # reference are extracted into the verdict scope
    assert "changed_test_files()" in review
    assert "referenced_scenarios(" in review
    assert "the scenarios the changed tests reference" in review
    # a delta-free run — no changed requirements and no referencing
    # changed test — is a vacuous pass, not a zero-verdict failure
    assert "not delta_feature_files()" in review
    assert "no changed requirements" in review
    # and the oracle's prompt agrees on the scope — the changed feature
    # files' scenarios plus the scenarios the changed tests reference
    prompt = _read("pi-prompts/review.md")
    assert "the scenarios the changed tests reference" in prompt
    assert "Do NOT re-judge scenarios beyond that scope" in prompt


def test_review_judges_a_test_change_by_its_referenced_requirement():
    """(test-and-review "A test change is judged by the requirement it
    references" — the new @review scenario; reference
    `requirements/test-and-review.feature::A test change is judged by
    the requirement it references`) a run whose work changes a test:
    a test that is only for correctness may be changed freely — it
    references nothing, so no verdict is owed on its account and it is
    not a problem on its own; a test that references a requirement is
    judged against that requirement — the changed test's scenario
    reference (the docstring form the implement stage prescribes) is
    extracted into the review's verdict scope, must leave the referenced
    scenario fulfilled after the change, and a test change that leaves
    it unfulfilled is a fix-loop problem like any other unfulfilled
    scenario."""
    spec = importlib.util.spec_from_file_location(
        "cw_review_stage_sandbox",
        os.path.join(ROOT, ".github", "actions", "review-stage",
                     "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # a changed test that references a requirement puts the referenced
    # scenario into the verdict scope — the citation is read from the
    # test's docstrings; a correctness-only test contributes nothing,
    # a path mentioned in prose is not a citation, and a test file that
    # does not parse contributes no references
    import shutil
    ws = tempfile.mkdtemp(prefix="cw-review-ws-")
    saved = {k: os.environ.get(k) for k in ("GITHUB_WORKSPACE",)}
    os.environ["GITHUB_WORKSPACE"] = ws
    try:
        os.makedirs(os.path.join(ws, "tests"))
        with open(os.path.join(ws, "tests", "test_ref.py"), "w") as f:
            f.write(
                '"""The module docstring names no scenario."""\n'
                "def test_referencing():\n"
                "    '''A test that implements a Gherkin scenario cites it\n"
                "    in the machine form.\n"
                "    `requirements/guard-rail.feature::Guard repairs are capped`\n"
                "    '''\n"
                "    assert True\n"
                "def test_correctness_only():\n"
                "    '''A correctness-only check — no Gherkin scenario behind\n"
                "    it; `requirements/safety.feature` is mentioned in prose,\n"
                "    without a citation.\n"
                "    '''\n"
                "    assert True\n"
                "def test_quoting_without_citing():\n"
                "    '''Quotes a scenario name in prose (\"Guard repairs are\n"
                "    capped\") but carries no machine citation — prose is not\n"
                "    a reference.\n"
                "    '''\n"
                "    assert True\n")
        with open(os.path.join(ws, "tests", "test_broken.py"), "w") as f:
            f.write("def test_unparsed(:\n    pass\n")
        refs = mod.referenced_scenarios(["tests/test_ref.py",
                                         "tests/test_broken.py"])
        assert refs == [("guard-rail.feature", "Guard repairs are capped")], (
            "the changed tests' scenario references are extracted from "
            f"their docstrings: {refs!r}")
        # the review prompt carries the judgement rule both ways — a
        # correctness-only test may be changed freely, a referencing test
        # must leave the referenced scenario fulfilled — and the fix loop
        # consumes a test-referenced UNFULFILLED verdict like any other
        # unfulfilled scenario of the run's delta
        prompt = _read("pi-prompts/review.md")
        assert ("A changed test is judged by the requirement it references"
                in prompt)
        assert "only for correctness references no scenario" in prompt
        assert "may be changed freely" in prompt
        assert "must leave that scenario fulfilled after the change" in prompt
        review = _read(".github/actions/review-stage/stage.py")
        assert "The following Gherkin scenarios are UNFULFILLED" in review, \
            "a test change that leaves its referenced scenario unfulfilled is a fix-loop problem"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)


def test_reviewers_report_is_fed_into_the_fixer():
    """(test-and-review "The reviewer's report is fed into the fixer",
    "The review judges every iteration, red or green"; reference
    `requirements/test-and-review.feature::The reviewer's report is fed
    into the fixer`,
    `requirements/test-and-review.feature::The review judges every
    iteration, red or green`)
    the fix directive the stage-11 fixer receives is built from the
    reviewer's report, not a lossy reduction of it: the review runs on
    every iteration's suite output — red or green (a red suite is never
    a pass, so the review's own breakdown cannot hide one; the old form
    skipped the review call on a red iteration) — and its full captured
    output (the verdict block with each line's evidence, the
    UNFULFILLED lines' "what's missing / what the fix must do", the
    note on what the tests don't cover) is mirrored per iteration into
    the state dir; the directive names the report by path — the fixer
    reads it on demand, the no-injection idiom the review call itself
    uses for the test output — and the report joins the fix call's
    path-referenced context; the machine-parsed verdict summary and,
    for a red suite, the raw output tail ride alongside. A red
    iteration whose review breaks keeps the fix loop running on the raw
    output, while the same breakdown on a green suite fails the stage
    (the oracle cannot be assumed green)."""
    review = _read(".github/actions/review-stage/stage.py")
    # the review is no longer conditional on a green suite — every
    # iteration's output is reviewed, red or green
    assert "res, rrc = review(i, out)" in review
    assert "if rc == 0 else" not in review
    # the report is mirrored per iteration into the state dir (→ artifact)
    assert "review-report-" in review
    # the directive names the report by path — the fixer reads it on demand
    assert "(read it)" in review
    # the report joins the fix call's path-referenced context
    assert "report_f" in review
    # the breakdown asymmetry: a green suite with a broken review fails the
    # stage; a red suite never passes, so its broken review keeps the fix
    # loop running on the raw output
    assert "stage fails" in review
    assert "runs on the raw test output" in review
    # the review prompt tells the model its output is what the fixer reads
    prompt = _read("pi-prompts/review.md")
    assert "reads your full output" in prompt


def test_pr_body_generated_by_pi():
    """(pr-and-gates "a pull request is opened against the target
    branch"; reference
    `requirements/pr-and-gates.feature::A pull request is opened
    against the target branch`)
    stage 12 generates the PR body with pi from the requirements, the plan
    and the review — the template assembler is the fallback, and the body
    still references the source issue."""
    factory = _read(".github/workflows/factory.yml")
    assert "Generate the PR body with pi" in factory
    assert "pr-body" in factory
    prompt = _read("pi-prompts/pr-body.md")
    assert "the requirements" in prompt and "the plan" in prompt and "the review" in prompt
    assert "Reference the source issue" in prompt
    # the body describes the issue it implements — and keeps the
    # configuration out of the description (workflow-log material)
    assert "describes the issue" in prompt
    assert "resolved configuration" in prompt


def _pr_fallback_source() -> str:
    """The pr job's template-fallback step, reduced to its runnable python.
    The step's `run: |` block is a bash step that launches python over a
    `<<'EOF'` heredoc; this extracts the heredoc body (from the line that
    opens it to the closing `EOF`) and dedents it to a source string, so
    the same sandbox-exec idiom the report action's step uses applies."""
    lines = _read(".github/workflows/factory.yml").splitlines()
    start = None
    for i, ln in enumerate(lines):
        if "Assemble the PR body" in ln and "template fallback" in ln:
            start = i
            break
    assert start is not None, "the pr job's fallback step is gone"
    # the heredoc is located by its markers, not its indent: the step's
    # body now runs inside the run's console-mirror subshell (issue #106
    # made the step mirror its full output into the run's artefact state
    # dir), so the heredoc sits 4 deeper than the run block's dedent base
    her_start = None
    for j in range(start + 1, len(lines)):
        l = lines[j]
        if l.strip() and (len(l) - len(l.lstrip(" "))) < 6:
            break  # left the step's block without finding the heredoc
        if "<<" in l and "EOF" in l:
            her_start = j
            break
        if l.strip() == "EOF" and "<<" not in l:
            break  # a heredoc closed before its opener — shape changed
    assert her_start is not None, \
        "the fallback step no longer runs python via a heredoc"
    her_end = next((k for k in range(her_start + 1, len(lines))
                    if lines[k].strip() == "EOF"), None)
    assert her_end is not None, "the fallback heredoc never closes"
    body = lines[her_start + 1:her_end]
    indents = [len(l) - len(l.lstrip(" ")) for l in body if l.strip()]
    base = min(indents) if indents else 0
    return "\n".join(l[base:] if l.strip() else "" for l in body)


def test_pr_body_fallback_describes_the_issue():
    """(pr-and-gates "the PR body describes the issue it implements";
    reference
    `requirements/pr-and-gates.feature::The PR body describes the issue
    it implements`) the
    template fallback — used when the pi call produced no body —
    describes the issue: it names the source issue's number and title
    from the trigger's state files (a job-env relay that dropped
    CW_ISSUE / CW_TITLE must not yield a body that reads 'issue: # —'),
    embeds the issue's plan, lists the requirement scenarios the run
    changed against the baseline (and only those), and carries no
    resolved-configuration dump."""
    import shutil
    import tempfile
    src = _pr_fallback_source()
    ws = tempfile.mkdtemp(prefix="cw-pr-ws-")
    rt = tempfile.mkdtemp(prefix="cw-pr-rt-")
    # the step's diff block runs only where the workspace is a git
    # checkout: the marker dir makes the sandbox carry that shape (the
    # fake model needs no .git of its own)
    os.makedirs(os.path.join(ws, ".git"), exist_ok=True)
    trig = os.path.join(rt, "cw", "state", "trigger")
    os.makedirs(trig)
    os.makedirs(os.path.join(ws, "requirements"))
    with open(os.path.join(ws, "requirements", "topic.feature"), "w") as f:
        f.write("Feature: Topic\n"
                "  Scenario: A standing scenario\n"
                "    Given a\n    When b\n    Then c\n")
    # the sandbox's fake model stands in for the git binary: the step's
    # own single git entry point is injected with it (a test never spawns
    # the real git binary)
    fake = _FakeRepo(ws)
    ws_key = os.path.realpath(ws)
    _FAKE_REPOS[ws_key] = fake
    restore_git = _patch_git_exec()
    fake.exec(["init", "-q"])
    fake.exec(["add", "-A"])
    fake.exec(["commit", "-qm", "baseline"])
    base_sha = fake.exec(["rev-parse", "HEAD"]).stdout.strip()
    # the run's delta: the issue's plan + a new scenario in the topic file
    os.makedirs(os.path.join(ws, "plans"))
    with open(os.path.join(ws, "plans", "42.md"), "w") as f:
        f.write("# Issue #42 — the test plan\n\n**Steps**\n\n- [x] build the thing\n")
    with open(os.path.join(ws, "requirements", "topic.feature"), "a") as f:
        f.write("  Scenario: The changed scenario\n"
                "    Given x\n    When y\n    Then z\n")
    fake.exec(["add", "-A"])
    fake.exec(["commit", "-qm", "delta"])
    with open(os.path.join(trig, "issue-number.txt"), "w") as f:
        f.write("42\n")
    with open(os.path.join(trig, "issue-title.txt"), "w") as f:
        f.write("The test issue\n")
    with open(os.path.join(trig, "base-sha.txt"), "w") as f:
        f.write(base_sha + "\n")
    out = os.path.join(rt, "cw", "pr-body.md")
    keys = ("PATH", "RUNNER_TEMP", "GITHUB_WORKSPACE", "CW_ISSUE",
            "CW_TITLE", "CW_TARGET", "CW_MODEL", "CW_RUNNER",
            "REQUIREMENTS_DIR", "PLAN_DIR")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        # the job-env relay drops the trigger's values on this runner
        # build — the fallback reads them from the state files instead
        "CW_ISSUE": "",
        "CW_TITLE": "",
        "CW_TARGET": "main",
        "REQUIREMENTS_DIR": "requirements",
        "PLAN_DIR": "plans",
    })
    argv_saved, hook = sys.argv, sys.excepthook
    sys.argv = ["python3", out]
    try:
        exec(compile(src, "<factory.yml pr fallback step>", "exec"),
             {"__name__": "cw_pr_fallback_test",
              "git_exec": _fake_git_exec})
        body = open(out, encoding="utf-8").read()
    finally:
        sys.argv, sys.excepthook = argv_saved, hook
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)
        restore_git()
        _FAKE_REPOS.pop(ws_key, None)
    # names the issue from the trigger's state files (the env was empty)
    assert "#42" in body and "The test issue" in body, body
    # embeds the plan — what the run set out to build
    assert "## The plan for this issue" in body
    assert "build the thing" in body, body
    # lists the scenarios the run changed against the baseline, and only
    # those (the standing scenario is not part of the delta)
    assert "The changed scenario" in body, body
    assert "A standing scenario" not in body, body
    # carries no resolved-configuration dump
    assert "## Resolved configuration" not in body, body
    # stage 15 still owns the completion
    assert "Stage 15" in body


def test_report_falls_back_to_top_level_arc42():
    """(reporting "the arc42 documents the AI activity"; safety "an audit
    trail exists for human review"; reference
    `requirements/reporting.feature::The arc42 documents the AI
    activity`,
    `requirements/safety.feature::An audit trail exists for human
    review`) the report stage appends the
    AI-activity section to the arc42 markdown under the doc dir — and
    falls back to the top-level PLAN.md where a target has no doc dir."""
    # the arc42-activity logic lives in the runtime tree's stage script
    # (issue #106's giant-body collapse moved it out of the workflow);
    # the workflow's step only launches the stashed copy
    action = _read(".github/actions/report/stage.py")
    assert '## AI activity (code-weaver)' in action
    assert 'elif os.path.isfile("PLAN.md")' in action
    docs = os.path.join(ROOT, "docs")
    assert os.path.isdir(docs), "the repo's arc42 set lives under docs/ (one chapter per file)"
    ch1 = os.path.join(docs, "01-introduction.md")
    assert os.path.isfile(ch1)
    assert "## AI activity (code-weaver)" in open(ch1, encoding="utf-8").read()


def _report_action_source() -> str:
    """The report stage's status-report python, read from the runtime
    tree's stage script and reduced to its runnable body. The stage's
    body used to inline in the workflow (the former action file is
    gone); issue #106's giant-body collapse moved it into the tree, and
    the workflow's step only launches the stashed script — so the source
    is the tree file, and the tests exec its body against a sandboxed
    state dir: the assembled report is a function of the state dir's
    contents (the per-call usage ledger, the trigger's resolved
    configuration) and the step's env, so no live workflow is needed.
    The body keeps the RUNNER_TEMP-relative stash resolution (not a
    `__file__` one), so the exec's sandboxed RUNNER_TEMP stands in for
    the run's."""
    # The status-report body no longer inlines in the workflow: issue
    # #106's giant-body collapse moved it into the runtime tree's stage
    # script (the workflow's step only launches it from the job's
    # stash), so the source is read from the tree file the launcher
    # runs — the same file the stash carries, and the same file the
    # step's python executes.
    src = _read(".github/actions/report/stage.py")
    m = re.search(r"^try:", src, re.M)
    assert m is not None, \
        "the stage script is no longer the status-report python"
    return src[m.start():]


def _models_config(r_in: float, r_out: float) -> str:
    """A minimal pi models.json (the shape the setup stage parses) with one
    provider: Ornith priced at the given USD-per-1M rates, and a second
    model with no `cost` entry — the unpriced case the report lists when
    the configuration carries the model but not its rates."""
    return ('{\n'
            '  "providers": {\n'
            '    "test": {\n'
            '      "baseUrl": "http://example.invalid/v1",\n'
            '      "api": "openai-completions",\n'
            '      "models": [\n'
            '        {"id": "Ornith-1.5-35B-A3B",\n'
            f'         "cost": {{"input": {r_in}, "output": {r_out},\n'
            '                  "cacheRead": 0.05, "cacheWrite": 0}},\n'
            '        {"id": "Some-Other-Runner-Model",\n'
            '         "contextWindow": 8192}\n'
            '      ]\n'
            '    }\n'
            '  }\n'
            '}\n')


def _run_report_action(run_result="success", pr_number="7", issue_number="42",
                       ledger=None, model="Ornith-1.5-35B-A3B",
                       view_body="## Progress so far",
                       shared_module="fallback",
                       models_config=None, pi_models_env=None,
                       stage_summary=None):
    """Exec the report action's inline python in a sandbox: a plain temp
    workspace (no git repo, no doc dir, no PLAN.md — the arc42-activity
    path has nothing to touch), a temp RUNNER_TEMP carrying the merged
    stage state (the per-call usage ledger the report job's artifact
    downloads leave behind, plus the trigger's resolved configuration),
    and a fake `gh` on PATH that serves the PR view and captures the issue
    comment body it is posted with — no network. The PR view the fake
    serves is `view_body` for EVERY read (before and after the edit):
    '## Progress so far' simulates a PR whose body never took the
    completion (already merged / edit refused), a body carrying the
    '## Final status' marker simulates a verified completion. Returns
    (the final PR body, the issue comment, whether the source issue was
    closed).

    `shared_module` parameterises the step's `import common` resolution:
    the default "fallback" is the forced-fallback setup every standing
    test in this file relies on — the scripts dir scrubbed from sys.path
    and the `common` module popped from sys.modules, so the import fails
    and the body runs on the step's local fallback definitions (the path
    this runner build takes in production); "import" instead stashes a
    copy of the repo's .github tree into the sandbox's
    $RUNNER_TEMP/cw/stash — the tree the report job's first step stashes
    before its first checkout — so the step's own scripts-dir insertion
    resolves the shared module from the stashed tree and the shared
    module's definitions bind the body's five plumbing names (the import
    path task 1's test pins). The `common` module is popped from
    sys.modules either way: a module another test module cached would
    satisfy the import in place of the tree. `stage_summary` overrides the
    stage-summary fixture the sandbox writes (the merged summary lines the
    report stage renders its stage-outcome table from); the default is the
    standing one-line form (the extract stage's completion line)."""
    import shutil
    import tempfile
    ws = tempfile.mkdtemp(prefix="cw-report-ws-")
    rt = tempfile.mkdtemp(prefix="cw-report-rt-")
    cw = os.path.join(rt, "cw")
    os.makedirs(cw)
    if ledger is not None:
        with open(os.path.join(cw, "tokens.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(ledger) + "\n")
    with open(os.path.join(cw, "resolved-config.txt"), "w", encoding="utf-8") as f:
        f.write("### Code Weaver — resolved configuration "
                "(workflow log; never committed)\n"
                f"- issue: #{issue_number}\n"
                f"- LLM model (which configured model): `{model}`\n"
                f"- caps: max-loops=`5` (0 = no cap)\n")
    with open(os.path.join(cw, "stage-summary.txt"), "w", encoding="utf-8") as f:
        f.write(stage_summary if stage_summary is not None
                else "stage 4 extract: clean — stage complete\n")
    if models_config is not None:
        # the run's model configuration as the repo-file provider — the
        # .pi/agent/models.json the report job resolves in the workspace
        # (the provider the setup stage falls back to when the secret is
        # absent)
        agent = os.path.join(ws, ".pi", "agent")
        os.makedirs(agent)
        with open(os.path.join(agent, "models.json"), "w", encoding="utf-8") as f:
            f.write(models_config)
    fake = tempfile.mkdtemp(prefix="cw-report-fake-")
    binp = os.path.join(fake, "bin")
    os.makedirs(binp)
    comment_f = os.path.join(fake, "issue-comment.txt")
    view_json = json.dumps(
        {"body": view_body,
         "head": {"sha": "f" * 40, "ref": "ai/code-weaver/7"},
         "html_url": "https://gh.example/pr/7"})
    with open(os.path.join(binp, "gh"), "w", encoding="utf-8") as f:
        f.write("#!%s\n" % sys.executable +
                "import json, os, sys\n"
                "args = sys.argv[1:]\n"
                "body = ''\n"
                "for a in args:\n"
                "    if a.startswith('body='):\n"
                "        body = a[len('body='): ]\n"
                "if args[:1] == ['api'] and any('pulls/' in a for a in args):\n"
                f"    print({view_json!r})\n"
                "    sys.exit(0)\n"
                "if args[:1] == ['api'] and 'state=closed' in args:\n"
                "    open(os.environ['FAKE_GH_OUT'] + '.closed', 'w')"
                ".write('closed')\n"
                "if body:\n"
                "    open(os.environ['FAKE_GH_OUT'], 'w').write(body)\n"
                "if args[:2] == ['pr', 'edit'] and '--body-file' in args:\n"
                "    bf = args[args.index('--body-file') + 1]\n"
                "    open(os.environ['FAKE_GH_OUT'] + '.pr-body', 'w')"
                ".write(open(bf).read())\n")
    os.chmod(os.path.join(binp, "gh"), 0o755)
    keys = ("PATH", "RUNNER_TEMP", "GITHUB_WORKSPACE", "GITHUB_REPOSITORY",
            "GH_TOKEN", "GITHUB_ACTION_PATH", "AI_BRANCH", "DOC_DIR",
            "CW_RUN_RESULT", "CW_PR_NUMBER", "CW_ISSUE_NUMBER",
            "CW_PI_MODELS", "INPUT_PI_MODELS", "FAKE_GH_OUT")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "PATH": binp + os.pathsep + (saved["PATH"] or ""),
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        "GITHUB_REPOSITORY": "code-weaver/test-target",
        "GH_TOKEN": "fake-token",
        "GITHUB_ACTION_PATH": "",
        "FAKE_GH_OUT": comment_f,
        "CW_RUN_RESULT": run_result,
        "CW_ISSUE_NUMBER": issue_number,
        "CW_PR_NUMBER": pr_number,
        # the run's model configuration provider relay — set when the test
        # names pi_models_env (the secret wins over the repo file), empty
        # otherwise (an empty provider value is an absent provider)
        "CW_PI_MODELS": pi_models_env or "",
    })
    hook, cwd = sys.excepthook, os.getcwd()
    os.chdir(ws)
    # a `common` module another test module cached in this process is
    # popped first (restored in the finally): it would satisfy the step's
    # import in place of the tree and the resolution under test would not
    # be the one that ran.
    common_mod = sys.modules.pop("common", None)
    path_saved = list(sys.path)
    if shared_module == "fallback":
        # the forced-fallback setup every standing test in the file relies
        # on: the action's `import common` must fail here, as it does on
        # this runner build (the action dir's `/./` segment breaks the
        # scripts path resolution): the action then runs on its local
        # fallback definitions — the path production takes. Otherwise the
        # scripts dir already on sys.path would satisfy the import and the
        # fallback definitions would never land.
        scripts_dir = os.path.realpath(
            os.path.join(ROOT, ".github", "scripts"))
        sys.path[:] = [p for p in sys.path
                       if p and os.path.realpath(p) != scripts_dir]
    else:
        # the import path: the report job's first step stashed the runtime
        # tree to $RUNNER_TEMP/cw/stash before its first checkout — the
        # copy below is that same tree, so the step's own scripts-dir
        # insertion puts a resolvable scripts dir at the front of sys.path
        # and the shared module resolves from the stashed tree
        shutil.copytree(os.path.join(ROOT, ".github"),
                        os.path.join(cw, "stash", ".github"))
    out = {"pr_body": "", "comment": ""}
    try:
        try:
            exec(compile(_report_action_source(),
                          "<report action.yml run block>", "exec"),
                 {"__name__": "cw_report_action_test"})
        except SystemExit:
            pass
        pf = os.path.join(cw, "final-pr-body.md")
        if os.path.isfile(pf):
            out["pr_body"] = open(pf, encoding="utf-8").read()
        if os.path.isfile(comment_f):
            out["comment"] = open(comment_f, encoding="utf-8").read()
        out["closed"] = os.path.isfile(comment_f + ".closed")
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        sys.path[:] = path_saved
        if common_mod is not None:
            sys.modules["common"] = common_mod
        else:
            # the import path ran: drop the module it loaded from the
            # stash (the temp tree is removed below) so no later test
            # picks it up
            sys.modules.pop("common", None)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)
        shutil.rmtree(fake, ignore_errors=True)
    return out["pr_body"], out["comment"], out["closed"]


def test_report_step_plumbing_is_bound_on_the_import_path():
    """(reporting "The report step's plumbing is bound on a runner where the
    shared module imports" — new scenario; reference
    `requirements/reporting.feature::The report step's plumbing is bound
    on a runner where the shared module imports`) on a runner where the
    shared module resolves from the runtime tree the report job stashed to
    $RUNNER_TEMP before its first checkout, the step's `import common`
    succeeds, and its five plumbing names — the state dir, the state file,
    the log, the gh api, the branch push — are bound for the step's body to
    the shared module's definitions: the body's bare-name calls resolve on
    that path, the step does not die with an undefined-name error before
    any of its report work has run (the crash wrapper's stage-fail-reason
    diagnosis is not produced), and the report completes (the final PR body
    carries the final status, the issue comment is posted, a successful run
    closes the source issue). The sandbox mirrors the standing harness (a
    temp workspace, a merged-state RUNNER_TEMP, a fake `gh` on PATH) with
    the import resolution flipped: the stashed runtime tree carries a
    resolvable scripts dir, so the step's own scripts-dir insertion puts the
    shared module on sys.path and the import lands. A `common` cached in
    sys.modules by another test module would satisfy the import without
    resolving from the stashed tree — it is popped for the run (restored
    after) so the stash is the resolution source."""
    import shutil
    ws = tempfile.mkdtemp(prefix="cw-report-ws-")
    rt = tempfile.mkdtemp(prefix="cw-report-rt-")
    cw = os.path.join(rt, "cw")
    os.makedirs(cw)
    # the report job's first step stashed the runtime tree to
    # $RUNNER_TEMP/cw/stash before its first checkout — the tree the step's
    # scripts-dir resolution reads, so on a runner where that path works the
    # shared module resolves from the stash
    shutil.copytree(os.path.join(ROOT, ".github"),
                    os.path.join(cw, "stash", ".github"))
    with open(os.path.join(cw, "resolved-config.txt"), "w", encoding="utf-8") as f:
        f.write("### Code Weaver — resolved configuration "
                "(workflow log; never committed)\n"
                "- issue: #42\n"
                "- LLM model (which configured model): `Ornith-1.5-35B-A3B`\n"
                "- caps: max-loops=`5` (0 = no cap)\n")
    with open(os.path.join(cw, "stage-summary.txt"), "w", encoding="utf-8") as f:
        f.write("stage 4 extract: clean — stage complete\n")
    fake = tempfile.mkdtemp(prefix="cw-report-fake-")
    binp = os.path.join(fake, "bin")
    os.makedirs(binp)
    comment_f = os.path.join(fake, "issue-comment.txt")
    # a PR view carrying the '## Final status' marker: a verified completion
    view_json = json.dumps(
        {"body": "## Progress so far\n\n## Final status\n"
                "- **Run result:** success\n",
         "head": {"sha": "f" * 40, "ref": "ai/code-weaver/42"},
         "html_url": "https://gh.example/pr/7"})
    with open(os.path.join(binp, "gh"), "w", encoding="utf-8") as f:
        f.write("#!%s\n" % sys.executable +
                "import json, os, sys\n"
                "args = sys.argv[1:]\n"
                "body = ''\n"
                "for a in args:\n"
                "    if a.startswith('body='):\n"
                "        body = a[len('body='): ]\n"
                "if args[:1] == ['api'] and any('pulls/' in a for a in args):\n"
                f"    print({view_json!r})\n"
                "    sys.exit(0)\n"
                "if args[:1] == ['api'] and 'state=closed' in args:\n"
                "    open(os.environ['FAKE_GH_OUT'] + '.closed', 'w')"
                ".write('closed')\n"
                "if body:\n"
                "    open(os.environ['FAKE_GH_OUT'], 'w').write(body)\n"
                "if args[:2] == ['pr', 'edit'] and '--body-file' in args:\n"
                "    bf = args[args.index('--body-file') + 1]\n"
                "    open(os.environ['FAKE_GH_OUT'] + '.pr-body', 'w')"
                ".write(open(bf).read())\n")
    os.chmod(os.path.join(binp, "gh"), 0o755)
    keys = ("PATH", "RUNNER_TEMP", "GITHUB_WORKSPACE", "GITHUB_REPOSITORY",
            "GH_TOKEN", "GITHUB_ACTION_PATH", "AI_BRANCH", "DOC_DIR",
            "CW_RUN_RESULT", "CW_PR_NUMBER", "CW_ISSUE_NUMBER", "FAKE_GH_OUT")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "PATH": binp + os.pathsep + (saved["PATH"] or ""),
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        "GITHUB_REPOSITORY": "code-weaver/test-target",
        "GH_TOKEN": "fake-token",
        "GITHUB_ACTION_PATH": "",
        "FAKE_GH_OUT": comment_f,
        "CW_RUN_RESULT": "success",
        "CW_ISSUE_NUMBER": "42",
        "CW_PR_NUMBER": "7",
    })
    hook, cwd = sys.excepthook, os.getcwd()
    common_mod = sys.modules.pop("common", None)
    path_saved = list(sys.path)
    os.chdir(ws)
    ns = {"__name__": "cw_report_action_import_path"}
    crashed = False
    pr_body = comment = ""
    closed = False
    try:
        try:
            exec(compile(_report_action_source(),
                          "<report action.yml run block>", "exec"), ns)
        except SystemExit:
            pass
        crashed = os.path.isfile(os.path.join(cw, "stage-fail-reason.txt"))
        pf = os.path.join(cw, "final-pr-body.md")
        if os.path.isfile(pf):
            pr_body = open(pf, encoding="utf-8").read()
        if os.path.isfile(comment_f):
            comment = open(comment_f, encoding="utf-8").read()
        closed = os.path.isfile(comment_f + ".closed")
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        sys.path[:] = path_saved
        if common_mod is not None:
            sys.modules["common"] = common_mod
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)
        shutil.rmtree(fake, ignore_errors=True)
    # the shared module resolved from the stashed runtime tree — the import
    # path's resolution source, not a copy elsewhere on sys.path
    mod = ns.get("common")
    assert isinstance(mod, types.ModuleType), \
        "the import path: `import common` must resolve the shared module"
    assert os.path.realpath(mod.__file__).startswith(
        os.path.realpath(os.path.join(cw, "stash", ".github", "scripts"))), \
        ("the shared module must resolve from the runtime tree the job "
         f"stashed to $RUNNER_TEMP, got {mod.__file__!r}")
    # the five plumbing names are bound for the step's body to the shared
    # module's definitions — the body's bare-name calls resolve on the
    # import path
    for name in ("state_dir", "state_file", "log", "gh_api", "push_branch"):
        assert ns.get(name) is getattr(mod, name), \
            (f"the import path must bind the body's {name} to the shared "
             f"module's definition, got {ns.get(name)!r}")
    # the step completes rather than crashing: the crash wrapper's
    # stage-fail-reason diagnosis (the one it writes before any report work)
    # is not produced — an undefined-name error would have written it
    assert not crashed, \
        ("the step died with an error before any report work — the crash "
         "wrapper's diagnosis was produced on the import path")
    # the report completes on the import path: the final PR body carries the
    # final status, the issue comment is posted, a successful run closes the
    # source issue
    assert "## Final status" in pr_body and "success" in pr_body, \
        f"the final PR body must carry the final status: {pr_body!r}"
    assert comment, "the issue comment must be posted on the import path"
    assert closed, "a successful run closes the source issue"


def test_report_fallback_plumbing_completes_the_report_as_the_import_path():
    """(reporting "The report step's fallback plumbing stays effective
    where the shared module cannot import" — new scenario; the "stays
    effective" half is the standing stage-contract tests, which force the
    import failure and assert the report the forced-fallback run
    completes; reference
    `requirements/reporting.feature::The report step's fallback plumbing
    stays effective where the shared module cannot import`) where the
    shared module does not resolve from the runtime
    tree, the step's ImportError branch stays in force — the body runs on
    its local fallback definitions and completes its report AS ON THE
    IMPORT PATH: the two paths are behaviourally equivalent for the
    report's output — one ledger, one set of numbers on both surfaces.
    The standing sandbox runs on both import resolutions (the
    forced-fallback path the standing tests use — the scripts dir scrubbed
    from sys.path, the `common` module popped; and the import path task 1
    makes work — the shared module resolving from the runtime tree the job
    stashed to $RUNNER_TEMP) and the two completed reports are asserted to
    agree: the same final-status content on the PR-body surface and the
    same issue comment — the usage totals, the stage outcomes, the
    pointer-vs-self-contained comment form — and the same close state."""
    ledger = ["10000 2000", "5000 1500"]
    # the run's one ledger: the totals every surface of both paths'
    # reports must carry
    totals = ("- **Total input tokens:** 15000",
              "- **Total output tokens:** 3500")
    # the completion timestamp is minute-granularity and the two runs may
    # straddle a minute boundary — normalise it before the equality
    norm = lambda s: re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC",
                            "<completed>", s)
    # the two comment forms the completion verification selects: a
    # verified completion keeps the pointer comment, a completion that
    # could not be applied makes the comment self-contained
    for view_body in ("## Progress so far\n\n## Final status\n- stale\n",
                      "## Progress so far"):
        fb_body, fb_comment, fb_closed = _run_report_action(
            ledger=ledger, view_body=view_body)
        im_body, im_comment, im_closed = _run_report_action(
            shared_module="import", ledger=ledger, view_body=view_body)
        for pr_body, comment, closed in (
                (fb_body, fb_comment, fb_closed),
                (im_body, im_comment, im_closed)):
            # the report completes on that path: the PR body carries the
            # final status, the usage totals and the stage outcomes
            assert "## Final status" in pr_body and "success" in pr_body, \
                f"the final PR body must carry the final status: {pr_body!r}"
            for line in totals:
                assert line in pr_body, \
                    f"the PR body lists the run's totals: {pr_body!r}"
                assert line in comment, \
                    f"the issue comment lists the same totals: {comment!r}"
            assert "### Stage outcomes" in pr_body, pr_body
            assert "stage 4 extract: clean" in pr_body, pr_body
            if "## Final status" in view_body:
                assert "final status is in the PR body" in comment, \
                    (f"a verified completion keeps the pointer comment: "
                     f"{comment!r}")
            else:
                assert "could not be completed" in comment, comment
                assert "### Stage outcomes" in comment, comment
                assert "stage 4 extract: clean" in comment, comment
            assert closed, "a successful run closes the source issue"
        # the two completed reports agree: the same final-status content
        # on the PR-body surface and the same issue comment (the usage
        # totals, the stage outcomes, the pointer-vs-self-contained form)
        # and the same close state
        assert norm(im_body) == norm(fb_body), \
            ("the fallback-completed report must equal the import path's: "
             f"{im_body!r} != {fb_body!r}")
        assert norm(im_comment) == norm(fb_comment), \
            ("the fallback-completed issue comment must equal the import "
             f"path's: {im_comment!r} != {fb_comment!r}")
        assert im_closed == fb_closed, \
            (f"the close state must agree on both paths: "
             f"{im_closed} != {fb_closed}")


def test_report_lists_usage_totals_assembled_from_the_ledger():
    """(issue-43 "the final report lists the input and output tokens used
    during the run", "the usage totals cover every pi call the run
    made"; reference
    `requirements/cost-and-token-usage.feature::The final report lists
    the input and output tokens used during the run`,
    `requirements/cost-and-token-usage.feature::The usage totals cover
    every pi call the run made`)
    the report action assembles the run's usage totals from the per-call
    usage records in the state dir (one tokens.txt line per pi call: input
    + output tokens; the report job downloads the stages' artifacts in
    pipeline order, so the ledger surviving the downloads is the complete
    one) into the final status report: the PR body lists the total input
    and the total output tokens across the run, and the source-issue
    comment carries the same totals."""
    pr_body, comment, _closed = _run_report_action(
        ledger=["10000 2000", "5000 1500"])
    for surface in (pr_body, comment):
        assert "- **Total input tokens:** 15000" in surface, \
            ("the report must total every pi call the run made "
             f"(10000 + 5000 input): {surface!r}")
        assert "- **Total output tokens:** 3500" in surface, \
            ("the report must total every pi call the run made "
             f"(2000 + 1500 output): {surface!r}")


def test_report_cost_derives_from_usage_and_resolved_model():
    """(issue-43 "the final report lists the total cost of the run" —
    "the listed cost is consistent with the run's recorded token usage";
    reference
    `requirements/cost-and-token-usage.feature::The final report lists
    the total cost of the run`)
    the listed cost is derived from the recorded usage, keyed on the run's
    resolved model (the llm-model setting from the trigger's
    resolved-config state), and priced at the rates the run's model
    configuration declares for that model — the `cost` object of the
    model's models.json entry, read from the configuration's provider the
    way the setup stage resolves it (here the repo file
    .pi/agent/models.json, the source the report lists so the cost stays
    auditable); a model the configuration carries no cost entry for is
    listed as unpriced, and the recorded usage
    totals still land in the report."""
    # 15000 in / 3500 out across the run; the resolved model is priced by
    # the configuration the sandbox writes as the repo file
    ledger = ["10000 2000", "5000 1500"]
    r_in, r_out = 0.10, 0.20
    priced = (f"- **Total cost:** ${(15000 * r_in + 3500 * r_out) / 1e6:.4f} "
              f"(model `Ornith-1.5-35B-A3B` @ ${r_in:.2f}/M input, "
              f"${r_out:.2f}/M output — rates from the repo file "
              f".pi/agent/models.json)")
    pr_body, comment, _closed = _run_report_action(
        ledger=ledger, models_config=_models_config(r_in, r_out))
    for surface in (pr_body, comment):
        assert priced in surface, \
            ("the listed cost must be recorded usage × the resolved model's "
             f"configuration rates, with the source listed: {surface!r}")
    # a model the configuration carries but gives no cost entry for is
    # listed as unpriced — the usage totals are reported regardless
    pr_body, comment, _closed = _run_report_action(
        ledger=ledger, model="Some-Other-Runner-Model",
        models_config=_models_config(r_in, r_out))
    unpriced = (f"- **Total cost:** unpriced (model "
                f"`Some-Other-Runner-Model` has no cost rates in the "
                f"run's model configuration — put the model's cost rates in "
                ".pi/agent/models.json (or the models-configuration "
                f"secret))")
    for surface in (pr_body, comment):
        assert unpriced in surface, \
            f"a model with no cost entry is listed as unpriced: {surface!r}"
        assert "- **Total input tokens:** 15000" in surface
        assert "- **Total output tokens:** 3500" in surface


def test_report_cost_prices_at_the_secret_provider_over_the_repo_file():
    """(the same issue-43 cost pin — provider resolution; reference
    `requirements/cost-and-token-usage.feature::The final report lists
    the total cost of the run`) the rates the report prices with are the
    ones the run's model
    configuration declares, and the configuration is resolved the way the
    setup stage resolves it: a non-empty PI_MODELS secret wins over the
    repo file .pi/agent/models.json. The sandbox carries both providers at
    different rates — the report must list the secret's rates, name the
    provider it priced from, and stay consistent with the recorded
    usage."""
    ledger = ["10000 2000"]
    r_in, r_out = 0.30, 0.40
    priced = (f"- **Total cost:** ${(10000 * r_in + 2000 * r_out) / 1e6:.4f} "
              f"(model `Ornith-1.5-35B-A3B` @ ${r_in:.2f}/M input, "
              f"${r_out:.2f}/M output — rates from the run's model "
              f"configuration (a GitHub secret))")
    pr_body, comment, _closed = _run_report_action(
        ledger=ledger,
        models_config=_models_config(0.10, 0.20),
        pi_models_env=_models_config(0.30, 0.40))
    for surface in (pr_body, comment):
        assert priced in surface, \
            ("a non-empty PI_MODELS secret wins over the repo file — "
             f"the report must price at the secret's rates: {surface!r}")


def test_failed_run_report_covers_the_calls_before_the_stop():
    """(issue-43 "the usage and cost of a failed run are reported too";
    reference
    `requirements/cost-and-token-usage.feature::The usage and cost of a
    failed run are reported too`) the report job runs on success and
    failure: a run that stopped early
    in a failed stage is reported with the usage and cost of the pi calls
    made before the stop — a stage that never ran (its artifact never
    uploaded) contributes nothing, so the totals cover exactly the
    pre-stop calls. The failed run's issue comment lists the tokens and
    the cost (with a PR: alongside the stage outcomes; without one, the
    no-PR failure comment: the PR body has no final status to complete).
    """
    # the run made pi calls in one stage before it stopped; the later
    # stages never ran, so the ledger holds exactly the pre-stop calls
    ledger = ["3000 400"]
    r_in, r_out = 0.10, 0.20
    priced = (f"- **Total cost:** ${(3000 * r_in + 400 * r_out) / 1e6:.4f} "
              f"(model `Ornith-1.5-35B-A3B` @ ${r_in:.2f}/M input, "
              f"${r_out:.2f}/M output — rates from the repo file "
              f".pi/agent/models.json)")
    # a failed run that reached the PR: the comment (and the PR body's
    # final status) carry the pre-stop usage and cost
    pr_body, comment, _closed = _run_report_action(
        run_result="failure", ledger=ledger,
        models_config=_models_config(r_in, r_out))
    for surface in (pr_body, comment):
        for line in ("- **Total input tokens:** 3000",
                     "- **Total output tokens:** 400",
                     priced):
            assert line in surface, \
                ("a failed run is reported with the calls made before "
                 f"the stop: {surface!r}")
    # a run that died before the PR existed: the no-PR failure comment
    # still lists the pre-stop usage and cost
    pr_body, comment, _closed = _run_report_action(
        run_result="failure", pr_number="",
        ledger=ledger, models_config=_models_config(r_in, r_out))
    assert pr_body == "", "no PR was opened — there is no PR body to complete"
    for line in ("- **Total input tokens:** 3000",
                 "- **Total output tokens:** 400",
                 priced):
        assert line in comment, \
            f"the no-PR failure report still lists the pre-stop usage: {comment!r}"


def test_report_verifies_the_pr_body_completion():
    """(reporting "the PR description carries the same usage numbers as
    the issue comment"; reference
    `requirements/reporting.feature::The PR description carries the
    same usage numbers as the issue comment`) after editing the PR body
    the stage re-reads the
    PR: where the completion is verifiably in the body, the issue comment
    is the pointer form — 'final status is in the PR body' — and still
    lists the usage lines, the same strings the body carries (one ledger,
    one set of numbers on both surfaces), and the run's success closes the
    source issue."""
    pr_body, comment, closed = _run_report_action(
        ledger=["10000 2000", "5000 1500"],
        view_body="## Progress so far\n\n## Final status\n- stale\n")
    assert "final status is in the PR body" in comment, \
        f"a verified completion keeps the pointer comment: {comment!r}"
    for line in ("- **Total input tokens:** 15000",
                 "- **Total output tokens:** 3500"):
        assert line in comment, f"the comment lists the run's usage: {comment!r}"
        assert line in pr_body, \
            ("the PR description carries the same numbers the comment "
             f"posts: {pr_body!r}")
    assert closed, "a successful run closes the source issue"


def test_report_unverified_completion_makes_the_comment_self_contained():
    """(reporting "the PR description carries the same usage numbers as
    the issue comment"; reference
    `requirements/reporting.feature::The PR description carries the
    same usage numbers as the issue comment`) where the completion could
    not be applied to the
    PR — the re-read shows a body without it (the PR was already merged,
    or the edit was refused on both write paths) — the issue comment
    carries the full final status itself: the usage lines and the stage
    outcomes — and makes no claim that the PR body carries them."""
    pr_body, comment, closed = _run_report_action(
        ledger=["10000 2000", "5000 1500"])
    assert "final status is in the PR body" not in comment, \
        f"the comment must not claim what the PR body never got: {comment!r}"
    assert "could not be completed" in comment
    assert "- **Total input tokens:** 15000" in comment
    assert "- **Total output tokens:** 3500" in comment
    assert "### Stage outcomes" in comment
    assert "stage 4 extract: clean" in comment
    assert closed, "a successful run closes the source issue either way"


def test_failed_run_leaves_the_source_issue_open():
    """(reporting "a failed run leaves the source issue open";
    reference
    `requirements/reporting.feature::A failed run leaves the source
    issue open`) a failure
    reports the stage outcomes and the pre-stop usage on the issue — but
    never closes it: the issue stays open for a re-trigger."""
    pr_body, comment, closed = _run_report_action(
        run_result="failure", ledger=["3000 400"])
    assert "run failed" in comment
    assert "left open" in comment, \
        f"a failed run's comment states the issue stays open: {comment!r}"
    assert not closed, "a failed run must not close the source issue"


def test_report_renders_stage_outcomes_per_step_and_stage_complete():
    """(reporting "The final status report is the PR" — the two And lines
    this run's delta adds to the scenario: a stage that will re-run is
    reported per step — "step <k>/<n> done" for each of its finished
    steps — and a stage that is done is reported "stage complete"; the
    scenario's standing lines — run status, source issue, every stage
    outcome, no report file in the repo — stand; reference
    `requirements/reporting.feature::The final status report is the PR`)
    the report stage's stage-outcome assembly renders from the recorded
    stage-summary lines (the state dir the report job downloads — state
    rides artifacts, never the repo tree): the implement stage records its
    per-step state on that channel — one "stage 8 implementation: step
    <k>/<n> done" line per step it finished, a "stage complete" line only
    when its plan is fully tracked. A stage that will re-run (per-step
    lines without a completion line) is reported per step on both report
    surfaces the report completes — the PR body's stage-outcomes table and,
    in the self-contained form, the issue comment — "step <k>/<n> done"
    for each of its finished steps; a stage that is done (its summary
    carries a completion line) is reported "stage complete", its per-step
    lines staying out of the outcome."""
    # the implement stage will re-run: its per-step lines are recorded and
    # no completion line (its plan left steps open, so the per-step loop
    # never exited fully tracked) — while the extract stage's summary
    # carries its completion line (a stage that is done)
    pr_body, comment, _closed = _run_report_action(stage_summary=(
        "stage 4 extract: clean — stage complete\n"
        "stage 8 implementation: step 1/3 done\n"
        "stage 8 implementation: step 2/3 done\n"))
    for surface in (pr_body, comment):
        assert "### Stage outcomes" in surface, surface
        # a stage that is done: reported "stage complete"
        assert "stage 4 extract: clean — stage complete" in surface, \
            f"a done stage is reported 'stage complete': {surface!r}"
        # a stage that will re-run: reported per step — "step <k>/<n>
        # done" for each of its finished steps
        assert "stage 8 implementation: step 1/3 done" in surface, surface
        assert "stage 8 implementation: step 2/3 done" in surface, surface
        # …and that stage carries no completion line of its own
        assert "stage 8 implementation: stage complete" not in surface, \
            (f"a stage that will re-run carries no completion line: "
             f"{surface!r}")
    # …and the complement: the implement stage fully tracked its plan —
    # its summary carries the per-step lines AND its completion line — so
    # it is a stage that is done, reported "stage complete": the
    # per-step lines stay out of the outcome
    pr_body, comment, _closed = _run_report_action(stage_summary=(
        "stage 4 extract: clean — stage complete\n"
        "stage 8 implementation: step 1/3 done\n"
        "stage 8 implementation: step 2/3 done\n"
        "stage 8 implementation: step 3/3 done\n"
        "stage 8 implementation: stage complete\n"))
    for surface in (pr_body, comment):
        assert "### Stage outcomes" in surface, surface
        assert "stage 8 implementation: stage complete" in surface, \
            f"a stage that is done is reported 'stage complete': {surface!r}"
        for k in (1, 2, 3):
            assert f"step {k}/3 done" not in surface, \
                (f"a done stage's per-step lines stay out of the outcome: "
                 f"{surface!r}")
        assert "stage 4 extract: clean — stage complete" in surface, surface


def test_validator_skips_when_parser_port_absent():
    """(test-and-review "the suite runs on an interpreter without
    pytest"; reference
    `requirements/test-and-review.feature::The suite runs on an
    interpreter without pytest`) where the official Gherkin-parser port
    is absent, the oracle check is
    skipped-not-failed: validate_file reports a skip and exits clean, and
    the validator's own parser-dependent unit tests skip with it."""
    spec = importlib.util.spec_from_file_location(
        "gw_stage_contract",
        os.path.join(ROOT, ".github", "scripts", "gherkin-validate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    real = mod.Parser
    try:
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd()
            os.chdir(d)
            try:
                with open("ok.feature", "w", encoding="utf-8") as f:
                    f.write("Feature: a tiny oracle\n  Scenario: it parses\n    Given x\n")
                mod.Parser = None  # simulate an interpreter without the port
                rc, errs = mod.validate_file("ok.feature")
                assert rc == 0, f"absent port must not fail, got rc={rc}: {errs}"
                assert any("skipped" in e for e in errs)
            finally:
                os.chdir(cwd)
        # the test file carries the skip guards for its parser-dependent tests
        tv = _read("tests/test_validator.py")
        assert tv.count("if Parser is None") >= 4
    finally:
        mod.Parser = real


def _workflow_input_default(factory: str, name: str) -> str:
    """A reusable-workflow input's default, line-based (stdlib only — the
    inputs block is flat, and the whole-document yaml parse this repo's
    trigger-contract tests deliberately avoid is not needed here)."""
    lines = factory.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip() == f"{name}:":
            for j in range(i + 1, min(i + 5, len(lines))):
                m = re.search(r'^\s+default:\s*"([^"]*)"', lines[j])
                if m:
                    return m.group(1)
            break
    raise AssertionError(f"no default found for input {name!r}")


def _workflow_input_entry(factory: str, name: str) -> str:
    """One entry of the workflow_call inputs block, line-based (the same
    stdlib-only parse-avoidance as _workflow_input_default): from its
    6-indent key line to the next 6-indent (or shallower) line, kept as
    text so a test can assert the entry's type and required lines."""
    lines = factory.splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if ln.strip() == f"{name}:"), None)
    assert start is not None, \
        f"no {name} input in the factory's inputs block"
    entry = [lines[start]]
    for cont in lines[start + 1:]:
        if cont.strip():
            indent = len(cont) - len(cont.lstrip(" "))
            if indent <= 6:
                break
        entry.append(cont)
    return "\n".join(entry)


def test_stage_instructions_avoid_file_lists_without_meaning():
    """(configuration "A stage instruction avoids file lists that carry no
    meaning"; reference
    `requirements/configuration.feature::A stage instruction avoids file
    lists that carry no meaning`) a file list appears in a stage
    instruction only where the set is the instruction's scope, and no
    instruction lists project files as context to rummage through: the
    rummage phrasing is gone from every stage's instruction surface (the
    five prompt templates, the prompt files the stages assemble — the
    plan target, the implement target, the review prompt, the PR body
    prompt — and the guard's repair instructions), the scoped file lists
    appear exactly where the scenario names them (the plan's
    changed-requirements list, the guard's off-limits list in the repair
    instructions, the implement target's single plan file), and each is
    tied in the instructions to the scope it bounds."""
    import shutil
    # no instruction lists project files as context to rummage through —
    # the rummage phrasing is gone from every stage's instruction surface:
    # the five prompt templates, the prompt-file assembly in the stage
    # scripts, the PR body prompt assembly in the workflow, and the
    # guard's repair instructions. (The plumbing's bracketed context block
    # is the invocation's path-referenced slice — the standing @config
    # scenario governs what the invocation embeds; this rule governs what
    # the instructions say.)
    surfaces = (
        "pi-prompts/requirements.md",
        "pi-prompts/plan.md",
        "pi-prompts/implement.md",
        "pi-prompts/review.md",
        "pi-prompts/pr-body.md",
        ".github/actions/extract-stage/stage.py",
        ".github/actions/plan-stage/stage.py",
        ".github/actions/implement-stage/stage.py",
        ".github/actions/review-stage/stage.py",
        ".github/workflows/factory.yml",
        ".github/scripts/common.py",
    )
    for path in surfaces:
        text = _read(path).lower()
        for phrase in ("rummage", "browse", "the ones you need",
                       "open what you need", "as you like"):
            assert phrase not in text, (
                f"{path} lists project files as context to rummage "
                f"through ({phrase!r}) — a file list appears in an "
                f"instruction only where the set is the instruction's "
                f"scope")
    # a file-list segment in a prompt template (two or more consecutive
    # bullet lines naming files) must be tied to the scope it bounds —
    # today none of the five templates carries one (the oracle reaches the
    # extract call as its directory; the plan's delta list, the guard's
    # off-limits list and the implement target's plan file ride the
    # assembled prompt files)
    file_bullet = re.compile(
        r"^\s*[-*]\s+.*(?:`[^`]+\.(?:md|feature|py|txt|json|yml|toml)`"
        r"|\b[\w.-]+/[^\s`]*\.(?:md|feature|py|txt|json|yml|toml)\b)")
    scope_ties = ("the delta this plan must cover", "your task's input",
                  "verdict scope", "exactly this plan file",
                  "the off-limits files that changed",
                  "no other file may change", "generated from all of them")
    for template in ("requirements", "plan", "implement", "review",
                     "pr-body"):
        lines = _read(f"pi-prompts/{template}.md").splitlines()
        run = 0
        for i, line in enumerate(lines):
            if not file_bullet.match(line):
                run = 0
                continue
            run += 1
            if run >= 2:
                header = next((l.strip() for l in reversed(lines[:i])
                               if l.strip()), "")
                assert any(t in header for t in scope_ties), (
                    f"pi-prompts/{template}.md lists files as context to "
                    f"rummage through — the list's set is not the "
                    f"instruction's scope (introduced by {header!r})")
    # the scoped file lists appear exactly where the scenario names them,
    # each tied in the instructions to the scope it bounds —
    # (1) the plan's changed-requirements list: the delta section the plan
    # target carries — the list is introduced as the delta's input and the
    # changes ride as the delta the plan must cover
    plan_stage = _read(".github/actions/plan-stage/stage.py")
    assert "## The requirement delta (your task's input)" in plan_stage
    assert "The following requirement files changed since the run's " \
        in plan_stage
    assert "the delta this plan must cover" in plan_stage
    # (2) the guard's off-limits list in the repair instructions — the
    # assembled instructions name the off-limits files, the list is
    # introduced as the revert's scope, and the revert is bounded to the
    # named files (no other file may change)
    spec = importlib.util.spec_from_file_location(
        "cw_guard_repair_instructions",
        os.path.join(ROOT, ".github", "scripts", "common.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cw_guard_repair_instructions"] = mod  # the @dataclass resolves its module
    try:
        spec.loader.exec_module(mod)
        ins = mod._guard_repair_instructions(
            "baseline-sha", ["requirements/guard-rail.feature",
                              "plans/9.md"],
            "stage 8 implementation", "implement")
        assert "The off-limits files that changed against the stage's " \
            "baseline" in ins
        assert "  - requirements/guard-rail.feature" in ins
        assert "  - plans/9.md" in ins
        assert "Revert exactly the named files — no other file may change." \
            in ins
        assert "Keep the stage's own work valid against the task its " \
            "initial instructions gave it" in ins
    finally:
        sys.modules.pop("cw_guard_repair_instructions", None)
    # (3) the implement target's single plan file — the target names
    # exactly the one plan file the stage works, and only that one
    spec = importlib.util.spec_from_file_location(
        "cw_implement_target",
        os.path.join(ROOT, ".github", "actions", "implement-stage",
                     "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    saved = {k: os.environ.get(k) for k in ("RUNNER_TEMP",)}
    rt = tempfile.mkdtemp(prefix="cw-instr-scope-")
    os.environ["RUNNER_TEMP"] = rt
    try:
        target = open(mod.build_target("42", "plans"),
                      encoding="utf-8").read()
        assert "Open and update exactly this plan file (and only this " \
            "issue's plan)" in target
        assert "    plans/42.md" in target
        assert target.count(".md") == 1, \
            "the implement target names exactly one plan file"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(rt, ignore_errors=True)
    # the review prompt's file lists are scope lists — the changed feature
    # files' scenarios and the scenarios the changed tests reference join
    # the verdict scope (the set is the instruction's scope, as the
    # plan's delta list is) — and the PR body prompt's context list is the
    # body's scope: the body is generated from all of its context files,
    # each role naming the part of the body its source supplies
    review_stage = _read(".github/actions/review-stage/stage.py")
    assert "are in your verdict scope" in review_stage
    assert "the verdict scope with the changed feature files'" in review_stage
    factory = _read(".github/workflows/factory.yml")
    assert "The context files the pi call carries — the body is " \
        in factory
    assert "generated from all of them" in factory
    assert "each role naming the part of the body its source supplies:" \
        in factory


def test_loop_cap_defaults_match_oracle():
    """(configuration "the loop caps are configurable", "a loop cap of 0
    means no cap"; reference
    `requirements/configuration.feature::The loop caps are
    configurable`,
    `requirements/configuration.feature::A loop cap of 0 means no
    cap`) the oracle's Given pins the factory's max-loops default
    as 5 — the reusable workflow declares it, and the doc surface that
    repeats the value (the README's input table, the arc42 quality chapter)
    agrees with it; the token budget is gone from the configuration surface
    — no max-tokens row on the doc surfaces, no token-budget default
    wording — and the old 25 / 5,000,000 pair is gone from the tree. A
    target still lowers or raises the cap per repo — the inputs → job env →
    caps_ok machinery is unchanged (0 = no cap). The loop rename the
    delta's adjusted configuration/cost/safety scenarios carry lands on
    these surfaces: the quality chapter's "Loop caps" bullet and the README
    state the loop name as "guard repair", and "guard re-run" appears on
    neither."""
    factory = _read(".github/workflows/factory.yml")
    assert _workflow_input_default(factory, "max-loops") == "5", \
        "the oracle pins the MAX_LOOPS default as 5"
    readme = _read("README.md")
    quality = _read("docs/09-quality-requirements.md")
    assert "| `max-loops` | `5` |" in readme
    assert "default 5" in quality
    # the token budget is gone from the doc surfaces that used to repeat
    # it: no max-tokens row, no token-budget default wording
    assert "| `max-tokens` |" not in readme
    assert "default 500,000" not in quality
    # the old declared pair is gone from every surface that repeats it
    assert "| `max-loops` | `25` |" not in readme
    assert "| `max-tokens` | `5000000` |" not in readme
    assert "default 25" not in quality
    for surface in (factory, readme, quality):
        assert "5000000" not in surface
        assert "5,000,000" not in surface
    # the loop-cap surfaces state the loop name as "guard repair" (the
    # delta's rename), and the old "guard re-run" name appears on none of
    # them
    assert "guard repair" in quality
    assert "guard re-run" not in quality
    assert "guard repair" in readme
    assert "guard re-run" not in readme


def test_pi_call_time_cap_is_a_configurable_workflow_input():
    """(configuration "The pi call time cap is a configurable workflow
    input"; reference
    `requirements/configuration.feature::The pi call time cap is a
    configurable workflow input`) the reusable workflow declares
    pi-timeout on its input surface — a string input, optional (an
    older consumer's with: block stays schema-valid), default "21600":
    the 360-minute per-call cap that today rides the shared pi-call
    plumbing as a hard-coded constant becomes one of the settings a
    target overrides per repo through the with: block, and the
    README's Inputs table carries the row. A consumer that leaves the
    input undeclared keeps the current 360-minute cap, so such a run is
    unchanged — the consumer workflow gains no line: this repo's own
    consumer workflow (the dogfood) declares no pi-timeout of its own.
    The cap's runtime half — the stage jobs relaying the value and the
    shared pi-call plumbing resolving the chain, and the trigger's
    resolved-configuration record naming the resolved cap — lands in the
    steps that consume the input; this test pins the declaration and the
    doc surface."""
    factory = _read(".github/workflows/factory.yml")
    # the input surface declares the cap with the 360-minute default —
    # a string input, optional (an older consumer's with: block stays
    # schema-valid), the max-loops/dependency-upgrade input pattern
    assert _workflow_input_default(factory, "pi-timeout") == "21600", \
        "the pi call time cap's default is the 360-minute cap"
    entry = _workflow_input_entry(factory, "pi-timeout")
    assert "type: string" in entry, \
        "the pi-timeout input is not a string input"
    assert "required: false" in entry, \
        "the pi-timeout input must be optional — an older " \
        "consumer's with: block stays schema-valid"
    # the README's Inputs table carries the row
    readme = _read("README.md")
    assert "| `pi-timeout` | `21600` |" in readme, \
        "the README's Inputs table has no pi-timeout row"
    # a consumer that leaves the input undeclared keeps the current
    # 360-minute cap, so such a run is unchanged: the consumer
    # workflow gains no line (this repo's own consumer workflow — the
    # dogfood — declares no pi-timeout of its own)
    consumer = _read(".github/workflows/code-weaver.yml")
    assert "pi-timeout" not in consumer, \
        "the consumer workflow gains no pi-timeout line — a consumer " \
        "that leaves the input undeclared runs unchanged"


def _pi_timeout_sandbox(cw_pi_timeout):
    """The sandbox the pi call cap's job-env relay half runs: a temp
    workspace (GITHUB_WORKSPACE — the call's cwd), a temp RUNNER_TEMP state
    dir, the suite's fake `pi` on PATH (it records the call and settles
    cleanly), and the fake job env — CW_PI_TIMEOUT where the test names a
    value, BOTH chain links unset where it is None (the
    undeclared-consumer half). The stage code (stages.pi_stage → the shared
    pi-call plumbing) runs in-process against a spy on the plumbing's
    subprocess call that records the timeout kwarg it hands the pi
    subprocess — the fake answers promptly, so the recorded value is the
    cap the call ran under, no waiting out a 360-minute default. The
    stage's template file resolves against the repository's own
    `pi-prompts/` dir (the stage code anchors it from the shared module's
    own location, the way it resolves in the factory's stashed runtime
    tree), so the sandbox calls the stage with a template the repo
    carries. Returns a namespace: repo, rt, fake,
    captured_timeout (the timeout the pi subprocess ran under — None when
    the plumbing never reached the subprocess), returncode, and cleanup
    (restore the env, the spy, the sys.modules/sys.path entries and remove
    the temp dirs)."""
    import shutil
    import subprocess
    import tempfile
    repo = tempfile.mkdtemp(prefix="cw-pitmo-repo-")
    rt = tempfile.mkdtemp(prefix="cw-pitmo-rt-")
    fake = tempfile.mkdtemp(prefix="cw-pitmo-fake-")
    os.makedirs(os.path.join(fake, "bin"))
    with open(os.path.join(fake, "bin", "pi"), "w") as f:
        f.write(_FAKE_PI)
    os.chmod(os.path.join(fake, "bin", "pi"), 0o755)

    keys = ("GITHUB_WORKSPACE", "RUNNER_TEMP", "LLM_MODEL", "PATH",
            "INPUT_PI_TIMEOUT", "CW_PI_TIMEOUT")
    saved = {k: os.environ.get(k) for k in keys}
    # both chain links start unset; the test's value (where it names one)
    # rides the CW_ link — the job-env relay the stage jobs carry
    for k in ("INPUT_PI_TIMEOUT", "CW_PI_TIMEOUT"):
        os.environ.pop(k, None)
    if cw_pi_timeout is not None:
        os.environ["CW_PI_TIMEOUT"] = str(cw_pi_timeout)
    os.environ.update({
        "GITHUB_WORKSPACE": repo,
        "RUNNER_TEMP": rt,
        "LLM_MODEL": "fake-model",
        "PATH": os.path.join(fake, "bin") + os.pathsep + (saved["PATH"] or ""),
    })

    # the stage code's `import common` must resolve to the repo's shared
    # module: a suite sibling that already installed it under the canonical
    # name is reused (it is that very file); otherwise the scripts dir goes
    # on sys.path and the import loads it
    scripts = os.path.join(ROOT, ".github", "scripts")
    common_mod = sys.modules.get("common")
    added_path = (common_mod is None
                  or not (getattr(common_mod, "__file__", "") or "")
                      .replace(os.sep, "/")
                      .endswith(".github/scripts/common.py"))
    if added_path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "cw_stages_pi_timeout_sandbox",
        os.path.join(scripts, "stages.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cw_stages_pi_timeout_sandbox"] = mod
    spec.loader.exec_module(mod)

    # the spy: record the timeout the plumbing hands the pi subprocess,
    # then delegate to the real run (the fake pi it spawns answers
    # promptly, so the delegation completes under the cap)
    captured = {}
    real_run = subprocess.run

    def spy_run(*args, **kw):
        captured["timeout"] = kw.get("timeout")
        return real_run(*args, **kw)
    subprocess.run = spy_run
    try:
        r = mod.pi_stage("pr-body")
    finally:
        subprocess.run = real_run

    def cleanup():
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if added_path:
            sys.path.remove(scripts)
        sys.modules.pop("cw_stages_pi_timeout_sandbox", None)
        for d in (repo, rt, fake):
            shutil.rmtree(d, ignore_errors=True)

    return {"repo": repo, "rt": rt, "fake": fake,
            "captured_timeout": captured.get("timeout"),
            "returncode": getattr(r, "returncode", None),
            "cleanup": cleanup}


def test_pi_call_cap_rides_the_job_env_relay():
    """(configuration "The pi call cap rides the job-env relay like every
    other setting" — the runtime half of "The pi call time cap is a
    configurable workflow input"; reference
    `requirements/configuration.feature::The pi call cap rides the job-env
    relay like every other setting`,
    `requirements/configuration.feature::The pi call time cap is a
    configurable workflow input`) every stage job relays the declared
    value as CW_PI_TIMEOUT in its job env — the documented CW_<name>
    job/step env idiom the other settings ride — and the shared pi-call
    plumbing resolves each call's time cap as INPUT_PI_TIMEOUT, then
    CW_PI_TIMEOUT, then the 21600 code default: a value set at the
    CW_PI_TIMEOUT link caps the run's pi calls, and a consumer that
    leaves the input undeclared (no value at either chain link) resolves
    the 21600-second 360-minute cap its run ran under before the input
    existed — the sandbox drives the stage code against a fake job env
    and a spy records the timeout the pi subprocess runs under, while the
    workflow-file half asserts each stage job's env carries the relay
    from the input (the guard's repair call and the PR-body call ride the
    same shared plumbing, and the setup stage's smoke check runs under
    its short probe budget, the target's value where it is shorter). The
    sandbox's third case — a CW_PI_TIMEOUT declared longer than the
    stage jobs' job-level timeout-minutes backstop (the clamp case the
    delta's deleted scenario quoted) — records the pi subprocess running
    under the declared value: the chain no longer clamps the resolved
    cap. The trigger-time validation is the enforcement point — a
    declared value that leaves the stage's non-call work no headroom
    inside the job's timeout fails the run at trigger time, and no stage
    runs after the trigger — so a run that reaches a stage has validated
    that its resolved cap leaves that headroom: a value set at the
    CW_PI_TIMEOUT link caps the run's pi calls, as declared."""
    # the workflow-file half: every stage job's job-env block relays
    # CW_PI_TIMEOUT from the reusable workflow's pi-timeout input
    factory = _read(".github/workflows/factory.yml")
    lines = factory.splitlines()
    job_keys = ("trigger", "setup-pi", "baseline", "extract", "plan",
                "implement", "review", "pr", "gates", "report")
    starts = [i for i, ln in enumerate(lines)
              if ln.startswith("  ") and not ln.startswith("   ")
              and ln.strip() in {k + ":" for k in job_keys}]
    assert len(starts) == len(job_keys), \
        f"the factory's ten jobs are not all found in the workflow file: " \
        f"{len(starts)}"
    relay = "CW_PI_TIMEOUT: ${{ inputs.pi-timeout }}"
    for a, b in zip(starts, starts[1:] + [len(lines)]):
        name = lines[a].strip()[:-1]
        # stage 1 makes no pi call — the relay rides the stage jobs' env
        if name == "trigger":
            continue
        section = "\n".join(lines[a:b])
        env = section[section.index("    env:"):section.index("    steps:")]
        assert relay in env, \
            (f"the {name} job's env does not relay CW_PI_TIMEOUT from "
             "the reusable workflow's pi-timeout input")
    # the sandbox half: a fake job env drives the stage code / shared
    # pi-call plumbing — with CW_PI_TIMEOUT set, the pi subprocess call
    # runs under that timeout; with neither chain link set, it resolves
    # to the 21600-second default
    # a value set at the CW_PI_TIMEOUT link caps the run's pi calls at
    # that declared value (12345s — headroom to spare inside the stage
    # jobs' job-level timeout-minutes backstop — and the 99999s that
    # declares a cap longer than the backstop: the chain no longer
    # clamps it, the trigger-time validation is the enforcement point,
    # so a run that reaches a stage has validated that its resolved cap
    # leaves the stage's non-call work its headroom); with neither chain
    # link set the cap resolves to the 21600-second default
    for cw_value, expected in (("12345", 12345), (None, 21600),
                               (99999, 99999)):
        ns = _pi_timeout_sandbox(cw_value)
        try:
            assert ns["captured_timeout"] == expected, \
                (f"the pi subprocess ran under timeout "
                 f"{ns['captured_timeout']!r} with CW_PI_TIMEOUT="
                 f"{cw_value!r} — the stage code did not resolve the "
                 f"cap through INPUT_PI_TIMEOUT → CW_PI_TIMEOUT → the "
                 f"21600 default and honour the resolved value: the "
                 f"chain carries no clamp any more (a declared value "
                 f"that leaves the stage's non-call work no headroom "
                 f"inside the job's timeout fails the run at trigger "
                 f"time, so no run that reached a stage carried one)")
            assert ns["returncode"] == 0, \
                "the pi call completed under its cap (the fake answers)"
        finally:
            ns["cleanup"]()


def test_job_timeout_backstop_is_a_target_side_input():
    """(configuration "The job's timeout backstop is a target-side
    input" — adjusted: it flips the baseline scenario "The job's timeout
    backstop is a factory-side property", which this delta deletes in
    the same hunk; reference
    `requirements/configuration.feature::The job's timeout backstop is
    a target-side input`) the reusable workflow declares the job-timeout
    input — a string input, optional (an older consumer's with: block
    stays schema-valid), default "480" minutes — and the five stage jobs
    that make pi calls (extract, plan, implement, review, pr — the jobs
    whose steps carry the stages' generation calls, the guard's repair
    call and the PR-body call) carry the target's value as their
    job-level timeout-minutes, while the jobs that stay factory-side —
    the trigger (which declares no job-level timeout at all) and
    setup-pi, baseline, gates and report, which the delta leaves
    unchanged — keep their fixed declarations: the trigger and setup-pi
    jobs are unaffected by the input, and a consumer that leaves the
    input undeclared resolves the 480-minute backstop, so its run is
    unchanged. The stage code still knows that same value through the
    shared plumbing — the constant common.py resolves matches the
    input's default, the value an undeclared consumer's jobs run under,
    so the file↔code one property the test pins can never drift
    apart."""
    factory = _read(".github/workflows/factory.yml")
    # the reusable workflow's input surface declares job-timeout — a
    # string input, optional (an older consumer's with: block stays
    # schema-valid), default "480" minutes
    assert _workflow_input_default(factory, "job-timeout") == "480", \
        "the job-timeout input's default is not the 480-minute backstop"
    entry = _workflow_input_entry(factory, "job-timeout")
    assert "type: string" in entry, \
        "the job-timeout input is not a string input"
    assert "required: false" in entry, \
        "the job-timeout input must be optional — an older " \
        "consumer's with: block stays schema-valid"
    lines = factory.splitlines()
    job_keys = ("trigger", "setup-pi", "baseline", "extract", "plan",
                "implement", "review", "pr", "gates", "report")
    starts = [i for i, ln in enumerate(lines)
              if ln.startswith("  ") and not ln.startswith("   ")
              and ln.strip() in {k + ":" for k in job_keys}]
    assert len(starts) == len(job_keys), \
        f"the factory's ten jobs are not all found in the workflow file: " \
        f"{len(starts)}"
    # the five stage jobs that make pi calls carry the target's value as
    # their job-level timeout-minutes — the entry is input-driven, not a
    # plain literal — while the jobs that stay factory-side (setup-pi,
    # and the jobs the delta leaves unchanged: baseline, gates, report)
    # keep plain literals; the trigger declares no job-level timeout
    for a, b in zip(starts, starts[1:] + [len(lines)]):
        name = lines[a].strip()[:-1]
        if name == "trigger":
            continue  # stage 1 declares no job-level timeout at all
        section = "\n".join(lines[a:b])
        # the job-level entry sits at 4-space indent (a step's entry
        # sits at 6)
        m = re.search(r"^    timeout-minutes: (.+?)\s*$", section, re.M)
        assert m is not None, \
            (f"the {name} stage job does not declare a job-level "
             f"timeout-minutes")
        value = m.group(1)
        if name in ("extract", "plan", "implement", "review", "pr"):
            assert value == "${{ inputs.job-timeout }}", \
                (f"the {name} job — a stage job that makes pi calls — "
                 f"carries {value!r} as its job-level timeout-minutes "
                 f"instead of the target's job-timeout input value")
        else:
            assert value.isdigit(), \
                (f"the {name} job's timeout-minutes value {value!r} is "
                 f"not a plain literal — the delta leaves this job's "
                 f"declaration unchanged")
    # the stage code still knows the 480-minute backstop through the
    # shared plumbing: the constant common.py resolves matches the
    # job-timeout input's default — the value an undeclared consumer's
    # jobs run under
    spec = importlib.util.spec_from_file_location(
        "cw_job_timeout_backstop_common",
        os.path.join(ROOT, ".github", "scripts", "common.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cw_job_timeout_backstop_common"] = mod
    try:
        spec.loader.exec_module(mod)
        assert mod.JOB_TIMEOUT_MINUTES == 480, \
            (f"the shared plumbing's JOB_TIMEOUT_MINUTES "
             f"({mod.JOB_TIMEOUT_MINUTES}) does not match the "
             f"job-timeout input's default (480) — the value an "
             f"undeclared consumer's jobs run under")
    finally:
        sys.modules.pop("cw_job_timeout_backstop_common", None)


def test_job_timeout_documentation_names_the_runner_that_enforces_it():
    """(configuration "The job timeout documentation names the runner
    that enforces it"; reference
    `requirements/configuration.feature::The job timeout documentation
    names the runner that enforces it`) the README's Inputs table — the
    target's documented surface — carries the job-timeout row with the
    480-minute default, and the row says the job timeout is enforced by
    whichever runner runs the job and that the target names that runner
    through the `runner` input (an existing row of the same table whose
    default is already documented there); the table's pi-timeout row no
    longer states the withdrawn clamp (a declared value longer than the
    stage jobs' job-level timeout backstop clamped to that backstop —
    the declared cap not honoured, the run recording the exceedance):
    with the validation moved to trigger time it states the trigger-time
    failure instead — a declared value that leaves the stage's non-call
    work no headroom fails the run at trigger, and a run that passes
    validation honours the declared value."""
    readme = _read("README.md")
    lines = readme.splitlines()
    # the Inputs table carries the job-timeout row with the 480-minute
    # default
    assert "| `job-timeout` | `480` |" in readme, \
        "the README's Inputs table has no job-timeout row"
    row = next((ln for ln in lines
                if ln.startswith("| `job-timeout` |")), None)
    assert row is not None, \
        "the README's Inputs table has no job-timeout row"
    # the row says the job timeout is enforced by whichever runner runs
    # the job
    assert "the job timeout is enforced by whichever runner runs the job" \
        in row, \
        ("the README's job-timeout row does not state that the job "
         "timeout is enforced by whichever runner runs the job")
    # and the target names that runner through the `runner` input
    assert "the target names that runner through the `runner` input" in row, \
        ("the README's job-timeout row does not name the `runner` input "
         "as the means the target names the runner that enforces the "
         "job timeout")
    # the pi-timeout row no longer states the withdrawn clamp: no
    # clamped-to-the-backstop, no not-honoured, no recorded-exceedance
    row = next((ln for ln in lines
                if ln.startswith("| `pi-timeout` |")), None)
    assert row is not None, \
        "the README's Inputs table has no pi-timeout row"
    for withdrawn in ("clamped", "not honoured", "exceedance"):
        assert withdrawn not in row, \
            (f"the README's pi-timeout row still states the withdrawn "
             f"clamp (its {withdrawn!r} clause)")
    # and it states the trigger-time failure the clamp's place took: a
    # declared value that leaves the stage's non-call work no headroom
    # fails the run at trigger, a run that passes validation honours the
    # declared value
    assert "leaves the stage's non-call work no headroom" in row, \
        ("the README's pi-timeout row does not name the headroom a "
         "declared value must leave the stage's non-call work")
    assert "fails the run at trigger" in row, \
        ("the README's pi-timeout row does not state that a declared "
         "value that leaves the stage's non-call work no headroom fails "
         "the run at trigger")
    assert "honours the declared value" in row, \
        ("the README's pi-timeout row does not state that a run that "
         "passes validation honours the declared value")


def test_dependency_upgrade_setting_is_configurable():
    """(configuration "The dependency-upgrade setting is configurable";
    reference
    `requirements/configuration.feature::The dependency-upgrade setting
    is configurable`) the setting's configuration-channel half rides the
    documented settings end-to-end: the reusable workflow declares
    dependency-upgrade on its input surface — a string input, optional
    (an older consumer's with: block stays schema-valid, the
    dependency-install input's pattern), default on — and the trigger's
    resolved-config log records it (the documented audit surface — the
    resolved configuration is recorded in the workflow log for audit,
    never committed to the repo): the on default names the value, and a
    target-declared off value records that the run's pipeline runs without
    the dependency-upgrade stage, the run's stages, pull request and
    final status report unchanged by the upgrade's absence. The
    setting's input → stage-environment relay and the pipeline step that
    skips itself where the setting is off — the scenario's pipeline half
    — land in the step that consumes the setting (the project-dependencies
    tests pin it); this test pins the declaration and the audit record."""
    factory = _read(".github/workflows/factory.yml")
    # the input surface declares the setting with its on default — a
    # string input, optional (an older consumer's with: block stays
    # schema-valid)
    assert _workflow_input_default(factory, "dependency-upgrade") == "on", \
        "the dependency-upgrade setting's default is on"
    entry = _workflow_input_entry(factory, "dependency-upgrade")
    assert "type: string" in entry, \
        "the dependency-upgrade input is not a string input"
    assert "required: false" in entry, \
        "the dependency-upgrade input must be optional — an older " \
        "consumer's with: block stays schema-valid"
    # the trigger's resolved-config log records the setting — the block is
    # the trigger's `{ … } | tee` group that writes the audit file
    trig = factory[factory.index("  trigger:"):factory.index("  setup-pi:")]
    heading = trig.index('echo "### Code Weaver — resolved configuration')
    assert heading != -1, "the trigger lost its resolved-config heading"
    start = trig.rfind("{", 0, heading)
    assert start != -1, \
        "the resolved-config group lost its opening brace"
    end = trig.find('} | tee -a "$RUNNER_TEMP/cw/resolved-config.txt"',
                    heading)
    assert end != -1, "the resolved-config group lost its `} | tee` close"
    block = trig[start:end]
    # the block branches on the setting's off value
    assert 'if [ "${{ inputs.dependency-upgrade }}" = "off" ]; then' in block, \
        "the resolved-config block does not branch on the off value"
    # a target-declared off value names the value and records that the
    # pipeline runs without the dependency-upgrade stage — the run's
    # stages, pull request and final status report unchanged by the
    # upgrade's absence
    off = [ln for ln in block.splitlines()
           if "echo" in ln and "dependency-upgrade" in ln
           and "runs without the dependency-upgrade stage" in ln]
    assert off, ("the resolved-config log has no off-value line for the "
                 "dependency-upgrade setting")
    # the value is backtick-quoted on the line, in the file's shell-escape
    # form (a backslash before each backtick, as on every other
    # resolved-config line)
    assert all("\\`off\\`" in ln for ln in off), \
        "the off-value line does not name the value it records"
    assert any("the run's stages, pull request and final status report" in ln
               and "unchanged" in ln for ln in off), \
        "the off-value line does not record the run as unchanged by the " \
        "upgrade's absence"
    # the on default names the setting's value (the on branch of the same
    # record)
    on = [ln for ln in block.splitlines()
          if "echo" in ln and "dependency-upgrade" in ln
          and "{{ inputs.dependency-upgrade }}" in ln]
    assert on, ("the resolved-config log does not name the setting's value "
                "for the on default")
    assert any("on by default" in ln for ln in on), \
        "the on-value line does not state the setting's on default"


def test_implement_guard_protects_requirements_and_other_plans():
    """(implement "implementation may only edit the current issue's
    plan"; reference
    `requirements/implement.feature::Implementation may only edit the
    current issue's plan`)
    the implement guard runs inverted-allow — the stage's DENY set is the
    protected set (requirements + plans dir, the guard's `!` entries) and
    its ALLOW set re-admits exactly the current issue's plan file plus
    `__pycache__`: another issue's plan file and a requirements file are
    violations the guard repairs with a pi call (no stage re-run; a
    requirements-dir edit does not loop back to the plan stage), while
    everything else is the implementation's lane — judged with the guard's
    own predicate (common.guard_denied)."""
    spec = importlib.util.spec_from_file_location(
        "cw_implement_stage",
        os.path.join(ROOT, ".github", "actions", "implement-stage", "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    spec_c = importlib.util.spec_from_file_location(
        "cw_common", os.path.join(ROOT, ".github", "scripts", "common.py"))
    common = importlib.util.module_from_spec(spec_c)
    sys.modules["cw_common"] = common  # the @dataclass GuardResult resolves its module
    spec_c.loader.exec_module(common)
    saved = {k: os.environ.get(k) for k in ("PLAN_DIR", "REQUIREMENTS_DIR")}
    os.environ["PLAN_DIR"] = "plans"
    os.environ["REQUIREMENTS_DIR"] = "requirements"
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        deny = mod.protected_dirs()
        assert "plans" in deny, "the plans dir is denied"
        assert "requirements" in deny, "the requirements dir is denied"
        # main()'s allow construction, replayed: the re-admissions over the
        # deny set are the current issue's plan file + pycache at any depth
        current = mod.current_plan_path("20", "plans")
        assert current == "plans/20.md"
        assert os.path.isfile(current), "this repo carries its own issue-20 plan"
        allow = ["__pycache__"]
        if current:
            allow.append(current)
        assert common.guard_denied(current, allow, deny) is False, \
            "the current issue's plan file must be admitted over the deny"
        assert common.guard_denied("plans/7.md", allow, deny), \
            "another issue's plan file must be off-limits"
        assert common.guard_denied("requirements/trigger.feature", allow, deny), \
            "the requirements dir stays off-limits"
        # the implementation's lane: everything else is admitted — the code
        # dirs, the tests the implementation has the job to implement
        # (including a `tests/` dir that did not exist at stage start), the
        # arc42 set, the README, and pycache the suite runs generate at any
        # depth (run 40735387017's iterations reverted these)
        for f in ("src/app.py", "tests/run.py", "tests/test_sync.py",
                  "tests/__pycache__/test_sync.cpython-313.pyc",
                  "docs/07-runtime-view.md", "README.md", "Makefile",
                  ".github/workflows/sync.yml"):
            assert not common.guard_denied(f, allow, deny), \
                f"{f} is the implementation's lane and must be admitted"
    finally:
        os.chdir(cwd)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# The fake `pi` both guard sandboxes put on PATH: it records each
# call's instructions to the state dir, performs the revert the
# instructions name when its mode says so ("revert" — every call;
# "revert-second" — the second call only; "noop" — never), and
# closes with a usage-carrying JSONL event stream (a message_end
# with input/output usage, then agent_settled) the way a real
# `pi --mode json` call's stdout reads. The revert restores the
# fixture's baseline-tree snapshot onto the named paths — the
# revert's file mechanics without a git child (the fake `pi` is a
# subprocess, and a subprocess cannot see the in-process mock).
_FAKE_PI = (
        "#!" + sys.executable + "\n"
        "import json, os, re, shutil, sys\n"
        "ins = sys.argv[-1]\n"
        "sd = os.path.join(os.environ['RUNNER_TEMP'], 'cw')\n"
        "os.makedirs(sd, exist_ok=True)\n"
        "with open(os.path.join(sd, 'fake-pi-call.txt'), 'a') as f:\n"
        "    f.write(ins + chr(10))\n"
        "cf = os.path.join(sd, 'fake-pi-count.txt')\n"
        "n = (int(open(cf).read().strip() or 0)\n"
        "      if os.path.exists(cf) else 0) + 1\n"
        "with open(cf, 'w') as f:\n"
        "    f.write(str(n))\n"
        "mode = os.environ.get('FAKE_PI_MODE', 'noop')\n"
        "if mode == 'revert' or (mode == 'revert-second' and n >= 2):\n"
        "    ws = os.environ['GITHUB_WORKSPACE']\n"
        "    snap_root = os.path.join(sd, 'baseline-tree')\n"
        "    for fm in re.finditer(r'  - (\\S+)', ins):\n"
        "        p = fm.group(1)\n"
        "        full = os.path.join(ws, p)\n"
        "        snap = os.path.join(snap_root, p)\n"
        "        if os.path.exists(snap):\n"
        "            if os.path.isdir(snap):\n"
        "                shutil.rmtree(full, ignore_errors=True)\n"
        "                shutil.copytree(snap, full)\n"
        "            else:\n"
        "                os.makedirs(os.path.dirname(full) or '.',\n"
        "                            exist_ok=True)\n"
        "                shutil.copyfile(snap, full)\n"
        "        elif os.path.isdir(full):\n"
        "            shutil.rmtree(full)\n"
        "        elif os.path.exists(full):\n"
        "            os.remove(full)\n"
        "print(json.dumps({'type': 'message_end', 'message': {\n"
        "    'role': 'assistant',\n"
        "    'content': 'the named files are reverted',\n"
        "    'usage': {'input': 11, 'output': 7}}}))\n"
        "print(json.dumps({'type': 'agent_settled'}))\n"
)


def _guard_repair_sandbox(allow, deny, mode, max_loops,
                          stage="stage 6 planning", template="plan",
                          leak=True):
    """A sandbox that exercises the shared guard's repair loop end to end:
    a temp workspace the sandbox's fake model tracks as a git repo (a
    committed baseline — a requirements feature file, the issue's plan
    file, a src file), the scenario's leak (an off-limits edit in the
    requirements dir) applied to the working tree on top of the
    stage's own allowed work, and a fake `pi` on
    PATH that records each call's instructions to the state dir and
    performs the revert they name when its mode says so ("revert" — every
    call; "revert-second" — the second call only; "noop" — never). The
    canonical guard (common.guard, imported in-process) then runs its real
    detection + repair loop against the fake baseline and working tree
    with no model in the middle and no git process spawned (the guard's
    git traffic rides the mocked single entry point). Returns a namespace:
    repo (the repo dir), rt (the state-dir root), baseline (the baseline
    sha), mod (the common module), result (the guard's GuardResult — None
    when the guard exited the stage instead), exit_code (the SystemExit
    the guard raised), calls (the recorded repair-call instructions),
    fail_reason (the failure report the guard wrote to the state dir, if
    any) and cleanup (restore the env, the git-exec mock and remove the
    temp dirs)."""
    import shutil
    import tempfile
    repo = tempfile.mkdtemp(prefix="cw-guard-repo-")
    rt = tempfile.mkdtemp(prefix="cw-guard-rt-")
    fake = tempfile.mkdtemp(prefix="cw-guard-fake-")
    os.makedirs(os.path.join(repo, "requirements"))
    os.makedirs(os.path.join(repo, "plans"))
    os.makedirs(os.path.join(repo, "src"))
    with open(os.path.join(repo, "requirements", "guard-rail.feature"), "w") as f:
        f.write("Feature: baseline\n  Scenario: the baseline scenario\n"
                "    Given the baseline tree\n")
    with open(os.path.join(repo, "plans", "69.md"), "w") as f:
        f.write("# Issue 69\n- [ ] a step\n")
    with open(os.path.join(repo, "src", "app.py"), "w") as f:
        f.write("print('baseline')\n")

    ws_fake = _FakeRepo(repo)
    repo_key = os.path.realpath(repo)
    _FAKE_REPOS[repo_key] = ws_fake
    ws_fake.exec(["init", "-q"])
    ws_fake.exec(["add", "-A"])
    ws_fake.exec(["commit", "-q", "-m", "baseline"])
    baseline = ws_fake.exec(["rev-parse", "HEAD"]).stdout.strip()
    assert baseline, "the sandbox's fake baseline commit failed"
    # the fake `pi`'s revert restores this snapshot of the baseline tree
    _write_baseline_snapshot(ws_fake, rt)

    # the stage's own work (an allowed change to the plan file) plus — when
    # the scenario asks for the leak — an off-limits edit in the
    # requirements dir
    with open(os.path.join(repo, "plans", "69.md"), "a") as f:
        f.write("- [x] a step\n")
    if leak:
        with open(os.path.join(repo, "requirements", "guard-rail.feature"),
                  "a") as f:
            f.write("  Scenario: a leak\n"
                    "    Given the stage edited the oracle\n")

    os.makedirs(os.path.join(fake, "bin"))
    with open(os.path.join(fake, "bin", "pi"), "w") as f:
        f.write(_FAKE_PI)
    os.chmod(os.path.join(fake, "bin", "pi"), 0o755)

    keys = ("GITHUB_WORKSPACE", "RUNNER_TEMP", "LLM_MODEL", "MAX_LOOPS",
            "PATH", "FAKE_PI_MODE")
    saved = {k: os.environ.get(k) for k in keys}
    os.environ.update({
        "GITHUB_WORKSPACE": repo,
        "RUNNER_TEMP": rt,
        "LLM_MODEL": "fake-model",
        "MAX_LOOPS": str(max_loops),
        "PATH": os.path.join(fake, "bin") + os.pathsep + (saved["PATH"] or ""),
        "FAKE_PI_MODE": mode,
    })

    spec = importlib.util.spec_from_file_location(
        "cw_common_guard_sandbox",
        os.path.join(ROOT, ".github", "scripts", "common.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cw_common_guard_sandbox"] = mod
    spec.loader.exec_module(mod)
    # the guard's git traffic (the detection's diff + ls-files, the repair
    # commit) rides the mocked single entry point — the fake model
    restore_git = _patch_git_exec()

    ns = {"repo": repo, "rt": rt, "fake": fake, "baseline": baseline,
          "mod": mod, "result": None, "exit_code": None, "calls": "",
          "fail_reason": None}
    try:
        ns["result"] = mod.guard(baseline, allow, deny,
                                 stage=stage, template=template)
    except SystemExit as e:
        ns["exit_code"] = e.code
    try:
        ns["calls"] = open(os.path.join(rt, "cw", "fake-pi-call.txt")).read()
    except OSError:
        pass
    try:
        ns["fail_reason"] = open(
            os.path.join(rt, "cw", "stage-fail-reason.txt"),
            encoding="utf-8").read()
    except OSError:
        pass

    def cleanup():
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        restore_git()
        sys.modules.pop("cw_common_guard_sandbox", None)
        _FAKE_REPOS.pop(repo_key, None)
        for d in (repo, rt, fake):
            shutil.rmtree(d, ignore_errors=True)
    ns["cleanup"] = cleanup
    return ns


def test_guard_repairs_a_violation_with_a_pi_call():
    """(guard-rail "a leaking stage is repaired by a pi call, not
    restarted", "guard repairs are capped"; reference
    `requirements/guard-rail.feature::A leaking stage is repaired by a
    pi call, not restarted`,
    `requirements/guard-rail.feature::Guard repairs are capped`,
    `requirements/cost-and-token-usage.feature::The usage totals cover
    every pi call the run made`,
    `requirements/plan.feature::The plan stage may only touch its own
    plan file`) an off-limits change in the
    working tree makes the shared guard call pi — its instructions name
    the off-limits files, instruct pi to revert the changes to the named
    files, and instruct pi to keep the stage's own work valid against the
    task its initial instructions gave it; a clean re-check after the
    repair returns a passing result — the guard records the cleared
    repair in the state dir: the extract and implement stages complete
    without re-running their generation, the plan stage re-runs on it
    (plan "the plan stage may only touch its own plan file"); the allowed
    changes stay intact, the off-limits file is reverted in place; the
    repair calls ride the
    documented shared pi-call plumbing — each finished call appends its
    usage to the run's ledger (cost-and-token-usage "the usage totals
    cover every pi call the run made"); the repair loop is bounded by
    MAX_LOOPS (0 = no cap — a cap of 2 stops the loop after two repair
    calls, a 0 cap lets the same calls run to the clearing one), and a
    cap exhausted without clearing the violation fails the stage with a
    failure report listing the violations."""
    # a violation the repair clears on its first call
    ns = _guard_repair_sandbox(["plans"], [], "revert", "3")
    try:
        assert ns["exit_code"] is None, \
            ("a cleared repair completes the stage — the guard did not "
             f"exit the stage: {ns['exit_code']!r}")
        assert ns["result"].ok, \
            "a clean re-check after the repair lets the stage pass"
        # the guard called pi to repair the violation — one call cleared
        # it; the stage was not reverted and re-run
        n_calls = ns["calls"].count("You are repairing a guard violation")
        assert n_calls == 1, \
            f"one repair call cleared the violation — no re-run: {n_calls}"
        # the call names the off-limits file that changed
        assert "requirements/guard-rail.feature" in ns["calls"], \
            "the repair call's instructions name the off-limits file"
        # ... instruct pi to revert the changes to the named files
        assert "Revert the changes to the named files" in ns["calls"]
        assert ns["baseline"] in ns["calls"], \
            "the revert is to the stage's baseline"
        # ... and to keep the stage's own work valid against the task its
        # initial instructions gave it
        assert "Keep the stage's own work valid against the task its " \
            "initial instructions gave it" in ns["calls"]
        assert "pi-prompts/plan.md" in ns["calls"], \
            "the stage's initial instructions are its prompt template"
        # the off-limits file is reverted in place; the stage's own work
        # (an allowed change) stays intact
        feat = open(os.path.join(ns["repo"], "requirements",
                                 "guard-rail.feature")).read()
        assert "a leak" not in feat, \
            "the off-limits change is reverted in place"
        plan = open(os.path.join(ns["repo"], "plans", "69.md")).read()
        assert "- [x] a step" in plan, \
            "the allowed changes stay intact"
        # the finished repair call appends its usage to the run's ledger
        # (the new call kind rides the documented pi-call machinery)
        ledger = open(os.path.join(ns["rt"], "cw", "tokens.txt"),
                      encoding="utf-8").read()
        assert "11 7" in ledger, \
            f"each finished call appends its usage to the ledger: {ledger!r}"
    finally:
        ns["cleanup"]()
    # a cap exhausted without clearing the violation fails the stage with a
    # failure report listing the violations
    ns2 = _guard_repair_sandbox(["plans"], [], "noop", "2")
    try:
        assert ns2["exit_code"] == 1, \
            "a cap exhausted without clearing the violation fails the stage"
        n_calls = ns2["calls"].count("You are repairing a guard violation")
        assert n_calls == 2, \
            f"the guard's repair call runs MAX_LOOPS (2) times: {n_calls}"
        assert ns2["fail_reason"] is not None, \
            "the stage fails with a failure report"
        assert "requirements/guard-rail.feature" in ns2["fail_reason"], \
            "the failure report lists the violations (the named off-limits files)"
    finally:
        ns2["cleanup"]()
    # MAX_LOOPS 0 = no cap: the loop runs past a small count to the call
    # that clears the violation
    ns3 = _guard_repair_sandbox(["plans"], [], "revert-second", "0")
    try:
        assert ns3["exit_code"] is None and ns3["result"].ok, \
            "a cap of 0 is no cap — the repair loop runs to the clearing call"
        n_calls = ns3["calls"].count("You are repairing a guard violation")
        assert n_calls == 2, \
            f"the clearing call was the second one: {n_calls}"
        feat = open(os.path.join(ns3["repo"], "requirements",
                                 "guard-rail.feature")).read()
        assert "a leak" not in feat, \
            "the second repair call cleared the violation"
    finally:
        ns3["cleanup"]()


def _guard_fallback_sandbox(allow, deny, mode, max_loops,
                            stage="stage 6 planning", template="plan"):
    """The fallback-form twin of _guard_repair_sandbox: the same temp
    workspace (the sandbox's fake model tracks it as a git repo — a
    committed baseline, the stage's own allowed work, the off-limits
    leak) and the same fake `pi` on PATH, but the guard runs as the
    SELF-CONTAINED fallback — the guard-check.py entry script laid out
    where the sibling scripts/ dir is absent (the degenerate sparse
    checkout the fallback exists for), driven in-process against the
    mocked single git entry point: its _load() finds no canonical
    common.py and defines the inline fallback, and the process boundary
    a subprocess form would carry is exactly what the mock exists to
    remove — a test never spawns the real git binary. Returns a
    namespace: repo (the repo dir), rt (the state-dir root), baseline,
    returncode (the guard CLI's exit), out (its captured stdout — the
    narrative run_guard relays), err, and cleanup (restore the env, the
    git-exec mock and remove the temp dirs)."""
    import shutil
    import tempfile
    repo = tempfile.mkdtemp(prefix="cw-guardfb-repo-")
    rt = tempfile.mkdtemp(prefix="cw-guardfb-rt-")
    fake = tempfile.mkdtemp(prefix="cw-guardfb-fake-")
    tree = tempfile.mkdtemp(prefix="cw-guardfb-tree-")
    os.makedirs(os.path.join(repo, "requirements"))
    os.makedirs(os.path.join(repo, "plans"))
    os.makedirs(os.path.join(repo, "src"))
    with open(os.path.join(repo, "requirements", "guard-rail.feature"),
              "w") as f:
        f.write("Feature: baseline\n  Scenario: the baseline scenario\n"
                "    Given the baseline tree\n")
    with open(os.path.join(repo, "plans", "69.md"), "w") as f:
        f.write("# Issue 69\n- [ ] a step\n")
    with open(os.path.join(repo, "src", "app.py"), "w") as f:
        f.write("print('baseline')\n")

    ws_fake = _FakeRepo(repo)
    repo_key = os.path.realpath(repo)
    _FAKE_REPOS[repo_key] = ws_fake
    ws_fake.exec(["init", "-q"])
    ws_fake.exec(["add", "-A"])
    ws_fake.exec(["commit", "-q", "-m", "baseline"])
    baseline = ws_fake.exec(["rev-parse", "HEAD"]).stdout.strip()
    assert baseline, "the sandbox's fake baseline commit failed"
    # the fake `pi`'s revert restores this snapshot of the baseline tree
    _write_baseline_snapshot(ws_fake, rt)

    # the stage's own work (an allowed change to the plan file) plus the
    # scenario's leak (an off-limits edit in the requirements dir)
    with open(os.path.join(repo, "plans", "69.md"), "a") as f:
        f.write("- [x] a step\n")
    with open(os.path.join(repo, "requirements", "guard-rail.feature"),
              "a") as f:
        f.write("  Scenario: a leak\n"
                "    Given the stage edited the oracle\n")

    os.makedirs(os.path.join(fake, "bin"))
    with open(os.path.join(fake, "bin", "pi"), "w") as f:
        f.write(_FAKE_PI)
    os.chmod(os.path.join(fake, "bin", "pi"), 0o755)

    # the fallback is the self-contained guard: a copy of the entry script
    # laid out where the sibling scripts/ dir is absent (its _load() finds
    # no canonical common.py and defines the inline fallback)
    os.makedirs(os.path.join(tree, "guard-check"))
    shutil.copy(os.path.join(ROOT, ".github", "actions", "guard-check",
                             "guard-check.py"),
                os.path.join(tree, "guard-check", "guard-check.py"))

    keys = ("GITHUB_WORKSPACE", "RUNNER_TEMP", "LLM_MODEL", "MAX_LOOPS",
            "PATH", "FAKE_PI_MODE")
    saved = {k: os.environ.get(k) for k in keys}
    os.environ.update({
        "GITHUB_WORKSPACE": repo,
        "RUNNER_TEMP": rt,
        "LLM_MODEL": "fake-model",
        "MAX_LOOPS": str(max_loops),
        "PATH": os.path.join(fake, "bin") + os.pathsep + (saved["PATH"] or ""),
        "FAKE_PI_MODE": mode,
    })

    # the entry script runs in-process against the mocked single git entry
    # point: the tree copy has no sibling scripts dir, so its _load() takes
    # the fallback branch — the code path a `python3 guard-check.py`
    # subprocess would run, minus the process boundary the mock removes
    spec = importlib.util.spec_from_file_location(
        "cw_guardcheck_fallback",
        os.path.join(tree, "guard-check", "guard-check.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cw_guardcheck_fallback"] = mod
    spec.loader.exec_module(mod)
    restore_git = _patch_git_exec()
    argv_saved = sys.argv
    sys.argv = [os.path.join(tree, "guard-check", "guard-check.py"),
                baseline, *allow]
    if deny:
        sys.argv += ["!", *deny]
    exit_code = None
    try:
        mod._load()()
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else (
            0 if e.code is None else 1)
    finally:
        sys.argv = argv_saved
    ns = {"repo": repo, "rt": rt, "fake": fake, "ws_fake": ws_fake,
          "tree": tree,
          "baseline": baseline,
          "returncode": exit_code if exit_code is not None else 0,
          "out": "", "err": ""}

    def cleanup():
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        restore_git()
        sys.modules.pop("cw_guardcheck_fallback", None)
        _FAKE_REPOS.pop(repo_key, None)
        for d in (repo, rt, fake, tree):
            shutil.rmtree(d, ignore_errors=True)
    ns["cleanup"] = cleanup
    return ns


def test_guard_fallback_matches_the_canonical_repair():
    """(guard-rail "All three checks share one implementation" — one
    script, three call sites, the self-contained fallback included;
    "A leaking stage is repaired by a pi call, not restarted";
    reference
    `requirements/guard-rail.feature::All three checks share one
    implementation`,
    `requirements/guard-rail.feature::A leaking stage is repaired by a
    pi call, not restarted`,
    `requirements/cost-and-token-usage.feature::The usage totals cover
    every pi call the run made`) the fallback the guard entry script
    falls back to when the sibling scripts/ dir is absent (the
    degenerate sparse checkout the fallback exists for) keeps the
    canonical guard's semantics end to end: the same detection, the
    same bounded repair loop through a pi call, a cleared re-check
    passing the stage without re-running its generation — and the
    cleared repair's bookkeeping stays whole: the reverts are committed
    so they ride the branch, the state-dir record names the files the
    call reverted, and each finished repair call appends its usage to
    the run's token ledger (cost-and-token-usage "The usage totals
    cover every pi call the run made")."""
    import subprocess
    ns = _guard_fallback_sandbox(["plans"], [], "revert", "3")
    try:
        assert ns["returncode"] == 0, \
            (f"a cleared repair passes the guard (exit 0): exit "
             f"{ns['returncode']}, stderr: {ns['err']!r}")
        # the off-limits file is reverted in place; the stage's own work
        # (an allowed change) stays intact
        feat = open(os.path.join(ns["repo"], "requirements",
                                 "guard-rail.feature")).read()
        assert "a leak" not in feat, \
            "the off-limits change is reverted in place"
        plan = open(os.path.join(ns["repo"], "plans", "69.md")).read()
        assert "- [x] a step" in plan, \
            "the allowed changes stay intact"

        def show(ref, path):
            r = ns["ws_fake"].exec(["show", f"{ref}:{path}"])
            return r.stdout if r.returncode == 0 else None

        # the reverts are committed to the branch — the off-limits file
        # rides at its baseline content (a later stage's guard would
        # otherwise re-flag it against the stage baseline), and the
        # stage's own allowed work rides with them
        assert show("HEAD", "requirements/guard-rail.feature") == \
            show(ns["baseline"], "requirements/guard-rail.feature"), \
            "the cleared repair's reverts are committed to the branch"
        assert "- [x] a step" in (show("HEAD", "plans/69.md") or ""), \
            "the stage's own work is committed alongside the reverts"
        # the cleared-repair record names the files the call reverted
        record = open(os.path.join(ns["rt"], "cw",
                                   "stage-guard-repaired.txt"),
                      encoding="utf-8").read()
        assert "requirements/guard-rail.feature" in record, \
            f"the record names the cleared files: {record!r}"
        # the finished repair call appends its usage to the run's ledger
        ledger = open(os.path.join(ns["rt"], "cw", "tokens.txt"),
                      encoding="utf-8").read()
        assert "11 7" in ledger, \
            f"each finished call appends its usage to the ledger: {ledger!r}"
    finally:
        ns["cleanup"]()


def test_plan_stage_may_only_touch_its_own_plan_file():
    """(plan "the plan stage may only touch its own plan file"; reference
    `requirements/plan.feature::The plan stage may only touch its own
    plan file`,
    `requirements/guard-rail.feature::All three checks share one
    implementation`,
    `requirements/guard-rail.feature::A leaking stage is repaired by a
    pi call, not restarted`,
    `requirements/guard-rail.feature::A requirement edited during
    implementation is reverted in place`) when the plan stage wrote a
    change outside its one allowed plan file, the plan-check (the shared
    guard — one implementation, three call sites) reverts it with the
    shared remedy — the guard's pi call, the off-limits file named, told
    to be reverted, the plan told to stay valid — and the plan stage
    re-runs: the guard records the cleared repair in the state dir
    (stage-guard-repaired.txt), the plan stage's loop machinery claims
    the record and re-runs the generation, the guard re-checking the
    re-run — only the plan file is left changed. A clean plan stage
    writes no record and completes without re-running, and the extract
    and implement checks' machinery never claims the record — their
    stages complete without re-running, while all three checks share the
    one guard implementation."""
    # a leak at the plan check: the shared guard repairs it with a pi
    # call and records the cleared repair in the state dir — the record
    # the plan stage's loop machinery claims to re-run the generation
    ns = _guard_repair_sandbox(["plans/69.md"], [], "revert", "3")
    try:
        assert ns["exit_code"] is None and ns["result"].ok, \
            "a cleared repair lets the plan check pass"
        assert "You are repairing a guard violation" in ns["calls"], \
            "the guard repairs the violation with a pi call (the shared remedy)"
        assert "requirements/guard-rail.feature" in ns["calls"], \
            "the repair call names the off-limits file"
        feat = open(os.path.join(ns["repo"], "requirements",
                                 "guard-rail.feature")).read()
        assert "a leak" not in feat, \
            "any other change is reverted"
        plan = open(os.path.join(ns["repo"], "plans", "69.md")).read()
        assert "- [x] a step" in plan, \
            "the plan file (the stage's own work) stays intact"
        marker = os.path.join(ns["rt"], "cw", "stage-guard-repaired.txt")
        assert os.path.exists(marker), \
            "the guard records the cleared repair in the state dir"
        assert "requirements/guard-rail.feature" in open(marker).read(), \
            "the record names the reverted off-limits file"
    finally:
        ns["cleanup"]()
    # the plan stage's machinery claims the record and re-runs the
    # generation; the extract and implement stages' machinery never
    # claims it (their stages complete without re-running)
    plan_stage = _read(".github/actions/plan-stage/stage.py")
    assert "rerun_on_repair=True" in plan_stage, \
        "the plan stage re-runs its generation on the guard's cleared repair"
    assert "rerun_on_repair" not in _read(
        ".github/actions/extract-stage/stage.py"), \
        "the extract check keeps the repair-without-re-run form"
    assert "rerun_on_repair" not in _read(
        ".github/actions/implement-stage/stage.py"), \
        "the implement check keeps the repair-without-re-run form"
    stages = _read(".github/scripts/stages.py")
    assert "rerun_on_repair" in stages, \
        "the loop machinery carries the claim of the guard's cleared-repair record"
    assert "stage-guard-repaired" in stages, \
        "the loop machinery claims the record and re-runs the generation"
    assert "stage-guard-repaired" in _read(".github/scripts/common.py"), \
        "the shared guard writes the record the plan stage's machinery claims"
    # a clean plan stage: no violation, no repair call, no record — the
    # stage completes without re-running
    ns2 = _guard_repair_sandbox(["plans/69.md"], [], "revert", "3",
                                leak=False)
    try:
        assert ns2["exit_code"] is None and ns2["result"].ok, \
            "a clean plan stage passes the guard"
        assert ns2["calls"] == "", \
            "a clean stage makes no repair call"
        assert not os.path.exists(
            os.path.join(ns2["rt"], "cw", "stage-guard-repaired.txt")), \
            "a clean stage writes no repair record — no re-run"
    finally:
        ns2["cleanup"]()


def test_implement_stage_has_no_plan_loop_back():
    """(guard-rail "a requirement edited during implementation is reverted
    in place", implement "implementation must not edit requirements";
    reference
    `requirements/guard-rail.feature::A requirement edited during
    implementation is reverted in place`,
    `requirements/implement.feature::Implementation must not edit
    requirements`) a requirements-dir violation at the implement check is
    repaired in place
    by the shared guard's pi call — the implement stage's violation hook no
    longer regenerates the plan and no loop back to the plan stage exists
    (the hook is gone from the stage and from the shared loop machinery's
    signature; the stage docstring and the implement prompt's hard rule are
    reworded to the repair-in-place form). The inverted-allow detection
    shape is unchanged — a requirements-dir edit is still a violation; only
    the remedy is the repair call, and the plan file is left byte-identical
    (nothing regenerates it)."""
    stage = _read(".github/actions/implement-stage/stage.py")
    assert "plan_loop_back" not in stage, \
        "the implement stage's loop-back hook is removed — a requirements-dir violation is repaired in place"
    assert "on_violation" not in stage, \
        "the stage no longer hands a violation to a loop-back hook"
    assert "loops back to the plan stage" not in stage, \
        "the module docstring's loop-back sentences are reworded to the repair-in-place form"
    stages = _read(".github/scripts/stages.py")
    assert "on_violation" not in stages, \
        "the shared loop machinery carries no loop-back hook any more"
    prompt = _read("pi-prompts/implement.md")
    assert "loops back to planning" not in prompt, \
        "the implement prompt's hard rule is reworded to the repair-in-place form"
    assert "reverted in place" in prompt and \
        "guard's pi repair call" in prompt, \
        "the hard rule names the guard's pi repair call as the remedy"
    # behaviour: the implement guard's inverted-allow shape (deny =
    # {requirements, plans}; the current issue's plan file re-allowed) with
    # a requirements-dir violation — repaired in place by the same shared
    # guard, no plan regeneration
    ns = _guard_repair_sandbox(
        ["plans/69.md", "__pycache__"], ["requirements", "plans"],
        "revert", "3",
        stage="stage 8 implementation", template="implement")
    try:
        assert ns["exit_code"] is None and ns["result"].ok, \
            "a requirements-dir violation at the implement check is repaired in place"
        plan = open(os.path.join(ns["repo"], "plans", "69.md")).read()
        assert plan == "# Issue 69\n- [ ] a step\n- [x] a step\n", \
            "the plan file is not regenerated — no loop back to the plan stage"
        feat = open(os.path.join(ns["repo"], "requirements",
                                 "guard-rail.feature")).read()
        assert "a leak" not in feat, \
            "the guard calls pi with the changed file named to revert the edit"
        assert "requirements/guard-rail.feature" in ns["calls"], \
            "the repair call's instructions name the changed file"
        assert "pi-prompts/implement.md" in ns["calls"], \
            "the call keeps the stage's own work valid against the task its initial instructions gave it"
    finally:
        ns["cleanup"]()


# The fake `pi` the implement-stage sandbox puts on PATH: it plays the
# implementer's one-step-per-call contract — it works the plan file named
# in the target instructions (the prompt's "open exactly this plan file"
# fence, or the plan's `@`-argument where the call injects it), flipping
# the plan's first open `- [ ]` step to `- [x]` (one step per invocation,
# the template's work-one-open-step rule), and closes with a
# usage-carrying JSONL event stream (a message_end with input/output
# usage, then agent_settled) the way a real `pi --mode json` call's stdout
# reads. Where the sandbox names the events file (the FAKE_PI_EVENTS env
# entry), it also appends its own invocation line to that file — the same
# file the sandbox's fake git model appends to for every git call it
# handles — so the sandbox's test reads one ordered sequence interleaving
# the stage's pi calls with its git calls (the per-step push lands in
# that sequence between the step's commit and the next step's call).
_FAKE_PI_IMPLEMENT = (
        "#!" + sys.executable + "\n"
        "import json, os, re, sys\n"
        "ws = os.environ['GITHUB_WORKSPACE']\n"
        "sd = os.path.join(os.environ['RUNNER_TEMP'], 'cw')\n"
        "os.makedirs(sd, exist_ok=True)\n"
        "cf = os.path.join(sd, 'fake-pi-count.txt')\n"
        "n = (int(open(cf).read().strip() or 0)\n"
        "      if os.path.exists(cf) else 0) + 1\n"
        "with open(cf, 'w') as f:\n"
        "    f.write(str(n))\n"
        "ef = os.environ.get('FAKE_PI_EVENTS')\n"
        "if ef:\n"
        "    d = os.path.dirname(ef)\n"
        "    if d:\n"
        "        os.makedirs(d, exist_ok=True)\n"
        "    with open(ef, 'a') as f:\n"
        "        f.write('pi\\n')\n"
        "arg = sys.argv[-1]\n"
        "plan_rel = arg[1:] if arg.startswith('@') else None\n"
        "if plan_rel is None:\n"
        "    m = re.search(r'```\\n\\s*(plans/[\\w.-]+\\.md)\\n\\s*```', arg)\n"
        "    if m:\n"
        "        plan_rel = m.group(1)\n"
        "if plan_rel is not None:\n"
        "    plan = os.path.join(ws, plan_rel)\n"
        "    if os.path.isfile(plan):\n"
        "        lines = open(plan, encoding='utf-8').read().splitlines()\n"
        "        for i, l in enumerate(lines):\n"
        "            if re.match(r'^\\s*-\\s*\\[\\s*\\]\\s*', l):\n"
        "                lines[i] = l.replace('- [ ]', '- [x]', 1)\n"
        "                break\n"
        "        open(plan, 'w', encoding='utf-8').write('\\n'.join(lines) + '\\n')\n"
        "print(json.dumps({'type': 'message_end', 'message': {\n"
        "    'role': 'assistant',\n"
        "    'content': 'one open plan step implemented and marked done',\n"
        "    'usage': {'input': 5, 'output': 3}}}))\n"
        "print(json.dumps({'type': 'agent_settled'}))\n"
)


def _implement_stage_sandbox(plan_text):
    """Run the implement stage against a sandboxed plan file: a temp
    workspace (GITHUB_WORKSPACE) the sandbox's fake model tracks as a git
    repo, whose plan file holds the given checklist, a
    temp RUNNER_TEMP state dir (the trigger's issue-number state file, the
    baseline's sha under both the run's and the stage's baseline state
    names), and the fake implementer `pi` on PATH. The stage's real
    generation loop, guard call and completion logging run un-faked (the
    stage's git traffic rides the mocked single entry point — no git
    process is spawned). The
    stage's own log is the mirror every common.log line lands in
    (stage-console.log in the state dir — the runner's job log is a ghost
    on this build). Returns a namespace: repo, rt, mod (the implement
    stage module), baseline, and cleanup (restore the env, the git-exec
    mock and the sys.modules entries, and remove the temp dirs)."""
    import shutil
    import tempfile
    repo = tempfile.mkdtemp(prefix="cw-implement-ws-")
    rt = tempfile.mkdtemp(prefix="cw-implement-rt-")
    fake = tempfile.mkdtemp(prefix="cw-implement-fake-")
    os.makedirs(os.path.join(repo, "plans"))
    with open(os.path.join(repo, "plans", "74.md"), "w", encoding="utf-8") as f:
        f.write(plan_text)
    ws_fake = _FakeRepo(repo)
    repo_key = os.path.realpath(repo)
    _FAKE_REPOS[repo_key] = ws_fake
    ws_fake.exec(["init", "-q"])
    ws_fake.exec(["add", "-A"])
    ws_fake.exec(["commit", "-qm", "baseline"])
    baseline = ws_fake.exec(["rev-parse", "HEAD"]).stdout.strip()
    assert baseline, "the sandbox's fake baseline commit failed"
    cw = os.path.join(rt, "cw")
    os.makedirs(os.path.join(cw, "state", "trigger"))
    with open(os.path.join(cw, "baseline.sha"), "w") as f:
        f.write(baseline + "\n")
    with open(os.path.join(cw, "stage-baseline.sha"), "w") as f:
        f.write(baseline + "\n")
    with open(os.path.join(cw, "state", "trigger", "issue-number.txt"),
              "w") as f:
        f.write("74\n")
    os.makedirs(os.path.join(fake, "bin"))
    with open(os.path.join(fake, "bin", "pi"), "w") as f:
        f.write(_FAKE_PI_IMPLEMENT)
    os.chmod(os.path.join(fake, "bin", "pi"), 0o755)
    keys = ("GITHUB_WORKSPACE", "RUNNER_TEMP", "LLM_MODEL", "MAX_LOOPS",
            "PATH", "PLAN_DIR", "REQUIREMENTS_DIR", "DOC_DIR",
            "BASELINE_REF", "CW_ISSUE_NUMBER", "INPUT_ISSUE_NUMBER")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "GITHUB_WORKSPACE": repo,
        "RUNNER_TEMP": rt,
        "LLM_MODEL": "fake-model",
        "MAX_LOOPS": "5",
        "PATH": os.path.join(fake, "bin") + os.pathsep + (saved["PATH"] or ""),
        "PLAN_DIR": "plans",
        "REQUIREMENTS_DIR": "requirements",
    })
    saved_mods = {k: sys.modules.get(k) for k in ("common", "stages")}
    spec = importlib.util.spec_from_file_location(
        "cw_implement_stage_sandbox",
        os.path.join(ROOT, ".github", "actions", "implement-stage",
                     "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cw_implement_stage_sandbox"] = mod
    spec.loader.exec_module(mod)
    # the stage's git traffic (guard detection, the stage's own commit)
    # rides the mocked single entry point — the fake model
    restore_git = _patch_git_exec()

    def cleanup():
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for k, v in saved_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        sys.modules.pop("cw_implement_stage_sandbox", None)
        restore_git()
        _FAKE_REPOS.pop(repo_key, None)
        for d in (repo, rt, fake):
            shutil.rmtree(d, ignore_errors=True)

    return {"repo": repo, "rt": rt, "mod": mod, "baseline": baseline,
            "cleanup": cleanup}


def test_implement_logs_per_step_line_on_clean_call():
    """(implement "A clean call with steps still open logs the per-step
    line, not a stage completion" — new scenario; reference
    `requirements/implement.feature::A clean call with steps still open
    logs the per-step line, not a stage completion`) the plan file has
    open (`- [ ]`) and done (`- [x]`) steps, and a clean generation call
    inside the implement stage has just marked a step done (one step per
    invocation — the sandbox's fake `pi` flips the plan's first open
    checkbox): the implement stage logs the per-step line, "stage 8
    implementation: clean — step <done>/<total> of the plan done;
    <remaining> step(s) remain", with done, total and remaining counted
    from the plan file's checkboxes (the sandbox plan holds one done step
    and two open ones — the call leaves 2 of 3 done, 1 remaining), and no
    "stage complete" is printed by the stage while any step of its plan
    remains open — every stage-complete line in the stage's log is the
    full-step-count exit line, which lands only after the per-step line,
    once the loop's exit check finds no open step left. The shared
    generation loop carries the hook the per-step line rides — its plain
    completion form is not what the implement caller gets."""
    ns = _implement_stage_sandbox(
        "# Issue 74\n\n## Steps\n\n"
        "- [x] a done step\n"
        "- [ ] an open step one\n"
        "- [ ] an open step two\n")
    hook, cwd = sys.excepthook, os.getcwd()
    os.chdir(ns["repo"])
    try:
        ns["mod"].main()
        console = open(os.path.join(ns["rt"], "cw", "stage-console.log"),
                       encoding="utf-8").read()
        lines = [l for l in console.splitlines() if l.strip()]
        per_step = ("stage 8 implementation: clean — step 2/3 of the plan "
                    "done; 1 step(s) remain")
        all_done = ("stage 8 implementation: all 3 plan steps done — "
                    "stage complete")
        # the clean call that marked a step done logs the per-step line —
        # done, total and remaining counted from the plan file's checkboxes
        assert per_step in lines, console
        # …and no "stage complete" while any step of the plan remains open:
        # every stage-complete line the stage prints is the full-count exit
        # line, and it lands only after the per-step line
        assert all_done in lines, console
        assert lines.index(per_step) < lines.index(all_done)
        for l in lines:
            if "stage complete" in l:
                assert l == all_done, \
                    f"a stage-complete line while a step may still be open: {l!r}"
        # the loop kept working open steps until the plan was fully tracked
        plan = open(os.path.join(ns["repo"], "plans", "74.md"),
                    encoding="utf-8").read()
        assert "- [ ]" not in plan, plan
        assert plan.count("- [x]") == 3, plan
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        ns["cleanup"]()


def test_implement_fully_tracked_plan_logs_full_step_count():
    """(implement "A fully tracked plan logs the full step count before
    the stage completes" — new scenario; reference
    `requirements/implement.feature::A fully tracked plan logs the full
    step count before the stage completes`) a plan the implement stage
    finds with no open (`- [ ]`) steps left exits its per-step loop on
    the open-step check — without consuming a generation call (the
    sandbox's fake `pi` is never invoked) — and logs the full step count
    before the stage completes: "stage 8 implementation: all <total> plan
    steps done — stage complete" with the plan's total step count (the
    sandbox plan holds three steps, all done), and that is the only line
    the stage prints that calls the stage complete — one form on both
    exit paths (a plan already fully tracked when the stage starts, and a
    plan made fully tracked by the last call), no per-step line in the
    stage's log."""
    ns = _implement_stage_sandbox(
        "# Issue 74\n\n## Steps\n\n"
        "- [x] a done step\n"
        "- [x] a done step two\n"
        "- [x] a done step three\n")
    hook, cwd = sys.excepthook, os.getcwd()
    os.chdir(ns["repo"])
    try:
        ns["mod"].main()
        console = open(os.path.join(ns["rt"], "cw", "stage-console.log"),
                       encoding="utf-8").read()
        lines = [l for l in console.splitlines() if l.strip()]
        all_done = ("stage 8 implementation: all 3 plan steps done — "
                    "stage complete")
        # exiting the per-step loop logs the full step count — the plan's
        # total step count (three steps, all done)
        assert all_done in lines, console
        # …and that is the only line the stage prints that calls the stage
        # complete, with no per-step line in the log
        for l in lines:
            if "stage complete" in l:
                assert l == all_done, \
                    f"an unexpected stage-complete line: {l!r}"
        assert not any("of the plan done" in l for l in lines), \
            "no per-step line — the plan has no open steps left"
        # the exit is the loop's open-step check — no generation call
        # behind it (the fake `pi` was never invoked)
        cf = os.path.join(ns["rt"], "cw", "fake-pi-count.txt")
        assert not os.path.exists(cf) or open(cf).read().strip() == "0", \
            "a fully tracked plan exits the per-step loop without a pi call"
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        ns["cleanup"]()


def test_every_completed_implement_step_is_committed_and_pushed():
    """(implement "Every completed implementation step is committed and
    pushed" — new scenario; reference
    `requirements/implement.feature::Every completed implementation step
    is committed and pushed`) the implement stage works the plan one step
    at a time — the sandbox's fake `pi` flips the plan's first open step
    per call (the sandbox plan holds two open steps, so the stage's
    per-step loop runs the shared generation loop once per step) — and
    the shared loop's stage-completion push is the mechanism that makes
    each completed step's work durable: after each clean iteration (the
    step's changes committed, the guard passed) the loop pushes the AI
    branch before returning to the stage's per-step loop, so a push of
    the AI branch lands after each completed step's commit and before
    the stage starts the next step. The test asserts the git-call order
    the fake model records — the step-1 commit, then the push, then the
    step-2 pi call (the sandbox's fake `pi` appends its own line to the
    model's events file, so the sequence interleaves the two), then the
    step-2 commit and its push — and that the first push's tip carries
    the state a run terminated after that push keeps on the remote
    branch: the pushed tip's tree holds the plan file with the step-1
    checkbox marked `- [x]` (the step's commit sweeps the working tree —
    the flipped checkbox rides in the same commit the push carries) — so
    a re-triggered run reusing the remote branch (the resume semantics)
    reads the plan file at the remote tip and finds the step still
    marked done; the last push's tip holds every step done and is the
    branch tip the stage leaves."""
    ns = _implement_stage_sandbox(
        "# Issue 74\n\n## Steps\n\n"
        "- [ ] a first step\n"
        "- [ ] a second step\n")
    ws_fake = _FAKE_REPOS[os.path.realpath(ns["repo"])]
    # the ordered event log: the fake model appends one line per git call
    # it handles, the sandbox's fake `pi` appends its own invocation line
    # to the same file — the two write to one file, so the test reads a
    # single sequence interleaving the stage's git calls with its pi calls
    events = os.path.join(ns["rt"], "cw", "git-events.log")
    ws_fake.events_file = events
    # the documented stage-value channel the stage-completion push
    # resolves (the AI_BRANCH job env every stage job writes, the
    # push idiom's GITHUB_REPOSITORY/GH_TOKEN riding along), and the
    # events file the sandbox's fake `pi` appends to
    extra = ("AI_BRANCH", "GITHUB_REPOSITORY", "GH_TOKEN",
             "FAKE_PI_EVENTS")
    saved = {k: os.environ.get(k) for k in extra}
    for k in extra:
        os.environ.pop(k, None)
    os.environ.update({
        "AI_BRANCH": "ai/code-weaver/74",
        "GITHUB_REPOSITORY": "code-weaver/target",
        "GH_TOKEN": "fake-token",
        "FAKE_PI_EVENTS": events,
    })
    hook, cwd = sys.excepthook, os.getcwd()
    os.chdir(ns["repo"])
    try:
        ns["mod"].main()
        console = open(os.path.join(ns["rt"], "cw", "stage-console.log"),
                       encoding="utf-8").read()
        lines = [l for l in console.splitlines() if l.strip()]
        # the per-step loop ran the shared loop once per completed step —
        # both of the plan's open steps worked and marked done
        assert ("stage 8 implementation: clean — step 1/2 of the plan "
                "done; 1 step(s) remain") in lines, console
        assert ("stage 8 implementation: all 2 plan steps done — "
                "stage complete") in lines, console
        # the stage-completion push fired once per completed step, on the
        # AI branch — inside the stage machinery, before the run proceeds
        assert [b for b, _ in ws_fake.pushes] == [
            "ai/code-weaver/74", "ai/code-weaver/74"], ws_fake.pushes
        (step1_branch, step1_tip) = ws_fake.pushes[0]
        (step2_branch, step2_tip) = ws_fake.pushes[1]
        assert step1_tip != step2_tip, \
            "the stage pushed the same branch tip for both completed steps"
        assert step2_tip == ws_fake.heads[-1], \
            "the last push is not the branch tip the stage left"
        # the git-call order the fake model records: the step-1 commit,
        # then the push of the AI branch, then the step-2 pi call (the
        # push precedes the next step), then the step-2 commit and its push
        ev = [l.strip()
              for l in open(events, encoding="utf-8").read().splitlines()
              if l.strip()]
        pi_calls = [i for i, l in enumerate(ev) if l == "pi"]
        assert len(pi_calls) == 2, \
            f"the stage ran one pi call per completed step: {ev!r}"
        i_c1 = ev.index(f"commit {step1_tip}")
        i_p1 = ev.index(f"push {step1_branch} {step1_tip}")
        i_c2 = ev.index(f"commit {step2_tip}")
        i_p2 = ev.index(f"push {step2_branch} {step2_tip}")
        assert i_c1 < i_p1 < pi_calls[1] < i_c2 < i_p2, \
            f"the push must land after the step's commit and before the " \
            f"stage starts the next step: {ev!r}"
        # the first push's tip — the remote state a run terminated right
        # after it keeps — carries the step-1 commit's tree: the plan
        # file with the step-1 checkbox flipped done, step 2 still open
        plan1 = ws_fake.commits.get(step1_tip, {}).get("plans/74.md")
        assert plan1 is not None, \
            "the pushed tip does not carry the plan file"
        assert "- [x] a first step" in plan1, plan1
        assert "- [ ] a second step" in plan1, plan1
        # …and the last push's tip holds every step marked done: a
        # re-triggered run reuses the remote branch and reads the plan
        # file from it, finding every completed step still done
        plan2 = ws_fake.commits.get(step2_tip, {}).get("plans/74.md")
        assert "- [x] a first step" in plan2 and \
               "- [x] a second step" in plan2, plan2
        # the stage's per-step loop left the plan fully tracked in the
        # worktree — committed and pushed
        plan = open(os.path.join(ns["repo"], "plans", "74.md"),
                    encoding="utf-8").read()
        assert "- [ ]" not in plan, plan
        assert plan.count("- [x]") == 2, plan
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        ns["cleanup"]()


def test_single_call_stages_keep_plain_completion_line():
    """(implement "The single-call stages keep the plain completion
    line" — new scenario; reference
    `requirements/implement.feature::The single-call stages keep the plain
    completion line`) the extract, plan or review stage completes in a
    single generation call, and when the shared generation loop comes
    back clean for it, it logs the plain "clean — stage complete" line
    for that stage: the loop's completion-line hook defaults to that
    plain form, and the per-step completion label is the implement
    stage's own — the shared loop does not force one wording on every
    caller. The plan stage's real entry (its single-call shape: one
    generation call through the shared loop) run in the stage sandbox
    (a temp workspace + state dir, a fake `pi` on PATH that writes the
    stage's one allowed plan file and closes with a settled JSONL event
    stream) logs exactly the plain line for its stage when the loop comes
    back clean — and no per-step form anywhere in the stage's log."""
    import shutil
    import tempfile
    spec = importlib.util.spec_from_file_location(
        "cw_plan_stage_sandbox",
        os.path.join(ROOT, ".github", "actions", "plan-stage", "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cw_plan_stage_sandbox"] = mod
    spec.loader.exec_module(mod)
    # the stage's git traffic (the guard call in its loop) rides the
    # mocked single entry point — the fake model, no git process spawned
    restore_git = _patch_git_exec()
    ws = tempfile.mkdtemp(prefix="cw-plan-plain-ws-")
    rt = tempfile.mkdtemp(prefix="cw-plan-plain-rt-")
    fake = tempfile.mkdtemp(prefix="cw-plan-plain-fake-")
    with open(os.path.join(ws, "README.md"), "w") as f:
        f.write("# the project\n")
    ws_fake = _FakeRepo(ws)
    ws_key = os.path.realpath(ws)
    _FAKE_REPOS[ws_key] = ws_fake
    ws_fake.exec(["init", "-q"])
    ws_fake.exec(["add", "-A"])
    ws_fake.exec(["commit", "-qm", "baseline"])
    baseline = ws_fake.exec(["rev-parse", "HEAD"]).stdout.strip()
    assert baseline, "the sandbox's fake baseline commit failed"
    cw = os.path.join(rt, "cw")
    os.makedirs(os.path.join(cw, "state", "trigger"))
    with open(os.path.join(cw, "baseline.sha"), "w") as f:
        f.write(baseline + "\n")
    with open(os.path.join(cw, "stage-baseline.sha"), "w") as f:
        f.write(baseline + "\n")
    with open(os.path.join(cw, "state", "trigger", "issue-number.txt"),
              "w") as f:
        f.write("74\n")
    os.makedirs(os.path.join(fake, "bin"))
    # the fake `pi` plays the planner: it writes the plan file and closes
    # with a usage-carrying JSONL event stream the way a real
    # `pi --mode json` call's stdout reads
    with open(os.path.join(fake, "bin", "pi"), "w") as f:
        f.write("#!" + sys.executable + "\n"
                "import json, os\n"
                "ws = os.environ['GITHUB_WORKSPACE']\n"
                "os.makedirs(os.path.join(ws, 'plans'), exist_ok=True)\n"
                "with open(os.path.join(ws, 'plans', '74.md'), 'w',\n"
                "          encoding='utf-8') as f:\n"
                "    f.write('# Issue 74\\n\\n## Steps\\n\\n- [ ] a step\\n')\n"
                "print(json.dumps({'type': 'message_end', 'message': {\n"
                "    'role': 'assistant',\n"
                "    'content': 'the plan is written',\n"
                "    'usage': {'input': 4, 'output': 2}}}))\n"
                "print(json.dumps({'type': 'agent_settled'}))\n")
    os.chmod(os.path.join(fake, "bin", "pi"), 0o755)
    keys = ("GITHUB_WORKSPACE", "RUNNER_TEMP", "LLM_MODEL", "MAX_LOOPS",
            "PATH", "PLAN_DIR", "REQUIREMENTS_DIR", "DOC_DIR",
            "BASELINE_REF", "CW_ISSUE_NUMBER", "INPUT_ISSUE_NUMBER")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "GITHUB_WORKSPACE": ws,
        "RUNNER_TEMP": rt,
        "LLM_MODEL": "fake-model",
        "MAX_LOOPS": "5",
        "PATH": os.path.join(fake, "bin") + os.pathsep + (saved["PATH"] or ""),
        "PLAN_DIR": "plans",
    })
    saved_mods = {k: sys.modules.get(k) for k in ("common", "stages")}
    hook, cwd = sys.excepthook, os.getcwd()
    os.chdir(ws)
    try:
        mod.main()
        console = open(os.path.join(rt, "cw", "stage-console.log"),
                       encoding="utf-8").read()
        lines = [l for l in console.splitlines() if l.strip()]
        # the shared loop comes back clean for the single-call stage — it
        # logs the plain line for that stage…
        assert "stage 6 planning: clean — stage complete" in lines, console
        # …exactly that plain form: the only completion line in the
        # stage's log (the per-step completion label is the implement
        # stage's own hook — no per-step form rides the single-call stages)
        for l in lines:
            if "stage complete" in l:
                assert l == "stage 6 planning: clean — stage complete", \
                    f"an unexpected completion line: {l!r}"
        assert not any("of the plan done" in l for l in lines), \
            "no per-step form — the shared loop's plain form is the default"
        # the stage completed on its single generation call: the plan file
        # the fake `pi` wrote landed, committed, guard-clean
        assert os.path.isfile(os.path.join(ws, "plans", "74.md"))
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for k, v in saved_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        sys.modules.pop("cw_plan_stage_sandbox", None)
        restore_git()
        _FAKE_REPOS.pop(ws_key, None)
        for d in (ws, rt, fake):
            shutil.rmtree(d, ignore_errors=True)


def test_completed_stage_work_is_committed_and_pushed():
    """(safety "A completed stage's work is committed and pushed to the
    AI branch" — new scenario; reference
    `requirements/safety.feature::A completed stage's work is committed
    and pushed to the AI branch`) a single-call generation stage (the
    plan stage) run to clean completion in the stage sandbox (a temp
    workspace the fake model tracks as a git repo, a temp state dir, the
    fake `pi` on PATH writing the stage's one allowed plan file): the
    stage's generation call commits the plan file on the AI branch, the
    guard passes, and the shared generation loop pushes the AI branch to
    the remote as part of the stage completing — the push moves from the
    job-tail workflow step (a step a terminated run never reaches) into
    the stage machinery: a push of the AI branch is recorded after the
    stage's commit, and the pushed tip is the commit carrying the
    stage's changed file — a run terminated after the stage completes
    loses none of the completed stage's work (the remote branch holds
    it; the job tail's push step stays as the job's final sync). The
    push reuses the factory's sanitised push idiom (the token rewritten
    out of the log, the GIT_CONFIG hygiene) and resolves the branch name
    through the documented stage-value channel — the AI_BRANCH job env
    every stage job writes, with the CW_/trigger-state fallback; where
    the branch is unresolvable (an idle run) it skips with a log line
    rather than failing, and a push that actually fails fails the
    stage."""
    import shutil
    import tempfile
    spec = importlib.util.spec_from_file_location(
        "cw_plan_push_sandbox",
        os.path.join(ROOT, ".github", "actions", "plan-stage", "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cw_plan_push_sandbox"] = mod
    spec.loader.exec_module(mod)
    # the stage's git traffic (the guard call in its loop, and its
    # stage-completion push) rides the mocked single entry point — the
    # fake model records the push
    restore_git = _patch_git_exec()
    ws = tempfile.mkdtemp(prefix="cw-plan-push-ws-")
    rt = tempfile.mkdtemp(prefix="cw-plan-push-rt-")
    fake = tempfile.mkdtemp(prefix="cw-plan-push-fake-")
    with open(os.path.join(ws, "README.md"), "w") as f:
        f.write("# the project\n")
    ws_fake = _FakeRepo(ws)
    ws_key = os.path.realpath(ws)
    _FAKE_REPOS[ws_key] = ws_fake
    ws_fake.exec(["init", "-q"])
    ws_fake.exec(["add", "-A"])
    ws_fake.exec(["commit", "-qm", "baseline"])
    baseline = ws_fake.exec(["rev-parse", "HEAD"]).stdout.strip()
    assert baseline, "the sandbox's fake baseline commit failed"
    cw = os.path.join(rt, "cw")
    os.makedirs(os.path.join(cw, "state", "trigger"))
    with open(os.path.join(cw, "baseline.sha"), "w") as f:
        f.write(baseline + "\n")
    with open(os.path.join(cw, "stage-baseline.sha"), "w") as f:
        f.write(baseline + "\n")
    with open(os.path.join(cw, "state", "trigger", "issue-number.txt"),
              "w") as f:
        f.write("74\n")
    os.makedirs(os.path.join(fake, "bin"))
    # the fake `pi` plays the planner: it writes the plan file and closes
    # with a usage-carrying JSONL event stream the way a real
    # `pi --mode json` call's stdout reads
    with open(os.path.join(fake, "bin", "pi"), "w") as f:
        f.write("#!" + sys.executable + "\n"
                "import json, os\n"
                "ws = os.environ['GITHUB_WORKSPACE']\n"
                "os.makedirs(os.path.join(ws, 'plans'), exist_ok=True)\n"
                "with open(os.path.join(ws, 'plans', '74.md'), 'w',\n"
                "          encoding='utf-8') as f:\n"
                "    f.write('# Issue 74\\n\\n## Steps\\n\\n- [ ] a step\\n')\n"
                "print(json.dumps({'type': 'message_end', 'message': {\n"
                "    'role': 'assistant',\n"
                "    'content': 'the plan is written',\n"
                "    'usage': {'input': 4, 'output': 2}}}))\n"
                "print(json.dumps({'type': 'agent_settled'}))\n")
    os.chmod(os.path.join(fake, "bin", "pi"), 0o755)
    keys = ("GITHUB_WORKSPACE", "RUNNER_TEMP", "LLM_MODEL", "MAX_LOOPS",
            "PATH", "PLAN_DIR", "REQUIREMENTS_DIR", "DOC_DIR",
            "BASELINE_REF", "CW_ISSUE_NUMBER", "INPUT_ISSUE_NUMBER",
            "AI_BRANCH", "CW_AI_BRANCH", "GITHUB_REPOSITORY", "GH_TOKEN")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "GITHUB_WORKSPACE": ws,
        "RUNNER_TEMP": rt,
        "LLM_MODEL": "fake-model",
        "MAX_LOOPS": "5",
        "PATH": os.path.join(fake, "bin") + os.pathsep + (saved["PATH"] or ""),
        "PLAN_DIR": "plans",
        # the documented stage-value channel the stage-completion push
        # resolves: the AI_BRANCH job env every stage job writes
        "AI_BRANCH": "ai/code-weaver/74",
        "GITHUB_REPOSITORY": "code-weaver/target",
        "GH_TOKEN": "fake-token",
    })
    saved_mods = {k: sys.modules.get(k) for k in ("common", "stages")}
    hook, cwd = sys.excepthook, os.getcwd()
    os.chdir(ws)
    try:
        mod.main()
        console = open(os.path.join(rt, "cw", "stage-console.log"),
                       encoding="utf-8").read()
        lines = [l for l in console.splitlines() if l.strip()]
        # the single-call stage completed clean on its generation call:
        # the plan file the fake `pi` wrote landed, committed, guard-clean
        assert "stage 6 planning: clean — stage complete" in lines, console
        # the stage-completion push: the shared loop pushed the AI branch
        # after the stage's commit, before the run proceeds — the fake
        # model recorded it
        assert ws_fake.pushes, (
            "the stage completed but pushed nothing — the job-tail "
            "workflow step a terminated run never reaches was the "
            "stage's only push")
        branch, tip = ws_fake.pushes[-1]
        assert branch == "ai/code-weaver/74", (
            f"the push carried a branch other than the AI branch: "
            f"{branch!r}")
        # the push is recorded AFTER the stage's commit: the pushed tip
        # is the stage's commit (not the baseline the stage started on)
        assert tip != baseline, \
            "the push recorded the stage's baseline as its tip — the " \
            "stage's commit is not on it"
        assert tip == ws_fake.heads[-1], \
            "the push's tip is not the branch tip the stage left"
        # and the pushed tip carries the stage's changed file — a run
        # terminated after the push keeps it on the remote branch
        assert "plans/74.md" in ws_fake.commits[tip], \
            "the pushed tip does not carry the stage's changed file"
        assert ws_fake.commits[tip]["plans/74.md"] == \
            "# Issue 74\n\n## Steps\n\n- [ ] a step\n"
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for k, v in saved_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        sys.modules.pop("cw_plan_push_sandbox", None)
        restore_git()
        _FAKE_REPOS.pop(ws_key, None)
        for d in (ws, rt, fake):
            shutil.rmtree(d, ignore_errors=True)


def test_templates_plans_and_logs_agree_on_step_wording():
    """(implement "The templates, the plan files and the stage log agree
    on one word for the plan's units" — new scenario; reference
    `requirements/implement.feature::The templates, the plan files and
    the stage log agree on one word for the plan's units`) one word for
    the plan's checklist units — "step" — across every plan-facing
    surface: the planner template prescribes the plan's section heading
    "Steps" and its units as steps, the implementer template calls the
    units steps, the implement stage's log lines use "steps", and the
    checkbox form (`- [ ]` for an open unit, `- [x]` for a done one) is
    unchanged — the code that reads the plan keys on the checkbox, not
    the word: a plan file whose unit word is reworded parses identically
    (the reader's done/total counts and its open-step check come out the
    same for a plan whose units are called steps and for one whose units
    are called something else)."""
    import shutil
    import tempfile
    # the planner template prescribes the plan's section heading
    # "Steps" and its units as steps
    plan = _read("pi-prompts/plan.md")
    assert ("**Steps** section — an ordered, atomic, "
            "independently-achievable checkbox\n"
            "checklist (`- [ ] <step>`)") in plan
    assert "Each step states, in order:" in plan
    assert ("The implementation stage reads the Steps checklist "
            "top-to-bottom, one step at a\ntime") in plan
    # the implementer template calls the plan's units steps
    implement = _read("pi-prompts/implement.md")
    assert ("its **Steps** section is an ordered checklist\n"
            "of open (`- [ ]`) and done (`- [x]`) steps") in implement
    assert "first `- [ ]` step (from the top)" in implement
    assert ("**Mark the step done** — flip its checkbox to `- [x]` in "
            "the plan file.") in implement
    # the implement stage's log lines use "steps": the per-step line
    # while steps remain open, the full-step-count line the stage's
    # completion exit prints (the only line that calls the stage
    # complete), and the per-step state the stage records on the
    # stage-summary channel
    stage = _read(".github/actions/implement-stage/stage.py")
    assert 'f"stage 8 implementation: clean — step {done}/{total} "' in stage
    assert 'f"of the plan done; {total - done} step(s) remain")' in stage
    assert 'f"stage 8 implementation: all {total} plan steps "' in stage
    assert 'f"done — stage complete")' in stage
    assert 'f"stage 8 implementation: step {k}/{total} "' in stage
    # the checkbox form is unchanged and the reader keys on the
    # checkbox, not the word: a plan file whose unit word is reworded
    # parses identically
    spec = importlib.util.spec_from_file_location(
        "cw_implement_step_wording",
        os.path.join(ROOT, ".github", "actions", "implement-stage",
                     "stage.py"))
    mod = importlib.util.module_from_spec(spec)
    saved_mods = {k: sys.modules.get(k) for k in ("common", "stages")}
    ws = tempfile.mkdtemp(prefix="cw-implement-wording-")
    try:
        spec.loader.exec_module(mod)
        for name, unit in (("steps.md", "step"), ("reworded.md", "task")):
            with open(os.path.join(ws, name), "w", encoding="utf-8") as f:
                f.write(f"# Issue 75\n\n## Steps\n"
                        f"\n- [x] a done {unit}\n"
                        f"- [ ] an open {unit}\n")
            path = os.path.join(ws, name)
            assert mod.count_plan_steps(path) == (1, 2), \
                f"the plan reader counts the plan's checkboxes, {name!r}"
            assert mod.has_open_task(path) is True, \
                f"the open checkbox still reads as an open unit, {name!r}"
        # both plans parse identically — the word is not the key
        assert (mod.count_plan_steps(os.path.join(ws, "steps.md")) ==
                mod.count_plan_steps(os.path.join(ws, "reworded.md")))
    finally:
        for k, v in saved_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        shutil.rmtree(ws, ignore_errors=True)


def test_implement_instructions_prescribe_the_test_reference():
    """(implement "Tests are generated for the new behaviour" — the new
    And step; test-and-review "Tests reference the Gherkin requirement
    they arose from", "A changed requirement pulls in the tests that
    reference it"; reference
    `requirements/implement.feature::Tests are generated for the new
    behaviour`,
    `requirements/test-and-review.feature::Tests reference the Gherkin
    requirement they arose from`,
    `requirements/test-and-review.feature::A changed requirement pulls in
    the tests that reference it`) the implement prompt template
    prescribes the reference convention the suite and the oracle join on:
    a test that implements a Gherkin scenario carries a reference to the
    scenario it arose from — the machine form is the test's docstring
    citing the scenario, and a test that is only for correctness carries
    no such reference; a scenario changed in place pulls in the tests
    that reference it — the adjusted tests fulfil the requirement as it
    now reads."""
    prompt = _read("pi-prompts/implement.md")
    # a test that implements a Gherkin scenario carries a reference to
    # the scenario it arose from — the machine form is the docstring
    # citation `<feature file>::<scenario name>`, in the example shape
    assert "Gherkin scenario carries a reference to the scenario it" in prompt
    assert "citing the scenario as" in prompt
    assert "`<feature file>::<scenario name>`" in prompt
    assert ("requirements/guard-rail.feature::Guard repairs are capped"
            in prompt)
    # a test that is only for correctness carries no such reference
    assert "is only for correctness carries no such reference" in prompt
    # a scenario changed in place pulls in the tests that reference it —
    # the adjusted tests fulfil the requirement as it now reads
    assert ("changed a Gherkin scenario in place, adjust every test that"
            in prompt)
    assert "references that changed scenario with it" in prompt
    assert "the adjusted tests fulfil" in prompt
    assert "the requirement as it now reads" in prompt


def test_implement_instructions_prescribe_the_brownfield_work():
    """(implement "A brown field run adjusts the tests without
    implementing code" — new @brownfield scenario; reference
    `requirements/implement.feature::A brown field run adjusts the
    tests without implementing code`) on a run whose requirements
    were extracted from the project's existing code, the implement
    prompt template's brownfield clause prescribes the work the
    scenario demands: where the plan the stage works is a
    brownfield plan — its steps are all about adjusting the
    tests to reference the extracted scenarios, none implements
    code (the plan stage's brownfield scope makes the plan read
    that way) — the implementation changes no source code, the
    changed files are the tests and the issue's plan file; the
    existing tests are adjusted to reference the requirements
    they describe; each adjusted test that implements a scenario
    cites it in its docstring as `<feature file>::<scenario
    name>` — the machine form the template already prescribes
    for generated tests, applied to *adjusted* existing tests;
    where the plan is not a brownfield plan, the clause does not
    apply — the standing instructions govern. No guard change
    rides with the clause — the inverted allow already admits
    the brownfield change set (the tests, and the plan file
    re-allowed over the denied plans dir)."""
    prompt = _read("pi-prompts/implement.md")
    # the clause is the implement prompt's item 7 — the standing
    # items 1-6 and the hard rules stand unchanged
    assert "7. **A brownfield plan scopes your work to the" in prompt
    # the clause keys on the plan the stage works being a brownfield
    # plan — its steps are all about adjusting tests to reference
    # the extracted scenarios, none implements code
    assert ("Where the plan you are working is a brownfield plan — its\n"
            "   steps are all about adjusting tests to reference the\n"
            "   extracted scenarios, none implements code") in prompt
    # the premise: the plan stage's brownfield scope makes the plan
    # read that way
    assert ("(the plan\n   stage's brownfield scope makes the plan read"
            " that way)") in prompt
    # the implementation changes no source code — the changed files
    # are the tests and the issue's plan file
    assert ("your implementation changes **no source code**: the changed\n"
            "   files are the tests and the issue's plan file") in prompt
    # the existing tests are adjusted to reference the requirements
    # they describe
    assert ("You adjust\n   the existing tests to reference the"
            " requirements\n   they describe") in prompt
    # each adjusted test that implements a scenario cites it in its
    # docstring as `<feature file>::<scenario name>` — the machine
    # form item 6 prescribes for generated tests, applied to
    # adjusted existing tests
    assert ("each adjusted test that implements a\n"
            "   scenario cites it in its docstring as\n"
            "   `<feature file>::<scenario name>` — the machine form"
            " item 6") in prompt
    assert ("prescribes for generated tests, applied to *adjusted*\n"
            "   existing tests.") in prompt
    # where the plan is not a brownfield plan, the clause does not
    # apply — the standing instructions govern
    assert ("Where the plan is not a brownfield plan\n"
            "   (a step implements code, as on the standing runs),"
            " this\n   clause does not apply — the standing"
            " instructions govern.") in prompt


def test_tests_that_implement_scenarios_reference_them():
    """(test-and-review "Tests reference the Gherkin requirement they
    arose from", "A changed requirement pulls in the tests that reference
    it"; reference
    `requirements/test-and-review.feature::Tests reference the Gherkin
    requirement they arose from`,
    `requirements/test-and-review.feature::A changed requirement pulls in
    the tests that reference it`) the suite-level form of the reference
    convention: over the test suite under tests/, every test that
    implements a Gherkin scenario carries a reference to the scenario it
    arose from — the cited feature file exists under requirements/ and
    the cited scenario name is a scenario of that file — and a test with
    no such reference is one that is only for correctness. The suite's
    standing prose form (the scenario name quoted in the test's
    docstring) is the mention side of the join: a scenario the docstring
    quotes must be cited in the machine form, so the review stage can
    extract the reference from the run's changed tests, and a run that
    changed a scenario in place can find the tests to adjust with it."""
    import ast
    reqdir = os.path.join(ROOT, "requirements")
    scenarios = {}
    for fname in sorted(os.listdir(reqdir)):
        if not fname.endswith(".feature"):
            continue
        with open(os.path.join(reqdir, fname), encoding="utf-8") as f:
            scenarios[fname] = [
                m.group(1).strip() for line in f
                for m in [re.match(
                    r"^\s*Scenario(?:\s+Outline)?\s*:\s*(.+?)\s*$", line)]
                if m]
    owners = {}
    for fname, names in scenarios.items():
        for name in names:
            owners.setdefault(name.lower(), []).append(fname)
    checked = cited = 0
    testsdir = os.path.join(ROOT, "tests")
    for fname in sorted(os.listdir(testsdir)):
        if not (fname.startswith("test_") and fname.endswith(".py")):
            continue
        with open(os.path.join(testsdir, fname), encoding="utf-8") as f:
            src = f.read()
        for node in ast.parse(src).body:
            if not (isinstance(node, ast.FunctionDef)
                    and node.name.startswith("test_")):
                continue
            doc = " ".join((ast.get_docstring(node) or "").split())
            cites = [(f, n.strip()) for f, n in re.findall(
                r"`requirements/([\w.-]+\.feature)::([^`]+)`", doc)]
            # every cited feature file exists under requirements/ and the
            # cited scenario name is a scenario of that file
            for f, n in cites:
                assert f in scenarios, (
                    f"{fname}::{node.name} cites {f!r} — no oracle file "
                    f"under requirements/")
                assert n in scenarios[f], (
                    f"{fname}::{node.name} cites {n!r}, which is not a "
                    f"scenario of requirements/{f}")
                cited += 1
            # every scenario the docstring quotes in the suite's standing
            # prose form is cited in the machine form
            for q in re.findall(r'"([^"]+)"', doc):
                q = " ".join(q.split())
                if q.lower() in owners:
                    assert any(c in owners[q.lower()]
                               and n.lower() == q.lower()
                               for c, n in cites), (
                        f"{fname}::{node.name} quotes scenario {q!r} (a "
                        f"scenario of {sorted('requirements/' + f for f in owners[q.lower()])}) "
                        f"but carries no <feature file>::<scenario name> "
                        f"reference to it")
            checked += 1
    assert checked, "no test functions discovered under tests/"
    assert cited, "no test in the suite carries a scenario reference"


def _run_gates_stage(pages, head_sha="a" * 40, empty_polls=None):
    """Exec the gates stage's python in a sandbox: a temp RUNNER_TEMP state
    dir, a fake `gh` on PATH serving the canned `actions/runs` pages in
    call order (recording every query URL), and a no-op `time.sleep` so
    the poll loop runs at test speed — no network, no pi. Returns (exit
    code, the stage-summary file's text, the recorded query URLs).

    `pages` is the list of response bodies the fake serves, one per call
    (the last page repeats once the list is exhausted) — exactly the page
    walk `pr_runs` performs against the live endpoint.
    """
    import shutil
    import tempfile as _tf
    ws = _tf.mkdtemp(prefix="cw-gates-ws-")
    rt = _tf.mkdtemp(prefix="cw-gates-rt-")
    fake = _tf.mkdtemp(prefix="cw-gates-fake-")
    binp = os.path.join(fake, "bin")
    os.makedirs(binp)
    pages_f = os.path.join(fake, "pages.json")
    urls_f = os.path.join(fake, "urls.txt")
    with open(pages_f, "w", encoding="utf-8") as f:
        json.dump(pages, f)
    with open(os.path.join(binp, "gh"), "w", encoding="utf-8") as f:
        f.write("#!%s\n" % sys.executable +
                "import json, os, sys\n"
                "args = sys.argv[1:]\n"
                "logf = os.environ['FAKE_GH_URLS']\n"
                "n = sum(1 for _ in open(logf)) if os.path.exists(logf) else 0\n"
                "with open(logf, 'a') as lf:\n"
                "    lf.write((args[-1] if args else '') + chr(10))\n"
                "if any('actions/runs' in a for a in args):\n"
                "    pages = json.load(open(os.environ['FAKE_GH_PAGES']))\n"
                "    print(json.dumps(pages[min(n, len(pages) - 1)]))\n"
                "else:\n"
                "    print('{}')\n")
    os.chmod(os.path.join(binp, "gh"), 0o755)
    keys = ("PATH", "RUNNER_TEMP", "GITHUB_WORKSPACE", "GITHUB_REPOSITORY",
            "GH_TOKEN", "CW_HEAD_SHA", "CW_GATE_EMPTY_POLLS", "CW_GATE_POLLS",
            "AI_BRANCH", "FAKE_GH_PAGES", "FAKE_GH_URLS", "INPUT_HEAD_SHA")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update({
        "PATH": binp + os.pathsep + (saved["PATH"] or ""),
        "RUNNER_TEMP": rt,
        "GITHUB_WORKSPACE": ws,
        "GITHUB_REPOSITORY": "code-weaver/test-target",
        "GH_TOKEN": "fake-token",
        "AI_BRANCH": "ai/code-weaver/test",
        "CW_HEAD_SHA": head_sha,
        "FAKE_GH_PAGES": pages_f,
        "FAKE_GH_URLS": urls_f,
    })
    if empty_polls is not None:
        os.environ["CW_GATE_EMPTY_POLLS"] = str(empty_polls)
    # a no-op `time` stands in for the stdlib one so the poll loop does not
    # sleep for real: the stage's `import time` picks the stub up via
    # sys.modules (nothing else in the sandbox touches time)
    real_time = sys.modules.get("time")
    stub = types.ModuleType("time")
    stub.sleep = lambda s: None
    sys.modules["time"] = stub
    ns = {"__name__": "__main__",
          "__file__": os.path.join(ROOT, ".github", "actions", "gates-stage",
                                   "stage.py")}
    hook, cwd = sys.excepthook, os.getcwd()
    code = 0
    summary = ""
    urls = []
    os.chdir(ws)
    try:
        try:
            exec(compile(_read(".github/actions/gates-stage/stage.py"),
                         ns["__file__"], "exec"), ns)
        except SystemExit as e:
            code = (e.code if isinstance(e.code, int)
                    else (0 if e.code is None else 1))
        # read the state the stage left behind before the finally block
        # removes the temp dirs
        sf = os.path.join(rt, "cw", "stage-summary.txt")
        if os.path.isfile(sf):
            summary = open(sf, encoding="utf-8").read()
        if os.path.isfile(urls_f):
            urls = [l.strip() for l in open(urls_f) if l.strip()]
    finally:
        os.chdir(cwd)
        sys.excepthook = hook
        sys.modules["time"] = real_time
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(rt, ignore_errors=True)
        shutil.rmtree(fake, ignore_errors=True)
    return code, summary, urls


def test_gates_stage_query_is_scoped_to_the_pr_head():
    """(pr-and-gates "all PR-triggered workflows must be green";
    reference
    `requirements/pr-and-gates.feature::All PR-triggered workflows must
    be green`)
    the run query is scoped to the PR's head sha server-side — never a
    client-side filter over the repo-wide listing's first 100 newest runs —
    and the client-side event filter keeps push-triggered runs on the same
    sha out of the gate (they are not triggered on the pull request)."""
    sha = "b" * 40
    pages = [{"total_count": 3, "workflow_runs": [
        {"id": 1, "name": "house CI", "event": "pull_request",
         "head_sha": sha, "status": "completed", "conclusion": "success"},
        {"id": 2, "name": "fork-safe CI", "event": "pull_request_target",
         "head_sha": sha, "status": "completed", "conclusion": "success"},
        {"id": 3, "name": "push-only CI", "event": "push",
         "head_sha": sha, "status": "completed", "conclusion": "failure"},
    ]}]
    code, summary, urls = _run_gates_stage(pages, head_sha=sha)
    assert code == 0, \
        f"a green head passes the gates (push runs are not part of them): {summary!r}"
    assert "all 2 green" in summary, \
        f"the gate covers exactly the PR-triggered runs: {summary!r}"
    assert urls, "the gate never queried the runs endpoint"
    for u in urls:
        assert "head_sha=" + sha in u, \
            f"the run query must be scoped to the PR's head sha: {u}"
        assert "per_page=100" in u, f"the run query must page explicitly: {u}"


def test_gates_stage_sees_runs_beyond_the_first_hundred():
    """(pr-and-gates "the gate sees the PR's runs on a busy repo";
    reference
    `requirements/pr-and-gates.feature::The gate sees the PR's runs on a
    busy repo`)
    the run query walks the result set to its end — a full page means a
    next page exists — so a PR whose runs sit past the listing's first 100
    is still polled and judged. This is the field failure behind the
    rewrite: the earlier version read only that first page and hard-failed
    a healthy head whose runs it never saw."""
    sha = "e" * 40
    full = {"total_count": 101, "workflow_runs": [
        {"id": i, "name": f"noise {i}", "event": "push",
         "head_sha": sha, "status": "completed", "conclusion": "success"}
        for i in range(100)]}
    tail = {"total_count": 101, "workflow_runs": [
        {"id": 101, "name": "house CI", "event": "pull_request",
         "head_sha": sha, "status": "completed", "conclusion": "success"}]}
    code, summary, urls = _run_gates_stage([full, tail], head_sha=sha)
    assert code == 0, \
        f"the gate must find the PR's run on page two: {summary!r}"
    assert "all 1 green" in summary, \
        f"the gate judges exactly the PR-triggered runs: {summary!r}"
    assert any("page=2" in u for u in urls), \
        "a full page must page on — the run set was never walked to its end"


def test_gates_stage_empty_head_is_vacuously_green():
    """(pr-and-gates "a head with no PR-triggered workflow is vacuously
    green"; reference
    `requirements/pr-and-gates.feature::A head with no PR-triggered
    workflow is vacuously green`)
    a head with no visible PR-triggered run succeeds after the grace
    window: the earlier version's vacuously-green return was dead code
    inside the all-completed branch, so such a head fell through to the
    in-progress branch and hard-failed its poll cap twenty minutes later
    instead of letting the factory proceed."""
    code, summary, urls = _run_gates_stage(
        [{"total_count": 0, "workflow_runs": []}],
        head_sha="c" * 40, empty_polls=2)
    assert code == 0, \
        f"an empty gate set is vacuously green, not a poll-cap failure: {summary!r}"
    assert "vacuously green" in summary, \
        f"the summary records the vacuous pass: {summary!r}"
    assert urls, "the grace window must actually poll the endpoint"


def test_gates_stage_polls_in_progress_runs_to_green():
    """(pr-and-gates "all PR-triggered workflows must be green";
    reference
    `requirements/pr-and-gates.feature::All PR-triggered workflows must
    be green`)
    runs that are still in progress keep the gate polling (bounded by the
    poll cap, the job timeout behind that), and the gate proceeds only once
    every run has completed green — the stage's exit reflects the final
    state, not the first poll."""
    sha = "d" * 40
    running = {"id": 1, "name": "house CI", "event": "pull_request",
               "head_sha": sha, "status": "in_progress", "conclusion": None}
    done = {"id": 1, "name": "house CI", "event": "pull_request",
            "head_sha": sha, "status": "completed", "conclusion": "success"}
    code, summary, urls = _run_gates_stage(
        [{"total_count": 1, "workflow_runs": [running]},
         {"total_count": 1, "workflow_runs": [done]}],
        head_sha=sha)
    assert code == 0 and "all 1 green" in summary, \
        f"the gate waits out the in-progress run and then passes: {summary!r}"
    assert len(urls) >= 2, \
        "the gate must re-poll until every run has completed"


def test_tests_never_invoke_the_real_git_binary():
    """(test-and-review "Tests never invoke the real git binary"; reference
    `requirements/test-and-review.feature::Tests never invoke the real
    git binary`) the factory's python routes every git call through one
    mockable function — the shared module's git_exec, the factory's
    single git entry point (each inline workflow step's own-interpreter
    python carries its own copy of the same one-function shape) — and no
    test spawns the real git binary: a test's git child on the runner
    would read the runner's git configuration and could touch a real
    repository's state, so the sandboxes mock that one function with the
    in-test fake model of a git repo (the guard and stage sandboxes above
    are the behavioural proof — they run the production code end to end
    against the fake). This test pins the shape statically: a direct git
    call is a subprocess.run whose argument list starts with the "git"
    literal; the one-function shape calls git_exec([...]) instead (the
    entry-point definition's own subprocess.run(["git"] + argv) is a
    list-plus-args, not the direct-call shape)."""
    import ast
    import pathlib

    def direct_git_calls(src: str, where: str):
        calls = []
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if not (isinstance(f, ast.Attribute) and f.attr == "run"
                    and isinstance(f.value, ast.Name)
                    and f.value.id == "subprocess"):
                continue
            a0 = node.args[0] if node.args else None
            if (isinstance(a0, ast.List) and a0.elts
                    and isinstance(a0.elts[0], ast.Constant)
                    and a0.elts[0].value == "git"):
                calls.append(f"{where}:{node.lineno}")
        return calls

    bad = []
    # the factory's python — every script the stages import or run
    for p in sorted(pathlib.Path(ROOT, ".github").rglob("*.py")):
        bad += direct_git_calls(p.read_text(),
                                os.path.relpath(p, ROOT))
    # the workflow's inline python: the entry-point definitions write
    # ["git"] + argv, so any line starting a git argument list with a
    # comma — or a run call that does — is a bypass of the one function
    yml = _read(".github/workflows/factory.yml")
    bad += [f".github/workflows/factory.yml:{i}"
            for i, ln in enumerate(yml.splitlines(), 1)
            if re.search(r"^\s*[\"']git[\"']\s*,", ln)
            or re.search(r"subprocess\.run\(\s*[\"']git[\"']\s*,", ln)]
    assert not bad, (
        "the factory's python calls the git binary directly — every git "
        "call must route through the one mockable function the tests "
        "mock: " + ", ".join(bad))
    # and no test spawns the real git binary either: the suite's git
    # traffic is the sandboxes' fake model, installed as the mock for the
    # one function the production code calls
    for p in sorted(pathlib.Path(ROOT, "tests").glob("*.py")):
        bad += direct_git_calls(p.read_text(), f"tests/{p.name}")
    assert not bad, (
        "a test spawns the real git binary — it must mock the factory's "
        "one git entry point with the in-test fake: " + ", ".join(bad))
    # the oracle scenario is implemented: a test in the suite cites it in
    # the machine form (whitespace collapsed — the docstring wraps)
    cite = ("requirements/test-and-review.feature::Tests never invoke "
            "the real git binary")
    assert any(cite in " ".join((ast.get_docstring(node) or "").split())
               for node in ast.parse(_read("tests/test_stage_contract.py")).body
               if isinstance(node, ast.FunctionDef)
               and node.name.startswith("test_")), \
        "no test cites the scenario in the machine form"
