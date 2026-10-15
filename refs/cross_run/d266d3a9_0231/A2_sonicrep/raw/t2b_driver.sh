#!/usr/bin/env bash
# Lane A2 T2 batch-2 driver: the 3 remaining single-variable arms, at
# CONCURRENCY 2 (degraded from 3) because /proc/pressure/cpu some avg10 crossed
# the 10% discipline threshold (20.31 at 2026-10-07T18:58:25Z, node load 125.4).
# Disjoint CPU sets, nice 19, timeout 900 s. Each arm differs from the frozen
# T1 recipe in EXACTLY ONE variable.
set -u
D=/data/group4/20261008-023143-qoder-d266d3a9/A2_sonicrep
cd "$D" || exit 9
echo $$ > "$D/raw/T2b.driver.pid"
LOG="$D/raw/T2.driver.log"

FULL="--strict-execution --finger-gain 3 --grip-preload-mm 1.5 --table-front .24 --lift-height .15 --reference-fallback --grip-frame-lift --direct-table --adaptive-hand --kinematic-servo --pinch-geometry --flat-pinch --surface-capture --phase-clips --capture-radius .007 --c2-reference --endpoint-seed --endpoint-seed-native --contact-close --contact-entry-dwell .04 --gravity-arm 1 --opponent middle --close-seconds .5 --neutral-shoulder-offset .2 --clearance-approach --clearance-native-branch --clearance-branch-servo"

vary() {
  local out="${FULL//$1/$2}"
  if [[ "$out" == "$FULL" ]]; then
    echo "FATAL: substitution '$1' -> '$2' changed nothing" >> "$LOG"; exit 9
  fi
  printf '%s' "$out"
}

launch() {
  local name="$1" cpus="$2" label="$3" flags="$4" rc
  echo "-- $(date -u +%FT%TZ) START $name cpus=$cpus single_variable=[$label] concurrency=2(degraded)" >> "$LOG"
  echo "   flags: $flags" >> "$LOG"
  A2_CPUS="$cpus" A2_TIMEOUT=900 A2_NICE=19 bash run_own.sh "$name" $flags >> "$LOG" 2>&1
  rc=$?
  echo "   -> $name rc=$rc $(date -u +%FT%TZ)" >> "$LOG"
}

{
  echo "== T2b driver start $(date -u +%FT%TZ) host=$(hostname) concurrency=2 (pressure-degraded)"
  echo "== driver_sha256=$(sha256sum "$D/raw/t2b_driver.sh" 2>/dev/null | cut -d' ' -f1)"
  echo "== pressure_cpu: $(tr '\n' ' ' < /proc/pressure/cpu)"
  echo "== loadavg: $(cat /proc/loadavg)"
} >> "$LOG" 2>&1

launch a2x_lift12_1   96,97,98,99     "lift-height: .15 -> .12"     "$(vary '--lift-height .15' '--lift-height .12')" &
R1=$!
launch a2x_tfront23_1 100,101,102,103 "table-front: .24 -> .23"     "$(vary '--table-front .24' '--table-front .23')" &
R2=$!
wait $R1 $R2
echo "== T2b batch A done $(date -u +%FT%TZ)" >> "$LOG"

launch a2x_preload20_1 96,97,98,99    "grip-preload-mm: 1.5 -> 2.0" "$(vary '--grip-preload-mm 1.5' '--grip-preload-mm 2.0')" &
R3=$!
wait $R3
echo "== T2b batch B done $(date -u +%FT%TZ)" >> "$LOG"

echo "== T2b driver end $(date -u +%FT%TZ)" >> "$LOG"
