import subprocess, os, time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

log_file = "C:/Users/jeffr/Downloads/Lifting/quick_test2.log"
gap_code = '''
LogTo("''' + log_file + '''");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
allPass := true;
known := rec(); known.2:=2; known.3:=4; known.4:=11; known.5:=19; known.6:=56; known.7:=96; known.8:=296;
for n in [2..8] do
    count := CountAllConjugacyClassesFast(n);
    if count = known.(n) then Print("S_",n,"=",count," PASS\n");
    else Print("S_",n,"=",count," FAIL (expected ",known.(n),")\n"); allPass:=false; fi;
od;
if allPass then Print("ALL PASS\n"); else Print("FAILURES\n"); fi;
LogTo(); QUIT;
'''

with open(os.path.join(LIFTING_DIR, "quick_test2.g"), "w") as f:
    f.write(gap_code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

start = time.time()
p = subprocess.Popen(
    [BASH_EXE, "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "/cygdrive/c/Users/jeffr/Downloads/Lifting/quick_test2.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=GAP_RUNTIME)
stdout, stderr = p.communicate(timeout=300)
print(f"Done in {time.time()-start:.1f}s")

with open(os.path.join(LIFTING_DIR, "quick_test2.log")) as f:
    for line in f:
        if "S_" in line or "PASS" in line or "FAIL" in line:
            print(line.rstrip())
