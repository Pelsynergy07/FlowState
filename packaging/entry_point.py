"""Top-level PyInstaller entry script.

Deliberately not part of the flowstate package itself: running a
package's __main__.py directly as a frozen entry point breaks its
relative imports, so this thin script sits outside the package and just
calls into it, exactly like `python -m flowstate` would.
"""

import sys

from flowstate.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
