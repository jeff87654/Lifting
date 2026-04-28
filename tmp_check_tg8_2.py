import subprocess, os
gap_code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/tg8_check2.log");
# Check what the anomalous 7 have in common
for Y in [12, 25, 32, 36, 37, 48, 49] do
    G := TransitiveGroup(8, Y);
    nNormals := Length(NormalSubgroups(G));
    isNaturalSym := IsNaturalSymmetricGroup(G);
    isNaturalAlt := IsNaturalAlternatingGroup(G);
    Print("TG(8,", Y, "): |G|=", Size(G),
          ", nNormals=", nNormals,
          ", NaturalSym=", isNaturalSym,
          ", NaturalAlt=", isNaturalAlt, "\n");
od;
# Also check TG(8,22) and TG(8,35) which produce LARGE counts for comparison
Print("\nComparison (non-anomalous):\n");
for Y in [22, 35, 9, 11, 15] do
    G := TransitiveGroup(8, Y);
    nNormals := Length(NormalSubgroups(G));
    Print("TG(8,", Y, "): |G|=", Size(G), ", nNormals=", nNormals, "\n");
od;
LogTo();
QUIT;
'''
with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_tg8_2.g", "w") as f:
    f.write(gap_code)
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_tg8_2.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
p.communicate(timeout=120)
print(open(r"C:\Users\jeffr\Downloads\Lifting\tg8_check2.log").read())
