import argparse
import json
import os
import random
import sys
from itertools import product
from typing import Callable

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data_generation.domains import SUPPORTED_DOMAINS
from data_generation.generation.constants import (
    DEFAULT_BRANCH_BUDGETS,
    DEFAULT_CANDIDATE_RESAMPLE_RETRIES,
    DEFAULT_CANDIDATES_PER_SLOT,
    DEFAULT_COLS,
    DEFAULT_HIDDEN_SLOTS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_OPEN_VALID_PREFERENCE_TRIES,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_ROWS,
)
from data_generation.generation.dataset_io import (
    build_output_filename,
    normalize_dimension_values,
    print_validation_report,
    validate_dataset_file,
    validate_payload,
)
from data_generation.generation.instance_builder import (
    build_instance_from_scaffold,
    build_instance_scaffold,
    compute_effective_candidates_per_slot,
)
from data_generation.validation import validate_dataset
from utils.console_display import ConsoleDisplay


def _print_generation_failure(
    domain: str,
    rows: int,
    cols: int,
    hidden_slots: int,
    branch_budget: int,
    effective_candidates: int,
    scaffold_retries: int,
    candidate_retries: int,
    reason: str,
) -> None:
    """在终端展示生成失败时的详细条件和原因。"""
    ConsoleDisplay.console.print()
    ConsoleDisplay.console.print(
        "[bold red]生成失败[/bold red] - 无法为该组合生成有效实例",
        style="red",
    )
    ConsoleDisplay.print_kv_panel(
        title="[bold red]当前生成条件[/bold red]",
        items=[
            ("domain", domain),
            ("rows", rows),
            ("cols", cols),
            ("hidden_slots", hidden_slots),
            ("branch_budget", branch_budget),
            ("实际 candidates_per_slot", effective_candidates),
            ("scaffold 重试次数", scaffold_retries),
            ("candidate 重采样次数", candidate_retries),
        ],
        border_style="red",
    )
    ConsoleDisplay.console.print(f"[bold red]失败原因:[/bold red] {reason}")
    ConsoleDisplay.console.print("[yellow]建议: 可尝试重新运行，或调整参数。[/yellow]")
    ConsoleDisplay.console.print()


