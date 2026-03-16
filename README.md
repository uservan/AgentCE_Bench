# cached_agent_benchmark

## Dataset Generation

数据生成器在 `data_generation/generate.py`，生成出的 JSON 默认保存在项目根目录下的 `data/`。

单个领域的生成例子：

```bash
python data_generation/generate.py --domain course --num-instances 1 --rows 5 --cols 2 3 4 5 6 7 --candidates-per-slot 24 --valid-options 2 --seed 42
```

这条命令表示：

- 生成 `course` 场景的数据
- 对每一种尺寸组合都生成 `1` 个实例
- `rows` 固定为 `5`
- `cols` 依次取 `2 3 4 5 6 7`
- 因此会生成 `5x2`、`5x3`、`5x4`、`5x5`、`5x6`、`5x7`
- 输出到项目根目录下的 `data/`
- 每个 slot 显式存 `24` 个候选 item id
- 要求每个 slot 恰好有 `2` 个最终满足行列约束的候选
- 使用随机种子 `42`

当前生成逻辑是先生成一个满足所有约束的完整 `truth_solution`，再对每个格子单独构造一组 `candidate_ids`。这些候选都会满足该格的 `slot_constraints`，但只有其中一部分在替换进真表后还能继续满足对应的 `row_constraints`、`col_constraints` 和 `global_constraints`。

这会生成：

- `data/course_dataset_n6_r5_c2-3-4-5-6-7_cand24_valid2_seed42.json`

如果想一次生成所有场景，也可以用同样的尺寸设置：

```bash
python data_generation/generate.py --all-domains --num-instances 1 --rows 5 --cols 2 3 4 5 6 7 --candidates-per-slot 24 --valid-options 2 --seed 42
```

同一个 domain 的多个尺寸组合会被整合到同一个 JSON 文件里，顶层结构仍然是 `domain`、`num_instances`、`instances`。不同尺寸组合的实例会一起放在 `instances` 中，每个实例自己的 `meta` 里保留对应的 `rows` 和 `cols`。

生成时会自动验证；如果生成出的实例没有真解、某个 slot 候选数不对、或者有效候选数不在目标范围内，程序会重新采样，直到成功或超过最大重试次数。

最终数据文件的结构类似：

```json
{
  "domain": "course",
  "num_instances": 2,
  "instances": [
    {
      "instance_id": "course_r5_c2_000",
      "domain": "course",
      "meta": {
        "rows": 5,
        "cols": 2
      },
      "global_constraints": {},
      "item_pool": {},
      "truth_solution": [],
      "row_constraints": [],
      "col_constraints": [],
      "slots": []
    },
    {
      "instance_id": "course_r5_c3_000",
      "domain": "course",
      "meta": {
        "rows": 5,
        "cols": 3
      },
      "global_constraints": {},
      "item_pool": {},
      "truth_solution": [],
      "row_constraints": [],
      "col_constraints": [],
      "slots": []
    }
  ]
}
```

其中：

- 顶层的 `num_instances` 是这个文件里总共包含的实例数
- `instances` 里可以同时包含同一个 domain 下的多个不同矩阵大小
- 每个实例自己的 `meta` 会单独记录该实例对应的 `rows` 和 `cols`
- `item_pool` 是一个 `item_id -> item_info` 的字典
- `truth_solution` 是完整真值网格
- `row_constraints` 是每一行的约束
- `col_constraints` 是每一列的约束
- `global_constraints` 是整张表的全局约束
- `slots` 保存每个格子的局部约束、真值 id、候选 id 列表，以及便于调试的 `valid_candidate_ids`

## Benchmark Eval

评测入口在 `main.py`，可以直接用命令行运行。

例如，使用本地 vLLM 对 `course` 领域做一次最小评测：

```bash
OPENAI_API_KEY=EMPTY python main.py \
  --model openai/Qwen/Qwen3-8B \
  --domain course \
  --agent-params '{"api_base":"http://localhost:8001/v1","temperature":0.6}' \
  --hidden-rates 0.1 \
  --max-steps 200 \
  --tool-failure-rates "[0.0]" \
  --num-trials 1 \
  --save-path results/ \
  --seed 42
```

这条命令对应 `debug.py` 里的示例配置，含义是：

- 使用模型 `openai/Qwen/Qwen3-8B`
- 只评测 `course` 领域
- 连接本地 `http://localhost:8001/v1`
- 只跑 `hidden_rate=0.1`
- 每个 task 最多执行 `200` 步
- tool 失败率为 `0.0`
- 每个实例只跑 `1` 次
- 结果保存到 `results/`

如果想一次评测全部领域，可以这样运行：

```bash
OPENAI_API_KEY=EMPTY python main.py \
  --model openai/Qwen/Qwen3-8B \
  --domain all \
  --agent-params '{"api_base":"http://localhost:8001/v1","temperature":0.6}' \
  --hidden-rates 0.1 0.3 0.5 0.7 0.9 \
  --tool-failure-rates "[0.0]" \
  --num-trials 1 \
  --save-path results/ \
  --seed 42
```

结果会按如下结构保存：

- `results/<model-last-name>/<instance_id>/hidden-<hidden_rate>_fail-<tool_failure_rate>_trial-<trial_index>.json`