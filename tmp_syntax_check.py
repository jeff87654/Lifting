import subprocess, os
code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/syntax_check_after_fix.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Print("SYNTAX_OK\\n");
LogTo();
QUIT;
'''
with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_syntax_after_fix.g", "w") as f:
    f.write(code)
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_syntax_after_fix.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
try:
    o, e = p.communicate(timeout=90)
except subprocess.TimeoutExpired:
    p.kill(); o, e = p.communicate()
log = open(r"C:\Users\jeffr\Downloads\Lifting\syntax_check_after_fix.log").read()
# Count syntax errors and warnings
import re
errors = len(re.findall(r"Syntax error", log))
warnings = len(re.findall(r"Syntax warning", log))
print(f"SYNTAX_OK present: {'SYNTAX_OK' in log}")
print(f"Syntax errors: {errors}")
print(f"Syntax warnings: {warnings}")
if errors > 0:
    print("\nError context:")
    for m in re.finditer(r".{50}Syntax error.{100}", log):
        print(" ", m.group())
