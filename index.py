from __future__ import annotations

import sys
import os

# Ensure current task directory is at the head of sys.path
task_root = os.path.dirname(os.path.abspath(__file__))
if task_root not in sys.path:
    sys.path.insert(0, task_root)

from src.infrastructure.lambda_handler import handler
