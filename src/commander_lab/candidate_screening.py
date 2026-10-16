"""Moved to commander_lab.candidate_workflow.screening; this alias keeps the old import path working."""

import sys

from commander_lab.candidate_workflow import screening as _moved

sys.modules[__name__] = _moved
