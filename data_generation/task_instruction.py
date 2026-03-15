try:
    from .domains import DOMAIN_SPECS
except ImportError:
    from domains import DOMAIN_SPECS


DOMAIN_GRID_DESCRIPTIONS = {
    "course": {
        "intro_template": (
            "This course scheduling plan has {rows} scheduling days as rows and {cols} class time slots "
            "per day as columns."
        ),
        "row_label": "day",
        "col_label": "time slot",
    },
    "shopping": {
        "intro_template": (
            "This grocery shopping plan has {rows} shopping days as rows and {cols} item slots "
            "to fill per day as columns."
        ),
        "row_label": "shopping day",
        "col_label": "item slot",
    },
    "travel": {
        "intro_template": (
            "This travel itinerary has {rows} travel days as rows and {cols} activity slots "
            "per day as columns."
        ),
        "row_label": "travel day",
        "col_label": "activity slot",
    },
    "workforce": {
        "intro_template": (
            "This workforce scheduling plan has {rows} work days as rows and {cols} shift slots "
            "to staff per day as columns."
        ),
        "row_label": "work day",
        "col_label": "shift slot",
    },
    "meal": {
        "intro_template": (
            "This meal planning task has {rows} planning days as rows and {cols} meal slots "
            "to fill per day as columns."
        ),
        "row_label": "meal day",
        "col_label": "meal slot",
    },
    "pc_build": {
        "intro_template": (
            "This PC build task has {rows} build configurations as rows and {cols} component slots "
            "within each configuration as columns."
        ),
        "row_label": "build track",
        "col_label": "component slot",
    },
}


DOMAIN_TASK_INSTRUCTIONS = {
    "course": (
        "You are solving a course scheduling task. Fill the {rows}x{cols} grid with course ids.\n"
        "{grid_description}\n"
        "Each cell must use exactly one candidate id from that slot.\n\n"
        "{global_constraints_text}\n\n"
        "{row_constraints_text}\n\n"
        "{col_constraints_text}\n\n"
        "Each slot also has its own local constraints, but those slot-specific limits must be "
        "looked up from the dataset/database for that slot before deciding which candidate id to use.\n"
        "Return only a {rows}x{cols} list of course ids."
    ),
    "shopping": (
        "You are solving a grocery shopping task. Fill the {rows}x{cols} grid with product ids.\n"
        "{grid_description}\n"
        "Each cell must use exactly one candidate id from that slot.\n\n"
        "{global_constraints_text}\n\n"
        "{row_constraints_text}\n\n"
        "{col_constraints_text}\n\n"
        "Each slot also has its own local constraints, but those slot-specific limits must be "
        "looked up from the dataset/database for that slot before deciding which candidate id to use.\n"
        "Return only a {rows}x{cols} list of product ids."
    ),
    "travel": (
        "You are solving a travel itinerary task. Fill the {rows}x{cols} grid with activity ids.\n"
        "{grid_description}\n"
        "Each cell must use exactly one candidate id from that slot.\n\n"
        "{global_constraints_text}\n\n"
        "{row_constraints_text}\n\n"
        "{col_constraints_text}\n\n"
        "Each slot also has its own local constraints, but those slot-specific limits must be "
        "looked up from the dataset/database for that slot before deciding which candidate id to use.\n"
        "Return only a {rows}x{cols} list of activity ids."
    ),
    "workforce": (
        "You are solving a workforce scheduling task. Fill the {rows}x{cols} grid with worker ids.\n"
        "{grid_description}\n"
        "Each cell must use exactly one candidate id from that slot.\n\n"
        "{global_constraints_text}\n\n"
        "{row_constraints_text}\n\n"
        "{col_constraints_text}\n\n"
        "Each slot also has its own local constraints, but those slot-specific "
        "limits must be looked up from the dataset/database for that slot before deciding which "
        "candidate id to use.\n"
        "Return only a {rows}x{cols} list of worker ids."
    ),
    "meal": (
        "You are solving a meal planning task. Fill the {rows}x{cols} grid with dish ids.\n"
        "{grid_description}\n"
        "Each cell must use exactly one candidate id from that slot.\n\n"
        "{global_constraints_text}\n\n"
        "{row_constraints_text}\n\n"
        "{col_constraints_text}\n\n"
        "Each slot also has its own local constraints, "
        "but those slot-specific limits must be looked up from the dataset/database for that slot "
        "before deciding which candidate id to use.\n"
        "Return only a {rows}x{cols} list of dish ids."
    ),
    "pc_build": (
        "You are solving a PC build configuration task. Fill the {rows}x{cols} grid with component ids.\n"
        "{grid_description}\n"
        "Each cell must use exactly one candidate id from that slot.\n\n"
        "{global_constraints_text}\n\n"
        "{row_constraints_text}\n\n"
        "{col_constraints_text}\n\n"
        "Each slot also has its own local constraints, "
        "but those slot-specific limits must be looked up from the dataset/database for that slot "
        "before deciding which candidate id to use.\n"
        "Return only a {rows}x{cols} list of component ids."
    ),
}


