import random


CUISINES = ["asian", "mediterranean", "american", "mexican", "italian", "fusion"]
CHEFS = [
    "Chef Lin",
    "Chef Carter",
    "Chef Gomez",
    "Chef Rossi",
    "Chef Patel",
    "Chef Morgan",
    "Chef Baker",
    "Chef Rivera",
]
NAME_PARTS = {
    "asian": ["Noodle Bowl", "Rice Plate", "Dumpling Set", "Curry Dish"],
    "mediterranean": ["Salad Plate", "Grill Platter", "Wrap Meal", "Falafel Box"],
    "american": ["Burger Plate", "Steak Meal", "Sandwich Box", "Roast Tray"],
    "mexican": ["Taco Plate", "Burrito Bowl", "Quesadilla Set", "Salsa Meal"],
    "italian": ["Pasta Dish", "Risotto Plate", "Pizza Slice", "Lasagna Tray"],
    "fusion": ["Chef Special", "Power Bowl", "Mix Grill", "Seasonal Plate"],
}

SPEC = {
    "id_key": "dish_id",
    "slot_rules": [
        {"name": "max_calories", "attr": "calories", "kind": "max", "candidates": [350, 500, 650, 800, 900]},
        {"name": "min_protein", "attr": "protein", "kind": "min", "candidates": [5, 15, 25, 35]},
        {"name": "max_price", "attr": "price", "kind": "max", "candidates": [10, 15, 20, 28, 35]},
    ],
    "row_rules": [
        {"name": "total_calories_max", "type": "sum_max", "attr": "calories", "slack": 250, "per_item_cap": 900},
        {"name": "total_protein_min", "type": "sum_min", "attr": "protein", "slack": 25, "floor": 0},
        {"name": "total_price_max", "type": "sum_max", "attr": "price", "slack": 18, "per_item_cap": 35},
        {"name": "same_cuisine_row_max", "type": "repeat_max", "attr": "cuisine"},
        {"name": "same_chef_row_max", "type": "repeat_max", "attr": "chef"},
        {"name": "total_spiciness_max", "type": "sum_max", "attr": "spiciness", "slack": 5, "per_item_cap": 5},
    ],
    "col_rules": [
        {"name": "total_calories_max", "type": "sum_max", "attr": "calories", "slack": 250, "per_item_cap": 900},
        {"name": "total_protein_min", "type": "sum_min", "attr": "protein", "slack": 25, "floor": 0},
        {"name": "total_price_max", "type": "sum_max", "attr": "price", "slack": 18, "per_item_cap": 35},
        {"name": "same_cuisine_col_max", "type": "repeat_max", "attr": "cuisine"},
        {"name": "same_chef_col_max", "type": "repeat_max", "attr": "chef"},
        {"name": "max_spiciness", "type": "max_cap", "attr": "spiciness", "cap": 5},
    ],
    "global_rules": [
        {"name": "weekly_calories_max", "type": "sum_max", "attr": "calories", "slack": 700, "per_item_cap": 900},
        {"name": "weekly_protein_min", "type": "sum_min", "attr": "protein", "slack": 100, "floor": 0},
        {"name": "same_cuisine_max", "type": "repeat_max", "attr": "cuisine"},
        {"name": "same_chef_max", "type": "repeat_max", "attr": "chef"},
        {"name": "weekly_price_max", "type": "sum_max", "attr": "price", "slack": 90, "per_item_cap": 35},
        {"name": "weekly_spiciness_max", "type": "sum_max", "attr": "spiciness", "slack": 18, "per_item_cap": 5},
    ],
    "min_slot_matches": 6,
}


def build_item(index):
    cuisine = random.choice(CUISINES)
    name_part = random.choice(NAME_PARTS[cuisine])
    return {
        "dish_id": f"D{index + 1:03d}",
        "name": f"{name_part} {100 + index}",
        "calories": random.randint(150, 900),
        "protein": random.randint(5, 60),
        "price": random.randint(5, 35),
        "cuisine": cuisine,
        "chef": random.choice(CHEFS),
        "spiciness": random.randint(1, 5),
    }
