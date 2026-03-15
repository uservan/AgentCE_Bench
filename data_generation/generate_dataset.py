import argparse
import json
import os
import random
from itertools import product

try:
    from . import (
        DEFAULT_CANDIDATES_PER_SLOT,
        DEFAULT_COLS,
        DEFAULT_MAX_RETRIES,
        DEFAULT_NUM_INSTANCES,
        DEFAULT_OUTPUT_DIR,
        DEFAULT_ROWS,
        DEFAULT_SLOT_CANDIDATE_RETRIES,
        DEFAULT_VALID_OPTIONS,
    )
    from .constraints import (
        aggregate_constraint_satisfied,
        item_matches_slot_constraint,
        make_aggregate_constraints,
    )
    from .domains import DOMAIN_BUILDERS, DOMAIN_SPECS, SUPPORTED_DOMAINS
    from .items import generate_item_pool, generate_truth_solution
    from .task_instruction import build_task_instruction_from_instance
    from .validation import validate_dataset
except ImportError:
    from __init__ import (
        DEFAULT_CANDIDATES_PER_SLOT,
        DEFAULT_COLS,
        DEFAULT_MAX_RETRIES,
        DEFAULT_NUM_INSTANCES,
        DEFAULT_OUTPUT_DIR,
        DEFAULT_ROWS,
        DEFAULT_SLOT_CANDIDATE_RETRIES,
        DEFAULT_VALID_OPTIONS,
    )
    from constraints import (
        aggregate_constraint_satisfied,
        item_matches_slot_constraint,
        make_aggregate_constraints,
    )
    from domains import DOMAIN_BUILDERS, DOMAIN_SPECS, SUPPORTED_DOMAINS
    from items import generate_item_pool, generate_truth_solution
    from task_instruction import build_task_instruction_from_instance
    from validation import validate_dataset


def row_items(truth_solution, item_lookup, row_index):
    return [item_lookup[item_id] for item_id in truth_solution[row_index]]


def col_items(truth_solution, item_lookup, col_index):
    return [item_lookup[truth_solution[row_index][col_index]] for row_index in range(len(truth_solution))]


def global_items(truth_solution, item_lookup):
    return [item_lookup[item_id] for row in truth_solution for item_id in row]


def rule_attr_key(rule):
    if "attr" in rule:
        return rule["attr"]
    if "predicate_key" in rule:
        return rule["predicate_key"]
    return rule["name"]


def active_rules(rule_specs, constraint):
    return [rule for rule in rule_specs if rule["name"] in constraint]


def ordered_attr_keys(rule_specs):
    keys = []
    seen = set()
    for rule in rule_specs:
        key = rule_attr_key(rule)
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def pick_rule_for_attr(rule_specs, attr_key):
    for rule in rule_specs:
        if rule_attr_key(rule) == attr_key:
            return rule
    return None


def select_constraint_rule_sets(spec):
    row_rules = spec["row_rules"]
    col_rules = spec["col_rules"]
    global_rules = spec["global_rules"]

    global_attrs = ordered_attr_keys(global_rules)[: min(4, len(ordered_attr_keys(global_rules)))]
    row_attrs = ordered_attr_keys(row_rules)
    col_attrs = ordered_attr_keys(col_rules)

    row_shared = [attr for attr in global_attrs if attr in row_attrs][:2]
    col_shared = [attr for attr in global_attrs if attr in col_attrs][:2]

    row_extra = next((attr for attr in row_attrs if attr not in global_attrs), None)
    col_extra = next(
        (attr for attr in col_attrs if attr not in global_attrs and attr != row_extra),
        None,
    )
    if col_extra is None:
        col_extra = next((attr for attr in col_attrs if attr not in global_attrs), None)

    selected_row_attrs = []
    for attr in row_shared:
        if attr not in selected_row_attrs:
            selected_row_attrs.append(attr)
    if row_extra is not None and row_extra not in selected_row_attrs:
        selected_row_attrs.append(row_extra)
    for attr in row_attrs:
        if len(selected_row_attrs) >= min(3, len(row_attrs)):
            break
        if attr not in selected_row_attrs:
            selected_row_attrs.append(attr)

    selected_col_attrs = []
    for attr in col_shared:
        if attr not in selected_col_attrs:
            selected_col_attrs.append(attr)
    if col_extra is not None and col_extra not in selected_col_attrs:
        selected_col_attrs.append(col_extra)
    for attr in col_attrs:
        if len(selected_col_attrs) >= min(3, len(col_attrs)):
            break
        if attr not in selected_col_attrs:
            selected_col_attrs.append(attr)

    selected_row_rules = [pick_rule_for_attr(row_rules, attr) for attr in selected_row_attrs]
    selected_col_rules = [pick_rule_for_attr(col_rules, attr) for attr in selected_col_attrs]
    selected_global_rules = [pick_rule_for_attr(global_rules, attr) for attr in global_attrs]

    return (
        [rule for rule in selected_row_rules if rule is not None],
        [rule for rule in selected_col_rules if rule is not None],
        [rule for rule in selected_global_rules if rule is not None],
    )


