"""
Test whether H^1 cache hits have mismatched generators.
For each cache hit during [6,6,3] computation, log whether the cached module
and current module have the same generators.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/cache_gen_test.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Monkey-patch CachedComputeH1 to detect generator mismatches
_OrigCachedComputeH1 := CachedComputeH1;
_CACHE_MISMATCH_COUNT := 0;
_CACHE_HIT_COUNT := 0;

CachedComputeH1 := function(module)
    local cacheKey, result, cachedModule, i, sameGens;

    if not H1_CACHE_ENABLED then
        return ComputeH1(module);
    fi;

    cacheKey := ComputeModuleFingerprint(module);

    if IsBound(H1_CACHE.(cacheKey)) then
        _CACHE_HIT_COUNT := _CACHE_HIT_COUNT + 1;
        result := H1_CACHE.(cacheKey);

        # Check if the cached module has the same generators
        cachedModule := result.module;

        sameGens := true;
        if Length(module.generators) = Length(cachedModule.generators) then
            for i in [1..Length(module.generators)] do
                if module.generators[i] <> cachedModule.generators[i] then
                    sameGens := false;
                    break;
                fi;
            od;
        else
            sameGens := false;
        fi;

        if not sameGens then
            _CACHE_MISMATCH_COUNT := _CACHE_MISMATCH_COUNT + 1;
            Print("CACHE MISMATCH #", _CACHE_MISMATCH_COUNT,
                  " (hit #", _CACHE_HIT_COUNT, "):\\n");
            Print("  |G|=", Size(module.group),
                  " p=", module.p, " dim=", module.dimension, "\\n");
            Print("  current gens: ", module.generators, "\\n");
            Print("  cached  gens: ", cachedModule.generators, "\\n");
            if IsBound(module.preimageGens) and IsBound(cachedModule.preimageGens) then
                Print("  current preimageGens: ", module.preimageGens, "\\n");
                Print("  cached  preimageGens: ", cachedModule.preimageGens, "\\n");
            fi;
        fi;

        return result;
    fi;

    # Cache miss - compute and store
    result := ComputeH1(module);
    H1_CACHE.(cacheKey) := result;
    return result;
end;

# Run [6,6,3] with orbital ON
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
t0 := Runtime();
result := FindFPFClassesForPartition(15, [6, 6, 3]);
t1 := Runtime();

Print("\\n=== SUMMARY ===\\n");
Print("Result: ", Length(result), " classes\\n");
Print("Time: ", (t1-t0)/1000.0, "s\\n");
Print("Cache hits: ", _CACHE_HIT_COUNT, "\\n");
Print("Cache mismatches: ", _CACHE_MISMATCH_COUNT, "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_cache_gen_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_cache_gen_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting at {time.strftime('%H:%M:%S')}")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    env=env, cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=7200)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['CACHE MISMATCH', 'SUMMARY', 'Result:', 'Time:',
                                      'Cache hits', 'Cache mismatches', 'current gens',
                                      'cached  gens', 'current preimage', 'cached  preimage',
                                      '|G|=']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
