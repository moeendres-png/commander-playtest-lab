"""Moved to commander_lab.identity.variant; this alias keeps the old import path working."""

import sys

from commander_lab.identity import variant as _moved

sys.modules[__name__] = _moved
