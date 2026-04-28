"""Concatenate all holt_engine/*.g files into a single monolithic file
in the dependency order defined by holt_engine/loader.g."""

import os

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
HOLT_DIR = os.path.join(LIFTING_DIR, "holt_engine")
OUT_FILE = os.path.join(LIFTING_DIR, "holt_engine_monolith.g")

# Order from loader.g (excluding loader.g itself since we replace its logic).
FILES = [
    "subgroup_record.g",
    "heartbeat.g",
    "checkpoint.g",
    "dedup_invariants.g",
    "series_builder.g",
    "module_layer.g",
    "orbit_action.g",
    "presentation_engine.g",
    "cohomology_lifter.g",
    "tf_database.g",
    "symmetric_specialization.g",
    "engine.g",
    "verification.g",
]

HEADER = """# holt_engine_monolith.g
#
# Auto-generated monolithic concatenation of holt_engine/*.g.
#
# Load order matches holt_engine/loader.g: leaves first, engine last.
# Requires the legacy engine to be loaded first, since many Holt*
# wrappers delegate into lifting_algorithm.g / lifting_method_fast_v2.g /
# cohomology.g / h1_action.g / modules.g:
#
#     Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
#     Read("C:/Users/jeffr/Downloads/Lifting/holt_engine_monolith.g");
#
# Feature flag matches loader.g.

if not IsBound(USE_HOLT_ENGINE) then
  USE_HOLT_ENGINE := false;
fi;

HOLT_ENGINE_DIR := "C:/Users/jeffr/Downloads/Lifting/holt_engine/";

"""

FOOTER = """
HOLT_ENGINE_LOADED := true;
Print("holt_engine_monolith loaded\\n");
"""

def section_banner(name):
    bar = "#" * 78
    return f"{bar}\n# SECTION: {name}\n{bar}\n\n"


def main():
    parts = [HEADER]
    for fname in FILES:
        path = os.path.join(HOLT_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            contents = f.read()
        parts.append(section_banner(fname))
        parts.append(contents)
        if not contents.endswith("\n"):
            parts.append("\n")
        parts.append("\n")
    parts.append(FOOTER)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("".join(parts))
    total_lines = sum(1 for _ in open(OUT_FILE, "r", encoding="utf-8"))
    total_bytes = os.path.getsize(OUT_FILE)
    print(f"Wrote {OUT_FILE}")
    print(f"  {total_lines} lines, {total_bytes} bytes")
    print(f"  {len(FILES)} source files concatenated")


if __name__ == "__main__":
    main()
