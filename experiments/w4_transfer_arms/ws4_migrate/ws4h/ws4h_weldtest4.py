import numpy as np, mujoco, warnings
from pathlib import Path
warnings.filterwarnings('ignore')
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
def test(tau=2e-4, simp=None, force=2.0, steps=600):
    m = mujoco.MjModel.from_xml_path(str(M / 'rep_ext_w1/rep/out/d80w1_10/scene.xml'))
    m.eq_solref[0] = [tau, 1.0]
    if simp is not None: m.eq_solimp[0] = simp
    for g in range(m.ngeom):
        bn = m.body(int(m.geom_bodyid[g])).name or ''
        if bn not in ('world', 'red_cube'):
            m.geom_contype[g] = 0; m.geom_conaffinity[g] = 0
    d = mujoco.MjData(m); mujoco.mj_forward(m, d)
    z0 = float(d.xpos[m.body('red_cube').id][2])
    d.xfrc_applied[m.body('red_cube').id, 2] = -force
    for i in range(steps): mujoco.mj_step(m, d)
    return (z0 - d.xpos[m.body('red_cube').id][2]) * 1e3
for simp in ([0.9999, 0.99999, 1e-05, 0.5, 2.0], [0.99, 0.999, 1e-04, 0.5, 2.0], [0.5, 0.9, 0.05, 0.5, 2.0]):
    print('solimp', simp, '-> sag %.3f mm' % test(simp=simp))
print('force linearity: 1N %.3f mm, 2N %.3f mm, 4N %.3f mm' % (test(force=1.), test(force=2.), test(force=4.)))
print('solver iterations test:')
m = mujoco.MjModel.from_xml_path(str(M / 'rep_ext_w1/rep/out/d80w1_10/scene.xml'))
print('  model solver', m.opt.solver, 'iterations', m.opt.iterations, 'tolerance', m.opt.tolerance, 'ls_iterations', m.opt.ls_iterations)
m.opt.iterations = 200
for g in range(m.ngeom):
    bn = m.body(int(m.geom_bodyid[g])).name or ''
    if bn not in ('world', 'red_cube'):
        m.geom_contype[g] = 0; m.geom_conaffinity[g] = 0
d = mujoco.MjData(m); mujoco.mj_forward(m, d)
z0 = float(d.xpos[m.body('red_cube').id][2])
d.xfrc_applied[m.body('red_cube').id, 2] = -2.0
for i in range(600): mujoco.mj_step(m, d)
print('  with iterations=200 -> sag %.3f mm' % ((z0 - d.xpos[m.body('red_cube').id][2]) * 1e3))
