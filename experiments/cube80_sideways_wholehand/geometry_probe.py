from pathlib import Path
import json,sys
import numpy as np,mujoco
import wholehand_side as w
R=Path(__file__).resolve().parent
o=R/'out'/'geometry_probe';o.mkdir()
m,d,bq,hj,hq,armed=w.build(o,.06,[.35,-.18],.12)
aq,av,hv,lim,idx,pads,cube,table,bones=w.setup(m,d,bq,hj,hq)
print('mapping',[(m.joint(int(i)).name,int(m.jnt_qposadr[i])) for i in m.actuator_trnid[:,0]])
print('limits',lim.tolist())
for a in [w.sonic.DEFAULT_ANGLES[22:29],[-1.1,-.8,-1.7,1.5,-1.5,1.2,.3]]:
 d.qpos[aq]=a;mujoco.mj_forward(m,d)
 print('pose',json.dumps({'arm':list(a),'wrist':d.xpos[m.body('right_wrist_yaw_link').id].tolist(),'pads':d.geom_xpos[pads].tolist(),
 'bones':[(m.geom(int(g)).name,d.geom_xpos[g].tolist(),float(w.clearances(m,d,np.array([g]),cube,table)[0,1])) for g in bones]}))
print('robot_hand_xml')
t=(R/'lib/src/g1/g1_29dof_with_hand.xml').read_text();i=t.find('<body name="right_wrist_yaw_link"');print(t[i:i+17000])
print('archive_fields')
p=R/'lib/out/w7_faceservo_replay327/trajectory.npz'
# archive data resides in original own task, not copied library.
p=Path('/data/group4/20261006-093203-codex-6385a841/out/w7_faceservo_replay327/trajectory.npz')
with np.load(p,allow_pickle=False) as z:
 print([(k,z[k].shape) for k in z.files])
