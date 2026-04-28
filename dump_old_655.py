"""Read old [6,5,5] generators, reconstruct groups in GAP, output to file."""
import subprocess
import os

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

gens_file = os.path.join(LIFTING_DIR, "parallel_s16", "gens", "gens_6_5_5.txt")
output_file = os.path.join(LIFTING_DIR, "old_655_groups.txt")
log_file = os.path.join(LIFTING_DIR, "dump_old_655.log")

# Join continuation lines
with open(gens_file, "r") as f:
    raw = f.readlines()

joined = []
current = ""
for line in raw:
    line = line.rstrip("\n").rstrip("\r")
    if line.endswith("\\"):
        current += line[:-1]
    else:
        current += line
        if current.strip():
            joined.append(current.strip())
        current = ""
if current.strip():
    joined.append(current.strip())

print(f"Parsed {len(joined)} generator lists from {gens_file}")

# Write a GAP script that reads each generator list, builds Group, prints it
gap_script = os.path.join(LIFTING_DIR, "temp_dump_655.g")

with open(gap_script, "w") as f:
    f.write(f'LogTo("{log_file.replace(chr(92), "/")}");\n')
    f.write(f'outfile := "{output_file.replace(chr(92), "/")}";\n')
    f.write('PrintTo(outfile, "");\n')
    f.write(f'Print("Building {len(joined)} groups from old [6,5,5] generators...\\n");\n\n')

    for i, gen_str in enumerate(joined):
        f.write(f'_gens := {gen_str};\n')
        f.write(f'_perms := List(_gens, g -> PermList(g));\n')
        f.write(f'_G := Group(_perms);\n')
        f.write(f'AppendTo(outfile, "{i+1}: |G|=", Size(_G), '
                f'" gens=", _perms, "\\n");\n')
        if (i + 1) % 100 == 0:
            f.write(f'Print("{i+1}/{len(joined)} done\\n");\n')

    f.write(f'\nPrint("Done. {len(joined)} groups written to ", outfile, "\\n");\n')
    f.write('LogTo();\n')
    f.write('QUIT;\n')

print(f"GAP script written: {gap_script}")
print(f"Output will go to: {output_file}")

# Run GAP
script_cygwin = gap_script.replace("C:\\", "/cygdrive/c/").replace("\\", "/")
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print("Launching GAP...")
process = subprocess.Popen(
    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    env=env, cwd=GAP_RUNTIME
)
process.wait(timeout=600)
print(f"GAP exited with rc={process.returncode}")

# Check output
if os.path.exists(output_file):
    size = os.path.getsize(output_file)
    with open(output_file, "r") as f:
        n_lines = sum(1 for _ in f)
    print(f"Output: {output_file} ({n_lines} lines, {size/1024:.0f} KB)")
else:
    print("ERROR: No output file produced")
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            print(f"Log tail:\n{f.read()[-2000:]}")
