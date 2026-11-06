"""Run only by tests/test_paid_guard.py (named on the command line, with a fake OpenRouter key set): what a test sees under the
paid-service fail-safe of tests/conftest.py."""
import os
import socket
import subprocess
import sys

import pytest


def test_paid_probe_inner():
    assert not [k for k in os.environ if k.startswith(("OPENROUTER_", "USE_LLM_DESIGN_"))]
    with pytest.raises(OSError, match="paid service"):
        socket.getaddrinfo("openrouter.ai", 443)
    with pytest.raises(OSError, match="paid service"):
        socket.getaddrinfo("api.OpenRouter.ai.", 443)
    sub = subprocess.run([sys.executable, "-c", "import os; print(sorted(k for k in os.environ if 'OPENROUTER' in k or 'USE_LLM_DESIGN' in k))"],
                         capture_output=True, text=True)
    assert sub.stdout.strip() == "[]", "a program a test starts sees no key either"
