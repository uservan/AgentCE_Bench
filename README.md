# cached_agent_benchmark

## Dataset Generation

数据生成器在 `data_generation/generate.py`，生成出的 JSON 默认保存在项目根目录下的 `data/`。

单个领域的生成例子：

```bash
python data_generation/generate.py --domain course --rows 5 --cols 7 --hidden-slots 1 5 7 11 15 21 --branch-budget 0 2 4 8 10 15 19 21 25 --candidates-per-slot 25 --max-retries 250 --candidate-resample-retries 20 --open-valid-preference-tries 50 100 150 --seed 42 --max-workers 8
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
- `--max-workers` 控制并行生成 `(hidden_slot, branch_budget)` 组合的线程数，默认为 `1`（串行）；设为大于 `1` 时并行生成，注意并行模式下随机状态不保证与串行完全一致
- `open_valid_preference_tries` 默认是 `30 50 70`，表示 decoy 在 `future hidden=None` 场景下的三级偏好放松阈值：前 `30` 次优先满足“任意历史 truth/decoy 组合 + 当前 decoy”有效；前 `50` 次优先满足“前缀 truth + 后缀 decoy 组合 + 当前 decoy”有效；前 `70` 次优先满足“全历史 truth + 当前 decoy”有效；超过后只保留最初的硬约束
- 每个实例里只会隐藏指定数量的 slot，非 hidden slot 保持固定，不再生成无用候选
- 约束只保留 `slot_constraints` 和 `global_constraints`，不再生成 `row_constraints` / `col_constraints`
- 使用随机种子 `42`

当前生成逻辑可以分成两部分：先确定 `truth_solution` 和约束，再为每个 hidden slot 生成候选。

### 整体流程

1. 先生成完整的 `truth_solution`，也就是最终正确答案网格。
2. 在完整真值上生成 `global_constraints`，这些约束描述整张表整体必须满足的条件。
3. 只对 hidden slots 生成 `slot_constraints`，不再为可见位置生成无用候选。
4. `slot_constraints` 默认每个 hidden slot 覆盖 2 个属性，并尽量让所有 hidden slots 联合起来覆盖完整的 slot 属性空间；如果 hidden slots 太少，个别 slot 会覆盖超过 2 个属性来补齐。
5. 从 hidden slots 中随机选出一部分作为 branch slots，再把 `branch_budget` 拆成若干个正整数，分配到这些 branch slots 上。
6. 对每个 hidden slot 生成 `candidate_ids`，其中包括正确答案 `truth_id`、用于制造全局误导的 `decoy_ids`，以及直接违反本地 slot 约束的 `filter_candidate_ids`。

`branch_budget_allocations` 的规则是：

- 如果只有 1 个 branch slot，就直接分成 `[branch_budget]`
- 如果有 2 个 branch slots，只要求拆成两个正整数
- 只有当 branch slot 数不少于 3 时，才额外要求每个分配值都不超过 `branch_budget // 2`

### Decoy 设计

`decoy` 的目标不是“本地就错”，而是“本地看起来对，但放到全局里会错”。因此每个 `decoy` 都必须先满足当前 slot 的 `slot_constraints`，否则它就应该被归到 `filter_candidate_ids`，而不是 `decoy_ids`。

生成某个 branch slot 的 `decoy` 时，系统会把“之前的 branch 决策”看成历史，把“后面的 hidden slots”看成未来，然后同时考虑两类场景：

1. `future hidden = truth`
2. `future hidden = None`

其中第一类是硬约束，第二类是偏好约束。

#### 1. 硬约束：必须让完整填写后失败

每个 `decoy` 必须满足下面这条多阶段保证：

- `历史 truth/decoy 组合 + 当前 decoy + 未来 hidden 全部取 truth -> global invalid`

这里的“历史 truth/decoy 组合”指的是：之前所有 branch slots 可以保持 truth，也可以替换成它们各自已经生成出的 decoy，系统会枚举这些历史组合。只有当当前候选在这些组合下、并且未来 hidden slots 都填回 truth 时，都会触发至少一个 global constraint 违规，这个候选才算合格的 `decoy`。

这条规则保证了：agent 在前面即使已经走错过一次或多次，只要当前再选到这个 `decoy`，当整张表最后被补全时，依然会在全局上失败。

#### 2. 三级偏好：尽量让未填未来时仍然看起来合法

除了上面的硬约束，生成器还会尽量满足 open-prefix 偏好，也就是把未来 hidden slots 暂时留空为 `None` 时，当前 `decoy` 不要过早暴露全局违规。

默认参数 `--open-valid-preference-tries 30 50 70` 表示 3 个放松阶段：

1. 前 `30` 次，优先满足：
   `任意历史 truth/decoy 组合 + 当前 decoy + 未来 hidden=None -> global valid`
2. 第 `31` 到 `50` 次，放松为只要求：
   `前缀 truth + 后缀 decoy 组合 + 当前 decoy + 未来 hidden=None -> global valid`
3. 第 `51` 到 `70` 次，再放松为只要求：
   `全历史 truth + 当前 decoy + 未来 hidden=None -> global valid`
