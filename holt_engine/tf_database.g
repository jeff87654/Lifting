# holt_engine/tf_database.g
#
# Write-through cache of subgroup classes for trivial-Fitting groups.
# A miss computes (via ConjugacyClassesSubgroups or CCS fast path for
# |Q| <= 96), serializes to database/tf_groups/<key>.g, appends to
# database/tf_groups/index.g, and logs to tf_miss_log.txt.
#
# Public API:
#   HoltIdentifyTFTop(Q)           -> rec(key, size, id_group, canonical_group)
#     Keys by IdGroup(Q) when |Q| <= 2000, else by a structural fingerprint
#     (order + derived_length + composition_factor_multiset +
#      |abelianization| + |center|) compatible with TF_SUBGROUP_LATTICE.
#   HoltLoadTFClasses(tf_info)     -> [ subgroup classrep in canonical_group ]
#     Lookup order:
#       1. In-memory HOLT_TF_CACHE
#       2. database/tf_groups/<key>.g on disk
#       3. TF_SUBGROUP_LATTICE (existing monolithic cache)
#       4. TransitiveGroup library via GetSubgroupClassReps
#       5. Compute via ConjugacyClassesSubgroups + write-through
#   HoltTFDatabasePath()           -> path to database/tf_groups/
#   HoltTFMissLogPath()            -> path to tf_miss_log.txt
#   HoltSaveTFEntry(key, Q, classes, elapsed_ms) -> write-through serializer
#   HoltLogTFMiss(key, size, structure_desc, elapsed_ms)

if not IsBound(HOLT_TF_CACHE) then
  HOLT_TF_CACHE := rec();
fi;

if not IsBound(HOLT_TF_STATS) then
  HOLT_TF_STATS := rec(
    mem_hits := 0,
    disk_hits := 0,
    tf_lattice_hits := 0,
    transitive_hits := 0,
    misses := 0,
    maximal_recursions := 0,
    total_load_ms := 0
  );
fi;

# Default thresholds bound at module load so _HoltSubgroupsRecurse can
# reference them even when called outside HoltLoadTFClasses (e.g. via
# HoltFPFViaMaximals from the dispatcher pre-check path).
# Raised from 5000 to 200000 per the M4 plan — direct CCS on groups up
# to 200K is typically in the seconds-to-minute range and preferable to
# max-recursion's broader descent. Above 200K, routes to
# HoltTopSubgroupsByMaximals (FPF context) or HoltSubgroupsViaMaximals (generic).
if not IsBound(HOLT_TF_CCS_DIRECT) then
  HOLT_TF_CCS_DIRECT := 200000;
fi;
if not IsBound(HOLT_TF_WARN_ABOVE) then
  HOLT_TF_WARN_ABOVE := 50000;
fi;

# Recursive-from-maximals (architecture doc §3.2).
# For |Q| too big for CCS, enumerate maximal subgroup classes (much
# cheaper than full ConjugacyClassesSubgroups) and recurse on each.
#
# CRITICAL: do NOT go through HoltLoadTFClasses for the recursion.
# That cache is keyed by IdGroup (abstract isomorphism), so two
# embedded copies of the same abstract group (e.g. two A_8-classes
# of AGL(3,2)) would share a cache entry whose subgroups are
# embedded in the FIRST copy's ambient — wrong for the second copy.
# We need subgroups embedded in the SPECIFIC M we're recursing on.

# Enumerate subgroup classes of G, direct or via further recursion
_HoltSubgroupsRecurse := function(G)
  if Size(G) <= HOLT_TF_CCS_DIRECT then
    return List(ConjugacyClassesSubgroups(G), Representative);
  fi;
  return HoltSubgroupsViaMaximals(G);
end;

