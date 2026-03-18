import json

from data_generation.validation import validate_dataset
from utils.console_display import ConsoleDisplay


def normalize_dimension_values(values):
    if isinstance(values, int):
        return [values]
    if not values:
        raise ValueError("dimension values must not be empty")
    return [int(value) for value in values]


def build_output_filename(
    domain,
    rows,
    cols,
    hidden_slots,
    candidates_per_slot,
    branch_budget,
    seed=None,
):
    row_values = normalize_dimension_values(rows)
    col_values = normalize_dimension_values(cols)
    hidden_values = normalize_dimension_values(hidden_slots)
    budget_values = normalize_dimension_values(branch_budget)
    row_tag = "-".join(str(value) for value in row_values)
    col_tag = "-".join(str(value) for value in col_values)
    hidden_tag = "-".join(str(value) for value in hidden_values)
    budget_tag = "-".join(str(value) for value in budget_values)
    filename = (
        f"{domain}_dataset_"
        f"r{row_tag}_"
        f"c{col_tag}_"
        f"h{hidden_tag}_"
        f"cand{candidates_per_slot}_"
        f"budget{budget_tag}"
    )
    if seed is not None:
        filename += f"_seed{seed}"
    return f"{filename}.json"


def summarize_dataset(dataset):
    hidden_slots = list(dataset["slots"])
    candidate_counts = [len(slot.get("candidate_ids", [])) for slot in hidden_slots] or [0]
    branch_slot_count = sum(1 for slot in hidden_slots if slot.get("is_branch_slot"))
    total_decoys = sum(len(slot.get("decoy_ids", [])) for slot in hidden_slots)
    return {
        "instance_id": dataset.get("instance_id"),
        "avg_candidates": round(sum(candidate_counts) / len(candidate_counts), 2),
        "hidden_slots": len(hidden_slots),
        "branch_budget": dataset["meta"].get("branch_budget", total_decoys),
        "branch_slots": branch_slot_count,
        "total_decoys": total_decoys,
        "item_pool_size": len(dataset["item_pool"]),
    }


def validate_payload(payload):
    summaries = []
    for dataset in payload["instances"]:
        if not validate_dataset(dataset):
            return False, []
        summaries.append(summarize_dataset(dataset))
    return True, summaries


def validate_dataset_file(path):
    with open(path, "r", encoding="utf-8") as input_file:
        payload = json.load(input_file)
    return validate_payload(payload)


def print_validation_report(domain, summaries):
    ConsoleDisplay.print_dataset_summary_report(domain, summaries)