4. 超过 `70` 次后，不再强求 `future hidden=None` 这类偏好，只保留前面的硬约束

这 3 级偏好的直觉是：

- 第 1 级最强，要求几乎所有历史 truth/decoy 混合路径下，当前 `decoy` 在“未来未填完”时都暂时看不出全局违规
- 第 2 级稍弱，只覆盖一种更接近“沿路径逐步走错”的历史模式，也就是前面一段保持 truth，后面连续若干个 branch slots 已经选成 decoy
- 第 3 级最弱，只要求“如果前面都还是 truth”，当前 `decoy` 在未来未填完时仍然 global valid

因此，越早找到候选，`decoy` 的“迷惑性”越强；如果前面的偏好太严格导致难以采样，系统就逐步放松，避免数据完全生成不出来。

#### 3. 为什么 `future=None` 时只检查部分 global 约束

当未来 hidden slots 还是 `None` 时，生成器只会强检查那些“填得越多越容易违规”的 global 约束，比如上界类约束。对一些下界类约束，例如至少多少学分、至少多少个满足条件的 item，这时不会把“暂时没填够”当成失败，因为这些约束在未来补全 truth 后仍然可能满足。

所以这里的 `global valid` 更准确地说，是“在当前前缀下，没有提前暴露出确定性的 global violation”。

#### 4. 最后一个 branch slot 的特殊处理

如果当前 slot 是最后一个 branch slot，那么后面已经没有未来 branch 决策了。这种情况下，代码会跳过上面的三级 `future hidden=None` 偏好，不再强求它在 open-prefix 场景里继续显得合法，而只保留那条核心硬约束：

- `历史 truth/decoy 组合 + 当前 decoy + 未来 truth -> global invalid`

由于此时未来 branch 路径已经结束，这样做能显著减少无解或极慢采样的情况。

#### 5. Targeted Sampling

为了避免完全靠拒绝采样反复碰运气，生成器不会纯随机瞎试。它会先根据当前历史上下文和 `global_constraints` 预计算一批 target specs，再优先把候选往更可能满足“full truth 时违规、future=None 时暂时合法”的方向去引导。

通常它会优先利用上界类约束来构造 `decoy`，例如总 credit 不能超过多少、某个类别不能重复太多次。这类约束天然更适合做 branch decoy，因为：

- 当未来 hidden slots 都补成 truth 时，更容易超过上界，形成稳定的 global invalid
- 当未来 hidden slots 暂时是 `None` 时，总量通常会下降，又更容易保持暂时合法

#### 6. Filter 候选和 Decoy 的区别

- `truth_id`：当前 hidden slot 的正确答案
- `decoy_ids`：满足当前 slot 的本地约束，但会在合适的全局组合下触发 global violation
- `filter_candidate_ids`：直接不满足当前 slot 的本地约束，用来提供明显错误的干扰项

可以把它理解成：

- `filter` 是“本地就错”
- `decoy` 是“本地像对的，但全局会错”

这会生成类似这样的文件名：

- `data/course_dataset_r5_c5_h1-3-5-7-9-13-17_cand15_budget0-2-4-6-8-10_seed42.json`

如果想一次生成所有场景，也可以用同样的尺寸设置：

```bash
python data_generation/generate.py --all-domains --rows 5 --cols 5 --hidden-slots 1 3 5 7 9 13 17 --branch-budget 0 2 4 6 8 10 --candidates-per-slot 15 --max-retries 160 --candidate-resample-retries 12 --open-valid-preference-tries 30 50 70 --seed 42 --max-workers 36
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
- 默认 `check_include_reason=False`，即 `check_*_slot_constraints` 和 `check_*_global_constraints` 默认只返回 `is_valid`，不返回 `reason`；如果想返回原因，可加 `--check-include-reason`
- `--global-check-alpha` 默认是 `1`，用于限制全局约束检查次数，budget = `floor(alpha * hidden_slots)`
- alpha 难度可按下面理解：
- `0`：不允许调用 global check
- `0.5`：很严格
- `1`：默认值，大约每个 hidden slot 一次
- `2`：比较宽松
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

# 如果希望 check tool 额外返回 reason，可以显式打开
OPENAI_API_KEY=EMPTY python main.py \
  --model openai/Qwen/Qwen3-8B \
  --domain course \
  --agent-params '{"api_base":"http://localhost:8001/v1","temperature":0.6}' \
  --check-include-reason \
  --global-check-alpha 2 \
  --hidden-slots 5 \
  --branch-budget 4 \
  ...

# 跑 hidden_slots 为 1/3/5、branch_budget 为 0/2/4 的数据集
OPENAI_API_KEY=EMPTY python main.py \
  --domain course \
  --hidden-slots 1 3 5 \
  --branch-budget 0 2 4 \
  ...
```

结果会按如下结构保存：

- `results/<model-last-name>/<instance_id>_ids<max_query_ids>_fields<max_query_fields>/fail-<tool_failure_rate>_trial-<trial_index>.json`

