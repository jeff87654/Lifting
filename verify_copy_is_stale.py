"""Verify that every group in the ' - Copy' file also exists in the
non-Copy file before we delete the Copy."""
import os
import re

COPY = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\[4,4,4,4,2]\[2,1]_[4,3]_[4,3]_[4,3]_[4,3] - Copy.g"
REAL = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\[4,4,4,4,2]\[2,1]_[4,3]_[4,3]_[4,3]_[4,3].g"


def joined_groups(fp):
    with open(fp, 'r') as f:
        content = f.read()
    content = re.sub(r'\\\n', '', content)
    out = set()
    for line in content.split('\n'):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if s.startswith('['):
            out.add(s)
    return out


copy_groups = joined_groups(COPY)
real_groups = joined_groups(REAL)
print(f"Copy file groups:   {len(copy_groups):,}")
print(f"Real file groups:   {len(real_groups):,}")
print(f"Copy AND Real:      {len(copy_groups & real_groups):,}")
print(f"In Copy only:       {len(copy_groups - real_groups):,}")
print(f"In Real only:       {len(real_groups - copy_groups):,}")
if copy_groups - real_groups:
    print("WARNING: Copy has groups NOT in Real. Do NOT delete yet!")
else:
    print("SAFE: Copy is a subset of Real. Copy can be deleted.")
