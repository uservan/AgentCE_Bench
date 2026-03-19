import argparse
import itertools
import json
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

DEFAULT_VALIDATION_EXAMPLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "course_dataset_r5_c5_h1-3-5-7-9-13-17_cand15_budget0-2-4-6-8-10_seed42.json",
)

try:
    from .domains import DOMAIN_SPECS
    from .generation.constants import DEFAULT_BRANCH_BUDGETS, DEFAULT_CANDIDATES_PER_SLOT
    from .generation.constraints import item_matches_slot_constraint
    from .valid.dataset_checks import validate_dataset_structure
    from .valid.messages import format_rule_message
    from .valid.rules import rule_satisfied
    from .valid.utils import build_slot_map
    from utils.console_display import ConsoleDisplay
except ImportError:
    from domains import DOMAIN_SPECS
    from generation.constants import DEFAULT_BRANCH_BUDGETS, DEFAULT_CANDIDATES_PER_SLOT
    from generation.constraints import item_matches_slot_constraint
    from valid.dataset_checks import validate_dataset_structure
    from valid.messages import format_rule_message
    from valid.rules import rule_satisfied
    from valid.utils import build_slot_map
    from utils.console_display import ConsoleDisplay


def validate_slot_assignment(
    item_id,
    row_index,
    col_index,
    domain,
    item_pool,
    slots,
    truth_solution=None,
):
    if truth_solution is None:
        return False, "truth_solution is required for slot validation"
    if row_index < 0 or row_index >= len(truth_solution) or col_index < 0 or col_index >= len(truth_solution[0]):
        return False, f"slot ({row_index}, {col_index}) is out of range"
    if item_id is None:
        return True, None
    if item_id not in item_pool:
        return False, f"unknown item id '{item_id}' appears in slot ({row_index}, {col_index})"

    slot_map = build_slot_map(slots)
    slot_entry = slot_map.get((row_index, col_index))
    if slot_entry is None:
        expected_id = truth_solution[row_index][col_index]
        if item_id != expected_id:
            return False, f"slot ({row_index}, {col_index}) is fixed and must remain '{expected_id}'"
        return True, None

    if item_id not in slot_entry["candidate_ids"]:
        return False, (
            f"slot ({row_index}, {col_index}) contains id '{item_id}', "
            "which is not one of the candidate options for that slot"
        )
    if not item_matches_slot_constraint(
        item_pool[item_id],
        slot_entry["slot_constraints"],
        DOMAIN_SPECS[domain]["slot_rules"],
    ):
        return False, f"slot ({row_index}, {col_index}) violates its slot constraints"
    return True, None


def validate_slot_constraints(
    solution,
    domain,
    row_index,
    col_index,
    slot_constraint,
    item_pool,
    slots,
    truth_solution=None,
):
    del slot_constraint
    return validate_slot_assignment(
        item_id=solution[row_index][col_index],
        row_index=row_index,
        col_index=col_index,
        domain=domain,
        item_pool=item_pool,
        slots=slots,
        truth_solution=truth_solution,
    )


def validate_global_constraints(solution, domain, global_constraints, item_pool, slots, truth_solution=None):
    if truth_solution is None:
        return False, "truth_solution is required for global validation"

    ids = []
    for row_index, row in enumerate(solution):
        for col_index, item_id in enumerate(row):
            slot_ok, slot_reason = validate_slot_assignment(
                item_id=item_id,
                row_index=row_index,
                col_index=col_index,
                domain=domain,
                item_pool=item_pool,
                slots=slots,
                truth_solution=truth_solution,
            )
            if not slot_ok:
                return False, slot_reason
            if item_id is not None:
                ids.append(item_id)

    items = [item_pool[item_id] for item_id in ids]
    is_complete = all(item_id is not None for row in solution for item_id in row)
    active_global_rules = [rule for rule in DOMAIN_SPECS[domain]["global_rules"] if rule["name"] in global_constraints]
    for rule in active_global_rules:
        if not rule_satisfied(rule, global_constraints[rule["name"]], items, is_complete, solution, item_pool):
            return False, format_rule_message(domain, rule, global_constraints[rule["name"]], "the whole grid")
    return True, None


