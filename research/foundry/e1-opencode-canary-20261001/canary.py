"""E1 canary: does a launcher-configured OpenCode run write outside its worktree?

Usage: canary.py <new-run-dir> <opencode-1.18.30-binary> <empty-target-dir> [control] [sibling-name]
controls: none | deny-outside | deny-outside-edit | deny-outside-edit-rel |
deny-outside-edit-any | deny-outside-edit-rootrel | deny-sibling-edit | isolate

Harmless: every target is a dedicated empty canary directory created here; the
model is a local mock that scripts the tool calls; HOME/XDG are isolated.
Only the provider/model part of the launcher bundle is replaced; the permission
block is exactly what the launcher produces.
"""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(LAB / "tools/foundry"))
import launcher  # noqa: E402

E1 = Path(sys.argv[1]).resolve()
BIN = str(Path(sys.argv[2]).resolve())
OUTSIDE = Path(sys.argv[3])  # dedicated empty directory outside the worktree and outside /tmp
if E1.exists():
    raise SystemExit(f"refusing to reuse an existing directory: {E1}")
home, repo, run_dir = E1 / "home", E1 / "repo", E1 / "run"
sib = E1 / (sys.argv[5] if len(sys.argv) > 5 else "repo-sibling")
for d in (home, run_dir):
    d.mkdir(parents=True)
OUTSIDE.mkdir(parents=True, exist_ok=True)
assert not any(OUTSIDE.iterdir()), "canary target must be empty"


def git(*args: str, cwd: Path = repo) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


repo.mkdir()
git("init", "-q", "-b", "main")
(repo / "README.md").write_text("canary\n")
git("add", ".")
git("-c", "user.name=c", "-c", "user.email=c@c", "commit", "-qm", "init")
git("worktree", "add", "-q", str(sib), "-b", "sibling")
state = E1 / "state.yaml"
state.write_text("canary: true\n")

env = launcher.resolve_environment(
    canonical_root=str(LAB),
    worktree=str(repo),
    branch="main",
    workstream="e1-canary",
    effort="high",
    session="e1",
    drift_suppressed=False,
    run_dir=str(run_dir),
    state_path=str(state),
    mode="implement",
    references=[],
    workspace_access=[],
    opencode_binary=BIN,
)
bundle = json.loads(env["OPENCODE_CONFIG_CONTENT"])
permission_before = json.dumps(bundle["permission"], sort_keys=True)
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
bundle["provider"] = {
    "canary": {
        "npm": "@ai-sdk/openai-compatible",
        "name": "canary",
        "options": {"baseURL": f"http://127.0.0.1:{port}/v1", "apiKey": "canary-not-a-secret"},
        "models": {"canary": {"name": "canary", "tool_call": True}},
    }
}
bundle["model"] = bundle["small_model"] = "canary/canary"
bundle["enabled_providers"] = ["canary"]
bundle["agent"] = {k: {"model": "canary/canary"} for k in bundle["agent"]}
bundle["experimental"]["policies"] = [
    p for p in bundle["experimental"].get("policies", []) if p.get("action") != "provider.use"
] + [{"action": "provider.use", "effect": "allow", "resource": "canary"}]
assert json.dumps(bundle["permission"], sort_keys=True) == permission_before
CONTROL = sys.argv[4] if len(sys.argv) > 4 else ""
if CONTROL == "deny-outside":
    for pattern in launcher._root_patterns(str(OUTSIDE)):
        bundle["permission"]["external_directory"][pattern] = "deny"
if CONTROL == "deny-sibling-edit":
    for pattern in launcher.sibling_denies(str(repo)):
        bundle["permission"]["edit"][pattern] = "deny"
if CONTROL == "isolate":
    plain = E1 / "plain"
    plain.mkdir(exist_ok=True)
    for pattern in launcher._root_patterns(str(plain)):
        bundle["permission"]["external_directory"][pattern] = "deny"
    bundle["permission"]["edit"]["../" + sib.name + "/*"] = "deny"
