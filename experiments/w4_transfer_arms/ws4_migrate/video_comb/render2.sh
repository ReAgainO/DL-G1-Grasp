#!/usr/bin/env bash
export PYTHONDONTWRITEBYTECODE=1 MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa
export LD_LIBRARY_PATH=/data/group4/20261008-220500-codex-6c40bf04/lib
cd /data/group4/20261008-221515-qoder-03c4673f/ws4_migrate || exit 2
PY=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
$PY -B ws4c_render.py rep_ext_comb/rep/out/a35_00_15__comb video_comb/a35_00_15__comb.mp4 4
$PY -B ws4c_render.py rep_ext_comb/rep/out/b25_00_00__comb video_comb/b25_00_00__comb.mp4 4
