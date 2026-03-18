import itertools
import random
from collections import Counter

from data_generation.domains import DOMAIN_BUILDERS, DOMAIN_SPECS
from data_generation.generation.constants import DEFAULT_SLOT_CANDIDATE_RETRIES
from data_generation.generation.constraint_plan import active_rules
from data_generation.generation.constraints import (
    build_slot_constraint,
    item_matches_slot_constraint,
)
from data_generation.valid.rules import rule_satisfied

PREFERRED_OPEN_MATCH_RELAX_AFTER_TRIES = 50

def global_constraints_satisfied(solution, domain, global_constraints, item_pool):
    spec = DOMAIN_SPECS[domain]
    ids = [item_id for row in solution for item_id in row if item_id is not None]
    global_group = [item_pool[item_id] for item_id in ids]
    is_complete = all(item_id is not None for row in solution for item_id in row)
    return all(
        rule_satisfied(
            rule,
            global_constraints[rule["name"]],
            global_group,
            is_complete,
            solution,
            item_pool,
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


def _solution_with_open_future_hidden_slots(truth_solution, assignments, future_hidden_positions):
    solution = _solution_with_assignments(truth_solution, assignments)
    for row_index, col_index in future_hidden_positions:
        solution[row_index][col_index] = None
    return solution


def _iter_required_open_assignments(previous_branch_slots):
    yield {}


def _iter_preferred_open_assignments(previous_branch_slots):
    for slot in previous_branch_slots:
        for candidate_id in slot.get("decoy_ids", []):
            yield {(slot["row"], slot["col"]): candidate_id}


def _build_rule_context(solution, item_pool, global_rules):
    items = [item_pool[item_id] for row in solution for item_id in row if item_id is not None]
    row_count = len(solution)
    contexts = {}
    for rule in global_rules:
        rule_type = rule["type"]
        rule_name = rule["name"]
        if rule_type in ("sum_min", "sum_max"):
            contexts[rule_name] = sum(item[rule["attr"]] for item in items)
            continue
        if rule_type == "max_cap":
            contexts[rule_name] = max((item[rule["attr"]] for item in items), default=0)
            continue
        if rule_type == "repeat_max":
            counts = Counter(item[rule["attr"]] for item in items)
            contexts[rule_name] = counts
            continue
        if rule_type == "count_min":
            contexts[rule_name] = sum(
                1 for item in items if item[rule["predicate_key"]] == rule["predicate_value"]
            )
            continue
        if rule_type == "count_min_threshold":
            contexts[rule_name] = sum(1 for item in items if item[rule["attr"]] >= rule["threshold"])
            continue
        if rule_type == "max_row_sum":
            row_sums = [0] * row_count
            for row_index, row in enumerate(solution):
                for item_id in row:
                    if item_id is None:
                        continue
                    row_sums[row_index] += item_pool[item_id][rule["attr"]]
            contexts[rule_name] = row_sums
            continue
        raise ValueError(f"Unsupported rule type: {rule_type}")
    return contexts


def _build_prior_assignment_contexts(
    *,
    domain,
    truth_solution,
    item_pool,
    global_constraints,
    row_index,
    col_index,
    previous_branch_slots,
    future_hidden_positions,
):
    global_rules = active_rules(DOMAIN_SPECS[domain]["global_rules"], global_constraints)
    required_open_contexts = []
    for open_assignments in _iter_required_open_assignments(previous_branch_slots):
        open_solution = _solution_with_open_future_hidden_slots(
            truth_solution,
            open_assignments,
            future_hidden_positions,
        )
        open_solution[row_index][col_index] = None
        required_open_contexts.append(_build_rule_context(open_solution, item_pool, global_rules))

    preferred_open_contexts = []
    for open_assignments in _iter_preferred_open_assignments(previous_branch_slots):
        open_solution = _solution_with_open_future_hidden_slots(
            truth_solution,
            open_assignments,
            future_hidden_positions,
        )
        open_solution[row_index][col_index] = None
        preferred_open_contexts.append(_build_rule_context(open_solution, item_pool, global_rules))

    full_contexts = []
    for prior_assignments in _iter_previous_decoy_assignments(previous_branch_slots):
        full_solution = _solution_with_assignments(truth_solution, prior_assignments)
        full_solution[row_index][col_index] = None
        full_contexts.append(_build_rule_context(full_solution, item_pool, global_rules))
    combined_preferred_open_contexts = [*required_open_contexts, *preferred_open_contexts]
    return global_rules, required_open_contexts, combined_preferred_open_contexts, full_contexts


def _rule_is_valid_with_candidate(rule, constraint_value, context_value, candidate, row_index):
    rule_type = rule["type"]
    if rule_type in ("sum_min", "sum_max"):
        observed = context_value + candidate[rule["attr"]]
        return observed >= constraint_value if rule_type == "sum_min" else observed <= constraint_value
    if rule_type == "max_cap":
        return max(context_value, candidate[rule["attr"]]) <= constraint_value
    if rule_type == "repeat_max":
        return (context_value.get(candidate[rule["attr"]], 0) + 1) <= constraint_value
    if rule_type == "count_min":
        observed = context_value + int(candidate[rule["predicate_key"]] == rule["predicate_value"])
        return observed >= constraint_value
    if rule_type == "count_min_threshold":
        observed = context_value + int(candidate[rule["attr"]] >= rule["threshold"])
        return observed >= constraint_value
    if rule_type == "max_row_sum":
        row_sums = list(context_value)
        row_sums[row_index] += candidate[rule["attr"]]
        return max(row_sums) <= constraint_value
    raise ValueError(f"Unsupported rule type: {rule_type}")


def _candidate_satisfies_decoy_requirements(
    *,
    candidate,
    row_index,
    global_constraints,
    global_rules,
    full_assignment_contexts,
    is_last_branch_slot,
):
    for full_context in full_assignment_contexts:
        full_has_violation = False
        for rule in global_rules:
            constraint_value = global_constraints[rule["name"]]
            if not _rule_is_valid_with_candidate(
                rule,
                constraint_value,
                full_context[rule["name"]],
                candidate,
                row_index,
            ):
                full_has_violation = True
                break
        if not full_has_violation:
            return False
    return True


def _count_preferred_open_matches(
    *,
    candidate,
    row_index,
    global_constraints,
    global_rules,
    preferred_open_assignment_contexts,
):
    matched_contexts = 0
    for open_context in preferred_open_assignment_contexts:
        is_valid = True
        for rule in global_rules:
            constraint_value = global_constraints[rule["name"]]
            if rule["type"] in ("sum_min", "count_min", "count_min_threshold"):
                continue
            if not _rule_is_valid_with_candidate(
                rule,
                constraint_value,
                open_context[rule["name"]],
                candidate,
                row_index,
            ):
                is_valid = False
                break
        if is_valid:
            matched_contexts += 1
    return matched_contexts


def _infer_numeric_attr_bounds(attr, item_pool, global_rules, slot_constraint, slot_rules):
    values = [
        item[attr]
        for item in item_pool.values()
        if attr in item and isinstance(item[attr], int)
    ]
    lower = min(values) if values else 0
    upper = max(values) if values else 100
    for rule in global_rules:
        if rule.get("attr") != attr:
            continue
        if "per_item_cap" in rule:
            upper = max(upper, int(rule["per_item_cap"]))
        if "cap" in rule:
            upper = max(upper, int(rule["cap"]))
        if "threshold" in rule:
            upper = max(upper, int(rule["threshold"]))
        if "floor" in rule:
            lower = min(lower, int(rule["floor"]))
    for rule in slot_rules:
        if rule["name"] not in slot_constraint.get("active_rule_names", []):
            continue
        if rule["attr"] != attr:
            continue
        constraint_value = int(slot_constraint[rule["name"]])
        if rule["kind"] == "max":
            upper = min(upper, constraint_value)
        if rule["kind"] == "min":
            lower = max(lower, constraint_value)
    return lower, upper


def _candidate_value_catalog(attr, item_pool, candidate):
    values = {item[attr] for item in item_pool.values() if attr in item}
    if attr in candidate:
        values.add(candidate[attr])
    return list(values)


def _build_target_specs(
    *,
    item_pool,
    global_rules,
    global_constraints,
    required_open_assignment_contexts,
    full_assignment_contexts,
    row_index,
    is_last_branch_slot,
    slot_constraint,
    slot_rules,
):
    primary_target_specs = []
    fallback_target_specs = []
    for rule in global_rules:
        rule_name = rule["name"]
        constraint_value = global_constraints[rule_name]
        rule_type = rule["type"]

        if rule_type == "sum_max":
            lower = max(int(constraint_value - context[rule_name] + 1) for context in full_assignment_contexts)
            upper = None if is_last_branch_slot else min(
                int(constraint_value - context[rule_name]) for context in required_open_assignment_contexts
            )
            attr_low, attr_high = _infer_numeric_attr_bounds(
                rule["attr"], item_pool, global_rules, slot_constraint, slot_rules
            )
            low = max(lower, attr_low)
            high = attr_high if upper is None else min(upper, attr_high)
            if low <= high:
                primary_target_specs.append(
                    {"kind": "numeric_interval", "attr": rule["attr"], "low": low, "high": high}
                )
            continue

        if rule_type == "max_row_sum":
            lower = max(
                int(constraint_value - context[rule_name][row_index] + 1)
                for context in full_assignment_contexts
            )
            upper = None if is_last_branch_slot else min(
                int(constraint_value - context[rule_name][row_index])
                for context in required_open_assignment_contexts
            )
            attr_low, attr_high = _infer_numeric_attr_bounds(
                rule["attr"], item_pool, global_rules, slot_constraint, slot_rules
            )
            low = max(lower, attr_low)
            high = attr_high if upper is None else min(upper, attr_high)
            if low <= high:
                primary_target_specs.append(
                    {"kind": "numeric_interval", "attr": rule["attr"], "low": low, "high": high}
                )
            continue

        if rule_type == "max_cap":
            if not is_last_branch_slot:
                continue
            attr_low, attr_high = _infer_numeric_attr_bounds(
                rule["attr"], item_pool, global_rules, slot_constraint, slot_rules
            )
            low = max(int(constraint_value) + 1, attr_low)
            if low <= attr_high:
                primary_target_specs.append(
                    {"kind": "numeric_interval", "attr": rule["attr"], "low": low, "high": attr_high}
                )
            continue

        if rule_type == "sum_min":
            upper = min(int(constraint_value - context[rule_name] - 1) for context in full_assignment_contexts)
            attr_low, attr_high = _infer_numeric_attr_bounds(
                rule["attr"], item_pool, global_rules, slot_constraint, slot_rules
            )
            high = min(upper, attr_high)
            if attr_low <= high:
                fallback_target_specs.append(
                    {"kind": "numeric_interval", "attr": rule["attr"], "low": attr_low, "high": high}
                )
            continue

        if rule_type == "count_min":
            if all(context[rule_name] < constraint_value for context in full_assignment_contexts):
                fallback_target_specs.append(
                    {
                        "kind": "categorical_exclude",
                        "attr": rule["predicate_key"],
                        "excluded_value": rule["predicate_value"],
                    }
                )
            continue

        if rule_type == "count_min_threshold":
            if all(context[rule_name] < constraint_value for context in full_assignment_contexts):
                attr_low, attr_high = _infer_numeric_attr_bounds(
                    rule["attr"], item_pool, global_rules, slot_constraint, slot_rules
                )
                high = min(int(rule["threshold"]) - 1, attr_high)
                if attr_low <= high:
                    fallback_target_specs.append(
                        {"kind": "numeric_interval", "attr": rule["attr"], "low": attr_low, "high": high}
                    )
            continue

        if rule_type == "repeat_max":
            shared_values = None
            for full_counter, open_counter in itertools.product(
                [context[rule_name] for context in full_assignment_contexts],
                [context[rule_name] for context in required_open_assignment_contexts] if not is_last_branch_slot else [Counter()],
            ):
                values = {
                    value
                    for value, count in full_counter.items()
                    if count >= constraint_value and (is_last_branch_slot or open_counter.get(value, 0) < constraint_value)
                }
                shared_values = values if shared_values is None else (shared_values & values)
            if shared_values:
                primary_target_specs.append(
                    {"kind": "categorical_include", "attr": rule["attr"], "choices": sorted(shared_values)}
                )
            continue
    return primary_target_specs or fallback_target_specs


def _apply_target_spec(candidate, target_spec, item_pool):
    guided = dict(candidate)
    kind = target_spec["kind"]
    if kind == "numeric_interval":
        low = int(target_spec["low"])
        high = int(target_spec["high"])
        if low > high:
            return None
        guided[target_spec["attr"]] = random.randint(low, high)
        return guided
    if kind == "categorical_include":
        choices = list(target_spec["choices"])
        if not choices:
            return None
        guided[target_spec["attr"]] = random.choice(choices)
        return guided
    if kind == "categorical_exclude":
        choices = [
            value
            for value in _candidate_value_catalog(target_spec["attr"], item_pool, candidate)
            if value != target_spec["excluded_value"]
        ]
        if not choices:
            return None
        guided[target_spec["attr"]] = random.choice(choices)
        return guided
    return guided


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
    is_last_branch_slot,
    future_hidden_positions,
    next_index,
):
    spec = DOMAIN_SPECS[domain]
    decoy_ids = []
    global_rules, required_open_assignment_contexts, preferred_open_assignment_contexts, full_assignment_contexts = _build_prior_assignment_contexts(
        domain=domain,
        truth_solution=truth_solution,
        item_pool=item_pool,
        global_constraints=global_constraints,
        row_index=row_index,
        col_index=col_index,
        previous_branch_slots=previous_branch_slots,
        future_hidden_positions=future_hidden_positions,
    )
    is_last_hidden_slot = not future_hidden_positions
    target_specs = _build_target_specs(
        item_pool=item_pool,
        global_rules=global_rules,
        global_constraints=global_constraints,
        required_open_assignment_contexts=required_open_assignment_contexts,
        full_assignment_contexts=full_assignment_contexts,
        row_index=row_index,
        is_last_branch_slot=is_last_branch_slot,
        slot_constraint=slot_constraint,
        slot_rules=spec["slot_rules"],
    )
    fallback_candidates: list[tuple[str, dict]] = []
    relax_preferred_open_requirement = False
    effective_preferred_open_assignment_contexts = [] if is_last_branch_slot else preferred_open_assignment_contexts

    for attempt_index in range(1, DEFAULT_SLOT_CANDIDATE_RETRIES + 1):
        if len(decoy_ids) >= decoy_count:
            break

        candidate_id, candidate = _sample_candidate(domain, next_index)
        next_index += 1
        if candidate_id in item_pool:
            continue
        if target_specs and random.random() < 0.85:
            target_spec = random.choice(target_specs)
            guided_candidate = _apply_target_spec(candidate, target_spec, item_pool)
            if guided_candidate is not None:
                candidate = guided_candidate
        if not item_matches_slot_constraint(candidate, slot_constraint, spec["slot_rules"]):
            continue

        if not _candidate_satisfies_decoy_requirements(
            candidate=candidate,
            row_index=row_index,
            global_constraints=global_constraints,
            global_rules=global_rules,
            full_assignment_contexts=full_assignment_contexts,
            is_last_branch_slot=is_last_branch_slot,
        ):
            continue

        preferred_match_count = _count_preferred_open_matches(
            candidate=candidate,
            row_index=row_index,
            global_constraints=global_constraints,
            global_rules=global_rules,
            preferred_open_assignment_contexts=effective_preferred_open_assignment_contexts,
        )
        if (
            effective_preferred_open_assignment_contexts
            and not relax_preferred_open_requirement
            and preferred_match_count == 0
        ):
            fallback_candidates.append((candidate_id, candidate))
            if attempt_index >= PREFERRED_OPEN_MATCH_RELAX_AFTER_TRIES:
                relax_preferred_open_requirement = True
            continue

        item_pool[candidate_id] = candidate
        decoy_ids.append(candidate_id)

    while len(decoy_ids) < decoy_count and (
        relax_preferred_open_requirement or not effective_preferred_open_assignment_contexts
    ) and fallback_candidates:
        fallback_candidate_id, fallback_candidate = fallback_candidates.pop(0)
        if fallback_candidate_id in item_pool:
            continue
        item_pool[fallback_candidate_id] = fallback_candidate
        decoy_ids.append(fallback_candidate_id)

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
    is_last_branch_slot,
    previous_branch_slots,
    future_hidden_positions,
    next_index,
):
    spec = DOMAIN_SPECS[domain]
    truth_id = truth_solution[row_index][col_index]
    truth_item = item_pool[truth_id]
    slot_constraint = build_slot_constraint(domain, row_index, col_index, truth_item, selected_rules)

    if 1 + allocated_budget > candidates_per_slot:
        return None, next_index
    decoy_ids: list[str] = []
    if allocated_budget > 0:
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
            is_last_branch_slot=is_last_branch_slot,
            future_hidden_positions=future_hidden_positions,
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
