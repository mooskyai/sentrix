"""Verify that direct-file M6.5 CLI execution can import Django settings."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_direct_script_resolves_project_root_without_pythonpath() -> None:
    backend_root = Path(__file__).resolve().parents[3]
    script = backend_root / "scripts" / "m6_readback.py"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    process = subprocess.run(
        [
            sys.executable,
            str(script),
            "--run-id",
            "319b34b2346645fe8729b5518ca8a236",
            "--trace-id",
            "29b8393d3bef43d191ebc371b0113e26",
            "--time",
            "2026-10-24T17:11:41.422946+00:00",
        ],
        input="deliberately-invalid-project-key\n",
        text=True,
        capture_output=True,
        cwd=backend_root,
        env=env,
        timeout=20,
        check=False,
    )

    assert process.returncode == 1
    assert "Project key rejected" in process.stderr
    assert "ModuleNotFoundError" not in process.stderr
