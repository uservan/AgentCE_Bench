import json
import os
from dataclasses import dataclass


DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
LEGACY_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

@dataclass
class SavedDatasetObject:
    domain: str
    instance_id: str
    meta: dict
    global_constraints: dict
    row_constraints: list
    col_constraints: list
    item_pool: dict
    truth_solution: list
    slots: list
    task_instruction: str
    source_path: str
    source_filename: str

def _build_dataset_object(instance, source_path):
    return SavedDatasetObject(
        domain=instance["domain"],
        instance_id=instance["instance_id"],
        meta=instance["meta"],
        global_constraints=instance["global_constraints"],
        row_constraints=instance["row_constraints"],
        col_constraints=instance["col_constraints"],
        item_pool=instance["item_pool"],
        truth_solution=instance["truth_solution"],
        slots=instance["slots"],
        task_instruction=instance["task_instruction"],
        source_path=source_path,
        source_filename=os.path.basename(source_path),
    )


def load_dataset_objects_from_file(path):
    with open(path, "r", encoding="utf-8") as input_file:
        payload = json.load(input_file)

    if "instances" not in payload:
        raise ValueError(f"Dataset file does not contain 'instances': {path}")

    return [
        _build_dataset_object(instance, path)
        for instance in payload["instances"]
    ]


def load_dataset_object(path, instance_index=0):
    dataset_objects = load_dataset_objects_from_file(path)
    if instance_index < 0 or instance_index >= len(dataset_objects):
        raise IndexError(f"instance_index {instance_index} is out of range for {path}")
    return dataset_objects[instance_index]


def load_all_dataset_objects(data_dir=DEFAULT_DATA_DIR):
    if data_dir == DEFAULT_DATA_DIR and not os.path.isdir(data_dir) and os.path.isdir(LEGACY_DATA_DIR):
        data_dir = LEGACY_DATA_DIR
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"Data directory does not exist: {data_dir}")

    dataset_objects = []
    for filename in sorted(os.listdir(data_dir)):
        if not filename.endswith(".json"):
            continue
        file_path = os.path.join(data_dir, filename)
        dataset_objects.extend(load_dataset_objects_from_file(file_path))

    return dataset_objects


def load_dataset_objects_by_domain(data_dir=DEFAULT_DATA_DIR):
    grouped = {}
    for dataset_object in load_all_dataset_objects(data_dir=data_dir):
        grouped.setdefault(dataset_object.domain, []).append(dataset_object)
    return grouped


if __name__ == "__main__":
    dataset_objects = load_all_dataset_objects(data_dir=DEFAULT_DATA_DIR)
    for dataset_object in dataset_objects:
        print(dataset_object.task_instruction)
    print(f"Loaded {len(dataset_objects)} dataset objects from {DEFAULT_DATA_DIR}")

    for dataset_object in dataset_objects:
        print(
            f"- {dataset_object.domain} | {dataset_object.instance_id} | "
            f"{dataset_object.source_filename}"
        )

    if dataset_objects:
        sample = dataset_objects[0]
        print("\nSample task instruction:\n")
        print(sample.task_instruction)

# 我现在需要写tools，也是在/Users/yangwang/dev_programs/python/cached_agent_benchmark/saved_datasets下面写个文件夹，然后对应每个domain的有着对应的tools。 具体的tools （1）对于每个slot，查询candidate，包括对应的id，name和 category；（2）根据id查询item的信息 （3）在slot写入对应的id （4）在slot去掉对应的id