HoltSubgroupsViaMaximals := function(G)
  local max_classes, all_subs, M, subs_of_M, H, found, K,
        sz, bucketKey, buckets, keyStr;
  Print("    [maximal-rec] |G|=", Size(G), " expanding maximals...\n");
  max_classes := List(ConjugacyClassesMaximalSubgroups(G), Representative);
  Print("    [maximal-rec] |G|=", Size(G), " -> ", Length(max_classes),
        " maximal classes: sizes ", List(max_classes, Size), "\n");

  # Collect subgroups from each maximal, bucket by size for cheap dedup
  buckets := rec();
  bucketKey := String(Size(G));
  buckets.(bucketKey) := [G];

  for M in max_classes do
    subs_of_M := _HoltSubgroupsRecurse(M);
    for H in subs_of_M do
      sz := Size(H);
      bucketKey := String(sz);
      if not IsBound(buckets.(bucketKey)) then
        buckets.(bucketKey) := [H];
      else
        # Dedup under G-conjugation (OnPoints = conjugation action).
        found := false;
        for K in buckets.(bucketKey) do
          if RepresentativeAction(G, H, K, OnPoints) <> fail then
            found := true;
            break;
          fi;
        od;
        if not found then
          Add(buckets.(bucketKey), H);
        fi;
      fi;
    od;
  od;

  all_subs := [];
  for keyStr in RecNames(buckets) do
    Append(all_subs, buckets.(keyStr));
  od;
  return all_subs;
end;

HoltTFDatabasePath := function()
  return "C:/Users/jeffr/Downloads/Lifting/database/tf_groups/";
end;

HoltTFMissLogPath := function()
  return "C:/Users/jeffr/Downloads/Lifting/tf_miss_log.txt";
end;

# Structural fingerprint matching TF_SUBGROUP_LATTICE key format
# (see database/tf_groups/tf_subgroup_lattice.g). Used when |Q| > 2000.
HoltStructuralKey := function(Q)
  local sz, ds, ab, cs, nc, ex, z;
  sz := Size(Q);
  ds := DerivedSeriesOfGroup(Q);
  ds := List(ds, Size);
  ab := AbelianInvariants(Q);
  cs := List(CompositionSeries(Q), Size);
  nc := NrConjugacyClasses(Q);
  ex := Exponent(Q);
  z := Size(Center(Q));
  return Concatenation(
    "lg_", String(sz),
    "_ds=", String(ds),
    "_ab=", String(ab),
    "_cs=", String(cs),
    "_nc=", String(nc),
    "_ex=", String(ex),
    "_z=", String(z)
  );
end;

HoltIdentifyTFTop := function(Q)
  local sz, idk, desc;
  sz := Size(Q);
  if sz = 1 then
    return rec(
      key := "trivial",
      size := 1,
      id_group := [1, 1],
      canonical_group := Q,
      structure_desc := "1"
    );
  fi;
  if sz <= 2000 then
    idk := IdGroup(Q);
    return rec(
      key := Concatenation("id_", String(idk[1]), "_", String(idk[2])),
      size := sz,
      id_group := idk,
      canonical_group := Q,
      structure_desc := fail
    );
  fi;
  return rec(
    key := HoltStructuralKey(Q),
    size := sz,
    id_group := fail,
    canonical_group := Q,
    structure_desc := fail
  );
end;

# _HoltSerializeGroupGens: serialize a perm group as ListPerm-style lists,
# compatible with GroupFromGenLists / PermFromList in load_database.g.
_HoltSerializeGroupGens := function(G)
  local gens, moved_max, g;
  gens := [];
  if not IsPermGroup(G) then
    return gens;
  fi;
  moved_max := LargestMovedPoint(G);
  if moved_max = 0 then
    return gens;
  fi;
  for g in GeneratorsOfGroup(G) do
    if g = () then
      Add(gens, []);
    else
      Add(gens, ListPerm(g, moved_max));
    fi;
  od;
  return gens;
end;

# Iso-transport default — set at module-load time so all gate-sites
# (tf_database.g tier 5, lifting_algorithm.g LookupTFSubgroups,
# warm_cache.g _ProcessEntry) see the flag defined from first call.
# See memory/iso_transport_bug.md for the S_16 off-by-1 trace.
if not IsBound(HOLT_DISABLE_ISO_TRANSPORT) then
  HOLT_DISABLE_ISO_TRANSPORT := true;
