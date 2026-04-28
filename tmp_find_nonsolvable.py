"""Enumerate non-solvable transitive groups of degree 2..18 via GAP."""
import subprocess, os
code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/nonsolvable_tgs.log");
for d in [2..18] do
    nonsol := [];
    n := NrTransitiveGroups(d);
    for i in [1..n] do
        G := TransitiveGroup(d, i);
        if not IsSolvable(G) then
            Add(nonsol, i);
        fi;
    od;
    Print(d, ": ", nonsol, "\\n");
od;
LogTo();
QUIT;
'''
with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_find_nonsolvable.g", "w") as f:
    f.write(code)
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_find_nonsolvable.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
try:
    p.communicate(timeout=300)
except subprocess.TimeoutExpired:
    p.kill(); p.communicate()
print(open(r"C:\Users\jeffr\Downloads\Lifting\nonsolvable_tgs.log").read())