def generate_dataset(
    domain="course",
    rows=DEFAULT_ROWS,
    cols=DEFAULT_COLS,
    output_dir=DEFAULT_OUTPUT_DIR,
    candidates_per_slot=DEFAULT_CANDIDATES_PER_SLOT,
    branch_budget=DEFAULT_BRANCH_BUDGETS,
    hidden_slots=DEFAULT_HIDDEN_SLOTS,
    max_retries=DEFAULT_MAX_RETRIES,
    candidate_resample_retries=DEFAULT_CANDIDATE_RESAMPLE_RETRIES,
    open_valid_preference_tries=DEFAULT_OPEN_VALID_PREFERENCE_TRIES,
    seed=None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
):
    if domain not in SUPPORTED_DOMAINS:
        raise ValueError(f"Unsupported domain: {domain}")

    row_count = int(rows)
    col_count = int(cols)
    hidden_slot_values = normalize_dimension_values(hidden_slots)
    branch_budget_values = normalize_dimension_values(branch_budget)

    if row_count <= 0 or col_count <= 0:
        raise ValueError("rows and cols must be positive integers")
    if any(value < 0 for value in hidden_slot_values):
        raise ValueError("hidden_slots must be non-negative")
    if any(value < 0 for value in branch_budget_values):
        raise ValueError("branch_budget must be non-negative")
    if len(open_valid_preference_tries) != 3:
        raise ValueError("open_valid_preference_tries must contain exactly three integers")
    if any(value < 0 for value in open_valid_preference_tries):
        raise ValueError("open_valid_preference_tries must be non-negative")
    if list(open_valid_preference_tries) != sorted(open_valid_preference_tries):
        raise ValueError("open_valid_preference_tries must be non-decreasing")

    if seed is not None:
        random.seed(seed)

    instances = []
    total_combinations = len(hidden_slot_values) * len(branch_budget_values)
    completed_combinations = 0
    for hidden_slot_count, branch_budget_value in product(hidden_slot_values, branch_budget_values):
        if hidden_slot_count > row_count * col_count:
            raise ValueError("hidden_slots cannot exceed rows * cols")

        effective_candidates = compute_effective_candidates_per_slot(
            hidden_slot_count,
            candidates_per_slot,
            branch_budget_value,
        )

        dataset = None
        last_failure_reason = None
        for scaffold_try in range(1, max_retries + 1):
            if progress_callback is not None:
                progress_callback({
                    "stage": "scaffold",
                    "domain": domain,
                    "rows": row_count,
                    "cols": col_count,
                    "hidden_slots": hidden_slot_count,
                    "branch_budget": branch_budget_value,
                    "scaffold_try": scaffold_try,
                    "scaffold_total": max_retries,
                    "completed": completed_combinations,
                    "total": total_combinations,
                })
            scaffold = build_instance_scaffold(
                domain,
                rows=row_count,
                cols=col_count,
                candidates_per_slot=effective_candidates,
                branch_budget=branch_budget_value,
                hidden_slots=hidden_slot_count,
            )
            if scaffold is None:
                last_failure_reason = (
                    "scaffold 构建失败（truth/global/hidden_positions 无法满足当前分支预算）"
                )
                continue
            for candidate_try in range(1, candidate_resample_retries + 1):
                if progress_callback is not None:
                    progress_callback({
                        "stage": "candidates",
                        "domain": domain,
                        "rows": row_count,
                        "cols": col_count,
                        "hidden_slots": hidden_slot_count,
                        "branch_budget": branch_budget_value,
                        "scaffold_try": scaffold_try,
                        "scaffold_total": max_retries,
                        "candidate_try": candidate_try,
                        "candidate_total": candidate_resample_retries,
                        "completed": completed_combinations,
                        "total": total_combinations,
                    })
                candidate = build_instance_from_scaffold(
                    scaffold,
                    open_valid_preference_tries=list(open_valid_preference_tries),
                )
                if candidate is None:
                    last_failure_reason = (
                        "candidate_ids 重采样失败（无法为 hidden slots 构造满足多阶保证的 decoy/filter）"
                    )
                    continue
                if validate_dataset(candidate):
                    dataset = candidate
                    break
                last_failure_reason = (
                    "生成的实例未通过 branch-budget 结构校验"
                )
            if dataset is not None:
                break

        completed_combinations += 1
        if dataset is None:
            if progress_callback is not None:
                progress_callback({
                    "stage": "failed",
                    "domain": domain,
                    "rows": row_count,
                    "cols": col_count,
                    "hidden_slots": hidden_slot_count,
                    "branch_budget": branch_budget_value,
                    "completed": completed_combinations,
                    "total": total_combinations,
                })
            _print_generation_failure(
                domain=domain,
                rows=row_count,
                cols=col_count,
                hidden_slots=hidden_slot_count,
                branch_budget=branch_budget_value,
                effective_candidates=effective_candidates,
                scaffold_retries=max_retries,
                candidate_retries=candidate_resample_retries,
                reason=last_failure_reason or "未知原因",
            )
            raise RuntimeError(
                "Failed to build a valid dataset for "
                f"domain='{domain}', rows={row_count}, cols={col_count}, "
                f"hidden_slots={hidden_slot_count}, branch_budget={branch_budget_value}. "
                f"Reason: {last_failure_reason or '未知原因'}. 可尝试重新运行。"
            )

        dataset["instance_id"] = (
            f"{domain}_r{row_count}_c{col_count}_"
            f"h{hidden_slot_count}_b{branch_budget_value}"
        )
        instances.append(dataset)
        if progress_callback is not None:
            progress_callback({
                "stage": "completed",
                "domain": domain,
                "instance_id": dataset["instance_id"],
                "rows": row_count,
                "cols": col_count,
                "hidden_slots": hidden_slot_count,
                "branch_budget": branch_budget_value,
                "completed": completed_combinations,
                "total": total_combinations,
            })

    os.makedirs(output_dir, exist_ok=True)
    output_filename = build_output_filename(
        domain=domain,
        rows=row_count,
        cols=col_count,
        hidden_slots=hidden_slot_values,
        candidates_per_slot=candidates_per_slot,
        branch_budget=branch_budget_values,
        seed=seed,
    )
    output_path = os.path.join(output_dir, output_filename)
    payload = {
        "domain": domain,
        "num_instances": len(instances),
        "rows": row_count,
        "cols": col_count,
        "hidden_slots": hidden_slot_values,
        "branch_budget": branch_budget_values,
        "candidates_per_slot": candidates_per_slot,
        "instances": instances,
    }

    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, indent=2)

    is_valid, _ = validate_payload(payload)
    if not is_valid:
        raise RuntimeError(f"Generated dataset failed validation: {output_path}")

    return payload


