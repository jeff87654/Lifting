# Refine multi-group buckets with additional invariants
# Load the same groups, compute additional invariants for groups in multi-group buckets

startTime := Runtime();;

LogTo("C:/Users/jeffr/Downloads/Lifting/bucket_refine_output.txt");;

groups := [];;
orders := [];;

Print("Loading groups...\n");;

Read("C:/Users/jeffr/Downloads/Lifting/bucket_invariants.g.groups");;
# Actually we need to re-create the groups. Let me just re-read the original script's group definitions.
# Instead, let me just inline them here by re-generating.

# Restart: load all groups from scratch
QUIT;
