import random
from math import ceil, sqrt

from data_generation.domains import DOMAIN_SPECS
from data_generation.generation.constants import (
    DEFAULT_BRANCH_BUDGETS,
    DEFAULT_CANDIDATES_PER_SLOT,
    DEFAULT_COLS,
    DEFAULT_ROWS,
)
from data_generation.generation.constraint_plan import build_truth_constraints
from data_generation.generation.items import generate_item_pool, generate_truth_solution
from data_generation.generation.slot_candidates import build_hidden_slot_entry
from data_generation.generation.task_instruction import build_task_instruction_from_instance


def compute_effective_candidates_per_slot(hidden_slots: int, candidates_per_slot: int, branch_budget: int) -> int:
    if hidden_slots <= 0:
        return candidates_per_slot
    # truth + decoys + 至少 1 个 filter
    return max(candidates_per_slot, branch_budget + 2)


def compute_branch_slot_count(hidden_slots: int, branch_budget: int) -> int:
    if hidden_slots <= 0 or branch_budget <= 0:
        return 0
    return min(hidden_slots, ceil(sqrt(branch_budget)))


def _max_branch_allocation(branch_budget: int, branch_slot_count: int) -> int:
    if branch_slot_count <= 2:
        return branch_budget
    return branch_budget // 2


def _is_branch_split_feasible(branch_budget: int, branch_slot_count: int) -> bool:
    if branch_slot_count == 0:
        return branch_budget == 0
    if branch_budget < branch_slot_count:
        return False
    max_allocation = _max_branch_allocation(branch_budget, branch_slot_count)
    return branch_budget <= branch_slot_count * max_allocation


def resolve_branch_slot_count(hidden_slots: int, branch_budget: int) -> int:
    branch_slot_count = compute_branch_slot_count(hidden_slots, branch_budget)
    while branch_slot_count > 0 and not _is_branch_split_feasible(branch_budget, branch_slot_count):
        branch_slot_count -= 1
    return branch_slot_count


def split_branch_budget(branch_budget: int, branch_slot_count: int) -> list[int]:
    if branch_budget < 0:
        raise ValueError("branch_budget must be non-negative")
    if branch_slot_count == 0:
        return []
    if not _is_branch_split_feasible(branch_budget, branch_slot_count):
        raise ValueError("branch_budget cannot be split under the current allocation cap")
    if branch_slot_count == 1:
        return [branch_budget]

    remaining = branch_budget
    allocations = []
    max_allocation = _max_branch_allocation(branch_budget, branch_slot_count)
    for index in range(branch_slot_count - 1):
        remaining_slots = branch_slot_count - index - 1
        min_current = max(1, remaining - remaining_slots * max_allocation)
        max_current = min(max_allocation, remaining - remaining_slots)
        current = random.randint(min_current, max_current)
        allocations.append(current)
        remaining -= current
    if remaining <= 0 or remaining > max_allocation:
        raise ValueError("branch_budget split produced an invalid tail allocation")
    allocations.append(remaining)
    random.shuffle(allocations)
    return allocations


def assign_slot_rule_sets(domain: str, ordered_hidden_positions: list[int], preferred_rules_per_slot: int = 2) -> dict[int, list[dict]]:
    slot_rules = list(DOMAIN_SPECS[domain]["slot_rules"])
    if not ordered_hidden_positions or not slot_rules:
        return {}

    assignments = {slot_index: [] for slot_index in ordered_hidden_positions}
    shuffled_rules = slot_rules[:]
    random.shuffle(shuffled_rules)

    # 先保证所有 hidden slots 联合起来覆盖全部 slot 属性。
    for rule_index, rule in enumerate(shuffled_rules):
        slot_index = ordered_hidden_positions[rule_index % len(ordered_hidden_positions)]
        assignments[slot_index].append(rule)

    target_rules_per_slot = min(preferred_rules_per_slot, len(slot_rules))
    for slot_index in ordered_hidden_positions:
        assigned_names = {rule["name"] for rule in assignments[slot_index]}
        while len(assignments[slot_index]) < target_rules_per_slot:
            available_rules = [rule for rule in shuffled_rules if rule["name"] not in assigned_names]
            if not available_rules:
                break
            chosen_rule = random.choice(available_rules)
            assignments[slot_index].append(chosen_rule)
            assigned_names.add(chosen_rule["name"])

    return assignments


