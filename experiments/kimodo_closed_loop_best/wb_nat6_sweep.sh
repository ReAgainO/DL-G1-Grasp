#!/bin/bash
# NAT6 sweep: --approach-orient-blend steers APPROACH ONLY.
# --approach-grasp-orient-blend stays 0 so the delivered 20/20 grasp geometry
# (DESCEND/CLOSE/LIFT targetR) is preserved bit-for-bit.
B=/data/group4/20261008-232029-workbuddy-34e89f61
H=$B/harness_nat2
STEM=n4_conv
echo "=== NAT6 sweep $(date -u +%FT%TZ) ==="
echo "delivered  $(sha256sum $B/harness_s1000/rep/sonic_grasp.py | cut -c1-16)"
echo "frozen     $(sha256sum $B/delivered_frozen_20261009/rep/sonic_grasp.py | cut -c1-16)"
echo "working    $(sha256sum $H/rep/sonic_grasp.py | cut -c1-16)"

# fine sweep: does a gentle APPROACH-only correction keep 20/20?
for OB in 0.05 0.1 0.15 0.2 0.25 0.3; do
  TAG=$(echo "$OB" | tr -d '.')
  NAME="wb_nat6_n4_o${TAG}"
  echo "### $NAME (approach_orient_blend=$OB grasp=0) $(date -u +%FT%TZ)"
  T0=$(date +%s)
  bash "$H/run_cell_nat2w.sh" "$NAME" 35 0.267 -0.118 0 "$STEM" "$OB"
  RC=$?
  T1=$(date +%s)
  echo "### $NAME rc=$RC $((T1-T0)) s"
done
echo "=== NAT6 sweep done $(date -u +%FT%TZ) ==="
