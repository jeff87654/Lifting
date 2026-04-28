"""
Test whether H^1 cache causes generator mismatch between cached and current module.
For the [6,6,3] partition, check if two different parents produce modules with
matching fingerprints but different generators.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/cache_mismatch.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Reconstruct the [6,6,3] combo [T66_5, T66_8, T63_2]
T63_2 := TransitiveGroup(3, 2);
T66_5 := TransitiveGroup(6, 5);
T66_8 := TransitiveGroup(6, 8);
factors := [T66_5, T66_8, T63_2];
shifted := [];
offs := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
series := RefinedChiefSeries(P);

# Lift through layers 1 to 7 to get parents at the last layer
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();

parents := [P];
for i in [1..Length(series)-2] do
    ClearH1Cache();
    parents := LiftThroughLayer(P, series[i], series[i+1], parents, shifted, offs, fail);
od;
Print("Parents at final layer: ", Length(parents), "\\n\\n");

# For each parent S, form Q = S/L (L = trivial) and create the module
M := series[Length(series)-1];  # M = C_3
L := series[Length(series)];    # L = trivial

Print("=== Module comparison across parents ===\\n");
Print("M = ", M, " |M| = ", Size(M), "\\n");
Print("L = ", L, " |L| = ", Size(L), "\\n\\n");

moduleInfos := [];
for idx in [1..Length(parents)] do
    S := parents[idx];
    hom := NaturalHomomorphismByNormalSubgroup(S, L);
    Q := ImagesSource(hom);
    M_bar := Image(hom, M);
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));

    fingerprint := ComputeModuleFingerprint(module);

    # Collect key info about the module
    info := rec(
        idx := idx,
        sizeS := Size(S),
        sizeQ := Size(Q),
        sizeG := Size(module.group),
        ngens := Length(module.generators),
        dim := module.dimension,
        p := module.p,
        fingerprint := fingerprint,
        generators := module.generators,
        preimageGens := module.preimageGens,
        matrices := module.matrices
    );
    Add(moduleInfos, info);

    Print("Parent ", idx, ": |S|=", Size(S), " |Q|=", Size(Q), " |G|=", Size(module.group),
          " ngens=", Length(module.generators), " dim=", module.dimension,
          " fp=", fingerprint, "\\n");
    Print("  generators: ", module.generators, "\\n");
    Print("  preimageGens: ", module.preimageGens, "\\n");
od;

# Check for fingerprint collisions with different generators
Print("\\n=== Fingerprint collision check ===\\n");
for i in [1..Length(moduleInfos)] do
    for j in [i+1..Length(moduleInfos)] do
        if moduleInfos[i].fingerprint = moduleInfos[j].fingerprint then
            sameGens := moduleInfos[i].generators = moduleInfos[j].generators;
            samePre := moduleInfos[i].preimageGens = moduleInfos[j].preimageGens;
            sameMat := moduleInfos[i].matrices = moduleInfos[j].matrices;
            Print("  FP COLLISION: parent ", i, " vs parent ", j,
                  " sameGens=", sameGens,
                  " samePreimage=", samePre,
                  " sameMatrices=", sameMat, "\\n");
            if not sameGens then
                Print("    DANGER: generators differ but fingerprint matches!\\n");
                Print("    parent ", i, " gens: ", moduleInfos[i].generators, "\\n");
                Print("    parent ", j, " gens: ", moduleInfos[j].generators, "\\n");
            fi;
            if not samePre then
                Print("    DANGER: preimageGens differ but fingerprint matches!\\n");
                Print("    parent ", i, " preimageGens: ", moduleInfos[i].preimageGens, "\\n");
                Print("    parent ", j, " preimageGens: ", moduleInfos[j].preimageGens, "\\n");
            fi;
        fi;
    od;
od;

# Now verify: does the cache produce different results?
# Clear cache and process parent 1 (fills cache), then parent 2 (uses cache)
Print("\\n=== Cache hit test ===\\n");
ClearH1Cache();

S1 := parents[1];
hom1 := NaturalHomomorphismByNormalSubgroup(S1, L);
Q1 := ImagesSource(hom1);
M_bar1 := Image(hom1, M);
module1 := ChiefFactorAsModule(Q1, M_bar1, TrivialSubgroup(M_bar1));
H1_1 := CachedComputeH1(module1);
Print("Parent 1: H1 dim=", H1_1.H1Dimension, " numCompl=", H1_1.numComplements, "\\n");
Print("  H1_1.module = module1? ", IsIdenticalObj(H1_1.module, module1), "\\n");

if Length(parents) >= 2 then
    S2 := parents[2];
    hom2 := NaturalHomomorphismByNormalSubgroup(S2, L);
    Q2 := ImagesSource(hom2);
    M_bar2 := Image(hom2, M);
    module2 := ChiefFactorAsModule(Q2, M_bar2, TrivialSubgroup(M_bar2));
    H1_2 := CachedComputeH1(module2);
    Print("Parent 2: H1 dim=", H1_2.H1Dimension, " numCompl=", H1_2.numComplements, "\\n");
    Print("  H1_2.module = module2? ", IsIdenticalObj(H1_2.module, module2), "\\n");
    Print("  H1_2.module = module1? ", IsIdenticalObj(H1_2.module, module1), "\\n");
    Print("  Same H1 object? ", IsIdenticalObj(H1_1, H1_2), "\\n");

    if IsIdenticalObj(H1_1, H1_2) and not (module1.generators = module2.generators) then
        Print("\\n*** BUG CONFIRMED: Cache returns H1 from module1 but used with module2 ***\\n");
        Print("*** module1.generators = ", module1.generators, "\\n");
        Print("*** module2.generators = ", module2.generators, "\\n");
    fi;
fi;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_cache_mismatch.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_cache_mismatch.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting at {time.strftime('%H:%M:%S')}")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    env=env, cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=600)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['Parent', 'FP COLLISION', 'DANGER', 'BUG',
                                      'generators', 'preimageGens', 'Cache',
                                      'dim=', 'module', 'Same', '===', 'sameGens']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
