import random

from data_generation.domains import DOMAIN_SPECS


def get_rule_candidates(item, rule):
    candidates = []
    observed_value = item[rule["attr"]]

    for candidate in rule["candidates"]:
        if rule["kind"] == "max" and candidate >= observed_value:
            candidates.append(candidate)
        if rule["kind"] == "min" and candidate <= observed_value:
            candidates.append(candidate)

    if not candidates:
        candidates.append(observed_value)

    return candidates


def build_slot_constraint(domain, row_index, col_index, truth_item, selected_rules):
    constraint = {
        "row": row_index,
        "col": col_index,
        "active_rule_names": [rule["name"] for rule in selected_rules],
    }
    for rule in selected_rules:
        constraint[rule["name"]] = random.choice(get_rule_candidates(truth_item, rule))
    return constraint


def active_slot_rules(slot_constraint, slot_rules):
    active_names = set(slot_constraint.get("active_rule_names", []))
    if not active_names:
        return list(slot_rules)
    return [rule for rule in slot_rules if rule["name"] in active_names]


def item_matches_slot_constraint(item, slot_constraint, slot_rules):
    for rule in active_slot_rules(slot_constraint, slot_rules):
        value = slot_constraint[rule["name"]]
        observed = item[rule["attr"]]
        if rule["kind"] == "max" and observed > value:
            return False
        if rule["kind"] == "min" and observed < value:
            return False
    return True


def count_matching_items(domain, item_pool, slot_constraint):
    slot_rules = DOMAIN_SPECS[domain]["slot_rules"]
    return sum(1 for item in item_pool if item_matches_slot_constraint(item, slot_constraint, slot_rules))


def repeat_max(items, key):
    counts = {}
    for item in items:
        value = item[key]
        counts[value] = counts.get(value, 0) + 1
    return max(counts.values()) if counts else 0


def evaluate_aggregate_rule(rule, items, truth_solution=None, item_lookup=None):
    rule_type = rule["type"]

    if rule_type in ("sum_min", "sum_max"):
        return sum(item[rule["attr"]] for item in items)

    if rule_type == "max_cap":
        return max(item[rule["attr"]] for item in items)

    if rule_type == "repeat_max":
        return repeat_max(items, rule["attr"])

    if rule_type == "count_min":
        return sum(1 for item in items if item[rule["predicate_key"]] == rule["predicate_value"])

    if rule_type == "count_min_threshold":
        return sum(1 for item in items if item[rule["attr"]] >= rule["threshold"])

    if rule_type == "max_row_sum":
        row_totals = []
        rows = len(truth_solution)
        cols = len(truth_solution[0])
        for row_index in range(rows):
            row_total = 0
            for col_index in range(cols):
                item_id = truth_solution[row_index][col_index]
                row_total += item_lookup[item_id][rule["attr"]]
            row_totals.append(row_total)
        return max(row_totals)

    raise ValueError(f"Unsupported rule type: {rule_type}")


def build_constraint_value(rule, observed, group_size):
    rule_type = rule["type"]

    if rule_type == "sum_min":
        return random.randint(max(rule.get("floor", 0), observed - rule["slack"]), observed)

    if rule_type == "sum_max":
        upper_cap = group_size * rule["per_item_cap"]
        return random.randint(observed, min(upper_cap, observed + rule["slack"]))

    if rule_type == "max_cap":
        return random.randint(observed, rule["cap"])

    if rule_type == "repeat_max":
        return random.randint(observed, group_size)

    if rule_type in ("count_min", "count_min_threshold"):
        return random.randint(max(0, observed - rule["slack"]), observed)

    raise ValueError(f"Unsupported rule type: {rule_type}")


def make_aggregate_constraints(rule_specs, items, prefix_key, prefix_value, truth_solution=None, item_lookup=None, cols=None):
    constraints = {prefix_key: prefix_value}
    group_size = len(items)

    for rule in rule_specs:
        observed = evaluate_aggregate_rule(rule, items, truth_solution=truth_solution, item_lookup=item_lookup)
        if rule["type"] == "max_row_sum":
            upper_cap = cols * rule["per_item_cap"]
            constraints[rule["name"]] = random.randint(observed, min(upper_cap, observed + rule["slack"]))
        else:
            constraints[rule["name"]] = build_constraint_value(rule, observed, group_size)

    return constraints


def aggregate_constraint_satisfied(rule, constraint_value, items, truth_solution=None, item_lookup=None):
    observed = evaluate_aggregate_rule(rule, items, truth_solution=truth_solution, item_lookup=item_lookup)
    rule_type = rule["type"]

    if rule_type in ("sum_max", "max_cap", "repeat_max", "max_row_sum"):
        return observed <= constraint_value

    if rule_type in ("sum_min", "count_min", "count_min_threshold"):
        return observed >= constraint_value

    raise ValueError(f"Unsupported rule type: {rule_type}")
