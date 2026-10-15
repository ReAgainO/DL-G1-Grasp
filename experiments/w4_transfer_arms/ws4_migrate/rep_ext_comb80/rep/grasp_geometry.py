"""Index-pad surface contact frame, not a penetrating closed-pad midpoint.

Uses the cube support function and physical pad radius. The expected object
centre lies one support radius inward from the fixed opposing index pad.
This modifies only task geometry/SONIC references, never physical object state.
"""
import numpy as np,mujoco
import source_physics_core as core

def contact_frame(m,d,cube_R=None,av=None,opponent=1,cube_half_m=None):
 if opponent not in [1,2]:raise ValueError('Opposing pad must be index1 or middle2')
 R=np.eye(3) if cube_R is None else np.asarray(cube_R)
 # A3/H1': the cube half-extent used by the box support function was hardcoded to
 # .0175 (= the 35mm template cube). Read it live from the model instead; the
 # optional cube_half_m stays as an explicit override for tests/scans. At the
 # default 35mm scene the live value is the very same double as the .0175 literal,
 # so the baseline trajectory is bit-identical.
 half=float(m.geom_size[m.geom('red_cube_geom').id,0]) if cube_half_m is None else float(cube_half_m)
 if not np.isfinite(half) or not .004<=half<=.045:raise ValueError('Cube half-extent must be finite and 4..45mm (W4f widened input domain)')
 ids=[m.geom(core.PADS[i]).id for i in [0,opponent]];a,b=[d.geom_xpos[i].copy() for i in ids]
 v=b-a;length=float(np.linalg.norm(v))
 if length<.005:raise ValueError('Degenerate pad direction <5mm')
 n=v/length;axis=R.T@n;extent=half*np.sum(abs(axis));radius=float(m.geom_size[ids[1],0])
 # Half millimetre allowed elastic pad contact, not a geometry overwrite.
 offset=extent+radius-.0005;point=b-n*offset
 if av is None:return point
 ja=np.zeros((3,m.nv));jb=ja.copy();mujoco.mj_jacGeom(m,d,ja,None,ids[0]);mujoco.mj_jacGeom(m,d,jb,None,ids[1])
 dn=(np.eye(3)-np.outer(n,n))@(jb[:,av]-ja[:,av])/length
 # The box support function is nondifferentiable at an exactly face-aligned
 # direction. Use its symmetric zero subgradient there (not roundoff's sign).
 signs=np.where(abs(axis)<1e-8,0.,np.sign(axis))
 de=half*(R@signs)@dn
 J=jb[:,av]-offset*dn-n[:,None]*de[None]
 return point,J
