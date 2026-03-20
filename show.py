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


def validate_dataset() -> None:
    """Validate dataset. Logic placeholder, to be implemented later."""
    ConsoleDisplay.print_kv_panel(
        title="[bold yellow]Validate Dataset[/bold yellow]",
        items=[("Status", "[yellow]Not implemented yet[/yellow]")],
        border_style="yellow",
    )


def view_eval_results() -> None:
    """Main flow for viewing eval results."""
    from show.view_results import _prompt_choice

    while True:
        base_path = prompt_path(default="results")
        if base_path == MAIN:
            return

        while True:
            model = prompt_model(base_path)
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
                    nav = run_specific_results(base_path, model)
                    if nav == MAIN:
                        return
                    if nav == BACK:
                        continue
                    continue

                # Default or 1: average results
                model_path = Path(base_path) / model
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
                run_average_results(base_path, model, domain_filter)
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
