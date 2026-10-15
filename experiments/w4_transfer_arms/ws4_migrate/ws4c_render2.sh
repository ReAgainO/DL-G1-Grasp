#!/usr/bin/env bash
D=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate
export PYTHONDONTWRITEBYTECODE=1 MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa
export LD_LIBRARY_PATH=/data/group4/20261008-220500-codex-6c40bf04/lib:${LD_LIBRARY_PATH:-}
cd $D || exit 2
PY=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
for c in b25_00_00__phys b25_12_04__phys; do
  $PY -B ws4c_render.py rep_ext_phys/rep/out/$c video_phys/$c.mp4 4
done