def build_instance_scaffold(
    domain,
    rows=DEFAULT_ROWS,
    cols=DEFAULT_COLS,
    candidates_per_slot=DEFAULT_CANDIDATES_PER_SLOT,
    branch_budget=DEFAULT_BRANCH_BUDGETS[0],
    hidden_slots=1,
):
    total_cells = rows * cols
    if hidden_slots < 0 or hidden_slots > total_cells:
        return None
    if branch_budget < 0:
        return None

    effective_candidates = compute_effective_candidates_per_slot(
        hidden_slots,
        candidates_per_slot,
        branch_budget,
    )
    base_pool = generate_item_pool(
        domain,
        total_cells=total_cells,
        min_valid_options=max(1, branch_budget + 2),
        max_valid_options=max(1, branch_budget + 2),
    )
    truth_solution, base_lookup = generate_truth_solution(domain, base_pool, rows=rows, cols=cols)
    truth_ids = {item_id for row in truth_solution for item_id in row}
    item_pool = {item_id: base_lookup[item_id] for item_id in truth_ids}

    global_constraints = build_truth_constraints(
        domain,
        truth_solution,
        item_pool,
        rows,
        cols,
    )
    hidden_positions = set(random.sample(range(total_cells), hidden_slots))
    ordered_hidden_positions = sorted(hidden_positions)
    slot_rules_by_position = assign_slot_rule_sets(domain, ordered_hidden_positions)
    branch_slot_count = resolve_branch_slot_count(hidden_slots, branch_budget)
    branch_positions = sorted(random.sample(ordered_hidden_positions, branch_slot_count)) if branch_slot_count else []
    budget_allocations = split_branch_budget(branch_budget, branch_slot_count)
    branch_budget_by_slot = {
        slot_index: allocation
        for slot_index, allocation in zip(branch_positions, budget_allocations)
    }

    return {
        "domain": domain,
        "rows": rows,
        "cols": cols,
        "candidates_per_slot": effective_candidates,
        "requested_candidates_per_slot": candidates_per_slot,
        "branch_budget": branch_budget,
        "branch_slot_count": branch_slot_count,
        "branch_budget_allocations": budget_allocations,
        "truth_solution": truth_solution,
        "base_item_pool": item_pool,
        "global_constraints": global_constraints,
        "hidden_positions": hidden_positions,
        "ordered_hidden_positions": ordered_hidden_positions,
        "slot_rules_by_position": slot_rules_by_position,
        "branch_budget_by_slot": branch_budget_by_slot,
        "next_index_start": len(base_pool),
    }


def build_instance_from_scaffold(scaffold):
    domain = scaffold["domain"]
    rows = scaffold["rows"]
    cols = scaffold["cols"]
    candidates_per_slot = scaffold["candidates_per_slot"]
    truth_solution = scaffold["truth_solution"]
    global_constraints = scaffold["global_constraints"]
    hidden_positions = scaffold["hidden_positions"]
    ordered_hidden_positions = scaffold["ordered_hidden_positions"]
    slot_rules_by_position = scaffold["slot_rules_by_position"]
    branch_budget_by_slot = scaffold["branch_budget_by_slot"]
    item_pool = dict(scaffold["base_item_pool"])

    slots = []
    next_index = scaffold["next_index_start"]
    branch_history = []
    for slot_index in ordered_hidden_positions:
        row_index = slot_index // cols
        col_index = slot_index % cols
        allocated_budget = branch_budget_by_slot.get(slot_index, 0)
        branch_rank = len(branch_history) if slot_index in branch_budget_by_slot else None
        slot_entry, next_index = build_hidden_slot_entry(
            domain=domain,
            truth_solution=truth_solution,
            item_pool=item_pool,
            global_constraints=global_constraints,
            row_index=row_index,
            col_index=col_index,
            selected_rules=slot_rules_by_position[slot_index],
            candidates_per_slot=candidates_per_slot,
            branch_rank=branch_rank,
            allocated_budget=allocated_budget,
            previous_branch_slots=branch_history,
            next_index=next_index,
        )
        if slot_entry is None:
            return None
        slots.append(slot_entry)
        if slot_entry["is_branch_slot"]:
            branch_history.append(slot_entry)

    partial_solution = [row[:] for row in truth_solution]
    hidden_slot_entries = []
    for slot in slots:
        if slot["is_hidden"]:
            partial_solution[slot["row"]][slot["col"]] = None
            hidden_slot_entries.append({"row": slot["row"], "col": slot["col"]})

    instance = {
        "domain": domain,
        "meta": {
            "rows": rows,
            "cols": cols,
            "hidden_slots": len(hidden_positions),
            "branch_budget": scaffold["branch_budget"],
            "branch_slot_count": scaffold["branch_slot_count"],
            "branch_budget_allocations": scaffold["branch_budget_allocations"],
            "candidates_per_slot": candidates_per_slot,
            "requested_candidates_per_slot": scaffold["requested_candidates_per_slot"],
        },
        "global_constraints": global_constraints,
        "item_pool": item_pool,
        "truth_solution": truth_solution,
        "partial_solution": partial_solution,
        "hidden_slots": hidden_slot_entries,
        "slots": slots,
    }
    instance["task_instruction"] = build_task_instruction_from_instance(instance)
    return instance


def build_instance(
    domain,
    rows=DEFAULT_ROWS,
    cols=DEFAULT_COLS,
    candidates_per_slot=DEFAULT_CANDIDATES_PER_SLOT,
    branch_budget=DEFAULT_BRANCH_BUDGETS[0],
    hidden_slots=1,
):
    scaffold = build_instance_scaffold(
        domain=domain,
        rows=rows,
        cols=cols,
        candidates_per_slot=candidates_per_slot,
        branch_budget=branch_budget,
        hidden_slots=hidden_slots,
    )
    if scaffold is None:
        return None
    return build_instance_from_scaffold(scaffold)
