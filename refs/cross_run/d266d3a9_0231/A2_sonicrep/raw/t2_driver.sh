#!/usr/bin/env bash
# Lane A2 T2: single-variable extension arms (predicate P5). 6 runs,
# concurrency 3, disjoint CPU sets, nice 19, timeout 900 s.
# Every arm differs from the frozen T1 recipe in EXACTLY ONE variable.
# These are single-variable probe points, NOT a random success-rate sample.
set -u
D=/data/group4/20261008-023143-qoder-d266d3a9/A2_sonicrep
cd "$D" || exit 9
echo $$ > "$D/raw/T2.driver.pid"
LOG="$D/raw/T2.driver.log"

# Frozen T1 recipe (identical to t1_driver.sh; --motion-profile absent by design,
# see FINDING.md "纠正 2").
FULL="--strict-execution --finger-gain 3 --grip-preload-mm 1.5 --table-front .24 --lift-height .15 --reference-fallback --grip-frame-lift --direct-table --adaptive-hand --kinematic-servo --pinch-geometry --flat-pinch --surface-capture --phase-clips --capture-radius .007 --c2-reference --endpoint-seed --endpoint-seed-native --contact-close --contact-entry-dwell .04 --gravity-arm 1 --opponent middle --close-seconds .5 --neutral-shoulder-offset .2 --clearance-approach --clearance-native-branch --clearance-branch-servo"

vary() {  # vary <from> <to> -> modified flag string; dies if the substitution is a no-op
  local out="${FULL//$1/$2}"
  if [[ "$out" == "$FULL" ]]; then
    echo "FATAL: substitution '$1' -> '$2' changed nothing" >> "$LOG"
    exit 9
  fi
  printf '%s' "$out"
}

launch() {  # launch <name> <cpus> <single-variable-label> <flagstring>
  local name="$1" cpus="$2" label="$3" flags="$4" rc
  echo "-- $(date -u +%FT%TZ) START $name cpus=$cpus single_variable=[$label]" >> "$LOG"
  echo "   flags: $flags" >> "$LOG"
  A2_CPUS="$cpus" A2_TIMEOUT=900 A2_NICE=19 bash run_own.sh "$name" $flags >> "$LOG" 2>&1
  rc=$?
  echo "   -> $name rc=$rc $(date -u +%FT%TZ)" >> "$LOG"
}

{
  echo "== T2 driver start $(date -u +%FT%TZ) host=$(hostname)"
  echo "== driver_sha256=$(sha256sum "$D/raw/t2_driver.sh" 2>/dev/null | cut -d' ' -f1)"
  echo "== frozen base: $FULL"
  echo "== arms: a2x_opp_index_1 a2x_preload10_1 a2x_fgain2_1 | a2x_lift12_1 a2x_tfront23_1 a2x_preload20_1"
} >> "$LOG" 2>&1

# ---- batch 1: concurrency 3, disjoint CPU sets ----
launch a2x_opp_index_1 96,97,98,99      "opponent: middle -> index"        "$(vary '--opponent middle' '--opponent index')" &
P1=$!
launch a2x_preload10_1 100,101,102,103  "grip-preload-mm: 1.5 -> 1.0"      "$(vary '--grip-preload-mm 1.5' '--grip-preload-mm 1.0')" &
P2=$!
launch a2x_fgain2_1    104,105,106,107  "finger-gain: 3 -> 2"              "$(vary '--finger-gain 3' '--finger-gain 2')" &
P3=$!
wait $P1 $P2 $P3
echo "== batch1 done $(date -u +%FT%TZ)" >> "$LOG"

# ---- batch 2: concurrency 3, disjoint CPU sets ----
launch a2x_lift12_1    96,97,98,99      "lift-height: .15 -> .12"          "$(vary '--lift-height .15' '--lift-height .12')" &
Q1=$!
launch a2x_tfront23_1  100,101,102,103  "table-front: .24 -> .23"          "$(vary '--table-front .24' '--table-front .23')" &
Q2=$!
launch a2x_preload20_1 104,105,106,107  "grip-preload-mm: 1.5 -> 2.0"      "$(vary '--grip-preload-mm 1.5' '--grip-preload-mm 2.0')" &
Q3=$!
wait $Q1 $Q2 $Q3
echo "== batch2 done $(date -u +%FT%TZ)" >> "$LOG"

echo "== T2 driver end $(date -u +%FT%TZ)" >> "$LOG"
