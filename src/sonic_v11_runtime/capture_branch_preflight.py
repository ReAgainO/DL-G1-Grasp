"""Saved-state hand/branch reachability comparison; mj_forward only, no stepping."""
import argparse
import json
import sys
from pathlib import Path
import mujoco
import numpy as np
import sonic_v11 as s
import source_physics_core as core
from adaptive_hand import AdaptiveHand
from sonic_grasp import ik, pinch_center

p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('episodes',nargs='+');a=p.parse_args()
root=Path(__file__).resolve().parent
assert Path(a.output).name==a.output and 1<=len(a.episodes)<=4
output=root/'out'/a.output
assert not output.exists()
branches=json.loads((root/'out/pinch-feasibility.json').read_text())
old=min([r for r in branches['records'] if r['target']=='pregrasp' and r['feasible']],key=lambda r:r['native_seed_deviation_rad'])
records=[]
for name in a.episodes:
    assert Path(name).name==name
    folder=root/'out'/name;r=json.loads((folder/'result.json').read_text())
    assert r['runtime_stamp']['mujoco_version']==mujoco.__version__
    m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'))
    for key,file in [('scene','scene.xml'),('robot','g1_free_grasp.xml')]:
        assert s.sha(folder/file)==r['runtime_stamp']['model_sha'][key]
    aq=m.jnt_qposadr[m.actuator_trnid[:29,0]];av=m.jnt_dofadr[m.actuator_trnid[:29,0]]
    hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]]
    wrist=m.body('right_wrist_yaw_link').id;cube=m.body('red_cube').id
    pads=[m.geom(n).id for n in core.PADS];opponent=2 if r['opposing_pad']=='right_middle_fingertip' else 1
    hand=core.CLOSED.copy();hand[2]=-.88
    with np.load(folder/'trajectory.npz',allow_pickle=False) as z:
        assert len(z['qpos'])<=2250
        states={k:z[k].copy() for k in ['qpos','qvel','time','phase','body_reference','hand_reference']}
    phases=states['phase'];samples=[]
    for phase in ['CLOSE','LIFT','HOLD']:
        indices=np.flatnonzero(phases==phase)
        if len(indices):
            samples.extend([int(indices[0]),int(indices[len(indices)//2])])
    samples=sorted(set(samples));assert len(samples)<=6
    observations=[]
    for index in samples:
        d=mujoco.MjData(m);d.qpos[:]=states['qpos'][index];d.qvel[:]=states['qvel'][index]
        mujoco.mj_forward(m,d)
        f=mujoco.MjData(m);f.qpos[:]=d.qpos;f.qpos[hq]=hand;mujoco.mj_forward(m,f)
        normal=f.geom_xpos[pads[opponent]]-f.geom_xpos[pads[0]]
        solver=AdaptiveHand(m,opponent,r.get('grip_preload_mm',.5)*.001,r.get('grip_face_half_mm',15)*.001)
        solver.solve(d,d.xpos[cube].copy(),d.xmat[cube].reshape(3,3),states['hand_reference'][index],normal)
        observations.append(dict(phase=str(phases[index]),saved_time_s=float(states['time'][index]),
            body_arm_rad=d.qpos[aq[22:29]].tolist(),body_reference_arm_rad=states['body_reference'][index,22:29].tolist(),
            wrist_position_m=d.xpos[wrist].tolist(),wrist_rotation=d.xmat[wrist].reshape(3,3).tolist(),
            cube_position_m=d.xpos[cube].tolist(),actual_finger_q_rad=d.qpos[hq].tolist(),
            hand_reference_rad=states['hand_reference'][index].tolist(),
            actual_pad_centres_m=d.geom_xpos[pads].tolist(),
            hypothetical_closed_surface_point_m=pinch_center(m,f,True,d.xmat[cube].reshape(3,3),opponent).tolist(),
            hypothetical_closed_capture_error_m=float(np.linalg.norm(pinch_center(m,f,True,d.xmat[cube].reshape(3,3),opponent)-d.xpos[cube])),
            zero_step_hand_replan=solver.audit()))
    # Compare feasible local branches at the REAL saved floating base, not at
    # the legacy search's root z=.74, using the selected middle surface frame.
    app=np.flatnonzero(phases=='APPROACH');assert len(app)
    index=int(app[-1]);d=mujoco.MjData(m);d.qpos[:]=states['qpos'][index];mujoco.mj_forward(m,d)
    target=d.xpos[cube].copy()+[0,0,.1];R=d.xmat[cube].reshape(3,3).copy()
    seeds=[('actual_arm_at_approach_end',d.qpos[aq[22:29]].copy()),('legacy_selected_endpoint',np.asarray(old['q']))]
    candidates=[]
    for label,seed in seeds:
        f=mujoco.MjData(m);f.qpos[:]=d.qpos;f.qpos[hq]=hand
        q=seed.copy()
        for _ in range(4):q=ik(m,f,aq[22:29],av[22:29],target,np.eye(3),q,seed,0.,True,True,True,R,opponent)
        f.qpos[aq[22:29]]=q;mujoco.mj_forward(m,f)
        point=pinch_center(m,f,True,R,opponent)
        closed_error=float(np.linalg.norm(point-target))
        solver=AdaptiveHand(m,opponent,.0005,.015)
        solver.solve(f,target,R,hand,f.geom_xpos[pads[opponent]]-f.geom_xpos[pads[0]])
        # Initial OPEN-hand clearance after the same body pose; geometry only.
        table=m.geom('table_top').id;f.qpos[hq]=core.OPEN;mujoco.mj_forward(m,f)
        robot_bodies={m.body('pelvis').id}
        for body in range(1,m.nbody):
            if int(m.body_parentid[body]) in robot_bodies:robot_bodies.add(body)
        geoms=[g for g in range(m.ngeom) if int(m.geom_bodyid[g]) in robot_bodies
            and ((int(m.geom_contype[g])&int(m.geom_conaffinity[table]))
                 or (int(m.geom_contype[table])&int(m.geom_conaffinity[g])))]
        distance=min(float(mujoco.mj_geomDistance(m,f,g,table,.2,None)) for g in geoms)
        candidates.append(dict(seed_label=label,body_q=q.tolist(),target_m=target.tolist(),
            closed_surface_error_m=closed_error,open_hand_robot_table_min_distance_m=distance,
            zero_step_finger_replan_error_m=solver.last['max_pad_target_error_m'],
            source_legacy_seed=old['seed'] if label.startswith('legacy') else None))
    records.append(dict(episode=name,result_sha256=s.sha(folder/'result.json'),
        trajectory_sha256=s.sha(folder/'trajectory.npz'),source_runtime_stamp=r['runtime_stamp'],
        observations=observations,branch_candidates=candidates))
answer=dict(runtime_stamp=dict(mujoco_version=mujoco.__version__,python=sys.version,
    sys_executable=sys.executable,scene_generator_sha=s.sha(__file__),dt=.002,
    library_sha={n:s.sha(root/(n+'.py')) for n in ['sonic_grasp','adaptive_hand','grasp_geometry','source_physics_core']},
    endpoint_inventory_sha=s.sha(root/'out/pinch-feasibility.json')),
    physical_steps=0,records=records,
    limits='Saved-state FK/hand-IK feasibility only. Forward recomputation does not supply original solver force. Legacy branch uses a different root/frame and per-own-seed metric; candidates have no SONIC tracking, dynamic collision-free path or physical grasp certificate.')
output.mkdir();(output/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(dict(physical_steps=0,records=[dict(episode=r['episode'],
    samples=[dict(phase=o['phase'],time_s=o['saved_time_s'],closed_capture_error_mm=o['hypothetical_closed_capture_error_m']*1000,
        replan_error_mm=o['zero_step_hand_replan']['last']['max_pad_target_error_m']*1000) for o in r['observations']],
    branch_candidates=r['branch_candidates']) for r in records]),indent=2))
