"""Index-pad surface contact frame, not a penetrating closed-pad midpoint.

Uses the cube support function and physical pad radius. The expected object
centre lies one support radius inward from the fixed opposing index pad.
This modifies only task geometry/SONIC references, never physical object state.
"""
import numpy as np,mujoco
import source_physics_core as core

def contact_frame(m,d,cube_R=None,av=None):
 R=np.eye(3) if cube_R is None else np.asarray(cube_R)
 ids=[m.geom(n).id for n in core.PADS[:2]];a,b=[d.geom_xpos[i].copy() for i in ids]
 v=b-a;length=float(np.linalg.norm(v))
 if length<.005:raise ValueError('Degenerate pad direction <5mm')
 n=v/length;axis=R.T@n;extent=.0175*np.sum(abs(axis));radius=float(m.geom_size[ids[1],0])
 # Half millimetre allowed elastic pad contact, not a geometry overwrite.
 offset=extent+radius-.0005;point=b-n*offset
 if av is None:return point
 ja=np.zeros((3,m.nv));jb=ja.copy();mujoco.mj_jacGeom(m,d,ja,None,ids[0]);mujoco.mj_jacGeom(m,d,jb,None,ids[1])
 dn=(np.eye(3)-np.outer(n,n))@(jb[:,av]-ja[:,av])/length
 de=.0175*(R@np.sign(axis))@dn
 J=jb[:,av]-offset*dn-n[:,None]*de[None]
 return point,J
