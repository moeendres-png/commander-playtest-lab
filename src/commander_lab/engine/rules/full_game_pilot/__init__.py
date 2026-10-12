"""External pilot decision policy for XMage full games, split by decision kind.

Layers build on each other: state (bookkeeping and views) <- payment <-
choices <- combat <- priority <- policy (the ``decide`` entry point).
"""

from .policy import ExternalPilotDecisionPolicy

__all__ = ["ExternalPilotDecisionPolicy"]
