import random


CATEGORIES = ["produce", "dairy", "snack", "protein", "grain", "beverage"]
BRANDS = [
    "FreshFarm",
    "DailyChoice",
    "GreenLeaf",
    "PrimeSelect",
    "UrbanTaste",
    "HomeHarvest",
    "NutriBest",
    "PeakMarket",
]
NAME_PARTS = {
    "produce": ["Apples", "Bananas", "Tomatoes", "Berries", "Greens"],
    "dairy": ["Milk", "Yogurt", "Cheese", "Butter", "Cream"],
    "snack": ["Crackers", "Bars", "Cookies", "Chips", "Nuts"],
    "protein": ["Chicken", "Tofu", "Beans", "Eggs", "Fish"],
    "grain": ["Rice", "Pasta", "Oats", "Bread", "Quinoa"],
    "beverage": ["Juice", "Tea", "Coffee", "Smoothie", "Water"],
}

SPEC = {
    "id_key": "product_id",
    "slot_rules": [
        {"name": "max_price", "attr": "price", "kind": "max", "candidates": [8, 12, 16, 20, 25]},
        {"name": "min_calories", "attr": "calories", "kind": "min", "candidates": [50, 150, 250, 350]},
        {"name": "min_protein", "attr": "protein", "kind": "min", "candidates": [0, 10, 20, 30]},
    ],
    "row_rules": [
        {"name": "total_price_max", "type": "sum_max", "attr": "price", "slack": 15, "per_item_cap": 25},
        {"name": "total_calories_min", "type": "sum_min", "attr": "calories", "slack": 180, "floor": 0},
        {"name": "total_protein_min", "type": "sum_min", "attr": "protein", "slack": 25, "floor": 0},
        {"name": "same_brand_row_max", "type": "repeat_max", "attr": "brand"},
        {"name": "total_weight_max", "type": "sum_max", "attr": "weight", "slack": 800, "per_item_cap": 1500},
        {"name": "same_category_row_max", "type": "repeat_max", "attr": "category"},
    ],
    "col_rules": [
        {"name": "total_price_max", "type": "sum_max", "attr": "price", "slack": 15, "per_item_cap": 25},
        {"name": "total_calories_min", "type": "sum_min", "attr": "calories", "slack": 180, "floor": 0},
        {"name": "total_protein_min", "type": "sum_min", "attr": "protein", "slack": 25, "floor": 0},
        {"name": "same_brand_col_max", "type": "repeat_max", "attr": "brand"},
        {"name": "total_weight_max", "type": "sum_max", "attr": "weight", "slack": 800, "per_item_cap": 1500},
        {"name": "same_category_col_max", "type": "repeat_max", "attr": "category"},
    ],
    "global_rules": [
        {"name": "weekly_budget_max", "type": "sum_max", "attr": "price", "slack": 60, "per_item_cap": 25},
        {"name": "weekly_calories_min", "type": "sum_min", "attr": "calories", "slack": 600, "floor": 0},
        {"name": "weekly_protein_min", "type": "sum_min", "attr": "protein", "slack": 90, "floor": 0},
        {"name": "same_brand_max", "type": "repeat_max", "attr": "brand"},
        {"name": "weekly_weight_max", "type": "sum_max", "attr": "weight", "slack": 3000, "per_item_cap": 1500},
        {"name": "same_category_max", "type": "repeat_max", "attr": "category"},
    ],
    "min_slot_matches": 6,
}


def build_item(index):
    category = random.choice(CATEGORIES)
    name_part = random.choice(NAME_PARTS[category])
    return {
        "product_id": f"P{index + 1:03d}",
        "name": f"{name_part} {100 + index}",
        "category": category,
        "price": random.randint(2, 25),
        "calories": random.randint(50, 800),
        "protein": random.randint(0, 40),
        "brand": random.choice(BRANDS),
        "weight": random.randint(200, 1500),
    }
