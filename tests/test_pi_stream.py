"""Unit tests for the pi output capture (the stage primitive's contract).

The factory's stages parse the captured model output (`pi-<template>.out`);
the capture must contain EVERY completed assistant message of the pi run,
not only the last one — a model observed delivering the review's
REVIEW-VERDICT block in a non-final turn and closing with a bare summary
made the old last-message-only capture parse zero verdicts and fail stage
10 on a fully reviewed run (run 40200905062).

Plain-python by design: every test is a no-argument function that raises on
failure. The same files run under pytest where it exists (plain functions
are valid pytest tests) and under the stdlib-only runner
`python3 tests/run.py` where it does not.
"""
from __future__ import annotations

import importlib.util
import json
import os

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", ".github", "scripts")

import sys

spec = importlib.util.spec_from_file_location(
    "common", os.path.join(SCRIPTS, "common.py"))
common = importlib.util.module_from_spec(spec)
sys.modules["common"] = common          # stage.py's `import common` reuses this
sys.path.insert(0, SCRIPTS)
spec.loader.exec_module(common)

_spec = importlib.util.spec_from_file_location(
    "cw_review_stage",
    os.path.join(os.path.dirname(__file__), "..", ".github", "actions",
                 "review-stage", "stage.py"))
stage = importlib.util.module_from_spec(_spec)
sys.modules["cw_review_stage"] = stage
_spec.loader.exec_module(stage)


def _assistant(content, total=0, stop="stop"):
    return {"type": "message_end",
            "message": {"role": "assistant", "content": content,
                         "usage": {"input": 10, "output": 5, "cacheRead": 0,
                                   "cacheWrite": 0, "reasoning": 0,
                                   "totalTokens": total},
                         "stopReason": stop}}


def test_stream_capture_reconstructs_every_assistant_message():
    # The failure shape: the verdict block rides a NON-final turn, the
    # final turn is a bare summary — text mode captured only the summary.
    raw = "\n".join([
        json.dumps({"type": "session", "version": 3, "id": "x",
                    "timestamp": "t", "cwd": "/w"}),
        json.dumps({"type": "agent_start"}),
        json.dumps({"type": "turn_start"}),
        json.dumps({"type": "message_end",
                    "message": {"role": "user", "content": "review it"}}),
        json.dumps(_assistant([{"type": "thinking", "thinking": "hm"},
                                {"type": "toolCall", "id": "c1",
                                 "toolName": "read"}], 100, stop="toolUse")),
        json.dumps({"type": "message_end",
                    "message": {"role": "toolResult",
                                 "content": "file body"}}),
        json.dumps(_assistant([{"type": "thinking", "thinking": "now"},
                                {"type": "text",
                                 "text": "REVIEW-VERDICT\n"
                                         "SCENARIO a.feature::S1: FULFILLED — ok\n"
                                         "END-REVIEW-VERDICT"}], 200)),
        json.dumps(_assistant([{"type": "text",
                                 "text": "The review is complete and "
                                         "delivered — my final message "
                                         "above carries the full result."}
                                ], 300)),
        json.dumps({"type": "agent_end", "messages": [], "willRetry": False}),
        json.dumps({"type": "agent_settled", "aborted": False}),
    ])
    is_jsonl, texts, usage, settled = common.pi_stream_capture(raw)
    assert is_jsonl, "a JSONL stream must be recognised as such"
    assert settled is True, "agent_settled must mark a completed stream"
    joined = "\n\n".join(t for t in texts if t.strip())
    assert "SCENARIO a.feature::S1: FULFILLED — ok" in joined, \
        "the verdict block in the non-final turn must survive the capture"
    assert "the full result" in joined, "the final turn must survive too"
    assert usage == 300, "budget usage = the LAST completed assistant message"


def test_stream_capture_splits_records_on_lf_only():
    # pi's JSONL framing: Unicode line separators inside JSON strings are
    # payload, not record boundaries — splitlines() would shred the record.
    text = "before\u2028after\u2029end"
    # ensure_ascii=False so the separator lands in the stream as RAW bytes
    # (Python's default would escape it to \\u2028, which is a different case)
    raw = "\n".join([
        json.dumps({"type": "agent_start"}),
        json.dumps(_assistant([{"type": "text", "text": text}], 7),
                   ensure_ascii=False),
    ])
    is_jsonl, texts, usage, settled = common.pi_stream_capture(raw)
    assert is_jsonl and not settled
    assert texts == [text], f"U+2028/U+2029 inside a string must stay in the record: {texts!r}"
    assert usage == 7


def test_stream_capture_survives_a_truncated_trailing_record():
    # A stream cut off mid-record: every COMPLETE record before the torn
    # line survives; the torn line is skipped, not fatal.
    complete = json.dumps(_assistant([{"type": "text", "text": "done work"}], 42))
    torn = json.dumps(_assistant([{"type": "text", "text": "never arrived"}], 99))
    raw = f"{json.dumps({'type': 'agent_start'})}\n{complete}\n{torn[:len(torn) // 2]}"
    is_jsonl, texts, usage, settled = common.pi_stream_capture(raw)
    assert is_jsonl
    assert settled is False, "no agent_settled: the stream died mid-flight"
    assert texts == ["done work"], "complete turns survive the torn trailing line"
    assert usage == 42


