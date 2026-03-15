try:
    from . import (
        DEFAULT_CANDIDATES_PER_SLOT,
        DEFAULT_VALID_OPTIONS,
    )
    from .constraints import (
        aggregate_constraint_satisfied,
        item_matches_slot_constraint,
    )
    from .domains import DOMAIN_SPECS
except ImportError:
    from __init__ import (
        DEFAULT_CANDIDATES_PER_SLOT,
        DEFAULT_VALID_OPTIONS,
    )
    from constraints import (
        aggregate_constraint_satisfied,
        item_matches_slot_constraint,
    )
    from domains import DOMAIN_SPECS


DOMAIN_ITEM_LABELS = {
    "course": ("course", "courses"),
    "shopping": ("product", "products"),
    "travel": ("activity", "activities"),
    "workforce": ("worker", "workers"),
    "meal": ("dish", "dishes"),
    "pc_build": ("component", "components"),
}


def _label_for_attr(attr_name):
    return attr_name.replace("_", " ")


def _format_rule_message(domain, rule, value, scope_text):
    item_singular, item_plural = DOMAIN_ITEM_LABELS[domain]
    rule_type = rule["type"]

    if rule_type == "sum_min":
        return f"the total {_label_for_attr(rule['attr'])} of all {item_plural} in {scope_text} must be at least {value}"
    if rule_type == "sum_max":
        return f"the total {_label_for_attr(rule['attr'])} of all {item_plural} in {scope_text} must be at most {value}"
    if rule_type == "max_cap":
        return f"the maximum {_label_for_attr(rule['attr'])} of any {item_singular} in {scope_text} must be at most {value}"
    if rule_type == "repeat_max":
        return f"the same {_label_for_attr(rule['attr'])} can appear at most {value} times in {scope_text}"
    if rule_type == "count_min":
        return (
            f"there must be at least {value} {item_plural} in {scope_text} whose "
            f"{_label_for_attr(rule['predicate_key'])} is {rule['predicate_value']}"
        )
    if rule_type == "count_min_threshold":
        return (
            f"there must be at least {value} {item_plural} in {scope_text} whose "
            f"{_label_for_attr(rule['attr'])} is at least {rule['threshold']}"
        )
    if rule_type == "max_row_sum":
        return f"for any single row in {scope_text}, the total {_label_for_attr(rule['attr'])} must be at most {value}"
    return f"constraint '{rule['name']}' failed in {scope_text}"


def _build_constraint_maps(dataset):
    slot_map = {(slot["row"], slot["col"]): slot for slot in dataset["slots"]}
    row_map = {constraint["row"]: constraint for constraint in dataset["row_constraints"]}
    col_map = {constraint["col"]: constraint for constraint in dataset["col_constraints"]}
    return slot_map, row_map, col_map


def _build_slot_map(slots):
    return {(slot["row"], slot["col"]): slot for slot in slots}


def _active_rules(rule_specs, constraint):
    return [rule for rule in rule_specs if rule["name"] in constraint]


def _ids_to_items(item_ids, item_pool):
    items = []
    for item_id in item_ids:
        if item_id is None:
            continue
        if item_id not in item_pool:
            raise KeyError(item_id)
        items.append(item_pool[item_id])
    return items


def _partial_max_row_sum(solution, item_pool, attr):
    row_totals = []
    for row in solution:
        row_total = 0
        for item_id in row:
            if item_id is None:
                continue
            row_total += item_pool[item_id][attr]
        row_totals.append(row_total)
    return max(row_totals) if row_totals else 0


def _rule_satisfied(rule, constraint_value, items, is_complete, solution, item_pool):
    if rule["type"] in ("sum_min", "count_min", "count_min_threshold") and not is_complete:
        return True
    if rule["type"] == "max_row_sum" and not is_complete:
        return _partial_max_row_sum(solution, item_pool, rule["attr"]) <= constraint_value
    return aggregate_constraint_satisfied(
        rule,
        constraint_value,
        items,
        truth_solution=solution,
        item_lookup=item_pool,
    )


def validate_row_constraints(solution, domain, row_index, row_constraints, item_pool, slots):
    if row_index < 0 or row_index >= len(solution):
        return False, f"row {row_index} is out of range"
    rule_specs = DOMAIN_SPECS[domain]["row_rules"]
    row_constraint = row_constraints[row_index]
    row_ids = list(solution[row_index])
    slot_map = _build_slot_map(slots)
    for col_index, item_id in enumerate(row_ids):
        if item_id is None:
            continue
        if item_id not in slot_map[(row_index, col_index)]["candidate_ids"]:
            return False, (
                f"slot ({row_index}, {col_index}) contains id '{item_id}', "
                "which is not one of the candidate options for that slot"
            )
    try:
        row_items = _ids_to_items(row_ids, item_pool)
    except KeyError as exc:
        return False, f"unknown item id '{exc.args[0]}' appears in row {row_index}"

    is_complete = all(item_id is not None for item_id in row_ids)
    for rule in _active_rules(rule_specs, row_constraint):
        if not _rule_satisfied(
            rule,
            row_constraint[rule["name"]],
            row_items,
            is_complete,
            solution,
            item_pool,
        ):
            return False, _format_rule_message(domain, rule, row_constraint[rule["name"]], f"row {row_index}")
    return True, None


