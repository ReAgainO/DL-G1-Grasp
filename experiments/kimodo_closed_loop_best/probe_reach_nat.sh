#!/usr/bin/env bash
# probe_reach_nat.sh -- Kimodo prompt sweep for a NATURAL GRASP approach pose.
#
# Motivation (measured, see ledger §16):
#   The delivered p6 clip has hand_vs_down=125.5 deg (palm pointing AWAY from the
#   table) and elbow_bend=173.9 deg (arm almost fully straight), which is why the
#   grasp looks like a twisted arm. The official baseline is far more natural
#   (hand_vs_down=161.3, roll=79.7 deg), so the problem is our PROMPT, not Kimodo.
#
# Every prompt below therefore explicitly asks for:
#   - the palm facing DOWN toward the table
#   - a natural, slightly bent elbow (NOT a straight arm)
#   - grasping a small object on a table
#
# Same env + attnfix patch + duration/seed as the original reach probe, so the
# only thing that changes is the text.
set -o pipefail
set +u

B=/home/group4/group4_dasc7606c
source "$B/work/kimodo/env.sh"

D=/data/group4/20261008-232029-workbuddy-34e89f61
W=$B/work/20261008-232029-workbuddy-34e89f61/workbuddy
L=$D/kimodo_logs
OUT=$D/reach_nat
mkdir -p "$L" "$OUT"

DUR=${DUR:-3.0}
SEED=${SEED:-42}

run () {
  local stem="$1"; shift
  local prompt="$*"
  echo "[nat] $stem <- \"$prompt\""
  nice -n 19 "$PY" -u -B "$W/scripts/wb_gen_fix.py" \
      "$prompt" \
      --model kimodo-g1-rp \
      --duration "$DUR" \
      --num_samples 1 \
      --diffusion_steps 100 \
      --seed "$SEED" \
      --output "$OUT/$stem" \
      >> "$L/nat_$stem.log" 2>&1
  echo "[nat] $stem rc=$?"
}

run n1 "A person stands at a table and reaches down with their right hand, palm facing down, to pick up a small object on the table."
run n2 "A person reaches forward with their right arm, elbow relaxed and slightly bent, palm turned downward toward the table."
run n3 "A person stands and places their right palm flat down on the table in front of them, arm bent naturally."
run n4 "A person lowers their right hand onto the table with the palm facing downward, fingers relaxed, as if about to grasp a small cube."
run n5 "A person bends their right elbow and brings their palm down toward a small object on the table in front of them."
run n6 "A person reaches for a small object on a table, right arm bent at the elbow, wrist straight and palm facing down."

echo "[nat] ALL DONE"
