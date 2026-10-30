"""The automatic release's version number — issue-#21 release machinery.

A change landing on `main` publishes the next version: the tag is the
**next single increasing number** — the number after the highest
published version of the new scheme (a bare integer tag — no `v`
prefix, no dots), and where no numbered release is published yet the
first release is `1`. The older `vX.Y.Z` tags are not part of the new
number series — they are not numbers — so the numbers of published
releases never repeat and never decrease, and the older tags are left
where they are (workflows pinned to them keep working).

Three shapes, one rule:

  - `next_release_number(published)` — the pure computation of the next
    tag; `tests/test_release_contract.py` unit-tests it (auto-discovered
    by both runners — the stage-10 driver `python3 tests/run.py` and
    house CI's `pytest tests/`);
  - `published_at(tag_lines, sha)` — the guard's pure computation: the
    numbered tag names that point at a commit;
  - the CLI form below — default: one published ref (a tag name) per
    line on stdin, the next tag on stdout (the release workflow pipes
    the remote's tag list into it); `--published-at <sha>`: the raw
    `git ls-remote --tags` line list on stdin, the numbered tag names
    pointing at `<sha>` on stdout (none → empty) — the release
    workflow's one-tag-per-commit guard reads the empty / non-empty
    distinction.

Plain-stdlib on purpose: the `gh` CLI is a pre-requisite of the runner
environment (`docs/08`) — and the workflow consumes it, not this
module.
"""
from __future__ import annotations

import re
import sys

_NUMBER_RE = re.compile(r"\d+")


def next_release_number(published: list[str]) -> str:
    """The next automatic release's tag.

    `published` is the repo's published refs (tag names, any series —
    the workflow hands in the remote's whole tag list). Only the
    single-number tags enter the new series — a bare integer, no `v`
    prefix, no dots — and the result is the number after the highest
    one published: `1` where none is, else `N + 1` for the highest
    number `N`. Older `vX.Y.Z` tags are not numbers: they are ignored,
    which is what keeps the number series strictly increasing — never
    a repeat, never a decrease — next to the older tags."""
    nums = [int(t) for t in published if _NUMBER_RE.fullmatch(t)]
    return str((max(nums) if nums else 0) + 1)


def published_at(tag_lines: list[str], sha: str) -> list[str]:
    """The numbered tag names that point at `sha` — the
    one-tag-per-commit guard's pure computation.

    `tag_lines` is the raw `git ls-remote --tags` output, one
    `<sha>\trefs/tags/<name>` line per ref (an annotated tag adds a
    peeled `<sha>^{}` line beside its own). Only a bare-integer name on
    a line whose sha is `sha` itself matches: a peeled line is the tag
    object of an annotated tag, never the commit (and this flow's tags
    are lightweight, so their single line already carries the commit's
    sha), and the older `vX.Y.Z` series is not a number. The release
    workflow exits without publishing where the answer is non-empty — a
    re-run of the flow at an unchanged HEAD has nothing new to cut, and
    spending the next number on a duplicate of a published version is
    what would land a consumer pin written for that number on the
    duplicate instead of on the change."""
    names = []
    for line in tag_lines:
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        line_sha, ref = parts
        if line_sha != sha or ref.endswith("^{}") or not ref.startswith("refs/tags/"):
            continue
        name = ref[len("refs/tags/"):]
        if _NUMBER_RE.fullmatch(name):
            names.append(name)
    return sorted(names, key=int)


def main() -> None:
    """The CLI form — two input shapes:

    - default: one published ref (a tag name) per line on stdin; the
      next single-number tag on stdout (no refs at all → `1`);
    - `--published-at <sha>`: the raw `git ls-remote --tags` line list
      on stdin; the numbered tag names pointing at `<sha>`, one per line
      (none → empty output). The release workflow's guard tests the
      output's emptiness — non-empty, the flow exits before the tag."""
    args = sys.argv[1:]
    lines = [line.rstrip("\n") for line in sys.stdin if line.strip()]
    if "--published-at" in args:
        i = args.index("--published-at")
        if i + 1 >= len(args):
            raise SystemExit("usage: release-number.py [--published-at <sha>]")
        for name in published_at(lines, args[i + 1]):
            print(name)
        return
    print(next_release_number(lines))


if __name__ == "__main__":
    main()
