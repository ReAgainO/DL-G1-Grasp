"""Free-base SONIC grasp diagnostic: ARDY prior + explicit calibrated task geometry.

This is a hybrid retargeting method, NOT a native ARDY grasp claim. All 29 body
targets come from official SONIC; optional PD/gravity actuator adaptations are
explicitly audited. IK/search modify only the reference entering SONIC; there
is no scripted arm-target override or generalized/object force injection.
"""
import argparse,gzip,json,os,time,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np,mujoco
import source_physics_core as core
import sonic_v11 as s
from motion_input import ArdyMotion
from task_plan import rot_error,rotation_blend
from reference_filter import ReferenceFilter
from policy_reference import PolicyReference
from grasp_geometry import contact_frame
from discrete_reference import DiscreteReference
from adaptive_hand import AdaptiveHand
from contact_audit import ContactAudit
from decoded_arm_filter import DecodedArmFilter
from balance_audit import BalanceAudit
from table_placement import place_direct_table
from finger_control import finger_torques
from setdown_plan import SetdownPlan,table_supported_gate
from neutral_pose import neutral_body
from execution_monitor import ExecutionMonitor
from clearance_approach import ClearanceApproach
from motion_profile import MotionProfile
from native_branch import select_native_branch
from branch_execution import BranchExecution
from cycle_latency import CycleLatency
from branch_face_ik import face_ik

def runtime_stamp(root,scene,out,controller,motion,phase_motions,sonic_armature,endpoint_seed,selected_profile=None):
 return dict(mujoco_version=mujoco.__version__,sys_executable=__import__('sys').executable,python_version=__import__('sys').version,
            model_sha={'scene':s.sha(scene),'robot':s.sha(out/'g1_free_grasp.xml')},scene_generator_sha=s.sha(__file__),library_versions={'numpy':np.__version__,'onnxruntime':s.ort.__version__},
            library_sha={**controller.model_stamp,'sonic_v11':s.sha(s.__file__),'native_npz':motion.audit['source_npz_sha256'],
                         **{k:v.audit['source_npz_sha256'] for k,v in phase_motions.items()},
                         **{k:s.sha(root/(k+'.py')) for k in ['reference_filter','policy_reference','grasp_geometry','discrete_reference','adaptive_hand','contact_audit','decoded_arm_filter','balance_audit','table_placement','finger_control','setdown_plan','motion_input','task_plan','neutral_pose','execution_monitor','clearance_approach','motion_profile','native_branch','branch_execution','finger_clearance','cycle_latency','branch_face_ik']},
                         **({'input_profile':s.sha(selected_profile.path),'generation_summary':s.sha(selected_profile.summary)} if selected_profile is not None else {}),
                         **({'official_dynamics_audit':s.sha(root/'out/official-dynamics.json'),'official_training_g1':s.sha(root/'official_refs/g1_training.py')} if sonic_armature else {}),
                         **({'endpoint_seed':s.sha(root/'out/pinch-feasibility.json')} if endpoint_seed else {}),
                         'calibration':s.sha(root/'src/manual_grasp_calibration.npz'),'source_physics_core':s.sha(core.__file__)},dt=.002)

def scene_and_cal(root,out,fixed_base=False,direct_table=False,sonic_armature=False,passive_free=False,table_front=.23,cube_edge_mm=35.,cube_x=.267,cube_y=-.118):
 assets=root/'src/g1'
 # Rebuild calibration frame solely to recover human-specified wrist geometry.
 # A3/H1': this call is deliberately LEFT at the hardcoded human-demo cube
 # ([.267,-.118], .7745). It only yields `offset` = wrist - cube_centre of the
 # human demonstration, which sonic_grasp.py later re-expresses as
 # grasp = initial_cube + lowR@(lowR.T@offset) against the ACTUAL cube, so the
 # calibration frame must stay a property of the demo, not of the actual block.
 # prepare_model() also overwrites the calibration cube body pos itself
 # (source_physics_core.py:114), so resizing the template below does not move it.
 caldir=out/'calibration_geometry';caldir.mkdir()
 cm=mujoco.MjModel.from_xml_path(str(core.prepare_model(assets,caldir,[.267,-.118],.7745,True)))
 cd=mujoco.MjData(cm);cal=np.load(root/'src/manual_grasp_calibration.npz',allow_pickle=False)
 low=int(np.argmin(abs(cal['time']-12)));high=int(np.argmin(abs(cal['time']-17.5)))
 cd.qpos[:]=cal['qpos'][low];mujoco.mj_forward(cm,cd)
 wrist=cm.body('right_wrist_yaw_link').id;cube=cm.body('red_cube').id
 offset=(cd.xpos[wrist]-cd.xpos[cube]).copy();lowR=cd.xmat[wrist].reshape(3,3).copy()
 cd.qpos[:]=cal['qpos'][high];mujoco.mj_forward(cm,cd)
 highpos=cd.xpos[wrist].copy();highR=cd.xmat[wrist].reshape(3,3).copy()
 # Preserve floating base and all waist/body actuators. Only finger pad masks
 # match the previously isolated hand experiment; no equality constraints.
 robot=ET.parse(assets/'g1_29dof_with_hand.xml');robot.find('compiler').set('meshdir',str(assets/'meshes'))
 if passive_free:assert sonic_armature
 if sonic_armature:
  audit=json.loads((root/'out/official-dynamics.json').read_text());assert audit['official_source_sha']==s.sha(root/'official_refs/g1_training.py')
  mapping=audit['body_armatures'];count=0
  for joint in robot.iter('joint'):
   if joint.get('name') in mapping:
    joint.set('armature',format(mapping[joint.get('name')],'.12g'));count+=1
    if passive_free:joint.set('damping','0');joint.set('frictionloss','0')
  assert count==29
 if fixed_base:
  pelvis=robot.find(".//body[@name='pelvis']");assert pelvis is not None and (pelvis.find('freejoint') is not None or pelvis.find("joint[@type='free']") is not None)
  pelvis.set('pos','0 0 .788740')
 for body in robot.iter('body'):
  if body.get('name','').startswith('right_hand_'):
   for geom in body.findall('geom'):
    geom.set('contype','2' if geom.get('name') in core.PADS else '0');geom.set('conaffinity','0')
 robot.write(out/'g1_free_grasp.xml',encoding='utf-8')
 scene=ET.parse(assets/'scene_grasp_hand.xml');scene.find('include').set('file','g1_free_grasp.xml')
 for geom in scene.findall('.//worldbody//geom'):geom.set('conaffinity','3')
 scene.find(".//geom[@name='red_cube_geom']").set('contype','1')
 if direct_table:
  # A broad table directly supports the block at the SAME original initial
  # height. Remove the narrow riser, not the object's free joint or collisions.
  world=scene.find('worldbody');pedestal=world.find("body[@name='cube_pedestal']")
  assert pedestal is not None;world.remove(pedestal)
  table=world.find(".//geom[@name='table_top']");assert table is not None
  place_direct_table(table,table_front)
 # A3/H1' + A3 task2: cube edge length and cube xy have NO other entry point in
 # this route -- src/g1/scene_grasp_hand.xml is the only place they exist, and
 # sonic_grasp.py's CLI never exposed them. Rewrite them here in memory.
 # At the defaults (35mm, .267, -.118) the generated attribute text is
 # byte-identical to the template, so scene.xml and its sha256 are unchanged and
 # the baseline trajectory stays bit-identical. Mass is NOT rescaled: the cube
 # edge is the single variable.
 cube_body=scene.find(".//body[@name='red_cube']");cube_geom=scene.find(".//geom[@name='red_cube_geom']")
 assert cube_body is not None and cube_geom is not None and cube_geom.get('type')=='box'
 if not np.isfinite(cube_edge_mm) or not 10.<=cube_edge_mm<=80.:raise ValueError('Cube edge must be finite and 10..80mm (W4f widened input domain; success gates untouched)')
 if not np.isfinite(cube_x) or not np.isfinite(cube_y):raise ValueError('Finite cube xy required')
 cube_half=cube_edge_mm*.0005
 size_text='%.10g %.10g %.10g'%(cube_half,cube_half,cube_half)
 if cube_geom.get('size')!=size_text:cube_geom.set('size',size_text)
 table_geom=scene.find(".//geom[@name='table_top']");assert table_geom is not None
 if direct_table:
  tpos=[float(v) for v in table_geom.get('pos').split()];tsize=[float(v) for v in table_geom.get('size').split()]
  support_top=tpos[2]+tsize[2]
  # keep the whole footprint on the tabletop, else the block starts off-support
  if not (tpos[0]-tsize[0]+cube_half<=cube_x<=tpos[0]+tsize[0]-cube_half):raise ValueError('Cube footprint leaves the table in x')
  if not (tpos[1]-tsize[1]+cube_half<=cube_y<=tpos[1]+tsize[1]-cube_half):raise ValueError('Cube footprint leaves the table in y')
 else:
  support_top=.757 # template riser top: 0.741 + 0.016
 pos_text='%.10g %.10g %.10g'%(cube_x,cube_y,support_top+cube_half)
 if cube_body.get('pos')!=pos_text:cube_body.set('pos',pos_text)
 if fixed_base:
  equality=scene.find('equality')
  if equality is None:equality=ET.SubElement(scene.getroot(),'equality')
  ET.SubElement(equality,'weld',name='robot_base_fixture',body1='pelvis',solref='.002 1')
 scene.write(out/'scene.xml',encoding='utf-8')
 return out/'scene.xml',offset,lowR,highpos,highR

def pinch_center(m,fk,surface=False,cube_R=None,opponent=1):
 if surface:return contact_frame(m,fk,cube_R,opponent=opponent)
 return (fk.geom_xpos[m.geom(core.PADS[0]).id]+fk.geom_xpos[m.geom(core.PADS[1]).id])*.5