def validate_dataset(dataset, candidates_per_slot=None, branch_budget=None):
    resolved_candidates_per_slot = (
        dataset.get("meta", {}).get("candidates_per_slot", DEFAULT_CANDIDATES_PER_SLOT)
        if candidates_per_slot is None
        else candidates_per_slot
    )
    resolved_branch_budget = (
        dataset.get("meta", {}).get("branch_budget", DEFAULT_BRANCH_BUDGETS[0])
        if branch_budget is None
        else branch_budget
    )
    return validate_dataset_structure(
        dataset,
        candidates_per_slot=resolved_candidates_per_slot,
        branch_budget=resolved_branch_budget,
        validate_slot_constraints=validate_slot_constraints,
        validate_global_constraints=validate_global_constraints,
    )


def _load_payload(path):
    with open(path, "r", encoding="utf-8") as input_file:
        payload = json.load(input_file)
    if "instances" not in payload or not payload["instances"]:
        raise ValueError(f"Dataset file does not contain instances: {path}")
    return payload


def _copy_truth_solution(dataset):
    return [row[:] for row in dataset["truth_solution"]]


def _apply_assignments(dataset, assignments):
    solution = _copy_truth_solution(dataset)
    for row_index, col_index, candidate_id in assignments:
        solution[row_index][col_index] = candidate_id
    return solution


def _apply_assignments_with_open_future_hidden_slots(dataset, assignments, future_hidden_slots):
    solution = _apply_assignments(dataset, assignments)
    for slot in future_hidden_slots:
        solution[slot["row"]][slot["col"]] = None
    return solution


def _iter_previous_decoy_assignments(branch_slots):
    yield {}
    if not branch_slots:
        return
    for subset_size in range(1, len(branch_slots) + 1):
        for subset in itertools.combinations(branch_slots, subset_size):
            decoy_lists = [slot["decoy_ids"] for slot in subset]
            for selected_ids in itertools.product(*decoy_lists):
                assignment = {}
                for slot, candidate_id in zip(subset, selected_ids):
                    assignment[(slot["row"], slot["col"])] = candidate_id
                yield assignment


def _iter_partial_decoy_open_assignments(branch_slots):
    yield {}
    slot_count = len(branch_slots)
    for truth_prefix_len in range(slot_count):
        suffix_slots = branch_slots[truth_prefix_len:]
        if not suffix_slots:
            continue
        decoy_lists = [slot.get("decoy_ids", []) for slot in suffix_slots]
        if any(not decoy_ids for decoy_ids in decoy_lists):
            continue
        for selected_ids in itertools.product(*decoy_lists):
            yield {
                (slot["row"], slot["col"]): candidate_id
                for slot, candidate_id in zip(suffix_slots, selected_ids)
            }


def _ordered_hidden_slots(dataset):
    return sorted(dataset["slots"], key=lambda slot: (slot["row"], slot["col"]))


def _future_hidden_slots_after(dataset, current_slot):
    ordered_slots = _ordered_hidden_slots(dataset)
    current_index = next(
        index
        for index, slot in enumerate(ordered_slots)
        if slot["row"] == current_slot["row"] and slot["col"] == current_slot["col"]
    )
    return ordered_slots[current_index + 1:]


def _evaluate_global_solution(dataset, solution):
    return validate_global_constraints(
        solution,
        dataset["domain"],
        dataset["global_constraints"],
        dataset["item_pool"],
        dataset["slots"],
        truth_solution=dataset["truth_solution"],
    )


