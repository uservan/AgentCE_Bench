def build_constraint_maps(dataset):
    slot_map = {(slot["row"], slot["col"]): slot for slot in dataset["slots"]}
    row_map = {constraint["row"]: constraint for constraint in dataset.get("row_constraints", [])}
    col_map = {constraint["col"]: constraint for constraint in dataset.get("col_constraints", [])}
    return slot_map, row_map, col_map


def build_slot_map(slots):
    return {(slot["row"], slot["col"]): slot for slot in slots}


def active_rules(rule_specs, constraint):
    return [rule for rule in rule_specs if rule["name"] in constraint]


def ids_to_items(item_ids, item_pool):
    items = []
    for item_id in item_ids:
        if item_id is None:
            continue
        if item_id not in item_pool:
            raise KeyError(item_id)
        items.append(item_pool[item_id])
    return items
