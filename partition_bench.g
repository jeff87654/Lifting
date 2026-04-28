
LogTo("C:/Users/jeffr/Downloads/Lifting/partition_bench.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed S1-S12 from cache
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear H^1 and FPF caches for this partition
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
FPF_SUBDIRECT_CACHE := rec();

t := Runtime();
result := FindFPFClassesForPartition(13, [5,4,4]);
elapsed := (Runtime() - t) / 1000.0;

Print("Partition [5,4,4]: ", Length(result), " classes in ", elapsed, "s\n");

LogTo();
QUIT;
