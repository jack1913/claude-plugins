#!/usr/bin/env python3
"""Check every API the swift plugin's skills name against Apple's documentation (see apicheck/cli.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apicheck.cli import main  # noqa: E402

sys.exit(main())
