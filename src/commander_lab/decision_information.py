"""Moved to commander_lab.decision.information; this alias keeps the old import path working."""

import sys

from commander_lab.decision import information as _moved

sys.modules[__name__] = _moved
