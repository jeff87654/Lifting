import subprocess, os

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/temp_2groups.log");
for i in [1..50] do
    G := TransitiveGroup(8, i);
    ord := Size(G);
    if IsPrimePowerInt(ord) and SmallestRootInt(ord) = 2 then
        nn := Length(NormalSubgroups(G));
        Print("TG(8,", i, "): order=", ord, ", ", nn, " normal subgroups\n");
    fi;
od;
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_2groups.g", "w") as f:
    f.write(gap_commands)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_2groups.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime"
)
stdout, stderr = p.communicate(timeout=60)

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_2groups.log") as f:
    print(f.read())
