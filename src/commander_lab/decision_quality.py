"""Moved to commander_lab.decision.quality; this alias keeps the old import path working."""

import sys

from commander_lab.decision import quality as _moved

sys.modules[__name__] = _moved
