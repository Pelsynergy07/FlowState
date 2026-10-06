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
# Model downloads over hf-xet were seen to stall indefinitely mid-file;
# plain HTTPS downloads resume reliably.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

# A smoke check of the frozen runtime, before opening the user app or touching
# its model/session data. Used by release verification and upgrade tests.
if "--verify-runtime" in sys.argv:
    import json
    from pathlib import Path
    from PySide6.QtCore import qVersion
    from PySide6.QtWidgets import QApplication
    from flowstate.ui.settings_window import SettingsWindow
    from flowstate.config import ConfigStore
    from flowstate.usage import UsageStore
    root = Path(sys.argv[sys.argv.index("--verify-runtime") + 1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.environ["LOCALAPPDATA"] = str(root)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    application = QApplication([])
    window = SettingsWindow(ConfigStore(path=root / "config.json"))
    window.show()
    application.processEvents()
    assert window.tabs.count() == 8
    stats = UsageStore(root / "usage.sqlite3")
    stats.record(42, 10, 1200, "success")
    assert stats.snapshot()["words"] == 42
    # The GPU formatter runtime must be bundled with its tokenizer.
    import ctranslate2, tokenizers
    from flowstate.text import guard, llm
    assert guard.preserves_words("hello there", "Hello, there.")
    # First-run setup and the stats question must load in the frozen app.
    from flowstate.ui import consent, onboarding
    consent.ConsentDialog().close()
    assert onboarding.shortcut_conflict("ctrl+m")
    from flowstate import __version__
    (root / "runtime-check.json").write_text(json.dumps({"version": __version__, "qt": qVersion(),
                                                      "tabs": window.tabs.count(), "local_stats": True}), encoding="utf-8")
    window.close()
    sys.exit(0)

# Formats a sample with the real cached formatter model (GPU or CPU) inside
# the frozen runtime. Reads models only: nothing is downloaded or removed.
if "--verify-formatter" in sys.argv:
    import json
    from pathlib import Path
    from flowstate.text.formatter import SmartFormatter
    report = Path(sys.argv[sys.argv.index("--verify-formatter") + 1])
    SmartFormatter._remove_redundant_cpu_model = staticmethod(lambda: None)
    formatter = SmartFormatter()
    loaded = formatter.preload(allow_download=False)
    text = formatter.correct("Hey john can we talk tomorrow thanks sarah", budget_seconds=10) if loaded else ""
    report.write_text(json.dumps({"loaded": loaded, "runtime": formatter.runtime, "text": text}), encoding="utf-8")
    sys.exit(0 if loaded else 1)

from flowstate.__main__ import main

if __name__ == "__main__":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pelsynergy.flowstate.app")
    except Exception:
        pass
    sys.exit(main())