fi;

# Perm-rep signature: a short hex fingerprint of Q's specific permutation
# generators. Distinct perm-reps of the same abstract group get distinct
# signatures, so the disk cache `<key>__<sig>.g` never thrashes across
# perm-reps of the same IdGroup. Polynomial hash (mod a Mersenne-ish prime)
# over sorted generator strings — deterministic and collision-resistant
# enough for cache keys.
_HoltPermRepSignature := function(Q)
  local gens, s, h, c, i;
  gens := SortedList(List(GeneratorsOfGroup(Q), String));
  s := Concatenation(gens);
  h := 0;
  for i in [1..Length(s)] do
    c := IntChar(s[i]);
    h := (h * 131 + c) mod 1000000007;
  od;
  return HexStringInt(h);
end;

HoltSaveTFEntry := function(key, Q, classes, elapsed_ms)
  local path, tmpfile, canonicalGens, classGens, tag, sig, fullKey;
  sig := _HoltPermRepSignature(Q);
  fullKey := Concatenation(key, "__", sig);
  path := Concatenation(HoltTFDatabasePath(), fullKey, ".g");
  # Temp file with worker-unique suffix (Runtime + Random) so concurrent
  # writers don't clobber each other's in-progress files. Atomic rename
  # at the end publishes the result as a single step, so readers (via
  # Read() in HoltLoadTFClasses) never see a partial file.
  tag := Concatenation(String(Runtime()), "_", String(Random(1, 10^9)));
  tmpfile := Concatenation(path, ".tmp.", tag);
  canonicalGens := _HoltSerializeGroupGens(Q);
  classGens := List(classes, _HoltSerializeGroupGens);
  PrintTo(tmpfile, "# holt_engine tf_database entry. Auto-generated.\n");
  AppendTo(tmpfile, "HOLT_TF_LAST_LOAD := rec(\n");
  AppendTo(tmpfile, "  key := \"", key, "\",\n");
  AppendTo(tmpfile, "  sig := \"", sig, "\",\n");
  AppendTo(tmpfile, "  size := ", Size(Q), ",\n");
  AppendTo(tmpfile, "  canonical_gens := ", canonicalGens, ",\n");
  AppendTo(tmpfile, "  classes := ", classGens, ",\n");
  AppendTo(tmpfile, "  elapsed_ms := ", elapsed_ms, "\n");
  AppendTo(tmpfile, ");\n");
  # Atomic publish. If another worker beat us to it, last-writer-wins --
  # both workers computed semantically equivalent class lists (different
  # generators may be chosen but the classes coincide up to conjugacy).
  # `mv` over Cygwin is atomic on both POSIX and NTFS.
  Exec(Concatenation("mv '", tmpfile, "' '", path, "'"));
  return path;
end;

HoltLogTFMiss := function(key, size, structure_desc, elapsed_ms)
  local path;
  path := HoltTFMissLogPath();
  AppendTo(path, key, "\t", size, "\t",
    String(structure_desc), "\t", elapsed_ms, "\n");
end;

# Convert stored gen lists back into a group acting on the same points as Q
_HoltGroupFromStoredGens := function(genLists, moved_points)
  local gens, lst, p;
  gens := [];
  for lst in genLists do
    if Length(lst) > 0 then
      p := PermList(lst);
      if p <> () then
        Add(gens, p);
      fi;
    fi;
  od;
  if Length(gens) = 0 then
    return Group(());
  fi;
  return Group(gens);
end;

