import itertools
import random

from data_generation.domains import DOMAIN_BUILDERS, DOMAIN_SPECS
from data_generation.generation.constants import DEFAULT_SLOT_CANDIDATE_RETRIES
from data_generation.generation.constraint_plan import active_rules, global_items
from data_generation.generation.constraints import (
    aggregate_constraint_satisfied,
    build_slot_constraint,
    item_matches_slot_constraint,
)

def global_constraints_satisfied(solution, domain, global_constraints, item_pool):
    spec = DOMAIN_SPECS[domain]
    global_group = global_items(solution, item_pool)
    return all(
        aggregate_constraint_satisfied(
            rule,
            global_constraints[rule["name"]],
            global_group,
            truth_solution=solution,
            item_lookup=item_pool,
        )
        for rule in active_rules(spec["global_rules"], global_constraints)
    )


def _sample_candidate(domain, next_index):
    spec = DOMAIN_SPECS[domain]
    candidate = DOMAIN_BUILDERS[domain](next_index)
    return candidate[spec["id_key"]], candidate


def _solution_with_assignments(truth_solution, assignments):
    solution = [row[:] for row in truth_solution]
    for (row_index, col_index), candidate_id in assignments.items():
        solution[row_index][col_index] = candidate_id
    return solution


def _iter_previous_decoy_assignments(previous_branch_slots):
    if not previous_branch_slots:
        yield {}
        return

    yield {}
    for subset_size in range(1, len(previous_branch_slots) + 1):
        for subset in itertools.combinations(previous_branch_slots, subset_size):
            decoy_lists = [slot["decoy_ids"] for slot in subset]
            for selected_ids in itertools.product(*decoy_lists):
                assignment = {}
                for slot, candidate_id in zip(subset, selected_ids):
                    assignment[(slot["row"], slot["col"])] = candidate_id
                yield assignment


def _candidate_breaks_global_with_history(
    *,
    domain,
    truth_solution,
    item_pool,
    global_constraints,
    row_index,
    col_index,
    candidate_id,
    previous_branch_slots,
):
    for prior_assignments in _iter_previous_decoy_assignments(previous_branch_slots):
        trial_assignments = dict(prior_assignments)
        trial_assignments[(row_index, col_index)] = candidate_id
        trial_solution = _solution_with_assignments(truth_solution, trial_assignments)
        if global_constraints_satisfied(trial_solution, domain, global_constraints, item_pool):
            return False
    return True


def _extend_decoy_ids(
    *,
    domain,
    truth_solution,
    item_pool,
    global_constraints,
    row_index,
    col_index,
    slot_constraint,
    decoy_count,
    previous_branch_slots,
    next_index,
):
    spec = DOMAIN_SPECS[domain]
    decoy_ids = []

    for _ in range(DEFAULT_SLOT_CANDIDATE_RETRIES):
        if len(decoy_ids) >= decoy_count:
            break

        candidate_id, candidate = _sample_candidate(domain, next_index)
        next_index += 1
        if candidate_id in item_pool:
            continue
        if not item_matches_slot_constraint(candidate, slot_constraint, spec["slot_rules"]):
            continue

        trial_lookup = dict(item_pool)
        trial_lookup[candidate_id] = candidate
        if not _candidate_breaks_global_with_history(
            domain=domain,
            truth_solution=truth_solution,
            item_pool=trial_lookup,
            global_constraints=global_constraints,
            row_index=row_index,
            col_index=col_index,
            candidate_id=candidate_id,
            previous_branch_slots=previous_branch_slots,
        ):
            continue

        item_pool[candidate_id] = candidate
        decoy_ids.append(candidate_id)

    if len(decoy_ids) < decoy_count:
        return None, next_index
    return decoy_ids, next_index


def _extend_filter_ids(
    *,
    domain,
    item_pool,
    slot_constraint,
    filter_count,
    next_index,
):
    spec = DOMAIN_SPECS[domain]
    filter_ids = []

    for _ in range(DEFAULT_SLOT_CANDIDATE_RETRIES):
        if len(filter_ids) >= filter_count:
            break

        candidate_id, candidate = _sample_candidate(domain, next_index)
        next_index += 1
        if candidate_id in item_pool:
            continue
        if item_matches_slot_constraint(candidate, slot_constraint, spec["slot_rules"]):
            continue

        item_pool[candidate_id] = candidate
        filter_ids.append(candidate_id)

    if len(filter_ids) < filter_count:
        return None, next_index
    return filter_ids, next_index


def build_hidden_slot_entry(
    *,
    domain,
    truth_solution,
    item_pool,
    global_constraints,
    row_index,
    col_index,
    selected_rules,
    candidates_per_slot,
    branch_rank,
    allocated_budget,
    previous_branch_slots,
    next_index,
):
    spec = DOMAIN_SPECS[domain]
    truth_id = truth_solution[row_index][col_index]
    truth_item = item_pool[truth_id]
    slot_constraint = build_slot_constraint(domain, row_index, col_index, truth_item, selected_rules)

    if 1 + allocated_budget > candidates_per_slot:
        return None, next_index

    decoy_ids, next_index = _extend_decoy_ids(
        domain=domain,
        truth_solution=truth_solution,
        item_pool=item_pool,
        global_constraints=global_constraints,
        row_index=row_index,
        col_index=col_index,
        slot_constraint=slot_constraint,
        decoy_count=allocated_budget,
        previous_branch_slots=previous_branch_slots,
        next_index=next_index,
    )
    if decoy_ids is None:
        return None, next_index

    filter_ids, next_index = _extend_filter_ids(
        domain=domain,
        item_pool=item_pool,
        slot_constraint=slot_constraint,
        filter_count=candidates_per_slot - 1 - len(decoy_ids),
        next_index=next_index,
    )
    if filter_ids is None:
        return None, next_index

    candidate_ids = [truth_id, *decoy_ids, *filter_ids]
    random.shuffle(candidate_ids)
    return {
        "row": row_index,
        "col": col_index,
        "truth_id": truth_id,
        "is_hidden": True,
        "slot_constraints": slot_constraint,
        "candidate_ids": candidate_ids,
        "decoy_ids": decoy_ids,
        "filter_candidate_ids": filter_ids,
        "is_branch_slot": branch_rank is not None,
        "branch_rank": branch_rank,
        "allocated_budget": allocated_budget,
    }, next_index
