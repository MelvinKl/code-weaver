#!/usr/bin/env python3
"""The single guard script (plan §4.1) — invoked three times with different
allowed paths.

  guard-check.py <baseline-ref> <allowed-path>… [! <denied-path>…]

exit 0 → clean stage (everything changed is inside the allowed paths)
exit 1 → violations found: the offending files were reverted exactly
(modified files checked out from the baseline, untracked ones cleaned); the
calling stage re-runs its generation.

Plain entries admit. A `!` section marker switches to inverted-allow
entries, which DENY: the implementation guard's lane is "everything except
the protected set" (its call passes deny = {requirements, plans} +
allow = {this issue's plan file, `__pycache__`}) — a changed file is a
violation when it is denied AND no allow entry admits it (the deny set is
matched by prefix, the allow set also admits paths that carry an allow
entry as a component). The other stages' whitelist calls pass plain
entries only, where a denied file is one no allow entry matches.

Canonical implementation lives in .github/scripts/common.py (shared by every
stage); this file is a thin entry point so the guard is one self-contained
script. If the scripts dir is not materialised next to this action (degenerate
sparse checkout), an inline fallback with identical semantics is used."""
from __future__ import annotations

import os
import sys


def _load():
    here = os.path.dirname(os.path.abspath(__file__))
    scripts = os.path.join(os.path.dirname(os.path.dirname(here)), "scripts")
    if os.path.isdir(scripts):
        sys.path.insert(0, scripts)
        from common import changed_files, guard, main_guard_cli  # noqa: PLC0411
        return main_guard_cli
    # Fallback: same idiom, self-contained (only reached if the sibling
    # scripts/ dir is absent from the checkout).
    import dataclasses
    import subprocess

    def changed_files(baseline: str):
        tracked = subprocess.run(
            ["git", "diff", "--name-only", baseline, "--", "."],
            cwd=os.environ["GITHUB_WORKSPACE"], capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=os.environ["GITHUB_WORKSPACE"], capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        return sorted(set(tracked + untracked))

    def guard_denied(f, allow, deny):
        # Identical to common.guard_denied (see there for the semantics).
        allow = [a.rstrip("/") for a in allow if a]
        deny = [a.rstrip("/") for a in deny if a]
        if not any(f == a or f.startswith(a + "/") or a in f.split("/")
                   for a in allow):
            if not deny:
                return True
            return any(f == d or f.startswith(d + "/") for d in deny)
        return False

    @dataclasses.dataclass
    class GuardResult:
        ok: bool
        violations: list

    def guard(baseline: str, allow, deny=()):
        allow = [a.rstrip("/") for a in allow if a]
        deny = [a.rstrip("/") for a in deny if a]
        violations = [f for f in changed_files(baseline)
                      if guard_denied(f, allow, deny)]
        if not violations:
            print(f"guard: OK — only {' '.join(allow) or '(baseline)'} changed", flush=True)
            return GuardResult(True, [])
        for f in violations:
            exists_at_baseline = subprocess.run(
                ["git", "cat-file", "-e", f"{baseline}:{f}"],
                cwd=os.environ["GITHUB_WORKSPACE"], capture_output=True, text=True,
            ).returncode == 0
            if exists_at_baseline:
                subprocess.run(["git", "checkout", baseline, "--", f],
                               cwd=os.environ["GITHUB_WORKSPACE"], check=True)
            elif subprocess.run(["git", "ls-files", "--", f],
                                cwd=os.environ["GITHUB_WORKSPACE"],
                                capture_output=True, text=True).stdout.strip():
                subprocess.run(["git", "rm", "-f", "--", f],
                               cwd=os.environ["GITHUB_WORKSPACE"], check=True)
            else:
                p = os.path.join(os.environ["GITHUB_WORKSPACE"], f)
                if os.path.isdir(p):
                    subprocess.run(["git", "clean", "-fdq", "--", f],
                                   cwd=os.environ["GITHUB_WORKSPACE"])
                elif os.path.exists(p):
                    os.remove(p)
        print(f"::error::guard: REVERTED off-limits files: {' '.join(violations)}", flush=True)
        return GuardResult(False, violations)

    def main_guard_cli():
        args = sys.argv[1:]
        if not args or args[0] in ("-h", "--help"):
            print("usage: guard-check.py <baseline-ref> <allowed-path>… "
                  "[! <denied-path>…]")
            sys.exit(2)
        baseline = args[0]
        tail = args[1:]
        if "!" in tail:
            i = tail.index("!")
            allow, deny = tail[:i], [a for a in tail[i + 1:] if a]
        else:
            allow, deny = tail, []
        r = guard(baseline, allow, deny)
        sys.exit(0 if r.ok else 1)

    return main_guard_cli


if __name__ == "__main__":
    _load()()