# Cache-only lookup: return subgroup class reps if any tier has them,
# else return fail WITHOUT triggering a fresh compute. This lets the
# clean-pipeline dispatcher consult the cache cheaply before deciding
# between max-rec and direct CCS for large Q.
HoltLoadTFClassesIfCached := function(tf_info)
  local key, sig, fullKey, Q, path, classes, t0, H, lat_entry, moved;
  key := tf_info.key;
  Q := tf_info.canonical_group;
  sig := _HoltPermRepSignature(Q);
  fullKey := Concatenation(key, "__", sig);
  t0 := Runtime();

  # 1. In-memory (fullKey)
  if IsBound(HOLT_TF_CACHE.(fullKey)) then
    classes := HOLT_TF_CACHE.(fullKey);
    if ForAll(classes, H -> IsSubset(Q, H)) then
      HOLT_TF_STATS.mem_hits := HOLT_TF_STATS.mem_hits + 1;
      return classes;
    fi;
    Unbind(HOLT_TF_CACHE.(fullKey));
  fi;

  # 2. On-disk per-(key, sig) file
  path := Concatenation(HoltTFDatabasePath(), fullKey, ".g");
  if IsReadableFile(path) then
    HOLT_TF_LAST_LOAD := fail;
    Read(path);
    if IsBound(HOLT_TF_LAST_LOAD) and HOLT_TF_LAST_LOAD <> fail then
      classes := List(HOLT_TF_LAST_LOAD.classes,
                      gl -> _HoltGroupFromStoredGens(gl, fail));
      if ForAll(classes, H -> IsSubset(Q, H)) then
        HOLT_TF_CACHE.(fullKey) := classes;
        HOLT_TF_STATS.disk_hits := HOLT_TF_STATS.disk_hits + 1;
        HOLT_TF_STATS.total_load_ms := HOLT_TF_STATS.total_load_ms + (Runtime() - t0);
        return classes;
      fi;
    fi;
  fi;

  # 3. TF_SUBGROUP_LATTICE (monolithic, abstract-only; keyed by `key`).
  if IsBound(TF_SUBGROUP_LATTICE) and IsBound(TF_SUBGROUP_LATTICE.(key)) then
    lat_entry := TF_SUBGROUP_LATTICE.(key);
    if IsBound(lat_entry.subgroups) then
      classes := lat_entry.subgroups;
      if ForAll(classes, H -> IsSubset(Q, H)) then
        HOLT_TF_CACHE.(fullKey) := classes;
        HOLT_TF_STATS.tf_lattice_hits := HOLT_TF_STATS.tf_lattice_hits + 1;
        return classes;
      fi;
    fi;
  fi;

  # 4. TransitiveGroup library via GetSubgroupClassReps.
  if IsBound(GetSubgroupClassReps) then
    moved := MovedPoints(Q);
    if Length(moved) > 0 and IsTransitive(Q, moved) then
      classes := GetSubgroupClassReps(Q);
      if Length(classes) > 0 and ForAll(classes, H -> IsSubset(Q, H)) then
        HOLT_TF_CACHE.(fullKey) := classes;
        HOLT_TF_STATS.transitive_hits := HOLT_TF_STATS.transitive_hits + 1;
        return classes;
      fi;
    fi;
  fi;

  # 5. Iso-transport: any cached (key, *) can be transported to current Q
  # via IsomorphismGroups. Makes the cache robust to perm-rep differences
  # between how Q was constructed in the caller vs. whoever wrote the
  # disk entry.
  return _HoltIsoTransportFromCache(key, Q, fullKey, t0);
end;

# Helper: does string s start with prefix p?
_HoltStartsWith := function(s, p)
  local i;
  if Length(s) < Length(p) then return false; fi;
  for i in [1..Length(p)] do
    if s[i] <> p[i] then return false; fi;
  od;
  return true;
end;

# Helper: does string s end with suffix q?
_HoltEndsWith := function(s, q)
  local i, off;
  if Length(s) < Length(q) then return false; fi;
  off := Length(s) - Length(q);
  for i in [1..Length(q)] do
    if s[off + i] <> q[i] then return false; fi;
  od;
  return true;
end;

