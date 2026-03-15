import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from data_generation.task_instruction import (
    DOMAIN_GRID_DESCRIPTIONS,
    DOMAIN_TASK_INSTRUCTIONS,
    get_grid_description,
    get_task_instruction,
)
