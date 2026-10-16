"""Moved to commander_lab.rogshai.first_run_preparation; this alias keeps the old import path working."""

import sys

from commander_lab.rogshai import first_run_preparation as _moved

sys.modules[__name__] = _moved
