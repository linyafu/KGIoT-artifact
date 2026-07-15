#!/usr/bin/env python3
"""Shared utilities for the standalone Home TAP benchmark scripts."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


TAP_FIELDS = ("trigger", "condition", "action")
REPO_ROOT = Path(__file__).resolve().parent.parent
FIELD_TAP_ROLE = {"trigger": "trigger", "condition": "condition", "action": "action"}
_DEPLOY_FAILURE_MARKERS = (
    "fail to deploy to home assistant",
    "tap generated but deploy failed",
    "tap generation failed",
    "some thing wrong in tap_generator",
    "invalid literal for int()",
    "error: llm tap output is not a json object",
    "traceback (most recent call last)",
)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def strip_index_prefix(text: str) -> str:
    return re.sub(r"^\s*\d+[\.\)\s_-]+", "", text).strip()


def iter_benchmark_requests(gt_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return benchmark entries with stable index/request metadata."""
    gt = gt_data.get("ground_truth", {})
    if not isinstance(gt, dict):
        return []

    rows: List[Dict[str, Any]] = []
    for ordinal, (key, entry) in enumerate(gt.items(), start=1):
        if not isinstance(entry, dict):
            continue
        request = str(entry.get("request") or strip_index_prefix(key)).strip()
        rows.append(
            {
                "index": ordinal,
                "request_key": key,
                "request": request,
                "request_id": entry.get("request_id") or f"REQ_{ordinal:03d}",
                "home_id": entry.get("home_id") or gt_data.get("home_id"),
                "category": entry.get("category"),
                "entry": entry,
            }
        )
    return rows


def normalize_atom(atom: str) -> str:
    atom = str(atom or "").strip()
    if not atom:
        return ""
    if atom.lower().startswith("event:"):
        return "event:" + atom.split(":", 1)[1].strip()
    if atom.lower().startswith("call_action:"):
        return "call_action:" + atom.split(":", 1)[1].strip()

    for op in ["==", ">=", "<=", ">", "<", "="]:
        if op in atom:
            left, right = atom.split(op, 1)
            left = left.strip()
            right = right.strip()
            if right.lower() in {"true", "1"}:
                right = "true"
            elif right.lower() in {"false", "0"}:
                right = "false"
            return f"{left}{op}{right}"
    return atom


def parse_tap_field(value: Any) -> Set[str]:
    if value is None or not str(value).strip():
        return set()
    atoms: Set[str] = set()
    for part in str(value).split(","):
        for atom in re.split(r"\s+(?:and|or)\s+", part, flags=re.IGNORECASE):
            atom = atom.strip().strip("()")
            normalized = normalize_atom(atom)
            if normalized:
                atoms.add(normalized)
    return atoms


def normalize_tap(tap: Dict[str, Any]) -> Dict[str, str]:
    return {field: str(tap.get(field, "") or "").strip() for field in TAP_FIELDS}


def tap_atoms_by_field(tap: Dict[str, Any]) -> Dict[str, Set[str]]:
    norm = normalize_tap(tap)
    return {field: parse_tap_field(norm[field]) for field in TAP_FIELDS}


def _semantic_atom(atom: str, field: str) -> str:
    """Return canonical semantic atom used for matching, not structural validation."""
    atom = normalize_atom(atom)
    if not atom:
        return ""

    if atom.startswith("event:"):
        rest = atom.split(":", 1)[1].strip()
        if any(op in rest for op in ["==", ">=", "<=", ">", "<", "="]):
            # Invalid as syntax, but semantic matching should still see the underlying atom.
            if field in {"trigger", "condition"} and "=" in rest and not any(
                op in rest for op in ["==", ">=", "<="]
            ):
                left, right = rest.split("=", 1)
                return normalize_atom(f"{left}=={right}")
            return normalize_atom(rest)
        if rest.endswith(".magnet_sensor.open"):
            return rest[: -len(".open")] + ".contact_state==false"
        if rest.endswith(".magnet_sensor.close"):
            return rest[: -len(".close")] + ".contact_state==true"
        return atom

    if atom.startswith("time>="):
        return "time>=" + atom.split(">=", 1)[1]
    elif atom.startswith("time>"):
        return "time>=" + atom.split(">", 1)[1]
    elif atom.startswith("time<="):
        return "time<=" + atom.split("<=", 1)[1]
    elif atom.startswith("time<"):
        return "time<=" + atom.split("<", 1)[1]

    if atom.endswith(".magnet_sensor.contact_state==false"):
        return atom
    elif atom.endswith(".magnet_sensor.contact_state==true"):
        return atom

    # Treat a single equality sign in trigger/condition as semantically equivalent
    # to equality, while structural_validity still reports it as invalid. Do not
    # do this for actions, where single '=' is the valid assignment operator.
    if field in {"trigger", "condition"} and "=" in atom and not any(
        op in atom for op in ["==", ">=", "<="]
    ):
        left, right = atom.split("=", 1)
        return normalize_atom(f"{left}=={right}")

    return atom


