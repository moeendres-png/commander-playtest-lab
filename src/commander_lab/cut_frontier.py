"""Moved to commander_lab.candidate_workflow.cut_frontier; this alias keeps the old import path working."""

import sys

from commander_lab.candidate_workflow import cut_frontier as _moved

sys.modules[__name__] = _moved
