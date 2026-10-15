#!/usr/bin/env bash
# Task-named server entry: verified evidence or a NEW bounded simulation.
# No public server, GPU, real robot, or shared vendor-source replacement.
set -euo pipefail
D=/data/group4/20261006-093203-codex-6385a841
case "${1:-evidence}" in
  evidence)
    exec /usr/bin/python3 -B "$D/wave5_records.py"
    ;;
  preflight)
    shift
    exec bash "$D/run.sh" "$D/execution_preflight.py" "$@"
    ;;
  simulate)
    shift
    [[ $# -ge 1 ]] || { printf 'Need a NEW w6_... output name; all launches count toward the 20-slot budget.\n' >&2; exit 2; }
    exec bash "$D/run.sh" "$D/sonic_grasp.py" "$@"
    ;;
  *)
    printf 'Usage: bash %s evidence | preflight SOURCE NEW_OUTPUT | simulate NEW_w6_NAME [explicit experiment options]\n' "$0" >&2
    exit 2
    ;;
esac