def _validate_stage_contexts(dataset, current_slot, previous_slots, open_assignments_iterable):
    future_hidden_slots = _future_hidden_slots_after(dataset, current_slot)
    if not future_hidden_slots:
        return None, "last branch slot"
    failure_reason = None
    for candidate_id in current_slot.get("decoy_ids", []):
        for prior_assignments in open_assignments_iterable(previous_slots):
            assignments = [
                (row_index, col_index, assigned_id)
                for (row_index, col_index), assigned_id in prior_assignments.items()
            ]
            assignments.append((current_slot["row"], current_slot["col"], candidate_id))
            solution = _apply_assignments_with_open_future_hidden_slots(
                dataset,
                assignments,
                future_hidden_slots,
            )
            global_ok, global_reason = _evaluate_global_solution(dataset, solution)
            if not global_ok:
                failure_reason = (
                    f"candidate {candidate_id} with future=None failed: {global_reason or 'unknown reason'}"
                )
                return False, failure_reason
    return True, "all checked open-prefix contexts passed"


def _validate_hard_contexts(dataset, current_slot, previous_slots):
    failure_reason = None
    for candidate_id in current_slot.get("decoy_ids", []):
        for prior_assignments in _iter_previous_decoy_assignments(previous_slots):
            assignments = [
                (row_index, col_index, assigned_id)
                for (row_index, col_index), assigned_id in prior_assignments.items()
            ]
            assignments.append((current_slot["row"], current_slot["col"], candidate_id))
            solution = _apply_assignments(dataset, assignments)
            global_ok, global_reason = _evaluate_global_solution(dataset, solution)
            if global_ok:
                failure_reason = (
                    f"candidate {candidate_id} with future=truth stayed valid"
                )
                if global_reason:
                    failure_reason += f": {global_reason}"
                return False, failure_reason
    return True, "all checked truth-completed contexts failed globally as expected"


def _build_decoy_stage_report(dataset):
    branch_slots = sorted(
        [slot for slot in dataset["slots"] if slot.get("is_branch_slot") and slot.get("decoy_ids")],
        key=lambda entry: entry["branch_rank"],
    )
    results = []
    for current_index, slot in enumerate(branch_slots):
        previous_slots = branch_slots[:current_index]
        hard_ok, hard_reason = _validate_hard_contexts(dataset, slot, previous_slots)
        tier_one_ok, tier_one_reason = _validate_stage_contexts(
            dataset,
            slot,
            previous_slots,
            _iter_previous_decoy_assignments,
        )
        tier_two_ok, tier_two_reason = _validate_stage_contexts(
            dataset,
            slot,
            previous_slots,
            _iter_partial_decoy_open_assignments,
        )
        tier_three_ok, tier_three_reason = _validate_stage_contexts(
            dataset,
            slot,
            previous_slots,
            lambda _previous_slots: iter([{}]),
        )
        recorded_label = slot.get("decoy_generation_final_stage_label")
        if recorded_label == "tier_1":
            recorded_ok = tier_one_ok
            recorded_reason = tier_one_reason
        elif recorded_label == "tier_2":
            recorded_ok = tier_two_ok
            recorded_reason = tier_two_reason
        elif recorded_label == "tier_3":
            recorded_ok = tier_three_ok
            recorded_reason = tier_three_reason
        elif recorded_label in ("hard_only", "last_branch_hard_only"):
            recorded_ok = hard_ok
            recorded_reason = hard_reason
        else:
            recorded_ok = hard_ok
            recorded_reason = "missing recorded stage metadata; showing hard-check result only"
        results.append({
            "row": slot["row"],
            "col": slot["col"],
            "recorded": recorded_label or "missing",
            "recorded_ok": recorded_ok,
            "recorded_reason": recorded_reason,
            "hard_ok": hard_ok,
            "tier_one_ok": tier_one_ok,
            "tier_two_ok": tier_two_ok,
            "tier_three_ok": tier_three_ok,
        })
    return results


