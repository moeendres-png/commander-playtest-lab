from __future__ import annotations

from typing import Any

__all__ = [
    "CURRENT_MCP_PROTOCOL_VERSION",
    "LEGACY_MCP_PROTOCOL_VERSION",
    "MCP_PROTOCOL_VERSION",
    "CommanderMcpServer",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import server
        return getattr(server, name)
    raise AttributeError(name)
