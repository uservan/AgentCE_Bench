import random


CATEGORIES = ["museum", "outdoor", "food", "show", "landmark", "market"]
LOCATIONS = [
    "Downtown",
    "Old Town",
    "Riverside",
    "Harbor",
    "Hill District",
    "City Center",
    "Museum Quarter",
    "Garden Area",
]
NAME_PARTS = {
    "museum": ["Art Museum", "History Hall", "Science Center", "Gallery Tour"],
    "outdoor": ["Park Walk", "Boat Ride", "Mountain Trail", "Beach Visit"],
    "food": ["Street Food", "Tasting Tour", "Cafe Visit", "Dinner Cruise"],
    "show": ["Jazz Night", "Theater", "Dance Show", "Concert"],
    "landmark": ["Tower Visit", "Bridge Tour", "Castle Stop", "Monument Walk"],
    "market": ["Night Market", "Craft Market", "Farmers Market", "Bazaar"],
}

SPEC = {
    "id_key": "activity_id",
    "slot_rules": [
        {"name": "max_cost", "attr": "cost", "kind": "max", "candidates": [60, 90, 120, 160, 200]},
        {"name": "max_duration", "attr": "duration", "kind": "max", "candidates": [2, 3, 4, 5, 6]},
        {"name": "max_crowd", "attr": "crowd_level", "kind": "max", "candidates": [2, 3, 4, 5]},
    ],
    "row_rules": [
        {"name": "total_cost_max", "type": "sum_max", "attr": "cost", "slack": 120, "per_item_cap": 200},
        {"name": "total_duration_max", "type": "sum_max", "attr": "duration", "slack": 2, "per_item_cap": 6},
        {"name": "max_crowd", "type": "max_cap", "attr": "crowd_level", "cap": 5},
        {"name": "same_location_row_max", "type": "repeat_max", "attr": "location"},
        {"name": "same_category_row_max", "type": "repeat_max", "attr": "category"},
        {"name": "total_rating_min", "type": "sum_min", "attr": "rating", "slack": 3, "floor": 1},
    ],
    "col_rules": [
        {"name": "total_cost_max", "type": "sum_max", "attr": "cost", "slack": 120, "per_item_cap": 200},
        {"name": "total_duration_max", "type": "sum_max", "attr": "duration", "slack": 2, "per_item_cap": 6},
        {"name": "max_crowd", "type": "max_cap", "attr": "crowd_level", "cap": 5},
        {"name": "same_location_col_max", "type": "repeat_max", "attr": "location"},
        {"name": "same_category_col_max", "type": "repeat_max", "attr": "category"},
        {"name": "total_rating_min", "type": "sum_min", "attr": "rating", "slack": 3, "floor": 1},
    ],
    "global_rules": [
        {"name": "total_budget_max", "type": "sum_max", "attr": "cost", "slack": 300, "per_item_cap": 200},
        {"name": "museum_min", "type": "count_min", "predicate_key": "category", "predicate_value": "museum", "slack": 1},
        {"name": "outdoor_min", "type": "count_min", "predicate_key": "category", "predicate_value": "outdoor", "slack": 1},
        {"name": "location_repeat_max", "type": "repeat_max", "attr": "location"},
        {"name": "daily_duration_max", "type": "max_row_sum", "attr": "duration", "slack": 2, "per_item_cap": 6},
        {"name": "rating_total_min", "type": "sum_min", "attr": "rating", "slack": 10, "floor": 1},
    ],
    "min_slot_matches": 6,
}


def build_item(index):
    category = random.choice(CATEGORIES)
    name_part = random.choice(NAME_PARTS[category])
    return {
        "activity_id": f"A{index + 1:03d}",
        "name": f"{name_part} {100 + index}",
        "category": category,
        "cost": random.randint(10, 200),
        "duration": random.randint(1, 6),
        "crowd_level": random.randint(1, 5),
        "location": random.choice(LOCATIONS),
        "rating": random.randint(1, 5),
    }
