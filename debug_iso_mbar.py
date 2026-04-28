"""Test: does iso preserve M_bar? In Q = A_5 x A_5 there are TWO normal A_5's.
The iso may map one onto the OTHER, causing 'complements of first A_5' to
become 'complements of second A_5' in the destination."""
import subprocess, os
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = LIFTING / "debug_iso_mbar.log"

gap_commands = f'''
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");

Q1 := DirectProduct(AlternatingGroup(5), AlternatingGroup(5));
Q2 := Group([(1,2,3,4,5), (1,2,3), (10,11,12,13,14), (10,11,12)]);
emb1 := Embedding(Q1, 1);
M1 := Image(emb1);
M2 := Group([(1,2,3,4,5), (1,2,3)]);

Print("M1 = first A_5 in Q1 (moves [1..5])\\n");
Print("M2 = first A_5 in Q2 (moves [1..5])\\n");

iso := IsomorphismGroups(Q1, Q2);
Print("iso exists: ", iso <> fail, "\\n");

# Does iso map M1 to M2?
M1_img := Image(iso, M1);
Print("\\niso(M1) = ?\\n");
Print("Size: ", Size(M1_img), "\\n");
Print("Moved points: ", MovedPoints(M1_img), "\\n");
Print("M1_img = M2? ", M1_img = M2, "\\n");

# What are the normal A_5 subgroups of Q2?
nors := Filtered(NormalSubgroups(Q2), N -> Size(N) = 60);
Print("\\nNormal A_5's in Q2: ", Length(nors), "\\n");
for N in nors do
    Print("  Size=", Size(N), " moved=", MovedPoints(N),
          " == M2? ", N = M2, "\\n");
od;

# Now the critical test: cache subgroups of Q1, look up Q2, check
# whether complements-of-M1-in-Q1 are complements-of-M2-in-Q2 after iso.
TF_SUBGROUP_LATTICE := rec();
TF_SUBGROUP_LATTICE_DIRTY_KEYS := rec();
ComputeAndCacheTFSubgroups(Q1);

# Get Q1's complements of M1 directly
all_q1 := List(ConjugacyClassesSubgroups(Q1), Representative);
idx := Size(Q1) / Size(M1);
compls_q1 := Filtered(all_q1, H -> Size(H) = idx and Size(Intersection(H, M1)) = 1);
Print("\\nQ1: ", Length(compls_q1), " complements of M1\\n");

# Translate Q1's subgroups to Q2 via iso
Print("\\nTranslating Q1's subgroups via iso to Q2 perm rep...\\n");
translated := List(all_q1, function(H)
    local imgs;
    imgs := List(GeneratorsOfGroup(H), g -> Image(iso, g));
    if Length(imgs) = 0 then return TrivialSubgroup(Q2); fi;
    return Subgroup(Q2, imgs);
end);

# Filter translated for complements of M2
compls_via_iso := Filtered(translated, H -> Size(H) = idx and Size(Intersection(H, M2)) = 1);
Print("Filter for M2 in translated: ", Length(compls_via_iso), "\\n");

# Filter translated for complements of iso(M1) = M1_img
compls_via_iso_M1 := Filtered(translated, H -> Size(H) = idx and Size(Intersection(H, M1_img)) = 1);
Print("Filter for iso(M1) in translated: ", Length(compls_via_iso_M1), "\\n");

# Direct count of complements of M2 in Q2
all_q2 := List(ConjugacyClassesSubgroups(Q2), Representative);
direct_M2 := Filtered(all_q2, H -> Size(H) = idx and Size(Intersection(H, M2)) = 1);
Print("Direct CCS+filter for M2 in Q2: ", Length(direct_M2), "\\n");

LogTo();
QUIT;
'''

TMP = LIFTING / "temp_debug_iso_mbar.g"
TMP.write_text(gap_commands)
if LOG.exists():
    LOG.unlink()

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

proc = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_debug_iso_mbar.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
stdout, stderr = proc.communicate(timeout=300)
print(stdout[-2500:])