def semantic_atoms(atoms: Set[str], field: str) -> Set[str]:
    out: Set[str] = set()
    for atom in atoms:
        canonical = _semantic_atom(atom, field)
        if canonical:
            out.add(canonical)
    return out


def semantic_tap_atoms_by_field(tap: Dict[str, Any]) -> Dict[str, Set[str]]:
    raw = tap_atoms_by_field(tap)
    return {field: semantic_atoms(atoms, field) for field, atoms in raw.items()}


def get_full_tap_candidates(entry: Dict[str, Any]) -> List[Dict[str, str]]:
    candidates: List[Dict[str, Any]] = []
    primary = entry.get("tap")
    if isinstance(primary, dict):
        candidates.append(primary)
    for key in ["acceptable_taps", "alternative_taps", "alternatives"]:
        for item in entry.get(key) or []:
            if isinstance(item, dict) and isinstance(item.get("tap"), dict):
                candidates.append(item["tap"])
            elif isinstance(item, dict):
                candidates.append(item)

    seen: Set[Tuple[str, str, str]] = set()
    out: List[Dict[str, str]] = []
    for tap in candidates:
        norm = normalize_tap(tap)
        triple = tuple(norm[field] for field in TAP_FIELDS)
        if triple in seen:
            continue
        seen.add(triple)
        out.append(norm)
    return out


def get_explicit_tap_candidates(entry: Dict[str, Any]) -> List[Dict[str, str]]:
    candidates: List[Dict[str, Any]] = []
    explicit = entry.get("explicit_tap")
    if isinstance(explicit, dict):
        candidates.append(explicit)
    else:
        candidates.extend(get_full_tap_candidates(entry))
    for item in entry.get("acceptable_explicit_taps") or []:
        if isinstance(item, dict) and isinstance(item.get("tap"), dict):
            candidates.append(item["tap"])
        elif isinstance(item, dict):
            candidates.append(item)
    return [normalize_tap(tap) for tap in candidates]


