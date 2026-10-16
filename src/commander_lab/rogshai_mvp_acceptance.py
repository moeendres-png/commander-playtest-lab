"""Moved to commander_lab.rogshai.mvp_acceptance; this alias keeps the old import path working."""

import sys

from commander_lab.rogshai import mvp_acceptance as _moved

sys.modules[__name__] = _moved
