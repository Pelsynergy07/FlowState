"""Top-level PyInstaller entry script.

Deliberately not part of the flowstate package itself: running a
package's __main__.py directly as a frozen entry point breaks its
relative imports, so this thin script sits outside the package and just
calls into it, exactly like `python -m flowstate` would.
"""

import os
import sys

# The packaged build is windowed (flowstate.spec sets console=False), so
# there is no console attached and sys.stdout/stderr are literally None
# -- not a stream that discards writes, None itself. Any library that
# tries to print or write a progress bar to them (huggingface_hub's tqdm
# bars during the very first model download, for one) crashes instantly
# with "'NoneType' object has no attribute 'write'". Dev runs via
# `python -m flowstate` always have a real console, so this never showed
# up until the packaged installer was actually tested. Must happen before
# anything below has a chance to import huggingface_hub.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

from flowstate.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
