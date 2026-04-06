import argparse
import json
import random

from agent.agent import Agent
from agent.cache_env import CacheEnv
from agent.task import DEFAULT_MAX_QUERY_FIELDS, DEFAULT_MAX_QUERY_IDS
from load_datasets.loader import DEFAULT_DATA_DIR, load_all_dataset_objects
from utils.console_display import ConsoleDisplay


DOMAIN_CHOICES = ["course", "shopping", "travel", "workforce", "meal", "pc_build"]
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_SEED = 42
DEFAULT_AGENT_PARAMS = "{}"
DEFAULT_MAX_STEPS = 1000
DEFAULT_TOOL_FAILURE_RATES = "[0.0]"
DEFAULT_NUM_TRIALS = 1
DEFAULT_TOOLS_DOMAIN_ONLY = True
DEFAULT_SAVE_PATH = "output.json"
DEFAULT_OVERWRITE_RESULTS = False
DEFAULT_DOMAIN = ["all"]
DEFAULT_DOMAIN_FALLBACK = ["course"]
DEFAULT_EXTRA_QUERY_NUM = -1
DEFAULT_MAX_WORKERS = 25


def parse_list_arg(value, item_type):
    if value is None:
        return None

    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [item_type(item) for item in parsed]
    except json.JSONDecodeError:
        pass

    return [item_type(item.strip()) for item in value.split(",") if item.strip()]


def set_seed(seed: int) -> None:
    """Set random seed for reproducibility."""
    random.seed(seed)


