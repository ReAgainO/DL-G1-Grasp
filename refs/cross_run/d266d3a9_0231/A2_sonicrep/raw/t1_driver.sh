#!/usr/bin/env bash
# Lane A2 T1 driver: success arm + negative-control arm, SEQUENTIAL (no CPU
# contention, so the run-to-run bitwise-determinism claim is not confounded).
# Writes only inside the lane's own copy root. No quota gate, no rules_sha.
set -u
D=/data/group4/20261008-023143-qoder-d266d3a9/A2_sonicrep
cd "$D" || exit 9
echo $$ > "$D/raw/T1.driver.pid"

# Frozen T1 recipe = the owner's published wave-7 success flag string with
# --motion-profile REMOVED (see FINDING.md "纠正 2": w7_repeat327 has
# motion_profile=null and native_npz=78eac68c...=src/original_motions/near_s42.npz).
FLAGS=(--strict-execution --finger-gain 3 --grip-preload-mm 1.5 --table-front .24
  --lift-height .15 --reference-fallback --grip-frame-lift --direct-table
  --adaptive-hand --kinematic-servo --pinch-geometry --flat-pinch --surface-capture
  --phase-clips --capture-radius .007 --c2-reference --endpoint-seed
  --endpoint-seed-native --contact-close --contact-entry-dwell .04 --gravity-arm 1
  --opponent middle --close-seconds .5 --neutral-shoulder-offset .2
  --clearance-approach --clearance-native-branch --clearance-branch-servo)

export A2_CPUS=${A2_CPUS:-96,97,98,99}
export A2_TIMEOUT=${A2_TIMEOUT:-900}
export A2_NICE=${A2_NICE:-19}

{
  echo "== T1 driver start $(date -u +%FT%TZ) host=$(hostname) cpus=$A2_CPUS timeout=${A2_TIMEOUT}s"
  echo "== driver_sha256=$(sha256sum "$D/raw/t1_driver.sh" 2>/dev/null | cut -d' ' -f1)"
  echo "== frozen flags: ${FLAGS[*]}"
  echo
  echo "-- arm1 a2rep327_1 (P1 success arm)"
  bash run_own.sh a2rep327_1 "${FLAGS[@]}"
  echo "arm1_rc=$?"
  echo
  echo "-- arm2 a2rep327_nogrip_1 (P2 negative control = arm1 + --no-grip)"
  bash run_own.sh a2rep327_nogrip_1 "${FLAGS[@]}" --no-grip
  echo "arm2_rc=$?"
  echo
  echo "== T1 driver end $(date -u +%FT%TZ)"
} >> "$D/raw/T1.driver.log" 2>&1
