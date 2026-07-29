"""Static guard: no undefined name may exist anywhere in the backend source.

WHY THIS EXISTS
A NameError inside a function body does not fire until that function is CALLED.
`repositories/email_import_messages.stage_message` referenced `literal_column`
without importing it, and every signal we had came back clean:

  - `import app.repositories.email_import_messages` succeeded (module-level
    code was fine),
  - the whole email-import suite passed, because every test monkeypatches the
    repository layer, so the real function never ran.

It reached production and returned 500 on POST /api/integrations/email/sync.

Pyflakes catches exactly this in milliseconds, with no database and no
network, so the bug class cannot reach a deploy again.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "app"


def test_backend_source_has_no_undefined_names():
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pyflakes", str(SRC)],
            capture_output=True, text=True, timeout=180,
        )
    except FileNotFoundError:  # pragma: no cover
        pytest.skip("pyflakes not installed")
    if "No module named" in (proc.stderr or ""):
        pytest.skip("pyflakes not installed")

    undefined = [
        line for line in (proc.stdout or "").splitlines()
        if "undefined name" in line
    ]
    assert not undefined, (
        "Undefined name(s) in backend source — these raise NameError at call "
        "time, which import checks and mocked tests cannot catch:\n  "
        + "\n  ".join(undefined)
    )
