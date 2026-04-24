"""Verify parallel_sn/<n> data against OEIS A000638 and per-partition references.

Usage:
    python verify_parallel_sn.py                       # verify all
    python verify_parallel_sn.py --n 13                # just one degree
    python verify_parallel_sn.py --fetch-oeis          # also pull from OEIS b-file

Two levels of checks:

1. Per-n total vs OEIS A000638:
     sum_{partition in parallel_sn/<n>/} total_classes[partition]
     + A000638(n-1)                     # inherited (subgroups fixing >= 1 point)
     == A000638(n)

2. Per-partition vs reference file (when available):
     s{11..14}_partition_classes_output.txt: "[ p1, p2 ]  | count"
     s17_orbit_type_counts.txt:              "[p1,p2]        count"
     FPF partitions (no 1-parts) in the reference should match our directory.
"""
import os, re, sys, argparse, urllib.request, urllib.error
from pathlib import Path

BASE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_sn")
REF_PARTITION = Path(r"C:/Users/jeffr/Downloads/Symmetric Groups/Partition")
REF_ORBIT = Path(r"C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache")

# OEIS A000638 hardcoded (can be cross-checked with --fetch-oeis)
A000638 = {
    0: 1, 1: 1, 2: 2, 3: 4, 4: 11, 5: 19, 6: 56, 7: 96, 8: 296, 9: 554,
    10: 1593, 11: 3094, 12: 10723, 13: 20832, 14: 75154, 15: 159129,
    16: 686165, 17: 1466358, 18: 7274651,
}

OEIS_B_URL = "https://oeis.org/A000638/b000638.txt"


def fetch_oeis_b():
    """Fetch A000638 b-file. Returns dict n->a(n) or None on failure."""
    try:
        with urllib.request.urlopen(OEIS_B_URL, timeout=10) as resp:
            data = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"  [warn] could not fetch OEIS b-file: {e}")
        return None
    out = {}
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) == 2:
            try:
                out[int(parts[0])] = int(parts[1])
            except ValueError:
                pass
    return out


_part_re = re.compile(r"\[\s*([\d\s,]+?)\s*\]")


def parse_partition_str(s):
    """'[ 13, 5 ]' -> (13, 5); '[13,5]' -> (13, 5); return None on fail."""
    m = _part_re.search(s)
    if not m:
        return None
    try:
        return tuple(int(x.strip()) for x in m.group(1).split(",") if x.strip())
    except ValueError:
        return None


def part_str(t):
    return "[" + ",".join(str(x) for x in t) + "]"


