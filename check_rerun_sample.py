"""Compare rerun combos against random_sample_backup to find mismatches."""
from pathlib import Path

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
BK = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_random_sample_backup")


def deduped(p):
    try:
        with open(p, errors="replace") as f:
            for line in f:
                if line.startswith("# deduped:"):
                    return int(line.split(":",1)[1].strip())
                if line.startswith("["):
                    return None
    except OSError:
        return None


done = 0; pending = 0
same = 0; inc = 0; dec = 0
inc_list = []; dec_list = []
sum_bk = 0; sum_new = 0

for pdir in BK.iterdir():
    if not pdir.is_dir() or not pdir.name.startswith("["): continue
    for bf in pdir.glob("*.g"):
        bc = deduped(bf)
        if bc is None: continue
        cf = CUR / pdir.name / bf.name
        if not cf.is_file():
            pending += 1
            continue
        cc = deduped(cf)
        if cc is None:
            pending += 1
            continue
        done += 1
        sum_bk += bc; sum_new += cc
        if cc == bc: same += 1
        elif cc > bc:
            inc += 1
            inc_list.append((pdir.name, bf.name, bc, cc))
        else:
            dec += 1
            dec_list.append((pdir.name, bf.name, bc, cc))

print(f"Reruns done: {done} / {done + pending} total sampled")
print(f"  same:      {same}")
print(f"  increased: {inc}    delta +{sum(x[3]-x[2] for x in inc_list)}")
print(f"  decreased: {dec}    delta -{sum(x[2]-x[3] for x in dec_list)}")
print(f"  pending:   {pending}")
print()
print(f"Sum backup (matched): {sum_bk:,}")
print(f"Sum current (matched): {sum_new:,}")
print(f"Net delta: {sum_new - sum_bk:+,}")
if inc_list:
    inc_list.sort(key=lambda x: -(x[3]-x[2]))
    print(f"Top 10 INCREASES:")
    for p, c, b, n in inc_list[:10]:
        print(f"  {p}/{c}: {b} -> {n}  (+{n-b})")
if dec_list:
    dec_list.sort(key=lambda x: -(x[2]-x[3]))
    print(f"Top 10 DECREASES:")
    for p, c, b, n in dec_list[:10]:
        print(f"  {p}/{c}: {b} -> {n}  (-{b-n})")
