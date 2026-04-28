# holt_engine/heartbeat.g
#
# Routes heartbeat emissions through a single global with three call-sites
# (mid-dedup, post-combo, mid-layer) preserved verbatim from the old engine.
#
# Public API:
#   HoltEmitHeartbeat(msg)      -> append "msg" to _HEARTBEAT_FILE if set
#   HoltHeartbeatNoop(msg)      -> discard (used in tests)
#   HOLT_HEARTBEAT_CALLBACK     -> current callback
#
# Text formats (verbatim from lifting_method_fast_v2.g + lifting_algorithm.g):
#   "alive {t}s {combo} dedup {i}/{total}"
#   "alive {t}s {combo} done, combo #{n} fpf={count}"
#   "alive {t}s {combo} layer [{type}] parent {i}/{total}"

HoltEmitHeartbeat := function(msg)
  local path;
  if not IsBound(_HEARTBEAT_FILE) then
    return;
  fi;
  path := _HEARTBEAT_FILE;
  if path = fail or path = "" then
    return;
  fi;
  AppendTo(path, msg, "\n");
end;

HoltHeartbeatNoop := function(msg)
  return;
end;

HOLT_HEARTBEAT_CALLBACK := HoltEmitHeartbeat;
