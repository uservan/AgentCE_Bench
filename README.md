# cached_agent_benchmark

## Dataset Generation

数据生成器在 `data_generation/generate.py`，生成出的 JSON 默认保存在项目根目录下的 `data/`。

单个领域的生成例子：

```bash
python data_generation/generate.py --domain course --rows 5 --cols 5 --hidden-slots 1 3 5 7 9 13 17 --branch-budget 0 2 4 6 8 10 --candidates-per-slot 15 --max-retries 160 --candidate-resample-retries 12 --seed 42
```

这条命令表示：

- 生成 `course` 场景的数据
- `rows` 固定为 `5`
- `cols` 固定为 `5`
- `hidden_slots` 依次取 `1 3 5 7 9 13 17`
- `branch_budget` 依次取 `0 2 4 6 8 10`
- 因此会按 `hidden_slots x branch_budget` 的组合生成实例
- 输出到项目根目录下的 `data/`
- 每个 hidden slot 默认显式存 `15` 个候选 item id；如果某个 budget 需要更多候选，生成器会自动放大该实例实际使用的 `candidates_per_slot`
- `max_retries` 和 `candidate_resample_retries` 也可以通过命令行传入；如果不传，则分别默认使用 `160` 和 `12`
- 每个实例里只会隐藏指定数量的 slot，非 hidden slot 保持固定，不再生成无用候选
- 约束只保留 `slot_constraints` 和 `global_constraints`，不再生成 `row_constraints` / `col_constraints`
- 使用随机种子 `42`

当前生成逻辑是：

- 先生成完整 `truth_solution`
- 只为 hidden slots 生成 `slot_constraints`
- 为整张表生成 `global_constraints`
- `global_constraints` 会尽量覆盖全部全局属性；`slot_constraints` 默认每个 hidden slot 覆盖 2 个属性，并尽量让同一实例里所有 hidden slots 联合起来覆盖完全部 slot 属性；如果 hidden slots 太少，个别 slot 会覆盖超过 2 个属性来补齐
- 随机选出部分 hidden slots 作为分支 slot，并把 `branch_budget` 拆成若干个正整数分配给这些分支 slot
- `branch_budget_allocations` 的规则是：如果只有 1 个分支 slot，就直接分到 `[branch_budget]`；如果有 2 个分支 slot，只要求拆成两个正整数；只有当分支 slot 数不少于 3 时，才要求每个分配值都不超过 `branch_budget // 2`
- 逐个分支 slot 构造 decoy：每个 decoy 必须满足本 slot 的 `slot_constraints`，但在和 truth / 更早分支 slot 的 decoy 组合时，一定破坏 `global_constraints`
- 最后再为每个 hidden slot 补充一批 filter 候选，这些候选会直接违反该 slot 的 `slot_constraints`

这会生成类似这样的文件名：

- `data/course_dataset_r5_c5_h1-3-5-7-9-13-17_cand15_budget0-2-4-6-8-10_seed42.json`

如果想一次生成所有场景，也可以用同样的尺寸设置：

```bash
python data_generation/generate.py --all-domains --rows 5 --cols 5 --hidden-slots 1 3 5 7 9 13 17 --branch-budget 0 2 4 6 8 10 --candidates-per-slot 15 --max-retries 160 --candidate-resample-retries 12 --seed 42
```

同一个 domain 的多个组合会被整合到同一个 JSON 文件里，顶层结构仍然是 `domain`、`num_instances`、`instances`。同一个固定尺寸下，不同隐藏设定的实例会一起放在 `instances` 中，每个实例自己的 `meta` 里保留对应的 `rows`、`cols`、`hidden_slots`、`branch_budget` 和 `candidates_per_slot`。

生成时会自动验证；如果生成出的实例不满足 truth 的 slot/global 约束、hidden slot 候选数不对、或者 decoy 没有满足一阶/二阶/三阶等多阶全局失效保证，程序会重新采样，直到成功或超过最大重试次数。若最终失败，会直接抛异常并在终端打印当前生成条件与失败原因。

最终数据文件的结构类似：

```json
{
  "domain": "course",
  "num_instances": 2,
  "rows": 5,
  "cols": 5,
  "hidden_slots": [1, 3],
  "branch_budget": [0, 2, 4, 6, 8],
  "candidates_per_slot": 15,
  "instances": [
    {
      "instance_id": "course_r5_c5_h1_b0",
      "domain": "course",
      "meta": {
        "rows": 5,
        "cols": 5,
        "hidden_slots": 1,
        "branch_budget": 0,
        "branch_slot_count": 0,
        "branch_budget_allocations": [],
        "candidates_per_slot": 15
      },
      "global_constraints": {},
      "item_pool": {},
      "truth_solution": [],
      "partial_solution": [],
      "hidden_slots": [],
      "slots": [
        {
          "row": 0,
          "col": 1,
          "truth_id": "C013",
          "is_hidden": true,
          "slot_constraints": {
            "row": 0,
            "col": 1,
            "active_rule_names": ["max_difficulty", "min_credits"],
            "max_difficulty": 3,
            "min_credits": 2
          },
          "candidate_ids": ["C013", "C084", "C096"],
          "decoy_ids": [],
          "filter_candidate_ids": ["C084", "C096"],
          "is_branch_slot": false,
          "branch_rank": null,
          "allocated_budget": 0
        }
      ]
    },
    {
      "instance_id": "course_r5_c5_h3_b4",
      "domain": "course",
      "meta": {
        "rows": 5,
        "cols": 5,
        "hidden_slots": 3,
        "branch_budget": 4,
        "branch_slot_count": 2,
        "branch_budget_allocations": [3, 1],
        "candidates_per_slot": 15
      },
      "global_constraints": {},
      "item_pool": {},
      "truth_solution": [],
      "partial_solution": [],
      "hidden_slots": [],
      "slots": []
    }
  ]
}
```

