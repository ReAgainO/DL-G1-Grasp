"""Bounded ARDY-seeded branch planning after actual wrist clearance.

Candidate joints are SONIC INPUT references, never physical state or decoded
motor overrides. Static OPEN-hand clearance and finger reachability filter
branches but do not certify their dynamic path or contact stability.
"""
import numpy as np
import mujoco
import source_physics_core as core
from adaptive_hand import AdaptiveHand
from branch_face_ik import face_ik

class NativeBranchRejected(ValueError):
    def __init__(self,message,audit):
        super().__init__(message);self.audit=audit


def validate_candidates(candidates):
    if not 1 <= len(candidates) <= 7:
        raise ValueError('Branch count bound1..7')
    feasible=[]
    for row in candidates:
        q=np.asarray(row['body_q'],dtype=float)
        numbers=[row[k] for k in ['capture_error_m','pad_spread_m','minimum_arm_limit_margin_rad',
            'open_robot_table_clearance_m','finger_replan_error_m','native_pose_deviation_rad']]
        if q.shape!=(7,) or not np.isfinite(q).all() or not np.isfinite(numbers).all():
            raise ValueError('Finite seven-joint candidate and metrics required')
        okay=(row['capture_error_m']<=.001 and row['pad_spread_m']<=.002
            and row['minimum_arm_limit_margin_rad']>=.02
            and row['open_robot_table_clearance_m']>=.01
            and row['finger_replan_error_m']<=.0015)
        row['static_feasible']=bool(okay)
        if okay:feasible.append(row)
    if not feasible:
        raise ValueError('No candidate passes static capture/hand/limits/open-table filters')
    return min(feasible,key=lambda r:(r['finger_replan_error_m'],r['native_pose_deviation_rad']))


def select_native_branch(m,d,arm_qadr,arm_vadr,hand_qadr,hand_recipe,target,cube_R,
                         source_arm_frames,common_source_pose,opponent,ik_function,point_function,
                         face_alignment=False,hand_preload_m=.0005,hand_face_half_m=.015):
    frames=np.asarray(source_arm_frames,dtype=float)
    common=np.asarray(common_source_pose,dtype=float)
    if frames.ndim!=2 or frames.shape[1]!=7 or not 2<=len(frames)<=2250 or not np.isfinite(frames).all():
        raise ValueError('Bounded finite actual ARDY arm frames required')
    if common.shape!=(7,) or not np.isfinite(common).all():
        raise ValueError('Common source pose is required for genuine common-distance metric')
    indices=sorted(set(int(i) for i in np.linspace(0,len(frames)-1,6)))
    seeds=[('current_executed_arm',None,d.qpos[arm_qadr].copy())]
    seeds += [('selected_ardy_frame',i,frames[i].copy()) for i in indices]
    table=m.geom('table_top').id
    bodies={m.body('pelvis').id}
    for body in range(1,m.nbody):
        if int(m.body_parentid[body]) in bodies:bodies.add(body)
    geoms=[g for g in range(m.ngeom) if int(m.geom_bodyid[g]) in bodies
        and ((int(m.geom_contype[g])&int(m.geom_conaffinity[table]))
             or (int(m.geom_contype[table])&int(m.geom_conaffinity[g])))]
    assert 1<=len(geoms)<=128
    jids=m.dof_jntid[arm_vadr];limits=m.jnt_range[jids]
    pad_ids=[m.geom(n).id for n in core.PADS]
    candidates=[];rejected=[]
    for label,index,seed in seeds:
        f=mujoco.MjData(m);f.qpos[:]=d.qpos;f.qpos[hand_qadr]=hand_recipe
        q=seed.copy()
        try:
            for _ in range(4):
                q=(face_ik if face_alignment else ik_function)(m,f,arm_qadr,arm_vadr,np.asarray(target),np.eye(3),q,seed,0.,True,True,True,cube_R,opponent)
        except ValueError as error:
            if not face_alignment:raise
            rejected.append(dict(seed_label=label,source_frame=index,rejection=str(error),static_feasible=False))
            continue
        f.qpos[arm_qadr]=q;mujoco.mj_forward(m,f)
        capture_error=float(np.linalg.norm(point_function(m,f,True,cube_R,opponent)-target))
        spread=float(np.ptp(f.geom_xpos[pad_ids,2]))
        hand=AdaptiveHand(m,opponent,hand_preload_m,hand_face_half_m)
        hand.solve(f,np.asarray(target),cube_R,hand_recipe,
            f.geom_xpos[pad_ids[opponent]]-f.geom_xpos[pad_ids[0]])
        finger_error=hand.last['max_pad_target_error_m']
        f.qpos[hand_qadr]=core.OPEN;mujoco.mj_forward(m,f)
        clearance=min(float(mujoco.mj_geomDistance(m,f,g,table,.2,None)) for g in geoms)
        margin=float(np.min(np.minimum(q-limits[:,0],limits[:,1]-q)))
        candidates.append(dict(seed_label=label,source_frame=index,body_q=q.tolist(),
            capture_error_m=capture_error,pad_spread_m=spread,
            minimum_arm_limit_margin_rad=margin,open_robot_table_clearance_m=clearance,
            finger_replan_error_m=finger_error,native_pose_deviation_rad=float(np.linalg.norm(q-common))))
    audit=dict(kind='Selected ARDY multistart static IK branch after actual wrist-height clearance',
        candidate_count=len(seeds),evaluated_count=len(candidates),rejected=rejected,selected=None,candidates=candidates,
        face_alignment_enabled=bool(face_alignment),hand_preload_m=hand_preload_m,hand_face_half_m=hand_face_half_m,
        search_state=dict(time_s=float(d.time),qpos=d.qpos.tolist(),qvel=d.qvel.tolist(),
            interpretation='Exact actual state at live static search, not a full policy-history resume snapshot'),
        real_base_position_m=d.qpos[:3].tolist(),real_base_quaternion_wxyz=d.qpos[3:7].tolist(),
        target_closed_pad_surface_m=np.asarray(target).tolist(),
        physical_steps_in_search=0,body_motor_target_override=False,object_state_writes=False,
        arm_reference_changed=False,static_feasible=False,dynamic_collision_free_certified=False,
        hand_contact_stability_validated=False,
        metric_definition='Distance to one COMMON selected-source pose, not each branch own seed. Static thresholds capture1mm/spread2mm/arm margin20mrad/open-table10mm/hand-replan1.5mm; not success-gate relaxations.')
    try:chosen=validate_candidates(candidates)
    except ValueError as error:raise NativeBranchRejected(str(error),audit) from error
    audit.update(selected=chosen,arm_reference_changed=True,static_feasible=True)
    return np.asarray(chosen['body_q']),audit
