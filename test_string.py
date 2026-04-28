"""Test String formatting in GAP."""

import subprocess
import os

gap_commands = '''
Print("String(3): [", String(3), "]\\n");
Print("String(3, 2): [", String(3, 2), "]\\n");

# What we want is "03"
# Test concatenation
test := Concatenation("degree_", String(3, 2), ".g");
Print("Test path: [", test, "]\\n");

# The problem might be that String(3, 2) gives " 3" (space padded) not "03"
# Let's try a different approach
ZeroPad := function(n, width)
    local s;
    s := String(n);
    while Length(s) < width do
        s := Concatenation("0", s);
    od;
    return s;
end;

Print("ZeroPad(3, 2): [", ZeroPad(3, 2), "]\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_string.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_string.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=60)
print(stdout)
if stderr:
    print("STDERR:", stderr)
