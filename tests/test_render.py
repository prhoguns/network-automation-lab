"""Rendering is deterministic and the committed configs match the inventory (so nobody hand-edits a config)."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# When the tests themselves run inside a container, the docker daemon needs the *host* path for the bind mount.
HOST_ROOT = Path(os.getenv("LAB_HOST_ROOT", ROOT))


def test_configs_are_in_sync_with_inventory(tmp_path):
    sys.path.insert(0, str(ROOT))
    from scripts.render import load_topology, render_frr

    render_frr(load_topology(), out_dir=tmp_path)
    for name in load_topology()["routers"]:
        fresh = (tmp_path / name / "frr.conf").read_text()
        committed = (ROOT / "configs" / name / "frr.conf").read_text()
        assert (
            fresh == committed
        ), f"configs/{name}/frr.conf is stale: run scripts/render.py"


def test_every_router_config_parses_in_frr():
    """vtysh --dryrun validates syntax without a running daemon."""
    for cfg in sorted((ROOT / "configs").glob("*/frr.conf")):
        r = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{HOST_ROOT / cfg.parent.relative_to(ROOT)}:/etc/frr:ro",
                "quay.io/frrouting/frr:10.1.1",
                "vtysh",
                "--dryrun",
                "-f",
                "/etc/frr/frr.conf",
            ],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, f"{cfg}: {r.stderr or r.stdout}"
