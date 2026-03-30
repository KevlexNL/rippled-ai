"""Signal Trace Inspector CLI — WO-RIPPLED-SIGNAL-TRACE-INSPECTOR.

Trace a source item through each pipeline stage and output a structured report.

Usage:
    python scripts/trace_signal.py --id <source_item_id>
    python scripts/trace_signal.py --sample --type email --count 3
    python scripts/trace_signal.py --sample --type slack --count 2
    python scripts/trace_signal.py --sample --type meeting --count 2
    python scripts/trace_signal.py --sample --type email --count 3 --json
"""
from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, ".")

from app.db.session import get_sync_session
from app.services.trace import fetch_samples, trace_source_item


# ---------------------------------------------------------------------------
# Terminal formatting
# ---------------------------------------------------------------------------

_COLORS = {
    "green": "\033[92m",
    "amber": "\033[93m",
    "red": "\033[91m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}

_VERDICT_COLORS = {
    "commitment_created": "green",
    "candidate_promoted": "green",
    "candidate_pending": "amber",
    "rejected_as_noise": "red",
    "no_candidates_created": "red",
    "not_processed": "dim",
    "unknown": "dim",
}

_STAGE_STATUS_COLORS = {
    "loaded": "green",
    "complete": "green",
    "matched": "green",
    "found": "green",
    "commitment_created": "green",
    "promoted": "green",
    "no_match": "amber",
    "no_audit_records": "amber",
    "no_candidates": "red",
    "not_promoted": "red",
    "no_commitments": "dim",
    "no_clarification_records": "dim",
    "no_commitment": "red",
}


def _c(color: str, text: str) -> str:
    return f"{_COLORS.get(color, '')}{text}{_COLORS['reset']}"


def _print_stage(stage: dict) -> None:
    name = stage["stage"]
    status = stage["status"]
    data = stage.get("data", {})

    color = _STAGE_STATUS_COLORS.get(status, "dim")
    print(f"\n  {_c('bold', name.upper())} — {_c(color, status)}")

    if name == "raw":
        d = data
        print(f"    Source: {d.get('source_type')}  Sender: {d.get('sender_name') or d.get('sender_email') or '?'}")
        print(f"    Direction: {d.get('direction')}  Date: {d.get('occurred_at')}")
        print(f"    Content length: {d.get('content_length')} chars  External: {d.get('is_external')}")
        preview = d.get("content_preview", "")
        if preview:
            print(f"    Preview: {_c('dim', preview[:200])}")

    elif name == "normalization":
        d = data
        print(f"    Suppression patterns: {d.get('suppression_patterns_applied')}")
        spans = d.get("suppressed_spans", [])
        if spans:
            for s in spans[:5]:
                print(f"      Stripped [{s['pattern']}]: {_c('dim', s['matched_text'][:80])}")
        print(f"    Raw → Normalized: {d.get('raw_length')} → {d.get('normalized_length')} chars")

    elif name == "pattern_detection":
        d = data
        print(f"    Patterns checked: {d.get('patterns_checked')}  Matches: {d.get('matches_found')}")
        for m in d.get("matches", [])[:10]:
            conf = m.get("base_confidence", 0)
            print(f"      {_c('cyan', m['pattern_name'])} ({m['trigger_class']}) "
                  f"conf={conf:.2f}  → {_c('dim', m['matched_text'][:100])}")

    elif name == "llm_detection":
        audits = data.get("audits", [])
        for a in audits:
            print(f"    Tier: {a['tier_used']}  Model: {a.get('model') or '—'}  "
                  f"Prompt: {a.get('prompt_version') or '—'}  "
                  f"Tokens: {a.get('tokens_in') or 0}/{a.get('tokens_out') or 0}  "
                  f"Cost: ${a.get('cost_estimate') or 0:.4f}")
            if a.get("raw_prompt"):
                prompt_preview = a["raw_prompt"][:300]
                print(f"    Prompt: {_c('dim', prompt_preview)}")
            if a.get("raw_response"):
                resp_preview = a["raw_response"][:300]
                print(f"    Response: {_c('dim', resp_preview)}")
            if a.get("error_detail"):
                print(f"    {_c('red', 'Error: ' + a['error_detail'])}")

    elif name == "extraction":
        candidates = data.get("candidates", [])
        for c in candidates:
            print(f"    Candidate {_c('dim', str(c.get('id', ''))[:8])}  "
                  f"trigger={c.get('trigger_class')}  conf={c.get('confidence_score')}  "
                  f"method={c.get('detection_method')}")
            if c.get("raw_text"):
                print(f"      Text: {_c('dim', c['raw_text'][:150])}")

    elif name == "candidate_decision":
        for d in data.get("decisions", []):
            symbol = {"promoted": _c("green", "PROMOTED"), "discarded": _c("red", "DISCARDED"),
                      "pending": _c("amber", "PENDING")}.get(d["decision"], d["decision"])
            print(f"    {str(d['candidate_id'])[:8]} → {symbol}  ({d['reason']})")

    elif name == "clarification":
        for cl in data.get("clarifications", []):
            issues = ", ".join(cl.get("issue_types", []))
            print(f"    Issues: {issues}  Severity: {cl.get('issue_severity')}")
            print(f"    Recommendation: {cl.get('surface_recommendation')}")
            if cl.get("suggested_values"):
                print(f"    Suggestions: {json.dumps(cl['suggested_values'], default=str)[:200]}")

    elif name == "final_state":
        for cm in data.get("commitments", []):
            print(f"    {_c('green', cm.get('title', '?'))}")
            print(f"      Type: {cm.get('commitment_type')}  State: {cm.get('lifecycle_state')}  "
                  f"Priority: {cm.get('priority_class')}")
            print(f"      Owner: {cm.get('resolved_owner') or '?'}  "
                  f"Deadline: {cm.get('resolved_deadline') or '?'}")
            print(f"      Surfaced: {cm.get('is_surfaced')}  Score: {cm.get('priority_score')}")


def _print_trace(trace: dict) -> None:
    sid = trace["source_item_id"]
    verdict = trace["verdict"]
    vcolor = _VERDICT_COLORS.get(verdict, "dim")

    print(f"\n{'═' * 70}")
    print(f"  TRACE: {_c('bold', sid[:8])}…  Verdict: {_c(vcolor, verdict.upper())}")
    print(f"{'═' * 70}")

    for stage in trace["stages"]:
        _print_stage(stage)

    print(f"\n{'─' * 70}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Signal Trace Inspector — trace source items through the detection pipeline"
    )
    parser.add_argument("--id", type=str, help="Trace a specific source_item by ID")
    parser.add_argument("--sample", action="store_true", help="Sample recent items")
    parser.add_argument("--type", type=str, choices=["email", "slack", "meeting"],
                        help="Source type to sample (used with --sample)")
    parser.add_argument("--count", type=int, default=3, help="Number of items to sample (default: 3)")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    args = parser.parse_args()

    if not args.id and not args.sample:
        parser.print_help()
        sys.exit(1)

    if args.id:
        with get_sync_session() as db:
            trace = trace_source_item(args.id, db)
        if args.json_output:
            print(json.dumps(trace, indent=2, default=str))
        else:
            _print_trace(trace)

    elif args.sample:
        with get_sync_session() as db:
            samples = fetch_samples(args.type, args.count, db)
            if not samples:
                print(f"No source items found for type={args.type or 'all'}")
                sys.exit(0)

            traces = []
            for s in samples:
                trace = trace_source_item(s["id"], db)
                traces.append(trace)

        if args.json_output:
            print(json.dumps(traces, indent=2, default=str))
        else:
            print(f"\nTracing {len(traces)} {args.type or 'all'} item(s):\n")
            for trace in traces:
                _print_trace(trace)


if __name__ == "__main__":
    main()
