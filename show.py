#!/usr/bin/env python3
"""show.py - Interactive eval result viewer. Run directly to enter the interface."""
from pathlib import Path

from utils.console_display import ConsoleDisplay

from show.view_results import (
    BACK,
    MAIN,
    get_domains,
    prompt_model,
    prompt_path,
    run_average_results,
    run_specific_results,
)


DEFAULT_DATASET_PATH = "data/course_dataset_r5_c5_h1-3-5-7-9-13-17_cand15_budget0-2-4-6-8-10_seed42.json"


def validate_dataset() -> None:
    """Validate a dataset file using data_generation/validation.py."""
    from data_generation.validation import (
        _load_payload,
        _summarize_instance,
        _choose_representative_instances,
        _print_instance_summary,
        _build_truth_report,
        _print_decoy_stage_report,
        _print_truth_decoy_combination_stats,
        _print_representative_cases,
        validate_dataset as _validate_dataset,
    )

    while True:
        ConsoleDisplay.console.print(f"\n[bold]Enter dataset file path[/bold] [dim](default: {DEFAULT_DATASET_PATH})[/dim]")
        ConsoleDisplay.console.print("  [dim]0 = back[/dim]")
        inp = ConsoleDisplay.console.input("[bold cyan]> [/bold cyan]").strip()
        if inp == "0":
            return
        path = inp or DEFAULT_DATASET_PATH

        try:
            payload = _load_payload(path)
        except FileNotFoundError:
            ConsoleDisplay.console.print(f"[red]File not found: {path}. Please try again.[/red]")
            continue
        except Exception as e:
            ConsoleDisplay.console.print(f"[red]Failed to load file: {e}. Please try again.[/red]")
            continue

        instances = payload["instances"]
        summaries = []
        failed = []
        for dataset in instances:
            summaries.append(_summarize_instance(dataset))
            if not _validate_dataset(dataset):
                failed.append(dataset.get("instance_id", "-"))

        ConsoleDisplay.print_dataset_summary_report(payload["domain"], summaries)

        if failed:
            ConsoleDisplay.console.print(f"[red]Validation FAILED for instances: {', '.join(failed)}[/red]")
        else:
            ConsoleDisplay.console.print("[green]All instances passed validation.[/green]")

        for dataset in _choose_representative_instances(instances):
            ConsoleDisplay.print_validation_summary(
                dataset.get("instance_id", "-"),
                dataset["domain"],
                True,
            )
            _print_instance_summary(dataset)
            ConsoleDisplay.print_solution_report("Truth solution report", _build_truth_report(dataset))
            _print_decoy_stage_report(dataset)
            _print_truth_decoy_combination_stats(dataset)
            _print_representative_cases(dataset)
        return


def view_eval_results() -> None:
    """Main flow for viewing eval results."""
    from show.view_results import _prompt_choice

    while True:
        base_path = prompt_path(default="results")
        if base_path == MAIN:
            return

        while True:
            # First level: config_dir (e.g. ids5_fields5_eq20_alpha-1)
            ConsoleDisplay.console.print("\n[bold]Select config:[/bold]")
            config_dir = prompt_model(base_path)
            if config_dir is None:
                break
            if config_dir == MAIN:
                return
            if config_dir == BACK:
                break

            config_path = str(Path(base_path) / config_dir)
            while True:
                ConsoleDisplay.console.print("\n[bold]Select model:[/bold]")
                model = prompt_model(config_path)
                if model is None:
                    break
                if model == MAIN:
                    return
                if model == BACK:
                    break

                while True:
                    ConsoleDisplay.console.print("\n[bold]Choose action:[/bold]")
                    ConsoleDisplay.console.print("  1. View average results")
                    ConsoleDisplay.console.print("  2. View specific result")
                    ConsoleDisplay.console.print("  [dim]0 = back, m = main menu[/dim]")
                    inp = ConsoleDisplay.console.input("[bold cyan]> [/bold cyan]").strip().lower() or "1"

                    if inp == "m":
                        return
                    if inp == "0":
                        break
                    if inp not in ("1", "2"):
                        ConsoleDisplay.console.print("[red]Invalid option. Please enter 1, 2, 0, or m.[/red]")
                        continue

                    if inp == "2":
                        nav = run_specific_results(config_path, model)
                        if nav == MAIN:
                            return
                        if nav == BACK:
                            continue
                        continue

                    # Default or 1: average results
                    model_path = Path(config_path) / model
                    domains = get_domains(model_path)
                    if not domains:
                        ConsoleDisplay.console.print("[red]No domain found.[/red]")
                        continue

                    domain_options = ["all"] + domains
                    ConsoleDisplay.console.print("\n[bold]Choose domain (all = aggregate all):[/bold]")
                    chosen = _prompt_choice("[bold cyan]> [/bold cyan]", domain_options, "all")
                    if chosen == MAIN:
                        return
                    if chosen == BACK:
                        continue

                    domain_filter = None if chosen == "all" else chosen
                    run_average_results(config_path, model, domain_filter)
                    continue
                continue
            continue


def main() -> None:
    """Interactive entry point."""
    while True:
        ConsoleDisplay.console.print("\n[bold green]=== Cached Agent Benchmark - Result Viewer ===[/bold green]\n")
        ConsoleDisplay.console.print("[bold]Choose an option:[/bold]")
        ConsoleDisplay.console.print("  1. Validate dataset")
        ConsoleDisplay.console.print("  2. View eval results")
        ConsoleDisplay.console.print("  3. Exit")
        inp = ConsoleDisplay.console.input("[bold cyan]> [/bold cyan]").strip() or "2"

        if inp == "3":
            ConsoleDisplay.console.print("[green]Goodbye.[/green]")
            break
        if inp == "1":
            validate_dataset()
        elif inp == "2":
            view_eval_results()
        else:
            ConsoleDisplay.console.print("[red]Invalid option. Please enter 1, 2, or 3.[/red]")


if __name__ == "__main__":
    main()
