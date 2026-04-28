# holt_engine/checkpoint.g
#
# Save/Resume using the existing .g monolithic + .log delta format.
# The heavy lifting is in lifting_method_fast_v2.g (_SaveCheckpoint at
# :1958, _AppendCheckpointDelta at :2081, _LoadCheckpoint at :2147).
# These wrappers expose the clean Holt API; internals stay identical so
# checkpoints written by the legacy engine remain resumable by the Holt
# engine (Phase 9 S18 resume relies on this).
#
# Public API:
#   HoltSaveCheckpoint(path, completedKeys, all_fpf, totalCandidates,
#                      addedCount [,invKeys])
#       -> _SaveCheckpoint
#   HoltAppendCheckpointDelta(path, comboKey, newGroups, totalCandidates,
#                             addedCount, totalFpf [,newInvKeys])
#       -> _AppendCheckpointDelta
#   HoltResumeCheckpoint(path)
#       -> _LoadCheckpoint -- returns rec(completedKeys, allFpfGens,
#          totalCandidates, addedCount, invKeys?, richInvActive?) or fail.

HoltSaveCheckpoint := function(arg)
  CallFuncList(_SaveCheckpoint, arg);
end;

HoltAppendCheckpointDelta := function(arg)
  CallFuncList(_AppendCheckpointDelta, arg);
end;

HoltResumeCheckpoint := function(path)
  return _LoadCheckpoint(path);
end;
