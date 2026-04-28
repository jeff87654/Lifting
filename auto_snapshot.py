"""auto_snapshot.py — watch this repo and auto-commit code changes.

Run in the background:
    python auto_snapshot.py &        (Linux/macOS)
    Start-Process python auto_snapshot.py    (PowerShell)

Or just:
    python auto_snapshot.py

Watches all *.py, *.g, *.md files under the project root (respecting
.gitignore via the standard `git add -u` + `git add` flow).  When a file
is saved, waits DEBOUNCE_SECONDS for the dust to settle, then runs:

    git add -A    # honors .gitignore
    git commit -m "auto-snapshot YYYY-MM-DD HH:MM:SS"

Idempotent — no commit if nothing actually changed.

Logs to .git_snapshot.log (gitignored).
"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("watchdog not installed.  Run: pip install watchdog")
    sys.exit(1)

ROOT = Path(__file__).parent.resolve()
LOG = ROOT / ".git_snapshot.log"
DEBOUNCE_SECONDS = 8     # wait this long after last save before committing
WATCH_EXTS = {".py", ".g", ".md", ".json", ".sh", ".ps1"}

def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def commit_if_dirty():
    """Stage everything (.gitignore filters) and commit if there are changes."""
    # Check what changed
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        log(f"git status failed: {e}")
        return
    if not result.stdout.strip():
        return  # clean
    # Stage and commit
    files_changed = len(result.stdout.strip().splitlines())
    msg = f"auto-snapshot {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ({files_changed} files)"
    try:
        subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True,
                       capture_output=True)
        subprocess.run(["git", "commit", "-m", msg, "--no-verify"],
                       cwd=ROOT, check=True, capture_output=True, text=True)
        log(f"committed: {msg}")
    except subprocess.CalledProcessError as e:
        out = (e.stderr or e.stdout or b"").decode(errors="ignore") if isinstance(e.stderr, bytes) else (e.stderr or e.stdout or "")
        log(f"commit failed: {out.strip()[:300]}")

class SnapshotHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_event_t = 0.0
        self.pending = False

    def _matches(self, path):
        p = Path(path)
        if p.suffix.lower() not in WATCH_EXTS:
            return False
        # cheap blacklist for known-noisy dirs (gitignore is the real filter,
        # but skipping these saves churn)
        for skip in ("predict_species_tmp", "parallel_s", ".git",
                     "__pycache__", "checkpoints"):
            if skip in p.parts:
                return False
        return True

    def on_modified(self, event):
        if event.is_directory or not self._matches(event.src_path):
            return
        self.last_event_t = time.time()
        self.pending = True

    def on_created(self, event):
        self.on_modified(event)

    def on_moved(self, event):
        self.on_modified(event)

def main():
    log(f"watching {ROOT} (debounce={DEBOUNCE_SECONDS}s, extensions={sorted(WATCH_EXTS)})")
    handler = SnapshotHandler()
    obs = Observer()
    obs.schedule(handler, str(ROOT), recursive=True)
    obs.start()
    try:
        while True:
            time.sleep(2)
            if handler.pending and (time.time() - handler.last_event_t) > DEBOUNCE_SECONDS:
                handler.pending = False
                commit_if_dirty()
    except KeyboardInterrupt:
        log("stopped via KeyboardInterrupt")
        obs.stop()
    obs.join()

if __name__ == "__main__":
    main()