# Look for any on-disk cache entry matching `<key>__*.g` and transport its
# classes to `Q` via IsomorphismGroups. Returns fail if no entry exists or
# no valid iso can be found.
_HoltIsoTransportFromCache := function(key, Q, fullKey, t0)
  local dir, files, f, path, Q_ref, iso, classes_ref, classes,
        ref_gens_list, prefix;
  # DISABLED BY DEFAULT. Traced to -1 class undercounts on S_16 [8,4,4] and
  # [8,6,2]. See memory/iso_transport_bug.md for analysis. Default is set
  # at module-load time below (not inside this function) so LookupTFSubgroups
  # and other gated call sites see the flag defined even before first call.
  if HOLT_DISABLE_ISO_TRANSPORT then
    return fail;
  fi;
  dir := HoltTFDatabasePath();
  files := DirectoryContents(dir);
  if files = fail then return fail; fi;
  prefix := Concatenation(key, "__");
  for f in files do
    # Match `<key>__<sig>.g` — note the literal double-underscore separator.
    if not _HoltStartsWith(f, prefix) then continue; fi;
    if not _HoltEndsWith(f, ".g") then continue; fi;
    path := Concatenation(dir, f);
    HOLT_TF_LAST_LOAD := fail;
    Read(path);
    if not (IsBound(HOLT_TF_LAST_LOAD) and HOLT_TF_LAST_LOAD <> fail) then
      continue;
    fi;
    # Reconstruct Q_ref from canonical_gens.
    if not IsBound(HOLT_TF_LAST_LOAD.canonical_gens) then continue; fi;
    ref_gens_list := HOLT_TF_LAST_LOAD.canonical_gens;
    Q_ref := _HoltGroupFromStoredGens(ref_gens_list, fail);
    if Size(Q_ref) <> Size(Q) then continue; fi;
    iso := IsomorphismGroups(Q_ref, Q);
    if iso = fail then continue; fi;
    # Transport cached class reps via iso.
    classes_ref := List(HOLT_TF_LAST_LOAD.classes,
                        gl -> _HoltGroupFromStoredGens(gl, fail));
    classes := List(classes_ref, H -> Image(iso, H));
    if ForAll(classes, H -> IsSubset(Q, H)) then
      HOLT_TF_CACHE.(fullKey) := classes;
      if not IsBound(HOLT_TF_STATS.iso_hits) then
        HOLT_TF_STATS.iso_hits := 0;
      fi;
      HOLT_TF_STATS.iso_hits := HOLT_TF_STATS.iso_hits + 1;
      HOLT_TF_STATS.total_load_ms := HOLT_TF_STATS.total_load_ms + (Runtime() - t0);
      return classes;
    fi;
  od;
  return fail;
end;

