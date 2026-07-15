#!/usr/bin/env python3
"""Parse and score raw Home TAP benchmark outputs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmark_utils import (
    best_explicit_score,
    implicit_score,
    iter_benchmark_requests,
    load_home_environment,
    load_json,
    parse_tap_from_text,
    read_jsonl,
    structural_validity,
    write_jsonl,
)


def build_gt_indexes(gt_data: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    by_request_id: Dict[str, Dict[str, Any]] = {}
    by_request: Dict[str, Dict[str, Any]] = {}
    for item in iter_benchmark_requests(gt_data):
        row = {
            "index": item["index"],
            "request_key": item["request_key"],
            "request": item["request"],
            "request_id": item["request_id"],
            "home_id": item["home_id"],
            "category": item["category"],
            "entry": item["entry"],
        }
        by_request_id[str(item["request_id"])] = row
        by_request[item["request"].strip().lower()] = row
    return {"by_request_id": by_request_id, "by_request": by_request}


def find_gt(raw: Dict[str, Any], indexes: Dict[str, Dict[str, Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    request_id = raw.get("request_id")
    if request_id and str(request_id) in indexes["by_request_id"]:
        return indexes["by_request_id"][str(request_id)]
    request = str(raw.get("request", "")).strip().lower()
    if request in indexes["by_request"]:
        return indexes["by_request"][request]
    return None


def load_ha_metrics(path: Optional[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Load HA internal metrics, indexed by normalized user_request."""
    if not path:
        return {}
    rows_by_request: Dict[str, List[Dict[str, Any]]] = {}
    metrics_path = Path(path)
    if not metrics_path.exists():
        return {}
    with metrics_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            request = str(row.get("user_request", "")).strip().lower()
            if not request:
                continue
            rows_by_request.setdefault(request, []).append(row)
    return rows_by_request


