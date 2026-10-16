"""Moved to commander_lab.identity.workflow; this alias keeps the old import path working."""

import sys

from commander_lab.identity import workflow as _moved

sys.modules[__name__] = _moved