HoltLoadTFClasses := function(tf_info)
  local key, sig, fullKey, Q, path, classes, t0, H, lat_entry, moved, cached;
  key := tf_info.key;
  Q := tf_info.canonical_group;
  sig := _HoltPermRepSignature(Q);
  fullKey := Concatenation(key, "__", sig);
  t0 := Runtime();

  # Try all cache tiers first. HoltLoadTFClassesIfCached validates each
  # hit via IsSubset(Q, H), so hash collisions are caught.
  cached := HoltLoadTFClassesIfCached(tf_info);
  if cached <> fail then
    return cached;
  fi;

  # 5. Miss: compute + write-through with safe concurrent publish.
  #
  # The architecture doc §3.2 prefers erroring on miss, but for a working
  # system lazy population is operator-friendly. We bend the rule:
  #   - Compute via ConjugacyClassesSubgroups(Q) up to a HARD CEILING.
  #   - Write atomically to disk so concurrent workers don't corrupt the
  #     file.
  #   - HOLT_TF_STRICT_MISS (opt-in, default false): error on ANY miss.
  #   - HOLT_TF_CCS_CEILING (default 20000): above this, raise Error so
  #     the dispatcher can fall back to legacy fast paths (Goursat +
  #     D_4^3 + S_n short-circuit). CCS on groups above 20k often takes
  #     minutes-to-hours and blocks the worker.
  #   - HOLT_TF_WARN_ABOVE (default 5000): warning threshold.
  #
  # Before computing, re-check the disk: another worker may have written
  # the file between our earlier check and now. If so, load from disk.
  if IsBound(HOLT_TF_STRICT_MISS) and HOLT_TF_STRICT_MISS then
    HoltLogTFMiss(key, tf_info.size, tf_info.structure_desc, -1);
    Error("HoltLoadTFClasses: strict-miss mode, |Q|=", Size(Q),
          " not in database. Set HOLT_TF_STRICT_MISS := false ",
          "to enable lazy population.");
  fi;
  # Two-tier compute strategy (per architecture doc §3.2):
  #   |Q| <= HOLT_TF_CCS_DIRECT  -> direct CCS  (default 5000)
  #   otherwise                   -> recursive-from-maximals (HoltSubgroupsViaMaximals)
  #
  # No hard upper bound by default — max-recursion's cost scales with
  # MaximalSubgroupClassReps, which for A_8 x A_8 (|G|=406M) runs in ~1s.
  # Set HOLT_TF_MAXREC_CEILING to force an Error boundary for paranoia.
  if not IsBound(HOLT_TF_CCS_DIRECT) then
    HOLT_TF_CCS_DIRECT := 5000;
  fi;
  if IsBound(HOLT_TF_MAXREC_CEILING) and Size(Q) > HOLT_TF_MAXREC_CEILING then
    HoltLogTFMiss(key, tf_info.size, tf_info.structure_desc, -2);
    Error("HoltLoadTFClasses: |Q|=", Size(Q),
          " exceeds HOLT_TF_MAXREC_CEILING=", HOLT_TF_MAXREC_CEILING);
  fi;

  # Double-check disk — another worker may have just written to the same
  # (key, sig) path between our tier-2 check and now. Still validates
  # IsSubset(Q, H) as a safety backstop against hash collisions.
  path := Concatenation(HoltTFDatabasePath(), fullKey, ".g");
  if IsReadableFile(path) then
    HOLT_TF_LAST_LOAD := fail;
    Read(path);
    if IsBound(HOLT_TF_LAST_LOAD) and HOLT_TF_LAST_LOAD <> fail then
      classes := List(HOLT_TF_LAST_LOAD.classes,
                      gl -> _HoltGroupFromStoredGens(gl, fail));
      if ForAll(classes, H -> IsSubset(Q, H)) then
        HOLT_TF_CACHE.(fullKey) := classes;
        HOLT_TF_STATS.disk_hits := HOLT_TF_STATS.disk_hits + 1;
        HOLT_TF_STATS.total_load_ms := HOLT_TF_STATS.total_load_ms + (Runtime() - t0);
        return classes;
      fi;
      # Stale entry; fall through to fresh compute.
    fi;
  fi;

  if Size(Q) > HOLT_TF_CCS_DIRECT then
    # Maximal-subgroup recursion (architecture doc §3.2)
    Print("  [HoltLoadTFClasses] |Q|=", Size(Q),
          " above CCS-direct (", HOLT_TF_CCS_DIRECT,
          "); using maximal-subgroup recursion.\n");
    HOLT_TF_STATS.maximal_recursions := HOLT_TF_STATS.maximal_recursions + 1;
    classes := HoltSubgroupsViaMaximals(Q);
  else
    classes := List(ConjugacyClassesSubgroups(Q), Representative);
  fi;
  HoltSaveTFEntry(key, Q, classes, Runtime() - t0);
  HoltLogTFMiss(key, tf_info.size, tf_info.structure_desc, Runtime() - t0);
  HOLT_TF_CACHE.(fullKey) := classes;
  HOLT_TF_STATS.misses := HOLT_TF_STATS.misses + 1;
  HOLT_TF_STATS.total_load_ms := HOLT_TF_STATS.total_load_ms + (Runtime() - t0);
  return classes;
end;
