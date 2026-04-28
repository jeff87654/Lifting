"""Analyze invariant bucket sizes for completed combos.

For each specified combo file, read the groups, recompute invariants,
and report bucket size distribution.
"""
import subprocess, os, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

# Top combos to analyze (partition, combo filename, total points n)
COMBOS = [
    ("[4,4,4,3,2]", "[2,1]_[3,2]_[4,3]_[4,3]_[4,3].g", 17),
    ("[4,4,4,3,2]", "[2,1]_[3,2]_[4,2]_[4,3]_[4,3].g", 17),
    ("[8,4,3,2]",   "[2,1]_[3,2]_[4,3]_[8,35].g",      17),
]

BASE_DIR = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17_v2"

log_file = "C:/Users/jeffr/Downloads/Lifting/bucket_analysis.log"
script_path = r"C:\Users\jeffr\Downloads\Lifting\bucket_analysis.g"

# Build GAP script
gap_lines = [
    f'LogTo("{log_file}");',
    'Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");',
    'Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");',
    '',
    '_ComputeBlockRanges := function(partition)',
    '    local ranges, pos, d;',
    '    ranges := [];',
    '    pos := 0;',
    '    for d in partition do',
    '        Add(ranges, [pos+1, pos+d]);',
    '        pos := pos + d;',
    '    od;',
    '    return ranges;',
    'end;',
    '',
    '_JoinContinuations := function(content)',
    '    local result, i, len;',
    '    result := "";',
    '    i := 1;',
    '    len := Length(content);',
    '    while i <= len do',
    '        if i < len and content[i] = \'\\\\\' and content[i+1] = \'\\n\' then',
    '            i := i + 2;',
    '        else',
    '            Append(result, [content[i]]);',
    '            i := i + 1;',
    '        fi;',
    '    od;',
    '    return result;',
    'end;',
    '',
    '_AnalyzeBucketSizes := function(filepath, n, partition)',
    '    local content, lines, groups, line, gens, G, buckets, key, inv,',
    '          sizes, h, sorted, i, maxSize, avg, bigBuckets;',
    '    CURRENT_BLOCK_RANGES := _ComputeBlockRanges(partition);',
    '    content := StringFile(filepath);',
    '    if content = fail then',
    '        Print("ERROR: cannot read ", filepath, "\\n");',
    '        return;',
    '    fi;',
    '    content := _JoinContinuations(content);',
    '    lines := SplitString(content, "\\n");',
    '    groups := [];',
    '    for line in lines do',
    '        if Length(line) > 0 and line[1] = \'[\' then',
    '            gens := EvalString(line);',
    '            if Length(gens) > 0 then',
    '                G := Group(gens);',
    '            else',
    '                G := TrivialGroup();',
    '                SetParent(G, SymmetricGroup(n));',
    '            fi;',
    '            Add(groups, G);',
    '        fi;',
    '    od;',
    '    Print("\\n=== ", filepath, " ===\\n");',
    '    Print("Loaded ", Length(groups), " groups\\n");',
    '    buckets := rec();',
    '    for i in [1..Length(groups)] do',
    '        h := groups[i];',
    '        inv := CheapSubgroupInvariantFull(h);',
    '        key := InvariantKey(inv);',
    '        if not IsBound(buckets.(key)) then',
    '            buckets.(key) := 0;',
    '        fi;',
    '        buckets.(key) := buckets.(key) + 1;',
    '        if i mod 5000 = 0 then',
    '            Print("    progress: ", i, "/", Length(groups), "\\n");',
    '        fi;',
    '    od;',
    '    sizes := [];',
    '    for key in RecNames(buckets) do',
    '        Add(sizes, buckets.(key));',
    '    od;',
    '    Sort(sizes);',
    '    Print("Total unique keys: ", Length(sizes), "\\n");',
    '    Print("Max bucket size: ", Maximum(sizes), "\\n");',
    '    Print("Avg bucket size: ", Float(Sum(sizes)) / Float(Length(sizes)), "\\n");',
    '    bigBuckets := Filtered(sizes, s -> s >= 10);',
    '    Print("Buckets with >= 10 groups: ", Length(bigBuckets), "\\n");',
    '    Print("Buckets with >= 100 groups: ", Length(Filtered(sizes, s -> s >= 100)), "\\n");',
    '    Print("Top 10 bucket sizes: ", sizes{[Maximum(1, Length(sizes)-9)..Length(sizes)]}, "\\n");',
    'end;',
    '',
]

for partition, fname, n in COMBOS:
    filepath = os.path.join(BASE_DIR, partition, fname).replace("\\", "/")
    if not os.path.exists(filepath.replace("/", "\\")):
        print(f"SKIP: {filepath} not found")
        continue
    part_list = partition.replace("[", "").replace("]", "").split(",")
    part_gap = "[" + ",".join(part_list) + "]"
    gap_lines.append(f'_AnalyzeBucketSizes("{filepath}", {n}, {part_gap});')

gap_lines.append('LogTo();')
gap_lines.append('QUIT;')

with open(script_path, "w") as f:
    f.write("\n".join(gap_lines))

# Launch GAP
script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/bucket_analysis.g"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Launching GAP bucket analysis...")
proc = subprocess.Popen(
    [BASH_EXE, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     f'exec ./gap.exe -q -o 0 "{script_cygwin}"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=GAP_RUNTIME)
proc.wait(timeout=1800)

with open(log_file.replace("/", "\\")) as f:
    content = f.read()
# Filter out syntax warnings, keep only the analysis output
for line in content.split("\n"):
    if line.startswith("===") or line.startswith("Loaded ") or \
       line.startswith("Total ") or line.startswith("Max ") or \
       line.startswith("Avg ") or line.startswith("Buckets ") or \
       line.startswith("Top "):
        print(line)
