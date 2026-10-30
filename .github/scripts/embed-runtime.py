"""Embed the factory's runtime tree into the workflow file that carries it.

The reusable workflow (factory.yml) is the file a target pins — but
GitHub fetches only that file at the called ref, and the called ref is
not visible to the run's jobs. The runtime tree the stage steps execute
(the .github/scripts plumbing, the .github/actions stage scripts, the
pi-prompts templates) must therefore come from the file itself: it is
embedded in stage 1's first step as a base64 tarball behind a heredoc.

This is the release pipeline's rewrite of the published file. The
rewrite is committed to main by the maintainer (the `embed` make
target); the release flow itself only tags main's HEAD and pushes the
tag object — the push it is never refused (a workflow-file commit
would need the `workflows` scope, which the App behind the default
GITHUB_TOKEN cannot be granted) — and the tag the flow cuts therefore
points at a file that carries exactly the runtime tree of the tagged
commit. One ref selects the workflow file and its runtime tree as one
version; a consumer pins nothing besides its uses: line.

The payload region of the file is the heredoc body: the lines between
the line that opens the `base64 -d … <<'CW_EMBEDDED_RUNTIME_TAR'`
redirection and the `CW_EMBEDDED_RUNTIME_TAR` terminator line that
follows it. `--check` verifies the region matches a fresh build of the
tree (the contract test, tests/test_embedded_runtime.py, runs the same
comparison in-process); the default splices the fresh payload in place.
The build is deterministic — sorted member order, zeroed mtime/uid/gid,
gzip header mtime 0 — so re-running it on an unchanged tree rewrites
nothing.

Plain-stdlib by design (tarfile/base64 are stdlib): a runner whose
system python is externally-managed can still run it, and the contract
test loads it by file path with no third-party import available. No
compressor is in the build (see build_payload) — the payload bytes must
be reproducible on any runner's python, on any OS.
"""
from __future__ import annotations

import base64
import io
import os
import sys
import tarfile

# The runtime tree the stage steps execute, repo-relative — the curated
# subset of the checkout: the shared .github scripts (the stage code
# imports from here), the .github actions' stage scripts (the inlined
# steps run them from the stash), and the pi prompt templates (the pi
# invocations read them from here). The tree's paths under its root are
# the layout the stage code resolves against ($RUNNER_TEMP/cw/stash).
RUNTIME_PREFIXES = (".github/scripts", ".github/actions", "pi-prompts")

# The payload region's anchors inside the workflow file: the heredoc the
# stage-1 materialisation step feeds to `base64 -d`, and its terminator.
OPEN_MARKER = "<<'CW_EMBEDDED_RUNTIME_TAR'"
CLOSE_MARKER = "CW_EMBEDDED_RUNTIME_TAR"

BASE64_WRAP = 76