if CONTROL == "deny-outside-edit-rel":
    rel = os.path.relpath(str(OUTSIDE), str(repo))
    bundle["permission"]["edit"][rel] = "deny"
    bundle["permission"]["edit"][rel + "/*"] = "deny"
if CONTROL == "deny-outside-edit-any":
    bundle["permission"]["edit"]["*e1-canary-target*"] = "deny"
if CONTROL == "deny-outside-edit-rootrel":
    bundle["permission"]["edit"][str(OUTSIDE).lstrip("/") + "/*"] = "deny"
if CONTROL == "deny-outside-edit":
    for pattern in launcher._root_patterns(str(OUTSIDE)):
        bundle["permission"]["edit"][pattern] = "deny"
(E1 / "bundle.permission.json").write_text(json.dumps(bundle["permission"], indent=1))
env["OPENCODE_CONFIG_CONTENT"] = json.dumps(bundle)
# Isolation: never touch the real HOME, never pass ambient credentials.
for key in list(env):
    if key.endswith(("_API_KEY", "_TOKEN")) or key.startswith(("OPENCODE_API", "GH_", "GITHUB_")):
        env.pop(key)
env.update(
    HOME=str(home),
    XDG_CONFIG_HOME=str(home / ".config"),
    XDG_DATA_HOME=str(home / ".local/share"),
    XDG_CACHE_HOME=str(home / ".cache"),
    XDG_STATE_HOME=str(home / ".local/state"),
)

targets = {
    "inside_worktree": repo / "inside.txt",
    "outside_non_tmp": OUTSIDE / "outside.txt",
    "sibling_worktree": sib / "sibling.txt",
    "env_file_inside": repo / ".env",
    "bash_redirect_outside": OUTSIDE / "bash.txt",
    "python_write_outside": OUTSIDE / "python.txt",
    "plain_dir_with_external_deny": E1 / "plain" / "plain.txt",
}
plan = [
    {"tool": "write", "args": {"filePath": str(targets["inside_worktree"]), "content": "canary\n"}},
    {"tool": "write", "args": {"filePath": str(targets["outside_non_tmp"]), "content": "canary\n"}},
    {
        "tool": "write",
        "args": {"filePath": str(targets["sibling_worktree"]), "content": "canary\n"},
    },
    {
        "tool": "write",
        "args": {"filePath": str(targets["env_file_inside"]), "content": "CANARY=1\n"},
    },
    {
        "tool": "bash",
        "args": {
            "command": f"echo canary > {targets['bash_redirect_outside']}",
            "description": "canary",
        },
    },
    {
        "tool": "bash",
        "args": {
            "command": f"python3 -c \"open('{targets['python_write_outside']}','w').write('canary')\"",
            "description": "canary",
        },
    },
    {"tool": "write", "args": {"filePath": str(E1 / "plain" / "plain.txt"), "content": "canary\n"}},
    {"text": "done"},
]
(E1 / "plan.json").write_text(json.dumps(plan))
log = E1 / "mock.jsonl"
mock = subprocess.Popen(
    [
        sys.executable,
        str(Path(__file__).with_name("mock_provider.py")),
        str(port),
        str(E1 / "plan.json"),
        str(log),
    ]
)
time.sleep(1.0)
argv = launcher.build_argv(
    BIN,
    "headless",
    (["--print-logs", "--log-level", "DEBUG"] if os.environ.get("CANARY_LOGS") else [])
    + ["--agent", "foundry-implementer", "canary probe"],
)
try:
    with open(E1 / "opencode.stdout", "w") as out, open(E1 / "opencode.stderr", "w") as err:
        try:
            rc = subprocess.run(
                argv,
                cwd=repo,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                timeout=150,
            ).returncode
        except subprocess.TimeoutExpired:
            rc = "TIMEOUT"
finally:
    mock.terminate()
result = {name: path.exists() for name, path in targets.items()}
calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
print(
    json.dumps(
        {
            "returncode": rc,
            "written": result,
            "requests": len(calls),
            "tool_results": [c["tool_results"] for c in calls if c["tool_results"]][-1:],
        },
        indent=1,
    )
)
