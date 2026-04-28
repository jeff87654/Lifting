"""Smoke test for M1: TF-database infrastructure.

Verifies:
  - TFGroupFingerprint deterministic and distinct for non-iso groups
  - StoreTFSubgroups + LookupTFSubgroups round-trip in memory
  - SaveTFLattice writes disk file and LoadTFLattice re-reads it
  - Isomorphism translation maps cached subgroups to a fresh perm rep
"""
import subprocess
import os
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = LIFTING / "test_m1_tf_infra.log"
TMP = LIFTING / "temp_m1_commands.g"

gap_commands = f'''
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");

Print("\\n=== TEST 1: TFGroupFingerprint deterministic ===\\n");
g1 := AlternatingGroup(5);
g2 := AlternatingGroup(5);
fp1 := TFGroupFingerprint(g1);
fp2 := TFGroupFingerprint(g2);
Print("A5 fingerprint: ", fp1, "\\n");
Print("match: ", fp1 = fp2, "\\n");

Print("\\n=== TEST 2: Fingerprints distinguish ===\\n");
g3 := SymmetricGroup(5);
fp3 := TFGroupFingerprint(g3);
Print("S5 fingerprint: ", fp3, "\\n");
Print("A5 != S5: ", fp1 <> fp3, "\\n");

Print("\\n=== TEST 3: A5 x A5 fingerprint (size 3600) ===\\n");
g4 := DirectProduct(AlternatingGroup(5), AlternatingGroup(5));
fp4 := TFGroupFingerprint(g4);
Print("A5xA5 fingerprint: ", fp4, " |G|=", Size(g4), "\\n");

Print("\\n=== TEST 4: Store/Lookup round-trip ===\\n");
subs_a5 := List(ConjugacyClassesSubgroups(g1), Representative);
Print("A5 subgroup classes: ", Length(subs_a5), "\\n");
StoreTFSubgroups(g1, subs_a5);
lookup := LookupTFSubgroups(g1);
if lookup = fail then
    Print("LOOKUP FAILED\\n");
else
    Print("Lookup returned: ", Length(lookup), " subgroups\\n");
    Print("match count: ", Length(lookup) = Length(subs_a5), "\\n");
fi;

Print("\\n=== TEST 5: Isomorphism translation (different perm rep) ===\\n");
# Same abstract group, different embedding (degree 6 action of A5 = T(6,12))
g5 := TransitiveGroup(6, 12);  # this should be A5 on 6 points
Print("|g5|=", Size(g5), " deg=", NrMovedPoints(g5), "\\n");
Print("g5 iso A5? ", IsomorphismGroups(g5, g1) <> fail, "\\n");
lookup2 := LookupTFSubgroups(g5);
if lookup2 = fail then
    Print("LOOKUP FAILED on isomorphic perm rep\\n");
else
    Print("Cross-rep lookup: ", Length(lookup2), " subgroups\\n");
    # Verify the translated subgroups actually live in g5
    ok := ForAll(lookup2, H -> IsSubgroup(g5, H));
    Print("all live in g5: ", ok, "\\n");
fi;

Print("\\n=== TEST 6: Persist via SaveTFLattice, reload ===\\n");
SaveTFLattice(true);  # dirtyOnly = true
# Reset in-memory cache and reload
TF_SUBGROUP_LATTICE := rec();
TF_SUBGROUP_LATTICE_DIRTY_KEYS := rec();
DATABASE_LOADED := false;
DATABASE_LOAD_STATS.tf_lattice := 0;
LoadTFLattice();
Print("After reload, cached entries: ", Length(RecNames(TF_SUBGROUP_LATTICE)), "\\n");
lookup3 := LookupTFSubgroups(g1);
if lookup3 = fail then
    Print("POST-RELOAD LOOKUP FAILED\\n");
else
    Print("Post-reload lookup: ", Length(lookup3), " subgroups\\n");
fi;

Print("\\n=== TEST 7: Stats ===\\n");
Print("TF_LOOKUP_STATS: ", TF_LOOKUP_STATS, "\\n");

Print("\\n=== ALL TESTS DONE ===\\n");
LogTo();
QUIT;
'''

TMP.write_text(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_m1_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

# Clear log so we don't read stale output
if LOG.exists():
    LOG.unlink()

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cygwin}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime,
)

stdout, stderr = process.communicate(timeout=300)

print("=== STDOUT ===")
print(stdout[-4000:])
print("=== STDERR ===")
print(stderr[-2000:])

if LOG.exists():
    print("\n=== LOG ===")
    print(LOG.read_text()[-4000:])