def _summarize_instance(dataset):
    slots = dataset["slots"]
    candidate_counts = [len(slot.get("candidate_ids", [])) for slot in slots] or [0]
    return {
        "instance_id": dataset.get("instance_id", "-"),
        "hidden_slots": dataset["meta"]["hidden_slots"],
        "branch_budget": dataset["meta"]["branch_budget"],
        "branch_slots": sum(1 for slot in slots if slot.get("is_branch_slot")),
        "avg_candidates": round(sum(candidate_counts) / len(candidate_counts), 2),
        "item_pool_size": len(dataset["item_pool"]),
    }


def _build_truth_report(dataset):
    slot_results = []
    for slot in dataset["slots"]:
        ok, reason = validate_slot_assignment(
            item_id=slot["truth_id"],
            row_index=slot["row"],
            col_index=slot["col"],
            domain=dataset["domain"],
            item_pool=dataset["item_pool"],
            slots=dataset["slots"],
            truth_solution=dataset["truth_solution"],
        )
        slot_results.append({"row": slot["row"], "col": slot["col"], "ok": ok, "reason": reason})

    global_ok, global_reason = validate_global_constraints(
        dataset["truth_solution"],
        dataset["domain"],
        dataset["global_constraints"],
        dataset["item_pool"],
        dataset["slots"],
        truth_solution=dataset["truth_solution"],
    )
    return {
        "slots": slot_results,
        "global": {"ok": global_ok, "reason": global_reason},
    }


def _choose_representative_instances(instances):
    ordered = sorted(
        instances,
        key=lambda instance: (
            instance["meta"]["hidden_slots"],
            instance["meta"]["branch_budget"],
            instance.get("instance_id", ""),
        ),
    )
    if not ordered:
        return []
    selected = [ordered[0]]
    if ordered[-1].get("instance_id") != ordered[0].get("instance_id"):
        selected.append(ordered[-1])
    return selected


def _first_filter_assignment(dataset):
    for slot in sorted(dataset["slots"], key=lambda entry: (entry["row"], entry["col"])):
        filter_ids = slot.get("filter_candidate_ids", [])
        if filter_ids:
            return [
                {
                    "name": "single_filter_violation",
                    "assignments": [(slot["row"], slot["col"], filter_ids[0])],
                }
            ]
    return []


def _decoy_prefix_cases(dataset):
    branch_slots = sorted(
        [slot for slot in dataset["slots"] if slot.get("is_branch_slot") and slot.get("decoy_ids")],
        key=lambda entry: entry["branch_rank"],
    )
    cases = []
    for prefix_size in range(1, len(branch_slots) + 1):
        current_slot = branch_slots[prefix_size - 1]
        assignments = [
            (slot["row"], slot["col"], slot["decoy_ids"][0])
            for slot in branch_slots[:prefix_size]
        ]
        cases.append({
            "name": f"decoy_prefix_{prefix_size}",
            "assignments": assignments,
            "recorded_stage": current_slot.get("decoy_generation_final_stage_label", "-"),
            "future_hidden_slots": _future_hidden_slots_after(dataset, current_slot),
        })
    return cases


def _format_assignments(assignments):
    if not assignments:
        return "truth only"
    return ", ".join(f"({row},{col})={candidate_id}" for row, col, candidate_id in assignments)


