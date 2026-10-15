#!/usr/bin/env bash
# W4b arm1 driver: <=2 cells in parallel, serial batches, all with the real-robot grip target.
set -u
W=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate
B=$W/rep_ext_cfg; L=$W/logs
cd "$B" || exit 2
export GRIP_TARGET_JSON=$W/grip_real_map.json
CORS=(96,97 92,93)
i=0
while IFS='|' read -r n cx cy; do
  [ -z "$n" ] && continue
  c=${CORS[$((i%2))]}; i=$((i+1))
  while [ "$(jobs -rp | wc -l)" -ge 2 ]; do sleep 5; done
  nohup bash run_fixE.sh "$n" 25 "$cx" "$cy" 0 - "$c" >> "$L/grip_arm.launch.log" 2>&1 &
  printf 'DRIVER launched %s cpus=%s at %s\n' "$n" "$c" "$(date -u +%T)"
done < "$W/grip_arm_jobs.txt"
while [ "$(jobs -rp | wc -l)" -gt 0 ]; do sleep 5; done
printf 'DRIVER done at %s\n' "$(date -u +%T)"