def partition_count_from_dir(partition_dir):
    """Get class count for a partition dir via summary.txt or per-combo .g headers."""
    summary = partition_dir / "summary.txt"
    if summary.is_file():
        with open(summary) as f:
            for line in f:
                if line.startswith("total_classes:"):
                    try:
                        return int(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
    # Fallback: sum # deduped from combo files
    total = 0
    for cf in partition_dir.glob("*.g"):
        try:
            with open(cf, errors="replace") as f:
                for line in f:
                    if line.startswith("# deduped:"):
                        total += int(line.split(":", 1)[1].strip())
                        break
                else:
                    # No header -- assume one-liner (small n cases)
                    with open(cf, errors="replace") as f2:
                        total += sum(
                            1 for line in f2
                            if line.strip().startswith("[")
                        )
        except (OSError, ValueError):
            pass
    return total


def load_partition_ref(n):
    """Load per-partition reference counts for S_n, or None if not available.

    Returns dict partition_tuple -> count. Only FPF partitions
    (no 1-parts) are included for our comparison.
    """
    if 11 <= n <= 14:
        f = REF_PARTITION / f"s{n}_partition_classes_output.txt"
        if not f.is_file():
            return None
        out = {}
        with open(f) as fh:
            for line in fh:
                m = re.match(r"\s*\[([^\]]*)\]\s*\|\s*(\d+)", line)
                if m:
                    part_body, cnt = m.group(1), int(m.group(2))
                    try:
                        part = tuple(int(x.strip()) for x in part_body.split(",") if x.strip())
                    except ValueError:
                        continue
                    out[part] = cnt
        # s14_partition_classes_output.txt is a GAP error dump (OOM) with no
        # data lines -- treat as unavailable.
        if not out:
            return None
        return out
    if n == 17:
        f = REF_ORBIT / "s17_orbit_type_counts.txt"
        if not f.is_file():
            return None
        out = {}
        with open(f) as fh:
            for line in fh:
                line = line.rstrip()
                if not line or line.startswith("#") or line.startswith("Orbit") or line.startswith("-"):
                    continue
                m = re.match(r"\[([^\]]*)\]\s+(\d+)", line)
                if m:
                    part_body, cnt = m.group(1), int(m.group(2))
                    try:
                        part = tuple(int(x.strip()) for x in part_body.split(",") if x.strip())
                    except ValueError:
                        continue
                    out[part] = cnt
        return out
    return None


def is_fpf_partition(part):
    """FPF (fixed-point-free) <-> no 1-part in the partition."""
    return 1 not in part


def verify_n(n, a000638):
    """Verify S_n: per-n total vs OEIS and per-partition vs reference."""
    print(f"\n=== S_{n} ===")
    n_dir = BASE / str(n)
    if not n_dir.is_dir():
        print(f"  [skip] {n_dir} does not exist")
        return True

    # Per-partition totals from our data
    our = {}
    for d in sorted(os.listdir(n_dir)):
        if not d.startswith("["):
            continue
        part = parse_partition_str(d)
        if part is None:
            continue
        pdir = n_dir / d
        if not pdir.is_dir():
            continue
        our[part] = partition_count_from_dir(pdir)

    fpf_total = sum(our.values())
    print(f"  partitions: {len(our)}")
    print(f"  FPF sum (ours): {fpf_total:,}")

    # Per-n check vs OEIS
    if n in a000638:
        target = a000638[n]
        inherited = a000638.get(n - 1, 0)
        expected_fpf = target - inherited
        match = (fpf_total == expected_fpf)
        print(f"  OEIS A000638({n}) = {target:,} = {inherited:,} inherited + "
              f"{expected_fpf:,} FPF")
        if match:
            print(f"  [PASS] total FPF matches OEIS")
        else:
            print(f"  [FAIL] FPF sum {fpf_total:,} != expected {expected_fpf:,}")
    else:
        print(f"  [skip] no OEIS value")
        match = None

    # Per-partition check vs reference
    ref = load_partition_ref(n)
    if ref is None:
        print(f"  [skip] no per-partition reference for S_{n}")
        return match if match is not None else True

    ref_fpf = {p: c for p, c in ref.items() if is_fpf_partition(p)}
    print(f"  reference FPF partitions: {len(ref_fpf)}")

    mismatches = []
    missing_in_ours = []
    missing_in_ref = []
    for part, ref_count in ref_fpf.items():
        if part not in our:
            missing_in_ours.append((part, ref_count))
        elif our[part] != ref_count:
            mismatches.append((part, our[part], ref_count))
    for part, our_count in our.items():
        if part not in ref_fpf:
            missing_in_ref.append((part, our_count))

    if mismatches:
        print(f"  [FAIL] {len(mismatches)} partitions mismatch:")
        for part, oc, rc in mismatches[:10]:
            print(f"    {part_str(part)}: ours={oc}, ref={rc}")
    if missing_in_ours:
        print(f"  [FAIL] {len(missing_in_ours)} partitions missing from our data:")
        for part, rc in missing_in_ours[:10]:
            print(f"    {part_str(part)}: ref={rc}")
    if missing_in_ref:
        print(f"  [WARN] {len(missing_in_ref)} partitions in our data not in ref "
              f"(may be non-FPF or ref incomplete):")
        for part, oc in missing_in_ref[:5]:
            print(f"    {part_str(part)}: ours={oc}")

    if not mismatches and not missing_in_ours:
        print(f"  [PASS] all {len(ref_fpf)} reference partitions match")
        return match if match is not None else True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=None,
                        help="verify only this S_n")
    parser.add_argument("--fetch-oeis", action="store_true",
                        help="cross-check hardcoded A000638 against OEIS b-file")
    args = parser.parse_args()

    a000638 = dict(A000638)
    if args.fetch_oeis:
        print("Fetching OEIS A000638 b-file...")
        remote = fetch_oeis_b()
        if remote is not None:
            for n, v in A000638.items():
                if n in remote and remote[n] != v:
                    print(f"  [WARN] hardcoded A000638({n})={v} != OEIS {remote[n]}")
                elif n in remote:
                    print(f"  A000638({n}) = {v} confirmed")
            # Extend with any remote values we didn't have
            for n, v in remote.items():
                if n not in a000638:
                    a000638[n] = v

    ns = [args.n] if args.n else sorted(
        int(x) for x in os.listdir(BASE)
        if x.isdigit() and (BASE / x).is_dir()
    )

    all_pass = True
    for n in ns:
        if not verify_n(n, a000638):
            all_pass = False

    print()
    print("=" * 60)
    print("ALL PASS" if all_pass else "FAILURES DETECTED")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
