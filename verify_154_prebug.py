"""Verify that the 154 prebug groups for W506 combo 6
([5,5,2,2,2,2]/[2,1]^4_[5,5]^2) are pairwise non-N-conjugate.

Pre-processes the prebug file in Python (handles GAP's '\\\\n' line
continuations) into a clean GAP-loadable script, then runs strict pairwise
RA(N, ...) inside each invariant bucket.
"""
import subprocess, os, re

LOG = "C:/Users/jeffr/Downloads/Lifting/verify_154.log"
PREBUG = "C:/Users/jeffr/Downloads/Lifting/parallel_s18_prebugfix_backup/" \
         "[5,5,2,2,2,2]/[2,1]_[2,1]_[2,1]_[2,1]_[5,5]_[5,5].g"
GROUPS_FILE = "C:/Users/jeffr/Downloads/Lifting/tmp_154_groups.g"

# Preprocess: read prebug file, strip GAP line continuations, extract array entries.
with open(PREBUG, 'r') as f:
    content = f.read()
content = content.replace('\\\n', '')  # GAP line-continuation = backslash + newline

group_strs = []
for line in content.split('\n'):
    line = line.strip()
    if line.startswith('[') and line.endswith(']'):
        group_strs.append(line)

print(f"Extracted {len(group_strs)} groups from prebug file.")

# Write a clean GAP-readable file: PREBUG_GROUPS := [Group(...), Group(...), ...];
with open(GROUPS_FILE, 'w') as f:
    f.write("PREBUG_GROUPS := [\n")
    for s in group_strs:
        f.write(f"  Group({s}),\n")
    f.write("];\n")

print(f"Wrote {GROUPS_FILE}")

code = f'''
LogTo("{LOG}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("{GROUPS_FILE}");

T5 := TransitiveGroup(5, 5);;
T2 := TransitiveGroup(2, 1);;
partition := [5, 5, 2, 2, 2, 2];;
factors := [T5, T5, T2, T2, T2, T2];;
N := BuildPerComboNormalizer(partition, factors, 18);
Print("[verify] |N| = ", Size(N), "\\n");
Print("[verify] loaded ", Length(PREBUG_GROUPS), " prebug groups\\n");

inv := function(H)
    return [Size(H), AbelianInvariants(H),
            SortedList(List(Orbits(H, [1..18]), Length))];
end;

byInv := rec();
for i in [1..Length(PREBUG_GROUPS)] do
    k := String(inv(PREBUG_GROUPS[i]));
    if not IsBound(byInv.(k)) then byInv.(k) := []; fi;
    Add(byInv.(k), i);
od;
Print("[verify] ", Length(RecNames(byInv)), " distinct invariant buckets\\n");

t0 := Runtime();
dups := [];
n_ra := 0;
for k in RecNames(byInv) do
    bucket := byInv.(k);
    if Length(bucket) <= 1 then continue; fi;
    for i in [1..Length(bucket)-1] do
        for j in [i+1..Length(bucket)] do
            n_ra := n_ra + 1;
            r := RepresentativeAction(N,
                                      PREBUG_GROUPS[bucket[i]],
                                      PREBUG_GROUPS[bucket[j]]);
            if r <> fail then
                Add(dups, [bucket[i], bucket[j]]);
                Print("[verify] DUPLICATE: ", bucket[i], " ~ ", bucket[j],
                      " (bucket size ", Length(bucket), ")\\n");
            fi;
        od;
    od;
od;
elapsed := Runtime() - t0;

Print("\\n=== VERIFY RESULT ===\\n");
Print("[verify] groups loaded: ", Length(PREBUG_GROUPS), "\\n");
Print("[verify] RA calls: ", n_ra, "\\n");
Print("[verify] duplicates found: ", Length(dups), "\\n");
Print("[verify] elapsed: ", Float(elapsed/1000), "s\\n");
if Length(dups) = 0 then
    Print("[verify] CONFIRMED: 154 prebug groups are pairwise non-N-conjugate.\\n");
else
    Print("[verify] WARNING: 154 prebug count is over by ", Length(dups), "\\n");
fi;

LogTo();
QUIT;
''';

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_verify_154.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_verify_154.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
