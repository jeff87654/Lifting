"""Re-run the regressed combo [2,1]_[6,16]_[10,32] in partition [10,6,2]
with the new GeneralAutHomComplements enabled and see how many FPF classes
are produced. Compare vs the 8 prebugfix groups."""
import subprocess, os

code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_regressed.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("USE_GENERAL_AUT_HOM = ", USE_GENERAL_AUT_HOM, "\\n\\n");

T10 := TransitiveGroup(10, 32);;
T6  := TransitiveGroup(6, 16);;
T2  := TransitiveGroup(2, 1);;

Print("|T10| = ", Size(T10), "\\n");
Print("|T6|  = ", Size(T6),  "\\n");
Print("|T2|  = ", Size(T2),  "\\n\\n");

# partition [10,6,2], descending: block1=1..10, block2=11..16, block3=17..18
shifted := [ShiftGroup(T10, 0), ShiftGroup(T6, 10), ShiftGroup(T2, 16)];;
offsets := [0, 10, 16];;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));;
Print("|P| = ", Size(P), "\\n\\n");

N := BuildPerComboNormalizer([10, 6, 2], [T10, T6, T2], 18);;
Print("|N| = ", Size(N), "\\n\\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

Print("\\n=== RESULT ===\\n");
Print("Raw FPF candidates: ", Length(fpf), "\\n");
Print("Lifting elapsed: ", Float(elapsed/1000), "s\\n");

# Dedup
byInv := rec();
all_fpf := [];
CURRENT_BLOCK_RANGES := [[1,10], [11,16], [17,18]];
for H in fpf do
    if AddIfNotConjugate(N, H, all_fpf, byInv, ComputeSubgroupInvariant) then
    fi;
od;
Print("Deduped: ", Length(all_fpf), " classes\\n");
Print("Sizes: ", List(all_fpf, Size), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_test_regress.g", "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_test_regress.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
try:
    p.communicate(timeout=1200)
except subprocess.TimeoutExpired:
    p.kill(); p.communicate()

log = open(r"C:\Users\jeffr\Downloads\Lifting\test_regressed.log").read()
started = False
for line in log.splitlines():
    if "USE_GENERAL_AUT_HOM" in line:
        started = True
    if started:
        print(line)
