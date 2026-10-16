"""Typed shapes for the MCP stdio JSON-RPC boundary.

These describe what ``json.loads`` yields and what ``json.dumps`` is given at the
server edge. Peer-controlled fields are declared ``object`` and narrowed with
``isinstance`` where the server reads them; response shapes are exact. Nothing
here validates at runtime, so wire bytes and key order are unchanged.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict

# A JSON-RPC request id is peer-controlled (string, number or null).
JsonRpcId = object


class McpParams(TypedDict, total=False):
    """Union of the ``params`` keys the server reads across all methods."""

    _meta: object
    name: object
    arguments: object
    surface: object
    uri: object
    requestId: object
    protocolVersion: object
    clientInfo: object


class JsonRpcMessage(TypedDict, total=False):
    """One decoded inbound JSON-RPC message (request or notification)."""

    jsonrpc: object
    id: JsonRpcId
    method: object
    params: object


class McpServerInfo(TypedDict):
    name: str
    title: str
    version: str
    description: str


class McpErrorBody(TypedDict):
    code: int
    message: str
    data: NotRequired[object]
    _meta: NotRequired[dict[str, McpServerInfo]]


class JsonRpcErrorResponse(TypedDict):
    jsonrpc: str
    id: JsonRpcId
    error: McpErrorBody


class JsonRpcResultResponse(TypedDict):
    jsonrpc: str
    id: JsonRpcId
    result: dict[str, object]


JsonRpcResponse = JsonRpcErrorResponse | JsonRpcResultResponse


class McpResource(TypedDict):
    uri: str
    name: str
    description: str
    mimeType: str


class McpPromptArgument(TypedDict):
    name: str
    required: bool
    description: NotRequired[str]


class McpPrompt(TypedDict):
    name: str
    description: str
    arguments: list[McpPromptArgument]


class McpTextContent(TypedDict):
    type: str
    text: str


class McpToolAnnotations(TypedDict):
    readOnlyHint: bool
    destructiveHint: bool


class McpToolExecution(TypedDict):
    taskSupport: str


class McpTool(TypedDict):
    name: str
    description: str
    inputSchema: object
    annotations: McpToolAnnotations
    execution: McpToolExecution


class McpToolCallResult(TypedDict):
    content: list[McpTextContent]
    structuredContent: dict[str, object]
    isError: bool


class McpResourceContent(TypedDict):
    uri: str
    mimeType: str
    text: str


class McpResourceReadResult(TypedDict):
    contents: list[McpResourceContent]
    ttlMs: int
    cacheScope: str


class McpPromptMessage(TypedDict):
    role: str
    content: McpTextContent


class McpPromptResult(TypedDict):
    description: str
    messages: list[McpPromptMessage]
