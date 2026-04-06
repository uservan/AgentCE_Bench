"""Interactive logic for viewing eval results."""
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from utils.console_display import ConsoleDisplay

from .display import (
    print_average_matrices,
    print_metric_ranking,
    print_overall_average,
    print_single_result,
)
from .result_loader import (
    aggregate_by_hidden_branch,
    collect_json_files,
    compute_overall_average,
    compute_average_matrix,
    extract_run_result,
    load_json,
)

BACK = "__BACK__"
MAIN = "__MAIN__"


def _get_models(base_path: str) -> list[str]:
    """Get first-level directories under base_path as model list."""
    p = Path(base_path)
    if not p.is_dir():
        return []
    return [d.name for d in p.iterdir() if d.is_dir()]


def get_domains(model_path: Path) -> list[str]:
    """List domain directories directly under model_path."""
    domains: list[str] = []
    for d in model_path.iterdir():
        if d.is_dir():
            domains.append(d.name)
    return sorted(domains)


def _get_hidden_branch_pairs(model_path: Path, domain: str) -> list[tuple[int, int]]:
    """Get all (hidden_slots, branch_budget) pairs for this domain."""
    pairs: set[tuple[int, int]] = set()
    domain_dir = model_path / domain
    if not domain_dir.is_dir():
        return []
    for d in domain_dir.iterdir():
        if not d.is_dir():
            continue
        m = re.search(r"_h(\d+)_b(\d+)", d.name)
        if m:
            pairs.add((int(m.group(1)), int(m.group(2))))
    return sorted(pairs)


def _get_json_files_for_pair(
    model_path: Path, domain: str, hidden: int, branch: int
) -> list[Path]:
    """Get all json files for (domain, hidden, branch)."""
    domain_dir = model_path / domain
    if not domain_dir.is_dir():
        return []
    suffix = f"_h{hidden}_b{branch}"
    out: list[Path] = []
    for d in domain_dir.iterdir():
        if not d.is_dir():
            continue
        if suffix in d.name:
            for f in d.glob("*.json"):
                out.append(f)
    return sorted(out)


def _prompt_choice(
    prompt: str,
    options: list[str],
    default: str | None = None,
    allow_back: bool = True,
    allow_main: bool = True,
) -> str:
    """Show options, user inputs index or enter for default. Returns BACK or MAIN for navigation."""
    valid_range = f"1-{len(options)}"
    while True:
        for i, opt in enumerate(options, 1):
            marker = " [dim](default)[/dim]" if default is not None and opt == default else ""
            ConsoleDisplay.console.print(f"  {i}. {opt}{marker}")
        if allow_back or allow_main:
            nav = []
            if allow_back:
                nav.append("0 = back")
            if allow_main:
                nav.append("m = main menu")
            ConsoleDisplay.console.print(f"  [dim]{', '.join(nav)}[/dim]")
        inp = ConsoleDisplay.console.input(prompt).strip().lower()
        if inp == "m" and allow_main:
            return MAIN
        if inp == "0" and allow_back:
            return BACK
        if not inp and default is not None:
            return default
        try:
            idx = int(inp)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            pass
        ConsoleDisplay.console.print(f"[red]Invalid option. Please enter {valid_range}, 0 for back, or m for main menu.[/red]")


def prompt_path(default: str = "results") -> str:
    """Prompt user for path, default is results. Returns MAIN if user wants main menu."""
    ConsoleDisplay.console.print(f"\n[bold]Enter result directory path[/bold] (press Enter for default '{default}'):")
    ConsoleDisplay.console.print("  [dim]m = main menu[/dim]")
    inp = ConsoleDisplay.console.input("[bold cyan]> [/bold cyan]").strip().lower()
    if inp == "m":
        return MAIN
    return inp if inp else default


def prompt_model(base_path: str) -> str | None:
    """Prompt user to select model. Returns None if no models, BACK/MAIN for navigation."""
    models = _get_models(base_path)
    if not models:
        path = Path(base_path)
        if not path.exists():
            ConsoleDisplay.console.print(f"[red]Path does not exist: {base_path}[/red]")
        else:
            ConsoleDisplay.console.print(f"[red]No model directory found under: {base_path}[/red]")
        return None
    ConsoleDisplay.console.print("\n[bold]Select model:[/bold]")
    chosen = _prompt_choice("[bold cyan]> [/bold cyan]", models, models[0])
    return chosen if chosen not in (BACK, MAIN) else chosen


def run_average_results(base_path: str, model: str, domain: str | None) -> None:
    """Display average result matrices."""
    model_path = Path(base_path) / model
    if not model_path.is_dir():
        ConsoleDisplay.console.print("[red]Model directory does not exist.[/red]")
        return

    items = collect_json_files(model_path, domain=domain)
    if not items:
        ConsoleDisplay.console.print("[red]No matching JSON files found.[/red]")
        return

    agg = aggregate_by_hidden_branch(items)
    if not agg:
        ConsoleDisplay.console.print("[red]Failed to parse aggregated data.[/red]")
        return

    hidden_set = sorted({k[0] for k in agg})
    branch_set = sorted({k[1] for k in agg})
    overall_avg = compute_overall_average(agg)
    avg_data = compute_average_matrix(agg)
    print_overall_average(overall_avg)
    print_average_matrices(avg_data, hidden_set, branch_set)


