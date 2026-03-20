"""Load and parse eval result JSON files."""
import json
import re
from pathlib import Path
from typing import Any

# result_instance_id format: {domain}_r{rows}_c{cols}_h{hidden}_b{branch}_ids{ids}_fields{fields}_eq{eq}
_RESULT_INSTANCE_PATTERN = re.compile(
    r"^(\w+)_r\d+_c\d+_h(\d+)_b(\d+)_ids\d+_fields\d+_eq\d+$"
)


def parse_result_instance_id(result_instance_id: str) -> tuple[str, int, int] | None:
    """Parse result_instance_id, return (domain, hidden_slots, branch_budget)."""
    m = _RESULT_INSTANCE_PATTERN.match(result_instance_id)
    if m is None:
        return None
    domain, hidden, branch = m.group(1), int(m.group(2)), int(m.group(3))
    return (domain, hidden, branch)


def load_json(path: str) -> dict[str, Any] | None:
    """Load JSON file, return None on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def extract_run_result(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extract run_result info from payload."""
    run_result = payload.get("run_result")
    if not isinstance(run_result, dict):
        return None

    usage = run_result.get("usage") or {}
    result = run_result.get("result") or {}
    score = run_result.get("score")
    if score is None and isinstance(result, dict):
        s = result.get("score")
        score = 1 if s is True else (0 if s is False else None)

    return {
        "status": run_result.get("status"),
        "reason": run_result.get("reason") or result.get("reason"),
        "score": score,
        "completion_tokens": usage.get("completion_tokens"),
        "cost": usage.get("cost"),
        "time": usage.get("time"),
        "tool_calls_num": usage.get("tool_calls_num"),
        "step_num": usage.get("step_num"),
    }


def collect_json_files(root: Path, domain: str | None = None) -> list[tuple[Path, dict]]:
    """
    Recursively collect all .json files under root, return [(path, parsed_info), ...].
    parsed_info contains result_instance_id, domain, hidden_slots, branch_budget.
    domain=None means no filter; otherwise only matching domain.
    """
    out: list[tuple[Path, dict]] = []
    for p in root.rglob("*.json"):
        payload = load_json(str(p))
        if payload is None:
            continue
        rid = payload.get("result_instance_id") or payload.get("instance_id", "")
        parsed = parse_result_instance_id(rid)
        if parsed is None:
            continue
        d, h, b = parsed
        if domain is not None and d != domain:
            continue
        out.append((p, {"result_instance_id": rid, "domain": d, "hidden_slots": h, "branch_budget": b}))
    return out


def aggregate_by_hidden_branch(
    items: list[tuple[Path, dict]],
) -> dict[tuple[int, int], list[dict[str, Any]]]:
    """
    Aggregate by (hidden_slots, branch_budget).
    Return {(h, b): [extracted_run_result, ...]}
    """
    agg: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for path, info in items:
        payload = load_json(str(path))
        if payload is None:
            continue
        extracted = extract_run_result(payload)
        if extracted is None:
            continue
        key = (info["hidden_slots"], info["branch_budget"])
        agg.setdefault(key, []).append(extracted)
    return agg


def compute_average_matrix(
    agg: dict[tuple[int, int], list[dict[str, Any]]],
) -> dict[str, dict[tuple[int, int], float]]:
    """
    Compute average for each (h, b).
    Return {
        "score": {(h,b): avg},
        "completion_tokens": {...},
        ...
    }
    """
    metrics = ["score", "completion_tokens", "cost", "time", "tool_calls_num", "step_num"]
    out: dict[str, dict[tuple[int, int], float]] = {m: {} for m in metrics}
    for key, runs in agg.items():
        for m in metrics:
            vals = [r.get(m) for r in runs if r.get(m) is not None]
            if vals:
                out[m][key] = sum(vals) / len(vals)
    return out
