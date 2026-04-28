"""Run just the TG(6,16) x TG(12,242) combo with the new Hom-based code,
in a separate GAP process, writing to a test-only output directory so we
don't interfere with W501."""
import subprocess, os

# Test output dir — isolated from parallel_s18/[6,12]/
TEST_DIR = r"C:\Users\jeffr\Downloads\Lifting\hom_test_out"
os.makedirs(TEST_DIR, exist_ok=True)

code = f'''
LogTo("C:/Users/jeffr/Downloads/Lifting/hom_test_w501.log");
Print("Test: [6,16] x [12,242] with Hom-based fast path\\n");
Print("Started ", StringTime(Runtime()), "\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Use the same per-combo machinery the workers use, but isolated to this one combo.
T1 := TransitiveGroup(6, 16);
T2 := TransitiveGroup(12, 242);
Print("T1 = TG(6,16), |T1| = ", Size(T1), ", Desc = ", StructureDescription(T1), "\\n");
Print("T2 = TG(12,242), |T2| = ", Size(T2), ", Desc = ", StructureDescription(T2), "\\n");

# Shift factors to disjoint points: T1 on [1..6], T2 on [7..18]
shifted := [ShiftGroup(T1, 0), ShiftGroup(T2, 6)];
offsets := [0, 6];
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("|P| = ", Size(P), "\\n\\n");

# Per-combo normalizer — same as workers do
N := BuildPerComboNormalizer([6, 12], [T1, T2], 18);
Print("|N_per_combo| = ", Size(N), "\\n\\n");

# Flag already defaults true from the file; print to confirm
Print("USE_HOM_CENTRALIZER_PATH = ", USE_HOM_CENTRALIZER_PATH, "\\n\\n");

# Run the lifting directly
t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;
Print("\\nRaw fpf candidates: ", Length(fpf), "\\n");
Print("Lifting elapsed: ", elapsed, "ms = ", Float(elapsed/1000), "s\\n\\n");

# Now dedup under N
byInv := rec();
allInvKeys := [];
all_fpf := [];
addedCount := 0;
CURRENT_BLOCK_RANGES := [[1,6], [7,18]];
invFunc := ComputeSubgroupInvariant;
for H in fpf do
    if AddIfNotConjugate(N, H, all_fpf, byInv, invFunc) then
        addedCount := addedCount + 1;
    fi;
od;
elapsed := Runtime() - t0;
Print("Deduped: ", Length(all_fpf), " classes\\n");
Print("Total (lifting + dedup): ", elapsed, "ms = ", Float(elapsed/1000), "s\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_w501_test.g", "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_w501_test.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched test combo GAP at PID {p.pid}")
print(f"Log: C:/Users/jeffr/Downloads/Lifting/hom_test_w501.log")
print(f"To check: tail the log, or wait for completion.")
