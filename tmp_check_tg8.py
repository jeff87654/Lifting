import subprocess, os
gap_code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/tg8_check.log");
Print("TG(8,Y) structures:\\n");
for Y in [1,2,4,12,22,25,32,35,36,37,48,49] do
    G := TransitiveGroup(8, Y);
    Print("TG(8,", Y, "): |G|=", Size(G),
          ", IsSolvable=", IsSolvable(G),
          ", IsPrimitive=", IsPrimitive(G, [1..8]),
          ", Desc=", StructureDescription(G), "\\n");
od;
Print("\\nIsomorphism test for anomalous set {12,25,32,36,37,48,49}:\\n");
anom := [12, 25, 32, 36, 37, 48, 49];
for i in [1..Length(anom)] do
    for j in [i+1..Length(anom)] do
        G1 := TransitiveGroup(8, anom[i]);
        G2 := TransitiveGroup(8, anom[j]);
        iso := IsomorphismGroups(G1, G2);
        Print("  TG(8,", anom[i], ") vs TG(8,", anom[j], "): |G1|=", Size(G1),
              " |G2|=", Size(G2),
              " isomorphic=", iso <> fail, "\\n");
    od;
od;
LogTo();
QUIT;
'''
with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_tg8.g", "w") as f:
    f.write(gap_code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_tg8.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
try:
    o, e = p.communicate(timeout=120)
except subprocess.TimeoutExpired:
    p.kill(); o, e = p.communicate()
try:
    print(open(r"C:\Users\jeffr\Downloads\Lifting\tg8_check.log").read())
except FileNotFoundError:
    print("STDOUT:", o[-1500:])
    print("STDERR:", e[-500:])
