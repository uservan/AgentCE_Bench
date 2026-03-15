import os

DEFAULT_ROWS = 5
DEFAULT_COLS = 5
DEFAULT_NUM_INSTANCES = 1
DEFAULT_CANDIDATES_PER_SLOT = 24
DEFAULT_VALID_OPTIONS = 2
DEFAULT_MAX_RETRIES = 80
DEFAULT_SLOT_CANDIDATE_RETRIES = 4000
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def build_instance(*args, **kwargs):
    try:
        from .generate_dataset import build_instance as _build_instance
    except ImportError:
        from generate_dataset import build_instance as _build_instance
    return _build_instance(*args, **kwargs)


def generate_dataset(*args, **kwargs):
    try:
        from .generate_dataset import generate_dataset as _generate_dataset
    except ImportError:
        from generate_dataset import generate_dataset as _generate_dataset
    return _generate_dataset(*args, **kwargs)


def generate_all_datasets(*args, **kwargs):
    try:
        from .generate_dataset import generate_all_datasets as _generate_all_datasets
    except ImportError:
        from generate_dataset import generate_all_datasets as _generate_all_datasets
    return _generate_all_datasets(*args, **kwargs)

__all__ = [
    "DEFAULT_ROWS",
    "DEFAULT_COLS",
    "DEFAULT_NUM_INSTANCES",
    "DEFAULT_CANDIDATES_PER_SLOT",
    "DEFAULT_VALID_OPTIONS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_SLOT_CANDIDATE_RETRIES",
    "DEFAULT_OUTPUT_DIR",
    "build_instance",
    "generate_all_datasets",
    "generate_dataset",
]
