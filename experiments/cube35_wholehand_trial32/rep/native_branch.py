"""Bounded ARDY-seeded branch planning after actual wrist clearance.

Candidate joints are SONIC INPUT references, never physical state or decoded
motor overrides. Static OPEN-hand clearance and finger reachability filter
branches but do not certify their dynamic path or contact stability.

N2 (lane N2_cand) addition -- an ORDERED, cube-driven candidate-COVERAGE
schedule. Read this before touching anything:
  * validate_candidates() and all five of its thresholds are copied verbatim
    from the fork baseline and are NOT relaxed by a single unit.
  * Batch 0 of the schedule is bit-identical to the single batch the baseline
    evaluated (same 7 seeds, same order, same target), so with coverage
    disabled -- the default -- nothing at all changes.
  * Every further batch is also <=7 candidates and is judged by the same
    unmodified filters. A rejected batch triggers a REPLAN onto the next batch
    of the schedule instead of aborting the trial. The varied dimensions are
    all driven by the REAL cube centre and its REAL rotation:
       standoff_m   height of the pregrasp pinch-centre reference above the
                    grasp centre (approach profile),
       lateral_m    how far that reference sits off the vertical through the
                    centre, and
       azimuth_deg  the direction of that offset expressed in the CUBE frame,
                    i.e. which pair of opposing cube faces the pad line
                    straddles -> the APPROACH SIDE,
       family='redundancy'  the 2-DOF arm-nullspace neighbourhood of the best
                    converged pose of the matching profile batch -> the WRIST
                    ORIENTATION (roll/pitch/elbow) at a fixed pinch centre,
       frame_set    a denser ARDY source-seed sampling than linspace(0,n-1,6).
  * No live state is read except through d.qpos; the nullspace probe uses its
    own scratch MjData, never d.
  * The audit records every batch, its configuration, all per-candidate metrics
    and 'attempt_used', so a rejection is never merely a logged rejection.
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


# ---------------------------------------------------------------------------
# N2 coverage schedule: deterministic, ordered, bounded. Index 0 IS the
# baseline batch; every profile is tried as a source-seed batch first and then
# as the arm-nullspace (wrist orientation) refinement of that same profile.
# ---------------------------------------------------------------------------
N2_BASE_STANDOFF_M=.10                 # baseline: highpos = grasp centre + [0,0,.10]
N2_REDUNDANCY_STEPS_RAD=(-.10,.10)     # along each nullspace basis vector
N2_REDUNDANCY_SHEAR_RAD=(-.15,.15)     # along (u0+u1)/sqrt(2)
N2_PROFILES=((None,0.,None),            # 00 baseline approach profile
             (.06,0.,None),             # 01 lower standoff
             (.045,0.,None),            # 02 still lower
             (.085,0.,None),            # 03 higher standoff
             (.13,0.,None),             # 04 much higher standoff
             (None,.025,0.),            # 05 side offset toward cube +x face
             (None,.025,90.),           # 06 side offset toward cube +y face
             (None,.025,180.),          # 07 side offset toward cube -x face
             (None,.025,270.),          # 08 side offset toward cube -y face
             (.06,.025,0.),             # 09 side offset at lower standoff
             (.06,.025,90.),            # 10
             (.06,.025,180.),           # 11
             (.06,.025,270.),           # 12
             (None,.04,45.),            # 13 wider offset, diagonal face pair
             (None,.04,135.),           # 14
             (None,.04,225.),           # 15
             (None,.04,315.),           # 16
             (.045,.025,90.),           # 17 low standoff + side
             (.045,.025,270.))          # 18
N2_DENSER_OFFSETS=(4,9,14,24,29,34)     # extra ARDY frames, none in linspace(0,n-1,6)
N2_BATCH_LIMIT=40                       # 19 profiles x 2 families + 2 denser batches


def _profile_target(base_target,grasp_center,cube_R,standoff_m,lateral_m,azimuth_deg):
    """Pregrasp pinch-centre reference for one batch; None standoff -> baseline."""
    if standoff_m is None and not lateral_m:
        return np.asarray(base_target,dtype=float)
    center=np.asarray(grasp_center,dtype=float)
    height=(np.asarray(base_target,dtype=float)-center if standoff_m is None
            else np.array([0.,0.,float(standoff_m)]))
    lateral=np.zeros(3)
    if lateral_m:
        theta=np.deg2rad(float(azimuth_deg or 0.))
        lateral=np.asarray(cube_R,dtype=float)@np.array([float(lateral_m)*np.cos(theta),
                                                         float(lateral_m)*np.sin(theta),0.])
    return center+height+lateral


def _profile_key(config):
    return 's%s_l%s_a%s'%(config['standoff_m'],config['lateral_m'],config['azimuth_deg'])


def coverage_plan(frame_count):
    """Deterministic ordered batch configurations; plan[0] IS the baseline batch."""
    denser=[int(i) for i in N2_DENSER_OFFSETS if int(i)<int(frame_count)][:6]
    plan=[]
    for index,(standoff,lateral,azimuth) in enumerate(N2_PROFILES):
        plan.append(dict(tag='p%02d_source'%index,family='source',standoff_m=standoff,
            lateral_m=lateral,azimuth_deg=azimuth,frame_set=None))
        plan.append(dict(tag='p%02d_redundancy'%index,family='redundancy',standoff_m=standoff,
            lateral_m=lateral,azimuth_deg=azimuth,frame_set=None))
    if denser:
        plan.append(dict(tag='denser_source',family='source',standoff_m=None,lateral_m=0.,
            azimuth_deg=None,frame_set=denser))
        plan.append(dict(tag='denser_redundancy',family='redundancy',standoff_m=None,lateral_m=0.,
            azimuth_deg=None,frame_set=denser))
    return plan[:N2_BATCH_LIMIT]


def _nullspace_directions(m,arm_qadr,hand_qadr,hand_recipe,target,point_function,cube_R,
                          opponent,pads,q_ref,limit_lo,limit_hi):
    """Numerically span the arm redundancy left by the 5 rows ik() constrains.

    Uses its OWN scratch MjData; the live simulation state is never written.
    """
    fk=mujoco.MjData(m);h=1e-5
    def err(q):
        fk.qpos[arm_qadr]=np.clip(q,limit_lo,limit_hi);fk.qpos[hand_qadr]=hand_recipe
        mujoco.mj_forward(m,fk)
        point=np.asarray(point_function(m,fk,True,cube_R,opponent),dtype=float)-np.asarray(target,dtype=float)
        heights=np.array([fk.geom_xpos[pads[0],2]-fk.geom_xpos[pads[1],2],
                          fk.geom_xpos[pads[2],2]-fk.geom_xpos[pads[1],2]])
        return np.r_[point,heights]
    base=err(q_ref);J=np.zeros((5,7))
    for k in range(7):
        up=q_ref.copy();up[k]+=h;down=q_ref.copy();down[k]-=h
        J[:,k]=(err(up)-err(down))/(2*h)
    U,singular,Vh=np.linalg.svd(J)
    rank=int(np.sum(singular>max(J.shape)*max(float(singular[0]),1e-12)*1e-9)) if len(singular) else 0
    basis=np.asarray(Vh[rank:][:2],dtype=float)
    while len(basis)<2:
        basis=np.vstack([basis,np.zeros(7)])
    basis=basis/np.maximum(np.linalg.norm(basis,axis=1,keepdims=True),1e-12)
    return basis,rank,[float(v) for v in singular],float(np.linalg.norm(base))


def select_native_branch(m,d,arm_qadr,arm_vadr,hand_qadr,hand_recipe,target,cube_R,
                         source_arm_frames,common_source_pose,opponent,ik_function,point_function,
                         face_alignment=False,hand_preload_m=.0005,hand_face_half_m=.015,
                         coverage=False,grasp_center=None):
    frames=np.asarray(source_arm_frames,dtype=float)
    common=np.asarray(common_source_pose,dtype=float)
    if frames.ndim!=2 or frames.shape[1]!=7 or not 2<=len(frames)<=2250 or not np.isfinite(frames).all():
        raise ValueError('Bounded finite actual ARDY arm frames required')
    if common.shape!=(7,) or not np.isfinite(common).all():
        raise ValueError('Common source pose is required for genuine common-distance metric')
    if coverage and grasp_center is None:
        raise ValueError('N2 coverage needs the real grasp centre the schedule is built from')
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
    base_indices=sorted(set(int(i) for i in np.linspace(0,len(frames)-1,6)))

    def evaluate(seeds,tgt):
        """One batch of <=7 candidates; body copied verbatim from the baseline loop."""
        candidates=[];rejected=[];reference=None;reference_error=np.inf
        for label,index,seed in seeds:
            f=mujoco.MjData(m);f.qpos[:]=d.qpos;f.qpos[hand_qadr]=hand_recipe
            q=np.asarray(seed,dtype=float).copy()
            try:
                for _ in range(4):
                    q=(face_ik if face_alignment else ik_function)(m,f,arm_qadr,arm_vadr,np.asarray(tgt),np.eye(3),q,seed,0.,True,True,True,cube_R,opponent)
            except ValueError as error:
                if not (face_alignment or coverage):raise
                rejected.append(dict(seed_label=label,source_frame=index,rejection=str(error),static_feasible=False))
                continue
            f.qpos[arm_qadr]=q;mujoco.mj_forward(m,f)
            capture_error=float(np.linalg.norm(point_function(m,f,True,cube_R,opponent)-tgt))
            spread=float(np.ptp(f.geom_xpos[pad_ids,2]))
            hand=AdaptiveHand(m,opponent,hand_preload_m,hand_face_half_m)
            hand.solve(f,np.asarray(tgt),cube_R,hand_recipe,
                f.geom_xpos[pad_ids[opponent]]-f.geom_xpos[pad_ids[0]])
            finger_error=hand.last['max_pad_target_error_m']
            f.qpos[hand_qadr]=core.OPEN;mujoco.mj_forward(m,f)
            clearance=min(float(mujoco.mj_geomDistance(m,f,g,table,.2,None)) for g in geoms)
            margin=float(np.min(np.minimum(q-limits[:,0],limits[:,1]-q)))
            candidates.append(dict(seed_label=label,source_frame=index,body_q=q.tolist(),
                capture_error_m=capture_error,pad_spread_m=spread,
                minimum_arm_limit_margin_rad=margin,open_robot_table_clearance_m=clearance,
                finger_replan_error_m=finger_error,native_pose_deviation_rad=float(np.linalg.norm(q-common))))
            if capture_error<=.001 and finger_error<reference_error:
                reference_error=finger_error;reference=q.copy()
        return candidates,rejected,reference

    def source_seeds(frame_set=None):
        indices=base_indices if frame_set is None else sorted(set(int(i) for i in frame_set))
        seeds=[('current_executed_arm',None,d.qpos[arm_qadr].copy())]
        seeds+=[('selected_ardy_frame',i,frames[i].copy()) for i in indices]
        return seeds

    plan=(coverage_plan(len(frames)) if coverage else
          [dict(tag='b00_native',family='source',standoff_m=None,lateral_m=0.,
                azimuth_deg=None,frame_set=None)])
    reference_by_profile={};batches=[];chosen=None;attempt_used=None
    for batch_index,config in enumerate(plan):
        tgt=_profile_target(target,grasp_center,cube_R,config['standoff_m'],
                            config['lateral_m'],config['azimuth_deg'])
        key=_profile_key(config);seeds_extra=dict()
        if config['family']=='redundancy':
            q_ref=reference_by_profile.get(key)
            if q_ref is None:
                batches.append(dict(attempt=batch_index,tag=config['tag'],family='redundancy',
                    standoff_m=config['standoff_m'],lateral_m=config['lateral_m'],
                    azimuth_deg=config['azimuth_deg'],frame_set=config['frame_set'],
                    evaluated_target_m=np.asarray(tgt).tolist(),accepted=False,
                    skipped='no converged pose recorded for this profile yet',
                    candidate_count=0,evaluated_count=0,rejected=[],candidates=[]));continue
            basis,rank,singular,residual=_nullspace_directions(m,arm_qadr,hand_qadr,hand_recipe,tgt,
                point_function,cube_R,opponent,pad_ids,q_ref,limits[:,0]+.002,limits[:,1]-.002)
            shear=(basis[0]+basis[1])/np.sqrt(2.)
            variants=[('arm_nullspace_basis%02d_step%+04d'%(k,int(round(100*step))),None,
                       np.clip(q_ref+step*basis[k],limits[:,0]+.002,limits[:,1]-.002))
                       for k in range(2) for step in N2_REDUNDANCY_STEPS_RAD]
            variants+=[('arm_nullspace_shear_step%+04d'%int(round(100*step)),None,
                        np.clip(q_ref+step*shear,limits[:,0]+.002,limits[:,1]-.002))
                        for step in N2_REDUNDANCY_SHEAR_RAD]
            seeds=[('current_executed_arm',None,d.qpos[arm_qadr].copy())]+variants
            seeds=seeds[:7]
            seeds_extra=dict(nullspace_rank=int(rank),nullspace_singular_values=singular,
                converged_residual_m=residual,profile_reference_body_q=q_ref.tolist())
        else:
            seeds=source_seeds(config['frame_set'])
        candidates,rejected,reference=evaluate(seeds,tgt)
        if reference is not None:reference_by_profile.setdefault(key,reference)
        entry=dict(attempt=batch_index,tag=config['tag'],family=config['family'],
            standoff_m=config['standoff_m'],lateral_m=config['lateral_m'],
            azimuth_deg=config['azimuth_deg'],frame_set=config['frame_set'],
            evaluated_target_m=np.asarray(tgt).tolist(),candidate_count=len(seeds),
            evaluated_count=len(candidates),rejected=rejected,candidates=candidates,
            best_finger_replan_error_m=float(min((c['finger_replan_error_m'] for c in candidates),
                                                 default=np.inf)),
            best_capture_error_m=float(min((c['capture_error_m'] for c in candidates),default=np.inf)),
            accepted=False)
        entry.update(seeds_extra)
        try:
            selected=validate_candidates(candidates)
        except ValueError as error:
            entry['rejection']=str(error);batches.append(entry);continue
        entry['accepted']=True;entry['selected_seed_label']=selected['seed_label']
        entry['selected_source_frame']=selected['source_frame'];batches.append(entry)
        chosen=selected;attempt_used=batch_index;break
    first=batches[0]
    best_overall=min((b['best_finger_replan_error_m'] for b in batches
                      if b.get('evaluated_count')),default=first['best_finger_replan_error_m'])
    audit=dict(kind='Selected ARDY multistart static IK branch after actual wrist-height clearance',
        candidate_count=first['candidate_count'],evaluated_count=first['evaluated_count'],
        rejected=first['rejected'],selected=None,candidates=first['candidates'],
        face_alignment_enabled=bool(face_alignment),hand_preload_m=hand_preload_m,hand_face_half_m=hand_face_half_m,
        search_state=dict(time_s=float(d.time),qpos=d.qpos.tolist(),qvel=d.qvel.tolist(),
            interpretation='Exact actual state at live static search, not a full policy-history resume snapshot'),
        real_base_position_m=d.qpos[:3].tolist(),real_base_quaternion_wxyz=d.qpos[3:7].tolist(),
        target_closed_pad_surface_m=np.asarray(target).tolist(),
        physical_steps_in_search=0,body_motor_target_override=False,object_state_writes=False,
        arm_reference_changed=False,static_feasible=False,dynamic_collision_free_certified=False,
        hand_contact_stability_validated=False,
        metric_definition='Distance to one COMMON selected-source pose, not each branch own seed. Static thresholds capture1mm/spread2mm/arm margin20mrad/open-table10mm/hand-replan1.5mm; not success-gate relaxations.',
        coverage=dict(enabled=bool(coverage),attempt_used=attempt_used,
            batches_evaluated=len(batches),batch_bound=N2_BATCH_LIMIT,
            base_standoff_m=N2_BASE_STANDOFF_M,
            thresholds_unchanged=dict(capture_error_m=.001,pad_spread_m=.002,
                minimum_arm_limit_margin_rad=.02,open_robot_table_clearance_m=.01,
                finger_replan_error_m=.0015,candidate_count_bound='1..7 per batch'),
            best_finger_replan_error_m_over_all_batches=(float(best_overall)
                if np.isfinite(best_overall) else None),
            dimensions=('standoff_m/lateral_m/azimuth_deg of the pregrasp reference about the REAL cube '
                'centre and its REAL rotation (approach profile and which opposing cube face pair the pad '
                'line straddles); 2-DOF arm nullspace variants of the best converged pose of that same '
                'profile (wrist roll/pitch/elbow at a fixed pinch centre); denser ARDY source-seed '
                'sampling than linspace(0,n-1,6)'),
            rejection_action=('a rejected batch REPLANS onto the next batch of the ordered schedule and '
                'only the final exhaustion of the schedule aborts the trial'),
            schedule=plan,batches=batches))
    if chosen is None:
        raise NativeBranchRejected('No candidate passes static capture/hand/limits/open-table filters',audit)
    audit.update(selected=chosen,arm_reference_changed=True,static_feasible=True)
    return np.asarray(chosen['body_q']),audit