def build_truth_constraints(domain, truth_solution, item_lookup, rows, cols):
    spec = DOMAIN_SPECS[domain]
    row_rule_specs, col_rule_specs, global_rule_specs = select_constraint_rule_sets(spec)
    row_constraints = []
    col_constraints = []

    for row_index in range(rows):
        row_constraints.append(
            make_aggregate_constraints(
                row_rule_specs,
                row_items(truth_solution, item_lookup, row_index),
                "row",
                row_index,
                cols=cols,
            )
        )

    for col_index in range(cols):
        col_constraints.append(
            make_aggregate_constraints(
                col_rule_specs,
                col_items(truth_solution, item_lookup, col_index),
                "col",
                col_index,
                cols=cols,
            )
        )

    global_constraints = make_aggregate_constraints(
        global_rule_specs,
        global_items(truth_solution, item_lookup),
        "global",
        "global",
        truth_solution=truth_solution,
        item_lookup=item_lookup,
        cols=cols,
    )

    return row_constraints, col_constraints, global_constraints


def build_slot_constraint(domain, row_index, col_index, candidate_ids, item_pool):
    spec = DOMAIN_SPECS[domain]
    constraint = {"row": row_index, "col": col_index}

    for rule in spec["slot_rules"]:
        values = [item_pool[candidate_id][rule["attr"]] for candidate_id in candidate_ids]
        if rule["kind"] == "max":
            constraint[rule["name"]] = max(values)
        else:
            constraint[rule["name"]] = min(values)

    return constraint


def generate_target_valid_counts(rows, cols, valid_options):
    return [valid_options for _ in range(rows * cols)]


def candidate_status(
    domain,
    truth_solution,
    item_lookup,
    row_constraints,
    col_constraints,
    global_constraints,
    row_index,
    col_index,
    candidate_id,
):
    spec = DOMAIN_SPECS[domain]
    trial_solution = [row[:] for row in truth_solution]
    trial_solution[row_index][col_index] = candidate_id

    row_group = row_items(trial_solution, item_lookup, row_index)
    row_ok = all(
        aggregate_constraint_satisfied(rule, row_constraints[row_index][rule["name"]], row_group)
        for rule in active_rules(spec["row_rules"], row_constraints[row_index])
    )

    col_group = col_items(trial_solution, item_lookup, col_index)
    col_ok = all(
        aggregate_constraint_satisfied(rule, col_constraints[col_index][rule["name"]], col_group)
        for rule in active_rules(spec["col_rules"], col_constraints[col_index])
    )

    global_group = global_items(trial_solution, item_lookup)
    global_ok = all(
        aggregate_constraint_satisfied(
            rule,
            global_constraints[rule["name"]],
            global_group,
            truth_solution=trial_solution,
            item_lookup=item_lookup,
        )
        for rule in active_rules(spec["global_rules"], global_constraints)
    )

    return row_ok, col_ok, global_ok


