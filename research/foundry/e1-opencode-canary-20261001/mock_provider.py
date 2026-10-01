"""Minimal OpenAI-compatible chat-completions mock that scripts tool calls.

It never forwards anything; it only answers from a fixed plan and logs what the
client sent back (tool results) to a JSONL file.
"""

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PLAN = json.loads(Path(sys.argv[2]).read_text())  # list of {"tool": name, "args": {...}} then text
LOG = sys.argv[3]
state = {"i": 0}


def sse(handler, obj):
    handler.wfile.write(b"data: " + json.dumps(obj).encode() + b"\n\n")
    handler.wfile.flush()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        body = json.dumps(
            {"object": "list", "data": [{"id": "canary", "object": "model"}]}
        ).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("content-length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")
        msgs = req.get("messages", [])
        tool_msgs = [m for m in msgs if m.get("role") == "tool"]
        with open(LOG, "a") as f:
            f.write(
                json.dumps(
                    {
                        "path": self.path,
                        "n_messages": len(msgs),
                        "tools_offered": sorted(
                            t.get("function", {}).get("name", "")
                            for t in req.get("tools", []) or []
                        ),
                        "tool_results": [str(m.get("content"))[:400] for m in tool_msgs],
                    }
                )
                + "\n"
            )
        # Title/summary side requests carry no tools: answer with plain text.
        if not req.get("tools"):
            step = {"text": "canary"}
        else:
            idx = len(tool_msgs)
            step = PLAN[idx] if idx < len(PLAN) else {"text": "done"}
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        base = {
            "id": "c",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "canary",
        }
        if "tool" in step:
            call = {
                "index": 0,
                "id": f"call_{len(tool_msgs)}",
                "type": "function",
                "function": {"name": step["tool"], "arguments": json.dumps(step["args"])},
            }
            sse(
                self,
                {
                    **base,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "tool_calls": [call]},
                            "finish_reason": None,
                        }
                    ],
                },
            )
            sse(
                self,
                {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
            )
        else:
            sse(
                self,
                {
                    **base,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": step["text"]},
                            "finish_reason": None,
                        }
                    ],
                },
            )
            sse(self, {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        sse(
            self,
            {
                **base,
                "choices": [],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
