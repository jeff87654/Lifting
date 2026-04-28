"""Enumerate every (partition, combo) for S_n in a given range, compute
Q = P / RadicalGroup(P), and write out a dedup-by-(key,sig) catalog of
TF-top groups we will encounter during the full FPF lift.

Output: a JSONL file, one record per (n, partition, combo):
  {
    "n": 16,
    "partition": [8, 5, 3],
    "combo": [[8, 48], [5, 4], [3, 1]],
    "size_P": ...,
    "size_Pt": ...,
    "size_Q": ...,
    "key": "id_N_K" or "lg_...",
    "sig": "1A2B3C4D",
    "q_gens": ["(1,2)(3,4)", "(1,3)(5,7)", ...]    # permutation strings
  }

Concurrent workers share the output file via per-worker shards that are
concatenated at the end.

Usage:
  python dry_run_tops.py --n-start 16 --n-end 18 --workers 6
  python dry_run_tops.py --n 17                           # single degree
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
from math import comb
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
GAP_RUNTIME = Path(r"C:\Program Files\GAP-4.15.1\runtime")
BASH_EXE = GAP_RUNTIME / "bin" / "bash.exe"

NR_TRANSITIVE = {
    1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
    9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104,
    16: 1954, 17: 5, 18: 983,
}


def partitions_min_part(n, min_part=2):
    result = []
    def helper(remaining, max_part, current):
        if remaining == 0:
            result.append(tuple(current))
            return
        for i in range(min(remaining, max_part), min_part - 1, -1):
            current.append(i)
            helper(remaining - i, i, current)
            current.pop()
    helper(n, n, [])
    return result


def combos_for_partition(partition):
    """Yield (d_i, tg_id_i) tuples for each combo of this partition.
    Within same-degree blocks, enforce non-decreasing tg_id (multiset)."""
    from itertools import product as cart_product, combinations_with_replacement

    # Group by degree
    from collections import defaultdict
    degree_groups = defaultdict(list)
    for i, d in enumerate(partition):
        degree_groups[d].append(i)

    # For each degree d that appears k times, pick multiset of size k from tg_ids
    degrees_sorted = sorted(degree_groups.keys(), reverse=True)  # descending
    per_degree_choices = []
    for d in degrees_sorted:
        k = len(degree_groups[d])
        t = NR_TRANSITIVE.get(d, d)
        per_degree_choices.append(list(combinations_with_replacement(range(1, t + 1), k)))

    for choice_tuple in cart_product(*per_degree_choices):
        # Re-assemble combo in order of partition's blocks
        combo = [None] * len(partition)
        for d_idx, d in enumerate(degrees_sorted):
            indices_of_d = degree_groups[d]
            tg_ids = choice_tuple[d_idx]
            for i, pos in enumerate(indices_of_d):
                combo[pos] = (d, tg_ids[i])
        yield tuple(combo)


def count_combos(partition):
    cnt = 1
    from collections import Counter
    for d, k in Counter(partition).items():
        t = NR_TRANSITIVE.get(d, d)
        cnt *= comb(t + k - 1, k)
    return cnt


def write_task_csv(csv_path, tasks):
    """Write tasks as a CSV: each line is `n;partition;combo` (semicolon-separated)."""
    with open(csv_path, "w", encoding="utf-8") as f:
        for (n, partition, combo) in tasks:
            part_str = ",".join(str(x) for x in partition)
            combo_str = "|".join(f"{d}:{k}" for (d, k) in combo)
            f.write(f"{n};{part_str};{combo_str}\n")


def generate_gap_worker(worker_id, tasks_csv_path, output_path, log_path):
    """Generate a GAP script that reads tasks from `tasks_csv_path` line-by-line."""
    lines = []
    lines.append(f'LogTo("{log_path.as_posix()}");')
    lines.append('Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");')
    lines.append('Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");')
    lines.append('SizeScreen([100000, 24]);')
    lines.append(f'_OUT_PATH := "{output_path.as_posix()}";')
    lines.append('PrintTo(_OUT_PATH, "");')
    lines.append('_OUT := OutputTextFile(_OUT_PATH, true);')
    lines.append('SetPrintFormattingStatus(_OUT, false);')
    # Utility: serialize a permutation as a string
    lines.append('_PermToStr := function(p) return String(p); end;')
    # Utility: format an integer list like [1,2,3] with NO spaces (JSON-compact)
    lines.append('_FmtIntList := function(L) return Concatenation("[", JoinStringsWithSeparator(List(L, String), ","), "]"); end;')
    lines.append('_FmtComboList := function(C)')
    lines.append('  return Concatenation("[",')
    lines.append('    JoinStringsWithSeparator(')
    lines.append('      List(C, x -> Concatenation("[", String(x[1]), ",", String(x[2]), "]")), ","),')
    lines.append('    "]");')
    lines.append('end;')
    lines.append('_ProcessCombo := function(n, partition, combo)')
    lines.append('  local shifted, offsets, offset, i, d, tg_id, T, P,')
    lines.append('        Pt, Q, hom, key, sig, idg, qgens, qgens_str, gens_list,')
    lines.append('        line;')
    lines.append('  offsets := [];')
    lines.append('  offset := 0;')
    lines.append('  shifted := [];')
    lines.append('  for i in [1..Length(partition)] do')
    lines.append('    d := partition[i];')
    lines.append('    tg_id := combo[i][2];')
    lines.append('    T := TransitiveGroup(d, tg_id);')
    lines.append('    if offset > 0 then T := ShiftGroup(T, offset); fi;')
    lines.append('    Add(shifted, T);')
    lines.append('    Add(offsets, offset);')
    lines.append('    offset := offset + d;')
    lines.append('  od;')
    lines.append('  P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));')
    lines.append('  Pt := RadicalGroup(P);')
    lines.append('  if Size(Pt) = Size(P) then')
    lines.append('    # Q trivial. Record with empty generator list.')
    lines.append('    key := "trivial";')
    lines.append('    sig := "00000000";')
    lines.append('    qgens_str := "[]";')
    lines.append('  else')
    lines.append('    hom := NaturalHomomorphismByNormalSubgroup(P, Pt);')
    lines.append('    Q := ImagesSource(hom);')
    lines.append('    # Build key via IdGroup if small, else structural key.')
    lines.append('    if Size(Q) <= 2000 then')
    lines.append('      idg := IdGroup(Q);')
    lines.append('      key := Concatenation("id_", String(idg[1]), "_", String(idg[2]));')
    lines.append('    else')
    lines.append('      key := HoltStructuralKey(Q);')
    lines.append('    fi;')
    lines.append('    sig := _HoltPermRepSignature(Q);')
    lines.append('    qgens := GeneratorsOfGroup(Q);')
    lines.append('    gens_list := List(qgens, _PermToStr);')
    lines.append('    qgens_str := Concatenation("[\\"",')
    lines.append('      JoinStringsWithSeparator(gens_list, "\\",\\""),')
    lines.append('      "\\"]");')
    lines.append('  fi;')
    lines.append('  # Emit JSONL line (compact; no GAP space-insertion).')
    lines.append('  line := Concatenation(')
    lines.append('    "{\\"n\\":", String(n),')
    lines.append('    ",\\"partition\\":", _FmtIntList(partition),')
    lines.append('    ",\\"combo\\":", _FmtComboList(combo),')
    lines.append('    ",\\"size_P\\":", String(Size(P)),')
    lines.append('    ",\\"size_Pt\\":", String(Size(Pt)),')
    lines.append('    ",\\"size_Q\\":", String(Size(P)/Size(Pt)),')
    lines.append('    ",\\"key\\":\\"", key, "\\"",')
    lines.append('    ",\\"sig\\":\\"", sig, "\\"",')
    lines.append('    ",\\"q_gens\\":", qgens_str,')
    lines.append('    "}\\n");')
    lines.append('  WriteAll(_OUT, line);')
    lines.append('  return rec(n := n, partition := partition, combo := combo,')
    lines.append('             size_P := Size(P), size_Q := Size(P)/Size(Pt));')
    lines.append('end;')
    # Read tasks from CSV and process row-by-row (avoids GAP literal parsing
    # pathologies for large task sets).
    lines.append(f'_TASKS_CSV := "{tasks_csv_path.as_posix()}";')
    lines.append('_CSV_STR := StringFile(_TASKS_CSV);')
    lines.append('_ROWS := SplitString(_CSV_STR, "\\n");')
    lines.append('_t0 := Runtime();')
    lines.append('_ntasks := 0;')
    lines.append('_SplitAt := function(s, delim) return SplitString(s, delim); end;')
    lines.append('for _row in _ROWS do')
    lines.append('  _row := Filtered(_row, c -> c <> \'\\r\');')  # strip CR if present
    lines.append('  if Length(_row) = 0 then continue; fi;')
    lines.append('  _parts := SplitString(_row, ";");')
    lines.append('  if Length(_parts) < 3 then continue; fi;')
    lines.append('  _n := Int(_parts[1]);')
    lines.append('  _pstr := SplitString(_parts[2], ",");')
    lines.append('  _part := List(_pstr, Int);')
    lines.append('  _cstr := SplitString(_parts[3], "|");')
    lines.append('  _combo := List(_cstr, s -> List(SplitString(s, ":"), Int));')
    lines.append('  _ProcessCombo(_n, _part, _combo);')
    lines.append('  _ntasks := _ntasks + 1;')
    lines.append('od;')
    lines.append('CloseStream(_OUT);')
    lines.append('Print("Worker ", ' + str(worker_id) + ', " done in ", (Runtime() - _t0)/1000.0, "s, ", _ntasks, " tasks\\n");')
    lines.append('LogTo();')
    lines.append('QUIT;')
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, help="Single degree")
    parser.add_argument("--n-start", type=int, help="Start degree (inclusive)")
    parser.add_argument("--n-end", type=int, help="End degree (inclusive)")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--output", default=str(LIFTING / "tf_top_catalog.jsonl"))
    parser.add_argument("--work-dir", default=str(LIFTING / "dry_run_work"))
    args = parser.parse_args()

    if args.n is not None:
        ns = [args.n]
    elif args.n_start is not None and args.n_end is not None:
        ns = list(range(args.n_start, args.n_end + 1))
    else:
        parser.error("Specify --n or --n-start and --n-end")

    # Enumerate all tasks
    tasks = []
    for n in ns:
        for partition in partitions_min_part(n):
            for combo in combos_for_partition(partition):
                tasks.append((n, partition, combo))

    print(f"Total tasks across degrees {ns}: {len(tasks)}")

    # LPT by estimated cost (larger combos first). Use size_P heuristic.
    def est_cost(t):
        # Heuristic: max factor order in combo
        return sum(d for (d, _) in t[2]) ** 2

    tasks.sort(key=est_cost, reverse=True)

    # Round-robin assign to workers (approximates LPT).
    worker_tasks = [[] for _ in range(args.workers)]
    for i, t in enumerate(tasks):
        worker_tasks[i % args.workers].append(t)

    work_dir = Path(args.work_dir)
    work_dir.mkdir(exist_ok=True)

    # Launch workers in parallel.
    worker_outputs = []
    processes = []
    for wid, wt in enumerate(worker_tasks):
        script_path = work_dir / f"worker_{wid}.g"
        log_path = work_dir / f"worker_{wid}.log"
        out_path = work_dir / f"worker_{wid}.jsonl"
        tasks_csv = work_dir / f"worker_{wid}_tasks.csv"
        write_task_csv(tasks_csv, wt)
        worker_outputs.append(out_path)
        script = generate_gap_worker(wid, tasks_csv, out_path, log_path)
        script_path.write_text(script, encoding="utf-8")

        cygwin_script = "/cygdrive/c" + str(script_path).replace("\\", "/").replace("C:", "")
        gap_dir = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"
        env = os.environ.copy()
        env["PATH"] = str(GAP_RUNTIME / "bin") + ";" + env.get("PATH", "")
        env["CYGWIN"] = "nodosfilewarning"

        cmd = [str(BASH_EXE), "--login", "-c",
               f'cd "{gap_dir}" && ./gap.exe -q -o 0 "{cygwin_script}"']
        print(f"Worker {wid}: {len(wt)} tasks, script {script_path}")
        p = subprocess.Popen(cmd, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True)
        processes.append(p)

    # Wait and collect.
    for wid, p in enumerate(processes):
        out, err = p.communicate()
        if p.returncode != 0:
            print(f"Worker {wid} FAILED rc={p.returncode}")
            if err:
                print(f"stderr: {err[-500:]}")
        else:
            print(f"Worker {wid} done")

    # Concatenate output shards.
    combined = Path(args.output)
    with open(combined, "w", encoding="utf-8") as out_f:
        for p in worker_outputs:
            if p.exists():
                with open(p, encoding="utf-8") as in_f:
                    out_f.write(in_f.read())

    # Summary.
    n_lines = 0
    uniq_keys = set()
    size_Q_hist = []
    with open(combined, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            n_lines += 1
            uniq_keys.add((rec["key"], rec["sig"]))
            size_Q_hist.append(rec["size_Q"])

    print(f"\n=== Summary ===")
    print(f"Total combos processed: {n_lines}")
    print(f"Unique (key, sig) pairs: {len(uniq_keys)}")
    if size_Q_hist:
        size_Q_hist.sort()
        print(f"|Q| distribution: min={size_Q_hist[0]}, "
              f"median={size_Q_hist[len(size_Q_hist)//2]}, "
              f"max={size_Q_hist[-1]}")
        print(f"|Q| percentiles:")
        for pct in [50, 75, 90, 95, 99]:
            idx = min(len(size_Q_hist) - 1, int(len(size_Q_hist) * pct / 100))
            print(f"  p{pct}: {size_Q_hist[idx]}")
    print(f"Catalog written: {combined}")


if __name__ == "__main__":
    main()