def build_slot_entry(
    domain,
    truth_solution,
    item_pool,
    row_constraints,
    col_constraints,
    global_constraints,
    row_index,
    col_index,
    target_valid_count,
    candidates_per_slot,
    next_index,
):
    spec = DOMAIN_SPECS[domain]
    builder = DOMAIN_BUILDERS[domain]
    id_key = spec["id_key"]
    truth_id = truth_solution[row_index][col_index]
    item_lookup = item_pool

    valid_ids = [truth_id]
    distractor_ids = []

    for _ in range(DEFAULT_SLOT_CANDIDATE_RETRIES):
        if len(valid_ids) >= target_valid_count and len(valid_ids) + len(distractor_ids) >= candidates_per_slot:
            break

        candidate = builder(next_index)
        next_index += 1
        candidate_id = candidate[id_key]
        if candidate_id in item_pool:
            continue

        trial_lookup = dict(item_lookup)
        trial_lookup[candidate_id] = candidate
        row_ok, col_ok, global_ok = candidate_status(
            domain,
            truth_solution,
            trial_lookup,
            row_constraints,
            col_constraints,
            global_constraints,
            row_index,
            col_index,
            candidate_id,
        )

        if row_ok and col_ok and global_ok:
            if len(valid_ids) < target_valid_count:
                item_pool[candidate_id] = candidate
                valid_ids.append(candidate_id)
        elif (not row_ok or not col_ok) and len(valid_ids) + len(distractor_ids) < candidates_per_slot:
            item_pool[candidate_id] = candidate
            distractor_ids.append(candidate_id)

    if len(valid_ids) < target_valid_count or len(valid_ids) + len(distractor_ids) < candidates_per_slot:
        return None, next_index

    candidate_ids = valid_ids + distractor_ids[: candidates_per_slot - len(valid_ids)]
    random.shuffle(candidate_ids)
    slot_constraints = build_slot_constraint(domain, row_index, col_index, candidate_ids, item_pool)

    if not all(
        item_matches_slot_constraint(item_pool[candidate_id], slot_constraints, spec["slot_rules"])
        for candidate_id in candidate_ids
    ):
        return None, next_index

    return {
        "row": row_index,
        "col": col_index,
        "truth_id": truth_id,
        "slot_constraints": slot_constraints,
        "candidate_ids": candidate_ids,
        "valid_candidate_ids": valid_ids[:],
    }, next_index


def build_instance(
    domain,
    rows=DEFAULT_ROWS,
    cols=DEFAULT_COLS,
    candidates_per_slot=DEFAULT_CANDIDATES_PER_SLOT,
    valid_options=DEFAULT_VALID_OPTIONS,
):
    total_cells = rows * cols
    base_pool = generate_item_pool(
        domain,
        total_cells=total_cells,
        min_valid_options=valid_options,
        max_valid_options=valid_options,
    )
    truth_solution, base_lookup = generate_truth_solution(domain, base_pool, rows=rows, cols=cols)
    truth_ids = {item_id for row in truth_solution for item_id in row}
    item_pool = {item_id: base_lookup[item_id] for item_id in truth_ids}

    row_constraints, col_constraints, global_constraints = build_truth_constraints(
        domain,
        truth_solution,
        item_pool,
        rows,
        cols,
    )

    target_valid_counts = generate_target_valid_counts(
        rows,
        cols,
        valid_options,
    )

    slots = []
    next_index = len(base_pool)
    for slot_index in range(total_cells):
        row_index = slot_index // cols
        col_index = slot_index % cols
        slot_entry, next_index = build_slot_entry(
            domain,
            truth_solution,
            item_pool,
            row_constraints,
            col_constraints,
            global_constraints,
            row_index,
            col_index,
            target_valid_counts[slot_index],
            candidates_per_slot,
            next_index,
        )
        if slot_entry is None:
            return None
        slots.append(slot_entry)

    instance = {
        "domain": domain,
        "meta": {"rows": rows, "cols": cols},
        "global_constraints": global_constraints,
        "item_pool": item_pool,
        "truth_solution": truth_solution,
        "row_constraints": row_constraints,
        "col_constraints": col_constraints,
        "slots": slots,
    }
    instance["task_instruction"] = build_task_instruction_from_instance(instance)
    return instance


def build_output_filename(
    domain,
    num_instances,
    rows,
    cols,
    candidates_per_slot,
    valid_options,
    seed=None,
):
    row_values = normalize_dimension_values(rows)
    col_values = normalize_dimension_values(cols)
    row_tag = "-".join(str(value) for value in row_values)
    col_tag = "-".join(str(value) for value in col_values)
    filename = (
        f"{domain}_dataset_"
        f"n{num_instances}_"
        f"r{row_tag}_"
        f"c{col_tag}_"
        f"cand{candidates_per_slot}_"
        f"valid{valid_options}"
    )
    if seed is not None:
        filename += f"_seed{seed}"
    return f"{filename}.json"



