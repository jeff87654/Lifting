"""worker_status.py — at-a-glance snapshot of what each build_sn_v2 worker
is currently computing.

Scans predict_species_tmp/_two_factor_v2 for active super_batch / batch /
wreath logs (touched in the last N minutes), and for each prints:
  - which super-batch / combo it's running
  - current GROUP and JOB within the super-batch
  - latest pair-progress heartbeat
  - log age (seconds since last write — high age = stalled or quiet)

Usage:
    python worker_status.py                # default: 10 min window
    python worker_status.py --minutes 30   # widen the window
"""
from __future__ import annotations
import argparse
import re
import time
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
TMP = ROOT / "predict_species_tmp" / "_two_factor_v2"


def tail_n_lines(path: Path, n: int = 200) -> list[str]:
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            block = min(size, 64 * 1024)
            f.seek(size - block)
            data = f.read().decode("utf-8", errors="ignore")
        return data.splitlines()[-n:]
    except OSError:
        return []


def find_logs(window_seconds: int) -> list[Path]:
    cutoff = time.time() - window_seconds
    out = []
    if not TMP.exists():
        return out
    # Canonical worker log filenames; ignore leftover " - Copy" duplicates etc.
    canonical = {"super.log", "batch.log", "wreath.log", "c2.log"}
    for p in TMP.rglob("*.log"):
        if p.name not in canonical:
            continue
        try:
            if p.stat().st_mtime >= cutoff:
                out.append(p)
        except OSError:
            pass
    return sorted(out, key=lambda p: -p.stat().st_mtime)


PAT_GROUP = re.compile(r"^=== GROUP (\d+)/(\d+) ml=(\d+) jobs=(\d+) LEFT=(.+) ===")
PAT_JOB = re.compile(r"^  >> JOB (\d+)/(\d+) combo=(\S+) mode=(\S+) m_right=(\d+)")
PAT_PAIR = re.compile(r"^    \[t\+(\d+)ms\] pair (\d+)/(\d+) .*orb_so_far=(\d+)")
PAT_RESULT = re.compile(r"^RESULT (?:group=(\d+) )?(?:job=(\d+) )?predicted=(\d+) ")


def parse_log(path: Path) -> dict:
    lines = tail_n_lines(path, 400)
    info = {"path": path, "group": None, "job": None, "pair": None, "last_result": None}
    for ln in reversed(lines):
        if info["pair"] is None:
            m = PAT_PAIR.match(ln)
            if m:
                info["pair"] = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
                continue
        if info["last_result"] is None:
            m = PAT_RESULT.match(ln)
            if m:
                info["last_result"] = int(m.group(3))
        if info["job"] is None:
            m = PAT_JOB.match(ln)
            if m:
                info["job"] = (int(m.group(1)), int(m.group(2)), m.group(3), m.group(4))
        if info["group"] is None:
            m = PAT_GROUP.match(ln)
            if m:
                info["group"] = (int(m.group(1)), int(m.group(2)),
                                 int(m.group(4)), m.group(5))
        if info["group"] and info["job"]:
            break
    return info


def short(p: Path) -> str:
    parts = p.parts
    # Show the deepest meaningful directory: sb_xxxx, [combo], or _batch/[left]
    for tag in ("_super_batch", "_batch"):
        if tag in parts:
            i = parts.index(tag)
            return "/".join(parts[i:i + 2])
    # wreath / single-combo logs: last two dirs before the .log
    return "/".join(parts[-3:-1])


def fmt_age(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m {int(seconds % 60)}s"
    return f"{int(seconds / 3600)}h {int((seconds % 3600) / 60)}m"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=10,
                    help="window size in minutes (default 10)")
    args = ap.parse_args()

    logs = find_logs(args.minutes * 60)
    if not logs:
        print(f"No active worker logs found in last {args.minutes} min.")
        return

    now = time.time()
    print(f"=== {len(logs)} active worker log(s) in last {args.minutes} min ===\n")
    for log in logs:
        info = parse_log(log)
        age = now - log.stat().st_mtime
        print(f"[{short(log)}]  age={fmt_age(age)}")
        if info["group"]:
            g_idx, g_n, g_jobs, left = info["group"]
            print(f"  GROUP {g_idx}/{g_n}  jobs_in_group={g_jobs}  LEFT={left}")
        if info["job"]:
            j_idx, j_n, combo, mode = info["job"]
            print(f"  JOB   {j_idx}/{j_n}  combo={combo}  mode={mode}")
        if info["pair"]:
            p_done, p_total, orb = info["pair"]
            pct = 100 * p_done // max(p_total, 1)
            print(f"  PAIR  {p_done}/{p_total} ({pct}%)  orb_so_far={orb}")
        if info["last_result"] and not info["pair"]:
            print(f"  last RESULT predicted={info['last_result']}")
        if not (info["group"] or info["job"] or info["pair"]):
            print("  (no GROUP/JOB/pair lines yet — startup phase)")
        print()


if __name__ == "__main__":
    main()
