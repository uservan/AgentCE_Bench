import random


CATEGORIES = ["cpu", "gpu", "ram", "storage", "motherboard", "cooling"]
BRANDS = [
    "NovaTech",
    "ApexCore",
    "VoltForge",
    "SkyChip",
    "PixelWare",
    "IronGrid",
    "QuantumEdge",
    "TitanBit",
]
NAME_PARTS = {
    "cpu": ["Processor", "Compute Chip", "Performance CPU", "Gaming CPU"],
    "gpu": ["Graphics Card", "Render GPU", "Gaming GPU", "Creator GPU"],
    "ram": ["Memory Kit", "DDR Module", "Performance RAM", "Low Latency RAM"],
    "storage": ["SSD Drive", "NVMe Drive", "Performance Storage", "Archive Drive"],
    "motherboard": ["Mainboard", "ATX Board", "Compact Board", "Performance Board"],
    "cooling": ["Air Cooler", "Liquid Cooler", "Silent Cooler", "ARGB Cooler"],
}

SPEC = {
    "id_key": "component_id",
    "slot_rules": [
        {"name": "max_price", "attr": "price", "kind": "max", "candidates": [220, 400, 650, 900, 1500]},
        {"name": "min_performance", "attr": "performance", "kind": "min", "candidates": [20, 40, 60, 75]},
        {"name": "max_power", "attr": "power", "kind": "max", "candidates": [90, 150, 220, 320, 450]},
    ],
    "row_rules": [
        {"name": "total_price_max", "type": "sum_max", "attr": "price", "slack": 400, "per_item_cap": 1500},
        {"name": "total_power_max", "type": "sum_max", "attr": "power", "slack": 150, "per_item_cap": 450},
        {"name": "total_performance_min", "type": "sum_min", "attr": "performance", "slack": 50, "floor": 0},
        {"name": "same_brand_row_max", "type": "repeat_max", "attr": "brand"},
        {"name": "total_compatibility_min", "type": "sum_min", "attr": "compatibility", "slack": 40, "floor": 60},
        {"name": "same_category_row_max", "type": "repeat_max", "attr": "category"},
    ],
    "col_rules": [
        {"name": "total_price_max", "type": "sum_max", "attr": "price", "slack": 400, "per_item_cap": 1500},
        {"name": "total_power_max", "type": "sum_max", "attr": "power", "slack": 150, "per_item_cap": 450},
        {"name": "total_performance_min", "type": "sum_min", "attr": "performance", "slack": 50, "floor": 0},
        {"name": "same_brand_col_max", "type": "repeat_max", "attr": "brand"},
        {"name": "max_compatibility", "type": "max_cap", "attr": "compatibility", "cap": 100},
        {"name": "same_category_col_max", "type": "repeat_max", "attr": "category"},
    ],
    "global_rules": [
        {"name": "total_budget_max", "type": "sum_max", "attr": "price", "slack": 1200, "per_item_cap": 1500},
        {"name": "total_power_max", "type": "sum_max", "attr": "power", "slack": 500, "per_item_cap": 450},
        {"name": "same_brand_max", "type": "repeat_max", "attr": "brand"},
        {"name": "same_category_max", "type": "repeat_max", "attr": "category"},
        {"name": "high_performance_min", "type": "count_min_threshold", "attr": "performance", "threshold": 75, "slack": 2},
        {"name": "total_compatibility_min", "type": "sum_min", "attr": "compatibility", "slack": 180, "floor": 60},
    ],
    "min_slot_matches": 6,
}


def build_item(index):
    category = random.choice(CATEGORIES)
    name_part = random.choice(NAME_PARTS[category])
    return {
        "component_id": f"PC{index + 1:03d}",
        "name": f"{name_part} {100 + index}",
        "category": category,
        "price": random.randint(50, 1500),
        "performance": random.randint(10, 100),
        "power": random.randint(20, 450),
        "brand": random.choice(BRANDS),
        "compatibility": random.randint(60, 100),
    }
