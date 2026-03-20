"""
show.interaction - 交互逻辑。
"""

import os

DEFAULT_RESULTS_PATH = "results"


def _validate_dataset():
    """验证数据集。逻辑待后续补充。"""
    print("\n[验证数据集] 功能待补充。\n")


def _view_results(results_path: str) -> None:
    """查看结果。"""
    if not os.path.isdir(results_path):
        print(f"\n路径不存在或不是目录: {results_path}\n")
        return
    # 后续可在此调用 plot_results 或展示结果列表
    print(f"\n[查看结果] 路径: {results_path}")
    print("（结果展示与画图逻辑待补充）\n")


def run_interactive() -> None:
    """运行交互式主菜单。"""
    while True:
        print("\n" + "=" * 50)
        print("  Cached Agent Benchmark - 交互界面")
        print("=" * 50)
        print("  1. 验证数据集")
        print("  2. 查看结果")
        print("  q. 退出")
        print("=" * 50)

        choice = input("请选择 [1/2/q]: ").strip().lower()

        if choice == "q":
            print("\n再见。\n")
            break

        if choice == "1":
            _validate_dataset()
            continue

        if choice == "2":
            default_hint = f"（直接回车使用默认: {DEFAULT_RESULTS_PATH}）"
            path_input = input(f"\n请输入结果路径 {default_hint}: ").strip()
            results_path = path_input if path_input else DEFAULT_RESULTS_PATH
            _view_results(results_path)
            continue

        print("\n无效选项，请重新选择。\n")
