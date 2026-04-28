"""Compare FPF subdirects from a specific combo with orbital ON vs OFF.
Saves generator lists to identify the missing group."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"

def run_combo_test(orbital_on, log_suffix):
    log_file = f"C:/Users/jeffr/Downloads/Lifting/combo_compare_{log_suffix}.log"
    gens_file = f"C:/Users/jeffr/Downloads/Lifting/combo_compare_{log_suffix}_gens.txt"
    orbital_val = "true" if orbital_on else "false"

    gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_H1_ORBITAL := {orbital_val};
Print("USE_H1_ORBITAL = ", USE_H1_ORBITAL, "\\n");

# Clear caches
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Build the specific combo: [6,5] x [6,8] x [3,2]
f1 := TransitiveGroup(6, 5);
f2 := TransitiveGroup(6, 8);
f3 := TransitiveGroup(3, 2);

# Shift groups to separate orbits
shifted := [];
offs := [];
off := 0;

Add(offs, off);
Add(shifted, Image(ActionHomomorphism(f1, MovedPoints(f1)), f1));
# Actually use ShiftGroup utility
shifted := [];
offs := [];
off := 0;

for factor in [f1, f2, f3] do
    Add(offs, off);
    degree := NrMovedPoints(factor);
    shift_perm := MappingPermListList([1..degree], [off+1..off+degree]);
    Add(shifted, Group(List(GeneratorsOfGroup(factor), g -> g^shift_perm)));
    off := off + degree;
od;

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P = ", StructureDescription(P), ", |P| = ", Size(P), "\\n");
Print("Degree: ", off, "\\n");

# Compute the partition normalizer (N) for [6,6,3]
# Since we have [6,5] x [6,8] x [3,2], the first two orbits have different
# factor types, so no orbit-swapping normalizer elements
N := P;  # For distinct factors, partition normalizer = direct product

# Find FPF subdirects
Print("Finding FPF subdirects with orbital=", USE_H1_ORBITAL, "...\\n");
t0 := Runtime();
result := FindFPFClassesByLifting(P, shifted, offs, N);
elapsed := Runtime() - t0;
Print("Found ", Length(result), " FPF subdirects in ", elapsed, "ms\\n");

# Save generators
outf := OutputTextFile("{gens_file}", false);
for i in [1..Length(result)] do
    gens := GeneratorsOfGroup(result[i]);
    img_lists := List(gens, g -> ListPerm(g, off));
    WriteAll(outf, Concatenation(String(img_lists), "\\n"));
od;
CloseStream(outf);
Print("Saved generators to {gens_file}\\n");

# Also save invariants for each group
Print("\\nInvariants:\\n");
for i in [1..Length(result)] do
    G := result[i];
    Print("  Group ", i, ": |G|=", Size(G), " AbelInv=",
          SortedList(AbelianInvariants(G)), "\\n");
od;

LogTo();
QUIT;
'''

    temp_gap = os.path.join(LIFTING_DIR, f"temp_combo_{log_suffix}.g")
    with open(temp_gap, "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_combo_{log_suffix}.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    print(f"  Starting {log_suffix} at {time.strftime('%H:%M:%S')}")
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
    )
    stdout, stderr = process.communicate(timeout=3600)
    print(f"  Finished {log_suffix} at {time.strftime('%H:%M:%S')}")

    if stderr.strip():
        err_lines = [l for l in stderr.split('\n') if 'Error' in l]
        if err_lines:
            print(f"  ERRORS: {err_lines[:5]}")

    log_path = log_file.replace("/", os.sep)
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            log = f.read()
        # Print last 30 lines
        for line in log.split('\n')[-30:]:
            print(f"  {line}")

    return log_path

print("=" * 60)
print("Combo-level comparison: [6,5] x [6,8] x [3,2]")
print("=" * 60)

# Run OFF first
print("\n--- Orbital OFF ---")
run_combo_test(False, "off")

# Run ON
print("\n--- Orbital ON ---")
run_combo_test(True, "on")

# Compare results
print("\n--- Comparison ---")
gens_off = os.path.join(LIFTING_DIR, "combo_compare_off_gens.txt")
gens_on = os.path.join(LIFTING_DIR, "combo_compare_on_gens.txt")

if os.path.exists(gens_off) and os.path.exists(gens_on):
    with open(gens_off) as f:
        off_lines = [l.strip() for l in f if l.strip()]
    with open(gens_on) as f:
        on_lines = [l.strip() for l in f if l.strip()]
    print(f"OFF: {len(off_lines)} groups")
    print(f"ON:  {len(on_lines)} groups")
    print(f"Delta: {len(off_lines) - len(on_lines)}")
else:
    print("Generator files not found!")

print("=" * 60)
