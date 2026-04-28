"""Validate the mismatched combo file at the byte level.

Check every reconstructed generator list line:
  1. Starts with '[' and ends with ']' (well-formed)
  2. Balanced brackets/parens
  3. All permutation cycles are valid (tuples of ints in GAP cycle notation)

If every line passes, in-place dedup is safe. If any line is malformed
(truncated mid-cycle, two lines concatenated, etc.), we need a different
recovery strategy.
"""
import os
import re

PATH = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\[6,4,4,2,2]\[2,1]_[2,1]_[4,1]_[4,3]_[6,9].g"


def reconstruct_lines(text):
    """Undo GAP's line-continuation backslash-newline wrapping, then split
    on real newlines. Return list of (source_start_line, content)."""
    out = []
    src_line = 1
    buf = []
    buf_start = src_line
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n and text[i + 1] == "\n":
            # continuation — skip the backslash+newline, keep src_line counting
            i += 2
            src_line += 1
            continue
        if ch == "\n":
            out.append((buf_start, "".join(buf)))
            buf = []
            i += 1
            src_line += 1
            buf_start = src_line
            continue
        buf.append(ch)
        i += 1
    if buf:
        out.append((buf_start, "".join(buf)))
    return out


def check_line(line):
    """Return (ok, problem). Expects a generator-list line like
    '[(1,2),(3,4),...]' — a comma-separated list of GAP permutation cycles.
    """
    if not line.startswith("["):
        return True, "(not a gen line — skipping)"
    if not line.endswith("]"):
        return False, "missing trailing ']'"
    # Bracket/paren balance
    depth_sq = 0
    depth_rd = 0
    for c in line:
        if c == "[":
            depth_sq += 1
        elif c == "]":
            depth_sq -= 1
            if depth_sq < 0:
                return False, "unbalanced: too many ']'"
        elif c == "(":
            depth_rd += 1
        elif c == ")":
            depth_rd -= 1
            if depth_rd < 0:
                return False, "unbalanced: too many ')'"
    if depth_sq != 0:
        return False, f"square-bracket mismatch ({depth_sq:+d})"
    if depth_rd != 0:
        return False, f"paren mismatch ({depth_rd:+d})"
    # Inner content must be comma-separated cycles like (a,b,c)(d,e)
    inner = line[1:-1].strip()
    if inner == "":
        return True, None  # empty generator list is legal (trivial group)
    # Split on top-level commas (between cycles). Easiest: verify that
    # every '(...)' block is well-formed and ints between commas are numeric.
    # Walk the content, ensure structure is a sequence of (\d+(,\d+)*).
    j = 0
    m = len(inner)
    while j < m:
        # Skip permissible whitespace
        while j < m and inner[j] in " \t":
            j += 1
        if j >= m:
            break
        # At this point we expect '(' starting a cycle, or just after
        # a comma a '(' or continuation. Cycles may concatenate: (1,2)(3,4)
        # Also commas between generators: (1,2,3),(4,5)
        if inner[j] == ",":
            j += 1
            continue
        if inner[j] != "(":
            # Some generators are e.g. "()" — but we always enter with '('
            return False, f"unexpected char {inner[j]!r} at col {j}"
        # Parse cycle: '(' <int> ( ',' <int> )* ')'
        j += 1
        started = False
        while True:
            while j < m and inner[j] in " \t":
                j += 1
            if j < m and inner[j] == ")":
                j += 1
                break
            # Integer
            k = j
            while j < m and inner[j].isdigit():
                j += 1
            if j == k:
                return False, f"expected digit at col {j}"
            started = True
            while j < m and inner[j] in " \t":
                j += 1
            if j < m and inner[j] == ",":
                j += 1
                continue
            if j < m and inner[j] == ")":
                j += 1
                break
            return False, f"unexpected char {inner[j]!r} at col {j} inside cycle"
    return True, None


def main():
    with open(PATH, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    size = os.path.getsize(PATH)
    print(f"file size: {size} bytes, {text.count(chr(10))} raw newlines")

    logical = reconstruct_lines(text)
    gen_lines = [(src, ln) for src, ln in logical if ln.startswith("[")]
    header_lines = [(src, ln) for src, ln in logical if ln.startswith("# ")]
    other = [(src, ln) for src, ln in logical if ln and not ln.startswith("[") and not ln.startswith("# ")]
    print(f"logical lines: {len(logical)}")
    print(f"  gen-lines:    {len(gen_lines)}")
    print(f"  header-lines: {len(header_lines)}")
    print(f"  other non-empty: {len(other)}")
    if other:
        print(f"  SAMPLE non-gen/non-header lines:")
        for src, ln in other[:5]:
            print(f"    src line {src}: {ln[:80]!r}")

    bad = []
    for src, ln in gen_lines:
        ok, problem = check_line(ln)
        if not ok:
            bad.append((src, problem, ln[:100]))

    print(f"\nmalformed gen-lines: {len(bad)}")
    for src, problem, snippet in bad[:10]:
        print(f"  src line {src}: {problem}")
        print(f"    content: {snippet!r}")
    if len(bad) > 10:
        print(f"  ... and {len(bad) - 10} more")

    # Also flag duplicate header lines (would indicate two headers concatenated)
    header_counts = {}
    for _, ln in header_lines:
        header_counts[ln] = header_counts.get(ln, 0) + 1
    dup_hdr = {ln: c for ln, c in header_counts.items() if c > 1}
    if dup_hdr:
        print(f"\nDUPLICATE header lines (suggests two complete headers merged):")
        for ln, c in dup_hdr.items():
            print(f"  x{c}: {ln}")
    else:
        print("\nno duplicate header lines")


if __name__ == "__main__":
    main()
