#!/usr/bin/env python3
"""W4i seat4 = ws4i_seat3 copy with the contact-normal convention FIXED.

Finding (measured, ws4i_probe.py): MuJoCo's contact normal is the FIRST ROW of contact.frame
(contact.frame.reshape(3,3)[0,:]); W4h seat3 used [:,0] = (n_x, t1_x, t2_x) - a tangent mix.
Consequence: a fingertip pressing DOWN on the cube's top face (true n_z=-1) was scored as a
"support" (n_z=+1) whenever t2_x=1, so the 80mm 'cradle' d80w1_12 was really a lid
(index top-press + thumb/middle side cages) => nothing could carry the cube.
This patch orients the true normal pad->cube (force ON the cube) and keeps every other
criterion identical (>=2 supports mandatory, >=1 cage bonus, CoM containment >=8mm).
"""
from pathlib import Path
p = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/ws4i/ws4i_seat4.py')
s = p.read_text()
old = """            n = np.asarray(c.frame).reshape(3, 3)[:, 0].copy()
            if g1 == self.cube: n = -n  # normal direction of the force ON the cube
"""
new = """            n = np.asarray(c.frame).reshape(3, 3)[0, :].copy()  # W4i FIX: first ROW is the contact normal (frame[:,0] mixes tangent x-components)
            if float(n @ (d.geom_xpos[self.cube] - d.geom_xpos[other])) < 0.: n = -n  # orient so +n = force ON the cube (pad -> cube)
"""
assert s.count(old) == 1, 'anchor 1 count=%d' % s.count(old)
s = s.replace(old, new)
old2 = "    log('   contact %s n=%s n_z=%.2f pos=%s'"
assert s.count(old2) == 1, 'anchor 2 count=%d' % s.count(old2)
s = s.replace("W4h W1S seat3 cradle edge=%gmm", "W4i seat4 (corrected normal) edge=%gmm")
p.write_text(s)
print('PATCH4 OK lines=%d bytes=%d' % (s.count('\n'), len(s.encode())))
