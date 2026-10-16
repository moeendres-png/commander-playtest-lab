"""Moved to commander_lab.decision.context; this alias keeps the old import path working."""

import sys

from commander_lab.decision import context as _moved

sys.modules[__name__] = _moved
