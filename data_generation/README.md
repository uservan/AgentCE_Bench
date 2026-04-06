# Data Generation

## 1. Commands

### Single Domain

```bash
python data_generation/generate.py \
  --domain course \
  --rows 5 --cols 7 \
  --hidden-slots 1 5 7 11 15 21 \
  --branch-budget 0 2 4 8 10 15 19 21 25 \
  --candidates-per-slot 25 \
  --max-retries 250 \
  --candidate-resample-retries 20 \
  --open-valid-preference-tries 50 100 150 \
  --seed 42 \
  --max-workers 8
```

Key parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--domain` | required | Domain name, or `--all-domains` for all. Available: `course` (course scheduling), `meal` (meal planning), `pc_build` (PC configuration), `shopping` (shopping list), `travel` (travel itinerary), `workforce` (staff scheduling) |
| `--rows` / `--cols` | required | Grid dimensions |
| `--hidden-slots` | required | List of hidden slot counts to generate |
| `--branch-budget` | required | List of branch budgets to generate |
| `--candidates-per-slot` | `15` | Number of candidate IDs per hidden slot (auto-expanded if budget requires more) |
| `--max-retries` | `160` | Max retries per instance |
| `--candidate-resample-retries` | `12` | Max resamples per candidate |
| `--open-valid-preference-tries` | `30 50 70` | Three-level preference relaxation thresholds for decoy open-prefix validity |
| `--seed` | — | Random seed |
| `--max-workers` | `1` | Parallel threads for `(hidden_slots, branch_budget)` combinations |

Instances are generated for every `hidden_slots × branch_budget` combination. Output files are saved to `data/` in the project root, e.g.:

```
data/course_dataset_r5_c5_h1-3-5-7-9-13-17_cand15_budget0-2-4-6-8-10_seed42.json
```

### All Domains

```bash
python data_generation/generate.py \
  --all-domains \
  --rows 5 --cols 5 \
  --hidden-slots 1 3 5 7 9 13 17 \
  --branch-budget 0 2 4 6 8 10 \
  --candidates-per-slot 15 \
  --max-retries 160 \
  --candidate-resample-retries 12 \
  --open-valid-preference-tries 30 50 70 \
  --seed 42 \
  --max-workers 36
```

---

## 2. Generation Process

Generation proceeds in two phases: first fix the truth solution and constraints, then generate candidates for each hidden slot.

### Phase 1: Truth & Constraints

1. **Generate `truth_solution`** — the complete correct answer grid.
2. **Generate `global_constraints`** — conditions the entire table must satisfy.
3. **Generate `slot_constraints`** — only for hidden slots (visible slots get no candidates). Each hidden slot covers ~2 attributes; if there are too few hidden slots, some slots cover more to span the full attribute space.
4. **Select branch slots** — randomly pick a subset of hidden slots as branch slots, then split `branch_budget` into positive integers and allocate them across the branch slots.
   - 1 branch slot → allocate `[branch_budget]`
   - 2 branch slots → split into any two positive integers
   - 3+ branch slots → each allocation ≤ `branch_budget // 2`

### Phase 2: Candidate Generation

For each hidden slot, generate three kinds of candidates:

| Type | Description |
|------|-------------|
| `truth_id` | The correct answer for this slot |
| `decoy_ids` | Satisfies local slot constraints, but triggers a global constraint violation in the right global context |
| `filter_candidate_ids` | Directly violates local slot constraints (obviously wrong distractors) |

#### Decoy Design

A decoy's goal is to *look locally correct but fail globally*. Two conditions must hold:

**Hard constraint (required):**
Every decoy must ensure that for all combinations of previous branch slots (keeping truth or substituting their already-generated decoys), placing this decoy here and filling remaining hidden slots with their truth values results in a global constraint violation.

**Open-prefix preference (best-effort, 3 levels):**
The generator also tries to ensure the decoy does not prematurely reveal a global violation when future slots are still unfilled (`None`). The `--open-valid-preference-tries` thresholds control how long each level is attempted before relaxing:

1. **Level 1** (first N₁ tries): All history truth/decoy combinations + current decoy + future=None → globally valid
2. **Level 2** (N₁–N₂ tries): Prefix-truth + suffix-decoy history + current decoy + future=None → globally valid
3. **Level 3** (N₂–N₃ tries): All-truth history + current decoy + future=None → globally valid
4. **After N₃**: Only the hard constraint is enforced

The last branch slot skips the open-prefix preference entirely (no future branch decisions remain).

#### Targeted Sampling

Rather than pure rejection sampling, the generator pre-computes target specs from the current history and `global_constraints` to guide candidate generation toward items more likely to satisfy both the hard constraint and the open-prefix preference. Upper-bound constraints (e.g. total credits ≤ X, category count ≤ Y) are preferred targets because:
- With future slots filled as truth, totals tend to exceed the upper bound → stable global failure
- With future slots as `None`, totals are lower → temporarily valid

#### Why only partial global checks when future=None

When future hidden slots are `None`, only constraints that become *harder to satisfy as more slots are filled* (upper-bound style) are strictly checked. Lower-bound constraints (e.g. "at least N credits") are not treated as failures, since they may still be satisfied once the remaining slots are filled with truth values.

---

## 3. Output Format

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
        "rows": 5, "cols": 5,
        "hidden_slots": 1, "branch_budget": 0,
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
          "row": 0, "col": 1,
          "truth_id": "C013",
          "is_hidden": true,
          "slot_constraints": { "active_rule_names": ["max_difficulty", "min_credits"], "max_difficulty": 3, "min_credits": 2 },
          "candidate_ids": ["C013", "C084", "C096"],
          "decoy_ids": [],
          "filter_candidate_ids": ["C084", "C096"],
          "is_branch_slot": false,
          "branch_rank": null,
          "allocated_budget": 0
        }
      ]
    }
  ]
}
```

Top-level fields:
- `num_instances`: total number of instances in this file
- `instances`: can contain multiple instances with different hidden/budget configurations from the same domain; each instance's `meta` records its own `rows`, `cols`, `hidden_slots`, `branch_budget`, `branch_slot_count`, `branch_budget_allocations`, and actual `candidates_per_slot`

Per-instance fields:
- `global_constraints`: conditions the entire table must satisfy
- `item_pool`: `item_id → item_info` dict
- `truth_solution`: complete correct grid
- `partial_solution`: grid with hidden slots set to `null` (input to agent)
- `hidden_slots`: records which positions are hidden
- `slots`: only hidden slots, each with `slot_constraints`, `candidate_ids`, `decoy_ids`, `filter_candidate_ids`
- `decoy_ids`: candidates that satisfy local slot constraints but are designed to trigger global constraint violations
- `filter_candidate_ids`: candidates that directly violate local slot constraints (obviously wrong distractors)

Auto-validation runs after generation; if any instance fails truth/constraint/decoy checks, it is resampled up to `max_retries` times before raising an exception.
