"""Terminal display: matrices and single result using ConsoleDisplay."""
from typing import Any

from utils.console_display import ConsoleDisplay


def _fmt(v: float | None) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        if v == int(v):
            return str(int(v))
        return f"{v:.2f}"
    return str(v)


def print_matrix(
    matrix: dict[tuple[int, int], float],
    hidden_list: list[int],
    branch_list: list[int],
    title: str,
) -> None:
    """Print matrix with branch_budget as rows, hidden_slots as columns."""
    if not hidden_list or not branch_list:
        ConsoleDisplay.console.print(f"[{title}] No data")
        return

    headers = ["b\\h"] + [str(h) for h in hidden_list]
    rows = []
    for b in branch_list:
        row_vals = [_fmt(matrix.get((h, b))) for h in hidden_list]
        rows.append([str(b)] + row_vals)

    ConsoleDisplay.print_table(
        title=title,
        headers=headers,
        rows=rows,
        panel_title=f"[bold blue]{title}[/bold blue]",
        border_style="blue",
    )


def print_average_matrices(
    avg_data: dict[str, dict[tuple[int, int], float]],
    hidden_list: list[int],
    branch_list: list[int],
) -> None:
    """Print matrices for score, completion_tokens, cost, time, tool_calls_num, step_num."""
    titles = {
        "score": "Average Score",
        "completion_tokens": "Average Completion Tokens",
        "cost": "Average Cost",
        "time": "Average Time (s)",
        "tool_calls_num": "Average Tool Calls",
        "step_num": "Average Steps",
    }
    for key, title in titles.items():
        m = avg_data.get(key, {})
        print_matrix(m, hidden_list, branch_list, title)


def print_single_result(extracted: dict[str, Any]) -> None:
    """Print single run: status, reason, score, completion_tokens, cost, tool_calls_num, step_num."""
    items = [
        ("status", extracted.get("status", "-")),
        ("reason", extracted.get("reason", "-")),
        ("score", extracted.get("score", "-")),
        ("completion_tokens", extracted.get("completion_tokens", "-")),
        ("cost", extracted.get("cost", "-")),
        ("tool_calls_num", extracted.get("tool_calls_num", "-")),
        ("step_num", extracted.get("step_num", "-")),
        ("time (s)", extracted.get("time", "-")),
    ]
    ConsoleDisplay.print_kv_panel(
        title="[bold green]Run Result[/bold green]",
        items=items,
        border_style="green",
    )