def ik(m,fk,aq,av,target,R,seed,prior,weight,pinch=False,flat_pinch=False,surface=False,cube_R=None,opponent=1):
 q=seed.copy();jid=m.dof_jntid[av];lo=m.jnt_range[jid,0]+.002;hi=m.jnt_range[jid,1]-.002
 wrist=m.body('right_wrist_yaw_link').id;jp=np.zeros((3,m.nv));jr=jp.copy()
 for _ in range(15):
  fk.qpos[aq]=q;mujoco.mj_forward(m,fk)
  if pinch:
   ep=target-pinch_center(m,fk,surface,cube_R,opponent);er=np.zeros(3);jp2=jp.copy()
   mujoco.mj_jacGeom(m,fk,jp,jr,m.geom(core.PADS[0]).id);mujoco.mj_jacGeom(m,fk,jp2,None,m.geom(core.PADS[1]).id)
   J=10*(jp[:,av]+jp2[:,av])*.5;err=10*ep
   if surface:J=10*contact_frame(m,fk,cube_R,av,opponent)[1]
   if flat_pinch:
    jp3=np.zeros_like(jp);mujoco.mj_jacGeom(m,fk,jp3,None,m.geom(core.PADS[2]).id)
    heights=np.array([fk.geom_xpos[m.geom(core.PADS[0]).id,2]-fk.geom_xpos[m.geom(core.PADS[1]).id,2],
                      fk.geom_xpos[m.geom(core.PADS[2]).id,2]-fk.geom_xpos[m.geom(core.PADS[1]).id,2]])
    J=np.vstack([J,10*(jp[2,av]-jp2[2,av]),10*(jp3[2,av]-jp2[2,av])]);err=np.r_[err,-10*heights];er=heights
  else:
   ep=target-fk.xpos[wrist];er=rot_error(R,fk.xmat[wrist].reshape(3,3))
   mujoco.mj_jacBody(m,fk,jp,jr,wrist);J=np.vstack([10*jp[:,av],jr[:,av]]);err=np.r_[10*ep,er]
  pinv=J.T@np.linalg.solve(J@J.T+1e-4*np.eye(len(J)),np.eye(len(J)))
  dq=pinv@err+weight*(np.eye(7)-pinv@J)@(prior-q)
  dq*=min(1,.08/max(abs(dq).max(),1e-12));q=np.clip(q+dq,lo,hi)
  if np.linalg.norm(ep)<.0003 and np.linalg.norm(er)<.002:break
 return q

