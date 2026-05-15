"""Verify S20 output tree integrity.

Two independent checks:
  (1) Per-partition completeness — for each FPF partition of 20, enumerate the
      expected combos via the same combo_filename scheme as build_sn_topt, then
      assert every expected combo has an output file (no missing) and the
      partition dir has no UNEXPECTED files (no rogue combos).
  (2) Per-file integrity — for each .g file, parse '# deduped: N' from the
      header and count the number of generator-list lines (lines starting with
      '['). Assert N == actual_count. Catches silent truncations.

Prints a summary and per-error details.  Exit 0 on success, 1 on any error.
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting\parallel_sn_topt_v3\20")
NUM_TRANS_JSON = Path(r"C:\Users\jeffr\Downloads\Lifting\parallel_sn_topt_v3\_num_transitive.json")
N = 20

DEDUPED_RE = re.compile(rb"^# deduped:\s*(\d+)")


def fpf_partitions(n):
    def gen(remaining, max_part, prefix):
        if remaining == 0:
            yield prefix
            return
        for p in range(min(remaining, max_part), 1, -1):
            yield from gen(remaining - p, p, prefix + [p])
    return list(gen(n, n, []))


def combos_for_partition(partition, num_transitive):
    by_d = {}
    for d in partition:
        by_d[d] = by_d.get(d, 0) + 1
    degrees = sorted(by_d.keys())

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


def check_file(path: Path) -> tuple[int | None, int, bool]:
    """Returns (claimed_count, actual_count, ok).  claimed_count=None if header
    missing/unparseable.  actual_count = number of lines starting with '['."""
    claimed = None
    actual = 0
    try:
        with path.open("rb") as f:
            for line in f:
                if claimed is None:
                    m = DEDUPED_RE.match(line)
                    if m:
                        claimed = int(m.group(1))
                if line.startswith(b"["):
                    actual += 1
    except OSError as e:
        return (None, 0, False)
    if claimed is None:
        return (None, actual, False)
    return (claimed, actual, claimed == actual)


def main() -> int:
    t0 = time.time()
    num_transitive = {int(k): v for k, v in json.loads(NUM_TRANS_JSON.read_text()).items()}
    partitions = fpf_partitions(N)
    print(f"S{N} FPF partitions: {len(partitions)}")

    # --- check 1: per-partition completeness ---
    missing_combos: list[tuple[str, str]] = []        # (partition_dir, combo_name)
    extra_combos: list[tuple[str, str]] = []
    expected_per_partition: dict[str, int] = {}

    for partition in partitions:
        part_name = part_dirname(partition)
        part_dir = ROOT / part_name
        expected_combos = set()
        for combo in combos_for_partition(partition, num_transitive):
            expected_combos.add(combo_filename(combo))
        expected_per_partition[part_name] = len(expected_combos)
        if not part_dir.exists():
            for c in expected_combos:
                missing_combos.append((part_name, c))
            continue
        existing = set(p.stem for p in part_dir.glob("*.g"))
        for missing in expected_combos - existing:
            missing_combos.append((part_name, missing))
        for extra in existing - expected_combos:
            extra_combos.append((part_name, extra))

    total_expected = sum(expected_per_partition.values())
    print(f"S{N} expected combos: {total_expected}")
    print(f"  missing: {len(missing_combos)}")
    print(f"  extra:   {len(extra_combos)}")
    if missing_combos:
        print("  --- missing combos (first 10) ---")
        for p, c in missing_combos[:10]:
            print(f"    {p}/{c}.g")
        if len(missing_combos) > 10:
            print(f"    ... and {len(missing_combos) - 10} more")
    if extra_combos:
        print("  --- extra combos (first 10) ---")
        for p, c in extra_combos[:10]:
            print(f"    {p}/{c}.g")
        if len(extra_combos) > 10:
            print(f"    ... and {len(extra_combos) - 10} more")

    # --- check 2: per-file integrity ---
    print(f"\nScanning per-file integrity...")
    bad_files: list[tuple[Path, int | None, int]] = []
    n_files = 0
    n_ok = 0
    for partition in partitions:
        part_dir = ROOT / part_dirname(partition)
        if not part_dir.exists():
            continue
        for g in part_dir.glob("*.g"):
            n_files += 1
            claimed, actual, ok = check_file(g)
            if ok:
                n_ok += 1
            else:
                bad_files.append((g, claimed, actual))
    print(f"S{N} files scanned: {n_files}, ok: {n_ok}, mismatch/unreadable: {len(bad_files)}")
    if bad_files:
        print("  --- bad files (first 10) ---")
        for path, claimed, actual in bad_files[:10]:
            rel = path.relative_to(ROOT)
            print(f"    {rel}: claimed={claimed} actual={actual}")
        if len(bad_files) > 10:
            print(f"    ... and {len(bad_files) - 10} more")

    elapsed = time.time() - t0
    print(f"\nelapsed: {elapsed:.1f}s")

    ok = (len(missing_combos) == 0
          and len(extra_combos) == 0
          and len(bad_files) == 0)
    print()
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