def normalize_dimension_values(values):
    if isinstance(values, int):
        return [values]
    if not values:
        raise ValueError("dimension values must not be empty")
    return [int(value) for value in values]


def summarize_dataset(dataset):
    candidate_counts = [len(slot["candidate_ids"]) for slot in dataset["slots"]]
    valid_counts = [len(slot.get("valid_candidate_ids", [])) for slot in dataset["slots"]]
    return {
        "instance_id": dataset.get("instance_id"),
        "avg_candidates": round(sum(candidate_counts) / len(candidate_counts), 2),
        "avg_valid_options": round(sum(valid_counts) / len(valid_counts), 2),
        "item_pool_size": len(dataset["item_pool"]),
    }


def validate_payload(payload, candidates_per_slot=DEFAULT_CANDIDATES_PER_SLOT, valid_options=DEFAULT_VALID_OPTIONS):
    summaries = []
    for dataset in payload["instances"]:
        if not validate_dataset(
            dataset,
            candidates_per_slot=candidates_per_slot,
            valid_options=valid_options,
        ):
            return False, []
        summaries.append(summarize_dataset(dataset))
    return True, summaries


def validate_dataset_file(path, candidates_per_slot=DEFAULT_CANDIDATES_PER_SLOT, valid_options=DEFAULT_VALID_OPTIONS):
    with open(path, "r", encoding="utf-8") as input_file:
        payload = json.load(input_file)
    return validate_payload(
        payload,
        candidates_per_slot=candidates_per_slot,
        valid_options=valid_options,
    )


def print_validation_report(domain, summaries):
    headers = [
        "domain",
        "instance_id",
        "avg_candidates_each_slot",
        "avg_valid_options_each_slot",
        "item_pool_size",
    ]
    rows = []
    for summary in summaries:
        rows.append(
            [
                domain,
                summary["instance_id"],
                summary["avg_candidates"],
                summary["avg_valid_options"],
                summary["item_pool_size"],
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(str(value)))

    def format_row(values):
        return "| " + " | ".join(str(value).ljust(widths[index]) for index, value in enumerate(values)) + " |"

    separator = "+-" + "-+-".join("-" * width for width in widths) + "-+"
    print(separator)
    print(format_row(headers))
    print(separator)
    for row in rows:
        print(format_row(row))
    print(separator)

def generate_dataset(
    domain="course",
    num_instances=DEFAULT_NUM_INSTANCES,
    rows=DEFAULT_ROWS,
    cols=DEFAULT_COLS,
    output_dir=DEFAULT_OUTPUT_DIR,
    candidates_per_slot=DEFAULT_CANDIDATES_PER_SLOT,
    valid_options=DEFAULT_VALID_OPTIONS,
    seed=None,
):
    if domain not in SUPPORTED_DOMAINS:
        raise ValueError(f"Unsupported domain: {domain}")
    if candidates_per_slot < valid_options:
        raise ValueError("candidates_per_slot must be greater than or equal to valid_options")
    row_values = normalize_dimension_values(rows)
    col_values = normalize_dimension_values(cols)
    if seed is not None:
        random.seed(seed)

    instances = []
    for row_count, col_count in product(row_values, col_values):
        for instance_index in range(num_instances):
            dataset = None
            for _ in range(DEFAULT_MAX_RETRIES):
                candidate = build_instance(
                    domain,
                    rows=row_count,
                    cols=col_count,
                    candidates_per_slot=candidates_per_slot,
                    valid_options=valid_options,
                )
                if candidate is None:
                    continue
                if validate_dataset(
                    candidate,
                    candidates_per_slot=candidates_per_slot,
                    valid_options=valid_options,
                ):
                    dataset = candidate
                    break
            if dataset is None:
                raise RuntimeError(
                    f"Failed to build a valid dataset for domain '{domain}' with rows={row_count}, cols={col_count}"
                )

            dataset["instance_id"] = f"{domain}_r{row_count}_c{col_count}_{instance_index:03d}"
            instances.append(dataset)

    os.makedirs(output_dir, exist_ok=True)
    output_filename = build_output_filename(
        domain=domain,
        num_instances=len(instances),
        rows=row_values,
        cols=col_values,
        candidates_per_slot=candidates_per_slot,
        valid_options=valid_options,
        seed=seed,
    )
    output_path = os.path.join(output_dir, output_filename)
    payload = {
        "domain": domain,
        "num_instances": len(instances),
        "instances": instances,
    }

    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, indent=2)

    is_valid, summaries = validate_payload(
        payload,
        candidates_per_slot=candidates_per_slot,
        valid_options=valid_options,
    )
    if not is_valid:
        raise RuntimeError(f"Generated dataset failed validation: {output_path}")

    return payload


