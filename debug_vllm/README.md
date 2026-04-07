# Debug with vLLM


## Step 1: Start the vLLM Server

### （1）Download the Singularity Image

`run_agent_image.sh` runs the vLLM container via Singularity. The expected image path is:

```
/scratch/pioneer/jobs/user/save/images/vllm_0.17.1.sif
```

If the file does not exist, pull and convert it from Docker Hub first:

**1. Create the image directory**

```bash
IMAGE_DIR=/scratch/pioneer/jobs/user/save/images
mkdir -p $IMAGE_DIR
```

**2. Pull the image and convert to .sif**

```bash
singularity pull $IMAGE_DIR/vllm_0.17.1.sif docker://vllm/vllm-openai:v0.17.1
```

> `singularity pull` handles both pulling and conversion automatically. The resulting `.sif` file can be used directly.

### （2）Select a Model

Edit `run_agent_image.sh` and uncomment the line for the model you want to run:

```bash
# Small models (single GPU / 4 GPUs)
# AGENT_SCRIPT=$AGENT_DIR/qwen35_0.8b.sh
# AGENT_SCRIPT=$AGENT_DIR/qwen35_2b.sh
# AGENT_SCRIPT=$AGENT_DIR/qwen35_4b.sh
# AGENT_SCRIPT=$AGENT_DIR/qwen35_9b.sh
# AGENT_SCRIPT=$AGENT_DIR/qwen35_27b.sh
# AGENT_SCRIPT=$AGENT_DIR/qwen35_35b_a3b.sh
AGENT_SCRIPT=$AGENT_DIR/miro_thinker_1_7_mini.sh   # 31B (current default)

# Large models (8 GPUs)
# AGENT_SCRIPT=$AGENT_DIR/minimax_m21.sh            # 229B ~460GB
# AGENT_SCRIPT=$AGENT_DIR/qwen35_122b_a10b.sh       # 122B ~244GB
# AGENT_SCRIPT=$AGENT_DIR/deepseek_v3_2.sh          # 671B FP8
```

- Each model script lives under `agent/` (e.g. `agent/qwen35_9b.sh`) and starts `vllm serve` inside the container, listening on the corresponding port (see `config.py`).

- To add a custom model, create a new `.sh` script in `agent/` based on an existing one, then add the corresponding key and value to the `MODELS` dict in `config.py`.

### （3）Start the Server

```bash
bash run_agent_image.sh
```

The server runs in the background. Logs are written to:
- `vllm_server.log` — Singularity launch log
- `log/<model_name>-<port>.log` — vLLM server detailed log

Wait until `Application startup complete` appears in the log before proceeding.

---

## Step 2: Run Evaluation

### Edit debug.py

Open `debug.py` and set `cfg` to the model key you want to test (must match the model started in Step 1):

```python
cfg = MODELS["qwen35_9b"]   # change to the target key
main(
    model=cfg["model"],
    agent_params=cfg["agent_params"],
    domain=["course"],        # specify domain, or "all"
    data_dir="data/5x7",
    max_steps=2000,
    max_query_ids=5,
    max_query_fields=5,
    tool_failure_rates=[0.0, 0.1, 0.3],
    num_trials=1,
    save_path="/scratch/pioneer/jobs/user/save/cached_results2/",
    overwrite_results=False,
    check_include_reason=False,
    global_check_alpha=-1,
    seed=42,
    hidden_slots=None,   # None means no filter
    branch_budget=None,
    max_workers=64,
)
```

### (Optional) Example: Running Specific Hidden Slots and Branch Budgets

To run evaluation only on instances with specific hidden slots (e.g., 1 and 3) and branch budgets (e.g., 0 and 2), modify the `hidden_slots` and `branch_budget` parameters:

```python
cfg = MODELS["qwen35_9b"]   # change to the target key
main(
    model=cfg["model"],
    agent_params=cfg["agent_params"],
    domain=["course"],        # specify domain, or "all"
    data_dir="data/5x7",
    max_steps=2000,
    max_query_ids=5,
    max_query_fields=5,
    tool_failure_rates=[0.0, 0.1, 0.3],
    num_trials=1,
    save_path="/scratch/pioneer/jobs/user/save/cached_results2/",
    overwrite_results=False,
    check_include_reason=False,
    global_check_alpha=-1,
    seed=42,
    hidden_slots=[1, 3],   # only run instances with hidden slots 1 and 3
    branch_budget=[0, 2],  # only run instances with branch budgets 0 and 2
    max_workers=64,
)
```

Commonly changed parameters:

| Parameter | Description |
|-----------|-------------|
| `model` / `agent_params` | Set via `cfg = MODELS["<key>"]`; must match the model started in Step 1 |
| `domain` | List of domains to evaluate, e.g. `["course", "meal"]`, or `"all"` |
| `data_dir` | Path to the dataset directory, e.g. `"data/5x5"`, `"data/5x7"`, `"data/5x10"` |
| `max_steps` | Maximum agent steps per task |
| `tool_failure_rates` | List of failure rates to sweep, e.g. `[0.0, 0.1, 0.3, 0.5]` |
| `save_path` | Directory to save evaluation results |
| `max_workers` | Number of tasks to run in parallel |

For all other parameters, run `python main.py --help` to see descriptions.

### Available Model Keys (from config.py)

| Key | Model | Port |
|-----|-------|------|
| `qwen35_0.8b` | Qwen3.5-0.8B | 8003 |
| `qwen35_2b` | Qwen3.5-2B | 8001 |
| `qwen35_4b` | Qwen3.5-4B | 8002 |
| `qwen35_9b` | Qwen3.5-9B | 8000 |
| `qwen35_27b` | Qwen3.5-27B | 8004 |
| `qwen35_35b_a3b` | Qwen3.5-35B-A3B | 8006 |
| `qwen35_122b_a10b` | Qwen3.5-122B-A10B | 8011 |
| `qwen35_397b_a17b` | Qwen3.5-397B-A17B | 8012 |
| `minimax_m2` | MiniMax-M2 | 8014 |
| `minimax_m21` | MiniMax-M2.1 | 8005 |
| `minimax_m25` | MiniMax-M2.5 | 8005 |
| `miro_thinker_1_7_mini` | MiroThinker-1.7-mini | 8013 |
| `miro_thinker_1_7` | MiroThinker-1.7 | 8010 |
| `deepseek_v3_2` | DeepSeek-V3.2 | 8007 |
| `glm47` | GLM-4.7-FP8 | 8015 |
| `glm5` | GLM-5-FP8 | 8009 |
| `kimi_k2_5` | Kimi-K2.5 | 8008 |

### Run in Background (Recommended)

```bash
nohup python debug_vllm2/debug.py > debug_vllm2/debug_log/qwen35_9b.log 2>&1 &
disown
```

Logs are written to `debug_log/`. Use `tail -f` to follow in real time:

```bash
tail -f debug_vllm2/debug_log/qwen35_9b.log
```

---

## Results

Evaluation results are saved to the directory specified by `save_path`, with the following path format:

```
<save_path>/<model-last-name>/<instance_id>_ids<max_query_ids>_fields<max_query_fields>/fail-<tool_failure_rate>_trial-<trial_index>.json
```