def main(
    model,
    domain,
    data_dir=None,
    agent_params=None,
    max_steps=DEFAULT_MAX_STEPS,
    tool_failure_rates=None,
    num_trials=DEFAULT_NUM_TRIALS,
    tools_domain_only=DEFAULT_TOOLS_DOMAIN_ONLY,
    save_path=DEFAULT_SAVE_PATH,
    max_query_ids=DEFAULT_MAX_QUERY_IDS,
    max_query_fields=DEFAULT_MAX_QUERY_FIELDS,
    overwrite_results=DEFAULT_OVERWRITE_RESULTS,
    hidden_slots=None,
    branch_budget=None,
    check_include_reason=False,
    global_check_alpha=1,
    extra_query_num=DEFAULT_EXTRA_QUERY_NUM,
    seed=DEFAULT_SEED,
    max_workers=DEFAULT_MAX_WORKERS,
    max_length_truncations=3,
):
    """
    Assemble dataset, agent, and cache env, then run the full benchmark.
    """
    set_seed(seed)
    data_dir = data_dir or DEFAULT_DATA_DIR
    all_objects = load_all_dataset_objects(data_dir=data_dir)
    if domain == "all" or domain is None:
        dataset_objects = all_objects
    else:
        dataset_objects = [obj for obj in all_objects if obj.domain in domain]
    if hidden_slots is not None and len(hidden_slots) > 0:
        hidden_set = set(hidden_slots)
        dataset_objects = [
            obj for obj in dataset_objects
            if obj.hidden_slot_count is not None and obj.hidden_slot_count in hidden_set
        ]
    if branch_budget is not None and len(branch_budget) > 0:
        budget_set = set(branch_budget)
        dataset_objects = [
            obj for obj in dataset_objects
            if obj.branch_budget is not None and obj.branch_budget in budget_set
        ]
    if not dataset_objects:
        raise ValueError(f"No dataset objects found for domains: {domain}")
    if max_query_ids <= 0:
        raise ValueError("max_query_ids must be positive")
    if max_query_fields <= 0:
        raise ValueError("max_query_fields must be positive")
    if global_check_alpha is not None and global_check_alpha < 0 and global_check_alpha != -1:
        raise ValueError("global_check_alpha must be non-negative (or -1 for unlimited)")
    if extra_query_num < 0 and extra_query_num != -1:
        raise ValueError("extra_query_num must be non-negative (or -1 for unlimited)")

    ConsoleDisplay.print_kv_panel(
        title="[bold green]Benchmark Run Configuration[/bold green]",
        items=[
            ("Model", model),
            ("Data Dir", data_dir),
            ("Domains", ", ".join(domain)),
            ("Tool Failure Rates", tool_failure_rates or [0.0]),
            ("Num Trials", num_trials),
            ("Max Steps", max_steps),
            ("Tools Domain Only", tools_domain_only),
            ("Max Query IDs", max_query_ids),
            ("Max Query Fields", max_query_fields),
            ("Overwrite Results", overwrite_results),
            ("Hidden Slots Filter", str(hidden_slots) if hidden_slots else "-"),
            ("Branch Budget Filter", str(branch_budget) if branch_budget else "-"),
            ("Check Include Reason", check_include_reason),
            ("Global Check Alpha", global_check_alpha),
            ("Extra Query Num", extra_query_num),
            ("Max Workers", max_workers),
            ("Save Path", save_path),
            ("Seed", seed),
            ("Dataset Objects", len(dataset_objects)),
        ],
        border_style="green",
    )

    ConsoleDisplay.print_table(
        title="Selected dataset objects",
        headers=("Domain", "Instance ID", "Rows", "Cols", "Hidden Slots", "Branch Budget", "Branch Allocations"),
        rows=[
            (
                obj.domain,
                obj.instance_id,
                obj.rows,
                obj.cols,
                obj.hidden_slot_count,
                obj.branch_budget,
                str(obj.branch_budget_allocations_meta),
            )
            for obj in dataset_objects
        ],
        panel_title="[bold blue]Datasets To Run[/bold blue]",
        border_style="blue",
    )

    cache_env = CacheEnv(
        dataset_objects=dataset_objects,
        max_steps=max_steps,
        tool_failure_rates=tool_failure_rates or [0.0],
        num_trials=num_trials,
        tools_domain_only=tools_domain_only,
        max_query_ids=max_query_ids,
        max_query_fields=max_query_fields,
        check_include_reason=check_include_reason,
        global_check_alpha=global_check_alpha,
        extra_query_num=extra_query_num,
        benchmark_config={
            "model": model,
            "domain": list(domain),
            "data_dir": data_dir,
            "agent_params": agent_params or {},
            "max_steps": max_steps,
            "tool_failure_rates": list(tool_failure_rates or [0.0]),
            "num_trials": num_trials,
            "tools_domain_only": tools_domain_only,
            "save_path": save_path,
            "overwrite_results": overwrite_results,
            "max_query_ids": max_query_ids,
            "max_query_fields": max_query_fields,
            "hidden_slots": list(hidden_slots) if hidden_slots else None,
            "branch_budget": list(branch_budget) if branch_budget else None,
            "check_include_reason": check_include_reason,
            "global_check_alpha": global_check_alpha,
            "extra_query_num": extra_query_num,
            "seed": seed,
        },
        overwrite_results=overwrite_results,
        seed=seed,
        max_workers=max_workers,
        max_length_truncations=max_length_truncations,
    )
    agent = Agent(model=model, **(agent_params or {}))
    total_runs = cache_env.get_total_runs()

    ConsoleDisplay.print_kv_panel(
        title="[bold yellow]Benchmark Execution[/bold yellow]",
        items=[
            ("Stage", "Starting benchmark tasks"),
            ("Total Runs", total_runs),
            ("Datasets", len(dataset_objects)),
            ("Max Query IDs", max_query_ids),
            ("Max Query Fields", max_query_fields),
            ("Overwrite Results", overwrite_results),
            ("Hidden Slots Filter", str(hidden_slots) if hidden_slots else "-"),
            ("Branch Budget Filter", str(branch_budget) if branch_budget else "-"),
            ("Check Include Reason", check_include_reason),
            ("Global Check Alpha", global_check_alpha),
            ("Extra Query Num", extra_query_num),
            ("Save Path", save_path),
        ],
        border_style="yellow",
    )

    is_interactive_terminal = bool(getattr(ConsoleDisplay.console, "is_terminal", False))

    with ConsoleDisplay.create_progress() as progress:
        task_id = progress.add_task("Running benchmark tasks", total=total_runs)

        def on_progress(event: dict[str, object]) -> None:
            run_index = event.get("run_index", "-")
            total_runs_display = event.get("total_runs", total_runs)
            description = (
                f"[{run_index}/{total_runs_display}] "
                "Running "
                f"{event.get('domain', '-')}/"
                f"{event.get('instance_id', '-')}"
                f" | fail={event.get('tool_failure_rate', '-')}"
                f" | trial={event.get('trial_index', '-')}/{event.get('num_trials', '-')}"
            )
            if event.get("stage") == "start":
                progress.update(task_id, description=description)
                if not is_interactive_terminal:
                    ConsoleDisplay.console.print(description)
                return
            if event.get("stage") == "cached":
                progress.update(
                    task_id,
                    advance=1,
                    description=f"{description} | cached",
                )
                if not is_interactive_terminal:
                    ConsoleDisplay.console.print(f"{description} | cached")
                return
            progress.update(
                task_id,
                advance=1,
                description=description,
            )
            if not is_interactive_terminal:
                status = event.get("status", "-")
                ConsoleDisplay.console.print(f"{description} | status={status}")

        result = cache_env.run(agent=agent, save_path=save_path, progress_callback=on_progress)
        progress.update(task_id, completed=total_runs, description="Benchmark tasks completed")

    average_score = result.get("average_score") if isinstance(result, dict) else None
    average_usage = result.get("average_usage", {}) if isinstance(result, dict) else {}
    average_score_display = (
        f"{average_score:.4f}" if isinstance(average_score, (int, float)) else "-"
    )
    average_prompt_tokens = average_usage.get("prompt_tokens")
    average_completion_tokens = average_usage.get("completion_tokens")
    average_total_tokens = average_usage.get("total_tokens")
    average_cost = average_usage.get("cost")
    average_time = average_usage.get("time")
    average_tool_calls = average_usage.get("tool_calls_num")
    average_step_num = average_usage.get("step_num")
    summary = {
        "model": model,
        "domains": domain,
        "dataset_objects": len(dataset_objects),
        "total_runs": total_runs,
        "average_score": average_score,
        "average_prompt_tokens": average_prompt_tokens,
        "average_completion_tokens": average_completion_tokens,
        "average_total_tokens": average_total_tokens,
        "average_tool_calls": average_tool_calls,
        "average_step_num": average_step_num,
        "average_time_seconds": average_time,
        "average_cost": average_cost,
        "max_query_ids": max_query_ids,
        "max_query_fields": max_query_fields,
        "overwrite_results": overwrite_results,
        "hidden_slots": hidden_slots,
        "branch_budget": branch_budget,
        "extra_query_num": extra_query_num,
        "save_path": save_path,
        "status": "Completed",
    }
    if isinstance(result, dict):
        result["summary"] = summary

    ConsoleDisplay.print_kv_panel(
        title="[bold green]Benchmark Run Finished[/bold green]",
        items=[
            ("Model", model),
            ("Domains", ", ".join(domain)),
            ("Dataset Objects", len(dataset_objects)),
            ("Total Runs", total_runs),
            ("Average Score", average_score_display),
            ("Avg Prompt Tokens", f"{average_prompt_tokens:.2f}" if isinstance(average_prompt_tokens, (int, float)) else "-"),
            ("Avg Completion Tokens", f"{average_completion_tokens:.2f}" if isinstance(average_completion_tokens, (int, float)) else "-"),
            ("Avg Total Tokens", f"{average_total_tokens:.2f}" if isinstance(average_total_tokens, (int, float)) else "-"),
            ("Avg Tool Calls", f"{average_tool_calls:.2f}" if isinstance(average_tool_calls, (int, float)) else "-"),
            ("Avg Steps", f"{average_step_num:.2f}" if isinstance(average_step_num, (int, float)) else "-"),
            ("Avg Time (s)", f"{average_time:.2f}" if isinstance(average_time, (int, float)) else "-"),
            ("Avg Cost", f"{average_cost:.6f}" if isinstance(average_cost, (int, float)) else "-"),
            ("Max Query IDs", max_query_ids),
            ("Max Query Fields", max_query_fields),
            ("Overwrite Results", overwrite_results),
            ("Cached Runs", result.get("cached_runs", 0) if isinstance(result, dict) else 0),
            ("Hidden Slots Filter", str(hidden_slots) if hidden_slots else "-"),
            ("Branch Budget Filter", str(branch_budget) if branch_budget else "-"),
            ("Check Include Reason", check_include_reason),
            ("Global Check Alpha", global_check_alpha),
            ("Extra Query Num", extra_query_num),
            ("Save Path", save_path),
            ("Status", "[green]Completed[/green]"),
        ],
        border_style="green",
    )
    return result

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name")
    parser.add_argument(
        "--agent-params",
        default=DEFAULT_AGENT_PARAMS,
        help="Extra agent parameters as a JSON string",
    )
    parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        help="Path to the dataset directory",
    )
    parser.add_argument(
        "--domain",
        nargs="+",
        choices=DOMAIN_CHOICES + ["all"],
        default=DEFAULT_DOMAIN,
        help=f"One or more domains to evaluate: {', '.join(DOMAIN_CHOICES)}, or 'all'",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help="Maximum number of steps per task",
    )
    parser.add_argument(
        "--tool-failure-rates",
        default=DEFAULT_TOOL_FAILURE_RATES,
        help="List of tool failure rates, as JSON or comma-separated, e.g. [0,0.1,0.5]",
    )
    parser.add_argument(
        "--num-trials",
        dest="num_trials",
        type=int,
        default=DEFAULT_NUM_TRIALS,
        help="Number of repeated trials per task",
    )
    parser.add_argument(
        "--tools-all-domains",
        dest="tools_domain_only",
        action="store_false",
        default=DEFAULT_TOOLS_DOMAIN_ONLY,
        help="Expose tools for all domains; by default only the current domain's tools are shown",
    )
    parser.add_argument(
        "--save-path",
        default=DEFAULT_SAVE_PATH,
        help="Output path for results",
    )
    parser.add_argument(
        "--overwrite-results",
        action="store_true",
        default=DEFAULT_OVERWRITE_RESULTS,
        help="If set, overwrite existing result files; otherwise reuse cached results",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Random seed",
    )
    parser.add_argument(
        "--max-query-ids",
        type=int,
        default=DEFAULT_MAX_QUERY_IDS,
        help="Maximum number of item IDs per multi-attribute query",
    )
    parser.add_argument(
        "--max-query-fields",
        type=int,
        default=DEFAULT_MAX_QUERY_FIELDS,
        help="Maximum number of fields per multi-attribute query",
    )
    parser.add_argument(
        "--hidden-slots",
        type=int,
        nargs="*",
        default=None,
        help="Only run instances whose hidden_slots count is in this list; no filter if omitted",
    )
    parser.add_argument(
        "--branch-budget",
        type=int,
        nargs="*",
        default=None,
        help="Only run instances whose branch_budget is in this list; no filter if omitted",
    )
    parser.add_argument(
        "--check-include-reason",
        action="store_true",
        default=False,
        help="If set, constraint check tools return a violation reason in addition to is_valid",
    )
    parser.add_argument(
        "--global-check-alpha",
        type=float,
        default=-1,
        help=(
            "Limits global constraint check calls to floor(alpha * hidden_slots); default -1 (unlimited). "
            "0 = disallow all global checks, 0.5 = strict, 1 = ~one call per hidden slot, 2 = relaxed."
        ),
    )
    parser.add_argument(
        "--extra-query-num",
        dest="extra_query_num",
        type=int,
        default=DEFAULT_EXTRA_QUERY_NUM,
        help=(
            "Extra attribute query budget per hidden slot on top of (slot_constraints + hidden_slots); "
            "default -1 (unlimited)."
        ),
    )
    parser.add_argument(
        "--max-workers",
        dest="max_workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Maximum number of tasks to run in parallel; default 25",
    )
    parser.add_argument(
        "--max-length-truncations",
        dest="max_length_truncations",
        type=int,
        default=3,
        help=(
            "Maximum number of times a task's output may be truncated due to exceeding max_tokens "
            "before the task is marked as error and terminated; default 3."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    domain = DOMAIN_CHOICES if "all" in args.domain else (args.domain or DEFAULT_DOMAIN_FALLBACK)
    main(
        model=args.model,
        save_path=args.save_path,
        domain=domain,
        agent_params=json.loads(args.agent_params),
        max_steps=args.max_steps,
        tool_failure_rates=parse_list_arg(args.tool_failure_rates, float),
        num_trials=args.num_trials,
        tools_domain_only=args.tools_domain_only,
        data_dir=args.data_dir,
        max_query_ids=args.max_query_ids,
        max_query_fields=args.max_query_fields,
        overwrite_results=args.overwrite_results,
        hidden_slots=args.hidden_slots if args.hidden_slots else None,
        branch_budget=args.branch_budget if args.branch_budget else None,
        check_include_reason=args.check_include_reason,
        global_check_alpha=args.global_check_alpha,
        extra_query_num=args.extra_query_num,
        seed=args.seed,
        max_workers=args.max_workers,
        max_length_truncations=args.max_length_truncations,
    )
