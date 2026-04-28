"""Move my 86 W810-813 files to backup, then re-launch FindFPFClassesForPartition
to compute them with proper dedup."""
import os, shutil
import datetime
from pathlib import Path

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18/[6,4,4,4]")
BAK = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_w810_813_backup/[6,4,4,4]")
BAK.mkdir(parents=True, exist_ok=True)

# Find files mtime after launch (8:30 PM = 20:30)
LAUNCH = datetime.datetime(2026, 4, 24, 20, 30).timestamp()
moved = 0
for f in CUR.glob("*.g"):
    if f.stat().st_mtime >= LAUNCH:
        # Verify cand == deduped (W810-813 signature)
        cand = ded = None
        with open(f) as fh:
            for line in fh:
                if line.startswith("# candidates:"):
                    cand = int(line.split(":",1)[1].strip())
                elif line.startswith("# deduped:"):
                    ded = int(line.split(":",1)[1].strip())
                    break
        if cand == ded:  # only my W810-813 outputs match this
            shutil.move(str(f), str(BAK / f.name))
            moved += 1

print(f"Moved {moved} files to {BAK}")
print(f"Remaining in {CUR}: {len(list(CUR.glob('*.g')))} files")