def generate_all_datasets(
    domains=SUPPORTED_DOMAINS,
    num_instances=DEFAULT_NUM_INSTANCES,
    rows=DEFAULT_ROWS,
    cols=DEFAULT_COLS,
    output_dir=DEFAULT_OUTPUT_DIR,
    candidates_per_slot=DEFAULT_CANDIDATES_PER_SLOT,
    valid_options=DEFAULT_VALID_OPTIONS,
    seed=None,
):
    results = {}
    for domain in domains:
        results[domain] = generate_dataset(
            domain=domain,
            num_instances=num_instances,
            rows=rows,
            cols=cols,
            output_dir=output_dir,
            candidates_per_slot=candidates_per_slot,
            valid_options=valid_options,
            seed=seed,
        )
    return results


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Generate or validate planning datasets.")
    parser.add_argument("--domain", choices=SUPPORTED_DOMAINS, help="Generate a single domain dataset.")
    parser.add_argument("--all-domains", action="store_true", help="Generate datasets for all supported domains.")
    parser.add_argument("--num-instances", type=int, default=DEFAULT_NUM_INSTANCES, help="Number of instances per domain.")
    parser.add_argument("--rows", type=int, nargs="+", default=[DEFAULT_ROWS], help="One or more grid row counts.")
    parser.add_argument("--cols", type=int, nargs="+", default=[DEFAULT_COLS], help="One or more grid column counts.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for generated dataset files.")
    parser.add_argument(
        "--candidates-per-slot",
        type=int,
        default=DEFAULT_CANDIDATES_PER_SLOT,
        help="Number of visible candidate ids stored for each slot.",
    )
    parser.add_argument(
        "--valid-options",
        type=int,
        default=DEFAULT_VALID_OPTIONS,
        help="Exact number of row/col-valid candidates required per slot.",
    )
    parser.add_argument("--seed", type=int, help="Optional random seed for reproducible generation.")
    parser.add_argument("--validate-file", help="Validate an existing dataset JSON file instead of generating.")
    return parser



def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    row_values = normalize_dimension_values(args.rows)
    col_values = normalize_dimension_values(args.cols)

    if args.candidates_per_slot < args.valid_options:
        raise SystemExit("--candidates-per-slot must be greater than or equal to --valid-options")

    if args.seed is not None:
        random.seed(args.seed)

    if args.validate_file:
        is_valid, summaries = validate_dataset_file(
            args.validate_file,
            candidates_per_slot=args.candidates_per_slot,
            valid_options=args.valid_options,
        )
        if not is_valid:
            raise SystemExit(f"Validation failed: {args.validate_file}")
        print(f"Validation passed: {args.validate_file}")
        print_validation_report("file", summaries)
        return

    if args.all_domains:
        payloads = generate_all_datasets(
            num_instances=args.num_instances,
            rows=row_values,
            cols=col_values,
            output_dir=args.output_dir,
            candidates_per_slot=args.candidates_per_slot,
            valid_options=args.valid_options,
            seed=args.seed,
        )
        for domain, payload in payloads.items():
            _, summaries = validate_payload(
                payload,
                candidates_per_slot=args.candidates_per_slot,
                valid_options=args.valid_options,
            )
            print_validation_report(domain, summaries)
        return

    domain = args.domain or "course"
    payload = generate_dataset(
        domain=domain,
        num_instances=args.num_instances,
        rows=row_values,
        cols=col_values,
        output_dir=args.output_dir,
        candidates_per_slot=args.candidates_per_slot,
        valid_options=args.valid_options,
        seed=args.seed,
    )
    _, summaries = validate_payload(
        payload,
        candidates_per_slot=args.candidates_per_slot,
        valid_options=args.valid_options,
    )
    print_validation_report(domain, summaries)


if __name__ == "__main__":
    main()