def generate_all_datasets(
    domains=SUPPORTED_DOMAINS,
    rows=DEFAULT_ROWS,
    cols=DEFAULT_COLS,
    output_dir=DEFAULT_OUTPUT_DIR,
    candidates_per_slot=DEFAULT_CANDIDATES_PER_SLOT,
    branch_budget=DEFAULT_BRANCH_BUDGETS,
    hidden_slots=DEFAULT_HIDDEN_SLOTS,
    max_retries=DEFAULT_MAX_RETRIES,
    candidate_resample_retries=DEFAULT_CANDIDATE_RESAMPLE_RETRIES,
    open_valid_preference_tries=DEFAULT_OPEN_VALID_PREFERENCE_TRIES,
    seed=None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
):
    results = {}
    for domain in domains:
        results[domain] = generate_dataset(
            domain=domain,
            rows=rows,
            cols=cols,
            output_dir=output_dir,
            candidates_per_slot=candidates_per_slot,
            branch_budget=branch_budget,
            hidden_slots=hidden_slots,
            max_retries=max_retries,
            candidate_resample_retries=candidate_resample_retries,
            open_valid_preference_tries=open_valid_preference_tries,
            seed=seed,
            progress_callback=progress_callback,
        )
    return results


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Generate or validate planning datasets.")
    parser.add_argument("--domain", choices=SUPPORTED_DOMAINS, help="Generate a single domain dataset.")
    parser.add_argument("--all-domains", action="store_true", help="Generate datasets for all supported domains.")
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS, help="Grid row count.")
    parser.add_argument("--cols", type=int, default=DEFAULT_COLS, help="Grid column count.")
    parser.add_argument(
        "--hidden-slots",
        type=int,
        nargs="+",
        default=DEFAULT_HIDDEN_SLOTS,
        help="One or more counts of slots to hide for each generated size.",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for generated dataset files.")
    parser.add_argument(
        "--candidates-per-slot",
        type=int,
        default=DEFAULT_CANDIDATES_PER_SLOT,
        help="Number of stored candidate ids for each hidden slot.",
    )
    parser.add_argument(
        "--branch-budget",
        type=int,
        nargs="+",
        default=DEFAULT_BRANCH_BUDGETS,
        help="One or more branch-budget values used to build multi-order decoy branches.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Maximum scaffold retry attempts per hidden_slots x branch_budget combination.",
    )
    parser.add_argument(
        "--candidate-resample-retries",
        type=int,
        default=DEFAULT_CANDIDATE_RESAMPLE_RETRIES,
        help="Maximum candidate/decoy resampling attempts for each scaffold.",
    )
    parser.add_argument(
        "--open-valid-preference-tries",
        type=int,
        nargs=3,
        default=DEFAULT_OPEN_VALID_PREFERENCE_TRIES,
        metavar=("TIER1", "TIER2", "TIER3"),
        help=(
            "Three staged attempt thresholds for open-future decoy preferences: "
            "tier1=all history truth/decoy combos, tier2=prefix-truth suffix-decoy combos, "
            "tier3=all-history truth only. Defaults to 30 50 70."
        ),
    )
    parser.add_argument("--seed", type=int, help="Optional random seed for reproducible generation.")
    parser.add_argument("--validate-file", help="Validate an existing dataset JSON file instead of generating.")
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    hidden_slot_values = normalize_dimension_values(args.hidden_slots)
    branch_budget_values = normalize_dimension_values(args.branch_budget)

    if args.seed is not None:
        random.seed(args.seed)

    if args.validate_file:
        is_valid, summaries = validate_dataset_file(args.validate_file)
        if not is_valid:
            raise SystemExit(f"Validation failed: {args.validate_file}")
        ConsoleDisplay.print_kv_panel(
            title="[bold green]File Validation[/bold green]",
            items=[
                ("File", args.validate_file),
                ("Status", "[green]PASS[/green]"),
            ],
            border_style="green",
        )
        print_validation_report("file", summaries)
        return

    if args.all_domains:
        total_runs = len(SUPPORTED_DOMAINS) * len(hidden_slot_values) * len(branch_budget_values)
        with ConsoleDisplay.create_progress() as progress:
            task_id = progress.add_task("Generating datasets", total=total_runs)

            def on_progress(event: dict[str, object]) -> None:
                description = (
                    "Generating "
                    f"{event.get('domain', '-')}"
                    f" | size={event.get('rows', '-') }x{event.get('cols', '-')}"
                    f" | hidden={event.get('hidden_slots', '-')}"
                    f" | budget={event.get('branch_budget', '-')}"
                )
                stage = event.get("stage")
                if stage == "scaffold":
                    description += (
                        f" | scaffold {event.get('scaffold_try', '-')}/{event.get('scaffold_total', '-')}"
                    )
                elif stage == "candidates":
                    description += (
                        f" | scaffold {event.get('scaffold_try', '-')}/{event.get('scaffold_total', '-')}"
                        f" | candidates {event.get('candidate_try', '-')}/{event.get('candidate_total', '-')}"
                    )
                elif stage == "completed":
                    progress.update(task_id, advance=1, description=description)
                    return
                elif stage == "failed":
                    progress.update(task_id, advance=1, description=description)
                    return
                progress.update(task_id, completed=event.get("completed", 0), description=description)

            payloads = generate_all_datasets(
                rows=args.rows,
                cols=args.cols,
                output_dir=args.output_dir,
                candidates_per_slot=args.candidates_per_slot,
                branch_budget=branch_budget_values,
                hidden_slots=hidden_slot_values,
                max_retries=args.max_retries,
                candidate_resample_retries=args.candidate_resample_retries,
                open_valid_preference_tries=args.open_valid_preference_tries,
                seed=args.seed,
                progress_callback=on_progress,
            )
            progress.update(task_id, completed=total_runs, description="Dataset generation completed")
        for domain, payload in payloads.items():
            _, summaries = validate_payload(payload)
            print_validation_report(domain, summaries)
        return

    domain = args.domain or "course"
    total_runs = len(hidden_slot_values) * len(branch_budget_values)
    with ConsoleDisplay.create_progress() as progress:
        task_id = progress.add_task("Generating datasets", total=total_runs)

        def on_progress(event: dict[str, object]) -> None:
            description = (
                "Generating "
                f"{event.get('domain', '-')}"
                f" | size={event.get('rows', '-') }x{event.get('cols', '-')}"
                f" | hidden={event.get('hidden_slots', '-')}"
                f" | budget={event.get('branch_budget', '-')}"
            )
            stage = event.get("stage")
            if stage == "scaffold":
                description += (
                    f" | scaffold {event.get('scaffold_try', '-')}/{event.get('scaffold_total', '-')}"
                )
            elif stage == "candidates":
                description += (
                    f" | scaffold {event.get('scaffold_try', '-')}/{event.get('scaffold_total', '-')}"
                    f" | candidates {event.get('candidate_try', '-')}/{event.get('candidate_total', '-')}"
                )
            elif stage == "completed":
                progress.update(task_id, advance=1, description=description)
                return
            elif stage == "failed":
                progress.update(task_id, advance=1, description=description)
                return
            progress.update(task_id, completed=event.get("completed", 0), description=description)

        payload = generate_dataset(
            domain=domain,
            rows=args.rows,
            cols=args.cols,
            output_dir=args.output_dir,
            candidates_per_slot=args.candidates_per_slot,
            branch_budget=branch_budget_values,
            hidden_slots=hidden_slot_values,
            max_retries=args.max_retries,
            candidate_resample_retries=args.candidate_resample_retries,
            open_valid_preference_tries=args.open_valid_preference_tries,
            seed=args.seed,
            progress_callback=on_progress,
        )
        progress.update(task_id, completed=total_runs, description="Dataset generation completed")
    _, summaries = validate_payload(payload)
    print_validation_report(domain, summaries)


if __name__ == "__main__":
    main()
