import itertools

from data_generation.domains import DOMAIN_SPECS
from data_generation.generation.constraints import item_matches_slot_constraint
from data_generation.valid.utils import build_slot_map


def _replace_assignments(truth_solution, assignments):
    solution = [row[:] for row in truth_solution]
    for (row_index, col_index), candidate_id in assignments.items():
        solution[row_index][col_index] = candidate_id
    return solution


def _iter_prior_branch_assignments(branch_slots):
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


def validate_dataset_structure(
    dataset,
    *,
    candidates_per_slot,
    branch_budget,
    validate_slot_constraints,
    validate_global_constraints,
):
    item_pool = dataset["item_pool"]
    truth_solution = dataset["truth_solution"]
    partial_solution = dataset["partial_solution"]
    rows = dataset["meta"]["rows"]
    cols = dataset["meta"]["cols"]
    expected_hidden_slots = dataset["meta"]["hidden_slots"]
    expected_candidates_per_slot = dataset["meta"]["candidates_per_slot"]
    expected_branch_budget = dataset["meta"]["branch_budget"]
    expected_branch_slot_count = dataset["meta"].get("branch_slot_count", 0)
    expected_branch_budget_allocations = dataset["meta"].get("branch_budget_allocations", [])

    if expected_candidates_per_slot != candidates_per_slot:
        return False
    if expected_branch_budget != branch_budget:
        return False

    hidden_slot_entries = list(dataset["slots"])
    slot_map = build_slot_map(hidden_slot_entries)
    if len(hidden_slot_entries) != expected_hidden_slots:
        return False
    if len(dataset.get("hidden_slots", [])) != expected_hidden_slots:
        return False

    for row_index in range(rows):
        for col_index in range(cols):
            truth_id = truth_solution[row_index][col_index]
            if truth_id not in item_pool:
                return False
            slot_entry = slot_map.get((row_index, col_index))
            expected_partial_value = None if slot_entry is not None else truth_id
            if partial_solution[row_index][col_index] != expected_partial_value:
                return False

    global_ok, _ = validate_global_constraints(
        truth_solution,
        dataset["domain"],
        dataset["global_constraints"],
        item_pool,
        dataset["slots"],
        truth_solution=truth_solution,
    )
    if not global_ok:
        return False

    branch_slots = sorted(
        [slot for slot in hidden_slot_entries if slot.get("is_branch_slot")],
        key=lambda slot: slot["branch_rank"],
    )
    if len(branch_slots) != expected_branch_slot_count:
        return False
    if [slot["branch_rank"] for slot in branch_slots] != list(range(len(branch_slots))):
        return False
    actual_branch_budget_allocations = [slot.get("allocated_budget", 0) for slot in branch_slots]
    if actual_branch_budget_allocations != expected_branch_budget_allocations:
        return False
    if any(value <= 0 for value in actual_branch_budget_allocations):
        return False
    max_allowed_allocation = expected_branch_budget if len(branch_slots) <= 2 else expected_branch_budget // 2
    if any(value > max_allowed_allocation for value in actual_branch_budget_allocations):
        return False
    if sum(slot.get("allocated_budget", 0) for slot in branch_slots) != expected_branch_budget:
        return False

    for slot in hidden_slot_entries:
        truth_id = truth_solution[slot["row"]][slot["col"]]
        if slot["truth_id"] != truth_id:
            return False
        if len(slot["candidate_ids"]) != expected_candidates_per_slot:
            return False
        if len(set(slot["candidate_ids"])) != len(slot["candidate_ids"]):
            return False
        if truth_id not in slot["candidate_ids"]:
            return False
        if any(candidate_id not in item_pool for candidate_id in slot["candidate_ids"]):
            return False
        if "slot_constraints" not in slot:
            return False

        decoy_ids = slot.get("decoy_ids", [])
        filter_ids = slot.get("filter_candidate_ids", [])
        if set(decoy_ids) & set(filter_ids):
            return False
        if any(candidate_id not in slot["candidate_ids"] for candidate_id in [*decoy_ids, *filter_ids]):
            return False
        if slot.get("is_branch_slot"):
            if len(decoy_ids) != slot.get("allocated_budget", 0):
                return False
        elif decoy_ids:
            return False

        slot_ok, _ = validate_slot_constraints(
            truth_solution,
            dataset["domain"],
            slot["row"],
            slot["col"],
            slot["slot_constraints"],
            item_pool,
            dataset["slots"],
            truth_solution=truth_solution,
        )
        if not slot_ok:
            return False

        for candidate_id in decoy_ids:
            item = item_pool[candidate_id]
            if not item_matches_slot_constraint(item, slot["slot_constraints"], DOMAIN_SPECS[dataset["domain"]]["slot_rules"]):
                return False
            trial_solution = _replace_assignments(
                truth_solution,
                {((slot["row"], slot["col"])): candidate_id},
            )
            global_ok, _ = validate_global_constraints(
                trial_solution,
                dataset["domain"],
                dataset["global_constraints"],
                item_pool,
                dataset["slots"],
                truth_solution=truth_solution,
            )
            if global_ok:
                return False

        for candidate_id in filter_ids:
            item = item_pool[candidate_id]
            if item_matches_slot_constraint(item, slot["slot_constraints"], DOMAIN_SPECS[dataset["domain"]]["slot_rules"]):
                return False

    for current_index, slot in enumerate(branch_slots):
        previous_slots = branch_slots[:current_index]
        for candidate_id in slot["decoy_ids"]:
            for prior_assignments in _iter_prior_branch_assignments(previous_slots):
                trial_assignments = dict(prior_assignments)
                trial_assignments[(slot["row"], slot["col"])] = candidate_id
                trial_solution = _replace_assignments(truth_solution, trial_assignments)
                global_ok, _ = validate_global_constraints(
                    trial_solution,
                    dataset["domain"],
                    dataset["global_constraints"],
                    item_pool,
                    dataset["slots"],
                    truth_solution=truth_solution,
                )
                if global_ok:
                    return False

    return True
