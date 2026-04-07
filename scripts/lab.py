"""Helpers to talk to the running lab: run vtysh commands and get JSON back."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def topology() -> dict:
    return yaml.safe_load((ROOT / "inventory/topology.yml").read_text())


def vtysh(router: str, command: str) -> str:
    return subprocess.run(
        ["docker", "exec", router, "vtysh", "-c", command],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def vtysh_json(router: str, command: str) -> dict:
    return json.loads(
        vtysh(router, command if command.endswith("json") else command + " json")
    )


def ping(src: str, dst: str, count: int = 2) -> bool:
    r = subprocess.run(
        ["docker", "exec", src, "ping", "-c", str(count), "-W", "1", dst],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def internal_routers(topo: dict) -> list[str]:
    return [n for n, r in topo["routers"].items() if r["role"] != "isp"]
