"""Sum '# deduped: N' headers across all S20 output files."""
import re
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting\parallel_sn_topt_v3\20")
DEDUPED_RE = re.compile(rb"^# deduped:\s*(\d+)")


def file_count(p: Path) -> int | None:
    try:
        with p.open("rb") as f:
            for _ in range(6):
                line = f.readline()
                if not line:
                    return None
                m = DEDUPED_RE.match(line)
                if m:
                    return int(m.group(1))
        return None
    except OSError:
        return None


def main():
    t0 = time.time()
    by_part: dict[str, int] = defaultdict(int)
    file_count_by_part: dict[str, int] = defaultdict(int)
    skipped = 0
    total_files = 0
    for part_dir in sorted(ROOT.iterdir()):
        if not part_dir.is_dir():
            continue
        for g in part_dir.glob("*.g"):
            total_files += 1
            n = file_count(g)
            if n is None:
                skipped += 1
                continue
            by_part[part_dir.name] += n
            file_count_by_part[part_dir.name] += 1
    total = sum(by_part.values())
    print(f"S20 partitions present: {len(by_part)}")
    print(f"S20 output files: {total_files} ({skipped} missing/unparseable header)")
    print(f"S20 FPF subgroup total: {total:,}")
    print(f"elapsed: {time.time() - t0:.1f}s")
    print()
    print(f"{'partition':<28}  {'files':>7}  {'subgroups':>14}")
    print("-" * 54)
    for part, cnt in sorted(by_part.items(), key=lambda kv: -kv[1]):
        print(f"{part:<28}  {file_count_by_part[part]:>7,}  {cnt:>14,}")


if __name__ == "__main__":
    main()
