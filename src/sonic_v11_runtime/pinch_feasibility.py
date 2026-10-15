"""Finite multi-seed kinematic branch search, no physical stepping/grasp claim."""
import json,sys
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s,source_physics_core as core
from sonic_grasp import ik,pinch_center
from motion_input import ArdyMotion
root=Path(__file__).resolve().parent;out=root/'out/pinch-feasibility.json';assert not out.exists()
scene=root/'src/g1/scene_grasp_hand.xml';m=mujoco.MjModel.from_xml_path(str(scene));d=mujoco.MjData(m)
ids=m.actuator_trnid[:29,0];qa=m.jnt_qposadr[ids];va=m.jnt_dofadr[ids];aq=qa[22:29];av=va[22:29];hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]]
d.qpos[:3]=[0,0,.74];d.qpos[3:7]=[1,0,0,0];d.qpos[qa]=s.DEFAULT_ANGLES
hand=core.CLOSED.copy();hand[2]=-.88;d.qpos[hq]=hand;mujoco.mj_forward(m,d)
source=ArdyMotion(root/'src/original_motions/near_s42.npz');seeds=[s.DEFAULT_ANGLES[22:29].copy()]+[source.qpos[i,29:36].copy() for i in [0,25,31,50,75,99]]
seeds += [core.GRASP.copy(),core.HIGH.copy()]
records=[]
for label,target in [('grasp',[.267,-.118,.7745]),('pregrasp',[.267,-.118,.8745])]:
 for k,seed in enumerate(seeds):
  q=seed.copy()
  for attempt in range(10):q=ik(m,d,aq,av,np.array(target),np.eye(3),q,seed,0.,True,True)
  d.qpos[aq]=q;mujoco.mj_forward(m,d);p=np.array([d.geom_xpos[m.geom(n).id].copy() for n in core.PADS])
  poserr=float(np.linalg.norm(pinch_center(m,d)-target));spread=float(np.ptp(p[:,2]));limits=m.jnt_range[ids[22:29]]
  records.append(dict(target=label,seed=k,q=q.tolist(),position_error_m=poserr,pad_vertical_spread_m=spread,
                      within_limits=bool((q>=limits[:,0]).all() and (q<=limits[:,1]).all()),
                      native_seed_deviation_rad=float(np.linalg.norm(q-seed)),feasible=poserr<.003 and spread<.003))
best={label:min([r for r in records if r['target']==label],key=lambda r:10*r['position_error_m']+r['pad_vertical_spread_m']) for label in ['grasp','pregrasp']}
stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,model_sha={'scene':s.sha(scene),'robot':s.sha(root/'src/g1/g1_29dof_with_hand.xml')},
           scene_generator_sha=s.sha(__file__),library_sha={'ik_source':s.sha(root/'sonic_grasp.py'),'original_npz':source.audit['source_npz_sha256']},dt=.002)
r=dict(runtime_stamp=stamp,physical_steps=0,physical_grasp_established=False,records=records,best=best)
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(best=best,feasible_count=sum(x['feasible'] for x in records)),indent=2))
