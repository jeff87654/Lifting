"""Compare prebug's 154 groups vs w506's 147 groups for combo 6
([5,5,2,2,2,2]/[2,1]_[2,1]_[2,1]_[2,1]_[5,5]_[5,5]).

For each prebug group: does it N-conjugate to some w506 group?
  - If yes, prebug group is represented in w506's output — 'OK'.
  - If no, prebug group is missing from w506 — w506 is undercounting.

Also: are all prebug groups pairwise non-N-conjugate?
  - If some pair is N-conjugate to each other, prebug was over-counting
    (contains duplicates).
"""
import subprocess, os

code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/verify_combo6.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n===== Loading prebug and w506 groups for combo 6 =====\\n\\n");

# Load prebug file (154 groups)
prebug_path := "C:/Users/jeffr/Downloads/Lifting/parallel_s18_prebugfix_backup/[5,5,2,2,2,2]/[2,1]_[2,1]_[2,1]_[2,1]_[5,5]_[5,5].g";
# Load w506 file (mangled name)
w506_path := "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[5,5,2,2,2,2]/2,1]_[2,1]_[2,1]_[2,1]_[5,5]_[5,5.g";

LoadGroupsFile := function(path)
    local str, cleaned, c, i, L, groups, j, lineStart, lineEnd, line;
    str := StringFile(path);
    if str = fail then
        Print("  FAILED to read ", path, "\\n");
        return fail;
    fi;
    # Remove GAP line-continuation backslash-newline pairs
    cleaned := "";
    L := Length(str);
    i := 1;
    while i <= L do
        if i < L and str[i] = '\\\\' and str[i+1] = '\\n' then
            i := i + 2;  # skip backslash and newline
        else
            Add(cleaned, str[i]);
            i := i + 1;
        fi;
    od;
    L := Length(cleaned);
    groups := [];
    i := 1;
    while i <= L do
        j := i;
        while j <= L and cleaned[j] <> '\\n' do j := j + 1; od;
        lineStart := i;
        lineEnd := j - 1;
        if lineEnd >= lineStart and cleaned[lineStart] = '[' then
            line := cleaned{[lineStart..lineEnd]};
            Add(groups, EvalString(Concatenation("Group(", line, ")")));
        fi;
        i := j + 1;
    od;
    return groups;
end;

prebug_groups := LoadGroupsFile(prebug_path);
Print("Prebug groups loaded: ", Length(prebug_groups), "\\n");

w506_groups := LoadGroupsFile(w506_path);
Print("W506 groups loaded:   ", Length(w506_groups), "\\n\\n");

# Build partition normalizer
T5 := TransitiveGroup(5, 5);;
T2 := TransitiveGroup(2, 1);;
partition := [5, 5, 2, 2, 2, 2];;
factors := [T5, T5, T2, T2, T2, T2];;
N := BuildPerComboNormalizer(partition, factors, 18);;
Print("|N| = ", Size(N), "\\n\\n");

# Group sizes
Print("Prebug size distribution:\\n");
sizes := List(prebug_groups, Size);;
for s in Set(sizes) do
    Print("  |G|=", s, ": count=", Number(sizes, x -> x = s), "\\n");
od;
Print("\\nW506 size distribution:\\n");
w506_sizes := List(w506_groups, Size);;
for s in Set(w506_sizes) do
    Print("  |G|=", s, ": count=", Number(w506_sizes, x -> x = s), "\\n");
od;

# For each prebug group, find matching w506 group
Print("\\n===== Matching prebug -> w506 =====\\n");
matched := 0;
unmatched := [];
for i in [1..Length(prebug_groups)] do
    matching := fail;
    for j in [1..Length(w506_groups)] do
        if Size(prebug_groups[i]) = Size(w506_groups[j]) then
            if RepresentativeAction(N, prebug_groups[i], w506_groups[j]) <> fail then
                matching := j;
                break;
            fi;
        fi;
    od;
    if matching <> fail then
        matched := matched + 1;
    else
        Add(unmatched, i);
    fi;
od;
Print("  Matched: ", matched, " / ", Length(prebug_groups), "\\n");
Print("  Unmatched: ", Length(unmatched), "\\n");
if Length(unmatched) > 0 then
    Print("\\nUnmatched prebug groups (missing from w506):\\n");
    for i in unmatched do
        Print("  prebug[", i, "]: |G|=", Size(prebug_groups[i]),
              " gens=", Length(GeneratorsOfGroup(prebug_groups[i])), "\\n");
    od;
fi;

# For each w506 group, find matching prebug group (reverse direction)
Print("\\n===== Matching w506 -> prebug =====\\n");
w506_matched := 0;
w506_unmatched := [];
for i in [1..Length(w506_groups)] do
    matching := fail;
    for j in [1..Length(prebug_groups)] do
        if Size(w506_groups[i]) = Size(prebug_groups[j]) then
            if RepresentativeAction(N, w506_groups[i], prebug_groups[j]) <> fail then
                matching := j;
                break;
            fi;
        fi;
    od;
    if matching <> fail then
        w506_matched := w506_matched + 1;
    else
        Add(w506_unmatched, i);
    fi;
od;
Print("  Matched: ", w506_matched, " / ", Length(w506_groups), "\\n");
Print("  Unmatched: ", Length(w506_unmatched), "\\n");
if Length(w506_unmatched) > 0 then
    Print("\\nUnmatched w506 groups (new, not in prebug):\\n");
    for i in w506_unmatched do
        Print("  w506[", i, "]: |G|=", Size(w506_groups[i]), "\\n");
    od;
fi;

# Check prebug for internal duplicates
Print("\\n===== Prebug pairwise (same size buckets) =====\\n");
dup_pairs := 0;
for i in [1..Length(prebug_groups)] do
    for j in [i+1..Length(prebug_groups)] do
        if Size(prebug_groups[i]) = Size(prebug_groups[j]) then
            if RepresentativeAction(N, prebug_groups[i], prebug_groups[j]) <> fail then
                dup_pairs := dup_pairs + 1;
                Print("  DUPLICATE: prebug[", i, "] ~ prebug[", j, "]\\n");
                if dup_pairs > 10 then
                    Print("  ... (stopping dump at 10)\\n");
                    break;
                fi;
            fi;
        fi;
    od;
    if dup_pairs > 10 then break; fi;
od;
Print("Prebug internal N-conjugate pairs: ", dup_pairs, "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_verify_combo6.g", "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_verify_combo6.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
try:
    p.communicate(timeout=3600)
except subprocess.TimeoutExpired:
    p.kill(); p.communicate()

log = open(r"C:\Users\jeffr\Downloads\Lifting\verify_combo6.log").read()
started = False
for line in log.splitlines():
    if "===== Loading" in line:
        started = True
    if started:
        print(line)