def implicit_constraint_atoms(entry: Dict[str, Any]) -> Dict[str, List[str]]:
    raw = entry.get("implicit_constraints") if isinstance(entry, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    out = {"dependencies": [], "interlocks": []}
    for key in out:
        for item in raw.get(key) or []:
            atom = ""
            if isinstance(item, str):
                atom = item
            elif isinstance(item, dict):
                atom = str(item.get("atom", ""))
            atom = normalize_atom(atom)
            if atom and atom not in out[key]:
                out[key].append(atom)
    return out


def extract_response_text(response_json: Dict[str, Any]) -> str:
    return str(
        response_json.get("response", {})
        .get("speech", {})
        .get("plain", {})
        .get("speech", "")
    ).strip()


def _candidate_brace_payloads(text: str) -> List[str]:
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    payloads: List[str] = []
    for start in starts:
        depth = 0
        for end in range(start, len(text)):
            ch = text[end]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    payloads.append(text[start : end + 1])
                    break
    return payloads


def parse_tap_from_text(text: str) -> Tuple[Optional[Dict[str, str]], str]:
    """Extract a TAP dict from assistant text containing JSON or Python dict syntax."""
    for payload in reversed(_candidate_brace_payloads(text)):
        parsed: Any = None
        try:
            parsed = json.loads(payload)
        except Exception:
            try:
                parsed = ast.literal_eval(payload)
            except Exception:
                continue

        if isinstance(parsed, dict):
            if isinstance(parsed.get("TAP"), dict):
                parsed = parsed["TAP"]
            if all(field in parsed for field in TAP_FIELDS):
                return normalize_tap(parsed), ""
    return None, "no TAP dict found in response text"


def score_subset(target: Set[str], generated: Set[str]) -> Dict[str, Any]:
    matched = target & generated
    precision = len(matched) / len(generated) if generated else (1.0 if not target else 0.0)
    recall = len(matched) / len(target) if target else 1.0
    return {
        "score": 1 if target <= generated else 0,
        "precision": precision,
        "recall": recall,
        "target_atoms": sorted(target),
        "generated_atoms": sorted(generated),
        "missing_atoms": sorted(target - generated),
        "extra_atoms": sorted(generated - target),
    }


def field_subset_score(gt_tap: Dict[str, Any], pred_tap: Dict[str, Any]) -> Dict[str, Any]:
    gt = semantic_tap_atoms_by_field(gt_tap)
    pred = semantic_tap_atoms_by_field(pred_tap)
    trigger_match = gt["trigger"] <= pred["trigger"]
    condition_match = gt["condition"] <= pred["condition"]
    action_match = gt["action"] <= pred["action"]
    subset = score_subset(
        gt["trigger"] | gt["condition"] | gt["action"],
        pred["trigger"] | pred["condition"] | pred["action"],
    )
    return {
        "score": 1 if trigger_match and condition_match and action_match else 0,
        "trigger_match": trigger_match,
        "condition_match": condition_match,
        "action_match": action_match,
        "precision": subset["precision"],
        "recall": subset["recall"],
        "details": {
            "gt_trigger": sorted(gt["trigger"]),
            "pred_trigger": sorted(pred["trigger"]),
            "gt_condition": sorted(gt["condition"]),
            "pred_condition": sorted(pred["condition"]),
            "gt_action": sorted(gt["action"]),
            "pred_action": sorted(pred["action"]),
            "missing_atoms": subset["missing_atoms"],
            "extra_atoms": subset["extra_atoms"],
        },
    }


def explicit_exact_score(
    gt_tap: Dict[str, Any],
    pred_tap: Dict[str, Any],
    implicit_constraints: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    gt = semantic_tap_atoms_by_field(gt_tap)
    pred = semantic_tap_atoms_by_field(pred_tap)
    constraints = implicit_constraints or {"dependencies": [], "interlocks": []}
    pred["action"] = pred["action"] - semantic_atoms(set(constraints.get("dependencies") or []), "action")
    pred["condition"] = pred["condition"] - semantic_atoms(set(constraints.get("interlocks") or []), "condition")

    trigger_match = gt["trigger"] == pred["trigger"]
    condition_match = gt["condition"] == pred["condition"]
    action_match = gt["action"] == pred["action"]
    subset = score_subset(
        gt["trigger"] | gt["condition"] | gt["action"],
        pred["trigger"] | pred["condition"] | pred["action"],
    )
    return {
        "score": 1 if trigger_match and condition_match and action_match else 0,
        "trigger_match": trigger_match,
        "condition_match": condition_match,
        "action_match": action_match,
        "precision": subset["precision"],
        "recall": subset["recall"],
        "details": {
            "gt_trigger": sorted(gt["trigger"]),
            "pred_trigger": sorted(pred["trigger"]),
            "gt_condition": sorted(gt["condition"]),
            "pred_condition": sorted(pred["condition"]),
            "gt_action": sorted(gt["action"]),
            "pred_action": sorted(pred["action"]),
            "missing_atoms": subset["missing_atoms"],
            "extra_atoms": subset["extra_atoms"],
        },
    }


def exact_tap_score(gt_tap: Dict[str, Any], pred_tap: Dict[str, Any]) -> Dict[str, Any]:
    gt = semantic_tap_atoms_by_field(gt_tap)
    pred = semantic_tap_atoms_by_field(pred_tap)
    trigger_match = gt["trigger"] == pred["trigger"]
    condition_match = gt["condition"] == pred["condition"]
    action_match = gt["action"] == pred["action"]
    return {
        "score": 1 if trigger_match and condition_match and action_match else 0,
        "trigger_match": trigger_match,
        "condition_match": condition_match,
        "action_match": action_match,
        "details": {
            "gt_trigger": sorted(gt["trigger"]),
            "pred_trigger": sorted(pred["trigger"]),
            "gt_condition": sorted(gt["condition"]),
            "pred_condition": sorted(pred["condition"]),
            "gt_action": sorted(gt["action"]),
            "pred_action": sorted(pred["action"]),
        },
    }


def best_explicit_score(entry: Dict[str, Any], pred_tap: Dict[str, Any]) -> Dict[str, Any]:
    best: Optional[Dict[str, Any]] = None
    best_key: Optional[Tuple[Any, ...]] = None
    constraints = implicit_constraint_atoms(entry)
    for idx, candidate in enumerate(get_explicit_tap_candidates(entry)):
        result = explicit_exact_score(candidate, pred_tap, constraints)
        result["matched_candidate_index"] = idx
        key = (
            int(result["score"]),
            result["recall"],
            result["precision"],
            -len(result["details"]["extra_atoms"]),
        )
        if best_key is None or key > best_key:
            best_key = key
            best = result
    return best or {"score": 0, "precision": 0.0, "recall": 0.0, "details": {}}


def best_executable_score(entry: Dict[str, Any], pred_tap: Dict[str, Any]) -> Dict[str, Any]:
    best: Optional[Dict[str, Any]] = None
    best_key: Optional[Tuple[Any, ...]] = None
    pred_atoms = semantic_tap_atoms_by_field(pred_tap)
    for idx, candidate in enumerate(get_full_tap_candidates(entry)):
        result = exact_tap_score(candidate, pred_tap)
        gt_atoms = semantic_tap_atoms_by_field(candidate)
        overlap = sum(len(gt_atoms[field] & pred_atoms[field]) for field in TAP_FIELDS)
        result["matched_candidate_index"] = idx
        key = (
            int(result["score"]),
            int(result["trigger_match"]) + int(result["condition_match"]) + int(result["action_match"]),
            overlap,
        )
        if best_key is None or key > best_key:
            best_key = key
            best = result
    return best or {"score": 0, "details": {}}


def implicit_score(entry: Dict[str, Any], pred_tap: Dict[str, Any]) -> Dict[str, Any]:
    constraints = implicit_constraint_atoms(entry)
    deps = semantic_atoms(set(constraints["dependencies"]), "action")
    interlocks = semantic_atoms(set(constraints["interlocks"]), "condition")
    pred = semantic_tap_atoms_by_field(pred_tap)
    matched = (deps & pred["action"]) | (interlocks & pred["condition"])
    total = deps | interlocks
    completion = len(matched) / len(total) if total else None
    return {
        "applicable": bool(total),
        "score": (1 if matched == total else 0) if total else None,
        "completion": completion,
        "dependency_recall": len(deps & pred["action"]) / len(deps) if deps else None,
        "interlock_recall": len(interlocks & pred["condition"]) / len(interlocks) if interlocks else None,
        "dependency_target_atoms": sorted(deps),
        "interlock_target_atoms": sorted(interlocks),
        "missing_dependencies": sorted(deps - pred["action"]),
        "missing_interlocks": sorted(interlocks - pred["condition"]),
    }


def home_graph_index_path(home_id: str) -> Path:
    suffix = str(home_id or "").replace("home_", "").upper()
    return REPO_ROOT / "data" / "environments" / f"home_{suffix}_graph_index.json"


class HomeEnvironment:
    """Home graph snapshot used for offline TAP grounding checks."""

    def __init__(self, graph_index: Dict[str, Any]) -> None:
        self.name_to_id: Dict[str, int] = {}
        self.id_to_name: Dict[str, str] = {}
        self.device_caps: Dict[str, Set[str]] = {}
        self.cap_catalog: Dict[str, Dict[str, Any]] = {}

        device_index = graph_index.get("device_index") or {}
        device_to_caps = graph_index.get("device_to_caps") or {}
        cap_catalog = graph_index.get("cap_catalog") or {}
        if isinstance(cap_catalog, dict):
            self.cap_catalog = {str(k): v for k, v in cap_catalog.items() if isinstance(v, dict)}

        if isinstance(device_index, dict):
            for dev_id, dev in device_index.items():
                if not isinstance(dev, dict):
                    continue
                name = str(dev.get("name") or "").strip()
                if not name:
                    continue
                dev_key = str(dev_id)
                self.name_to_id[name] = int(dev.get("id", dev_id))
                self.id_to_name[dev_key] = name
                caps: Set[str] = set()
                for item in device_to_caps.get(dev_key) or device_to_caps.get(str(dev_id)) or []:
                    if isinstance(item, dict) and item.get("cap_key"):
                        caps.add(str(item["cap_key"]))
                self.device_caps[name] = caps
                self.device_caps[dev_key] = caps

    def resolve_device_name(self, token: str) -> Optional[str]:
        token = str(token or "").strip()
        if not token:
            return None
        if token in self.name_to_id:
            return token
        if token in self.id_to_name:
            return self.id_to_name[token]
        return None

    def device_has_capability(self, device_token: str, cap_key: str) -> bool:
        device_name = self.resolve_device_name(device_token)
        if not device_name:
            return False
        return cap_key in self.device_caps.get(device_name, set())

    def tap_role_allows(self, cap_key: str, role: str) -> bool:
        info = self.cap_catalog.get(cap_key)
        if not isinstance(info, dict):
            return False
        roles = [str(r).strip().lower() for r in (info.get("TAP_role") or [])]
        return str(role).strip().lower() in roles


_HOME_ENV_CACHE: Dict[str, HomeEnvironment] = {}


def load_home_environment(home_id: str) -> Optional[HomeEnvironment]:
    home_id = str(home_id or "").strip()
    if not home_id:
        return None
    if home_id in _HOME_ENV_CACHE:
        return _HOME_ENV_CACHE[home_id]
    graph_path = home_graph_index_path(home_id)
    if not graph_path.exists():
        return None
    env = HomeEnvironment(load_json(graph_path))
    _HOME_ENV_CACHE[home_id] = env
    return env


def _parse_atom_for_environment(atom: str, field: str) -> Optional[Tuple[str, str, str]]:
    """Return (device_token, cap_key, tap_role) for environment checks; None for time atoms."""
    atom = normalize_atom(atom)
    if not atom or atom.startswith("time"):
        return None

    if atom.startswith("call_action:"):
        body = atom.split(":", 1)[1].strip()
        parts = body.split(".", 2)
        if len(parts) != 3:
            return ("", "", FIELD_TAP_ROLE[field])
        return parts[0], f"{parts[1]}.{parts[2]}", "action"

    if atom.startswith("event:"):
        body = atom.split(":", 1)[1].strip()
        parts = body.split(".", 2)
        if len(parts) != 3:
            return ("", "", "trigger")
        return parts[0], f"{parts[1]}.{parts[2]}", "trigger"

    for op in ["==", ">=", "<=", ">", "<", "="]:
        if op in atom:
            left = atom.split(op, 1)[0].strip()
            parts = left.split(".", 2)
            if len(parts) != 3:
                return ("", "", FIELD_TAP_ROLE[field])
            return parts[0], f"{parts[1]}.{parts[2]}", FIELD_TAP_ROLE[field]
    return ("", "", FIELD_TAP_ROLE[field])


def _validate_environment(pred_tap: Dict[str, Any], home_env: HomeEnvironment) -> List[str]:
    errors: List[str] = []
    for field in TAP_FIELDS:
        for atom in parse_tap_field(pred_tap.get(field, "")):
            parsed = _parse_atom_for_environment(atom, field)
            if parsed is None:
                continue
            device_token, cap_key, role = parsed
            if not device_token or not cap_key:
                errors.append(f"{field} atom has invalid device/capability format: {atom}")
                continue
            device_name = home_env.resolve_device_name(device_token)
            if not device_name:
                errors.append(f"{field} references unknown device: {device_token} ({atom})")
                continue
            if not home_env.device_has_capability(device_token, cap_key):
                errors.append(
                    f"{field} references capability not exposed by device {device_name}: {cap_key} ({atom})"
                )
                continue
            if not home_env.tap_role_allows(cap_key, role):
                errors.append(
                    f"{field} uses capability {cap_key} with invalid TAP_role '{role}' ({atom})"
                )
    return errors


def deploy_succeeded(
    response_text: str,
    *,
    pipeline_success: Optional[bool] = None,
    pipeline_error: Optional[str] = None,
) -> Optional[bool]:
    if pipeline_success is False:
        return False
    if pipeline_error:
        err = str(pipeline_error).strip().lower()
        if err and err not in {"none", "null"}:
            return False
    text = str(response_text or "").strip().lower()
    if not text:
        return None
    if any(marker in text for marker in _DEPLOY_FAILURE_MARKERS):
        return False
    return True


def structural_validity(
    pred_tap: Optional[Dict[str, Any]],
    *,
    home_env: Optional[HomeEnvironment] = None,
    response_text: str = "",
    pipeline_success: Optional[bool] = None,
    pipeline_error: Optional[str] = None,
) -> Dict[str, Any]:
    if not isinstance(pred_tap, dict):
        return {
            "score": 0,
            "errors": ["parsed TAP is missing or not a dict"],
            "syntax_valid": False,
            "environment_valid": None,
            "deploy_valid": None,
        }

    errors: List[str] = []
    for field in TAP_FIELDS:
        if field not in pred_tap:
            errors.append(f"missing field: {field}")
        elif not isinstance(pred_tap[field], str):
            errors.append(f"field {field} is not a string")
    if not parse_tap_field(pred_tap.get("action", "")):
        errors.append("action has no parseable atoms")
    for field in ["trigger", "condition"]:
        for atom in parse_tap_field(pred_tap.get(field, "")):
            if atom.startswith("event:"):
                event_body = atom.split(":", 1)[1].strip()
                if any(op in event_body for op in ["==", ">=", "<=", ">", "<", "="]):
                    errors.append(f"{field} event atom must not use a comparison operator: {atom}")
                elif len(event_body.split(".", 2)) != 3:
                    errors.append(f"{field} event atom has invalid capability format: {atom}")
                continue
            if atom.startswith("time==") or atom.startswith("time"):
                continue
            has_comparison = any(op in atom for op in ["==", ">=", "<=", ">", "<"])
            if not has_comparison:
                errors.append(
                    f"{field} atom must be an event trigger, time guard, or state/comparison atom: {atom}"
                )
                continue
            if not atom.startswith("time"):
                left = re.split(r"==|>=|<=|>|<", atom, maxsplit=1)[0].strip()
                if left and not left.startswith("event:") and len(left.split(".", 2)) != 3:
                    errors.append(f"{field} atom has invalid capability format: {atom}")
    for atom in parse_tap_field(pred_tap.get("action", "")):
        if atom.startswith("call_action:"):
            left = atom.split(":", 1)[1].strip()
        elif "=" in atom:
            left = atom.split("=", 1)[0].strip()
        else:
            errors.append(f"action atom has no supported action operator: {atom}")
            continue
        if left and len(left.split(".", 2)) != 3:
            errors.append(f"action atom has invalid capability format: {atom}")

    syntax_valid = not errors
    environment_valid: Optional[bool] = None
    if home_env is not None:
        env_errors = _validate_environment(pred_tap, home_env)
        environment_valid = not env_errors
        errors.extend(env_errors)

    deploy_valid = deploy_succeeded(
        response_text,
        pipeline_success=pipeline_success,
        pipeline_error=pipeline_error,
    )
    if deploy_valid is False:
        errors.append("TAP was not successfully deployed to Home Assistant")

    return {
        "score": 0 if errors else 1,
        "errors": errors,
        "syntax_valid": syntax_valid,
        "environment_valid": environment_valid,
        "deploy_valid": deploy_valid,
    }
