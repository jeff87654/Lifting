"""Test: cache subgroups of A_5 x A_5 in one perm rep, lookup in another."""
import subprocess, os
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = LIFTING / "debug_tfdb_iso.log"

gap_commands = f'''
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");

# Build A_5 x A_5 in two different perm reps
Q1 := DirectProduct(AlternatingGroup(5), AlternatingGroup(5));
Print("Q1: |Q1|=", Size(Q1), " moved=", MovedPoints(Q1), "\\n");

# Q2: A_5 x A_5 acting on different points
Q2 := Group([(1,2,3,4,5), (1,2,3), (10,11,12,13,14), (10,11,12)]);
Print("Q2: |Q2|=", Size(Q2), " moved=", MovedPoints(Q2), "\\n");

# Get M_bars (first A_5 in each)
emb1_Q1 := Embedding(Q1, 1);
M1 := Image(emb1_Q1);
Print("M1: |M1|=", Size(M1), " moved=", MovedPoints(M1), "\\n");

M2 := Group([(1,2,3,4,5), (1,2,3)]);
Print("M2: |M2|=", Size(M2), " IsSubgroup(Q2,M2)? ", IsSubgroup(Q2, M2), "\\n");
Print("IsNormal(Q2,M2)? ", IsNormal(Q2, M2), "\\n");

# Reset cache
TF_SUBGROUP_LATTICE := rec();
TF_SUBGROUP_LATTICE_DIRTY_KEYS := rec();

# Step 1: Cache Q1's subgroups
Print("\\n--- Caching Q1's subgroups via ComputeAndCacheTFSubgroups ---\\n");
subs1 := ComputeAndCacheTFSubgroups(Q1);
Print("Cached ", Length(subs1), " subgroups of Q1\\n");

# Step 2: Lookup Q2 (should hit cache via iso)
Print("\\n--- Lookup Q2 (should be cache hit) ---\\n");
TF_LOOKUP_STATS := rec(calls := 0, hits := 0, misses_cached := 0,
    misses_oversized := 0, lookup_fails := 0, t_lookup := 0, t_compute := 0);
lookup2 := LookupTFSubgroups(Q2);
if lookup2 = fail then
    Print("LOOKUP FAILED!\\n");
else
    Print("Lookup returned ", Length(lookup2), " subgroups\\n");
    Print("Stats: ", TF_LOOKUP_STATS, "\\n");
fi;

# Step 3: Filter for complements of M2 in Q2 via TFDB
Print("\\n--- TFDB complement filter for (Q2, M2) ---\\n");
tf2 := EnumerateComplementsViaTFDatabase(Q2, M2);
Print("TFDB: ", Length(tf2), " complements\\n");

# Step 4: Compare with direct CCR on Q2
Print("\\n--- Direct CCR on (Q2, M2) ---\\n");
ccr2 := ComplementClassesRepresentatives(Q2, M2);
Print("CCR: ", Length(ccr2), " complements\\n");

# Step 5: Compare with ConjugacyClassesSubgroups + filter on Q2 directly
Print("\\n--- Direct ConjugacyClassesSubgroups + filter on Q2 ---\\n");
all_subs_q2 := List(ConjugacyClassesSubgroups(Q2), Representative);
idx2 := Size(Q2) / Size(M2);
Print("|Q2|=", Size(Q2), " |M2|=", Size(M2), " idx=", idx2, "\\n");
direct := Filtered(all_subs_q2, H -> Size(H) = idx2 and Size(Intersection(H, M2)) = 1);
Print("Direct filter: ", Length(direct), " complements\\n");

# Sanity: check that iso translation preserves M_bar correspondence
# Actually we don't translate M_bar, we directly intersect with current M_bar.
# The cached subgroups H are translated to live in Q2's perm rep.
# Then we intersect each with M2. So the question: do the cached
# subgroups (translated) include all complements of M2 in Q2?

# Let's check sizes of translated subgroups
Print("\\n--- Sizes of translated subgroups (lookup2) ---\\n");
sizes := SortedList(List(lookup2, Size));
sizes_direct := SortedList(List(all_subs_q2, Size));
Print("From cache, sizes: ", sizes{{[1..Minimum(20, Length(sizes))]}}, "...\\n");
Print("Direct, sizes:     ", sizes_direct{{[1..Minimum(20, Length(sizes_direct))]}}, "...\\n");
Print("Same multisets? ", sizes = sizes_direct, "\\n");

LogTo();
QUIT;
'''

TMP = LIFTING / "temp_debug_tfdb_iso.g"
TMP.write_text(gap_commands)
if LOG.exists():
    LOG.unlink()

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

proc = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_debug_tfdb_iso.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
stdout, stderr = proc.communicate(timeout=300)
print(stdout[-3000:])
