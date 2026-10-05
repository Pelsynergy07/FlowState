"""Content-free, persistent local counters and consent-gated PostHog events."""
from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import threading
import time
import urllib.request
from datetime import datetime, timezone
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from . import __version__

logger = logging.getLogger("flowstate.usage")
HOSTS = {"US": "https://us.i.posthog.com", "EU": "https://eu.i.posthog.com"}


def analytics_config() -> tuple[str, str]:
    try:
        data = json.loads(files("flowstate.resources").joinpath("analytics.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    key = os.environ.get("FLOWSTATE_POSTHOG_KEY", data.get("project_key", ""))
    region = os.environ.get("FLOWSTATE_POSTHOG_REGION", data.get("region", "US")).upper()
    return (key if isinstance(key, str) and key.startswith("phc_") else ""), HOSTS.get(region, HOSTS["US"])


class UsageStore:
    """Stores daily totals, never transcripts, filenames, audio, or error messages."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS daily (
                    day TEXT PRIMARY KEY, words INTEGER NOT NULL DEFAULT 0,
                    sessions INTEGER NOT NULL DEFAULT 0, successes INTEGER NOT NULL DEFAULT 0,
                    errors INTEGER NOT NULL DEFAULT 0, empty INTEGER NOT NULL DEFAULT 0,
                    audio_seconds REAL NOT NULL DEFAULT 0, processing_ms REAL NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS timings (id INTEGER PRIMARY KEY, milliseconds REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, payload TEXT NOT NULL, created REAL NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=2)
        try:
            with db:
                yield db
        finally:
            db.close()

    def record(self, words: int, audio_seconds: float, processing_ms: float, outcome: str,
               now: datetime | None = None) -> None:
        if outcome not in {"success", "error", "empty"}:
            raise ValueError("Unknown dictation outcome")
        now = now or datetime.now().astimezone()
        words, audio_seconds, processing_ms = max(0, int(words)), max(0, audio_seconds), max(0, processing_ms)
        with self.connect() as db:
            db.execute("""INSERT INTO daily(day,words,sessions,successes,errors,empty,audio_seconds,processing_ms)
                VALUES(?,?,1,?,?,?,?,?) ON CONFLICT(day) DO UPDATE SET
                words=words+excluded.words, sessions=sessions+1, successes=successes+excluded.successes,
                errors=errors+excluded.errors, empty=empty+excluded.empty,
                audio_seconds=audio_seconds+excluded.audio_seconds, processing_ms=processing_ms+excluded.processing_ms""",
                (now.date().isoformat(), words, int(outcome == "success"), int(outcome == "error"),
                 int(outcome == "empty"), audio_seconds, processing_ms if outcome == "success" else 0))
            if outcome == "success":
                db.execute("INSERT INTO timings(milliseconds) VALUES(?)", (processing_ms,))
                db.execute("DELETE FROM timings WHERE id NOT IN (SELECT id FROM timings ORDER BY id DESC LIMIT 1000)")

    def snapshot(self) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT COALESCE(SUM(words),0),COALESCE(SUM(sessions),0),COALESCE(SUM(successes),0),"
                             "COALESCE(SUM(errors),0),COALESCE(SUM(empty),0),COALESCE(SUM(audio_seconds),0) FROM daily").fetchone()
            timings = [r[0] for r in db.execute("SELECT milliseconds FROM timings ORDER BY milliseconds")]
            days = db.execute("SELECT day,words,sessions FROM daily ORDER BY day DESC LIMIT 7").fetchall()
        def percentile(p):
            if not timings:
                return None
            index = (len(timings) - 1) * p
            low, high = int(index), min(int(index) + 1, len(timings) - 1)
            return (timings[low] + (timings[high] - timings[low]) * (index - low)) / 1000
        return dict(zip(("words", "sessions", "successes", "errors", "empty", "audio_seconds"), row),
                    median_seconds=percentile(.5), p95_seconds=percentile(.95), days=days,
                    active_days=self.active_days())

    def active_days(self) -> int:
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM daily WHERE words > 0").fetchone()[0]

    def reset(self) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM daily")
            db.execute("DELETE FROM timings")


class UsageTracker:
    """Network activity runs on a daemon; disabled means no analytics requests."""

    def __init__(self, store: UsageStore, config_store, key: str | None = None, host: str | None = None):
        self.store, self.config_store = store, config_store
        default_key, default_host = analytics_config()
        self.key, self.host = default_key if key is None else key, host or default_host
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._enabled = False
        self.last_sync = None
        self.sync_error = False
        self.config_store.subscribe(self.configure)
        self.configure(self.config_store.config)

    @property
    def configured(self):
        return bool(self.key) and self.host in HOSTS.values()

    def configure(self, config):
        with self._lock:
            enabled = config.analytics.enabled is True and self.configured
            changed = enabled and not self._enabled
            self._enabled = enabled
            if not enabled:
                with self.store.connect() as db:
                    db.execute("DELETE FROM outbox")
                    db.execute("DELETE FROM metadata WHERE key='anonymous_id'")
            elif changed:
                with self.store.connect() as db:
                    existing = db.execute("SELECT value FROM metadata WHERE key='anonymous_id'").fetchone()
                if existing is None:
                    self._enqueue("analytics_enabled", {})
            self._wake.set()

    def start(self):
        if self._thread is not None:
            return
        self._enqueue("app_opened", {})
        self._thread = threading.Thread(target=self._run, daemon=True, name="flowstate-usage")
        self._thread.start()

    def close(self):
        self._stop.set()
        self._wake.set()
        self.config_store.unsubscribe(self.configure)

    def record(self, words, audio_seconds, processing_ms, outcome):
        self.store.record(words, audio_seconds, processing_ms, outcome)
        event = {"success": "dictation_completed", "error": "dictation_failed", "empty": "dictation_empty"}[outcome]
        self._enqueue(event, {"word_count": max(0, int(words)), "audio_seconds": round(max(0, audio_seconds), 2),
                              "processing_ms": round(max(0, processing_ms)), "outcome": outcome})

    def _enqueue(self, event, properties):
        if event not in {"analytics_enabled", "app_opened", "dictation_completed", "dictation_failed", "dictation_empty"}:
            raise ValueError("Unknown analytics event")
        properties = {key: value for key, value in properties.items()
                      if key in {"word_count", "audio_seconds", "processing_ms", "outcome"}}
        for key, value in properties.items():
            if key == "outcome":
                if value not in {"success", "error", "empty"}:
                    raise ValueError("Invalid analytics outcome")
            elif not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("Analytics counters must be finite nonnegative numbers")
        with self._lock:
            if not self._enabled:
                return
            with self.store.connect() as db:
                row = db.execute("SELECT value FROM metadata WHERE key='anonymous_id'").fetchone()
                identity = row[0] if row else str(uuid4())
                if row is None:
                    db.execute("INSERT INTO metadata VALUES('anonymous_id',?)", (identity,))
                identifier = str(uuid4())
                payload = {"uuid": identifier, "event": event,
                           "timestamp": datetime.now(timezone.utc).isoformat(),
                           "properties": {"distinct_id": identity, "app_version": __version__, "platform": "Windows",
                                          "$process_person_profile": False, "$geoip_disable": True, "$ip": "0.0.0.0",
                                          **properties}}
                db.execute("INSERT INTO outbox VALUES(?,?,?)", (identifier, json.dumps(payload), time.time()))
                db.execute("DELETE FROM outbox WHERE id NOT IN (SELECT id FROM outbox ORDER BY created DESC LIMIT 1000)")
            self._wake.set()

    def flush(self):
        with self._lock:
            if not self._enabled or self._stop.is_set():
                return
            with self.store.connect() as db:
                db.execute("DELETE FROM outbox WHERE created < ?", (time.time() - 30 * 86400,))
                rows = db.execute("SELECT id,payload FROM outbox ORDER BY created LIMIT 50").fetchall()
            if not rows:
                return
        request = urllib.request.Request(self.host + "/batch/", method="POST",
            data=json.dumps({"api_key": self.key, "batch": [json.loads(r[1]) for r in rows]}).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "FlowState-Usage"})
        # Recheck immediately before initiating a request after consent changes.
        if not self._enabled or self.config_store.config.analytics.enabled is not True:
            return
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                if not 200 <= response.status < 300:
                    raise OSError("Analytics service unavailable")
                response.read(1024)
        except Exception:
            self.sync_error = True
            return  # Same UUIDs remain queued, preventing retry double-counting.
        with self._lock, self.store.connect() as db:
            db.executemany("DELETE FROM outbox WHERE id=?", [(row[0],) for row in rows])
            self.last_sync = datetime.now().astimezone()
            self.sync_error = False

    def _run(self):
        while not self._stop.is_set():
            self._wake.wait(60)
            self._wake.clear()
            try:
                self.flush()
            except Exception:
                logger.debug("Usage sync unavailable", exc_info=True)
            # A failing endpoint must not cause a busy retry loop.
            self._stop.wait(30)
