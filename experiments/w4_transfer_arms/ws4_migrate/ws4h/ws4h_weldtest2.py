import numpy as np, mujoco, warnings
from pathlib import Path
warnings.filterwarnings('ignore')
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
m = mujoco.MjModel.from_xml_path(str(M / 'rep_ext_w1/rep/out/d80w1_10/scene.xml'))
print('neq', m.neq, 'eq_solref', m.eq_solref, 'eq_solimp', m.eq_solimp)
cube = m.body('red_cube'); cq = int(m.jnt_qposadr[int(cube.jntadr[0])])
# disable every robot geom contact; keep cube / world / table
for g in range(m.ngeom):
    bn = m.body(int(m.geom_bodyid[g])).name or ''
    if bn not in ('world', 'red_cube'):
        m.geom_contype[g] = 0; m.geom_conaffinity[g] = 0
d = mujoco.MjData(m)
z0 = float(d.xpos[cube.id][2])
print('t0 cube_z', z0, 'eq_active', d.eq_active)
# apply 2N down on the cube via xfrc
d.xfrc_applied[cube.id, 2] = -2.0
for i in range(500):
    mujoco.mj_step(m, d)
    if i % 100 == 99:
        print('step', i + 1, 'cube_z=%.6f dz_mm=%.4f' % (d.xpos[cube.id][2], (d.xpos[cube.id][2] - z0) * 1e3))
d.xfrc_applied[cube.id, 2] = 0.
for i in range(500):
    mujoco.mj_step(m, d)
print('after force off: cube_z=%.6f dz_mm=%.4f' % (d.xpos[cube.id][2], (d.xpos[cube.id][2] - z0) * 1e3))
# now deactivate the weld -> cube must free fall to the table
d2 = mujoco.MjData(m)
d2.eq_active[:] = 0
for i in range(500):
    mujoco.mj_step(m, d2)
print('weld OFF after 1s: cube_z=%.4f (free fall / table check)' % d2.xpos[cube.id][2])
