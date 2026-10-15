import numpy as np, mujoco, warnings
from pathlib import Path
warnings.filterwarnings('ignore')
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
base = mujoco.MjModel.from_xml_path(str(M / 'rep_ext_w1/rep/out/d80w1_10/scene.xml'))
cube = base.body('red_cube')
for tau in [2e-3, 2e-4, 2e-5, 2e-6]:
    m = mujoco.MjModel.from_xml_path(str(M / 'rep_ext_w1/rep/out/d80w1_10/scene.xml'))
    m.eq_solref[0] = [tau, 1.0]
    for g in range(m.ngeom):
        bn = m.body(int(m.geom_bodyid[g])).name or ''
        if bn not in ('world', 'red_cube'):
            m.geom_contype[g] = 0; m.geom_conaffinity[g] = 0
    d = mujoco.MjData(m); mujoco.mj_forward(m, d)
    z0 = float(d.xpos[cube.id][2])
    d.xfrc_applied[cube.id, 2] = -2.0
    for i in range(600):
        mujoco.mj_step(m, d)
    sag = (z0 - d.xpos[cube.id][2]) * 1e3
    print('tau=%.0e steady sag under 2N = %.3f mm -> k_eff=%.1f N/m' % (tau, sag, 2.0 / (sag * 1e-3) if sag > 1e-6 else float('inf')))
# solimp test at tau .0002
for simp in ([0.99, 0.999, 0.0001], [0.9999, 1.0, 1e-05]):
    m = mujoco.MjModel.from_xml_path(str(M / 'rep_ext_w1/rep/out/d80w1_10/scene.xml'))
    m.eq_solref[0] = [2e-4, 1.0]; m.eq_solimp[0] = simp
    for g in range(m.ngeom):
        bn = m.body(int(m.geom_bodyid[g])).name or ''
        if bn not in ('world', 'red_cube'):
            m.geom_contype[g] = 0; m.geom_conaffinity[g] = 0
    d = mujoco.MjData(m); mujoco.mj_forward(m, d)
    z0 = float(d.xpos[cube.id][2])
    d.xfrc_applied[cube.id, 2] = -2.0
    for i in range(600):
        mujoco.mj_step(m, d)
    sag = (z0 - d.xpos[cube.id][2]) * 1e3
    print('solimp=%s tau=2e-4 steady sag=%.3f mm' % (simp, sag))
