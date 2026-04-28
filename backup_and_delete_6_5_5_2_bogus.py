"""Back up the 80 bogus combo files in [6,5,5,2] (those containing [5,5])
into a timestamped tar archive, then delete them so the worker can re-run
with the fixed _SnFastPathFPFSubdirects code."""
import os
import tarfile
import datetime

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\[6,5,5,2]"
TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
TAR_PATH = rf"C:\Users\jeffr\Downloads\Lifting\parallel_s18\[6,5,5,2]_bogus_backup_{TS}.tar.gz"

# Identify affected files: anything with [5,5] in the name
affected = []
for name in sorted(os.listdir(BASE)):
    if name.endswith('.g') and '[5,5]' in name and 'backup' not in name and 'Copy' not in name:
        affected.append(name)

print(f"Found {len(affected)} files with [5,5] in name.")

# Create backup tar
print(f"Creating backup: {TAR_PATH}")
total_bytes = 0
with tarfile.open(TAR_PATH, "w:gz") as tar:
    for name in affected:
        fp = os.path.join(BASE, name)
        sz = os.path.getsize(fp)
        total_bytes += sz
        # Use arcname so the tar entries are relative (just filename)
        tar.add(fp, arcname=name)
print(f"Backup size: {os.path.getsize(TAR_PATH):,} bytes "
      f"(original files total: {total_bytes:,} bytes)")

# Delete the originals
print(f"Deleting {len(affected)} files...")
for name in affected:
    fp = os.path.join(BASE, name)
    os.remove(fp)
print(f"Done. Remaining files in [6,5,5,2]:")
remaining = [f for f in os.listdir(BASE)
             if f.endswith('.g') and 'backup' not in f and 'Copy' not in f]
print(f"  {len(remaining)} files kept")
print()
print(f"Backup archive: {TAR_PATH}")
