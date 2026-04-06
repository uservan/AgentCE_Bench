#!/usr/bin/env python3
"""show.py - Interactive eval result viewer. Run directly to enter the interface."""
import json
from pathlib import Path

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from utils.console_display import ConsoleDisplay

from show.view_results import (
    BACK,
    MAIN,
    compare_model_results,
    get_domains,
    prompt_model,
    prompt_path,
    run_average_results,
    run_specific_results,
)


DEFAULT_DATASET_DIR = "data/5x10"


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
        ConsoleDisplay.console.print(f"\n[bold]Enter dataset directory[/bold] [dim](default: {DEFAULT_DATASET_DIR})[/dim]")
        ConsoleDisplay.console.print("  [dim]0 = back[/dim]")
        inp = ConsoleDisplay.console.input("[bold cyan]> [/bold cyan]").strip()
        if inp == "0":
            return
        dir_path = Path(inp or DEFAULT_DATASET_DIR)

        if not dir_path.is_dir():
            ConsoleDisplay.console.print(f"[red]Directory not found: {dir_path}. Please try again.[/red]")
            continue

        json_files = sorted(dir_path.glob("*.json"))
        if not json_files:
            ConsoleDisplay.console.print(f"[red]No JSON files found in {dir_path}. Please try again.[/red]")
            continue

        while True:
            ConsoleDisplay.console.print(f"\n[bold]Select a dataset file[/bold] [dim]({dir_path})[/dim]")
            for i, f in enumerate(json_files, 1):
                ConsoleDisplay.console.print(f"  {i}. {f.name}")
            ConsoleDisplay.console.print("  [dim]0 = back[/dim]")

            sel = ConsoleDisplay.console.input("[bold cyan]> [/bold cyan]").strip()
            if sel == "0":
                break
            if not sel.isdigit() or not (1 <= int(sel) <= len(json_files)):
                ConsoleDisplay.console.print("[red]Invalid selection. Please try again.[/red]")
                continue

            path = json_files[int(sel) - 1]

            try:
                payload = _load_payload(str(path))
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
            # validation done, return to file list


DEFAULT_RESULT_PATH = "results/5x7/ids5_fields5_eq-1_alpha-1/GLM-4.7-FP8/course/course_r5_c7_h1_b0/fail-0.0_trial-1.json"

ROLE_STYLES = {
    "system":    ("bold white on dark_blue",  "System"),
    "user":      ("bold green",               "User"),
    "tool":      ("bold yellow",              "Tool"),
    "assistant": ("bold cyan",                "Assistant"),
}


def view_model_messages() -> None:
    """Display raw_messages from a result JSON file in a chat-like layout."""
    while True:
        ConsoleDisplay.console.print(f"\n[bold]Enter result JSON path[/bold] [dim](default: {DEFAULT_RESULT_PATH})[/dim]")
        ConsoleDisplay.console.print("  [dim]0 = back[/dim]")
        inp = ConsoleDisplay.console.input("[bold cyan]> [/bold cyan]").strip()
        if inp == "0":
            return

        path = Path(inp or DEFAULT_RESULT_PATH)
        if not path.is_file():
            ConsoleDisplay.console.print(f"[red]File not found: {path}[/red]")
            continue

        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            ConsoleDisplay.console.print(f"[red]Failed to load file: {e}[/red]")
            continue

        run_result = payload.get("run_result", {})
        messages = run_result.get("content", [])
        if not messages:
            ConsoleDisplay.console.print("[yellow]No messages found in run_result.raw_messages.[/yellow]")
            continue

        score = run_result.get("score")
        status = run_result.get("status", "-")
        ConsoleDisplay.console.print(
            f"\n[bold]File:[/bold] {path}  |  [bold]Status:[/bold] {status}  |  [bold]Score:[/bold] {score}\n"
        )

        table = Table(show_header=True, header_style="bold", expand=True, show_lines=True)
        table.add_column("Others", style="", ratio=1)
        table.add_column("Assistant", style="cyan", ratio=1)

        for i, msg in enumerate(messages, 1):
            role = (msg.get("role") or "unknown").lower()
            _, label = ROLE_STYLES.get(role, ("bold magenta", role.capitalize()))

            # Extract text content
            raw_content = msg.get("content") or ""
            if isinstance(raw_content, list):
                parts = []
                for part in raw_content:
                    if isinstance(part, dict):
                        parts.append(part.get("text") or str(part))
                    else:
                        parts.append(str(part))
                text_content = "\n".join(parts)
            else:
                text_content = str(raw_content)

            # Append tool calls for assistant messages
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                tc_lines = []
                for tc in tool_calls:
                    fn = tc.get("function") or {}
                    tc_lines.append(f"[dim]call: {fn.get('name', '?')}({fn.get('arguments', '')})[/dim]")
                if tc_lines:
                    text_content = (text_content + "\n\n" if text_content else "") + "\n".join(tc_lines)

            cell_style = ROLE_STYLES.get(role, ("bold magenta", ""))[0]
            cell = Text(f"[{i}] {label}\n", overflow="fold")
            cell.stylize(cell_style, 0, len(f"[{i}] {label}"))
            cell.append(text_content or "(empty)")

            if role == "assistant":
                table.add_row("", cell)
            else:
                table.add_row(cell, "")

        ConsoleDisplay.console.print(table)
        ConsoleDisplay.console.print(f"[dim]--- {len(messages)} messages total ---[/dim]\n")


DEFAULT_MODEL_PATH = "results/5x7/ids5_fields5_eq-1_alpha-1/GLM-4.7-FP8"


def view_model_metric_results() -> None:
    """Main flow for viewing model metric results."""
    from show.view_results import _prompt_choice

    while True:
        ConsoleDisplay.console.print(f"\n[bold]Enter model path[/bold] [dim](default: {DEFAULT_MODEL_PATH})[/dim]")
        ConsoleDisplay.console.print("  [dim]0 = back[/dim]")
        inp = ConsoleDisplay.console.input("[bold cyan]> [/bold cyan]").strip()
        if inp == "0":
            return
        if inp == "m":
            return

        model_path_str = inp or DEFAULT_MODEL_PATH
        model_path = Path(model_path_str)
        if not model_path.is_dir():
            ConsoleDisplay.console.print(f"[red]Directory not found: {model_path}[/red]")
            continue

        base_path = str(model_path.parent)
        model = model_path.name

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

            # Average results
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


def main() -> None:
    """Interactive entry point."""
    while True:
        ConsoleDisplay.console.print("\n[bold green]=== Cached Agent Benchmark - Result Viewer ===[/bold green]\n")
        ConsoleDisplay.console.print("[bold]Choose an option:[/bold]")
        ConsoleDisplay.console.print("  1. Validate dataset")
        ConsoleDisplay.console.print("  2. View model metric results")
        ConsoleDisplay.console.print("  3. Compare model metric results")
        ConsoleDisplay.console.print("  4. View model messages")
        ConsoleDisplay.console.print("  5. Exit")
        inp = ConsoleDisplay.console.input("[bold cyan]> [/bold cyan]").strip() or "2"

        if inp == "5":
            ConsoleDisplay.console.print("[green]Goodbye.[/green]")
            break
        if inp == "1":
            validate_dataset()
        elif inp == "2":
            view_model_metric_results()
        elif inp == "3":
            base_path = prompt_path(default="results/5x7/ids5_fields5_eq-1_alpha-1")
            if base_path != MAIN:
                compare_model_results(base_path)
        elif inp == "4":
            view_model_messages()
        else:
            ConsoleDisplay.console.print("[red]Invalid option. Please enter 1–5.[/red]")


if __name__ == "__main__":
    main()