def _evaluate_case(dataset, case):
    solution = _apply_assignments(dataset, case["assignments"])
    slot_checks = []
    failure_reasons = []
    for row_index, col_index, candidate_id in case["assignments"]:
        slot_ok, slot_reason = validate_slot_assignment(
            item_id=candidate_id,
            row_index=row_index,
            col_index=col_index,
            domain=dataset["domain"],
            item_pool=dataset["item_pool"],
            slots=dataset["slots"],
            truth_solution=dataset["truth_solution"],
        )
        slot_checks.append(slot_ok)
        if slot_reason:
            failure_reasons.append(f"slot({row_index},{col_index}): {slot_reason}")

    global_truth_ok, global_truth_reason = _evaluate_global_solution(dataset, solution)
    if global_truth_reason:
        failure_reasons.append(f"global@truth: {global_truth_reason}")

    future_hidden_slots = case.get("future_hidden_slots")
    if future_hidden_slots is None:
        global_open_ok = None
        global_open_reason = None
    else:
        open_solution = _apply_assignments_with_open_future_hidden_slots(
            dataset,
            case["assignments"],
            future_hidden_slots,
        )
        global_open_ok, global_open_reason = _evaluate_global_solution(dataset, open_solution)
        if global_open_reason:
            failure_reasons.append(f"global@open: {global_open_reason}")

    return (
        case["name"],
        case.get("recorded_stage", "-"),
        _format_assignments(case["assignments"]),
        "PASS" if all(slot_checks) else "FAIL",
        "PASS" if global_truth_ok else "FAIL",
        "N/A" if global_open_ok is None else ("PASS" if global_open_ok else "FAIL"),
        " | ".join(failure_reasons) if failure_reasons else "-",
    )


def _print_instance_summary(dataset):
    summary = _summarize_instance(dataset)
    ConsoleDisplay.print_kv_panel(
        title="[bold cyan]Representative Instance[/bold cyan]",
        items=[
            ("Instance", summary["instance_id"]),
            ("Hidden Slots", summary["hidden_slots"]),
            ("Branch Budget", summary["branch_budget"]),
            ("Branch Slots", summary["branch_slots"]),
            ("Final Decoy Stage", dataset.get("meta", {}).get("decoy_generation_final_stage_label", "-")),
            ("Avg Candidates", summary["avg_candidates"]),
            ("Item Pool Size", summary["item_pool_size"]),
        ],
        border_style="cyan",
    )


def _truth_decoy_combination_stats(dataset):
    decoy_slots = [
        slot
        for slot in sorted(dataset["slots"], key=lambda entry: (entry["row"], entry["col"]))
        if slot.get("decoy_ids")
    ]
    if not decoy_slots:
        return {
            "decoy_slot_count": 0,
            "total_combinations": 1,
            "valid_combinations": 1,
            "invalid_combinations": 0,
            "valid_non_truth_combinations": 0,
        }

    option_lists = [
        [slot["truth_id"], *slot["decoy_ids"]]
        for slot in decoy_slots
    ]
    total_combinations = 0
    valid_combinations = 0
    valid_non_truth_combinations = 0

    for selected_ids in itertools.product(*option_lists):
        assignments = [
            (slot["row"], slot["col"], candidate_id)
            for slot, candidate_id in zip(decoy_slots, selected_ids)
        ]
        solution = _apply_assignments(dataset, assignments)
        total_combinations += 1
        global_ok, _ = validate_global_constraints(
            solution,
            dataset["domain"],
            dataset["global_constraints"],
            dataset["item_pool"],
            dataset["slots"],
            truth_solution=dataset["truth_solution"],
        )
        if not global_ok:
            continue
        valid_combinations += 1
        if any(candidate_id != slot["truth_id"] for slot, candidate_id in zip(decoy_slots, selected_ids)):
            valid_non_truth_combinations += 1

    return {
        "decoy_slot_count": len(decoy_slots),
        "total_combinations": total_combinations,
        "valid_combinations": valid_combinations,
        "invalid_combinations": total_combinations - valid_combinations,
        "valid_non_truth_combinations": valid_non_truth_combinations,
    }


def _print_truth_decoy_combination_stats(dataset):
    stats = _truth_decoy_combination_stats(dataset)
    ConsoleDisplay.print_kv_panel(
        title="[bold magenta]Truth/Decoy Combination Stats[/bold magenta]",
        items=[
            ("Instance", dataset.get("instance_id", "-")),
            ("Decoy Slots", stats["decoy_slot_count"]),
            ("Total Truth/Decoy Combinations", stats["total_combinations"]),
            ("Valid Combinations", stats["valid_combinations"]),
            ("Invalid Combinations", stats["invalid_combinations"]),
            ("Valid Non-Truth Combinations", stats["valid_non_truth_combinations"]),
        ],
        border_style="magenta",
    )


