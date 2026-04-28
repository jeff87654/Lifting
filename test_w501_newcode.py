"""Re-run TG(6,16) x TG(12,242) alone with the new GeneralAutHomComplements
(stab-dedup per-hom + multi-invariant cross-hom dedup)."""
import subprocess, os

code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/w501_newcode.log");
GENERAL_AUT_HOM_VERBOSE := true;
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n========== W501 combo with NEW code ==========\\n");

T1 := TransitiveGroup(6, 16);
T2 := TransitiveGroup(12, 242);
shifted := [ShiftGroup(T1, 0), ShiftGroup(T2, 6)];
offsets := [0, 6];
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("|P| = ", Size(P), "\\n");
N := BuildPerComboNormalizer([6, 12], [T1, T2], 18);
Print("|N| = ", Size(N), "\\n\\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

Print("\\nRESULT: ", Length(fpf), " raw FPF, ",
      Float(elapsed/1000), "s\\n");

LogTo();
QUIT;
''';

with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_w501_newcode.g", "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_w501_newcode.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print("Log: C:/Users/jeffr/Downloads/Lifting/w501_newcode.log")