def repo_root() -> str:
    """Repo root from this file's location (…/.github/scripts/…)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def default_factory_path() -> str:
    return os.path.join(repo_root(), ".github", "workflows", "factory.yml")


def runtime_files(root: str):
    """[(arcname, abspath)] — the curated runtime tree, sorted by arcname
    (the deterministic build order): every regular file under the
    curated prefixes, `__pycache__` dirs and *.pyc excluded (the tracked
    tree is source; a compiled cache would make the build
    environment-dependent)."""
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


def build_payload(root: str):
    """(b64_lines, raw_bytes) — the runtime tree as a plain tar (sorted
    members; mtime/uid/gid zeroed; uname/gname empty; modes from the
    file — git-controlled, so identical on any checkout), base64-encoded
    and wrapped at 76 columns: the exact lines the file's payload region
    must hold for the embed to be fresh.

    Deliberately NOT gzipped: the payload is compared byte-exact by the
    contract test and the release gate on every runner, and a gzip layer
    is not byte-stable across platforms — the header's XFL/OS bytes are
    an interpreter detail, and the deflate bitstream depends on the
    zlib build. A plain USTAR tar is fully under our control: the format
    is frozen, every header field is set explicitly, and no compressor
    is involved — so the build is byte-identical on any runner's python,
    on any OS."""
    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode="w", format=tarfile.USTAR_FORMAT) as t:
        for arcname, abspath in runtime_files(root):
            with open(abspath, "rb") as f:
                data = f.read()
            ti = tarfile.TarInfo(arcname)
            ti.size = len(data)
            ti.mtime = 0
            ti.mode = os.stat(abspath).st_mode & 0o777
            ti.uid = 0
            ti.gid = 0
            ti.uname = ""
            ti.gname = ""
            t.addfile(ti, io.BytesIO(data))
    raw = tar.getvalue()
    b64 = base64.b64encode(raw).decode("ascii")
    lines = [b64[i:i + BASE64_WRAP] for i in range(0, len(b64), BASE64_WRAP)]
    return lines, raw


def payload_region(lines):
    """(open_idx, term_idx) — the payload region's bounds: the line that
    opens the heredoc, and the index of the terminator line that follows
    it (the region's body is the lines strictly between them). Raises
    ValueError when the anchors are missing or out of order."""
    open_idx = None
    for i, ln in enumerate(lines):
        if OPEN_MARKER in ln:
            open_idx = i
            break
    if open_idx is None:
        raise ValueError("no line opens the CW_EMBEDDED_RUNTIME_TAR heredoc")
    for j in range(open_idx + 1, len(lines)):
        if lines[j].strip() == CLOSE_MARKER:
            return open_idx, j
    raise ValueError("the CW_EMBEDDED_RUNTIME_TAR heredoc has no terminator line")


def current_payload_lines(lines):
    """The region's body as base64 lines, dedented to column 0 (the
    heredoc's own indent is the file's step-content indent)."""
    open_idx, term_idx = payload_region(lines)
    indent = len(lines[open_idx]) - len(lines[open_idx].lstrip(" "))
    body = lines[open_idx + 1:term_idx]
    return [ln[indent:] if ln.lstrip() else ln for ln in body]


def check(root: str, text: str):
    """(ok, message) — the file's payload region is exactly a fresh
    build of the tree's payload (a maintainer who changed the tree
    without `make embed` — or a stale splice — fails here)."""
    lines = text.splitlines()
    try:
        region = current_payload_lines(lines)
    except ValueError as e:
        return False, f"the workflow file has no payload region ({e})"
    fresh, _raw = build_payload(root)
    if region == fresh:
        return True, (
            f"the embedded runtime tree is fresh "
            f"({len(fresh)} payload lines, {len(runtime_files(root))} files)")
    return False, (
        f"the embedded runtime tree is STALE — the file holds "
        f"{len(region)} payload lines, a fresh build of the tree is "
        f"{len(fresh)} (they differ at line {next((i + 1 for i, (a, b) in enumerate(zip(region, fresh)) if a != b), 'past the shorter side')}); "
        "run `make embed` (python3 .github/scripts/embed-runtime.py) in "
        "the commit that changed .github/scripts, .github/actions or "
        "pi-prompts")


def splice(root: str, text: str) -> str:
    """The file text with its payload region replaced by a fresh build
    of the tree's payload (re-indented to the heredoc's own indent; an
    already-fresh file comes back unchanged)."""
    lines = text.splitlines()
    open_idx, term_idx = payload_region(lines)
    indent = len(lines[open_idx]) - len(lines[open_idx].lstrip(" "))
    fresh, _raw = build_payload(root)
    pad = " " * indent
    new_lines = lines[:open_idx + 1] + [pad + ln for ln in fresh] + lines[term_idx:]
    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = repo_root()
    path = argv[0] if argv and not argv[0].startswith("-") else default_factory_path()
    check_mode = "--check" in argv
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if check_mode:
        ok, message = check(root, text)
        print(("ok:   " if ok else "STALE: ") + message)
        return 0 if ok else 1
    new_text = splice(root, text)
    if new_text != text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)
    _lines, raw = build_payload(root)
    files = runtime_files(root)
    print(f"embedded the runtime tree in {os.path.relpath(path, root)} "
          f"({len(files)} files, payload {len(raw)} bytes, {len(_lines)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
