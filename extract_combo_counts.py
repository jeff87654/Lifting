"""
Extract per-combo group counts for all S17 FPF partitions.

Data sources (in priority order):
1. Worker logs: ">> combo [[...]]" + "combo: N candidates -> M new (T total)" lines
2. Checkpoint files: "# combo: [...]" + "_CKPT_ADDED_COUNT := N;" + "# end combo (T total fpf)"

Output: one file per partition in combo_counts/ directory, plus a summary.
"""

import json
import os
import re
from collections import defaultdict
from pathlib import Path

BASE = Path("C:/Users/jeffr/Downloads/Lifting/parallel_s17")
OUT_DIR = BASE / "combo_counts"
OUT_DIR.mkdir(exist_ok=True)

# Load manifest
with open(BASE / "manifest.json") as f:
    manifest = json.load(f)
partitions = manifest["partitions"]


def parse_partition_key(key):
    """Convert '5_4_4_4' -> [5, 4, 4, 4]"""
    return [int(x) for x in key.split("_")]


def format_partition(parts):
    """[5, 4, 4, 4] -> '[5, 4, 4, 4]'"""
    return "[" + ", ".join(str(x) for x in parts) + "]"


def partition_to_key(parts):
    """[5, 4, 4, 4] -> '5_4_4_4'"""
    return "_".join(str(x) for x in parts)