def test_stream_capture_non_json_stream_is_passthrough():
    # An older pi build answering in plain text: not a JSONL stream — the
    # raw capture is kept as-is (the caller's legacy path).
    raw = "plain final answer text"
    is_jsonl, texts, usage, settled = common.pi_stream_capture(raw)
    assert is_jsonl is False
    assert texts == [] and usage == 0 and settled is False


def test_stream_capture_ignores_non_assistant_message_ends():
    raw = "\n".join([
        json.dumps({"type": "message_end",
                    "message": {"role": "system", "content": "sys prompt"}}),
        json.dumps({"type": "message_end",
                    "message": {"role": "user", "content": "the prompt"}}),
        json.dumps(_assistant([{"type": "text", "text": "the answer"}], 3)),
    ])
    _, texts, usage, _ = common.pi_stream_capture(raw)
    assert texts == ["the answer"], "only assistant messages are model output"
    assert usage == 3


def test_parse_verdicts_dedupes_repeated_scenarios_last_wins():
    # Every-assistant-message capture: a model repeating (or correcting) a
    # verdict line across turns must not double-report the scenario.
    text = (
        "SCENARIO a.feature::S1: UNFULFILLED — first draft says missing\n"
        "SCENARIO a.feature::S2: FULFILLED — test passes\n"
        "later turn, corrected:\n"
        "SCENARIO a.feature::S1: FULFILLED — actually present in the code\n"
    )
    v = stage.parse_verdicts(text)
    assert v == [("a.feature", "S1", "FULFILLED"),
                 ("a.feature", "S2", "FULFILLED")], \
        f"dedupe on (file, name), the LATER verdict wins: {v}"


def test_parse_verdicts_still_accepts_em_dash_and_qualifier():
    # Regression guard for the pre-existing tolerance: an em dash where the
    # format wants a colon, and a parenthetical verdict qualifier.
    text = (
        "SCENARIO a.feature::S1 — FULFILLED (orchestration) —\n"
        "SCENARIO b.feature::S2: UNFULFILLED — what's missing\n"
    )
    v = stage.parse_verdicts(text)
    assert v == [("a.feature", "S1", "FULFILLED"),
                 ("b.feature", "S2", "UNFULFILLED")], f"{v}"


def test_text_mode_fallback_when_pi_rejects_mode_flag():
    # A runner whose pre-installed pi predates `--mode` rejects the flag at
    # startup (before any model call). pi_invoke must retry the ONE call in
    # plain text mode — the stage keeps working on the legacy capture —
    # instead of failing the stage as a broken environment.
    import shutil
    import tempfile
    fake = tempfile.mkdtemp()
    state = tempfile.mkdtemp()
    saved = {k: os.environ.get(k) for k in
             ("PATH", "RUNNER_TEMP", "GITHUB_WORKSPACE", "MAX_TOKENS")}
    os.makedirs(os.path.join(fake, "bin"), exist_ok=True)
    pi_path = os.path.join(fake, "bin", "pi")
    with open(pi_path, "w") as f:
        f.write(
            "#!%s\n" % sys.executable +
            "import sys\n"
            "if '--mode' in sys.argv[1:]:\n"
            "    print(\"error: unknown option '--mode'\", file=sys.stderr)\n"
            "    sys.exit(1)\n"
            "print('42 in, 7 out, 0 cache read, 49 total tok', file=sys.stderr)\n"
            "print('plain text answer')\n")
    os.chmod(pi_path, 0o755)
    os.environ["PATH"] = os.path.join(fake, "bin") + os.pathsep + (saved["PATH"] or "")
    os.environ["RUNNER_TEMP"] = state
    os.environ["GITHUB_WORKSPACE"] = state
    os.environ["MAX_TOKENS"] = "1000"
    sp = os.path.join(state, "review.md")
    with open(sp, "w") as f:
        f.write("instructions")
    try:
        r = common.pi_invoke("Model", sp, timeout=60)
        assert r.returncode == 0, \
            "the text-mode retry must run to completion, got exit %s" % r.returncode
        out = open(os.path.join(state, "cw", "pi-review.md.out")).read()
        assert "plain text answer" in out, \
            "a text-mode stream keeps the raw capture (legacy contract)"
        assert not os.path.exists(
            os.path.join(state, "cw", "pi-review.md.settled")), \
            "a text-mode build writes no settled marker (stages fall back " \
            "to the legacy no-output retry heuristic)"
        toks = open(os.path.join(state, "cw", "tokens.txt")).read().split()
        assert toks == ["49"], \
            "the legacy stderr usage summary still counts toward the budget"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(fake, ignore_errors=True)
        shutil.rmtree(state, ignore_errors=True)