def load_ha_token_usage(path: Optional[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Load HA token_usage.jsonl, indexed by normalized user_request."""
    if not path:
        return {}
    rows_by_request: Dict[str, List[Dict[str, Any]]] = {}
    token_path = Path(path)
    if not token_path.exists():
        return {}
    with token_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            request = str(row.get("user_request", "")).strip().lower()
            if not request:
                continue
            rows_by_request.setdefault(request, []).append(row)
    return rows_by_request


def _row_timestamp(row: Dict[str, Any]) -> Optional[datetime]:
    ts = row.get("timestamp") or row.get("ts")
    if not ts:
        return None
    return datetime.fromisoformat(str(ts))


def _raw_timestamp(raw: Dict[str, Any]) -> Optional[datetime]:
    ts = raw.get("timestamp")
    if not ts:
        return None
    return datetime.fromisoformat(str(ts))


def pick_row_for_raw(
    raw: Dict[str, Any],
    rows: List[Dict[str, Any]],
    *,
    max_delta_sec: float = 300.0,
) -> Optional[Dict[str, Any]]:
    """Pick the HA metrics/token row from the same benchmark invocation as this raw row."""
    if not rows:
        return None
    raw_ts = _raw_timestamp(raw)
    if raw_ts is None:
        return rows[-1]

    best: Optional[Dict[str, Any]] = None
    best_delta: Optional[float] = None
    for row in rows:
        row_ts = _row_timestamp(row)
        if row_ts is None:
            continue
        delta = abs((row_ts - raw_ts).total_seconds())
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best = row

    if best is None or best_delta is None:
        return rows[-1]
    if best_delta > max_delta_sec:
        return None
    return best


def find_ha_metrics(raw: Dict[str, Any], rows_by_request: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    request = str(raw.get("request", "")).strip().lower()
    rows = rows_by_request.get(request) or []
    return pick_row_for_raw(raw, rows)


def find_ha_token_usage(raw: Dict[str, Any], rows_by_request: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    request = str(raw.get("request", "")).strip().lower()
    rows = rows_by_request.get(request) or []
    return pick_row_for_raw(raw, rows)


def merge_ha_metric_sources(
    metrics_row: Optional[Dict[str, Any]],
    token_row: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Merge metrics.jsonl and token_usage.jsonl rows for one benchmark request."""
    if metrics_row:
        merged = dict(metrics_row)
        if token_row:
            for key, token_key in [
                ("total_prompt_tokens", "prompt_tokens"),
                ("total_completion_tokens", "completion_tokens"),
                ("total_tokens", "total_tokens"),
            ]:
                if merged.get(key) in (None, 0) and token_row.get(token_key) is not None:
                    merged[key] = token_row.get(token_key)
            if not merged.get("request_id") and token_row.get("request_id"):
                merged["request_id"] = token_row.get("request_id")
            if not merged.get("timestamp") and token_row.get("ts"):
                merged["timestamp"] = token_row.get("ts")
        return merged
    if not token_row:
        return None
    return {
        "request_id": token_row.get("request_id"),
        "timestamp": token_row.get("ts"),
        "user_request": token_row.get("user_request"),
        "success": None,
        "total_time_sec": None,
        "total_prompt_tokens": token_row.get("prompt_tokens"),
        "total_completion_tokens": token_row.get("completion_tokens"),
        "total_tokens": token_row.get("total_tokens"),
        "capability_grounding": {},
        "tap_correctness": None,
    }


def extract_ha_metrics(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    grounding = row.get("capability_grounding", {})
    if not isinstance(grounding, dict):
        grounding = {}
    preferred_stage = None
    for stage in [
        "homegenii_context_retrieve",
        "autoiot_generate",
        "subgraph_full_full_graph",
        "subgraph_full",
        "subgraph",
        "preprocess",
        "early_pruning",
        "filter_output",
        "sasha_filter",
        "sasha_plan_tap",
        "tap_output",
        "kg_recall",
        "clarify_reject",
    ]:
        if isinstance(grounding.get(stage), dict):
            preferred_stage = stage
            break
    selected = grounding.get(preferred_stage, {}) if preferred_stage else {}
    if not isinstance(selected, dict):
        selected = {}
    attempted = True
    return {
        "ha_request_id": row.get("request_id"),
        "ha_timestamp": row.get("timestamp"),
        "pipeline_success": row.get("success"),
        "pipeline_total_time_sec": row.get("total_time_sec"),
        "total_prompt_tokens": row.get("total_prompt_tokens"),
        "total_completion_tokens": row.get("total_completion_tokens"),
        "total_tokens": row.get("total_tokens"),
        "grounding_stage": preferred_stage,
        "grounding_attempted": attempted,
        "device_precision": selected.get("device_precision", 0.0),
        "device_recall": selected.get("device_recall", 0.0),
        "capability_precision": selected.get("capability_precision", 0.0),
        "capability_recall": selected.get("capability_recall", 0.0),
        "capability_grounding": grounding,
        "tap_correctness": row.get("tap_correctness"),
    }


def _join_atoms(atoms: Any, sep: str) -> str:
    if not isinstance(atoms, list):
        return ""
    return sep.join(str(atom) for atom in atoms if str(atom).strip())


def tap_from_ha_metrics(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Recover generated TAP atoms from HA internal tap_correctness details."""
    if not isinstance(row, dict):
        return None
    tc = row.get("tap_correctness")
    if not isinstance(tc, dict):
        return None
    details = tc.get("details")
    if not isinstance(details, dict):
        return None
    tap = {
        "trigger": _join_atoms(details.get("gen_trigger"), " and "),
        "condition": _join_atoms(details.get("gen_condition"), " and "),
        "action": _join_atoms(details.get("gen_action"), ", "),
    }
    if any(tap.values()):
        return tap
    return None


def score_one(
    raw: Dict[str, Any],
    gt_row: Optional[Dict[str, Any]],
    ha_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response_text = str(raw.get("response_text", "") or "")
    parsed_tap, parse_error = parse_tap_from_text(response_text)
    tap_source = "response_text"
    if parsed_tap is None:
        parsed_tap = tap_from_ha_metrics(ha_metrics)
        if parsed_tap is not None:
            tap_source = "ha_metrics"
            parse_error = "response text did not contain TAP; recovered generated TAP from HA metrics"
    home_env = load_home_environment(str(raw.get("home_id") or (gt_row or {}).get("home_id") or ""))
    validity = structural_validity(
        parsed_tap,
        home_env=home_env,
        response_text=response_text,
        pipeline_success=ha_metrics.get("success") if ha_metrics else None,
        pipeline_error=ha_metrics.get("error") if ha_metrics else None,
    )

    base = {
        "run_id": raw.get("run_id"),
        "method": raw.get("method"),
        "agent_id": raw.get("agent_id"),
        "base_url": raw.get("base_url"),
        "timestamp": raw.get("timestamp"),
        "index": raw.get("index"),
        "request_id": raw.get("request_id"),
        "home_id": raw.get("home_id"),
        "category": raw.get("category"),
        "request": raw.get("request"),
        "api_ok": raw.get("ok"),
        "api_status": raw.get("status"),
        "elapsed_ms": raw.get("elapsed_ms"),
        "parse_error": parse_error,
        "tap_source": tap_source if parsed_tap is not None else "",
        "parsed_tap": parsed_tap,
        "structural_validity": validity,
        "ha_metrics": extract_ha_metrics(ha_metrics),
        "raw_error": raw.get("error", ""),
    }

    if not gt_row:
        base.update(
            {
                "scoring_error": "ground truth entry not found",
                "explicit_intent": None,
                "implicit_constraints": None,
                "executable_correctness": None,
            }
        )
        return base

    entry = gt_row["entry"]
    base.update(
        {
            "request_id": gt_row["request_id"],
            "home_id": gt_row["home_id"],
            "category": gt_row["category"],
        }
    )

    if not parsed_tap:
        explicit = {"score": 0, "precision": 0.0, "recall": 0.0, "details": {"missing": "no parsed TAP"}}
        implicit = implicit_score(entry, {})
    else:
        explicit = best_explicit_score(entry, parsed_tap)
        implicit = implicit_score(entry, parsed_tap)

    executable_correctness = 1 if (
        validity.get("score") == 1
        and explicit.get("score") == 1
        and (not implicit.get("applicable") or implicit.get("score") == 1)
    ) else 0
    base.update(
        {
            "explicit_intent": explicit,
            "implicit_constraints": implicit,
            "executable_correctness": {
                "score": executable_correctness,
                "structural_validity_score": validity.get("score"),
                "explicit_intent_score": explicit.get("score"),
                "implicit_constraint_score": implicit.get("score"),
            },
            "scoring_error": "",
        }
    )
    return base


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score raw TAP benchmark outputs.")
    parser.add_argument("--raw", required=True, help="Raw outputs JSONL from run_ha_agent.py.")
    parser.add_argument("--ground-truth", required=True, help="Benchmark ground truth JSON.")
    parser.add_argument("--output", required=True, help="Scored JSONL output path.")
    parser.add_argument("--parsed-output", default=None, help="Optional parsed TAP JSONL path.")
    parser.add_argument(
        "--ha-metrics-jsonl",
        default=None,
        help="Optional HA internal metrics JSONL, e.g. config_home_S/.storage/kgiot/metrics.jsonl.",
    )
    parser.add_argument(
        "--ha-token-jsonl",
        default=None,
        help="Optional HA token_usage.jsonl fallback when metrics.jsonl is missing or incomplete.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_rows = read_jsonl(Path(args.raw))
    indexes = build_gt_indexes(load_json(Path(args.ground_truth)))
    ha_metrics_by_request = load_ha_metrics(args.ha_metrics_jsonl)
    ha_token_by_request = load_ha_token_usage(args.ha_token_jsonl)
    scored = [
        score_one(
            row,
            find_gt(row, indexes),
            merge_ha_metric_sources(
                find_ha_metrics(row, ha_metrics_by_request),
                find_ha_token_usage(row, ha_token_by_request),
            ),
        )
        for row in raw_rows
    ]
    write_jsonl(Path(args.output), scored)

    if args.parsed_output:
        parsed_rows = [
            {
                "method": row.get("method"),
                "request_id": row.get("request_id"),
                "home_id": row.get("home_id"),
                "category": row.get("category"),
                "request": row.get("request"),
                "parsed_tap": row.get("parsed_tap"),
                "parse_error": row.get("parse_error"),
            }
            for row in scored
        ]
        write_jsonl(Path(args.parsed_output), parsed_rows)

    n = len(scored)
    explicit = [row["explicit_intent"]["score"] for row in scored if isinstance(row.get("explicit_intent"), dict)]
    executable = [
        row["executable_correctness"]["score"]
        for row in scored
        if isinstance(row.get("executable_correctness"), dict)
    ]
    implicit = [
        row["implicit_constraints"]["completion"]
        for row in scored
        if isinstance(row.get("implicit_constraints"), dict)
        and row["implicit_constraints"].get("completion") is not None
    ]
    print(f"Saved scores: {args.output}")
    print(f"Rows: {n}")
    if executable:
        print(f"Executable correctness: {sum(executable) / len(executable):.1%}")
    if explicit:
        print(f"Explicit-intent score: {sum(explicit) / len(explicit):.1%}")
    if implicit:
        print(f"Implicit-constraint completion: {sum(implicit) / len(implicit):.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
