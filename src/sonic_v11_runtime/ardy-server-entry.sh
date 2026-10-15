#!/usr/bin/env bash
# Task-named server entry: verified evidence or a NEW bounded simulation.
# No public server, GPU, real robot, or shared vendor-source replacement.
set -euo pipefail
D=/data/group4/20261006-093203-codex-6385a841
case "${1:-evidence}" in
  evidence)
    exec /usr/bin/python3 -B "$D/wave5_records.py"
    ;;
  status)
    exec /usr/bin/python3 -B "$D/active_records.py"
    ;;
  profile-check)
    shift
    exec bash "$D/run.sh" "$D/profile_preflight.py" "$@"
    ;;
  preflight)
    shift
    exec bash "$D/run.sh" "$D/execution_preflight.py" "$@"
    ;;
  simulate)
    shift
    [[ $# -ge 1 ]] || { printf 'Need a NEW wN_... output name matching the registered active wave; all launches count toward its 20-slot budget.\n' >&2; exit 2; }
    exec bash "$D/run.sh" "$D/sonic_grasp.py" "$@"
    ;;
  *)
    printf 'Usage: bash %s evidence | status | preflight SOURCE NEW_OUTPUT | profile-check PROFILE NEW_JSON | simulate wN_NEW_NAME [explicit experiment options, optional --motion-profile]\n' "$0" >&2
    exit 2
    ;;
esac
