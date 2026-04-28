"""Compare rerun combos (from W710-W715) to their backed-up old counts."""
from pathlib import Path

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
BK = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_stale_sn_backup")


def deduped(path):
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if line.startswith("# deduped:"):
                    try: return int(line.split(":",1)[1].strip())
                    except ValueError: return None
                if line.startswith("["):
                    return None
    except OSError:
        return None


same_ct = 0
same_sum_old = same_sum_new = 0
inc_ct = 0
inc_sum_old = inc_sum_new = 0
dec_ct = 0
dec_sum_old = dec_sum_new = 0
pending_ct = 0
increases = []
decreases = []

for bkdir in BK.iterdir():
    if not bkdir.is_dir() or not bkdir.name.startswith("["):
        continue
    curdir = CUR / bkdir.name
    for bf in bkdir.glob("*.g"):
        bc = deduped(bf)
        if bc is None: continue
        cf = curdir / bf.name
        if not cf.is_file():
            pending_ct += 1
            continue
        cc = deduped(cf)
        if cc is None:
            pending_ct += 1
            continue
        if cc == bc:
            same_ct += 1
            same_sum_old += bc; same_sum_new += cc
        elif cc > bc:
            inc_ct += 1
            inc_sum_old += bc; inc_sum_new += cc
            increases.append((bkdir.name, bf.name, bc, cc))
        else:
            dec_ct += 1
            dec_sum_old += bc; dec_sum_new += cc
            decreases.append((bkdir.name, bf.name, bc, cc))

print(f"Combos re-run since backup: {same_ct + inc_ct + dec_ct}")
print(f"  same:      {same_ct:>6}  old={same_sum_old:>8} new={same_sum_new:>8}  delta=0")
print(f"  increased: {inc_ct:>6}  old={inc_sum_old:>8} new={inc_sum_new:>8}  delta=+{inc_sum_new-inc_sum_old}")
print(f"  decreased: {dec_ct:>6}  old={dec_sum_old:>8} new={dec_sum_new:>8}  delta=-{dec_sum_old-dec_sum_new}")
print(f"Still pending: {pending_ct}")
print()
if increases:
    increases.sort(key=lambda x: -(x[3] - x[2]))
    print("Top 10 increases:")
    for part, cn, o, n in increases[:10]:
        print(f"  {part}/{cn}: {o} -> {n}  (+{n - o})")
if decreases:
    print()
    print("DECREASES (concerning):")
    for part, cn, o, n in decreases[:10]:
        print(f"  {part}/{cn}: {o} -> {n}  (-{o - n})")
