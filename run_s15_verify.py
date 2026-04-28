#!/usr/bin/env python3
"""
run_s15_verify.py - Verify ALL S15 orbit type counts against brute-force reference.

Orbit type [1,...,1, d1,...,dk] in S15 = FPF partition [d1,...,dk] in S_{d1+...+dk}.
So verifying all 176 orbit types requires computing FPF partitions for S2 through S15.

Reference: count_orbit_types_output.txt (from brute-force ConjugacyClassesSubgroups(S15))

Usage:
    python run_s15_verify.py           # Launch 6 workers
    python run_s15_verify.py --dry-run # Preview assignment only
"""

import subprocess, os, json, re, time, sys

BASE_DIR = r"C:\Users\jeffr\Downloads\Lifting"
WORK_DIR = os.path.join(BASE_DIR, "parallel_s15_verify")
REF_FILE = r"C:\Users\jeffr\Downloads\Symmetric Groups\count_orbit_types_output.txt"
NUM_WORKERS = 6

GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"


def parse_reference():
    """Parse orbit type reference file.

    Each orbit type [d1,...,dk] (partition of 15) maps to FPF partition
    [e1,...,em] = parts > 1, at degree sum(ei).

    Returns dict: (degree, tuple(partition_descending)) -> expected_count
    """
    fpf_expected = {}
    with open(REF_FILE) as f:
        for line in f:
            m = re.match(r'\s*\[\s*([\d,\s]+)\]\s*:\s*(\d+)', line)
            if not m:
                continue
            parts = [int(x.strip()) for x in m.group(1).split(',')]
            count = int(m.group(2))
            fpf_parts = [p for p in parts if p > 1]
            if not fpf_parts:
                continue  # all-ones = trivial group, skip
            degree = sum(fpf_parts)
            fpf_partition = tuple(sorted(fpf_parts, reverse=True))
            fpf_expected[(degree, fpf_partition)] = count
    return fpf_expected


def estimate_cost(degree, expected_count):
    """Rough cost for LPT scheduling (higher degree = exponentially more expensive)."""
    weights = {
        2: 1, 3: 1, 4: 2, 5: 3, 6: 5, 7: 8,
        8: 15, 9: 30, 10: 60, 11: 120, 12: 300,
        13: 800, 14: 2000, 15: 4000
    }
    return expected_count * weights.get(degree, 4000)


