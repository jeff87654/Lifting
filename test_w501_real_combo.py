"""Test GeneralAutHomComplements on W501's actual combo layer.

W501 is stuck on the layer with:
  |Q| = 1866240  (TG(6,16) x TG(12,242) parent)
  |M_bar| = 360  (A_6 chief factor)
  |C| = 2592, idx = 5184, gcd = 72

This builds the exact setup and times GeneralAutHomComplements vs NSCR on
one parent of the layer. If it completes in seconds instead of minutes,
we have our win.
"""
import subprocess, os

code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/w501_real.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n===== W501 combo test =====\\n");

T1 := TransitiveGroup(6, 16);
T2 := TransitiveGroup(12, 242);
Print("T1 = TG(6,16), |T1| = ", Size(T1), "\\n");
Print("T2 = TG(12,242), |T2| = ", Size(T2), "\\n");

shifted := [ShiftGroup(T1, 0), ShiftGroup(T2, 6)];
offsets := [0, 6];
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("|P| = ", Size(P), "\\n");

# Compute P's chief series to find an A_6 chief factor.
series := ChiefSeries(P);
Print("Chief series length: ", Length(series), "\\n");

for i in [1..Length(series)-1] do
    if Size(series[i]) / Size(series[i+1]) = 360 then
        Print("Found A_6 chief factor at position ", i, "\\n");
        # Build Q = P (or possibly a descendant of it containing the chief factor).
        # For the layer, Q is P modulo a chain above.
        # Simplification: test with Q = P, M_bar = series[i+1] somehow.
        break;
    fi;
od;

# Actually, the real bottleneck is complement-finding in a single parent S
# at the A_6 layer. We reconstruct that by taking P = Q as the parent.
# Try: set Q = P, M_bar the natural A_6 copy (requires it to be present).
# For now, just run FindFPFClassesByLifting with the new path enabled.

# Quick check: USE_GENERAL_AUT_HOM flag state.
Print("USE_GENERAL_AUT_HOM = ", USE_GENERAL_AUT_HOM, "\\n\\n");

# Build per-combo normalizer N and run the lifting, noting per-layer
# timings. If GeneralAutHom fires on the A_6 layer, we should see
# "GeneralAutHom:" in the log.
N := BuildPerComboNormalizer([6, 12], [T1, T2], 18);
Print("|N_per_combo| = ", Size(N), "\\n\\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;
Print("\\nRaw FPF candidates: ", Length(fpf), "\\n");
Print("Lifting elapsed: ", elapsed, "ms = ", Float(elapsed/1000), "s\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_w501_real.g", "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_w501_real.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched W501 combo test at PID {p.pid}")
print(f"Log: C:/Users/jeffr/Downloads/Lifting/w501_real.log")
