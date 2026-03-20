"""Interactive logic for viewing eval results."""
import re
from pathlib import Path
from typing import Any

from utils.console_display import ConsoleDisplay

from .display import print_average_matrices, print_single_result
from .result_loader import (
    aggregate_by_hidden_branch,
    collect_json_files,
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
    """Infer domain list from result_instance_id directory names under model_path."""
    domains: set[str] = set()
    for d in model_path.iterdir():
        if not d.is_dir():
            continue
        name = d.name
        if "_r" in name and "_c" in name and "_h" in name and "_b" in name:
            domain = name.split("_r")[0]
            domains.add(domain)
    return sorted(domains)


def _get_hidden_branch_pairs(model_path: Path, domain: str) -> list[tuple[int, int]]:
    """Get all (hidden_slots, branch_budget) pairs for this domain."""
    pairs: set[tuple[int, int]] = set()
    domain_prefix = f"{domain}_"
    for d in model_path.iterdir():
        if not d.is_dir() or not d.name.startswith(domain_prefix):
            continue
        m = re.search(r"_h(\d+)_b(\d+)_", d.name)
        if m:
            pairs.add((int(m.group(1)), int(m.group(2))))
    return sorted(pairs)


def _get_json_files_for_pair(
    model_path: Path, domain: str, hidden: int, branch: int
) -> list[Path]:
    """Get all json files for (domain, hidden, branch)."""
    prefix = f"{domain}_"
    suffix = f"_h{hidden}_b{branch}_"
    out: list[Path] = []
    for d in model_path.iterdir():
        if not d.is_dir():
            continue
        if d.name.startswith(prefix) and suffix in d.name:
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
    avg_data = compute_average_matrix(agg)
    print_average_matrices(avg_data, hidden_set, branch_set)


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
