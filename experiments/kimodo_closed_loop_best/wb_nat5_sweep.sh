#!/bin/bash
# NAT5 sweep: nat3 patch applies the orientation correction to `goal` AFTER the
# native-branch overwrite, so it can finally reach refarm/reference.
B=/data/group4/20261008-232029-workbuddy-34e89f61
H=$B/harness_nat2
STEM=n4_conv
LC=l1_conv
echo "=== NAT5 sweep $(date -u +%FT%TZ) ==="
echo "delivered  $(sha256sum $B/harness_s1000/rep/sonic_grasp.py | cut -c1-16)"
echo "frozen     $(sha256sum $B/delivered_frozen_20261009/rep/sonic_grasp.py | cut -c1-16)"
echo "working    $(sha256sum $H/rep/sonic_grasp.py | cut -c1-16)"

for OB in 0.0 0.25 0.5 0.75 1.0; do
  TAG=$(echo "$OB" | tr -d '.')
  NAME="wb_nat5_n4_o${TAG}"
  echo "### $NAME (orient_blend=$OB) $(date -u +%FT%TZ)"
  T0=$(date +%s)
  bash "$H/run_cell_nat2w.sh" "$NAME" 35 0.267 -0.118 0 "$STEM" "$OB"
  RC=$?
  T1=$(date +%s)
  echo "### $NAME rc=$RC $((T1-T0)) s"
done
echo "=== NAT5 sweep done $(date -u +%FT%TZ) ==="