def run(name,weight=.03,no_grip=False,pad_off=False,compensation=True,teleop=False,native_geometry=False,pinch_geometry=False,cart_compensation=False,phase_clips=False,capture_radius=.007,flat_pinch=False,c2_reference=False,policy_aware=False,endpoint_seed=False,arm_gain=1.,fixed_base=False,inverse_anchor=False,endpoint_seed_native=False,inverse_incremental=False,kinematic_servo=False,contact_close=False,align_seconds=8.,surface_capture=False,contact_entry_dwell=.2,freeze_close=False,gravity_arm_scale=0.,opponent=1,close_seconds=2.,teleop_fk_reference=False,discrete_servo=False,discrete_absolute=False,direct_table=False,adaptive_hand=False,grip_frame_lift=False,lock_grip=False,lift_damping=1.,sonic_armature=False,passive_free=False,decoded_filter_tau=0.,decoded_filter_speed=.6,reference_margin=.002,postcapture_arm_gain=0.,postcapture_servo_cap=.06,freeze_hold_servo=False,lift_height=.1,reference_fallback=False,ardy_off=False,table_front=.23,grip_preload_mm=.5,finger_gain=1.,setdown=False,grip_face_half_mm=15.,neutral_shoulder_offset=0.,strict_execution=False,execution_speed_limit=2.,clearance_approach=False,motion_profile=None,clearance_native_branch=False,clearance_branch_servo=False,finger_table_clearance_mm=0.,branch_face_alignment=False,face_aligned_servo=False,cube_edge_mm=35.,cube_x=.267,cube_y=-.118,branch_coverage=False,substep=1,contact_margin=0.,solref=None,impratio=0.):
 if not np.isfinite(finger_table_clearance_mm) or not 0<=finger_table_clearance_mm<=5:raise ValueError('Finger table margin0..5mm')
 if finger_table_clearance_mm:assert adaptive_hand and direct_table
 if ardy_off and clearance_native_branch:raise ValueError('ARDY-off counterfactual invalid while selected-source branch seeding is active; do not mislabel a partial ablation')
 if branch_face_alignment:assert clearance_native_branch and adaptive_hand
 if face_aligned_servo:assert branch_face_alignment and kinematic_servo and flat_pinch and surface_capture
 if branch_coverage:assert clearance_native_branch and adaptive_hand and pinch_geometry and surface_capture and flat_pinch and not branch_face_alignment,'N2 coverage keeps --branch-face-alignment off so the static finger probe still uses the baseline .0005 preload and .015 face region; no filter input is swapped'
 start=time.monotonic();root=Path(__file__).resolve().parent;out=root/'out'/name;out.mkdir()
 scene,offset,lowR,highpos,highR=scene_and_cal(root,out,fixed_base,direct_table,sonic_armature,passive_free,table_front,cube_edge_mm,cube_x,cube_y)
 m=mujoco.MjModel.from_xml_path(str(scene))
 # W4c: optional translation of the official small-object physics recipe (isaaclab
 # e30c25b1 pick_place_redblock: sim.dt=0.005 + 4 substeps, contact_offset 0.01,
 # num_position_iterations 16, CCD) into MuJoCo equivalents. Default OFF: the four
 # knobs below are all neutral and the code path is the original one.
 phys_recipe=None
 if substep!=1 or contact_margin>0 or solref is not None or impratio>0:
  assert isinstance(substep,int) and 1<=substep<=8,"W4c substep must be 1..8"
  assert 0.<=contact_margin<=.005,"W4c contact margin 0..5mm"
  assert 0.<=impratio<=100.,"W4c impratio 0..100"
  if substep!=1:m.opt.timestep=float(m.opt.timestep)/substep
  if impratio>0:m.opt.impratio=float(impratio)
  phys_geoms=[m.geom("red_cube_geom").id]+[m.geom(n).id for n in core.PADS]
  if contact_margin>0:
   for _g in phys_geoms:m.geom_margin[_g]=float(contact_margin)
  if solref is not None:
   assert len(solref)==2 and solref[0]>0 and solref[1]>=0,"W4c solref (timeconst dampratio)"
   for _g in phys_geoms:m.geom_solref[_g]=[float(solref[0]),float(solref[1])]
  phys_recipe=dict(requested=dict(substep=int(substep),contact_margin_m=float(contact_margin),
      solref=None if solref is None else [float(solref[0]),float(solref[1])],impratio=float(impratio)),
      control_hz=500.,physics_timestep_s=float(m.opt.timestep),physics_hz=1./float(m.opt.timestep),
      model_impratio=float(m.opt.impratio),geom_names=[m.geom(_g).name for _g in phys_geoms],
      geom_margin_m=[float(m.geom_margin[_g]) for _g in phys_geoms],
      geom_solref=[[float(x) for x in m.geom_solref[_g]] for _g in phys_geoms],
      scope="cube geom + three fingertip pads; nothing else in the model is touched",
      source="isaaclab @e30c25b1 pick_place_redblock_g1_29dof_dex3: sim.dt .005 x num_substeps 4 / num_position_iterations 16 / enable_ccd / object contact_offset .01 rest 0.0 -> MuJoCo equivalents: timestep/substep subdivision, geom margin, solver impratio; the model already carries <flag multiccd=enable>")
  print("W4C_PHYSICS "+json.dumps(phys_recipe),flush=True)
 d=mujoco.MjData(m)
 assert m.nu==43 and m.nq==57 and m.neq==int(fixed_base) and (m.jnt_type==mujoco.mjtJoint.mjJNT_FREE).sum()==2
 if fixed_base:assert m.eq_obj1id[0]==m.body('pelvis').id and m.eq_obj2id[0]==0
 controller=s.SonicV11(m);load_s=time.monotonic()-start
 selected_profile=MotionProfile(root,motion_profile) if motion_profile is not None else None
 if selected_profile is not None and endpoint_seed and not clearance_approach:
  raise ValueError('Legacy endpoint branches were not recomputed for selected motion; use the explicit clearance scaffold or disable endpoint seed')
 reach_entry=selected_profile.entries['reach'] if selected_profile is not None else None
 motion=ArdyMotion(reach_entry['npz'],check_csv=reach_entry['csv']) if reach_entry is not None else ArdyMotion(root/'src/original_motions'/(os.environ.get('N1_MOTION_STEM','near_s42')+'.npz'),check_csv=root/'src/original_motions'/(os.environ.get('N1_MOTION_STEM','near_s42')+'.csv'))
 if selected_profile is not None:selected_profile.validate_motion('reach',motion)
 phase_motions={};phase_consumed=set();lift_progress=None
 phase_stems={role:role+'_s42' for role in ['lift','hold','release']}
 if phase_clips:
  assert pinch_geometry
  for role in ['lift','hold','release']:
   if selected_profile is not None:
    entry=selected_profile.entries[role];stem=entry['npz'].stem
    phase_motions[stem]=ArdyMotion(entry['npz'],check_csv=entry['csv']);selected_profile.validate_motion(role,phase_motions[stem]);phase_stems[role]=stem
   else:
    stem=phase_stems[role];p=root/'out/generated_phases2'/stem;phase_motions[stem]=ArdyMotion(p.with_suffix('.npz'),check_csv=p.with_suffix('.csv'))
   assert phase_motions[stem].joint_names==motion.joint_names
 assert motion.joint_names==[m.joint(int(j)).name for j in controller.jids]
 arm=slice(22,29);aq=controller.aq[arm];av=controller.av[arm]
 hands=np.arange(36,43);hj=m.actuator_trnid[hands,0];hq=m.jnt_qposadr[hj];hv=m.jnt_dofadr[hj]
 neutral=neutral_body(m,s.DEFAULT_ANGLES,neutral_shoulder_offset)
 d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[controller.aq]=neutral;d.qpos[hq]=core.OPEN;mujoco.mj_forward(m,d)
 execution_monitor=ExecutionMonitor(m,execution_speed_limit)
 pads=[m.geom(n).id for n in core.PADS];cg=m.geom('red_cube_geom').id
 # A3/H1': live cube half-extent from the actual geom; replaces the hardcoded
 # .0175 (35mm template cube) that this route used for the cube-bottom telemetry.
 cube_half=float(m.geom_size[cg,0])
 if pad_off:
  for g in pads:m.geom_contype[g]=0;m.geom_conaffinity[g]=0
 cube=m.body('red_cube').id;wrist=m.body('right_wrist_yaw_link').id
 def point(data):return pinch_center(m,data,surface_capture,d.xmat[cube].reshape(3,3),opponent)
 if opponent!=1:assert surface_capture
 if surface_capture:assert (kinematic_servo or teleop_fk_reference or discrete_servo) and flat_pinch
 if teleop_fk_reference:assert teleop and pinch_geometry and c2_reference and not policy_aware and not kinematic_servo
 supportids={m.geom(n).id for n in (['table_top','floor'] if direct_table else ['table_top','cube_pedestal_geom','floor'])}
 table_id=m.geom('table_top').id;table_top_z=float(d.geom_xpos[table_id,2]+m.geom_size[table_id,2])
 initial_cube=d.xpos[cube].copy();grasp=initial_cube+offset;initial_base=d.qpos[:3].copy()
 fk=mujoco.MjData(m);geo=mujoco.MjData(m);geo.qpos[:]=d.qpos
 native_curve=[];native_R=[]
 for i in range(len(motion.qpos)):
  geo.qpos[:]=d.qpos;geo.qpos[:3]=[0,0,.74];geo.qpos[3:7]=[1,0,0,0];geo.qpos[controller.aq]=motion.qpos[i,7:]
  mujoco.mj_forward(m,geo);native_curve.append(geo.xpos[wrist].copy());native_R.append(geo.xmat[wrist].reshape(3,3).copy())
 native_curve=np.asarray(native_curve);native_R=np.asarray(native_R)
 if phase_clips:
  lift_z=[]
  for q in phase_motions[phase_stems['lift']].qpos:
   geo.qpos[:]=d.qpos;geo.qpos[:36]=q;mujoco.mj_forward(m,geo);lift_z.append(geo.xpos[wrist,2])
  lift_z=np.maximum.accumulate(lift_z)
  if lift_z[-1]-lift_z[0]<.01:raise RuntimeError('Generated lift has <1cm monotone vertical excursion; reject semantic failure')
  lift_progress=(lift_z-lift_z[0])/(lift_z[-1]-lift_z[0])
 native_frame=int(np.argmax(native_curve[:,0]))
 if native_geometry:
  # Keep the generated near-reach wrist orientation rather than human large
  # wrist rotations. Human calibration contributes ONLY local pinch offset.
  local_offset=lowR.T@offset;lowR=native_R[native_frame].copy();highR=lowR.copy()
  grasp=initial_cube+lowR@local_offset;highpos=grasp+np.array([0,0,.10])
 close_hand=core.CLOSED.copy()
 hand_solver=AdaptiveHand(m,opponent,grip_preload_mm*.001,grip_face_half_mm*.001,cube_half_m=cube_half);hand_goal=close_hand.copy();hand_command=core.OPEN.copy();closure_normal=None;release_hand=None;hand_refs=[]
 if grip_frame_lift:assert adaptive_hand and kinematic_servo
 if lift_height!=.1:assert grip_frame_lift
 if lock_grip:assert grip_frame_lift
 lift_wrist_origin=lift_cube_origin=lift_wrist_R=None;wrist_target=None;wrist_targets=[];setdown_path=None;setdown_dwell=0.;support_forces={};support_history=[]
 if setdown:assert grip_frame_lift and direct_table and not no_grip and not pad_off
 if pinch_geometry:
  assert not teleop or teleop_fk_reference
  close_hand[2]=-.88;grasp=initial_cube.copy();highpos=grasp+np.array([0,0,.10])
  geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo)
  # These are physical pad-frame coordinates, no human calibration endpoints.
  lowR=d.xmat[wrist].reshape(3,3).copy();highR=lowR.copy()
 def native_residual(u):
  if ardy_off:return np.zeros(3)
  x=np.clip(u,0,1)*(len(native_curve)-1);i=int(x);j=min(i+1,len(native_curve)-1);f=x-i
  residual=(1-f)*native_curve[i]+f*native_curve[j]-((1-u)*native_curve[0]+u*native_curve[-1])
  return residual*min(.2,.025/max(np.linalg.norm(residual),1e-12))
 # Human-calibrated route, with an explicit native ARDY redundancy prior.
 phase='SETTLE';phase_start=0.;events=[dict(phase=phase,time_s=0.)];fail=None;approach_planner=None;native_branch_target=None;native_branch_audit=None
 branch_executor=None;approach_timeout=BranchExecution.approach_timeout_seconds if clearance_branch_servo else 26.
 if clearance_approach:assert kinematic_servo and c2_reference and pinch_geometry
 if clearance_native_branch:
  assert clearance_approach and surface_capture and flat_pinch and not ardy_off
 if clearance_branch_servo:assert clearance_native_branch and kinematic_servo and c2_reference
 route_start_pos=d.xpos[wrist].copy();route_start_R=d.xmat[wrist].reshape(3,3).copy()
 reference=neutral.copy();last_goal=reference[arm].copy();bias=np.zeros(7);cart_bias=np.zeros(3);prev_ref=last_goal.copy();last_v=np.zeros(7)
 lo=m.jnt_range[controller.jids[22:29],0]+reference_margin;hi=m.jnt_range[controller.jids[22:29],1]-reference_margin
 smooth_reference=ReferenceFilter(reference[arm],lo,hi,reference_fallback);correction_clipped_cells=0
 inverse_policy=PolicyReference(controller)
 discrete_policy=DiscreteReference(controller)
 servo_updates=0;servo_max_delta=0.
 if policy_aware:assert c2_reference and pinch_geometry and not teleop and not cart_compensation
 if kinematic_servo:assert c2_reference and pinch_geometry and not policy_aware and not teleop and not cart_compensation
 if discrete_servo:assert c2_reference and surface_capture and flat_pinch and not policy_aware and not kinematic_servo and not teleop and not cart_compensation
 endpoint=None
 if endpoint_seed:
  assert (policy_aware or kinematic_servo or teleop_fk_reference or discrete_servo) and flat_pinch
  branch_data=json.loads((root/'out/pinch-feasibility.json').read_text())
  endpoint=branch_data['best']['pregrasp']
  if endpoint_seed_native:
   endpoint=min([r for r in branch_data['records'] if r['target']=='pregrasp' and r['feasible']],key=lambda r:r['native_seed_deviation_rad'])
  assert endpoint['feasible'];endpoint=np.asarray(endpoint['q'])
 alignment_dwell=0.;single_contact_dwell=0.;contact_dwell=0.;hold_start=hold_end=release_start=None;close_reference=None
 rows=[];frames=[];vels=[];references=[];motor_targets=[];raw_motor_targets=[];motor_errors=[];phases=[];calls_ms=[];ik_errors=[];warnings0=np.array([x.number for x in d.warning]);ext=0.
 stamp=runtime_stamp(root,scene,out,controller,motion,phase_motions,sonic_armature,endpoint_seed,selected_profile)
 contact_log=ContactAudit(m,cube,cg,pads,supportids,out,stamp)
 balance_log=BalanceAudit(m,supportids,stamp,out)
 decoded_filter=DecodedArmFilter(m.jnt_range[controller.jids[22:29],0],m.jnt_range[controller.jids[22:29],1],decoded_filter_tau,decoded_filter_speed) if decoded_filter_tau else None
 applied_targets=[];applied_errors=[];actuator_ctrls=[];previous_applied=controller.target.copy();filter_active=False
 actual_velocity_max=np.zeros(7);actual_limit_overshoot=np.zeros(7)
 ardy_prior_effect=[];targetpos=route_start_pos.copy();targetR=route_start_R.copy()
 def change(p,t):
  nonlocal phase,phase_start,route_start_pos,route_start_R,close_reference,closure_normal,hand_command,hand_goal,release_hand,lift_wrist_origin,lift_cube_origin,lift_wrist_R,setdown_path,approach_planner
  phase=p;phase_start=t;events.append(dict(phase=p,time_s=float(t)))
  route_start_pos=d.xpos[wrist].copy();route_start_R=d.xmat[wrist].reshape(3,3).copy()
  if pinch_geometry:
   geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo);route_start_pos=point(geo).copy()
  if p=='CLOSE':
   close_reference=reference[arm].copy();hand_command=d.qpos[hq].copy();hand_goal=close_hand.copy()
   closure_normal=geo.geom_xpos[pads[opponent]]-geo.geom_xpos[pads[0]]
  if p=='RELEASE':release_hand=hand_command.copy()
  if p=='APPROACH' and clearance_approach:approach_planner=ClearanceApproach(d.xpos[wrist],d.xmat[wrist].reshape(3,3),table_top_z,time_limit_s=approach_timeout)
  if p=='SETDOWN':
   landing=lift_cube_origin.copy();landing[0]=table_front+.08;landing[2]=initial_cube[2]-.001
   setdown_path=SetdownPlan(lift_wrist_origin+np.array([0,0,lift_height]),lift_wrist_origin+landing-lift_cube_origin)
  if p=='LIFT':
   lift_wrist_origin=d.xpos[wrist].copy();lift_cube_origin=d.xpos[cube].copy();lift_wrist_R=d.xmat[wrist].reshape(3,3).copy()
   if lock_grip:hand_goal=hand_command.copy()
 def quint(x):
  x=np.clip(x,0,1);return x*x*x*(10-15*x+6*x*x)
 latency=CycleLatency();face_servo_axis=None;face_servo_records=[]
 for step in range(45000):
  if latency.pending is not None:latency.end()
  latency.begin(step,phase)
  t=step*.002;e=t-phase_start
  if clearance_native_branch and phase=='APPROACH' and e>=approach_timeout:
   fail='approach native branch settling timeout' if native_branch_target is not None else 'approach actual wrist clearance timeout';break
  if step%10==0:
   if phase=='SETTLE':
    targetpos=d.xpos[wrist].copy();targetR=d.xmat[wrist].reshape(3,3).copy()
    if pinch_geometry:
     geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo);targetpos=point(geo).copy()
   elif phase=='APPROACH':
    # Nominal joint interpolation is converted to Cartesian path before IK.
    u=quint(e/10);geo.qpos[:]=d.qpos;geo.qpos[:3]=[0,0,.74];geo.qpos[3:7]=[1,0,0,0];geo.qpos[controller.aq]=neutral
    geo.qpos[aq]=(1-u)*neutral[arm]+u*core.SAFE;mujoco.mj_forward(m,geo)
    endpos=geo.xpos[wrist].copy();endR=geo.xmat[wrist].reshape(3,3).copy()
    targetpos=(1-u)*route_start_pos+u*endpos;targetR=rotation_blend(route_start_R,endR,u)
    if native_geometry or pinch_geometry:
     targetpos=(1-u)*route_start_pos+u*highpos+native_residual(u);targetR=rotation_blend(route_start_R,highR,u)
   elif phase=='PREGRASP':
    u=quint(e/12);targetpos=(1-u)*route_start_pos+u*highpos;targetR=rotation_blend(route_start_R,highR,u)
    if native_geometry or pinch_geometry:targetpos+=native_residual(u)
   elif phase in ['DESCEND','ALIGN','CLOSE']:
    u=quint(e/8) if phase=='DESCEND' else 1.;targetpos=(1-u)*highpos+u*grasp;targetR=rotation_blend(highR,lowR,u)
   elif phase=='LIFT':
    u=quint(e/8)
    if phase_clips and not ardy_off:u=float(np.interp(np.clip(e/8,0,1),np.linspace(0,1,len(lift_progress)),lift_progress))
    targetpos=(1-u)*grasp+u*highpos;targetR=rotation_blend(lowR,highR,u)
   else:targetpos=highpos.copy();targetR=highR.copy()
   wrist_target=None
   if phase=='APPROACH' and approach_planner is not None:
    geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo)
    approach_target=approach_planner.update(e,float(d.xpos[wrist,2]),point(geo),highpos)
    wrist_target=approach_target['wrist_target']
    if wrist_target is not None:targetR=approach_target['rotation']
    else:targetpos=approach_target['pad_target']
    if clearance_native_branch and approach_target['clearance_passed'] and native_branch_target is None:
     branch_tic=time.perf_counter()
     try:
      native_branch_target,native_branch_audit=select_native_branch(m,d,aq,av,hq,close_hand,highpos.copy(),d.xmat[cube].reshape(3,3).copy(),motion.qpos[:,29:36],motion.qpos[native_frame,29:36],opponent,ik,pinch_center,face_alignment=branch_face_alignment,hand_preload_m=grip_preload_mm*.001 if branch_face_alignment else .0005,hand_face_half_m=grip_face_half_mm*.001 if branch_face_alignment else .015,coverage=branch_coverage,grasp_center=(d.xpos[cube].copy() if branch_coverage else None))
     except ValueError as error:native_branch_audit=getattr(error,'audit',None);fail='native branch static search rejected: '+str(error);break
     native_branch_audit.update(branch_search_wall_s=float(time.perf_counter()-branch_tic),selected_time_s=float(d.time),selected_source_npz=motion.audit['source_npz'],selected_source_npz_sha256=motion.audit['source_npz_sha256'],actual_clearance_qualified_before_search=True,actual_wrist_z_at_search_m=float(d.xpos[wrist,2]))
     if clearance_branch_servo:branch_executor=BranchExecution(d.time,native_branch_target)
     if face_aligned_servo:
      fk.qpos[:]=d.qpos;fk.qpos[aq]=native_branch_target;fk.qpos[hq]=close_hand;mujoco.mj_forward(m,fk)
      face_vector=fk.geom_xpos[pads[opponent]]-fk.geom_xpos[pads[0]];face_vector[2]=0.
      if np.linalg.norm(face_vector)<.005:fail='selected grasp face direction degenerate';break
      face_servo_axis=int(np.argmax(abs(d.xmat[cube].reshape(3,3).T@face_vector)))
   if grip_frame_lift and phase in ['LIFT','HOLD','SETDOWN','RELEASE','SETTLE_RELEASE']:
    progress=u if phase=='LIFT' else 1.
    targetpos=lift_cube_origin+np.array([0,0,lift_height*progress])
    wrist_target=lift_wrist_origin+np.array([0,0,lift_height*progress]);targetR=lift_wrist_R.copy()
    if setdown_path is not None:
     wrist_target=setdown_path.evaluate(e if phase=='SETDOWN' else setdown_path.duration_s)[0]
     targetpos=lift_cube_origin+wrist_target-lift_wrist_origin
   if pinch_geometry and phase in ['DESCEND','ALIGN','CLOSE']:
    grasp=d.xpos[cube].copy() # simulator-state coordinate input, explicitly not vision
    if phase in ['ALIGN','CLOSE']:targetpos=grasp.copy()
    else:
     u=quint(e/8);targetpos=(1-u)*highpos+u*grasp
   prior=s.DEFAULT_ANGLES[arm].copy() if ardy_off else motion.sample(np.array([min(motion.times[-1],max(0,t-2)/10)]))[0][0,22:29]
   if phase_clips and not ardy_off:
    stem=phase_stems['lift'] if phase=='LIFT' else phase_stems['hold'] if phase in ['HOLD','SETDOWN'] else phase_stems['release'] if phase in ['RELEASE','SETTLE_RELEASE'] else None
    if stem:
     clip=phase_motions[stem];prior=clip.sample(np.array([min(clip.times[-1],e*.5)]))[0][0,22:29];phase_consumed.add(stem)
   if cart_compensation and pinch_geometry:
    if phase in ['ALIGN','CLOSE']:targetpos=d.xpos[cube].copy()
    if phase in ['ALIGN','CLOSE','LIFT','HOLD']:
     geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo)
     delta=.02*.8*(targetpos-point(geo));cart_bias+=np.clip(delta,-.0005,.0005)
     cart_bias*=min(1,.06/max(np.linalg.norm(cart_bias),1e-12))
   fk.qpos[:]=d.qpos
   if pinch_geometry:fk.qpos[hq]=close_hand
   goal=(last_goal.copy() if policy_aware or kinematic_servo or discrete_servo else ik(m,fk,aq,av,targetpos+cart_bias,targetR,last_goal,prior,weight,pinch_geometry,flat_pinch,surface_capture,d.xmat[cube].reshape(3,3),opponent)) if phase!='SETTLE' else neutral[arm].copy()
   if endpoint_seed and phase=='APPROACH' and not clearance_approach:goal=endpoint.copy()
   branch_servo_active=bool(branch_executor is not None and phase=='APPROACH' and branch_executor.servo_enabled(d.time))
   if native_branch_target is not None and phase=='APPROACH' and not branch_servo_active:goal=native_branch_target.copy()
   if freeze_close and phase=='CLOSE':goal=close_reference.copy()
   last_goal=goal.copy()
   fk.qpos[aq]=goal;mujoco.mj_forward(m,fk);ik_errors.append([np.linalg.norm(targetpos-(point(fk) if pinch_geometry else fk.xpos[wrist])),np.linalg.norm(rot_error(targetR,fk.xmat[wrist].reshape(3,3)))])
   if compensation and phase!='SETTLE' and not policy_aware and not kinematic_servo and not teleop_fk_reference and not discrete_servo:bias=np.clip(bias+.02*.6*(goal-d.qpos[aq]),-.25,.25)
   rawref=goal+bias
   # Bound reference speed independently of IK; this never changes actual qpos.
   refarm=prev_ref+np.clip(rawref-prev_ref,-.012,.012)
   lo=m.jnt_range[controller.jids[22:29],0]+reference_margin;hi=m.jnt_range[controller.jids[22:29],1]-reference_margin
   refarm=np.clip(refarm,lo,hi);v=np.clip((refarm-prev_ref)/.02,-.6,.6);last_v=.7*last_v+.3*v
   reference[arm]=refarm;future=np.repeat(reference[None],10,axis=0)
   future[:,22:29]=np.clip(refarm[None]+np.arange(10)[:,None]*.1*last_v[None],lo,hi)
   fv=np.zeros_like(future);fv[:,22:29]=last_v
   if c2_reference:
    safe=np.clip(rawref,lo,hi);correction_clipped_cells+=int(np.count_nonzero(abs(safe-rawref)>1e-10))
    try:qfuture,vfuture=smooth_reference.step(safe)
    except RuntimeError as error:fail='reference feasibility stop: '+str(error);break
    reference[arm]=qfuture[0];future[:]=neutral;future[:,22:29]=qfuture;fv[:]=0;fv[:,22:29]=vfuture;refarm=qfuture[0]
   tic=time.perf_counter()
   if teleop:
    # Official wrist/head point offsets and FULL root inverse transform.
    fk.qpos[:]=d.qpos;fk.qpos[controller.aq]=reference;mujoco.mj_forward(m,fk)
    rootR=s.rotation(d.qpos[3:7]);positions=[];quats=[]
    for i,(bn,ofs) in enumerate([('left_wrist_yaw_link',[.18,-.025,0]),('right_wrist_yaw_link',[.18,.025,0]),('torso_link',[0,0,.35])]):
     b=m.body(bn).id;R=fk.xmat[b].reshape(3,3).copy();pos=fk.xpos[b].copy()
     if i==1 and not teleop_fk_reference:pos=targetpos.copy();R=targetR.copy()
     positions.append(rootR.T@(pos+R@np.array(ofs)-d.qpos[:3]))
     quat=np.zeros(4);mujoco.mju_mat2Quat(quat,(rootR.T@R).reshape(-1));quats.append(quat)
    controller.step_teleop(d,future,fv,np.tile([1.,0,0,0],(10,1)),np.asarray(positions),np.asarray(quats))
   else:controller.step_policy(d,future,fv,np.tile([1.,0,0,0],(10,1)))
   calls_ms.append(1000*(time.perf_counter()-tic));prev_ref=refarm.copy()
   if policy_aware and step%100==0 and phase!='SETTLE' and not (endpoint_seed and phase=='APPROACH'):
    anchor=refarm.copy() if inverse_anchor else last_goal
    last_goal=inverse_policy.update(d,anchor,prior,targetpos,close_hand,flat_pinch,weight,inverse_incremental)
   if kinematic_servo and step%100==0 and phase!='SETTLE' and not (endpoint_seed and phase=='APPROACH' and not clearance_approach) and not (native_branch_target is not None and phase=='APPROACH' and not branch_servo_active) and not (freeze_close and phase=='CLOSE') and not (freeze_hold_servo and phase=='HOLD'):
    fk.qpos[:]=d.qpos;fk.qpos[hq]=close_hand
    servo_prior=native_branch_target if branch_servo_active else prior
    face_active=bool(face_aligned_servo and phase in ['PREGRASP','DESCEND','ALIGN','CLOSE'])
    if face_active:
     assert face_servo_axis is not None and wrist_target is None and len(face_servo_records)<450
     try:desired_q=face_ik(m,fk,aq,av,targetpos,targetR,d.qpos[aq].copy(),servo_prior,0.,True,True,True,d.xmat[cube].reshape(3,3),opponent,cube_axis=face_servo_axis)
     except ValueError as error:fail='face-aligned servo rejected: '+str(error);break
    else:desired_q=ik(m,fk,aq,av,wrist_target if wrist_target is not None else targetpos,targetR,d.qpos[aq].copy(),servo_prior,weight,wrist_target is None,flat_pinch if wrist_target is None else False,surface_capture if wrist_target is None else False,d.xmat[cube].reshape(3,3),opponent)
    cap=postcapture_servo_cap if phase in ['LIFT','HOLD','SETDOWN','RELEASE','SETTLE_RELEASE'] else .06
    delta=desired_q-d.qpos[aq];delta*=min(1.,cap/max(abs(delta).max(),1e-12))
    last_goal=np.clip(refarm+delta,lo,hi);servo_updates+=1;servo_max_delta=max(servo_max_delta,float(abs(delta).max()))
    if face_active:face_servo_records.append(dict(time_s=float(d.time),phase=phase,cube_axis=face_servo_axis,target_m=targetpos.tolist(),actual_arm_q=d.qpos[aq].tolist(),desired_arm_q=desired_q.tolist(),reference_correction_rad=delta.tolist()))
    if branch_servo_active:last_goal=branch_executor.correction(refarm,d.qpos[aq],desired_q,lo,hi)
   if discrete_servo and step%100==0 and phase!='SETTLE' and not (endpoint_seed and phase=='APPROACH') and not (freeze_close and phase=='CLOSE'):
    fk.qpos[:]=d.qpos;fk.qpos[hq]=close_hand
    desired_q=ik(m,fk,aq,av,targetpos,targetR,d.qpos[aq].copy(),prior,weight,True,True,True,d.xmat[cube].reshape(3,3),opponent)
    last_goal=discrete_policy.update(d,refarm,desired_q,prior,targetpos,close_hand,d.xmat[cube].reshape(3,3),opponent,not discrete_absolute)
   # Native source influence is evidenced by the IK/reference, not claimed necessary.
   ardy_prior_effect.append(float(np.linalg.norm(prior-goal)))
  applied_damping=lift_damping if phase in ['LIFT','HOLD'] else 1.
  applied_gain=postcapture_arm_gain if postcapture_arm_gain and phase in ['LIFT','HOLD'] else arm_gain
  applied_target=controller.target.copy()
  if decoded_filter is not None and phase in ['LIFT','HOLD','RELEASE','SETTLE_RELEASE']:
   if not filter_active:decoded_filter.reset(previous_applied[22:29]);filter_active=True
   applied_target[22:29]=decoded_filter.step(controller.target[22:29])
  d.ctrl[:29]=controller.torques(d,applied_gain,gravity_arm_scale,applied_damping,actuator_target=applied_target if filter_active else None)
  previous_applied=applied_target.copy();applied_errors.append(d.qpos[aq]-applied_target[22:29])
  actual_velocity_max=np.maximum(actual_velocity_max,abs(d.qvel[av]))
  limits=m.jnt_range[controller.jids[22:29]];actual_limit_overshoot=np.maximum(actual_limit_overshoot,np.maximum(limits[:,0]-d.qpos[aq],d.qpos[aq]-limits[:,1]))
  motor_errors.append(d.qpos[aq]-controller.target[22:29])
  hand=core.OPEN if phase in ['SETTLE','APPROACH','PREGRASP','DESCEND','ALIGN','SETTLE_RELEASE'] else core.blend(core.OPEN,close_hand,e/close_seconds) if phase=='CLOSE' else core.blend(close_hand,core.OPEN,e) if phase=='RELEASE' else close_hand
  if no_grip:hand=core.OPEN
  if adaptive_hand and not no_grip:
   if phase in ['CLOSE','LIFT','HOLD','SETDOWN']:
    if not (lock_grip and phase in ['LIFT','HOLD','SETDOWN']) and (step%50==0 or hand_solver.calls==0):
     try:hand_goal=hand_solver.solve(d,d.xpos[cube].copy(),d.xmat[cube].reshape(3,3),hand_goal,closure_normal,table_top_z if finger_table_clearance_mm else None,finger_table_clearance_mm*.001)
     except ValueError as error:fail='finger table-clearance planning rejected: '+str(error);break
    hand_command+=np.clip(hand_goal-hand_command,-.003,.003);hand=hand_command.copy()
   elif phase=='RELEASE':hand=core.blend(release_hand,core.OPEN,e)
  kp,kd=core.gains()
  active_finger_gain=finger_gain if phase in ['CLOSE','LIFT','HOLD','SETDOWN'] else 1.
  d.ctrl[hands]=finger_torques(hand,d.qpos[hq],d.qvel[hv],kp[core.HAND],kd[core.HAND],m.actuator_ctrlrange[hands],opponent,active_finger_gain)
  ext=max(ext,float(abs(d.xfrc_applied).max()),float(abs(d.qfrc_applied).max()))
  if substep==1:mujoco.mj_step(m,d)
  else:
   for _w4c_sub in range(substep):mujoco.mj_step(m,d)
  execution_monitor.step(d,phase)
  forces=np.zeros(3);support=0.;support_forces={g:0. for g in supportids}
  contact_log.begin(d,phase,step)
  for k in range(d.ncon):
   c=d.contact[k]
   if cg not in (c.geom1,c.geom2):continue
   other=c.geom2 if c.geom1==cg else c.geom1;f=np.zeros(6);mujoco.mj_contactForce(m,d,k,f)
   contact_log.record(c,k,f)
   if other in pads:forces[pads.index(other)]+=max(0.,f[0])
   if other in supportids:support+=max(0.,f[0]);support_forces[other]+=max(0.,f[0])
  support_history.append(support_forces[table_id])
  contact_log.end()
  balance_log.step(d,phase)
  poserr=np.linalg.norm(targetpos-d.xpos[wrist]);rerr=np.linalg.norm(rot_error(targetR,d.xmat[wrist].reshape(3,3)))
  if pinch_geometry:
   geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo);poserr=np.linalg.norm(targetpos-point(geo));rerr=0.
   if flat_pinch:
    zz=np.array([geo.geom_xpos[m.geom(n).id,2] for n in core.PADS]);rerr=float(zz.max()-zz.min()) # metres, NOT angle
  rot=s.rotation(d.qpos[3:7]);rel=d.xmat[wrist].reshape(3,3).T@(d.xpos[cube]-d.xpos[wrist])
  bottom=d.xpos[cube,2]-cube_half*abs(d.xmat[cube].reshape(3,3)[2]).sum()
  rows.append([d.time,*d.xpos[cube],*rel,*forces,support,bottom,np.linalg.norm(d.qpos[:2]-initial_base[:2]),rot[2,2],poserr,rerr,* (d.qpos[aq]-last_goal)])
  if step%20==0:
   frames.append(d.qpos.copy());vels.append(d.qvel.copy());references.append(reference.copy());phases.append(phase)
   motor_targets.append(controller.target.copy());raw_motor_targets.append((s.DEFAULT_ANGLES+controller.last_action[s.M2I]*s.ACTION_SCALE).copy())
   applied_targets.append(applied_target.copy());actuator_ctrls.append(d.ctrl.copy())
   hand_refs.append(hand.copy())
   wrist_targets.append(wrist_target.copy() if wrist_target is not None else np.full(3,np.nan))
  if not np.isfinite(d.qpos).all() or d.qpos[2]<.55 or rot[2,2]<.65:fail='fall/nonfinite';break
  if phase=='SETTLE' and e>=2:change('APPROACH',d.time)
  elif phase=='APPROACH':
   if approach_planner is None and e>=10:change('PREGRASP',d.time)
   elif approach_planner is not None:
    if approach_planner.passed_time is not None and e>=approach_planner.passed_time+6:
     ready=True
     if clearance_native_branch:
      geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo)
      ready=np.linalg.norm(point(geo)-highpos)<.025 and np.max(abs(d.qvel[av]))<.2
      if branch_executor is not None:ready=branch_executor.observe(d.time,float(np.linalg.norm(point(geo)-highpos)),float(np.max(abs(d.qvel[av]))))
     if ready:change('PREGRASP',d.time)
    elif e>=approach_timeout:fail='approach transition timeout after wrist clearance' if approach_planner.passed_time is not None else 'approach actual wrist clearance timeout';break
  elif phase=='PREGRASP' and e>=12:change('DESCEND',d.time)
  elif phase=='DESCEND' and e>=8:change('ALIGN',d.time)
  elif phase=='ALIGN':
   near_contact=contact_close and (forces>.05).any() and poserr<.035 and rerr<(.015 if flat_pinch else .10)
   aligned=poserr<capture_radius and rerr<(.012 if flat_pinch else .10) and abs(d.qvel[av]).max()<.15
   alignment_dwell=alignment_dwell+.002 if aligned else 0
   single_contact_dwell=single_contact_dwell+.002 if near_contact else 0
   if alignment_dwell>=.2 or single_contact_dwell>=contact_entry_dwell:change('CLOSE',d.time)
   elif e>max(align_seconds,12 if cart_compensation else 8):fail='alignment timeout';break
  elif phase=='CLOSE':
   contact_dwell=contact_dwell+.002 if (forces>.1).sum()>=2 else 0
   if e>=close_seconds and (contact_dwell>=.2 or no_grip or pad_off):change('LIFT',d.time)
   elif e>5:fail='two-finger contact timeout';break
  elif phase=='LIFT' and e>=8:change('HOLD',d.time);hold_start=d.time
  elif phase=='HOLD' and e>=2:
   hold_end=d.time;change('SETDOWN' if setdown else 'RELEASE',d.time)
   if not setdown:release_start=d.time
  elif phase=='SETDOWN':
   arrived=support_forces[table_id]>.05 and np.linalg.norm(d.xpos[cube,:2]-np.array([table_front+.08,lift_cube_origin[1]]))<.025
   setdown_dwell=setdown_dwell+.002 if arrived else 0.
   if e>=8 and setdown_dwell>=.2:change('RELEASE',d.time);release_start=d.time
   elif e>12:fail='contact-qualified table-return timeout';break
  elif phase=='RELEASE' and e>=1:change('SETTLE_RELEASE',d.time)
  elif phase=='SETTLE_RELEASE' and e>=3:break
 else:fail='90s horizon exhausted'
 if latency.pending is not None:latency.end()
 rows=np.asarray(rows);lift=rows[:,3]-initial_cube[2];contacts=(rows[:,7:10]>.01).sum(axis=1)
 hold=(rows[:,0]>(hold_start or 1e9)+.02)&(rows[:,0]<=(hold_end or -1));h=rows[hold];release=rows[rows[:,0]>(release_start or 1e9)+2]
 slip=float(np.max(np.linalg.norm(h[:,4:7]-h[0,4:7],axis=1))) if len(h) else 1e9
 warnings=(np.array([x.number for x in d.warning])-warnings0).tolist()
 gates=dict(completed=fail is None,hold_7cm=len(h)>0 and lift[hold].min()>=.07,two_fingers=len(h)>0 and contacts[hold].min()>=2,
            no_support=len(h)>0 and h[:,10].max()<.001,clearance_4cm=len(h)>0 and (h[:,11]-table_top_z).min()>=.04,
            slip_1cm=slip<.01,release_drop_6cm=len(h)>0 and len(release)>0 and h[-1,3]-release[:,3].min()>=.06,
            final_supported=rows[-1,10]>.05,final_fingers_off=contacts[-1]==0,no_external=ext==0,no_warnings=not any(warnings),upright=rows[:,13].min()>.9)
 assert stamp==runtime_stamp(root,scene,out,controller,motion,phase_motions,sonic_armature,endpoint_seed,selected_profile),'Runtime source/model drift'
 contact_audit=contact_log.finish(hold_start,hold_end)
 legacy_gates={k:bool(v) for k,v in gates.items()}
 balance_audit=balance_log.finish(hold_start,hold_end)
 if not fixed_base:
  for k in ['no_table_rest_in_hold','no_nonfoot_floor_support_in_hold','feet_supported_in_hold']:gates[k]=balance_audit[k]
 gates['fingertip_only_robot_contacts_in_hold']=contact_audit['fingertip_only_robot_contacts_in_hold']
 if direct_table:gates['final_table_supported']=table_supported_gate(support_history)
 execution_audit=execution_monitor.finish()
 if strict_execution:
  gates['actual_arm_speed_within_limit']=execution_audit['actual_arm_speed_within_limit']
  gates['actual_body_limits_within_2mrad']=execution_audit['actual_body_limits_within_2mrad']
  gates['no_robot_table_contact_full_task']=balance_audit['robot_table_all_max_normal_N']<.001
 result=dict(runtime_stamp=stamp,success=all(bool(v) for v in gates.values()),gates={k:bool(v) for k,v in gates.items()},
             gate_definition_version=5 if strict_execution else 4 if direct_table else 2 if fixed_base else 3,legacy_success=all(legacy_gates.values()),legacy_gates=legacy_gates,contact_audit_summary={k:contact_audit[k] for k in ['raw_contact_rows','all_steps','hold_steps','hold_sample_count','fingertip_only_robot_contacts_in_hold']},balance_audit_summary={k:v for k,v in balance_audit.items() if k not in ['runtime_stamp','columns']},
             execution_audit=execution_audit,strict_execution_gate_enabled=strict_execution,neutral_shoulder_offset_rad=neutral_shoulder_offset,neutral_body_reference=neutral.tolist(),neutral_stance_definition='Explicit simulation initialization and SONIC input neutral shoulder pitch offset on both arms; left offset held as neutral reference, right follows existing ARDY/task retargeting. Original official decoded motor targets remain untouched. Not a pure initialization-only counterfactual.',clearance_approach=approach_planner.audit() if approach_planner is not None else None,post_clearance_native_branch_enabled=clearance_native_branch,post_clearance_native_branch=native_branch_audit,
             setdown_enabled=setdown,setdown_plan=setdown_path.audit() if setdown_path is not None else None,setdown_rule='After HOLD, explicit C2 wrist scaffold toward cube x=table_front+80mm and original table height; retain independent grip until table load>.05N and XY error<25mm for200ms after8s, timeout12s; no object weld/state writes' if setdown else None,final_support_by_geom_N={m.geom(g).name:float(force) for g,force in support_forces.items()},final_table_min_force_last100ms_N=float(min(support_history[-50:])),
             kind=('ARDY selected reach shape/posture -> geometric pinch retargeting -> official SONIC '+('pelvis-fixtured' if fixed_base else 'free-base')+' body control + separate contact-gated fingers; no human grasp endpoint joints' if pinch_geometry else 'SONIC teleop-mode calibrated geometry diagnostic; native ARDY arm prior NOT consumed by teleop input' if teleop else 'HYBRID calibrated Cartesian route + selected ARDY posture prior -> official SONIC body control + contact-gated fingers'),
             hold_support_contact_gates_passed=bool(not fixed_base and all(balance_audit[k] for k in ['no_table_rest_in_hold','no_nonfoot_floor_support_in_hold','feet_supported_in_hold'])),com_cop_stability_validated=False,release_height_drop_definition='HOLD end minus late RELEASE/SETTLE_RELEASE cube height; includes prior controlled SETDOWN when enabled, not an isolated free-fall distance',
             ardy_arm_prior_consumed_by_sonic=bool(not ardy_off and (not teleop or teleop_fk_reference)),native_geometry=native_geometry,pinch_geometry=pinch_geometry,native_orientation_frame=native_frame,
             ardy_input_representation='FK of ARDY-shape/posture-conditioned reference -> official three-point VR position/orientation fields; G1 upper joint fields unused' if teleop_fk_reference else 'G1 joint reference' if not teleop else 'calibrated VR-only legacy diagnostic (no ARDY arm prior)',teleop_fk_reference=teleop_fk_reference,
             native_path_consumed_by_sonic=bool(not ardy_off and (native_geometry or pinch_geometry)),ardy_off=ardy_off,ardy_off_definition='disable native path residual, all native arm priors and generated phase timing; substitute neutral prior and quintic task lift; geometry/table/SONIC/fingers unchanged' if ardy_off else None,native_derived_endpoint_seed_held_constant_for_ablation=bool(ardy_off and endpoint_seed_native and not clearance_approach),
             native_ardy_grasp_established=False,human_calibration_used=not pinch_geometry,ardy_nullspace_weight=weight,source=motion.audit,motion_profile=selected_profile.audit() if selected_profile is not None else None,
             position_error_metric=('index' if opponent==1 else 'middle')+'-pad physical surface contact frame' if surface_capture else 'closed-hand FK thumb/index midpoint' if pinch_geometry else 'wrist frame',surface_capture=surface_capture,opposing_pad=core.PADS[opponent],close_command_duration_s=close_seconds,
             flat_pinch=flat_pinch,orientation_error_metric='closed-hand FK pad vertical spread in METRES' if flat_pinch else 'wrist rotation rad',
             c2_reference=c2_reference,reference_filter=smooth_reference.audit() if c2_reference else None,correction_clipped_cells=correction_clipped_cells,
             policy_aware_reference=policy_aware,policy_reference=inverse_policy.audit() if policy_aware else None,
             discrete_reference_servo=discrete_servo,discrete_reference=discrete_policy.audit() if discrete_servo else None,
             endpoint_branch_seed=bool(endpoint_seed and not clearance_approach),endpoint_branch_loaded=endpoint_seed,
             endpoint_seed_selection='legacy minimum per-branch OWN-seed deviation; not a common distance to selected ARDY input' if endpoint_seed_native else 'minimum geometric residual',
             inverse_reference_anchor='current executed SONIC input reference' if inverse_anchor else 'unexecuted accumulated reference goal',
             inverse_reference_linearization='actual pose + decoded motor target increment' if inverse_incremental else 'absolute decoded motor target FK',
             kinematic_outer_servo=dict(enabled=kinematic_servo,updates=servo_updates,max_reference_increment_rad=servo_max_delta,rate_hz=5,motor_target_override=False,kind='closed-hand actual FK IK delta added to current SONIC input reference'),
             base_fixture=fixed_base,fixture_constraint='pelvis-to-world only; cube is NEVER welded' if fixed_base else None,free_base_exercised=not fixed_base,whole_body_balance_validated=False,full_task_com_cop_validated=False,balance_validation_definition='HOLD support contacts audited separately; full-task COM/COP stability margins are not validated',
             right_arm_pd_kp_scale=arm_gain,right_arm_pd_kd_scale=float(np.sqrt(arm_gain)),decoder_targets_unchanged_by_PD_tuning=True,
             lift_only_right_arm_damping_scale=lift_damping,right_arm_pd_kd_definition='sqrt(kp scale) times independent damping scale during LIFT/HOLD; factory damping elsewhere',
             postcapture_arm_pd_gain_scale=postcapture_arm_gain or arm_gain,postcapture_pd_gain_scope='LIFT/HOLD only; raw official decoded targets unchanged',postcapture_outer_servo_increment_cap_rad=postcapture_servo_cap,hold_outer_servo_frozen=freeze_hold_servo,
             right_arm_gravity_feedforward_scale=gravity_arm_scale,actuator_gravity_adapter_not_factory_sonic=gravity_arm_scale!=0,
             joint_reference_error_definition='actual arm minus virtual SONIC input reference; not necessarily decoder motor setpoint',
             object_localization='simulator-state coordinates during DESCEND/ALIGN/CLOSE; not vision',
             direct_table=direct_table,table_top_z_m=table_top_z,object_support='broad table, no pedestal' if direct_table else '35mm-wide riser on table',
             table_front_x_m=float(d.geom_xpos[table_id,0]-m.geom_size[table_id,0]),table_back_x_m=float(d.geom_xpos[table_id,0]+m.geom_size[table_id,0]),table_placement_adaptation=bool(direct_table and table_front!=.23),table_placement_definition='only broad table x front changed, back=.87 and top=.757 fixed; cube initial pose/mass/friction and collision masks unchanged; environment placement counterfactual, not algorithm improvement',
             adaptive_hand_controller=adaptive_hand,adaptive_hand=hand_solver.audit() if adaptive_hand else None,hand_reference_speed_limit_rad_s=1.5 if adaptive_hand else None,grip_preload_mm=grip_preload_mm,grip_preload_adaptation=bool(adaptive_hand and grip_preload_mm!=.5),grip_face_half_mm=grip_face_half_mm,independent_finger_kp_gain=finger_gain,independent_finger_kd_gain=float(np.sqrt(finger_gain)),finger_gain_scope='thumb and selected opposing finger during CLOSE/LIFT/HOLD and optional SETDOWN; original actuator limits and passive joint physics unchanged; not SONIC body gain',
             grip_frame_lift=grip_frame_lift,post_capture_body_objective='full wrist pose translated vertically from actual capture pose; orientation held' if grip_frame_lift else 'closed recipe contact-frame position and flat heights',
             lock_grip=lock_grip,locked_grip_definition='hold the captured finger motor commands, NOT an object constraint or weld' if lock_grip else None,
             sonic_armature=sonic_armature,body_armature_runtime=m.dof_armature[controller.av].tolist(),passive_free_diagnostic=passive_free,passive_free_definition='zero passive BODY joint damping/friction only; a diagnostic assumption, NOT claimed full official model parity' if passive_free else None,
             cartesian_compensation=cart_compensation,final_cart_bias_m=cart_bias.tolist(),phase_clips_loaded=phase_clips,
             preclosure_capture_radius_m=capture_radius,final_success_gates_unchanged=False,success_gate_change='v2 non-pad cube contacts; v3 free-base HOLD feet/no table/nonfoot floor; v4 actual TABLE support final100ms; optional v5 actual arm speed<=declared limit, body soft-limit overshoot<=2mrad and no robot-table load full task; legacy_gates preserved',
             preclosure_contact_close_enabled=contact_close,preclosure_contact_rule='one pad >.05N AND capture-point error<35mm AND flat spread<15mm' if contact_close else None,preclosure_contact_dwell_s=contact_entry_dwell,freeze_reference_during_close=freeze_close,alignment_time_limit_s=align_seconds,
             phase_clips_consumed=sorted(phase_consumed),generated_lift_timewarp=f'positive vertical excursion normalized to {lift_height*100:g}cm, monotone accumulated; explicit task retargeting' if phase_clips and not ardy_off else None,requested_postcapture_lift_height_m=lift_height,
             body_action_override=False,no_grip=no_grip,pad_off=pad_off,compensation=compensation,teleop_mode=teleop,fail_reason=fail,events=events,
             duration_s=d.time,model_load_s=load_s,wall_s=time.monotonic()-start,max_lift_m=float(lift.max()),hold_min_lift_m=float(lift[hold].min()) if len(h) else -1.,
             hold_slip_m=slip,hold_min_contact_bodies=int(contacts[hold].min()) if len(h) else 0,max_drift_m=float(rows[:,12].max()),min_up_z=float(rows[:,13].min()),
             final_wrist_position_error_m=float(rows[-1,14]),
             **({'final_pad_vertical_spread_m':float(rows[-1,15])} if flat_pinch else {'final_wrist_rotation_error_rad':float(rows[-1,15])}),
             right_arm_tracking_rms_rad=float(np.sqrt(np.mean(rows[:,16:23]**2))),max_ik_position_error_m=float(np.max(np.asarray(ik_errors)[:,0])),
             actual_to_decoded_motor_target_rms_rad=float(np.sqrt(np.mean(np.asarray(motor_errors)**2))),
             decoded_motor_filter=decoded_filter.audit() if decoded_filter is not None else None,decoded_motor_filter_scope='right arm after capture; includes release; official raw action/history and non-arm targets unchanged' if decoded_filter is not None else None,
             actual_to_applied_motor_target_rms_rad=float(np.sqrt(np.mean(np.asarray(applied_errors)**2))),actual_arm_velocity_per_joint_max_rad_s=actual_velocity_max.tolist(),actual_arm_limit_overshoot_per_joint_max_rad=actual_limit_overshoot.tolist(),
             virtual_reference_goal_margin_rad=reference_margin,reference_margin_is_task_adaptation=reference_margin!=.002,
             final_actual_arm_rad=d.qpos[aq].tolist(),final_decoded_motor_target_rad=controller.target[22:29].tolist(),final_virtual_reference_rad=reference[22:29].tolist(),
             max_reference_bias_rad=float(abs(bias).max()),policy_median_ms=float(np.median(calls_ms)),policy_p95_ms=float(np.percentile(calls_ms,95)),
             user_corrections=0,correction_definition='no interactive user text corrections; preconfigured task geometry/environment, simulator-state object location and lift-height retargeting are NOT counted as zero human setup',
             peak_external_force=ext,warnings=warnings,sonic=controller.audit(),scene=str(scene))
 if ardy_off:result['kind']='COUNTERFACTUAL: neutral arm prior + geometry/quintic task lift -> official SONIC + same fingers; legacy endpoint branch loaded but not consumed' if clearance_approach else 'COUNTERFACTUAL: neutral arm prior + geometry/quintic task lift -> official SONIC + same fingers; legacy endpoint seed held constant if enabled'
 result['post_clearance_branch_servo_enabled']=clearance_branch_servo
 result['post_clearance_branch_servo']=branch_executor.audit() if branch_executor is not None else None
 result['execution_cycle_latency']=latency.audit()
 result['execution_cycle_latency']['actual_physics_steps']=len(rows)
 result['execution_cycle_latency']['aborted_iterations_without_physics']=latency.completed-len(rows)
 result['finger_table_clearance_mm']=finger_table_clearance_mm
 result['cube_geometry_entry']=dict(requested_edge_mm=cube_edge_mm,live_half_extent_m=cube_half,live_size_xyz_m=m.geom_size[cg].tolist(),mass_kg=float(m.body_mass[m.geom_bodyid[cg]]),initial_body_xyz_m=initial_cube.tolist(),requested_xy_m=[cube_x,cube_y],template='src/g1/scene_grasp_hand.xml',seat_rule='cube bottom rests on the support top z=0.757, so body z = 0.757 + half edge',calibration_frame='source_physics_core.prepare_model() keeps the hardcoded human-demo cube at ([.267,-.118],.7745); deliberately NOT resized or re-seated because it only supplies the local wrist-to-cube-centre offset',hardcoded_half_now_live=['adaptive_hand.py:36','grasp_geometry.py:16','grasp_geometry.py:25','sonic_grasp.py:433 (pre-patch line numbers)'],hardcoded_half_left_alone=['source_physics_core.py:115','source_physics_core.py:120','source_physics_core.py:241','source_physics_core.py:279'],note='edge length is the single variable; geom mass stays at the template 0.020 kg')
 if phys_recipe is not None:result['physics_recipe_w4c']=phys_recipe
 result['branch_face_alignment_enabled']=branch_face_alignment
 result['branch_coverage_enabled']=branch_coverage
 result['branch_coverage_definition']='N2 ordered candidate-COVERAGE schedule implemented in native_branch.py. Every batch is <=7 candidates judged by the UNCHANGED static thresholds (capture1mm/spread2mm/arm margin20mrad/open-table10mm/hand-replan1.5mm). Batch 0 is exactly the baseline batch. Later batches REPLAN the pregrasp reference about the real cube centre and its real rotation (standoff_m, lateral_m, azimuth in the cube frame = approach side / which opposing face pair), add arm-nullspace wrist-orientation variants of the best converged pose of that profile, and sample ARDY source frames more densely than linspace(0,n-1,6). No failure gate, no static threshold and no candidate-count bound is relaxed. Default off; off reproduces the baseline bit-for-bit.'
 result['branch_coverage_attempt_used']=(native_branch_audit or {}).get('coverage',{}).get('attempt_used')
 result['face_aligned_servo']=dict(enabled=face_aligned_servo,cube_axis=face_servo_axis,calls=len(face_servo_records),call_bound=450,iteration_bound_per_call=15,records=face_servo_records,definition='Optional5Hz virtual-input arm servo during PREGRASP/DESCEND/ALIGN/CLOSE; fixes cube face axis selected by the ARDY-seeded branch, zero nullspace prior, same0.06rad reference-correction cap and C2 envelope. No actual-state or body-motor override; default disabled. Not a contact-stability certificate.')
 result['branch_face_alignment_definition']='Optional ARDY-seeded static arm IK adds selected cube-face yaw matching and20.05mrad bounds; hand feasibility uses the actual independent-finger preload/face region. Same seven-source-candidate cap and original static/physical filters; virtual SONIC input only, not native ARDY orientation or motor/state override.'
 result['finger_table_clearance_definition']='Optional finger-IK target height >=table top+pad radius+declared margin, projected inside opposing cube face region. No contact masks/state/torques are overridden; actual solver table gate remains unchanged. Geometry is not a collision-free certificate.'
 with gzip.open(out/'cycle-latency.csv.gz','wt') as f:
  f.write('# runtime_stamp='+json.dumps(stamp)+'\ncycle,cycle_start_phase,wall_ms\n')
  for index,label,ms in latency.cycles:f.write(f'{index},{label},{ms:.9f}\n')
 np.savez_compressed(out/'trajectory.npz',qpos=frames,qvel=vels,body_reference=references,hand_reference=hand_refs,wrist_target=wrist_targets,decoded_motor_target=motor_targets,raw_decoded_motor_target=raw_motor_targets,applied_motor_target=applied_targets,actuator_ctrl=actuator_ctrls,phase=phases,time=rows[::20,0],fps=25,scene=str(scene),runtime_stamp=json.dumps(stamp))
 columns=['time_s','cube_x_m','cube_y_m','cube_z_m','cube_wrist_x_m','cube_wrist_y_m','cube_wrist_z_m','thumb_force_N','index_force_N','middle_force_N','support_force_N','cube_bottom_m','base_xy_drift_m','base_up_z','surface_capture_error_m' if surface_capture else 'closed_center_error_m' if pinch_geometry else 'wrist_position_error_m','pad_vertical_spread_m' if flat_pinch else 'wrist_rotation_error_rad']+['actual_minus_virtual_ref_'+m.joint(int(j)).name+'_rad' for j in controller.jids[22:29]]
 result['telemetry_schema']=dict(path='telemetry.csv.gz',columns=columns,physics_hz=500,format='gzip CSV; 9 significant digits; full result/NPZ floats preserved',finger_contact_white_list=core.PADS)
 with gzip.open(out/'telemetry.csv.gz','wt') as f:
  f.write('# runtime_stamp='+json.dumps(stamp)+'\n# '+','.join(columns)+'\n');np.savetxt(f,rows,delimiter=',',fmt='%.9g')
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ['source','sonic','runtime_stamp']},indent=2));return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--weight',type=float,default=.03);p.add_argument('--no-grip',action='store_true');p.add_argument('--pad-off',action='store_true');p.add_argument('--no-compensation',action='store_true');p.add_argument('--teleop',action='store_true');p.add_argument('--native-geometry',action='store_true');p.add_argument('--pinch-geometry',action='store_true');p.add_argument('--cart-compensation',action='store_true');p.add_argument('--phase-clips',action='store_true');p.add_argument('--capture-radius',type=float,default=.007);p.add_argument('--flat-pinch',action='store_true');p.add_argument('--c2-reference',action='store_true');p.add_argument('--policy-aware',action='store_true');p.add_argument('--endpoint-seed',action='store_true');p.add_argument('--arm-gain',type=float,default=1.)
 p.add_argument('--fixed-base',action='store_true');p.add_argument('--inverse-anchor',action='store_true');p.add_argument('--endpoint-seed-native',action='store_true');p.add_argument('--inverse-incremental',action='store_true');p.add_argument('--kinematic-servo',action='store_true');p.add_argument('--contact-close',action='store_true');p.add_argument('--align-seconds',type=float,default=8.);p.add_argument('--surface-capture',action='store_true');p.add_argument('--contact-entry-dwell',type=float,default=.2);p.add_argument('--freeze-close',action='store_true');p.add_argument('--gravity-arm',type=float,default=0.);p.add_argument('--opponent',choices=['index','middle'],default='index');p.add_argument('--close-seconds',type=float,default=2.);p.add_argument('--teleop-fk-reference',action='store_true');p.add_argument('--discrete-servo',action='store_true');p.add_argument('--discrete-absolute',action='store_true');p.add_argument('--direct-table',action='store_true');p.add_argument('--adaptive-hand',action='store_true');p.add_argument('--grip-frame-lift',action='store_true');p.add_argument('--lock-grip',action='store_true');p.add_argument('--lift-damping',type=float,default=1.);p.add_argument('--sonic-armature',action='store_true');p.add_argument('--passive-free',action='store_true')
 p.add_argument('--decoded-filter-tau',type=float,default=0.);p.add_argument('--decoded-filter-speed',type=float,default=.6);p.add_argument('--reference-margin',type=float,default=.002)
 p.add_argument('--postcapture-arm-gain',type=float,default=0.);p.add_argument('--postcapture-servo-cap',type=float,default=.06);p.add_argument('--freeze-hold-servo',action='store_true');p.add_argument('--lift-height',type=float,default=.1);p.add_argument('--reference-fallback',action='store_true');p.add_argument('--ardy-off',action='store_true');p.add_argument('--table-front',type=float,default=.23)
 p.add_argument('--grip-preload-mm',type=float,default=.5);p.add_argument('--finger-gain',type=float,default=1.);p.add_argument('--setdown',action='store_true');p.add_argument('--grip-face-half-mm',type=float,default=15.)
 p.add_argument('--neutral-shoulder-offset',type=float,default=0.);p.add_argument('--strict-execution',action='store_true');p.add_argument('--execution-speed-limit',type=float,default=2.);p.add_argument('--clearance-approach',action='store_true');p.add_argument('--motion-profile',help='Verified generated four-role manifest, relative to this project evidence root');p.add_argument('--clearance-native-branch',action='store_true');p.add_argument('--clearance-branch-servo',action='store_true');p.add_argument('--finger-table-clearance-mm',type=float,default=0.);p.add_argument('--branch-face-alignment',action='store_true');p.add_argument('--face-aligned-servo',action='store_true');p.add_argument('--branch-coverage',action='store_true',help='N2: ordered cube-driven candidate coverage with per-batch replanning in the static branch search; default off reproduces the baseline exactly')
 p.add_argument('--cube-edge-mm',type=float,default=35.,help='A3: red cube edge length in mm; 35.0 reproduces src/g1/scene_grasp_hand.xml byte-for-byte')
 p.add_argument('--cube-x',type=float,default=.267,help='A3: red cube body x in m; .267 reproduces the template')
 p.add_argument('--cube-y',type=float,default=-.118,help='A3: red cube body y in m; -.118 reproduces the template')
 p.add_argument('--substep',type=int,default=1,help='W4c M2 translation: physics sub-steps per 500Hz control tick (timestep = 0.002/substep); 1 reproduces the baseline exactly')
 p.add_argument('--contact-margin',type=float,default=0.,help='W4c M2 translation: geom margin [m] on cube+pads (isaaclab contact_offset); 0 reproduces the baseline exactly')
 p.add_argument('--solref',nargs=2,type=float,default=None,metavar=('TIMECONST','DAMPRATIO'),help='W4c M2 translation: geom solref on cube+pads; default None keeps the XML values (cube .006 1 / pads .008 1)')
 p.add_argument('--impratio',type=float,default=0.,help='W4c M2 translation: model.opt.impratio; 0 keeps the model default 1')
 a=p.parse_args()
 assert not a.endpoint_seed_native or a.endpoint_seed
 assert not a.inverse_anchor or a.policy_aware
 assert not a.inverse_incremental or a.policy_aware
 assert 0<=a.weight<=.1
 assert .005<=a.capture_radius<=.025
 assert not a.flat_pinch or a.pinch_geometry
 assert 1<=a.arm_gain<=4
 assert 8<=a.align_seconds<=25
 assert .02<=a.contact_entry_dwell<=.2
 assert .25<=a.close_seconds<=2
 assert not a.discrete_absolute or a.discrete_servo
 assert 1<=a.lift_damping<=4
 assert a.decoded_filter_tau==0 or .1<=a.decoded_filter_tau<=1.
 assert .2<=a.decoded_filter_speed<=1.5
 assert .002<=a.reference_margin<=.15
 assert a.postcapture_arm_gain==0 or 1<=a.postcapture_arm_gain<=4
 assert .01<=a.postcapture_servo_cap<=.06
 assert .07<=a.lift_height<=.2
 assert a.lift_height==.1 or a.grip_frame_lift
 assert .23<=a.table_front<=.245
 assert a.table_front==.23 or a.direct_table
 assert np.isfinite(a.grip_preload_mm) and .25<=a.grip_preload_mm<=2.5
 assert a.grip_preload_mm==.5 or a.adaptive_hand
 assert np.isfinite(a.finger_gain) and 1<=a.finger_gain<=3
 assert np.isfinite(a.grip_face_half_mm) and 6<=a.grip_face_half_mm<=15
 assert a.grip_face_half_mm==15 or a.adaptive_hand
 assert np.isfinite(a.neutral_shoulder_offset) and -.2<=a.neutral_shoulder_offset<=.4
 assert np.isfinite(a.execution_speed_limit) and .5<=a.execution_speed_limit<=3.
 assert np.isfinite(a.cube_edge_mm) and 10<=a.cube_edge_mm<=80,'A3: cube edge domain is 10..80mm (W4f widened input domain for the 80mm-cube test)'
 assert a.cube_edge_mm==35 or a.direct_table,'A3: a non-35mm cube needs --direct-table (the template riser is only 35mm wide)'
 assert np.isfinite(a.cube_x) and np.isfinite(a.cube_y),'A3: finite cube xy required'
 options=vars(a).copy();options['compensation']=not options.pop('no_compensation')
 options['gravity_arm_scale']=options.pop('gravity_arm');options['opponent']=1 if options['opponent']=='index' else 2
 run(**options)
