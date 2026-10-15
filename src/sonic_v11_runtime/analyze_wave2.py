"""Read-only semantic/FK checks; output a new analysis snapshot, no physics steps."""
import json,sys
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
from motion_input import ArdyMotion
root=Path(__file__).resolve().parent;out=root/'out'/('wave2-analysis-'+sys.argv[1]+'.json');assert not out.exists()
scene=root/'src/g1/scene_grasp_hand.xml';m=mujoco.MjModel.from_xml_path(str(scene));d=mujoco.MjData(m)
aq=m.jnt_qposadr[m.actuator_trnid[:29,0]];w=m.body('right_wrist_yaw_link').id
gen=[]
summary=json.loads((root/'out/generated_phases2/summary.json').read_text())
for job in summary['jobs']:
 p=root/'out/generated_phases2'/job['stem'];motion=ArdyMotion(p.with_suffix('.npz'),check_csv=p.with_suffix('.csv'))
 wrist=[];relative=[]
 for frame in motion.qpos:
  d.qpos[:]=0;d.qpos[:36]=frame;d.qpos[-7:]=[.267,-.118,.7745,1,0,0,0];mujoco.mj_forward(m,d)
  wrist.append(d.xpos[w].copy());relative.append(d.xpos[w]-frame[:3])
 wrist=np.asarray(wrist);relative=np.asarray(relative);limits=m.jnt_range[m.actuator_trnid[:29,0]]
 raw=motion.qpos[:,7:];violations=int(((raw<limits[:,0])|(raw>limits[:,1])).sum())
 gen.append(dict(stem=job['stem'],text=job['prompt'],wall_s=job['wall_s'],text_encode_s=job['text_encode_s'],native=motion.audit,
                 native_joint_limit_violations=violations,wrist_world_start=wrist[0].tolist(),wrist_world_end=wrist[-1].tolist(),
                 wrist_world_delta=(wrist[-1]-wrist[0]).tolist(),wrist_relative_delta=(relative[-1]-relative[0]).tolist(),
                 wrist_world_min=wrist.min(axis=0).tolist(),wrist_world_max=wrist.max(axis=0).tolist()))
physics=[]
for name in ['hybrid_sonic01','hybrid_teleop01','native_geometry_g101','native_geometry_teleop01']:
 path=root/'out'/name/'result.json'
 if not path.exists():continue
 r=json.loads(path.read_text());z=np.load(path.parent/'trajectory.npz',allow_pickle=False)
 ref=z['body_reference'][-1,22:29];actual=z['qpos'][-1,aq[22:29]]
 physics.append(dict(name=name,version=r['runtime_stamp']['mujoco_version'],success=r['success'],fail=r['fail_reason'],
                     wrist_pos_error=r['final_wrist_position_error_m'],wrist_rot_error=r['final_wrist_rotation_error_rad'],
                     min_up_z=r['min_up_z'],native_geometry=r.get('native_geometry'),
                     final_reference_arm=ref.tolist(),final_actual_arm=actual.tolist(),final_reference_minus_actual=(ref-actual).tolist(),
                     source_script_sha=r['runtime_stamp']['scene_generator_sha']))
result=dict(generated=gen,physics=physics,textencoder_load_s=summary['textencoder_load_s'],model_load_s=summary['model_load_s'],
            physics_sim_steps=0,native_pose_is_not_executable_grasp=True)
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
