"""Combo enumeration and combo-file format helpers.

A *combo* is the basic unit of the build: a sorted tuple of
`(degree, transitive-group-index)` pairs that fixes one transitive group per
block of the orbit partition.  These functions are all pure and stateless;
they read the output tree only via paths the caller hands in.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path


def fpf_partitions(n):
    """All partitions of n into parts >= 2, sorted descending."""
    def gen(remaining, max_part, prefix):
        if remaining == 0:
            yield prefix
            return
        for p in range(min(remaining, max_part), 1, -1):
            yield from gen(remaining - p, p, prefix + [p])
    return list(gen(n, n, []))


def combos_for_partition(partition, num_transitive):
    """Enumerate combos = list of (d, t) tuples.  For repeated d's, t's are
    sorted ascending so each S_n-equivalence class is enumerated exactly once.

    `num_transitive` is a dict {d: NrTransitiveGroups(d)}."""
    # Group by degree
    by_d = {}
    for d in partition:
        by_d[d] = by_d.get(d, 0) + 1
    degrees = sorted(by_d.keys())

    # For each distinct degree d with multiplicity m, choose a multiset of size m
    # from {1..num_transitive[d]} (with repetition, sorted ascending).
    def multisets(items, k):
        if k == 0:
            yield ()
            return
        for i, x in enumerate(items):
            for rest in multisets(items[i:], k - 1):
                yield (x,) + rest

    def cartesian(degs):
        if not degs:
            yield []
            return
        d = degs[0]
        rest = degs[1:]
        for ts in multisets(list(range(1, num_transitive[d] + 1)), by_d[d]):
            for tail in cartesian(rest):
                yield [(d, t) for t in ts] + tail

    for combo in cartesian(degrees):
        yield tuple(sorted(combo))


def combo_filename(combo):
    return "_".join(f"[{d},{t}]" for d, t in sorted(combo))


def part_dirname(partition):
    return "[" + ",".join(str(d) for d in partition) + "]"


def trailing_twos(partition):
    n = 0
    for d in reversed(partition):
        if d == 2:
            n += 1
        else:
            break
    return n


def left_class_count(left_combo, m_left, sn_dir):
    """Read the # deduped: header from the LEFT source file to gate
    super-batching.  Returns the class count, or 0 if source is missing
    (which routes the LEFT to standalone-batch as a safe default)."""
    parts = sorted([d for d, _ in left_combo], reverse=True)
    part_str = "[" + ",".join(str(p) for p in parts) + "]"
    src = Path(sn_dir) / str(m_left) / part_str / f"{combo_filename(left_combo)}.g"
    try:
        with open(src, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^# deduped:\s*(\d+)", line)
                if m:
                    return int(m.group(1))
                if line.startswith("["):
                    break  # no header found before generators
    except OSError:
        pass
    return 0


# --- Completeness cache ------------------------------------------------------
# `is_complete_combo_file` must read a combo .g IN FULL to count its generator
# lines (to check `# deduped: N` == count).  On a resume/retry-round scan that
# means re-reading the entire output tree -- ~22 GB across ~49k files for S21,
# and the heavy combos are huge (one is 1.6 GB).  That full re-read is the bulk
# of orchestrator startup time.
#
# This cache records (size, mtime_ns) for files that PASSED the full check, and
# is persisted to `<out>/_complete_cache.json`.  A later scan trusts the cache
# only when BOTH size and mtime_ns still match, so a recomputed / truncated /
# externally-changed file always falls through to a fresh full verify -- the
# cache can never report a stale "complete".  Because each scan re-saves the
# cache (including any newly-verified files), each restart full-reads only the
# delta of combos finished since the previous scan, not the whole tree.
#
# Orchestrator-process-local: workers never call is_complete_combo_file, so the
# in-memory dict needs no cross-process locking.
_complete_cache = None             # dict: abspath(str) -> [size, mtime_ns]
_complete_cache_path = None        # sidecar json path
_complete_cache_dirty = False


def init_completeness_cache(out_root):
    """Point the cache at <out_root>/_complete_cache.json and load it.  Call once
    at orchestrator startup, before the first output-tree scan."""
    global _complete_cache, _complete_cache_path, _complete_cache_dirty
    _complete_cache_path = os.path.join(str(out_root), "_complete_cache.json")
    _complete_cache_dirty = False
    try:
        with open(_complete_cache_path, encoding="utf-8") as f:
            _complete_cache = json.load(f)
    except (OSError, ValueError):
        _complete_cache = {}


def save_completeness_cache():
    """Atomically persist the cache if it changed.  Cheap to call repeatedly
    (no-op when nothing was added since the last save)."""
    global _complete_cache_dirty
    if (_complete_cache_path is None or _complete_cache is None
            or not _complete_cache_dirty):
        return
    tmp = f"{_complete_cache_path}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_complete_cache, f)
        os.replace(tmp, _complete_cache_path)
        _complete_cache_dirty = False
    except OSError:
        pass


def _cache_mark_complete(path, st):
    global _complete_cache_dirty
    if _complete_cache is None:
        return
    _complete_cache[os.path.abspath(str(path))] = [st.st_size, st.st_mtime_ns]
    _complete_cache_dirty = True


def is_complete_combo_file(path):
    """Verify a combo .g file is complete: # deduped: N matches the count of
    generator lines.  Returns True if valid, False if missing/truncated/inconsistent.
    Used by resume-skip to detect partial files left by killed mid-write GAP runs.

    Fast path: if the completeness cache holds this path with a matching
    (size, mtime_ns), trust it -- the file is byte-for-byte the one previously
    verified complete.  Otherwise do the exact full-read check and cache the
    result on success.  When the cache is uninitialised this is a plain extra
    stat() over the original behaviour."""
    try:
        st = os.stat(path)
    except OSError:
        return False
    if _complete_cache is not None:
        rec = _complete_cache.get(os.path.abspath(str(path)))
        if rec is not None and rec[0] == st.st_size and rec[1] == st.st_mtime_ns:
            return True
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeError):
        return False
    # Strip GAP line-continuation characters ("\<newline>") so generator lines
    # that wrap across multiple physical lines count as one.
    joined = re.sub(r"\\\r?\n", "", text)
    m = re.search(r"^# deduped:\s*(\d+)\s*$", joined, re.MULTILINE)
    if not m:
        return False
    expected = int(m.group(1))
    actual = sum(1 for ln in joined.splitlines() if ln.startswith("["))
    if actual != expected:
        return False
    _cache_mark_complete(path, st)
    return True
