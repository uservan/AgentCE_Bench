import argparse
import json

from agent.agent import Agent
from agent.cache_env import CacheEnv
from datasets import build_dataset, list_registered_datasets


def main(
    dataset,
    model,
    save_path,
    agent_params=None,
    max_steps=None,
    num_trials=1,
    dataset_kwargs=None,
    together_tasks=None,
    tool_failure_rates=None,
):
    """
    组装 dataset、agent、cache env，并执行完整流程。
    """
    dataset_obj = build_dataset(dataset, dataset_kwargs=dataset_kwargs)
    agent = Agent(model=model, **(agent_params or {}))
    cache_env = CacheEnv(
        max_steps=max_steps,
        num_trials=num_trials,
        together_tasks=together_tasks,
        tool_failure_rates=tool_failure_rates,
    )
    return cache_env.run(dataset=dataset_obj, agent=agent, save_path=save_path)


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


def parse_args():
    dataset_choices = list_registered_datasets()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        required=True,
        choices=dataset_choices,
        help=f"dataset 名称，可选值: {', '.join(dataset_choices)}",
    )
    parser.add_argument("--model", required=True, help="模型名称")
    parser.add_argument("--save-path", required=True, help="结果 JSON 输出路径")
    parser.add_argument(
        "--agent-params",
        default="{}",
        help="Agent 额外参数, JSON 字符串",
    )
    parser.add_argument(
        "--dataset-kwargs",
        default="{}",
        help="Dataset 初始化参数, JSON 字符串",
    )
    parser.add_argument("--max-steps", type=int, default=None, help="单个 task 最大步数")
    parser.add_argument(
        "--together-tasks",
        default="[1]",
        help="融合 task 数量列表，支持 JSON 或逗号分隔，如 [1,2,3] 或 1,2,3",
    )
    parser.add_argument(
        "--tool-failure-rates",
        default="[0.0]",
        help="tool 调用失败率列表，支持 JSON 或逗号分隔，如 [0,0.1,0.5]",
    )
    parser.add_argument(
        "--num-trials",
        dest="num_trials",
        type=int,
        default=1,
        help="每个 task 的重复运行次数",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(
        dataset=args.dataset,
        model=args.model,
        save_path=args.save_path,
        agent_params=json.loads(args.agent_params),
        max_steps=args.max_steps,
        num_trials=args.num_trials,
        dataset_kwargs=json.loads(args.dataset_kwargs),
        together_tasks=parse_list_arg(args.together_tasks, int),
        tool_failure_rates=parse_list_arg(args.tool_failure_rates, float),
    )