def _print_decoy_stage_report(dataset):
    results = _build_decoy_stage_report(dataset)
    if not results:
        ConsoleDisplay.print_kv_panel(
            title="[bold blue]Decoy Stage Report[/bold blue]",
            items=[("Status", "No branch slots with decoys")],
            border_style="blue",
        )
        return
    rows = []
    for result in results:
        rows.append(
            (
                f"({result['row']}, {result['col']})",
                result["recorded"],
                "PASS" if result["recorded_ok"] else "FAIL",
                "PASS" if result["hard_ok"] else "FAIL",
                "N/A" if result["tier_one_ok"] is None else ("PASS" if result["tier_one_ok"] else "FAIL"),
                "N/A" if result["tier_two_ok"] is None else ("PASS" if result["tier_two_ok"] else "FAIL"),
                "N/A" if result["tier_three_ok"] is None else ("PASS" if result["tier_three_ok"] else "FAIL"),
                result["recorded_reason"] or "-",
            )
        )
    ConsoleDisplay.print_table(
        title="Recorded decoy stage checks",
        headers=("Slot", "Recorded", "Recorded OK", "Hard", "Tier1", "Tier2", "Tier3", "Reason"),
        rows=rows,
        panel_title="[bold blue]Decoy Stage Report[/bold blue]",
        border_style="blue",
    )


def _print_representative_cases(dataset):
    cases = _first_filter_assignment(dataset) + _decoy_prefix_cases(dataset)
    if not cases:
        ConsoleDisplay.print_kv_panel(
            title="[bold yellow]Representative Cases[/bold yellow]",
            items=[("Status", "No hidden-slot example cases available")],
            border_style="yellow",
        )
        return
    rows = [_evaluate_case(dataset, case) for case in cases]
    ConsoleDisplay.print_table(
        title="Representative validation cases",
        headers=("Case", "Recorded Stage", "Assignments", "Slot", "Global@Truth", "Global@OpenNone", "Failure Reasons"),
        rows=rows,
        panel_title="[bold yellow]Representative Cases[/bold yellow]",
        border_style="yellow",
    )


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Validate and inspect a generated dataset file.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            f"  python data_generation/validation.py {DEFAULT_VALIDATION_EXAMPLE_PATH}\n"
            f"  python data_generation/validation.py {DEFAULT_VALIDATION_EXAMPLE_PATH} --instance-index 0"
        ),
    )
    parser.add_argument("dataset_path", nargs="?", default=DEFAULT_VALIDATION_EXAMPLE_PATH)
    parser.add_argument("--instance-index", type=int, help="Only inspect one instance by index.")
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    payload = _load_payload(args.dataset_path)
    instances = payload["instances"]

    summaries = []
    for dataset in instances:
        summaries.append(_summarize_instance(dataset))
        if not validate_dataset(dataset):
            raise SystemExit(f"Validation failed: {dataset.get('instance_id', '-')}")

    ConsoleDisplay.print_dataset_summary_report(payload["domain"], summaries)

    if args.instance_index is not None:
        if args.instance_index < 0 or args.instance_index >= len(instances):
            raise SystemExit(f"instance_index {args.instance_index} is out of range")
        representative_instances = [instances[args.instance_index]]
    else:
        representative_instances = _choose_representative_instances(instances)

    for dataset in representative_instances:
        ConsoleDisplay.print_validation_summary(
            dataset.get("instance_id", "-"),
            dataset["domain"],
            True,
        )
        _print_instance_summary(dataset)
        ConsoleDisplay.print_solution_report("Truth solution report", _build_truth_report(dataset))
        _print_decoy_stage_report(dataset)
        _print_truth_decoy_combination_stats(dataset)
        _print_representative_cases(dataset)


if __name__ == "__main__":
    main()
