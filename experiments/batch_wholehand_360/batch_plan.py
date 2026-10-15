"""Finite warm-start retargeting; FK only, never advances physics."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
import sys,json,shutil,argparse
from pathlib import Path
import numpy as np,mujoco
import wholehand_side as w
from scipy.optimize import least_squares
from motion_input import ArdyMotion
R=Path(__file__).resolve().parent

def main(a):
    config=json.loads(Path(a.config).read_text());name=config['id']
    assert name.replace('_','').isalnum()
    out=R/'out'/('plan_'+name);out.mkdir()
    base=json.loads((R/'out/baseline_plan/plan.json').read_text())
    identical=config['xy_m']==[.35,-.18] and config['edge_m']==.08 and config['root_x_m']==0
    if identical:
        for f in ['robot.xml','scene.xml']:shutil.copy2(R/'out/baseline_plan'/f,out/f)
        p=base
        p['retarget']='exact previously verified terminal pose; fresh dynamic run, not trajectory reuse'
        m=mujoco.MjModel.from_xml_path(str(out/'scene.xml'))
    else:
        m,d,bq,hj,hq,armed=w.build(out,config['edge_m'],config['xy_m'],config['mass_kg'])
        d.qpos[0]=config['root_x_m'];mujoco.mj_forward(m,d)
        aq,av,hv,lim,idx,pads,cube,table,bones=w.setup(m,d,bq,hj,hq)
        motion=ArdyMotion(R/'lib/src/original_motions/near_s42.npz');prior=motion.qpos[99,29:36].copy()
        targets=np.tile(d.xpos[m.body('red_cube').id],(3,1));axis=base['best']['axis'];gap=.02
        targets[:,axis]+=[-(config['edge_m']/2+.01+gap),config['edge_m']/2+.01+gap,config['edge_m']/2+.01+gap]
        targets[1,(axis+1)%2]+=.0285;targets[2,(axis+1)%2]-=.0285
        def residual(x,sat):
            d.qpos[idx]=x;mujoco.mj_forward(m,d)
            terms=[((d.geom_xpos[pads]-targets)*1000).ravel(),(x[:7]-prior)*(.15 if sat else .01)]
            if sat:terms.append(np.maximum(.001-w.clearances(m,d,bones,cube,table),0).ravel()*1000)
            return np.concatenate(terms)
        x=np.r_[base['arm'],base['closed_hand']];bounds=(lim[:,0]+.003,lim[:,1]-.003)
        rough=least_squares(lambda v:residual(v,False),x,bounds=bounds,max_nfev=80,diff_step=1e-5)
        fit=least_squares(lambda v:residual(v,True),rough.x,bounds=bounds,max_nfev=100,
                          ftol=1e-8,xtol=1e-8,gtol=1e-8,diff_step=1e-3)
        residual(fit.x,True);gaps=w.clearances(m,d,bones,cube,table)
        error=float(np.linalg.norm(d.geom_xpos[pads]-targets,axis=1).max());wrist=m.body('right_wrist_yaw_link').id
        best={'axis':axis,'seed':'frozen_baseline_warmstart','targets':targets.tolist(),'q':fit.x.tolist(),
              'pad_error_m':error,'min_bone_cube_gap_m':float(gaps[:,0].min()),'min_bone_table_gap_m':float(gaps[:,1].min()),
              'nfev':fit.nfev,'rough_nfev':rough.nfev}
        p={'best':best,'arm':fit.x[:7].tolist(),'closed_hand':fit.x[7:].tolist(),'open_hand':fit.x[7:].tolist(),
           'wrist_pos':d.xpos[wrist].tolist(),'wrist_R':d.xmat[wrist].reshape(3,3).tolist(),
           'edge_m':config['edge_m'],'mass_kg':config['mass_kg'],'pad_gap_m':gap,
           'cube_pos':d.xpos[m.body('red_cube').id].tolist(),'hand_geoms':armed,'ardy_source':motion.audit,'ardy_frame':99,
           'geometry_pass':bool(error<.003 and gaps.min()>=0),'retarget':'one warmstart, 80 rough + 100 SAT evaluations, fixed axis0',
           'scope':'ARDY seven-arm posture prior plus bounded reference-space geometry correction; not fullbody ARDY'}
    p['root_x']=config['root_x_m'];p['trial_config']=config
    p['runtime_stamp']={'mujoco_version':mujoco.__version__,'sys_executable':sys.executable,'python_version':sys.version,
                        'model_sha':{n:w.sha(out/(n+'.xml')) for n in ['robot','scene']},'scene_generator_sha':w.sha(__file__),
                        'library_sha':{'wholehand_side':w.sha(w.__file__),'sonic':w.sha(w.sonic.__file__),
                                       'ardy_npz':p['ardy_source']['source_npz_sha256']},'dt':float(m.opt.timestep)}
    (out/'plan.json').write_text(json.dumps(p,indent=2));print(json.dumps({'id':name,'geometry_pass':p['geometry_pass'],'best':p['best']}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);main(parser.parse_args())
