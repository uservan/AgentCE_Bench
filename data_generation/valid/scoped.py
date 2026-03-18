from data_generation.valid.messages import format_rule_message
from data_generation.valid.rules import rule_satisfied
from data_generation.valid.utils import active_rules, ids_to_items


def validate_scope_constraints(
    *,
    solution,
    domain,
    index,
    ids,
    positions,
    constraint,
    rule_specs,
    item_pool,
    slot_map,
    truth_solution=None,
    unknown_id_scope,
    scope_text,
):
    for row_index, col_index, item_id in positions:
        if item_id is None:
            continue
        slot_entry = slot_map.get((row_index, col_index))
        if slot_entry is None:
            if truth_solution is None:
                allowed_ids = [item_id]
            else:
                allowed_ids = [truth_solution[row_index][col_index]]
        else:
            allowed_ids = slot_entry.get("candidate_ids")
            if allowed_ids is None:
                allowed_ids = [slot_entry["truth_id"]]
        if item_id not in allowed_ids:
            return False, (
                f"slot ({row_index}, {col_index}) contains id '{item_id}', "
                "which is not one of the candidate options for that slot"
            )

    try:
        scope_items = ids_to_items(ids, item_pool)
    except KeyError as exc:
        return False, f"unknown item id '{exc.args[0]}' appears in {unknown_id_scope.format(index=index)}"

    is_complete = all(item_id is not None for item_id in ids)
    for rule in active_rules(rule_specs, constraint):
        if not rule_satisfied(
            rule,
            constraint[rule["name"]],
            scope_items,
            is_complete,
            solution,
            item_pool,
        ):
            return False, format_rule_message(domain, rule, constraint[rule["name"]], scope_text.format(index=index))
    return True, None
