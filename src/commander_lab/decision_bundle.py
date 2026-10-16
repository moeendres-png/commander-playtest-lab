"""Moved to commander_lab.decision.bundle; this alias keeps the old import path working."""

import sys

from commander_lab.decision import bundle as _moved

sys.modules[__name__] = _moved
