"""Verify a published S_n output tree and re-derive FPF(n), L_FPF(n), a(n).

Works on an extracted tree or directly on a .tar.xz archive (streamed, nothing
is extracted to disk).  For each requested n it checks:

  (1) completeness -- every FPF combo of n (one transitive group per orbit
      block, enumerated independently here from NrTransitiveGroups) has
      exactly one output file, and there are no unexpected files;
  (2) per-file integrity -- the '# deduped: N' header equals the number of
      generator lines in the file (catches truncated files);

and then re-tallies

  FPF(n)   = sum of '# deduped:'   headers  (subgroup classes, A000638 term)
  L_FPF(n) = sum of '# class_sum:' headers  (labelled count, A116693 term)
  a(n)     = FPF(n) + a(n-1)                (A000638)

comparing against OEIS where OEIS has the term and against this project's
values for n >= 19.

Usage:
  python verify_outputs.py --n 21 --tar parallel_sn_21.tar.xz
  python verify_outputs.py --n 21                    # tree at ./21/
  python verify_outputs.py --n 2-17 --tar parallel_sn_1_17.tar.xz
  python verify_outputs.py --n 21 --root some/dir --csv counts_21.csv

--root is the directory that CONTAINS the per-n directories (<root>/<n>/...);
it defaults to this script's directory, and parallel_sn_topt/<n>/ (the layout
of the in-repo archives) is also accepted.  Exit status 0 iff every check
passes.
"""
import argparse
import csv
import re
import sys
import tarfile
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

# NrTransitiveGroups(d), GAP transitive groups library.
NUM_TRANSITIVE = {2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50, 9: 34,
                  10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104, 16: 1954,
                  17: 10, 18: 983, 19: 8, 20: 1117, 21: 164, 22: 59, 23: 7}

# A000638: OEIS through n=18; n=19..21 computed by this project.
A000638 = {0: 1, 1: 1, 2: 2, 3: 4, 4: 11, 5: 19, 6: 56, 7: 96, 8: 296,
           9: 554, 10: 1593, 11: 3094, 12: 10723, 13: 20832, 14: 75154,
           15: 159129, 16: 686165, 17: 1466358, 18: 7274651,
           19: 16745233, 20: 104994596, 21: 245393739}
A000638_OEIS_MAX = 18

# A116693 (labelled FPF subgroups of S_n), OEIS through n=18; n=19..21 from
# this project.
A116693 = {2: 1, 3: 2, 4: 15, 5: 50, 6: 874, 7: 3515, 8: 94638, 9: 634630,
           10: 18368060, 11: 149965474, 12: 7392944314, 13: 61596293433,
           14: 4042125261152, 15: 46326163964879, 16: 4045711099761347,
           17: 47868661342996788, 18: 6066544790946772416,
           19: 84018278813226053237,
           20: 15346960414746000263759,
           21: 226997825369382551513614}

DEDUPED_RE = re.compile(rb"^# deduped:\s*(\d+)", re.M)
CLASS_SUM_RE = re.compile(rb"^# class_sum:\s*(\d+)", re.M)
CHUNK = 1 << 22


# ---------------------------------------------------------------- combos ---

def fpf_partitions(n):
    def gen(remaining, max_part, prefix):
        if remaining == 0:
            yield prefix
            return
        for p in range(min(remaining, max_part), 1, -1):
            yield from gen(remaining - p, p, prefix + [p])
    return list(gen(n, n, []))


def combos_for_partition(partition):
    by_d = defaultdict(int)
    for d in partition:
        by_d[d] += 1
    degrees = sorted(by_d)

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
        d, rest = degs[0], degs[1:]
        for ts in multisets(list(range(1, NUM_TRANSITIVE[d] + 1)), by_d[d]):
            for tail in cartesian(rest):
                yield [(d, t) for t in ts] + tail

    for combo in cartesian(degrees):
        yield tuple(sorted(combo))


def combo_name(combo):
    return "_".join(f"[{d},{t}]" for d, t in combo)


def part_name(partition):
    return "[" + ",".join(str(d) for d in partition) + "]"


def expected_files(n):
    """{(partition_dir, combo_stem)} for every FPF combo of n."""
    out = set()
    for partition in fpf_partitions(n):
        pn = part_name(partition)
        for combo in combos_for_partition(partition):
            out.add((pn, combo_name(combo)))
    return out


# ------------------------------------------------------------ file scan ---

def scan_stream(f):
    """Return (deduped, class_sum, generator_lines) for one output file.

    A generator line is a line starting with '['; GAP wraps long lines with
    a trailing backslash, and continuation lines never start with '['.
    """
    head = f.read(CHUNK)
    m = DEDUPED_RE.search(head[:8192])
    deduped = int(m.group(1)) if m else None
    m = CLASS_SUM_RE.search(head[:8192])
    class_sum = int(m.group(1)) if m else None
    lines = (1 if head.startswith(b"[") else 0) + head.count(b"\n[")
    prev_last = head[-1:]
    while True:
        buf = f.read(CHUNK)
        if not buf:
            break
        lines += buf.count(b"\n[")
        if prev_last == b"\n" and buf.startswith(b"["):
            lines += 1
        prev_last = buf[-1:]
    return deduped, class_sum, lines


