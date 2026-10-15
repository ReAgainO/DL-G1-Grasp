#!/usr/bin/env bash
# Run the natural-grasp candidate s4 (n4_conv) through the FULL 20-gate harness,
# exactly like the accepted delivery, so the result is directly comparable.
#
# wb_loop3.sh <reach_conv_stem|-> <lift_conv_stem|-> <run_name>
# We keep the accepted Kimodo lift (l1_conv) so the ONLY change vs the delivered
# wb_kimo_p6l1 is the approach clip: p6_conv -> n4_conv.
set -uo pipefail
D=/data/group4/20261008-232029-workbuddy-34e89f61
LOG="$D/nat_verify.log"
export TMPDIR="$D/tmp" XDG_CACHE_HOME="$D/cache"
mkdir -p "$TMPDIR" "$D/cache"

echo "###### NATURAL-GRASP VERIFY (n4_conv reach + l1_conv lift) $(date -u +%FT%TZ) ######" | tee -a "$LOG"
bash "$D/wb_loop3.sh" n4_conv l1_conv wb_nat_n4l1 >> "$LOG" 2>&1
echo "###### rc=$? ######" | tee -a "$LOG"

echo "--- result ---" | tee -a "$LOG"
/home/group4/group4_dasc7606c/envs/kimodo/bin/python "$D/wb_robust_report.py" 2>&1 | tee -a "$LOG"
echo NAT_VERIFY_DONE
