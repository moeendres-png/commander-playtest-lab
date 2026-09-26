#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/engine_setup"
OUT.mkdir(parents=True, exist_ok=True)


def command_result(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except FileNotFoundError as exc:
        return {"command": command, "error": "not_found", "detail": str(exc)}
    except Exception as exc:
        return {"command": command, "error": type(exc).__name__, "detail": str(exc)}


def dns(host: str) -> dict[str, Any]:
    try:
        return {
            "ok": True,
            "addresses": sorted({item[4][0] for item in socket.getaddrinfo(host, 443)}),
        }
    except Exception as exc:
        return {"ok": False, "error": repr(exc)}


def port_available(port: int) -> dict[str, Any]:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", port))
        return {"available": True}
    except Exception as exc:
        return {"available": False, "error": repr(exc)}
    finally:
        sock.close()


def main() -> int:
    probe_file = OUT / ".write_probe"
    write_ok = False
    write_error = None
    try:
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink()
        write_ok = True
    except Exception as exc:
        write_error = repr(exc)
    disk = shutil.disk_usage(ROOT)
    data = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_implementation": platform.python_implementation(),
        },
        "commands": {
            "java": command_result(["java", "-version"]),
            "javac": command_result(["javac", "-version"]),
            "maven": command_result(["mvn", "-version"]),
            "gradle": command_result(["gradle", "-version"]),
            "git": command_result(["git", "--version"]),
            "docker": command_result(["docker", "--version"]),
            "docker_compose": command_result(["docker", "compose", "version"]),
            "python": command_result(["python", "--version"]),
        },
        "network": {
            "dns": {
                host: dns(host)
                for host in ("github.com", "raw.githubusercontent.com", "repo.maven.apache.org")
            },
            "https": {
                url: command_result(["curl", "-I", "-L", "--max-time", "15", url])
                for url in (
                    "https://github.com",
                    "https://repo.maven.apache.org/maven2/",
                    "https://raw.githubusercontent.com/magefree/mage/master/pom.xml",
                )
            },
        },
        "filesystem": {
            "repo": str(ROOT),
            "write_ok": write_ok,
            "write_error": write_error,
            "free_bytes": disk.free,
            "free_gib": round(disk.free / 1024**3, 2),
        },
        "resources": {
            "cpu_count": os.cpu_count(),
            "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
        },
        "ports": {str(port): port_available(port) for port in (17171, 17172, 8080, 9090)},
        "environment": {
            key: os.getenv(key)
            for key in (
                "ENGINE_PROVIDER",
                "ENGINE_MODE",
                "ENGINE_SOURCE_PATH",
                "ENGINE_BINARY_PATH",
                "JAVA_HOME",
                "MAVEN_HOME",
            )
        },
        "subprocess_start": command_result(["python", "-c", "print('subprocess-ok')"]),
    }
    (OUT / "environment_diagnostics.json").write_text(
        json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
    )
    missing = [
        name
        for name in ("maven", "gradle", "docker", "docker_compose")
        if data["commands"][name].get("error")
    ]
    md = [
        "# Engine setup environment diagnostics",
        "",
        f"Generated: `{data['generated_at']}`",
        "",
        "## Platform",
        "",
        f"- OS: `{platform.system()} {platform.release()}`",
        f"- Architecture: `{platform.machine()}`",
        f"- CPU cores visible: `{os.cpu_count()}`",
        f"- Free storage: `{data['filesystem']['free_gib']} GiB`",
        f"- Repository writable: `{write_ok}`",
        "",
        "## Toolchain",
        "",
        "| Tool | Status | Version/output |",
        "|---|---|---|",
    ]
    for name, value in data["commands"].items():
        status = "available" if value.get("returncode") == 0 else "unavailable"
        detail = (value.get("stdout") or value.get("stderr") or value.get("detail") or "").replace(
            "\n", "<br>"
        )
        md.append(f"| {name} | {status} | `{detail}` |")
    md += ["", "## Network", ""]
    for host, value in data["network"]["dns"].items():
        md.append(f"- DNS `{host}`: `{value}`")
    md += [
        "",
        "## Preliminary conclusion",
        "",
        f"- Missing/unusable tools: `{', '.join(missing)}`",
        f"- GitHub DNS: `{data['network']['dns']['github.com']['ok']}`",
        f"- Maven Central DNS: `{data['network']['dns']['repo.maven.apache.org']['ok']}`",
    ]
    (OUT / "environment_diagnostics.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(OUT / "environment_diagnostics.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
