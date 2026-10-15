"""Actual saved finger geometry/command tracking near SETDOWN; no mj_step."""
import argparse,json
from pathlib import Path
import mujoco,numpy as np
import source_physics_core as core
from wave4_records import sha
p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('output');a=p.parse_args()
root=Path(__file__).resolve().parent
assert all(Path(n).name==n and len(n)<128 for n in [a.episode,a.output])
folder=root/'out'/a.episode;r=json.loads((folder/'result.json').read_text())
assert r['setdown_enabled'] and r['runtime_stamp']['mujoco_version']==mujoco.__version__
m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'));d=mujoco.MjData(m);f=mujoco.MjData(m)
cube=m.body('red_cube').id;ids=[m.geom(n).id for n in [core.PADS[0],core.PADS[2]]]
jids=m.actuator_trnid[36:43,0];hq=m.jnt_qposadr[jids];active=np.array([0,1,2,5,6])
with np.load(folder/'trajectory.npz',allow_pickle=False) as z:
    assert json.loads(str(z['runtime_stamp']))==r['runtime_stamp'] and 2<=len(z['time'])<=2250
    qs=z['qpos'].copy();hs=z['hand_reference'].copy();ctrl=z['actuator_ctrl'].copy();ts=z['time'].copy();phases=z['phase'].copy()
start=next(e['time_s'] for e in r['events'] if e['phase']=='SETDOWN')
idx=np.where((ts>start-.3)&(ts<start+.6))[0];assert 1<=len(idx)<=24
normal=np.asarray(r['adaptive_hand']['last']['normal']);axis=int(r['adaptive_hand']['last']['opposing_cube_axis'])
rows=[]
for i in idx:
    d.qpos[:]=qs[i];mujoco.mj_forward(m,d);R=d.xmat[cube].reshape(3,3).copy();pos=d.xpos[cube].copy()
    f.qpos[:]=d.qpos;f.qpos[hq]=hs[i];mujoco.mj_forward(m,f)
    local=np.array([R.T@(d.geom_xpos[k]-pos) for k in ids]);commandlocal=np.array([R.T@(f.geom_xpos[k]-pos) for k in ids])
    tangent=[j for j in range(3) if j!=axis]
    direction=d.geom_xpos[ids[1]]-d.geom_xpos[ids[0]];direction[2]=0
    cubeaxis=R[:,axis].copy();cubeaxis[2]=0
    yaw=None if min(np.linalg.norm(direction),np.linalg.norm(cubeaxis))<.005 else float(np.degrees(np.arccos(np.clip(abs(direction@cubeaxis)/(np.linalg.norm(direction)*np.linalg.norm(cubeaxis)),-1,1))))
    saturation=np.maximum(abs(ctrl[i,36:43][active])/np.maximum(abs(m.actuator_ctrlrange[36:43][active]).max(axis=1),1e-12),0)
    rows.append(dict(time_s=float(ts[i]),phase=str(phases[i]),actual_hand_minus_command_rad=(qs[i,hq]-hs[i]).tolist(),
        command_hand_rad=hs[i].tolist(),active_finger_torque_limit_fraction=saturation.tolist(),
        actual_pad_cube_local_m=local.tolist(),virtual_command_pad_cube_local_m=commandlocal.tolist(),
        pad_radius_m=[float(m.geom_size[k,0]) for k in ids],selected_cube_axis=axis,
        actual_tangential_excess_beyond15mm_m=np.maximum(abs(local[:,tangent])-.015,0).tolist(),
        virtual_tangential_excess_beyond15mm_m=np.maximum(abs(commandlocal[:,tangent])-.015,0).tolist(),
        actual_pad_pair_yaw_error_deg=yaw,cube_quaternion=d.xquat[cube].tolist()))
answer=dict(runtime_stamp=r['runtime_stamp'],physical_steps=0,script_sha256=sha(__file__),episode=a.episode,
    result_sha256=sha(folder/'result.json'),trajectory_sha256=sha(folder/'trajectory.npz'),samples=rows,sample_bound=24,
    selected_normal_world_m=normal.tolist(),maximum_active_finger_tracking_error_rad=float(max(np.max(abs(np.array(x['actual_hand_minus_command_rad'])[active])) for x in rows)),
    maximum_finger_torque_limit_fraction=float(max(max(x['active_finger_torque_limit_fraction']) for x in rows)),
    limitation='25Hz actual saved-state and virtual command FK, not per-step finger IK replay; post-drop cube rotation may change nearest face. Final solver axis read from audit and explicitly fixed for this diagnostic. Geometry alone cannot certify contact force or causal failure.')
dest=root/'out'/a.output;assert dest.suffix=='.json'
with dest.open('x') as f:f.write(json.dumps(answer,indent=2,allow_nan=False)+'\n')
print(json.dumps(answer,indent=2,allow_nan=False))