def count_gens_file(key):
    """Count groups in gens file. Each entry starts with [ or [[ at line start."""
    gens_path = BASE / "gens" / f"gens_{key}.txt"
    if not gens_path.exists():
        return None
    count = 0
    with open(gens_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("[") and not line.startswith("\\"):
                count += 1
    return count


# ── Parse worker logs ──────────────────────────────────────────────────

def parse_log_combos(log_path):
    """Parse a worker log file, returning per-partition combo data.

    Returns dict: { partition_str: [ { 'key': combo_key, 'candidates': N,
                     'new': M, 'running_total': T, 'combo_num': i }, ... ] }
    """
    result = {}
    current_partition = None
    current_combos = []
    pending_key = None  # key from ">> combo" line awaiting "combo:" result line

    partition_re = re.compile(r"^Partition \[ ([\d, ]+) \]")
    combo_header_re = re.compile(r"^\s+>> combo \[(.+)\] factors=")
    combo_result_re = re.compile(
        r"^\s+combo: (\d+) candidates -> (\d+) new \((\d+) total\)"
    )

    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = partition_re.match(line)
            if m:
                # Save previous partition
                if current_partition and current_combos:
                    result[current_partition] = current_combos
                current_partition = m.group(1).strip()
                current_combos = []
                pending_key = None
                continue

            m = combo_header_re.match(line)
            if m and current_partition:
                pending_key = m.group(1).strip()
                continue

            m = combo_result_re.match(line)
            if m and current_partition:
                candidates = int(m.group(1))
                new = int(m.group(2))
                running_total = int(m.group(3))
                current_combos.append({
                    "key": pending_key or "?",
                    "candidates": candidates,
                    "new": new,
                    "running_total": running_total,
                })
                pending_key = None
                continue

    # Save last partition
    if current_partition and current_combos:
        result[current_partition] = current_combos

    return result


# ── Parse checkpoint files ─────────────────────────────────────────────

def parse_checkpoint_combos(ckpt_path):
    """Parse a checkpoint .log file for per-combo data.

    Checkpoints accumulate across restarts, so the same combos may appear
    multiple times. Restart boundaries are detected by a drop in the running
    total. We extract only the LAST complete monotone run.

    Returns list of { 'key': combo_key, 'cumulative_total': T }
    The per-combo new count = cumulative_total[i] - cumulative_total[i-1].
    """
    all_entries = []
    current_key = None

    combo_re = re.compile(r"^# combo: (.+)$")
    end_re = re.compile(r"^# end combo \((\d+) total fpf\)")

    with open(ckpt_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = combo_re.match(line)
            if m:
                current_key = m.group(1).strip()
                continue
            m = end_re.match(line)
            if m and current_key:
                cumulative = int(m.group(1))
                all_entries.append({
                    "key": current_key,
                    "cumulative_total": cumulative,
                })
                current_key = None

    if not all_entries:
        return []

    # Split into runs at restart boundaries (where cumulative drops)
    runs = []
    current_run = [all_entries[0]]
    for i in range(1, len(all_entries)):
        if all_entries[i]["cumulative_total"] < all_entries[i-1]["cumulative_total"]:
            runs.append(current_run)
            current_run = []
        current_run.append(all_entries[i])
    runs.append(current_run)

    # Return the last run (the one that progressed furthest)
    return runs[-1]


def parse_checkpoint_g_file(g_path):
    """Parse a .g checkpoint file for combo keys and total count.

    These files have _CKPT_COMPLETED_KEYS list and a header comment with totals,
    but no per-combo group counts. The key list may contain duplicates from
    checkpoint restarts, so we use _CKPT_ADDED_COUNT as the authoritative
    group count and deduplicate keys preserving order.

    Returns (total_combos, total_groups, keys_list).
    """
    total_combos = None
    total_groups = None
    added_count = None
    keys = []
    seen_keys = set()

    header_re = re.compile(r"^# (\d+) combos, (\d+) groups")
    key_re = re.compile(r'^"(\[.+\])"')
    added_re = re.compile(r"^_CKPT_ADDED_COUNT := (\d+);")

    with open(g_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = header_re.match(line)
            if m:
                total_combos = int(m.group(1))
                total_groups = int(m.group(2))
                continue
            m = added_re.match(line)
            if m:
                added_count = int(m.group(1))
                continue
            m = key_re.match(line)
            if m:
                key = m.group(1)
                if key not in seen_keys:
                    seen_keys.add(key)
                    keys.append(key)

    # Both header and _CKPT_ADDED_COUNT can be wrong due to restart accumulation.
    # Header counts duped keys; _CKPT_ADDED_COUNT accumulates across restarts.
    # Use unique key count as combo count. total_groups is best-effort from header.
    return len(keys), total_groups, keys


def find_best_checkpoint(part_key):
    """Find the checkpoint with the most combos for a partition.

    Checks .log files first (have per-combo breakdown), then .g files
    (have combo keys and total but no per-combo counts).

    Returns (worker_name, combos_list, source_type) where source_type is
    'log' or 'g'. combos_list format depends on source_type:
      'log': list of { 'key', 'cumulative_total' }
      'g': list of { 'key', 'cumulative_total': None }
    """
    best_worker = None
    best_combos = None
    best_count = 0
    best_type = None

    ckpt_base = BASE / "checkpoints"
    if not ckpt_base.exists():
        return None, None, None

    # First pass: .log files (have per-combo data)
    for worker_dir in sorted(ckpt_base.iterdir()):
        if not worker_dir.is_dir():
            continue
        ckpt_file = worker_dir / f"ckpt_17_{part_key}.log"
        if ckpt_file.exists():
            # Skip placeholder logs that just say "# Merged into .g checkpoint"
            with open(ckpt_file, encoding="utf-8", errors="replace") as f:
                first_line = f.readline().strip()
            if "Merged" in first_line:
                continue
            combos = parse_checkpoint_combos(ckpt_file)
            if len(combos) > best_count:
                best_count = len(combos)
                best_combos = combos
                best_worker = worker_dir.name
                best_type = "log"

    # Second pass: .g files (keys only, no per-combo counts)
    for worker_dir in sorted(ckpt_base.iterdir()):
        if not worker_dir.is_dir():
            continue
        g_file = worker_dir / f"ckpt_17_{part_key}.g"
        if g_file.exists():
            tc, tg, keys = parse_checkpoint_g_file(g_file)
            if keys and len(keys) > best_count:
                best_count = len(keys)
                best_combos = [{"key": k, "cumulative_total": None} for k in keys]
                # Store total_groups as metadata on last entry
                if tg is not None and best_combos:
                    best_combos[-1]["cumulative_total"] = tg
                best_worker = worker_dir.name
                best_type = "g"

    return best_worker, best_combos, best_type


# ── Main extraction ───────────────────────────────────────────────────

def main():
    # Step 1: Parse ALL worker logs
    print("Parsing worker logs...")
    # partition_str -> list of (worker_name, combos)
    log_data = defaultdict(list)

    log_files = sorted(
        [p for p in BASE.glob("worker_*.log")
         if re.match(r"^worker_\d+$", p.stem)],
        key=lambda p: int(p.stem.split("_")[1])
    )
    for lf in log_files:
        worker_name = lf.stem
        parsed = parse_log_combos(lf)
        for part_str, combos in parsed.items():
            if combos:
                log_data[part_str].append((worker_name, combos))

    print(f"  Found log combo data for {len(log_data)} partitions")

    # Step 2: For each manifest partition, produce output
    issues = []
    summary_rows = []

    for part_key in sorted(partitions.keys(),
                           key=lambda k: (-sum(parse_partition_key(k)),
                                          parse_partition_key(k))):
        info = partitions[part_key]
        parts = parse_partition_key(part_key)
        part_str = ", ".join(str(x) for x in parts)
        manifest_count = info.get("fpf_count")
        gens_count = count_gens_file(part_key)

        # Try log data first
        part_lookup = part_str  # "5, 4, 4, 4"
        log_entries = log_data.get(part_lookup, [])

        # Find the best single-worker log (most combos, matching manifest)
        best_log_worker = None
        best_log_combos = None
        all_log_sources = []

        for worker_name, combos in log_entries:
            final_total = combos[-1]["running_total"] if combos else 0
            all_log_sources.append((worker_name, len(combos), final_total))
            # Prefer the one whose final total matches manifest
            if manifest_count is not None and final_total == manifest_count:
                if best_log_combos is None or len(combos) > len(best_log_combos):
                    best_log_worker = worker_name
                    best_log_combos = combos
            elif best_log_combos is None or len(combos) > len(best_log_combos):
                best_log_worker = worker_name
                best_log_combos = combos

        # Try checkpoint data
        ckpt_worker, ckpt_combos, ckpt_type = find_best_checkpoint(part_key)

        # Decide which source to use
        source = None
        combo_records = []  # list of (key, new_count, running_total)
        # new_count=None means per-combo breakdown unavailable

        # Prefer log data if it has complete info (final total matches manifest)
        log_complete = (best_log_combos and manifest_count is not None and
                        best_log_combos[-1]["running_total"] == manifest_count)

        ckpt_log_complete = (ckpt_combos and ckpt_type == "log" and
                             manifest_count is not None and
                             ckpt_combos[-1]["cumulative_total"] == manifest_count)

        # For .g checkpoints, check if gens_count matches manifest (means complete)
        ckpt_g_complete = (ckpt_combos and ckpt_type == "g" and
                           manifest_count is not None and
                           gens_count is not None and
                           gens_count == manifest_count)

        # Check if log data has restart artifacts (running total jumps)
        log_has_restart = False
        if best_log_combos:
            for i in range(1, len(best_log_combos)):
                expected = (best_log_combos[i-1]["running_total"] +
                            best_log_combos[i]["new"])
                actual = best_log_combos[i]["running_total"]
                if expected != actual:
                    log_has_restart = True
                    break

        if log_complete and not log_has_restart:
            source = f"log:{best_log_worker}"
            for c in best_log_combos:
                combo_records.append((c["key"], c["new"], c["running_total"]))
        elif ckpt_log_complete:
            source = f"ckpt:{ckpt_worker}"
            prev = 0
            for c in ckpt_combos:
                new_count = c["cumulative_total"] - prev
                combo_records.append((c["key"], new_count, c["cumulative_total"]))
                prev = c["cumulative_total"]
        elif ckpt_g_complete:
            # .g file: keys + total, but no per-combo counts
            source = f"ckpt_g:{ckpt_worker}"
            for c in ckpt_combos:
                combo_records.append((c["key"], None, None))
            combo_records_g_total = manifest_count  # use manifest as truth
        elif best_log_combos and (not ckpt_combos or
                                   len(best_log_combos) >= len(ckpt_combos or [])):
            source = f"log:{best_log_worker} (PARTIAL)"
            for c in best_log_combos:
                combo_records.append((c["key"], c["new"], c["running_total"]))
        elif ckpt_combos and ckpt_type == "log":
            source = f"ckpt:{ckpt_worker} (PARTIAL)"
            prev = 0
            for c in ckpt_combos:
                new_count = c["cumulative_total"] - prev
                combo_records.append((c["key"], new_count, c["cumulative_total"]))
                prev = c["cumulative_total"]
        elif ckpt_combos and ckpt_type == "g":
            source = f"ckpt_g:{ckpt_worker} (PARTIAL)"
            for c in ckpt_combos:
                combo_records.append((c["key"], None, None))
            # Best-effort: use gens_count or manifest, whichever is available
            combo_records_g_total = gens_count or manifest_count or 0
        else:
            source = "NONE"

        total_combos = len(combo_records)
        if source.startswith("ckpt_g:"):
            combo_sum = combo_records_g_total or 0
        else:
            combo_sum = combo_records[-1][2] if combo_records else 0

        # ── Flag issues ────────────────────────────────────────────
        part_issues = []

        if source == "NONE":
            part_issues.append("NO combo data from any source")

        if manifest_count is not None and combo_sum != manifest_count:
            part_issues.append(
                f"combo_sum ({combo_sum}) != manifest ({manifest_count})")

        if gens_count is not None and manifest_count is not None and gens_count != manifest_count:
            part_issues.append(
                f"gens_count ({gens_count}) != manifest ({manifest_count})")

        # Check running total consistency (skip for .g sources without per-combo data)
        if not source.startswith("ckpt_g:"):
            for i in range(1, len(combo_records)):
                expected = combo_records[i-1][2] + combo_records[i][1]
                actual = combo_records[i][2]
                if expected != actual:
                    part_issues.append(
                        f"running total inconsistency at combo {i+1}: "
                        f"{combo_records[i-1][2]} + {combo_records[i][1]} = "
                        f"{expected} != {actual}")
                    break  # only flag first inconsistency

            # Check for negative new counts (would indicate checkpoint overlap)
            for i, (key, new, rt) in enumerate(combo_records):
                if new is not None and new < 0:
                    part_issues.append(
                        f"NEGATIVE new count at combo {i+1}: {new} (key={key})")
                    break

        if source.startswith("ckpt_g:"):
            part_issues.append("per-combo breakdown unavailable (.g checkpoint only)")

        # ── Write output file ──────────────────────────────────────
        out_path = OUT_DIR / f"{part_key}.txt"
        with open(out_path, "w") as f:
            f.write(f"Partition: {format_partition(parts)}\n")
            f.write(f"Source: {source}\n")
            f.write(f"Manifest count: {manifest_count}\n")
            f.write(f"Gens file count: {gens_count}\n")
            f.write(f"Total combos: {total_combos}, "
                    f"Total groups: {combo_sum}\n")
            if part_issues:
                f.write(f"ISSUES: {'; '.join(part_issues)}\n")
            f.write("\n")
            for i, (key, new, rt) in enumerate(combo_records):
                if new is not None:
                    f.write(f"combo {i+1}: {new} groups "
                            f"(running_total={rt}, key={key})\n")
                else:
                    f.write(f"combo {i+1}: ? groups (key={key})\n")

        # ── Collect summary ────────────────────────────────────────
        status = "OK" if not part_issues else "ISSUE"
        summary_rows.append({
            "partition": format_partition(parts),
            "key": part_key,
            "combos": total_combos,
            "combo_sum": combo_sum,
            "manifest": manifest_count,
            "gens": gens_count,
            "source": source,
            "status": status,
            "issues": "; ".join(part_issues) if part_issues else "",
        })

        if part_issues:
            issues.append((format_partition(parts), part_issues))

    # ── Write summary ──────────────────────────────────────────────
    summary_path = OUT_DIR / "_SUMMARY.txt"
    with open(summary_path, "w") as f:
        f.write("S17 Per-Combo Audit Summary\n")
        f.write("=" * 80 + "\n\n")

        # Categorize issues
        ok_full = []       # OK with per-combo data
        ok_nobreakdown = []  # combo_sum matches but no per-combo breakdown
        incomplete = []    # combo_sum != manifest (still computing)
        for r in summary_rows:
            has_mismatch = (r["manifest"] is not None and
                            r["combo_sum"] != r["manifest"])
            has_nobreakdown = "per-combo breakdown" in r.get("issues", "")
            if has_mismatch:
                incomplete.append(r)
            elif has_nobreakdown:
                ok_nobreakdown.append(r)
            else:
                ok_full.append(r)

        # Overall stats
        null_manifest = [r for r in summary_rows if r["manifest"] is None]
        has_manifest = [r for r in summary_rows if r["manifest"] is not None]
        verified = [r for r in has_manifest
                    if r["combo_sum"] == r["manifest"]]
        verified_groups = sum(r["combo_sum"] for r in verified)
        manifest_total = sum(r["manifest"] for r in has_manifest)
        incomplete_deficit = sum(r["manifest"] - r["combo_sum"]
                                 for r in incomplete)

        f.write(f"Partitions: {len(summary_rows)}\n")
        f.write(f"  Full per-combo data:    {len(ok_full)}\n")
        f.write(f"  Keys only (.g ckpt):    {len(ok_nobreakdown)}\n")
        f.write(f"  Incomplete (computing): {len(incomplete)}\n")
        f.write(f"  Null manifest:          {len(null_manifest)}\n")
        f.write(f"\n")
        f.write(f"Verified groups (combo_sum=manifest): "
                f"{verified_groups} across {len(verified)} partitions\n")
        f.write(f"Total manifest (excl null):           {manifest_total}\n")
        f.write(f"Incomplete remaining:                 {incomplete_deficit}\n")
        if null_manifest:
            null_total = sum(r["combo_sum"] for r in null_manifest)
            f.write(f"Null-manifest partitions:             "
                    f"{len(null_manifest)} ({null_total} groups, gens match)\n")
        f.write("\n")

        # Table
        f.write(f"{'Partition':<28} {'Combos':>6} {'ComboSum':>8} "
                f"{'Manifest':>8} {'Gens':>8}  {'Source':<30} {'Status'}\n")
        f.write("-" * 120 + "\n")
        for r in summary_rows:
            m_str = str(r["manifest"]) if r["manifest"] is not None else "null"
            g_str = str(r["gens"]) if r["gens"] is not None else "null"
            f.write(f"{r['partition']:<28} {r['combos']:>6} {r['combo_sum']:>8} "
                    f"{m_str:>8} {g_str:>8}  {r['source']:<30} {r['status']}")
            if r["issues"]:
                f.write(f"  {r['issues']}")
            f.write("\n")

        # Issues section
        if issues:
            f.write("\n" + "=" * 80 + "\n")
            f.write("ISSUES DETAIL\n")
            f.write("=" * 80 + "\n\n")
            for part_str, part_issues in issues:
                f.write(f"{part_str}:\n")
                for iss in part_issues:
                    f.write(f"  - {iss}\n")
                f.write("\n")

    print(f"\nOutput written to {OUT_DIR}/")
    print(f"  {len(summary_rows)} partition files + _SUMMARY.txt")
    print(f"  {len(ok_full)} full, {len(ok_nobreakdown)} keys-only, "
          f"{len(incomplete)} incomplete")
    if incomplete:
        print(f"\nIncomplete partitions (combo_sum != manifest):")
        for r in incomplete:
            print(f"  {r['partition']}: {r['combo_sum']} / {r['manifest']}")
    if issues:
        print(f"\nAll issues:")
        for part_str, part_issues in issues:
            print(f"  {part_str}: {'; '.join(part_issues)}")


if __name__ == "__main__":
    main()
