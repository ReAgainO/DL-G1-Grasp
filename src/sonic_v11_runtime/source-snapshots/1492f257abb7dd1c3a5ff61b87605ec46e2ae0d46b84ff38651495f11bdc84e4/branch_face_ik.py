"""Static grasp-direction alignment; only virtual input arm coordinates."""
import numpy as np,mujoco
import source_physics_core as core
from grasp_geometry import contact_frame

def face_ik(m,fk,aq,av,target,R,seed,prior,weight,pinch=False,flat_pinch=False,surface=False,cube_R=None,opponent=1):
 if not (pinch and flat_pinch and surface and weight==0 and opponent in [1,2]):raise ValueError('Static surface/flat zero-prior branch only')
 q=np.asarray(seed).copy();limits=m.jnt_range[m.dof_jntid[av]];lo=limits[:,0]+.02005;hi=limits[:,1]-.02005
 pads=[m.geom(n).id for n in core.PADS];rotation=np.asarray(cube_R)
 fk.qpos[aq]=q;mujoco.mj_forward(m,fk)
 v=fk.geom_xpos[pads[opponent]]-fk.geom_xpos[pads[0]];v[2]=0.
 if np.linalg.norm(v)<.005:raise ValueError('Degenerate horizontal pad direction')
 v/=np.linalg.norm(v);axis=int(np.argmax(abs(rotation.T@v)));goal=rotation[:,axis].copy()
 goal[2]=0.
 if np.linalg.norm(goal)<.5:raise ValueError('Nonhorizontal cube grasp face')
 goal/=np.linalg.norm(goal);goal*=1. if goal@v>=0 else -1.
 desired=np.arctan2(goal[1],goal[0])
 for _ in range(15):
  fk.qpos[aq]=q;mujoco.mj_forward(m,fk)
  point,J=contact_frame(m,fk,rotation,av,opponent);ep=np.asarray(target)-point;jacs=[]
  for gid in pads:
   jp=np.zeros((3,m.nv));mujoco.mj_jacGeom(m,fk,jp,None,gid);jacs.append(jp[:,av].copy())
  heights=np.array([fk.geom_xpos[pads[0],2]-fk.geom_xpos[pads[1],2],fk.geom_xpos[pads[2],2]-fk.geom_xpos[pads[1],2]])
  v=fk.geom_xpos[pads[opponent]]-fk.geom_xpos[pads[0]];den=float(v[0]**2+v[1]**2)
  if den<.005**2:raise ValueError('Degenerate horizontal pad direction')
  dv=jacs[opponent]-jacs[0];Jyaw=(-v[1]*dv[0]+v[0]*dv[1])/den
  eyaw=float((desired-np.arctan2(v[1],v[0])+np.pi)%(2*np.pi)-np.pi)
  J=np.vstack([10*J,10*(jacs[0][2]-jacs[1][2]),10*(jacs[2][2]-jacs[1][2]),.15*Jyaw])
  error=np.r_[10*ep,-10*heights,.15*eyaw]
  dq=J.T@np.linalg.solve(J@J.T+1e-4*np.eye(6),error)
  dq*=min(1.,.08/max(np.max(abs(dq)),1e-12));q=np.clip(q+dq,lo,hi)
  if np.linalg.norm(ep)<.0003 and np.linalg.norm(heights)<.002 and abs(eyaw)<.01:break
 return q
