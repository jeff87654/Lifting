"""Delete all checkpoint files for the 26 partitions affected by the S_n
fast path bug. Workers will auto-skip combos whose output .g files still
exist (the valid ones we kept) and re-run the deleted bogus combos."""
import os
import glob
import datetime

CKPT_BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\checkpoints"
TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

AFFECTED = [
    "[10,5,3]", "[11,5,2]", "[5,5,3,3,2]", "[5,5,4,2,2]",
    "[5,5,4,4]", "[5,5,5,3]", "[6,5,3,2,2]", "[6,5,5,2]",
    "[6,6,2,2,2]", "[6,6,4,2]", "[6,6,6]", "[7,5,3,3]",
    "[7,5,4,2]", "[7,6,3,2]", "[7,6,5]", "[7,7,4]",
    "[8,5,3,2]", "[8,5,5]", "[8,6,2,2]", "[8,6,4]",
    "[8,7,3]", "[8,8,2]", "[9,5,2,2]", "[9,5,4]",
    "[9,6,3]", "[9,7,2]",
]


def partition_to_ckpt_pattern(part_str):
    """Convert '[10,5,3]' to 'ckpt_18_10_5_3*'"""
    inner = part_str[1:-1].replace(',', '_')
    return f"ckpt_18_{inner}"


total_deleted = 0
total_bytes = 0

print(f"Wiping checkpoints for {len(AFFECTED)} affected partitions")
print(f"Timestamp: {TS}")
print()

for part in AFFECTED:
    pattern = partition_to_ckpt_pattern(part)
    files_found = []
    for worker_dir in sorted(os.listdir(CKPT_BASE)):
        wdir = os.path.join(CKPT_BASE, worker_dir)
        if not os.path.isdir(wdir):
            continue
        for f in os.listdir(wdir):
            if f.startswith(pattern):
                files_found.append(os.path.join(wdir, f))
    if not files_found:
        continue
    part_bytes = sum(os.path.getsize(f) for f in files_found)
    for f in files_found:
        os.remove(f)
    total_deleted += len(files_found)
    total_bytes += part_bytes
    print(f"  {part:<18} {len(files_found):>4} files  ({part_bytes:>12,} bytes)")

print()
print(f"Total checkpoint files deleted: {total_deleted}")
print(f"Total bytes freed: {total_bytes:,}")
