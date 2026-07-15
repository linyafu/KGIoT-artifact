#!/usr/bin/env python3
"""Summarize scored TAP benchmark outputs into CSV tables and failure notes."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from benchmark_utils import read_jsonl


CATEGORY_ORDER = [
    "Basic TAP",
    "Conditional TAP",
    "Multi-Action TAP",
    "Constraint-Aware TAP",
]


def category_sort_key(category: str) -> tuple[int, int | str]:
    try:
        return (0, CATEGORY_ORDER.index(category))
    except ValueError:
        return (1, category)


def mean(values: Iterable[Optional[float]]) -> Optional[float]:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def is_vanilla_method(method: str) -> bool:
    return "vanilla" in method.lower()


def has_grounding_step(method: str) -> bool:
    """Only methods with an explicit context retrieval/filter stage report grounding metrics."""
    lowered = method.lower()
    if is_vanilla_method(method):
        return False
    if "autoiot" in lowered:
        return False
    return True


def metric_values(rows: List[Dict[str, Any]], *, include_grounding: bool = True) -> Dict[str, Optional[float]]:
    executable = [
        row.get("executable_correctness", {}).get("score")
        for row in rows
        if isinstance(row.get("executable_correctness"), dict)
    ]
    explicit = [
        row.get("explicit_intent", {}).get("score")
        for row in rows
        if isinstance(row.get("explicit_intent"), dict)
    ]
    implicit = [
        row.get("implicit_constraints", {}).get("completion")
        for row in rows
        if isinstance(row.get("implicit_constraints"), dict)
        and row.get("implicit_constraints", {}).get("completion") is not None
    ]
    structural = [
        row.get("structural_validity", {}).get("score")
        for row in rows
        if isinstance(row.get("structural_validity"), dict)
    ]
    ha_metrics = [row.get("ha_metrics") for row in rows if isinstance(row.get("ha_metrics"), dict)]
    out = {
        "n": len(rows),
        "executable_correctness": mean(executable),
        "structural_validity": mean(structural),
        "explicit_intent_score": mean(explicit),
        "implicit_constraint_completion": mean(implicit),
        "avg_e2e_latency_ms": mean([row.get("elapsed_ms") for row in rows]),
        "avg_total_tokens": mean([m.get("total_tokens") for m in ha_metrics]),
    }
    if include_grounding:
        out.update(
            {
                "device_precision": mean([m.get("device_precision") for m in ha_metrics]),
                "device_recall": mean([m.get("device_recall") for m in ha_metrics]),
                "capability_precision": mean([m.get("capability_precision") for m in ha_metrics]),
                "capability_recall": mean([m.get("capability_recall") for m in ha_metrics]),
            }
        )
    return out


def fmt(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return value


def method_label(path: Path, rows: List[Dict[str, Any]]) -> str:
    for row in rows:
        if row.get("method"):
            return str(row["method"])
    return path.stem.replace("_scores", "")


def write_csv(path: Path, rows: List[Dict[str, Any]], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt(row.get(field)) for field in fields})


def failure_reason(row: Dict[str, Any]) -> str:
    if row.get("parse_error"):
        return "parse_error"
    if isinstance(row.get("structural_validity"), dict) and row["structural_validity"].get("score") == 0:
        return "structural_invalid"
    if isinstance(row.get("explicit_intent"), dict) and row["explicit_intent"].get("score") == 0:
        return "explicit_intent_failed"
    if (
        isinstance(row.get("implicit_constraints"), dict)
        and row["implicit_constraints"].get("applicable")
        and row["implicit_constraints"].get("score") == 0
    ):
        return "implicit_constraint_missing"
    if isinstance(row.get("executable_correctness"), dict) and row["executable_correctness"].get("score") == 0:
        return "executable_incorrect"
    return ""


def _format_tap_for_markdown(tap: Any) -> List[str]:
    if not isinstance(tap, dict):
        return ["  Parsed TAP: null"]
    fields = {
        "trigger": tap.get("trigger", ""),
        "condition": tap.get("condition", ""),
        "action": tap.get("action", ""),
    }
    return [
        "  Parsed TAP:",
        "  ```json",
        f"  {fmt_json(fields)}",
        "  ```",
    ]


def fmt_json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def write_failures(path: Path, all_rows: Dict[str, List[Dict[str, Any]]]) -> None:
    lines: List[str] = ["# Failure Cases", ""]
    for method, rows in sorted(all_rows.items()):
        failures = [row for row in rows if failure_reason(row)]
        lines.append(f"## {method}")
        lines.append("")
        if not failures:
            lines.append("No failures detected by the automatic scorer.")
            lines.append("")
            continue
        for row in failures:
            reason = failure_reason(row)
            lines.append(f"- `{row.get('request_id')}` [{row.get('category')}] {reason}: {row.get('request')}")
            tap_source = row.get("tap_source") or ""
            if tap_source:
                lines.append(f"  TAP source: `{tap_source}`")
            parse_error = row.get("parse_error")
            if parse_error:
                lines.append(f"  Parse error: {parse_error}")
            lines.extend(_format_tap_for_markdown(row.get("parsed_tap")))

            structural = row.get("structural_validity", {})
            if isinstance(structural, dict) and structural.get("errors"):
                lines.append(f"  Structural errors: {structural.get('errors')}")

            explicit = row.get("explicit_intent", {})
            details = explicit.get("details", {}) if isinstance(explicit, dict) else {}
            if details.get("missing_atoms") or details.get("extra_atoms"):
                lines.append(f"  Missing explicit atoms: {details.get('missing_atoms', [])}")
                lines.append(f"  Extra explicit atoms: {details.get('extra_atoms', [])}")

            implicit = row.get("implicit_constraints", {})
            if isinstance(implicit, dict) and implicit.get("applicable"):
                lines.append(f"  Missing dependencies: {implicit.get('missing_dependencies', [])}")
                lines.append(f"  Missing interlocks: {implicit.get('missing_interlocks', [])}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize TAP benchmark score JSONL files.")
    parser.add_argument("--scores", nargs="+", required=True, help="One or more score JSONL files.")
    parser.add_argument("--output-dir", required=True, help="Directory for CSV/Markdown results.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    all_rows: Dict[str, List[Dict[str, Any]]] = {}
    main_rows: List[Dict[str, Any]] = []
    category_rows: List[Dict[str, Any]] = []
    per_case_rows: List[Dict[str, Any]] = []

    for score_path_str in args.scores:
        score_path = Path(score_path_str)
        rows = read_jsonl(score_path)
        method = method_label(score_path, rows)
        all_rows[method] = rows
        include_grounding = has_grounding_step(method)

        main = {"method": method, "score_file": str(score_path), **metric_values(rows, include_grounding=include_grounding)}
        main_rows.append(main)

        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row.get("category") or "unknown")].append(row)
            per_case_rows.append(
                {
                    "method": method,
                    "request_id": row.get("request_id"),
                    "home_id": row.get("home_id"),
                    "category": row.get("category"),
                    "request": row.get("request"),
                    "executable_correctness": row.get("executable_correctness", {}).get("score")
                    if isinstance(row.get("executable_correctness"), dict)
                    else None,
                    "structural_validity": row.get("structural_validity", {}).get("score")
                    if isinstance(row.get("structural_validity"), dict)
                    else None,
                    "explicit_intent_score": row.get("explicit_intent", {}).get("score")
                    if isinstance(row.get("explicit_intent"), dict)
                    else None,
                    "implicit_constraint_completion": row.get("implicit_constraints", {}).get("completion")
                    if isinstance(row.get("implicit_constraints"), dict)
                    else None,
                    "e2e_latency_ms": row.get("elapsed_ms"),
                    "total_tokens": row.get("ha_metrics", {}).get("total_tokens")
                    if isinstance(row.get("ha_metrics"), dict)
                    else None,
                    **(
                        {
                            "device_precision": row.get("ha_metrics", {}).get("device_precision")
                            if isinstance(row.get("ha_metrics"), dict)
                            else None,
                            "device_recall": row.get("ha_metrics", {}).get("device_recall")
                            if isinstance(row.get("ha_metrics"), dict)
                            else None,
                            "capability_precision": row.get("ha_metrics", {}).get("capability_precision")
                            if isinstance(row.get("ha_metrics"), dict)
                            else None,
                            "capability_recall": row.get("ha_metrics", {}).get("capability_recall")
                            if isinstance(row.get("ha_metrics"), dict)
                            else None,
                            "grounding_stage": row.get("ha_metrics", {}).get("grounding_stage")
                            if isinstance(row.get("ha_metrics"), dict)
                            else None,
                        }
                        if include_grounding
                        else {}
                    ),
                    "failure_reason": failure_reason(row),
                }
            )

        for category in sorted(grouped.keys(), key=category_sort_key):
            cat_rows = grouped[category]
            category_rows.append(
                {
                    "method": method,
                    "category": category,
                    **metric_values(cat_rows, include_grounding=include_grounding),
                }
            )

    grounding_fields = [
        "device_precision",
        "device_recall",
        "capability_precision",
        "capability_recall",
    ]
    include_grounding_in_output = any(has_grounding_step(row.get("method", "")) for row in main_rows)
    main_fields = [
        "method",
        "score_file",
        "n",
        "executable_correctness",
        "structural_validity",
        "explicit_intent_score",
        "implicit_constraint_completion",
        "avg_e2e_latency_ms",
        "avg_total_tokens",
    ]
    if include_grounding_in_output:
        main_fields.extend(grounding_fields)
    category_fields = ["method", "category"] + main_fields[2:]
    per_case_fields = [
        "method",
        "request_id",
        "home_id",
        "category",
        "request",
        "executable_correctness",
        "structural_validity",
        "explicit_intent_score",
        "implicit_constraint_completion",
        "e2e_latency_ms",
        "total_tokens",
    ]
    if include_grounding_in_output:
        per_case_fields.extend(grounding_fields + ["grounding_stage"])
    per_case_fields.append("failure_reason")
    write_csv(output_dir / "main_metrics.csv", main_rows, main_fields)
    write_csv(output_dir / "category_breakdown.csv", category_rows, category_fields)
    write_csv(output_dir / "per_case_scores.csv", per_case_rows, per_case_fields)
    write_failures(output_dir / "failure_cases.md", all_rows)
    print(f"Wrote results to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
