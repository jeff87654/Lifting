import subprocess, os
gap_cmd = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_tg12_214.log");
G := TransitiveGroup(12, 214);
Print("TG(12,214) = ", StructureDescription(G), "\n");
Print("|G| = ", Size(G), "\n");
Print("IsSolvable = ", IsSolvableGroup(G), "\n");
cs := ChiefSeries(G);
Print("Chief series lengths: ", List([1..Length(cs)], i -> Size(cs[i])), "\n");
for i in [1..Length(cs)-1] do
    Print("  Layer ", i, ": |M/N| = ", Size(cs[i])/Size(cs[i+1]), "\n");
od;
LogTo();
QUIT;
'''
with open(r"C:\Users\jeffr\Downloads\Lifting\test_tg12_214.g", "w") as f:
    f.write(gap_cmd)
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.run(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && exec ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_tg12_214.g"'],
    capture_output=True, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime", timeout=60)
with open(r"C:\Users\jeffr\Downloads\Lifting\test_tg12_214.log") as f:
    print(f.read())
