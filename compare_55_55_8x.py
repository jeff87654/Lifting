"""Compare current vs backups for all [5,5]_[5,5]_[8,*] combos in [8,5,5]."""
from pathlib import Path

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18/[8,5,5]")
PRE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_prebugfix_backup/[8,5,5]")
BF1 = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_bugfix1_backup/[8,5,5]")
RS  = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_random_sample_backup/[8,5,5]")


def deduped(p):
    if not p.is_file():
        return None
    try:
        with open(p, errors="replace") as f:
            for line in f:
                if line.startswith("# deduped:"):
                    return int(line.split(":", 1)[1].strip())
                if line.startswith("["):
                    return None
    except OSError:
        return None
    return None


print(f"{'k':>3}  {'cur':>6}  {'pre':>6}  {'bf1':>6}  {'rs':>6}  notes")
print("-" * 55)
sum_cur = 0; sum_pre = 0; sum_bf1 = 0
diff_pre = 0; diff_bf1 = 0
for k in range(1, 51):
    name = f"[5,5]_[5,5]_[8,{k}].g"
    cc = deduped(CUR / name)
    pc = deduped(PRE / name)
    bc = deduped(BF1 / name)
    rc = deduped(RS / name)
    notes = []
    if cc is not None and pc is not None and cc != pc:
        notes.append(f"cur-pre={cc-pc:+d}")
        diff_pre += (cc - pc)
    if cc is not None and bc is not None and cc != bc:
        notes.append(f"cur-bf1={cc-bc:+d}")
        diff_bf1 += (cc - bc)
    if cc is not None: sum_cur += cc
    if pc is not None: sum_pre += pc
    if bc is not None: sum_bf1 += bc
    print(f"{k:>3}  {cc!s:>6}  {pc!s:>6}  {bc!s:>6}  {rc!s:>6}  {' '.join(notes)}")

print("-" * 55)
print(f"sums: cur={sum_cur}  pre={sum_pre}  bf1={sum_bf1}")
print(f"deltas:  cur-pre={diff_pre:+d}   cur-bf1={diff_bf1:+d}")
