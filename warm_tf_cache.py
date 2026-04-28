"""Warm the TF cache by computing subgroup class reps for each (key, sig)
in the catalog. Uses isomorphism-transport: for abstract groups with
multiple perm-reps, compute CCS on ONE rep, then transport the answer
to the other perm-reps via IsomorphismGroups.

Processes in ascending |Q| order so the cache populates cheap entries
first (fastest cache-hit wins).

Usage:
  python warm_tf_cache.py                         # default: all catalog entries
  python warm_tf_cache.py --cap 1000000           # skip |Q| > cap
  python warm_tf_cache.py --no-transport          # compute CCS fresh for each
"""
import argparse
import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
CATALOG = LIFTING / "tf_top_catalog_s16_s18.jsonl"
CACHE_DIR = LIFTING / "database" / "tf_groups"
WORK_DIR = LIFTING / "warm_cache_work"
BASH_EXE = Path(r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe")


def load_catalog():
    """Dedupe by (key, sig); keep one entry per pair with generators."""
    seen = {}
    with open(CATALOG) as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["size_Q"] <= 1:
                continue  # trivial — no cache needed
            k = (rec["key"], rec["sig"])
            if k not in seen:
                seen[k] = rec
    return list(seen.values())


def already_cached(key, sig):
    path = CACHE_DIR / f"{key}__{sig}.g"
    return path.exists()


def write_gap_script(script_path, log_path, entries, cap, use_transport):
    """Generate the GAP script that computes/transports subgroup classes."""
    lines = [
        f'LogTo("{log_path.as_posix()}");',
        'Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");',
        'Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");',
        'SizeScreen([100000, 24]);',
        '',
        '# Process entries in order, grouping by key for iso-transport.',
        '_ReconstructQ := function(perm_strs)',
        '  local gens, s, p;',
        '  gens := [];',
        '  for s in perm_strs do',
        '    p := EvalString(s);',  # parses "(1,2)(3,4)" → permutation
        '    if p <> () then Add(gens, p); fi;',
        '  od;',
        '  if Length(gens) = 0 then return Group(()); fi;',
        '  return Group(gens);',
        'end;',
        '',
        '_CACHED_BY_KEY := rec();  # abstract-key -> (ref_Q, ref_classes)',
        '',
        '_ProcessEntry := function(key, sig, perm_strs, size_Q)',
        '  local Q, ref, iso, classes, H;',
        '  if IsBound(_CACHED_BY_KEY.(key)) then',
        '    # Transport from already-computed reference',
        '    ref := _CACHED_BY_KEY.(key);',
        '    Q := _ReconstructQ(perm_strs);',
        '    if Size(Q) <> Size(ref.Q) then',
        '      Print("[warn] size mismatch for key=", key, "; recomputing\\n");',
        '      classes := List(ConjugacyClassesSubgroups(Q), Representative);',
        '    else',
        '      iso := IsomorphismGroups(ref.Q, Q);',
        '      if iso = fail then',
        '        Print("[warn] iso fail for key=", key, "; recomputing\\n");',
        '        classes := List(ConjugacyClassesSubgroups(Q), Representative);',
        '      else',
        '        classes := List(ref.classes, H -> Image(iso, H));',
        '        if ForAny(classes, H -> not IsSubset(Q, H)) then',
        '          Print("[warn] iso-transport produced non-subgroup for key=", key, "; recomputing\\n");',
        '          classes := List(ConjugacyClassesSubgroups(Q), Representative);',
        '        fi;',
        '      fi;',
        '    fi;',
        '  else',
        '    Q := _ReconstructQ(perm_strs);',
        '    classes := List(ConjugacyClassesSubgroups(Q), Representative);',
        '    _CACHED_BY_KEY.(key) := rec(Q := Q, classes := classes);',
        '  fi;',
        '  HoltSaveTFEntry(key, Q, classes, 0);',
        '  return Length(classes);',
        'end;',
        '',
        '_t0 := Runtime();',
        '_done := 0;',
        '_total := ' + str(len(entries)) + ';',
    ]

    if not use_transport:
        # Skip cache-lookup; recompute everything
        lines.append('# --no-transport: recompute CCS per entry')
        lines.append('_CACHED_BY_KEY := rec();')

    # Progress file survives pipe closures / SIGPIPE.
    progress_path = WORK_DIR / "progress.txt"
    lines.append(f'_PROGRESS_PATH := "{progress_path.as_posix()}";')
    for e in entries:
        key = e["key"].replace('"', '\\"')
        sig = e["sig"]
        size_Q = e["size_Q"]
        perm_strs = e["q_gens"]
        if cap is not None and size_Q > cap:
            continue
        # GAP string list literal for perm_strs
        gs = ", ".join(f'"{s}"' for s in perm_strs)
        lines.append(
            f'_ProcessEntry("{key}", "{sig}", [{gs}], {size_Q}); '
            f'_done := _done + 1; '
            f'if _done mod 10 = 0 then '
            f'PrintTo(_PROGRESS_PATH, _done, "/", _total, " ", '
            f'(Runtime() - _t0)/1000.0, "s\\n"); fi;'
        )

    lines.append(
        'Print("DONE: ", _done, " entries cached in ", (Runtime() - _t0)/1000.0, "s\\n");'
    )
    lines.append('LogTo();')
    lines.append('QUIT;')

    script_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cap", type=int, default=None,
                        help="Skip entries with |Q| > cap")
    parser.add_argument("--no-transport", action="store_true",
                        help="Force full CCS per entry, no iso-transport")
    parser.add_argument("--skip-cached", action="store_true", default=True,
                        help="Skip entries whose cache file already exists")
    args = parser.parse_args()

    entries = load_catalog()
    if args.skip_cached:
        before = len(entries)
        entries = [e for e in entries if not already_cached(e["key"], e["sig"])]
        print(f"Catalog: {before} entries, {len(entries)} not yet cached")

    # Sort: (size_Q ascending, abstract-key) so we fill cheap entries first
    # and all entries of the same abstract key are contiguous (good for
    # iso-transport cache hits).
    entries.sort(key=lambda e: (e["size_Q"], e["key"]))

    if args.cap:
        entries = [e for e in entries if e["size_Q"] <= args.cap]
        print(f"After --cap {args.cap}: {len(entries)} entries")

    WORK_DIR.mkdir(exist_ok=True)
    script = WORK_DIR / "warm_cache.g"
    log = WORK_DIR / "warm_cache.log"
    write_gap_script(script, log, entries, args.cap, not args.no_transport)

    print(f"Entries to process: {len(entries)}")
    print(f"Script: {script}")
    print(f"Log: {log}")

    # Launch GAP
    cygwin_path = "/cygdrive/c" + str(script).replace("\\", "/").replace("C:", "")
    gap_dir = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"

    cmd = [str(BASH_EXE), "--login", "-c",
           f'cd "{gap_dir}" && ./gap.exe -q -o 0 "{cygwin_path}"']
    print("Launching GAP worker...")
    p = subprocess.Popen(cmd, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True)
    print(f"PID: {p.pid}")


if __name__ == "__main__":
    main()