def iter_dir(root, n):
    base = None
    for cand in (root / str(n), root / "parallel_sn_topt" / str(n)):
        if cand.is_dir():
            base = cand
            break
    if base is None:
        return
    for part_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        for g in sorted(part_dir.glob("*.g")):
            with g.open("rb") as f:
                yield part_dir.name, g.stem, scan_stream(f)


def iter_tar(tar_path, ns):
    """Stream every <n>/<partition>/<combo>.g member of the archive."""
    with tarfile.open(tar_path, "r|*") as tf:
        for member in tf:
            if not member.isfile() or not member.name.endswith(".g"):
                continue
            parts = member.name.split("/")
            if len(parts) < 3 or not parts[-3].isdigit():
                continue
            n = int(parts[-3])
            if n not in ns:
                continue
            f = tf.extractfile(member)
            yield n, parts[-2], parts[-1][:-2], scan_stream(f)


# ----------------------------------------------------------------- main ---

def parse_ns(spec):
    if "-" in spec:
        lo, hi = spec.split("-")
        return list(range(int(lo), int(hi) + 1))
    return [int(x) for x in spec.split(",")]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", required=True, help="21, or a range 2-21, or 19,20")
    ap.add_argument("--root", type=Path, default=HERE)
    ap.add_argument("--tar", type=Path, help="read a .tar.xz instead of a tree")
    ap.add_argument("--csv", type=Path, help="write n,partition,combo,classes,labelled_sum")
    args = ap.parse_args()
    ns = parse_ns(args.n)
    t0 = time.time()

    seen = {n: {} for n in ns}          # n -> {(part, combo): (ded, cs, lines)}
    if args.tar:
        src = iter_tar(args.tar, set(ns))
    else:
        src = ((n, p, c, r) for n in ns for p, c, r in iter_dir(args.root, n))
    for n, part, combo, res in src:
        seen[n][(part, combo)] = res

    ok_all = True
    rows = []
    for n in ns:
        files = seen[n]
        expect = expected_files(n)
        missing = sorted(expect - files.keys())
        extra = sorted(files.keys() - expect)
        bad = sorted(k for k, (ded, cs, lines) in files.items()
                     if ded is None or ded != lines)
        no_cs = sorted(k for k, (ded, cs, lines) in files.items() if cs is None)
        fpf = sum(ded or 0 for ded, cs, lines in files.values())
        l_fpf = sum(cs or 0 for ded, cs, lines in files.values())

        print(f"n={n}: {len(fpf_partitions(n))} FPF partitions, "
              f"{len(expect)} expected combos, {len(files)} files")
        print(f"  missing {len(missing)}, extra {len(extra)}, "
              f"header/line mismatch {len(bad)}, missing class_sum {len(no_cs)}")
        for label, items in (("missing", missing), ("extra", extra),
                             ("mismatch", bad)):
            for p, c in items[:10]:
                print(f"    {label}: {p}/{c}.g {files.get((p, c), '')}")
        # Older archives (n <= 19) predate the labelled harvest and carry no
        # '# class_sum:' headers; that only disables the L_FPF check.
        n_ok = not (missing or extra or bad)

        print(f"  FPF({n})   = {fpf:,}")
        if n - 1 in A000638:
            a_n = fpf + A000638[n - 1]
            print(f"  a({n})     = FPF({n}) + a({n - 1}) = {a_n:,}", end="")
            if n in A000638:
                src_tag = "OEIS" if n <= A000638_OEIS_MAX else "project"
                match = a_n == A000638[n]
                n_ok &= match
                print(f"   [{src_tag} {A000638[n]:,}: {'OK' if match else 'MISMATCH'}]")
            else:
                print()
        if no_cs:
            print(f"  L_FPF({n}) not checked ({len(no_cs)} files without class_sum)")
        elif n in A116693:
            print(f"  L_FPF({n}) = {l_fpf:,}", end="")
            src_tag = "OEIS" if n <= A000638_OEIS_MAX else "project"
            match = l_fpf == A116693[n]
            n_ok &= match
            print(f"   [{src_tag} A116693: {'OK' if match else 'MISMATCH'}]")
        else:
            print(f"  L_FPF({n}) = {l_fpf:,}")
        print(f"  {'PASS' if n_ok else 'FAIL'}\n")
        ok_all &= n_ok
        for (p, c), (ded, cs, lines) in sorted(files.items()):
            rows.append((n, p, c, ded, cs))

    if args.csv:
        with args.csv.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["n", "partition", "combo", "classes", "labelled_sum"])
            w.writerows(rows)
        print(f"wrote {len(rows)} rows to {args.csv}")
    print(f"elapsed {time.time() - t0:.1f}s")
    print("ALL PASS" if ok_all else "FAILURES PRESENT")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