def main():
    fpf_expected = parse_reference()

    # Build work items
    work_items = []
    for (degree, partition), count in fpf_expected.items():
        cost = estimate_cost(degree, count)
        work_items.append({
            'degree': degree,
            'partition': partition,
            'expected': count,
            'cost': cost
        })

    # Summary by degree
    by_degree = {}
    for item in work_items:
        d = item['degree']
        by_degree.setdefault(d, {'n_parts': 0, 'total_classes': 0})
        by_degree[d]['n_parts'] += 1
        by_degree[d]['total_classes'] += item['expected']

    print("=== S15 Full Verification Run ===\n")
    print("FPF partitions by degree:")
    for d in sorted(by_degree.keys()):
        info = by_degree[d]
        print(f"  S{d:2d}: {info['n_parts']:3d} partitions, {info['total_classes']:6d} expected classes")
    total_parts = len(work_items)
    total_classes = sum(i['expected'] for i in work_items)
    print(f"\n  Total: {total_parts} FPF partitions, {total_classes} expected classes")
    print(f"  (+ 1 trivial group = {total_classes + 1} = 159129)\n")

    # LPT scheduling: sort by cost desc, assign to least-loaded worker
    work_items.sort(key=lambda x: -x['cost'])
    worker_loads = [0.0] * NUM_WORKERS
    worker_items = [[] for _ in range(NUM_WORKERS)]

    for item in work_items:
        min_w = worker_loads.index(min(worker_loads))
        worker_items[min_w].append(item)
        worker_loads[min_w] += item['cost']

    print("Worker assignments:")
    for i in range(NUM_WORKERS):
        n = len(worker_items[i])
        total_exp = sum(it['expected'] for it in worker_items[i])
        heaviest = max(worker_items[i], key=lambda x: x['cost'])
        h_str = f"S{heaviest['degree']}{list(heaviest['partition'])}={heaviest['expected']}"
        print(f"  W{i}: {n:3d} partitions, {total_exp:6d} classes, heaviest: {h_str}")

    if "--dry-run" in sys.argv:
        print("\nDry run complete.")
        # Print detailed assignment for each worker
        for i in range(NUM_WORKERS):
            print(f"\n--- Worker {i} ---")
            items = sorted(worker_items[i], key=lambda x: (x['degree'], x['partition']))
            for it in items:
                print(f"  S{it['degree']:2d} {str(list(it['partition'])):20s} expected={it['expected']}")
        return

    # Create directories
    os.makedirs(WORK_DIR, exist_ok=True)
    for i in range(NUM_WORKERS):
        os.makedirs(os.path.join(WORK_DIR, "checkpoints", f"worker_{i}"), exist_ok=True)

    # Save manifest
    manifest = {}
    for i in range(NUM_WORKERS):
        for item in worker_items[i]:
            key = f"S{item['degree']}_{','.join(map(str, item['partition']))}"
            manifest[key] = {
                'worker': i,
                'degree': item['degree'],
                'partition': list(item['partition']),
                'expected': item['expected'],
                'status': 'pending'
            }
    with open(os.path.join(WORK_DIR, "manifest.json"), 'w') as f:
        json.dump(manifest, f, indent=2)

    # Create worker GAP scripts
    for wid in range(NUM_WORKERS):
        items = sorted(worker_items[wid], key=lambda x: (x['degree'], x['partition']))
        n_items = len(items)

        hb = f"C:/Users/jeffr/Downloads/Lifting/parallel_s15_verify/worker_{wid}_heartbeat.txt"
        res = f"C:/Users/jeffr/Downloads/Lifting/parallel_s15_verify/worker_{wid}_results.txt"
        log = f"C:/Users/jeffr/Downloads/Lifting/parallel_s15_verify/worker_{wid}.log"
        ckpt = f"C:/Users/jeffr/Downloads/Lifting/parallel_s15_verify/checkpoints/worker_{wid}"

        g = []
        g.append(f'LogTo("{log}");')
        g.append(f'Print("Worker {wid} starting at ", StringTime(Runtime()), "\\n");')
        g.append(f'Print("Verifying {n_items} FPF partitions (S2-S15)\\n\\n");')
        g.append('')
        g.append('Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");')
        g.append('Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");')
        g.append('')
        g.append(f'CHECKPOINT_DIR := "{ckpt}";')
        g.append(f'_HEARTBEAT_FILE := "{hb}";')
        g.append('')
        g.append('if IsBound(ClearH1Cache) then ClearH1Cache(); fi;')
        g.append('')
        g.append('totalCount := 0;')
        g.append('workerStart := Runtime();')
        g.append('mismatches := 0;')
        g.append('partsDone := 0;')
        g.append('')

        for item in items:
            d = item['degree']
            p = list(item['partition'])
            exp = item['expected']
            p_gap = str(p).replace(' ', '')

            g.append(f'Print("\\n========================================\\n");')
            g.append(f'Print("S{d} partition {p_gap}  (expected {exp}):\\n");')
            g.append(f'partStart := Runtime();')
            g.append(f'PrintTo("{hb}", "starting S{d} partition {p_gap}\\n");')
            g.append(f'fpf_classes := FindFPFClassesForPartition({d}, {p_gap});')
            g.append(f'partTime := (Runtime() - partStart) / 1000.0;')
            g.append(f'Print("  => ", Length(fpf_classes), " classes (", partTime, "s)");')
            g.append(f'if Length(fpf_classes) = {exp} then')
            g.append(f'    Print(" OK\\n");')
            g.append(f'else')
            g.append(f'    Print(" MISMATCH (expected {exp})\\n");')
            g.append(f'    mismatches := mismatches + 1;')
            g.append(f'fi;')
            g.append(f'totalCount := totalCount + Length(fpf_classes);')
            g.append(f'partsDone := partsDone + 1;')
            g.append(f'AppendTo("{res}", "S{d} {p_gap} ", String(Length(fpf_classes)), " expected={exp}\\n");')
            g.append(f'if IsBound(ClearH1Cache) then ClearH1Cache(); fi;')
            g.append(f'PrintTo("{hb}", "done S{d} {p_gap} = ", Length(fpf_classes), " (", partsDone, "/{n_items})\\n");')
            g.append('')

        g.append(f'workerTime := (Runtime() - workerStart) / 1000.0;')
        g.append(f'Print("\\nWorker {wid} complete: ", totalCount, " total in ", workerTime, "s\\n");')
        g.append(f'Print("Mismatches: ", mismatches, "\\n");')
        g.append(f'AppendTo("{res}", "TOTAL ", String(totalCount), "\\n");')
        g.append(f'AppendTo("{res}", "MISMATCHES ", String(mismatches), "\\n");')
        g.append(f'AppendTo("{res}", "TIME ", String(workerTime), "\\n");')
        g.append('LogTo();')
        g.append('QUIT;')

        script_path = os.path.join(WORK_DIR, f"worker_{wid}.g")
        with open(script_path, 'w') as f:
            f.write('\n'.join(g) + '\n')

    # Launch all workers
    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    for wid in range(NUM_WORKERS):
        script = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s15_verify/worker_{wid}.g"
        proc = subprocess.Popen(
            [BASH_EXE, "--login", "-c",
             f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script}"'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=GAP_RUNTIME)
        print(f"Worker {wid} launched (bash PID {proc.pid})")

    time.sleep(2)
    print(f"\nAll {NUM_WORKERS} workers launched.")
    print(f"Work dir: {WORK_DIR}")
    print(f"Monitor: worker_N_heartbeat.txt / worker_N_results.txt")
    print(f"\nExpected: 0 mismatches across all partitions")


if __name__ == '__main__':
    main()
