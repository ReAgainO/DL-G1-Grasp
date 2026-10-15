"""Prepare explicit planned body keyframes for native ARDY, not simulated success."""
from pathlib import Path
import json,numpy as np,mujoco
r=Path(__file__).resolve().parent;o=r/'out/native_ardy22';o.mkdir()
m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial16/scene.xml'));d=mujoco.MjData(m);tr=np.load(r/'out/normal_trial16/trajectory.npz');base=tr['qpos'][0].copy();j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];w=m.body('right_wrist_yaw_link').id
e=json.loads((r/'out/surface_entry22/entry.json').read_text());p=json.loads((r/'out/surface_path22/paths.json').read_text())[0]
arms=[base[qa[22:29]].tolist(),e['vertical_approach'][-1]['arm_q'],e['grasp']['arm_q'],p['lift_path'][-1]['arm_q']];q=[];wrists=[];wrist_R=[]
for arm in arms:
 d.qpos[:]=base;d.qpos[qa[22:29]]=arm;mujoco.mj_forward(m,d);q.append(d.qpos[qa[:29]].tolist());wrists.append(d.xpos[w].tolist());wrist_R.append(d.xmat[w].reshape(3,3).tolist())
res=dict(frame_indices=[0,60,125,199],fps=25,duration_s=8,body_joint_names=[m.joint(k).name for k in j[:29]],body_joint_q=q,root_xyz=[base[:3].tolist()]*4,root_wxyz=[base[3:7].tolist()]*4,wrist_xyz=wrists,wrist_R=wrist_R,cube=dict(x=.28,y=-.118,edge_m=.035,table_top_m=.757),scenario='original35mm with initialbase-.06',keyframes_are_planned_not_successful_physics=True)
(o/'planned_keyframes.json').write_text(json.dumps(res,indent=2));print('Wrote plannedbody keyframes, no simulation or success.')
