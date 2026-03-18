from data_generation.domains import DOMAIN_SPECS
from data_generation.generation.constraints import make_aggregate_constraints


def global_items(truth_solution, item_lookup):
    return [item_lookup[item_id] for row in truth_solution for item_id in row]


def active_rules(rule_specs, constraint):
    return [rule for rule in rule_specs if rule["name"] in constraint]


def select_global_rules(spec):
    # 新逻辑下 global 尽量覆盖全部属性，直接启用全部 global rules。
    return list(spec["global_rules"])


def build_truth_constraints(domain, truth_solution, item_lookup, rows, cols):
    spec = DOMAIN_SPECS[domain]
    global_rule_specs = select_global_rules(spec)
    return make_aggregate_constraints(
        global_rule_specs,
        global_items(truth_solution, item_lookup),
        "global",
        "global",
        truth_solution=truth_solution,
        item_lookup=item_lookup,
        cols=cols,
    )
