"""Zero-step reachability check; NOT a SONIC/physics success claim."""
import hashlib,json,sys
from pathlib import Path
import numpy as np,mujoco
from sonic_grasp import ik
root=Path(__file__).resolve().parent;out=root/'out/lift-height-preflight-v2';out.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=root/'out/w4_contact_baseline327';r=json.loads((source/'result.json').read_text());z=np.load(source/'trajectory.npz',allow_pickle=False)
assert r['runtime_stamp']['mujoco_version']==mujoco.__version__
m=mujoco.MjModel.from_xml_path(str(source/'scene.xml'));fk=mujoco.MjData(m);j=m.actuator_trnid[22:29,0];aq=m.jnt_qposadr[j];av=m.jnt_dofadr[j];w=m.body('right_wrist_yaw_link').id
k=np.flatnonzero(z['phase']=='LIFT')[0];base=z['qpos'][k].copy();fk.qpos[:]=base;mujoco.mj_forward(m,fk);pos=fk.xpos[w].copy();R=fk.xmat[w].reshape(3,3).copy();rows=[]
for height in [.1,.12,.15,.18,.2]:
    fk.qpos[:]=base;goal=pos+[0,0,height];q=base[aq].copy()
    for _ in range(5):q=ik(m,fk,aq,av,goal,R,q,base[aq],0.)
    fk.qpos[aq]=q;mujoco.mj_forward(m,fk)
    error=float(np.linalg.norm(goal-fk.xpos[w]));trace=float(np.trace(R@fk.xmat[w].reshape(3,3).T));angle=float(np.arccos(np.clip((trace-1)/2,-1,1)))
    margin=float(np.minimum(q-m.jnt_range[j,0],m.jnt_range[j,1]-q).min())
    rows.append(dict(requested_lift_m=height,position_error_m=error,rotation_error_rad=angle,joint_solution_rad=q.tolist(),minimum_joint_limit_margin_rad=margin,feasible=error<.003 and angle<.02,dynamic_reference_feasibility_verified=False))
stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,dt=float(m.opt.timestep),model_sha={'scene':sha(source/'scene.xml'),'robot':sha(source/'g1_free_grasp.xml')},scene_generator_sha=sha(__file__),library_sha={'ik_source':sha(root/'sonic_grasp.py'),'task_plan':sha(root/'task_plan.py'),'source_episode':sha(source/'result.json'),'source_trajectory':sha(source/'trajectory.npz')})
answer=dict(runtime_stamp=stamp,source_episode_runtime_stamp=r['runtime_stamp'],physical_steps=0,source_episode_sha=sha(source/'result.json'),scope='geometric wrist reachability only, no policy or dynamics; approach/capture unchanged',rows=rows,corrects='lift-height-preflight/result.json inherited episode dependency stamps instead of hashing actually used current IK module; v2 preserves episode provenance separately and adds the near-limit warning')
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n');print(json.dumps(answer,indent=2))