def validate_col_constraints(solution, domain, col_index, col_constraints, item_pool, slots):
    if not solution or col_index < 0 or col_index >= len(solution[0]):
        return False, f"column {col_index} is out of range"
    rule_specs = DOMAIN_SPECS[domain]["col_rules"]
    col_constraint = col_constraints[col_index]
    col_ids = [solution[row_index][col_index] for row_index in range(len(solution))]
    slot_map = _build_slot_map(slots)
    for row_index, item_id in enumerate(col_ids):
        if item_id is None:
            continue
        if item_id not in slot_map[(row_index, col_index)]["candidate_ids"]:
            return False, (
                f"slot ({row_index}, {col_index}) contains id '{item_id}', "
                "which is not one of the candidate options for that slot"
            )
    try:
        col_items = _ids_to_items(col_ids, item_pool)
    except KeyError as exc:
        return False, f"unknown item id '{exc.args[0]}' appears in column {col_index}"

    is_complete = all(item_id is not None for item_id in col_ids)
    for rule in _active_rules(rule_specs, col_constraint):
        if not _rule_satisfied(
            rule,
            col_constraint[rule["name"]],
            col_items,
            is_complete,
            solution,
            item_pool,
        ):
            return False, _format_rule_message(domain, rule, col_constraint[rule["name"]], f"column {col_index}")
    return True, None


def validate_global_constraints(solution, domain, global_constraints, item_pool, slots):
    rule_specs = DOMAIN_SPECS[domain]["global_rules"]
    global_ids = [item_id for row in solution for item_id in row]
    slot_map = _build_slot_map(slots)
    for row_index, row in enumerate(solution):
        for col_index, item_id in enumerate(row):
            if item_id is None:
                continue
            if item_id not in slot_map[(row_index, col_index)]["candidate_ids"]:
                return False, (
                    f"slot ({row_index}, {col_index}) contains id '{item_id}', "
                    "which is not one of the candidate options for that slot"
                )
    try:
        all_items = _ids_to_items(global_ids, item_pool)
    except KeyError as exc:
        return False, f"unknown item id '{exc.args[0]}' appears in the solution"

    is_complete = all(item_id is not None for item_id in global_ids)
    for rule in _active_rules(rule_specs, global_constraints):
        if not _rule_satisfied(
            rule,
            global_constraints[rule["name"]],
            all_items,
            is_complete,
            solution,
            item_pool,
        ):
            return False, _format_rule_message(domain, rule, global_constraints[rule["name"]], "the whole grid")
    return True, None


def validate_dataset(
    dataset,
    candidates_per_slot=DEFAULT_CANDIDATES_PER_SLOT,
    valid_options=DEFAULT_VALID_OPTIONS,
):
    domain = dataset["domain"]
    spec = DOMAIN_SPECS[domain]
    item_pool = dataset["item_pool"]
    truth_solution = dataset["truth_solution"]
    rows = dataset["meta"]["rows"]
    cols = dataset["meta"]["cols"]
    slot_map, row_map, col_map = _build_constraint_maps(dataset)

    for row_index in range(rows):
        for col_index in range(cols):
            truth_id = truth_solution[row_index][col_index]
            if truth_id not in item_pool:
                return False
            slot_entry = slot_map[(row_index, col_index)]
            if slot_entry["truth_id"] != truth_id:
                return False
            if len(slot_entry["candidate_ids"]) != candidates_per_slot:
                return False
            if len(set(slot_entry["candidate_ids"])) != len(slot_entry["candidate_ids"]):
                return False
            valid_candidate_ids = slot_entry.get("valid_candidate_ids")
            if valid_candidate_ids is None or len(set(valid_candidate_ids)) != len(valid_candidate_ids):
                return False
            if truth_id not in slot_entry["candidate_ids"] or truth_id not in valid_candidate_ids:
                return False
            if any(candidate_id not in slot_entry["candidate_ids"] for candidate_id in valid_candidate_ids):
                return False
            if any(candidate_id not in item_pool for candidate_id in slot_entry["candidate_ids"]):
                return False
            if any(
                not item_matches_slot_constraint(
                    item_pool[candidate_id],
                    slot_entry["slot_constraints"],
                    spec["slot_rules"],
                )
                for candidate_id in slot_entry["candidate_ids"]
            ):
                return False

            computed_valid_ids = []
            for candidate_id in slot_entry["candidate_ids"]:
                trial_solution = [row[:] for row in truth_solution]
                trial_solution[row_index][col_index] = candidate_id
                row_ok, _ = validate_row_constraints(
                    trial_solution,
                    domain,
                    row_index,
                    dataset["row_constraints"],
                    item_pool,
                    dataset["slots"],
                )
                if not row_ok:
                    continue
                col_ok, _ = validate_col_constraints(
                    trial_solution,
                    domain,
                    col_index,
                    dataset["col_constraints"],
                    item_pool,
                    dataset["slots"],
                )
                if not col_ok:
                    continue
                global_ok, _ = validate_global_constraints(
                    trial_solution,
                    domain,
                    dataset["global_constraints"],
                    item_pool,
                    dataset["slots"],
                )
                if global_ok:
                    computed_valid_ids.append(candidate_id)
            if set(computed_valid_ids) != set(valid_candidate_ids):
                return False
            if len(computed_valid_ids) != valid_options:
                return False

    for row_index in range(rows):
        row_ok, _ = validate_row_constraints(
            truth_solution,
            domain,
            row_index,
            dataset["row_constraints"],
            item_pool,
            dataset["slots"],
        )
        if not row_ok:
            return False

    for col_index in range(cols):
        col_ok, _ = validate_col_constraints(
            truth_solution,
            domain,
            col_index,
            dataset["col_constraints"],
            item_pool,
            dataset["slots"],
        )
        if not col_ok:
            return False

    global_ok, _ = validate_global_constraints(
        truth_solution,
        domain,
        dataset["global_constraints"],
        item_pool,
        dataset["slots"],
    )
    return global_ok
