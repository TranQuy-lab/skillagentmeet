#!/usr/bin/env python3
"""Compatibility wrapper: read messages incrementally since a cursor.

Delegates to `scripts/inbox.py` which provides cursor tracking, filtering,
and context-safe compact formatting.
"""

import sys
from pathlib import Path

# Run inbox.main() with current argv
inbox_script = Path(__file__).resolve().parent / "inbox.py"
if inbox_script.exists():
    import runpy
    runpy.run_path(str(inbox_script), run_name="__main__")
else:
    print(f"error: {inbox_script} not found", file=sys.stderr)
    sys.exit(1)