其中：

- 顶层的 `num_instances` 是这个文件里总共包含的实例数
- `instances` 里可以同时包含同一个 domain 下的多个不同隐藏配置
- 每个实例自己的 `meta` 会单独记录该实例对应的 `rows`、`cols`、`hidden_slots`、`branch_budget`、`branch_slot_count`、`branch_budget_allocations` 和实际使用的 `candidates_per_slot`
- `item_pool` 是一个 `item_id -> item_info` 的字典
- `truth_solution` 是完整真值网格
- `partial_solution` 是把 hidden slots 置为 `null` 之后给 agent 的初始网格
- `global_constraints` 是整张表的全局约束
- `hidden_slots` 只记录哪些位置被隐藏
- `slots` 只保存 hidden slots 的信息，其中会带 `slot_constraints`、`candidate_ids`、`decoy_ids`、`filter_candidate_ids`
- `decoy_ids` 表示满足本 slot 约束、但会按 branch-budget 设计去破坏全局约束的候选
- `filter_candidate_ids` 表示直接不满足本 slot 约束的候选

## Benchmark Eval

评测入口在 `main.py`，可以直接用命令行运行。

例如，使用本地 vLLM 对 `course` 领域做一次最小评测：

```bash
OPENAI_API_KEY=EMPTY python main.py \
  --model openai/Qwen/Qwen3-8B \
  --domain course \
  --agent-params '{"api_base":"http://localhost:8001/v1","temperature":0.6}' \
  --max-steps 200 \
  --max-query-ids 5 \
  --max-query-fields 6 \
  --tool-failure-rates "[0.0]" \
  --num-trials 1 \
  --save-path results/ \
  --seed 42
```

这条命令对应 `debug.py` 里的示例配置，含义是：

- 使用模型 `openai/Qwen/Qwen3-8B`
- 只评测 `course` 领域
- 连接本地 `http://localhost:8001/v1`
- 每个 task 最多执行 `200` 步
- 多 item 属性查询工具一次最多查询 `5` 个 id、最多查询 `6` 个属性
- `--hidden-slots` 和 `--branch-budget` 为白名单列表，不传时表示不过滤；传入时只跑对应值在列表内的数据集（如 `--hidden-slots 5` 只跑 hidden_slots=5，`--hidden-slots 1 3 5` 跑 hidden_slots 为 1/3/5 的数据集）
- tool 失败率为 `0.0`
- 每个实例只跑 `1` 次
- 结果保存到 `results/`

如果想一次评测全部领域，可以这样运行：

```bash
OPENAI_API_KEY=EMPTY python main.py \
  --model openai/Qwen/Qwen3-8B \
  --domain all \
  --agent-params '{"api_base":"http://localhost:8001/v1","temperature":0.6}' \
  --max-query-ids 5 \
  --max-query-fields 6 \
  --tool-failure-rates "[0.0]" \
  --num-trials 1 \
  --save-path results/ \
  --seed 42
```

如果只想测试指定 hidden_slots / branch_budget 的数据集，可传入白名单列表：

```bash
# 只跑 hidden_slots=5 且 branch_budget=4 的数据集
OPENAI_API_KEY=EMPTY python main.py \
  --model openai/Qwen/Qwen3-8B \
  --domain course \
  --agent-params '{"api_base":"http://localhost:8001/v1","temperature":0.6}' \
  --max-query-ids 5 \
  --max-query-fields 6 \
  --hidden-slots 5 \
  --branch-budget 4 \
  --tool-failure-rates "[0.0]" \
  --num-trials 1 \
  --save-path results/ \
  --seed 42

# 跑 hidden_slots 为 1/3/5、branch_budget 为 0/2/4 的数据集
OPENAI_API_KEY=EMPTY python main.py \
  --domain course \
  --hidden-slots 1 3 5 \
  --branch-budget 0 2 4 \
  ...
```

结果会按如下结构保存：

- `results/<model-last-name>/<instance_id>_ids<max_query_ids>_fields<max_query_fields>/fail-<tool_failure_rate>_trial-<trial_index>.json`

