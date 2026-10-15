#!/bin/bash
cd /data/group4/20261008-221515-qoder-03c4673f/ws1_menagerie
export LD_LIBRARY_PATH=/home/group4/group4_dasc7606c/render_test/mesa_probe/x_libosmesa6_23.2.1-1ubuntu3.1~22.04.4_amd64/usr/lib/x86_64-linux-gnu
export MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
PYENV=env/bin/python
for spec in "20 grasp 0" "25 grasp 0" "35 grasp 0" "20 negctl 0" "20 ideal 0"; do
  set -- $spec; e=$1; m=$2; s=$3
  nice -n 10 $PYENV -B scripts/ws1_run.py --edge $e --seed $s --mode $m --lam-extra 0.06 \
    --tag vid_e${e}_${m}_${s} --video video/e${e}_${m}_${s}.mp4
done
echo VIDEOS_DONE
