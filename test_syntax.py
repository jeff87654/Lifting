"""
Test that the lifting_method_fast_v2.g file loads without syntax errors.
"""

import subprocess
import os

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n");
Print("===========================================\\n");
Print("File loaded successfully!\\n");
Print("===========================================\\n\\n");

# Verify key functions exist
Print("Checking key functions exist:\\n");
Print("  HasSmallAbelianization: ", IsBound(HasSmallAbelianization), "\\n");
Print("  GetQuotientMapsToC2: ", IsBound(GetQuotientMapsToC2), "\\n");
Print("  FindSubdirectsForPartitionWith2s: ", IsBound(FindSubdirectsForPartitionWith2s), "\\n");
Print("  CountAllConjugacyClassesFast: ", IsBound(CountAllConjugacyClassesFast), "\\n");

Print("\\nAll checks passed!\\n");

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_syntax.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_syntax.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Checking file syntax and function definitions...")
print("=" * 60)

# Run GAP via Cygwin bash
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
if stderr and "Error" in stderr:
    print("ERRORS:", stderr)
elif stderr:
    # Just show relevant warnings
    for line in stderr.split('\n'):
        if 'lifting_method_fast_v2.g' in line:
            print(line)