DOMAIN_ITEM_LABELS = {
    "course": ("course", "courses"),
    "shopping": ("product", "products"),
    "travel": ("activity", "activities"),
    "workforce": ("worker", "workers"),
    "meal": ("dish", "dishes"),
    "pc_build": ("component", "components"),
}


ATTRIBUTE_LABELS = {
    "credits": "credits",
    "price": "price",
    "difficulty": "difficulty",
    "teacher": "teacher",
    "workload": "workload",
    "calories": "calories",
    "protein": "protein",
    "brand": "brand",
    "weight": "weight",
    "cost": "cost",
    "duration": "duration",
    "crowd_level": "crowd level",
    "location": "location",
    "rating": "rating",
    "skill": "skill",
    "hourly_cost": "hourly cost",
    "experience": "experience",
    "reliability": "reliability",
    "overtime_capacity": "overtime capacity",
    "cuisine": "cuisine",
    "chef": "chef",
    "spiciness": "spiciness",
    "dish_id": "dish",
    "performance": "performance",
    "power": "power",
    "compatibility": "compatibility",
    "worker_id": "worker",
}


def get_grid_description(domain, rows=None, cols=None):
    if domain not in DOMAIN_GRID_DESCRIPTIONS:
        raise KeyError(f"Unsupported domain for grid description: {domain}")
    description = DOMAIN_GRID_DESCRIPTIONS[domain].copy()
    if rows is not None and cols is not None:
        description["intro"] = description["intro_template"].format(rows=rows, cols=cols)
    else:
        description["intro"] = description["intro_template"]
    return description


def get_task_instruction(
    domain,
    rows=None,
    cols=None,
    grid_description=None,
    global_constraints_text=None,
    row_constraints_text=None,
    col_constraints_text=None,
):
    if domain not in DOMAIN_TASK_INSTRUCTIONS:
        raise KeyError(f"Unsupported domain for task instruction: {domain}")
    if (
        rows is None
        or cols is None
        or grid_description is None
        or global_constraints_text is None
        or row_constraints_text is None
        or col_constraints_text is None
    ):
        return DOMAIN_TASK_INSTRUCTIONS[domain]
    return DOMAIN_TASK_INSTRUCTIONS[domain].format(
        rows=rows,
        cols=cols,
        grid_description=grid_description,
        global_constraints_text=global_constraints_text,
        row_constraints_text=row_constraints_text,
        col_constraints_text=col_constraints_text,
    )


def _label_for_attr(attr_name):
    return ATTRIBUTE_LABELS.get(attr_name, attr_name.replace("_", " "))


