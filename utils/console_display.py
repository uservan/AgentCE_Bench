from __future__ import annotations

from typing import Iterable, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table


class ConsoleDisplay:
    console = Console()

    @classmethod
    def create_progress(cls) -> Progress:
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=cls.console,
            transient=False,
        )

    @classmethod
    def print_kv_panel(cls, title: str, items: Sequence[tuple[str, object]], border_style: str = "blue") -> None:
        lines = [f"[white]{label}:[/] {value}" for label, value in items]
        cls.console.print(
            Panel(
                "\n".join(lines),
                title=title,
                border_style=border_style,
            )
        )

    @classmethod
    def print_table(
        cls,
        title: str,
        headers: Sequence[str],
        rows: Iterable[Sequence[object]],
        *,
        panel_title: str | None = None,
        border_style: str = "blue",
    ) -> None:
        table = Table(title=title, show_header=True, header_style="bold magenta")
        for header in headers:
            table.add_column(header)
        for row in rows:
            table.add_row(*(str(cell) for cell in row))

        if panel_title is None:
            cls.console.print(table)
        else:
            cls.console.print(Panel(table, title=panel_title, border_style=border_style))

    @classmethod
    def print_validation_summary(cls, instance_id: str, domain: str, is_valid: bool) -> None:
        cls.print_kv_panel(
            title="[bold green]Validation Summary[/bold green]",
            items=[
                ("Instance", instance_id),
                ("Domain", domain),
                ("validate_dataset", "[green]PASS[/green]" if is_valid else "[red]FAIL[/red]"),
            ],
            border_style="green",
        )

    @classmethod
    def print_solution_report(cls, title: str, solution_report: dict) -> None:
        rows = [
            ("slot", f"({result['row']}, {result['col']})", "[green]PASS[/green]" if result["ok"] else "[red]FAIL[/red]", result["reason"] or "-")
            for result in solution_report["slots"]
        ]
        rows.append(
            (
                "global",
                "-",
                "[green]PASS[/green]" if solution_report["global"]["ok"] else "[red]FAIL[/red]",
                solution_report["global"]["reason"] or "-",
            )
        )
        cls.print_table(
            title=title,
            headers=("Scope", "Index", "Status", "Reason"),
            rows=rows,
            panel_title="[bold blue]Truth Solution Report[/bold blue]",
            border_style="blue",
        )

    @classmethod
    def print_slot_examples(cls, slot_examples: list[dict]) -> None:
        cls.console.print(Panel("[bold white]Slot substitution examples[/bold white]", border_style="cyan"))
        for slot in slot_examples:
            rows = []
            if not slot["examples"]:
                rows.append(("-", "-", "-", "-", "No alternative candidate examples"))
            else:
                for example in slot["examples"]:
                    reasons = []
                    if example["slot_reason"]:
                        reasons.append(f"slot: {example['slot_reason']}")
                    if example["global_reason"]:
                        reasons.append(f"global: {example['global_reason']}")

                    rows.append(
                        (
                            example["candidate_id"],
                            "[green]PASS[/green]" if example["slot_ok"] else "[red]FAIL[/red]",
                            "[green]PASS[/green]" if example["global_ok"] else "[red]FAIL[/red]",
                            "\n".join(reasons) if reasons else "-",
                        )
                    )

            cls.print_table(
                title="Candidate checks",
                headers=("Candidate", "Slot", "Global", "Reasons"),
                rows=rows,
                panel_title=(
                    f"[bold blue]Slot ({slot['row']}, {slot['col']})[/bold blue] "
                    f"[white]truth={slot['truth_id']}[/white] "
                ),
                border_style="blue",
            )

    @classmethod
    def print_dataset_summary_report(cls, domain: str, summaries: list[dict]) -> None:
        rows = [
            (
                domain,
                summary["instance_id"],
                summary["avg_candidates"],
                summary["branch_budget"],
                summary["branch_slots"],
                summary["item_pool_size"],
            )
            for summary in summaries
        ]
        cls.print_table(
            title="Generated dataset statistics",
            headers=(
                "Domain",
                "Instance ID",
                "Avg Candidates Each Hidden Slot",
                "Branch Budget",
                "Branch Slots",
                "Item Pool Size",
            ),
            rows=rows,
            panel_title=f"[bold green]Dataset Summary: {domain}[/bold green]",
            border_style="green",
        )
