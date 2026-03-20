"""画图方法：基于聚合数据绘制矩阵热力图等。"""
from typing import Any

try:
    import matplotlib.pyplot as plt
    import numpy as np

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def plot_score_heatmap(
    matrix: dict[tuple[int, int], float],
    hidden_list: list[int],
    branch_list: list[int],
    title: str = "Average Score",
    save_path: str | None = None,
) -> None:
    """
    绘制 score 矩阵热力图。
    hidden_list 为行（y），branch_list 为列（x）。
    """
    if not HAS_MATPLOTLIB:
        print("需要安装 matplotlib: pip install matplotlib")
        return

    data = np.zeros((len(hidden_list), len(branch_list)))
    for i, h in enumerate(hidden_list):
        for j, b in enumerate(branch_list):
            data[i, j] = matrix.get((h, b), float("nan"))

    fig, ax = plt.subplots()
    im = ax.imshow(data, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(range(len(branch_list)))
    ax.set_xticklabels(branch_list)
    ax.set_yticks(range(len(hidden_list)))
    ax.set_yticklabels(hidden_list)
    ax.set_xlabel("Branch Budget")
    ax.set_ylabel("Hidden Slots")
    ax.set_title(title)

    for i in range(len(hidden_list)):
        for j in range(len(branch_list)):
            v = data[i, j]
            if not np.isnan(v):
                text = ax.text(j, i, f"{v:.2f}", ha="center", va="center", color="black")

    plt.colorbar(im, ax=ax)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"已保存: {save_path}")
    else:
        plt.show()
    plt.close()


def plot_metric_heatmap(
    avg_data: dict[str, dict[tuple[int, int], float]],
    metric: str,
    hidden_list: list[int],
    branch_list: list[int],
    title: str | None = None,
    save_path: str | None = None,
) -> None:
    """绘制指定 metric 的矩阵热力图。score 使用 0-1 色标，其他 metric 自动缩放。"""
    if not HAS_MATPLOTLIB:
        print("需要安装 matplotlib: pip install matplotlib")
        return

    matrix = avg_data.get(metric, {})
    titles = {
        "score": "Average Score",
        "completion_tokens": "Average Completion Tokens",
        "cost": "Average Cost",
        "time": "Average Time (s)",
        "tool_calls_num": "Average Tool Calls",
        "step_num": "Average Steps",
    }
    data = np.zeros((len(hidden_list), len(branch_list)))
    for i, h in enumerate(hidden_list):
        for j, b in enumerate(branch_list):
            data[i, j] = matrix.get((h, b), float("nan"))

    fig, ax = plt.subplots()
    vmin, vmax = (0, 1) if metric == "score" else (None, None)
    im = ax.imshow(data, cmap="RdYlGn" if metric == "score" else "viridis", vmin=vmin, vmax=vmax, aspect="auto")

    ax.set_xticks(range(len(branch_list)))
    ax.set_xticklabels(branch_list)
    ax.set_yticks(range(len(hidden_list)))
    ax.set_yticklabels(hidden_list)
    ax.set_xlabel("Branch Budget")
    ax.set_ylabel("Hidden Slots")
    ax.set_title(title or titles.get(metric, metric))

    for i in range(len(hidden_list)):
        for j in range(len(branch_list)):
            v = data[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", color="black")

    plt.colorbar(im, ax=ax)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"已保存: {save_path}")
    else:
        plt.show()
    plt.close()