def _format_rule_text(domain, rule, value, scope_text):
    item_singular, item_plural = DOMAIN_ITEM_LABELS[domain]
    rule_type = rule["type"]

    if rule_type == "sum_min":
        return f"the total {_label_for_attr(rule['attr'])} of all {item_plural} in {scope_text} must be at least {value}"
    if rule_type == "sum_max":
        return f"the total {_label_for_attr(rule['attr'])} of all {item_plural} in {scope_text} must be at most {value}"
    if rule_type == "max_cap":
        return f"the maximum {_label_for_attr(rule['attr'])} of any {item_singular} in {scope_text} must be at most {value}"
    if rule_type == "repeat_max":
        return f"the same {_label_for_attr(rule['attr'])} can appear at most {value} times in {scope_text}"
    if rule_type == "count_min":
        return (
            f"there must be at least {value} {item_plural} in {scope_text} whose "
            f"{_label_for_attr(rule['predicate_key'])} is {rule['predicate_value']}"
        )
    if rule_type == "count_min_threshold":
        return (
            f"there must be at least {value} {item_plural} in {scope_text} whose "
            f"{_label_for_attr(rule['attr'])} is at least {rule['threshold']}"
        )
    if rule_type == "max_row_sum":
        return f"for any single row in {scope_text}, the total {_label_for_attr(rule['attr'])} must be at most {value}"
    raise ValueError(f"Unsupported rule type for natural-language formatting: {rule_type}")


def _numbered_rule_texts(rule_texts):
    return "\n".join(
        f"({index}) {rule_text}."
        for index, rule_text in enumerate(rule_texts, start=1)
    )


def _format_global_constraints(domain, global_constraints):
    rule_texts = []
    for rule in DOMAIN_SPECS[domain]["global_rules"]:
        if rule["name"] not in global_constraints:
            continue
        rule_texts.append(_format_rule_text(domain, rule, global_constraints[rule["name"]], "the whole grid"))
    if not rule_texts:
        return "Across the whole grid, there are no active global constraints."
    return "Across the whole grid, the plan must satisfy these global constraints:\n" + _numbered_rule_texts(rule_texts)


def _format_row_constraints(domain, row_constraints, row_label):
    parts = []
    for constraint in row_constraints:
        row_index = constraint["row"]
        rule_texts = []
        for rule in DOMAIN_SPECS[domain]["row_rules"]:
            if rule["name"] not in constraint:
                continue
            rule_texts.append(_format_rule_text(domain, rule, constraint[rule["name"]], f"{row_label} {row_index}"))
        if rule_texts:
            parts.append(f"For {row_label} {row_index}:\n{_numbered_rule_texts(rule_texts)}")
    if not parts:
        return "There are no active row constraints."
    return "For the row constraints:\n" + "\n\n".join(parts)


def _format_col_constraints(domain, col_constraints, col_label):
    parts = []
    for constraint in col_constraints:
        col_index = constraint["col"]
        rule_texts = []
        for rule in DOMAIN_SPECS[domain]["col_rules"]:
            if rule["name"] not in constraint:
                continue
            rule_texts.append(_format_rule_text(domain, rule, constraint[rule["name"]], f"{col_label} {col_index}"))
        if rule_texts:
            parts.append(f"For {col_label} {col_index}:\n{_numbered_rule_texts(rule_texts)}")
    if not parts:
        return "There are no active column constraints."
    return "For the column constraints:\n" + "\n\n".join(parts)


def build_task_instruction_from_instance(instance):
    domain = instance["domain"]
    rows = instance["meta"]["rows"]
    cols = instance["meta"]["cols"]
    grid_description = get_grid_description(domain, rows=rows, cols=cols)
    return DOMAIN_TASK_INSTRUCTIONS[domain].format(
        rows=rows,
        cols=cols,
        grid_description=grid_description["intro"],
        global_constraints_text=_format_global_constraints(domain, instance["global_constraints"]),
        row_constraints_text=_format_row_constraints(domain, instance["row_constraints"], grid_description["row_label"]),
        col_constraints_text=_format_col_constraints(domain, instance["col_constraints"], grid_description["col_label"]),
    )