def _build_model_average_summary(base_path: str, model: str) -> dict[str, Any] | None:
    """Build aggregated average summary for a single model."""
    model_path = Path(base_path) / model
    if not model_path.is_dir():
        return None

    items = collect_json_files(model_path, domain=None)
    if not items:
        return None

    agg = aggregate_by_hidden_branch(items)
    if not agg:
        return None

    return {
        "model": model,
        "item_count": len(items),
        "group_count": len(agg),
        "agg": agg,
        "hidden_set": sorted({k[0] for k in agg}),
        "branch_set": sorted({k[1] for k in agg}),
        "overall_avg": compute_overall_average(agg),
        "avg_data": compute_average_matrix(agg),
    }


def _model_ranking_key(model_summary: dict[str, Any]) -> tuple[float, float, float, float, str]:
    """Sort by score desc, then cost/time/tokens asc, then model name."""
    overall = model_summary["overall_avg"]
    score = overall.get("score")
    cost = overall.get("cost")
    time = overall.get("time")
    completion_tokens = overall.get("completion_tokens")
    return (
        -(score if score is not None else -math.inf),
        cost if cost is not None else math.inf,
        time if time is not None else math.inf,
        completion_tokens if completion_tokens is not None else math.inf,
        model_summary["model"],
    )


def _metric_ranking_key(metric: str, descending: bool) -> Any:
    """Build a sort key for one metric."""
    def sort_key(model_summary: dict[str, Any]) -> tuple[float, str]:
        value = model_summary["overall_avg"].get(metric)
        if descending:
            primary = -(value if value is not None else -math.inf)
        else:
            primary = value if value is not None else math.inf
        return (primary, model_summary["model"])

    return sort_key


def _print_model_loading_status(index: int, total: int, model: str, summary: dict[str, Any] | None) -> None:
    """Print loading status while collecting model summaries."""
    if summary is None:
        ConsoleDisplay.console.print(
            f"[yellow][{index}/{total}] {model}: no valid result files found, skipped[/yellow]"
        )
        return

    ConsoleDisplay.console.print(
        "[cyan]"
        f"[{index}/{total}] {model}: loaded {summary['item_count']} files, "
        f"{summary['group_count']} hidden/budget groups"
        "[/cyan]"
    )


def compare_model_results(base_path: str) -> None:
    """Compare all models under a result path and display ranked summaries."""
    models = _get_models(base_path)
    if not models:
        path = Path(base_path)
        if not path.exists():
            ConsoleDisplay.console.print(f"[red]Path does not exist: {base_path}[/red]")
        else:
            ConsoleDisplay.console.print(f"[red]No model directory found under: {base_path}[/red]")
        return

    ConsoleDisplay.console.print(
        f"\n[bold]Loading model results[/bold] [dim]({base_path})[/dim]"
    )

    total_models = len(models)
    results_map: dict[str, dict[str, Any] | None] = {}

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_model = {
            executor.submit(_build_model_average_summary, base_path, model): model
            for model in models
        }
        completed = 0
        for future in as_completed(future_to_model):
            model = future_to_model[future]
            summary = future.result()
            results_map[model] = summary
            completed += 1
            _print_model_loading_status(completed, total_models, model, summary)

    summaries = [
        results_map[model]
        for model in models
        if results_map.get(model) is not None
    ]

    if not summaries:
        ConsoleDisplay.console.print("[red]No matching JSON files found for any model.[/red]")
        return

    metric_orders = [
        ("score", True),
        ("completion_tokens", False),
        ("cost", False),
        ("time", False),
        ("tool_calls_num", False),
        ("step_num", False),
    ]
    for metric, descending in metric_orders:
        metric_ranked = sorted(summaries, key=_metric_ranking_key(metric, descending))
        print_metric_ranking(metric, metric_ranked, descending=descending)


def run_specific_results(base_path: str, model: str) -> str | None:
    """Display a specific run result. Returns BACK or MAIN for navigation."""
    model_path = Path(base_path) / model
    if not model_path.is_dir():
        ConsoleDisplay.console.print("[red]Model directory does not exist.[/red]")
        return None

    domains = get_domains(model_path)
    if not domains:
        ConsoleDisplay.console.print("[red]No domain found.[/red]")
        return None

    ConsoleDisplay.console.print("\n[bold]Select domain:[/bold]")
    domain = _prompt_choice("[bold cyan]> [/bold cyan]", domains, domains[0])
    if domain in (BACK, MAIN):
        return domain

    pairs = _get_hidden_branch_pairs(model_path, domain)
    if not pairs:
        ConsoleDisplay.console.print("[red]No (hidden, branch) pair found.[/red]")
        return None

    pair_strs = [f"h{h}_b{b}" for h, b in pairs]
    ConsoleDisplay.console.print("\n[bold]Select hidden_slots and branch_budget:[/bold]")
    chosen = _prompt_choice("[bold cyan]> [/bold cyan]", pair_strs, pair_strs[0])
    if chosen in (BACK, MAIN):
        return chosen
    h, b = pairs[pair_strs.index(chosen)]

    json_files = _get_json_files_for_pair(model_path, domain, h, b)
    if not json_files:
        ConsoleDisplay.console.print("[red]No JSON file found.[/red]")
        return None

    file_strs = [f.name for f in json_files]
    ConsoleDisplay.console.print("\n[bold]Select JSON file:[/bold]")
    chosen_file = _prompt_choice("[bold cyan]> [/bold cyan]", file_strs, file_strs[0])
    if chosen_file in (BACK, MAIN):
        return chosen_file
    path = json_files[file_strs.index(chosen_file)]

    payload = load_json(str(path))
    if payload is None:
        ConsoleDisplay.console.print("[red]Failed to load file.[/red]")
        return None
    extracted = extract_run_result(payload)
    if extracted:
        print_single_result(extracted)
    else:
        ConsoleDisplay.console.print("[red]Failed to parse run_result.[/red]")
    return None
