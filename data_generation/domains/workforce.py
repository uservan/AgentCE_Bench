import random


DEPARTMENTS = [
    "support",
    "sales",
    "operations",
    "security",
    "logistics",
    "maintenance",
]

SPEC = {
    "id_key": "worker_id",
    "slot_rules": [
        {"name": "min_skill", "attr": "skill", "kind": "min", "candidates": [1, 2, 3, 4]},
        {"name": "max_cost", "attr": "hourly_cost", "kind": "max", "candidates": [45, 60, 75, 90, 100]},
        {"name": "min_experience", "attr": "experience", "kind": "min", "candidates": [1, 4, 8, 12]},
    ],
    "row_rules": [
        {"name": "total_cost_max", "type": "sum_max", "attr": "hourly_cost", "slack": 45, "per_item_cap": 100},
        {"name": "total_skill_min", "type": "sum_min", "attr": "skill", "slack": 3, "floor": 0},
        {"name": "total_experience_min", "type": "sum_min", "attr": "experience", "slack": 12, "floor": 0},
        {"name": "same_department_row_max", "type": "repeat_max", "attr": "department"},
        {"name": "total_reliability_min", "type": "sum_min", "attr": "reliability", "slack": 4, "floor": 1},
        {"name": "total_overtime_min", "type": "sum_min", "attr": "overtime_capacity", "slack": 8, "floor": 0},
    ],
    "col_rules": [
        {"name": "total_cost_max", "type": "sum_max", "attr": "hourly_cost", "slack": 45, "per_item_cap": 100},
        {"name": "total_skill_min", "type": "sum_min", "attr": "skill", "slack": 3, "floor": 0},
        {"name": "total_experience_min", "type": "sum_min", "attr": "experience", "slack": 12, "floor": 0},
        {"name": "same_department_col_max", "type": "repeat_max", "attr": "department"},
        {"name": "total_reliability_min", "type": "sum_min", "attr": "reliability", "slack": 4, "floor": 1},
        {"name": "total_overtime_min", "type": "sum_min", "attr": "overtime_capacity", "slack": 8, "floor": 0},
    ],
    "global_rules": [
        {"name": "total_cost_max", "type": "sum_max", "attr": "hourly_cost", "slack": 160, "per_item_cap": 100},
        {"name": "total_skill_min", "type": "sum_min", "attr": "skill", "slack": 15, "floor": 0},
        {"name": "senior_shift_min", "type": "count_min_threshold", "attr": "experience", "threshold": 12, "slack": 2},
        {"name": "same_department_week_max", "type": "repeat_max", "attr": "department"},
        {"name": "total_reliability_min", "type": "sum_min", "attr": "reliability", "slack": 18, "floor": 1},
        {"name": "total_overtime_min", "type": "sum_min", "attr": "overtime_capacity", "slack": 40, "floor": 0},
    ],
    "min_slot_matches": 6,
}


def build_item(index):
    return {
        "worker_id": f"W{index + 1:03d}",
        "name": f"Worker {100 + index}",
        "skill": random.randint(1, 5),
        "hourly_cost": random.randint(20, 100),
        "experience": random.randint(1, 20),
        "department": random.choice(DEPARTMENTS),
        "reliability": random.randint(1, 5),
        "overtime_capacity": random.randint(0, 10),
    }
