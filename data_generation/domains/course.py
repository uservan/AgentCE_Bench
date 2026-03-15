import random


CATEGORIES = ["math", "cs", "core", "elective", "lab", "seminar"]

TEACHERS = [
    "Alice Johnson",
    "Bob Smith",
    "Carol Davis",
    "Daniel Lee",
    "Eva Brown",
    "Frank Wilson",
    "Grace Taylor",
    "Henry Moore",
    "Ivy Thomas",
    "Jack Martin",
    "Karen White",
    "Leo Harris",
    "Mia Clark",
    "Noah Walker",
    "Olivia Hall",
    "Peter Young",
]

NAME_PARTS = {
    "math": ["Algebra", "Calculus", "Geometry", "Statistics", "Optimization"],
    "cs": ["Algorithms", "Systems", "Databases", "Networks", "AI"],
    "core": ["Foundations", "Theory", "Practice", "Methods", "Analysis"],
    "elective": ["Design", "Media", "Business", "Writing", "Innovation"],
    "lab": ["Experiments", "Studio", "Workshop", "Simulation", "Prototyping"],
    "seminar": ["Topics", "Discussion", "Research", "Colloquium", "Perspectives"],
}

SPEC = {
    "id_key": "course_id",
    "slot_rules": [
        {"name": "max_difficulty", "attr": "difficulty", "kind": "max", "candidates": [3, 4, 5]},
        {"name": "min_credits", "attr": "credits", "kind": "min", "candidates": [1, 2, 3]},
        {"name": "max_price", "attr": "price", "kind": "max", "candidates": [280, 340, 400, 460, 500]},
    ],
    "row_rules": [
        {"name": "total_credits_min", "type": "sum_min", "attr": "credits", "slack": 2, "floor": 1},
        {"name": "total_price_max", "type": "sum_max", "attr": "price", "slack": 300, "per_item_cap": 500},
        {"name": "max_difficulty", "type": "max_cap", "attr": "difficulty", "cap": 5},
        {"name": "same_teacher_row_max", "type": "repeat_max", "attr": "teacher"},
        {"name": "same_category_row_max", "type": "repeat_max", "attr": "category"},
        {"name": "total_workload_max", "type": "sum_max", "attr": "workload", "slack": 6, "per_item_cap": 8},
    ],
    "col_rules": [
        {"name": "total_credits_min", "type": "sum_min", "attr": "credits", "slack": 2, "floor": 1},
        {"name": "total_price_max", "type": "sum_max", "attr": "price", "slack": 300, "per_item_cap": 500},
        {"name": "same_teacher_col_max", "type": "repeat_max", "attr": "teacher"},
        {"name": "max_workload", "type": "max_cap", "attr": "workload", "cap": 8},
        {"name": "same_category_col_max", "type": "repeat_max", "attr": "category"},
    ],
    "global_rules": [
        {"name": "total_credits_min", "type": "sum_min", "attr": "credits", "slack": 8, "floor": 1},
        {"name": "total_price_max", "type": "sum_max", "attr": "price", "slack": 1500, "per_item_cap": 500},
        {"name": "same_teacher_week_max", "type": "repeat_max", "attr": "teacher"},
        {"name": "same_category_week_max", "type": "repeat_max", "attr": "category"},
        {"name": "total_workload_max", "type": "sum_max", "attr": "workload", "slack": 20, "per_item_cap": 8},
    ],
    "min_slot_matches": 6,
}


def build_item(index):
    category = random.choice(CATEGORIES)
    name_part = random.choice(NAME_PARTS[category])
    return {
        "course_id": f"C{index + 1:03d}",
        "name": f"{name_part} {100 + index}",
        "category": category,
        "difficulty": random.randint(1, 5),
        "credits": random.randint(1, 4),
        "price": random.randint(100, 500),
        "teacher": random.choice(TEACHERS),
        "workload": random.randint(1, 8),
    }
