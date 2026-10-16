"""Moved to commander_lab.rogshai.experiments; this alias keeps the old import path working."""

import sys

from commander_lab.rogshai import experiments as _moved

sys.modules[__name__] = _moved
