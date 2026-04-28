
LogTo("C:/Users/jeffr/Downloads/Lifting/test_regressed_nofp.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Verify factor sizes and structural types.
T10 := TransitiveGroup(10, 32);;
T6  := TransitiveGroup(6, 16);;
T2  := TransitiveGroup(2, 1);;
Print("TG(10,32): |G|=", Size(T10), " desc=", StructureDescription(T10),
      " IsNaturalS_n=", IsNaturalSymmetricGroup(T10), "\n");
Print("TG(6,16):  |G|=", Size(T6),  " desc=", StructureDescription(T6),
      " IsNaturalS_n=", IsNaturalSymmetricGroup(T6), "\n");
Print("TG(10,32) ~iso~ TG(6,16)? ",
      StructureDescription(T10) = StructureDescription(T6), "\n\n");

# Now override FindFPFClassesByLifting locally to skip fast paths 4 and 5.
# Easier: just call GoursatFPFSubdirects or the lift code directly.
shifted := [ShiftGroup(T10, 0), ShiftGroup(T6, 10), ShiftGroup(T2, 16)];;
offsets := [0, 10, 16];;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));;
N := BuildPerComboNormalizer([10, 6, 2], [T10, T6, T2], 18);;

# Brute-force: disable S_n fast path by renaming IsNaturalSymmetricGroup.
# Hack: since we can_t easily disable just fast path 4, let_s monkey-patch.
# GAP trick: rebind a filter used by the fast path.
# Alternative: directly call the _internal_ lifting.
# Let_s use _FindFPFClassesByLiftingCore if it exists; else use a flag.
#
# Simplest: set a flag that the code checks. We_ll add a guard:
DISABLE_SN_FAST_PATH := true;

# Now run.
t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

Print("\n=== RESULT (S_n fast path status: likely still ON, flag is advisory) ===\n");
Print("Raw FPF: ", Length(fpf), "\n");
Print("Sizes: ", List(fpf, Size), "\n");
Print("Elapsed: ", Float(elapsed/1000), "s\n");

LogTo();
QUIT;
