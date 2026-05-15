"""Combo enumeration and combo-file format helpers.

A *combo* is the basic unit of the build: a sorted tuple of
`(degree, transitive-group-index)` pairs that fixes one transitive group per
block of the orbit partition.  These functions are all pure and stateless;
they read the output tree only via paths the caller hands in.
"""
from __future__ import annotations
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


def is_complete_combo_file(path):
    """Verify a combo .g file is complete: # deduped: N matches the count of
    generator lines.  Returns True if valid, False if missing/truncated/inconsistent.
    Used by resume-skip to detect partial files left by killed mid-write GAP runs."""
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
    return actual == expected
