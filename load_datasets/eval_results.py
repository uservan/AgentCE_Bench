import json

from data_generation.generation.constraints import aggregate_constraint_satisfied, item_matches_slot_constraint
from data_generation.domains import DOMAIN_SPECS


# Validate a model-generated grid against dataset constraints.
# `results` can be a grid of item ids, or a grid of full item dicts.
# In most cases you should use `validate_generated_results_from_dataset()`.
def _build_item_lookup(domain, item_pool):
    if item_pool is None:
        return None

    spec = DOMAIN_SPECS[domain]
    id_key = spec["id_key"]

    if isinstance(item_pool, dict):
        return item_pool

    return {item[id_key]: item for item in item_pool}


def _normalize_results(domain, results, item_pool=None):
    if not results or not isinstance(results, list) or not isinstance(results[0], list):
        raise ValueError("results must be a non-empty list of lists")

    row_lengths = {len(row) for row in results}
    if len(row_lengths) != 1:
        raise ValueError("results must be a rectangular grid")

    spec = DOMAIN_SPECS[domain]
    id_key = spec["id_key"]
    item_lookup = _build_item_lookup(domain, item_pool)

    normalized_grid = []
    normalized_ids = []

    for row in results:
        normalized_row = []
        normalized_id_row = []
        for cell in row:
            if isinstance(cell, dict):
                if id_key not in cell:
                    raise ValueError(f"result item dict must contain '{id_key}'")
                normalized_row.append(cell)
                normalized_id_row.append(cell[id_key])
                continue

            if item_lookup is None:
                raise ValueError("item_pool is required when results contains item ids")
            if cell not in item_lookup:
                raise ValueError(f"Unknown item id in results: {cell}")

            normalized_row.append(item_lookup[cell])
            normalized_id_row.append(cell)

        normalized_grid.append(normalized_row)
        normalized_ids.append(normalized_id_row)

    return normalized_grid, normalized_ids


def _slot_constraint_map(slot_constraints):
    if slot_constraints is None:
        return None

    if isinstance(slot_constraints, dict):
        return slot_constraints

    constraint_map = {}
    for constraint in slot_constraints:
        if "slot_constraints" in constraint:
            constraint_map[(constraint["row"], constraint["col"])] = constraint["slot_constraints"]
        else:
            constraint_map[(constraint["row"], constraint["col"])] = constraint
    return constraint_map


def _validate_shape(results):
    if not results or not results[0]:
        return False, "results must be a non-empty grid"
    return True, None


def validate_generated_results(
    domain,
    global_constraints,
    results,
    item_pool=None,
    slot_constraints=None,
    require_unique=True,
    return_details=False,
):
    # Generic validator when you already have all constraint objects in memory.
    # Returns either `bool` or `(bool, message)` depending on `return_details`.
    if domain not in DOMAIN_SPECS:
        raise ValueError(f"Unsupported domain: {domain}")

    normalized_grid, normalized_ids = _normalize_results(domain, results, item_pool=item_pool)
    shape_ok, shape_error = _validate_shape(normalized_grid)
    if not shape_ok:
        return (False, shape_error) if return_details else False

    spec = DOMAIN_SPECS[domain]
    slot_map = _slot_constraint_map(slot_constraints)

    if require_unique:
        flat_ids = [item_id for row in normalized_ids for item_id in row]
        if len(flat_ids) != len(set(flat_ids)):
            message = "results contains duplicate item ids"
            return (False, message) if return_details else False

    if slot_map is not None:
        for row_index, row in enumerate(normalized_grid):
            for col_index, item in enumerate(row):
                slot_constraint = slot_map[(row_index, col_index)]
                if not item_matches_slot_constraint(item, slot_constraint, spec["slot_rules"]):
                    message = f"slot constraint failed at ({row_index}, {col_index})"
                    return (False, message) if return_details else False

    all_items = [item for row in normalized_grid for item in row]
    item_lookup = {
        item_id: item
        for row, id_row in zip(normalized_grid, normalized_ids)
        for item, item_id in zip(row, id_row)
    }
    for rule in spec["global_rules"]:
        if rule["name"] not in global_constraints:
            continue
        if not aggregate_constraint_satisfied(
            rule,
            global_constraints[rule["name"]],
            all_items,
            truth_solution=normalized_ids,
            item_lookup=item_lookup,
        ):
            message = f"global constraint '{rule['name']}' failed"
            return (False, message) if return_details else False

    message = "results satisfy all checked constraints"
    return (True, message) if return_details else True


def validate_generated_results_from_dataset(
    dataset,
    results,
    require_unique=True,
    return_details=False,
    check_slot_constraints=False,
):
    """
    Example:
        from saved_datasets.eval_results import (
            load_dataset,
            validate_generated_results_from_dataset,
        )

        dataset = load_dataset("data/course_dataset_n1_r5_c5_cand16_valid4_seed42.json")
        ok, message = validate_generated_results_from_dataset(
            dataset,
            dataset["truth_solution"],
            require_unique=True,
            return_details=True,
            check_slot_constraints=True,
        )
    """
    # Convenience wrapper for a single dataset instance.
    # Pass the dataset dict directly, plus the model output grid.
    slot_constraints = dataset["slots"] if check_slot_constraints else None
    return validate_generated_results(
        domain=dataset["domain"],
        global_constraints=dataset["global_constraints"],
        results=results,
        item_pool=dataset["item_pool"],
        slot_constraints=slot_constraints,
        require_unique=require_unique,
        return_details=return_details,
    )


def load_dataset(path):
    # Load the first instance from a generated dataset JSON file.
    with open(path, "r", encoding="utf-8") as input_file:
        payload = json.load(input_file)

    if "instances" not in payload or not payload["instances"]:
        raise ValueError("dataset file does not contain any instances")

    return payload["instances"][0]
