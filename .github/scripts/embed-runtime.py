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
    ".github/actions/extract-stage/stage.py",
    ".github/actions/plan-stage/stage.py",
    ".github/actions/implement-stage/stage.py",
    ".github/actions/review-stage/stage.py",
    ".github/actions/gates-stage/stage.py",
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
    # The check is the only mode: the file is static plain text —
    # nothing here writes it (the splice that once rewrote the file's
    # payload region retires with the embed: a maintainer who changes
    # the runtime tree commits the tree, and the gate verifies the
    # tag's commit against the file). `--check` names the release
    # flow's publication gate; the no-argument form is the same check
    # as a local run.
    ok, message = check(root, path)
    print(("ok:   " if ok else "INCONSISTENT: ") + message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
