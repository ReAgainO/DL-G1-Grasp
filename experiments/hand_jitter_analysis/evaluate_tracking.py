"""Check wrist orientation, actual reference tracking and effort tradeoffs."""
import os,resource
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from pathlib import Path
import hashlib,json,sys,datetime
sys.path.insert(0,str(Path(__file__).resolve().parent/'plandeps310'))
import numpy as np,mujoco
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parent;OLD=Path('/data/group4/20261009-021611-codex-415484ce');B=Path('/home/group4/group4_dasc7606c')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
wavecount=int(sys.argv[1]);rows=[]
for wi in range(1,wavecount+1):
    evaluation=json.loads((R/'analysis'/f'wave{wi}-evaluation.json').read_text())
    for row in evaluation['rows']:
        if 'success' not in row:continue
        out=R/'out'/row['id'];tr=np.load(out/'dense_trace.npz',allow_pickle=False);stamp=row['runtime_stamp']
        assert sha(out/'result.json')==row['source_result_sha'] and sha(out/'dense_trace.npz')==row['source_dense_sha']
        assert json.loads(str(tr['runtime_stamp_json']))==stamp and stamp['mujoco_version']==mujoco.__version__=='3.2.7'
        m=mujoco.MjModel.from_xml_path(str(out/'scene.xml'));d=mujoco.MjData(m);wrist=m.body('right_wrist_yaw_link').id
        qa=m.jnt_qposadr[m.actuator_trnid[:,0]]
        source=row['config']['source_episode'];plan=json.loads((OLD/'out'/('plan_'+source)/'plan.json').read_text())
        contract=json.loads((out/'episode_contract.json').read_text())
        d.qpos[:]=contract['initial_qpos'];d.qpos[qa[22:29]]=plan['arm'];mujoco.mj_forward(m,d)
        terminal=d.xpos[wrist].copy();terminalR=d.xmat[wrist].reshape(3,3).copy()
        use=(tr['time']>=50.5)&(tr['time']<53);t=tr['time'][use];q=tr['qpos'][use];v=tr['qvel'][use]
        angles=[];angular=[];wristpos=[];rot_error=[];velocity=np.empty(6)
        for qi,vi in zip(q,v):
            d.qpos[:]=qi;d.qvel[:]=vi;mujoco.mj_forward(m,d)
            angles.append(d.xmat[wrist].reshape(3,3).copy());wristpos.append(d.xpos[wrist].copy())
            mujoco.mj_objectVelocity(m,d,mujoco.mjtObj.mjOBJ_BODY,wrist,velocity,0);angular.append(velocity[:3].copy())
            rot_error.append(Rotation.from_matrix(terminalR@angles[-1].T).magnitude())
        angles=Rotation.from_matrix(angles);rv=(angles.mean().inv()*angles).as_rotvec()
        X=np.c_[np.ones(len(t)),t-t[0]];rv-=X@np.linalg.lstsq(X,rv,rcond=None)[0]
        error=np.asarray(wristpos)-(terminal+[0,0,.1])
        arm_tau=tr['ctrl'][use][:,22:29];limits=m.actuator_ctrlrange[22:29]
        raw_error=np.asarray(wristpos)-tr['wrist_pos'][use]
        values={'id':row['id'],'success':row['success'],'source_episode':source,
                'hold_wrist_orientation_detrended_component_rms_deg':float(np.rad2deg(np.sqrt(np.mean(rv**2)))),
                'hold_wrist_angular_velocity_component_rms_rad_s':float(np.sqrt(np.mean(np.asarray(angular)**2))),
                'hold_wrist_goal_error_mean_norm_mm':float(1000*np.mean(np.linalg.norm(error,axis=1))),
                'hold_wrist_goal_error_max_norm_mm':float(1000*np.max(np.linalg.norm(error,axis=1))),
                'hold_wrist_goal_error_mean_vector_mm':(1000*error.mean(axis=0)).tolist(),
                'hold_wrist_orientation_goal_error_mean_deg':float(np.rad2deg(np.mean(rot_error))),
                'hold_arm_effort_rms_Nm':float(np.sqrt(np.mean(arm_tau**2))),
                'hold_arm_effort_limit_fraction':float(np.mean((arm_tau<=limits[:,0]+1e-7)|(arm_tau>=limits[:,1]-1e-7))),
                'stored_xpos_vs_recomputed_qpos_max_mm':float(1000*np.max(np.linalg.norm(raw_error,axis=1))),
                'note':'MuJoCo mj_step stored xpos reflects last FK; renderer recomputes actual recorded qpos; both conventions are identified, not hidden smoothing',
                'runtime_stamp':stamp,'source_dense_sha':row['source_dense_sha']}
        rows.append(values);print(json.dumps({k:values[k] for k in ['id','hold_wrist_goal_error_mean_norm_mm','hold_wrist_orientation_detrended_component_rms_deg','hold_wrist_angular_velocity_component_rms_rad_s','hold_arm_effort_limit_fraction']}),flush=True)
output={'rows':rows,'created':datetime.datetime.now().astimezone().isoformat(),'runtime_stamp':{'mujoco_version':mujoco.__version__,'sys_executable':sys.executable,
        'python_version':sys.version,'dt':.001,'metric_sample_dt_s':.005,'model_sha':{r['id']:r['runtime_stamp']['model_sha'] for r in rows},
        'scene_generator_sha':sha(R/'batch_plan.py'),'library_sha':sha(R/'lib/sonic_v11.py'),'analysis_source_sha':sha(__file__)}}
path=R/'analysis'/('tracking-'+str(wavecount)+'.json')
with path.open('x') as f:json.dump(output,f,indent=2)
with (B/'logs'/R.name/'steps.md').open('a') as f:f.write('\n- Tracking and orientation audit '+str(path)+' SHA='+sha(path)+'\n')
